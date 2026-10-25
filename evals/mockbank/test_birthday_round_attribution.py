"""Read-only attribution: real runtime/gate/executor; model connector never called.

Configuration-only same-file round restart is NOT the specified B26 reset.
Internal ports probes do not establish an HTTP or browser exploit.
"""

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.agent_platform.local_demo import build_runtime
from app.agent_platform.test_cross_runtime_wiring import RoutingModel
from app.agent_platform.test_local_demo import configuration
from app.api.app import ApiConfig, COOKIE, create_app
from app.api.test_app import enter, post, start
from app.contracts.bank import CaptureFrozenInput, QueryFailure, ReleaseFrozenInput
from app.contracts.common import Category, OperationStatus, Phase, SecurityDecisionCode
from app.contracts.platform import TrustedContext
from app.contracts.security import ActionDescriptor, ConfirmationAnswer
from app.modules.cross.birthday_ports import BirthdayPlan
from app.services.mock_bank.verification import AdminContext
from app.storage.database import connect


@pytest.fixture
def composition(tmp_path):
    runtimes = []

    def open_round(round_id):
        config = configuration(tmp_path).model_copy(update={"demo_round_id": round_id})
        model = RoutingModel(response_mode="transfer")
        with patch("app.agent_platform.local_demo.ChatOpenAI", return_value=model):
            runtime = build_runtime(config)
        runtimes.append(runtime)
        app = create_app(runtime, ApiConfig(
            secret=config.api_secret.get_secret_value().encode(),
            admin_key="local-test-admin", origins=("http://testserver",),
            demo_round_id=round_id,
        ))
        return runtime, app, model

    yield open_round
    for runtime in runtimes:
        runtime.close()


def task(runtime, round_id):
    now = datetime.now(timezone.utc)
    who = TrustedContext(user_id="U1", session_id="S-"+round_id, demo_round_id=round_id,
                         task_id="T-"+round_id, run_id="R-"+round_id, parent_task_id=None)
    runtime.application.create_session(who.session_id, who.user_id, who.demo_round_id,
        now.isoformat(), (now+timedelta(days=1)).isoformat())
    runtime.application.create_task(who.task_id, who.user_id, who.session_id,
        who.demo_round_id, who.run_id, "running",
        {"capability_name": "cross.start_task", "trace_id": str(uuid4())})
    delivery_ref = "delivery-"+round_id
    runtime.application.store_controlled_detail(delivery_ref, who.user_id, who.demo_round_id,
        who.task_id, "delivery", {"recipient_name": "测试收件人", "phone": "13800000000",
        "address": "测试路1号"}, now.isoformat())
    product = runtime.gateway.list_products(who).products[0]
    item = dict(product_id=product.product_id, amount_fen=product.unit_price_fen,
                merchant_id=product.merchant_id, merchant_name=product.merchant_name,
                name=product.product_name, category=product.category.value)
    plan = BirthdayPlan(payer_account_id="A1", budget_id="round-attribution",
        budget_version=1, budget_limit_fen=50000, freeze_amount_fen=50000,
        deliver_by=(now+timedelta(days=4)).isoformat(), delivery_ref=delivery_ref,
        items=(item,))
    return who, plan, item, runtime.birthday.ports_factory(who)


def approved_write(runtime, who, check, execute, *, grant=None):
    asked = check()
    assert asked.decision is SecurityDecisionCode.REQUIRE_CONFIRMATION, asked
    record = runtime.confirmations.get(runtime._context(who, None, None), asked.interaction.record_ref)
    runtime.answer_confirmation(who, ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version, choice="approve"))
    if grant is not None:
        grant(record.confirmation_id)
    waiting = execute()
    assert waiting.state == "verify_wait", waiting
    challenge_id = waiting.verify.record_ref
    code = runtime.gateway.get_demo_code_for_api(who, challenge_id)
    assert runtime.gateway.verify_code(who, challenge_id, uuid4(), code).kind == "verified"
    runtime.gateway.start_face(who, challenge_id, uuid4())
    face = runtime.gateway.verify_face(AdminContext(actor_id="demo-admin", authorized=True,
        demo_round_id=who.demo_round_id, target_user_id=who.user_id),
        challenge_id, uuid4(), "passed")
    assert face.kind == "verified" and face.verification_id
    runtime.bind_verification(who, face.verification_id)
    result = execute()
    assert result.executed and result.state == "completed", result
    assert result.result.operation_status is OperationStatus.SUCCEEDED
    return result.result


def old_bank_objects(runtime):
    who, plan, item, ports = task(runtime, "D1")
    frozen = approved_write(runtime, who,
        lambda: ports.freeze_check(who, plan), lambda: ports.freeze_execute(who, plan),
        grant=lambda ref: ports.grant_release(who, plan, ref))
    ports.bind_freeze(who, plan, str(frozen.operation_id))
    created = approved_write(runtime, who,
        lambda: ports.order_check(who, plan, item), lambda: ports.order_execute(who, plan, item))
    return who, plan, item, ports, frozen, created


def bank_state(runtime):
    with closing(connect(runtime.gateway._bank.store.path)) as connection:
        return {table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
                for table in ("accounts", "freezes", "orders", "order_payments", "ledger_entries", "bank_operations")}


def test_asgi_old_session_and_task_are_not_current(composition, record_property):
    _, app, _ = composition("D1")
    with TestClient(app) as client:
        _, old_task = start(client, "给妈妈准备生日")
        old_cookie = client.cookies.get(COOKIE)
        assert client.get(f"/api/v1/tasks/{old_task['task_id']}").status_code == 200
    # Reopen the same application and bank files under a new configured round.
    _, app, model = composition("D2")
    with TestClient(app) as client:
        client.cookies.set(COOKIE, old_cookie)
        stale = client.get("/api/v1/session")
        assert stale.status_code == 401
        client.cookies.clear()
        assert enter(client)["demo_round_id"] == "D2"
        assert client.get(f"/api/v1/tasks/{old_task['task_id']}").status_code == 404
        assert post(client, f"/tasks/{old_task['task_id']}/resume").status_code == 404
        # B26 endpoints are absent in this assembly; configuration restart is not reset.
        paths = {route.path for route in app.routes}
        assert "/api/v1/admin/demo/reset" not in paths
        assert "/api/v1/admin/demo/reset-preview" not in paths
        assert model.calls == 0
    record_property("http_boundary", "ASGI TestClient: stale cookie401; D2 old task GET/resume404; B26 routes absent")


def test_real_claim_gate_and_limited_release_reject_old_round(composition, record_property):
    old, _, _ = composition("D1")
    who, plan, item, old_ports, frozen, created = old_bank_objects(old)
    old_security_context = old_ports._security_context(who, str(frozen.operation_id))
    old.close()
    current, _, model = composition("D2")
    before = bank_state(current)
    gate = current.gateway
    # The genuine live-claim authorizer is wired; no test allow callback.
    for name, request in (
        ("capture_frozen", CaptureFrozenInput(freeze_id=frozen.receipt.freeze_id,
            order_id=created.receipt.order.order_id, amount_fen=item["amount_fen"],
            merchant_id=item["merchant_id"], merchant_name=item["merchant_name"],
            purpose=item["name"], category=Category.SHOPPING)),
        ("release_frozen", ReleaseFrozenInput(freeze_id=frozen.receipt.freeze_id, amount_fen=50000)),
    ):
        denied = getattr(gate, name)(who.model_copy(update={"demo_round_id": "D2"}), uuid4(), request)
        assert isinstance(denied, QueryFailure) and denied.error.code == "ACCESS_DENIED"
    # An old trusted task cannot get a new write approved by the current policy.
    ports = current.birthday.ports_factory(who)
    with pytest.raises(ValueError, match="STALE_ROUND"):
        ports.capture_check(who, plan, item, created.receipt.order.order_id)
    # The live runtime rejects the stale context before reaching its policy.
    # Independently exercise that actual gate too, using the original context.
    birthday_gate, _ = ports._gate(who)
    decision = birthday_gate.check_action(old_security_context, ActionDescriptor(
        action_name="bank.capture_frozen", parameters_ref=str(uuid4()),
        resource_refs=[created.receipt.order.order_id], phase=Phase.EXECUTION))
    assert decision.decision is SecurityDecisionCode.BLOCK
    assert "ACCESS_DENIED" in decision.reason_codes
    with pytest.raises(ValueError, match="STALE_ROUND"):
        ports.finalize(who, plan, "user_cancelled")
    assert bank_state(current) == before
    assert model.calls == 0
    record_property("write_boundary", "real claims deny direct calls; stale ports/finalize rejected STALE_ROUND by active-round memory scope; actual gate separately BLOCK ACCESS_DENIED; bank unchanged")


def test_current_task_internal_port_can_pay_known_old_order(composition, record_property):
    old, _, _ = composition("D1")
    old_who, _, _, old_ports, old_freeze, created = old_bank_objects(old)
    old_release_id = old_ports._release_id(old_who)
    old.close()
    current, app, model = composition("D2")
    who, plan, item, ports = task(current, "D2")
    with pytest.raises(ValueError, match="ACCESS_DENIED"):
        current.birthday.state.get_release_authorization(
            current._context(who, None, None), old_release_id)
    old_operation = current.gateway.get_operation(who, old_freeze.operation_id)
    assert isinstance(old_operation, QueryFailure) and old_operation.error.code == "ACCESS_DENIED"
    frozen = approved_write(current, who,
        lambda: ports.freeze_check(who, plan), lambda: ports.freeze_execute(who, plan),
        grant=lambda ref: ports.grant_release(who, plan, ref))
    ports.bind_freeze(who, plan, str(frozen.operation_id))
    old_order_id = created.receipt.order.order_id
    # Deliberately pass a known old ID at the INTERNAL port seam; no claim injection.
    paid = approved_write(current, who,
        lambda: ports.capture_check(who, plan, item, old_order_id),
        lambda: ports.capture_execute(who, plan, item, old_order_id))
    order = current.gateway.get_order(who, old_order_id).data.order
    assert order.payment_status == "paid" and order.payment_transaction_id == paid.receipt.transaction_id
    old_view = current.gateway.get_freeze(who, old_freeze.receipt.freeze_id).data
    new_view = current.gateway.get_freeze(who, frozen.receipt.freeze_id).data
    assert old_view.remaining_fen == 50000
    assert (new_view.captured_total_fen, new_view.remaining_fen) == (19900, 30100)
    # Actual runtime only registers birthday write handlers on this gate.
    birthday_gate, _ = ports._gate(who)
    assert birthday_gate.registry.get("bank.get_freeze") is None
    assert birthday_gate.registry.get("bank.get_order") is None
    assert not any("freeze" in route.path or "order" in route.path for route in app.routes)
    assert model.calls == 0
    record_property("internal_port_probe", json.dumps({
        "configuration_restart_only": True, "real_confirmation_and_step_up": True,
        "old_order_payment_status": order.payment_status,
        "old_freeze_remaining_fen": old_view.remaining_fen,
        "new_freeze_captured_fen": new_view.captured_total_fen,
        "new_freeze_remaining_fen": new_view.remaining_fen,
        "model_calls": model.calls, "public_http_exploit_proven": False,
    }))
