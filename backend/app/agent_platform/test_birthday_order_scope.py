"""Platform14: real order provenance, gates and bank effects; no model calls."""

from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.api.app import ApiConfig, create_app
from app.contracts.bank import BankError, QueryFailure
from app.contracts.common import OperationStatus, SecurityDecisionCode
from app.contracts.platform import TrustedContext
from app.contracts.security import ConfirmationAnswer
from app.modules.cross.birthday_ports import BirthdayPlan
from app.services.mock_bank.verification import AdminContext
from app.storage.database import connect

from .local_demo import build_runtime
from .test_birthday_runtime_wiring import NoopModel
from .test_local_demo import configuration


@pytest.fixture
def open_runtime(tmp_path):
    runtimes = []

    def open_round(round_id="D1"):
        config = configuration(tmp_path).model_copy(update={"demo_round_id": round_id})
        with patch("app.agent_platform.local_demo.ChatOpenAI",
                   return_value=NoopModel(response_mode="none")):
            runtime = build_runtime(config)
        create_app(runtime, ApiConfig(
            secret=config.api_secret.get_secret_value().encode(), admin_key="local-test-admin",
            origins=("http://testserver",), demo_round_id=round_id))
        runtimes.append(runtime)
        return runtime

    yield open_round
    for runtime in runtimes:
        runtime.close()


def task(runtime, suffix, round_id="D1"):
    now = datetime.now(timezone.utc)
    who = TrustedContext(user_id="U1", session_id="S-" + suffix, task_id="T-" + suffix,
                         run_id="R-" + suffix, parent_task_id=None, demo_round_id=round_id)
    runtime.application.create_session(who.session_id, "U1", round_id, now.isoformat(),
                                       (now + timedelta(days=1)).isoformat())
    runtime.application.create_task(who.task_id, "U1", who.session_id, round_id, who.run_id,
        "running", {"capability_name": "cross.start_task", "trace_id": str(uuid4())})
    delivery_ref = "delivery-" + suffix
    runtime.application.store_controlled_detail(delivery_ref, "U1", round_id, who.task_id,
        "delivery", {"recipient_name": "测试收件人", "phone": "13800000000",
                     "address": "测试路1号"}, now.isoformat())
    product = runtime.gateway.list_products(who).products[0]
    item = dict(product_id=product.product_id, amount_fen=product.unit_price_fen,
                merchant_id=product.merchant_id, merchant_name=product.merchant_name,
                name=product.product_name, category=product.category.value)
    plan = BirthdayPlan(payer_account_id="A1", budget_id="order-scope", budget_version=1,
        budget_limit_fen=50000, freeze_amount_fen=50000, delivery_ref=delivery_ref,
        deliver_by=(now + timedelta(days=4)).isoformat(), items=(item,))
    return who, plan, item, runtime.birthday.ports_factory(who)


def authorize(runtime, who, check, execute, *, grant=None):
    asked = check()
    assert asked.decision is SecurityDecisionCode.REQUIRE_CONFIRMATION, asked
    record = runtime.confirmations.get(runtime._context(who, None, None), asked.interaction.record_ref)
    runtime.answer_confirmation(who, ConfirmationAnswer(confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version, choice="approve"))
    if grant is not None:
        grant(record.confirmation_id)
    waiting = execute()
    assert waiting.state == "verify_wait", waiting
    challenge = waiting.verify.record_ref
    code = runtime.gateway.get_demo_code_for_api(who, challenge)
    assert runtime.gateway.verify_code(who, challenge, uuid4(), code).kind == "verified"
    runtime.gateway.start_face(who, challenge, uuid4())
    face = runtime.gateway.verify_face(AdminContext(actor_id="demo-admin", authorized=True,
        demo_round_id=who.demo_round_id, target_user_id=who.user_id), challenge, uuid4(), "passed")
    assert face.kind == "verified" and face.verification_id
    runtime.bind_verification(who, face.verification_id)


def approved(runtime, who, check, execute, *, grant=None):
    authorize(runtime, who, check, execute, grant=grant)
    outcome = execute()
    assert outcome.executed and outcome.state == "completed", outcome
    assert outcome.result.operation_status is OperationStatus.SUCCEEDED
    return outcome.result


def purchase(runtime, who, plan, item, ports):
    frozen = approved(runtime, who, lambda: ports.freeze_check(who, plan),
        lambda: ports.freeze_execute(who, plan),
        grant=lambda ref: ports.grant_release(who, plan, ref))
    ports.bind_freeze(who, plan, str(frozen.operation_id))
    created = approved(runtime, who, lambda: ports.order_check(who, plan, item),
                       lambda: ports.order_execute(who, plan, item))
    return frozen, created.receipt.order.order_id


def money_facts(runtime):
    with closing(connect(runtime.gateway._bank.store.path)) as connection:
        return {name: [tuple(row) for row in connection.execute(f"SELECT * FROM {name} ORDER BY 1")]
                for name in ("accounts", "freezes", "orders", "order_payments",
                             "ledger_entries", "bank_operations")}


def confirmation_count(runtime):
    with closing(connect(runtime.birthday.state.path)) as connection:
        return connection.execute("SELECT COUNT(*) FROM security_confirmations").fetchone()[0]


def assert_denied(runtime, who, plan, item, ports, order_id):
    before, confirmations = money_facts(runtime), confirmation_count(runtime)
    denied = ports.capture_check(who, plan, item, order_id)
    assert denied.decision is SecurityDecisionCode.BLOCK, denied
    assert denied.reason_code == "ACCESS_DENIED" and denied.interaction is None
    result = ports.capture_execute(who, plan, item, order_id)
    assert not result.executed
    assert confirmation_count(runtime) == confirmations
    assert money_facts(runtime) == before
    decisions = [event.payload.decision for event in runtime.audit._events(who.demo_round_id, who.task_id)
                 if event.event_type == "security.decided"]
    assert any(decision.decision is SecurityDecisionCode.BLOCK
               and "ACCESS_DENIED" in decision.reason_codes for decision in decisions)


@pytest.mark.parametrize("foreign_source", ["other_task", "previous_round"])
def test_foreign_order_is_denied_before_confirmation_and_payment(open_runtime, foreign_source):
    runtime = open_runtime()
    source = task(runtime, "source")
    _, foreign_order = purchase(runtime, *source)
    round_id = "D1"
    if foreign_source == "previous_round":
        runtime.close()
        round_id = "D2"
        runtime = open_runtime(round_id)
    target = task(runtime, "target", round_id)
    purchase(runtime, *target)  # A legitimate same-product order is not authority for the foreign one.
    assert_denied(runtime, *target, foreign_order)


@pytest.mark.parametrize("binding", ["unclaimed", "other_task"])
def test_order_requires_its_own_task_creation_claim(open_runtime, binding):
    runtime = open_runtime()
    target = task(runtime, "target")
    who, plan, item, ports = target
    _, own_order = purchase(runtime, *target)
    if binding == "unclaimed":
        changed = replace(plan, deliver_by=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat())
        assert ports.order_check(who, changed, item).decision is SecurityDecisionCode.REQUIRE_CONFIRMATION
    else:
        source = task(runtime, "source")
        _, own_order = purchase(runtime, *source)
        key = "order:" + item["product_id"]
        source_action = runtime.application.get_task("U1", "D1", source[0].task_id).snapshot["birthday_actions"][key]
        saved = runtime.application.get_task("U1", "D1", who.task_id)
        actions = {**saved.snapshot["birthday_actions"], key: source_action}
        runtime.application.update_task("U1", "D1", who.task_id, saved.revision, saved.run_id,
            saved.status, saved.checkpoint_id, {**saved.snapshot, "birthday_actions": actions})
    assert_denied(runtime, *target, own_order)


def test_confirmed_capture_rechecks_order_source_before_submission(open_runtime):
    runtime = open_runtime()
    who, plan, item, ports = task(runtime, "target")
    _, order_id = purchase(runtime, who, plan, item, ports)
    execute = lambda: ports.capture_execute(who, plan, item, order_id)
    authorize(runtime, who, lambda: ports.capture_check(who, plan, item, order_id), execute)
    saved = runtime.application.get_task("U1", "D1", who.task_id)
    actions = dict(saved.snapshot["birthday_actions"])
    del actions["order:" + item["product_id"]]
    runtime.application.update_task("U1", "D1", who.task_id, saved.revision, saved.run_id,
        saved.status, saved.checkpoint_id, {**saved.snapshot, "birthday_actions": actions})
    before = money_facts(runtime)
    assert not execute().executed  # Confirmation + verified code/face do not restore resource authority.
    assert money_facts(runtime) == before


def test_unavailable_order_receipt_cannot_prepare_a_payment(open_runtime):
    runtime = open_runtime()
    who, plan, item, ports = task(runtime, "target")
    _, order_id = purchase(runtime, who, plan, item, ports)
    before, confirmations = money_facts(runtime), confirmation_count(runtime)
    unavailable = QueryFailure(kind="error", error=BankError(code="BANK_UNAVAILABLE", details={}))
    with patch.object(runtime.gateway, "get_operation", return_value=unavailable):
        result = ports.capture_check(who, plan, item, order_id)
    assert result.decision is SecurityDecisionCode.PAUSE
    assert result.reason_code == "DEPENDENCY_UNAVAILABLE" and result.interaction is None
    assert confirmation_count(runtime) == confirmations and money_facts(runtime) == before


@pytest.mark.parametrize("recovery", ["restart", "response_loss"])
def test_own_order_can_pay_and_recover_the_original_operation(open_runtime, recovery):
    runtime = open_runtime()
    who, plan, item, ports = task(runtime, "target")
    frozen, order_id = purchase(runtime, who, plan, item, ports)
    execute = lambda: ports.capture_execute(who, plan, item, order_id)
    authorize(runtime, who, lambda: ports.capture_check(who, plan, item, order_id), execute)
    if recovery == "response_loss":
        runtime.gateway._bank.birthday.arm_response_loss("U1")
    first = execute()
    assert first.state == ("unknown" if recovery == "response_loss" else "completed")
    operation_id = first.operation_id
    if recovery == "restart":
        runtime.close()
        runtime = open_runtime()
        ports = runtime.birthday.ports_factory(who)
    observed = ports.requery(who, plan, "capture", operation_id)
    assert observed.state == "completed" and observed.operation_id == operation_id
    before = money_facts(runtime)
    replay = ports.capture_execute(who, plan, item, order_id)
    assert replay.state == "completed" and replay.operation_id == operation_id
    assert money_facts(runtime) == before
    freeze = runtime.gateway.get_freeze(who, frozen.receipt.freeze_id).data
    assert (freeze.captured_total_fen, freeze.remaining_fen) == (19900, 30100)
    assert runtime.gateway.get_order(who, order_id).data.order.payment_status == "paid"
