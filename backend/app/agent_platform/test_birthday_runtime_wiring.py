"""Ticket v05-cross-platform/09: the birthday goal on the real composition.

The whole chain runs on real parts only: the cross flow (business 03), the
platform ports (this ticket), the #272 security gate with its MEDIUM step-up
verification, the #262 birthday bank and the §3.5 limited release. No scripted
ports, no stand-in bank.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.api.app import ApiConfig, create_app
from app.contracts.common import OperationStatus, TaskStatus
from app.contracts.platform import TrustedContext

from .local_demo import build_runtime
from .test_local_demo import ConnectorTestModel, configuration
from .test_cross_runtime_wiring import submitted_ledger_count


NOW = datetime.now(timezone.utc)
DELIVERY_REF = "deliver-birthday-0001"
RAW_DELIVERY = {"recipient_name": "妈妈", "phone": "13800000000",
                "address": "幸福小区 1 号", "deliver_by": "2026-10-30T18:00:00+08:00"}


class NoopModel(ConnectorTestModel):
    """The flows below drive the cross entry directly; the chat planner is
    never consulted for these money paths."""

    model_name: str = "glm-4.7"


def composition(tmp_path):
    config = configuration(tmp_path)
    from unittest.mock import patch

    with patch("app.agent_platform.local_demo.ChatOpenAI",
               return_value=NoopModel(response_mode="none")):
        runtime = build_runtime(config)
    app = create_app(runtime, ApiConfig(
        secret=config.api_secret.get_secret_value().encode(), admin_key="local-test-admin",
        origins=("http://testserver",), demo_round_id=config.demo_round_id,
    ))
    TestClient(app)  # lifespan wires state.api
    now = datetime.now(timezone.utc)
    runtime.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    runtime.application.create_task(
        "BIRTHDAY", "U1", "S1", "D1", "R1", "running",
        {"capability_name": "cross.start_task", "trace_id": str(uuid4())})
    runtime.application.store_controlled_detail(
        DELIVERY_REF, "U1", "D1", "BIRTHDAY", "delivery", RAW_DELIVERY,
        now.isoformat(),
    )
    from app.memory.adapter import MemoryContext
    from app.modules.cross.entry import CrossEntry

    saver = runtime.memory.checkpointer(MemoryContext("U1", "S1", "D1"), "BIRTHDAY")
    entry = CrossEntry(runtime.harness, saver, None, runtime.gateway._bank.clock,
                       birthday_ports_factory=runtime.birthday.ports_factory)
    return runtime, entry


def trusted(runtime, run="R1"):
    return TrustedContext(user_id="U1", session_id="S1", task_id="BIRTHDAY",
                          run_id=run, parent_task_id=None, demo_round_id="D1")


def option_id(result, needle):
    matches = [item for item in result.interaction.options if needle in item.label]
    assert len(matches) == 1, [item.label for item in result.interaction.options]
    return matches[0].id


def approve_confirmation(runtime, who, record_ref):
    """Answer the durable confirmation record first (the HTTP button path);
    only then does the flow's approve continue to the write."""
    from app.contracts.security import ConfirmationAnswer

    record = runtime.confirmations.get(runtime._context(who, None, None), record_ref)
    runtime.answer_confirmation(who, ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version, choice="approve",
    ))


def answer_verification(runtime, who, run, record_ref):
    """Complete the real MEDIUM step-up (code + mock face) and bind the record."""
    from app.services.mock_bank.verification import AdminContext

    code = runtime.gateway.get_demo_code_for_api(who, record_ref)
    outcome = runtime.gateway.verify_code(who, record_ref, uuid4(), code)
    assert outcome.kind == "verified", outcome
    runtime.gateway.start_face(who, record_ref, uuid4())
    face = runtime.gateway.verify_face(
        AdminContext(actor_id="demo-admin", authorized=True, demo_round_id="D1",
                     target_user_id="U1"),
        record_ref, uuid4(), "passed",
    )
    assert face.kind == "verified" and face.verification_id, face
    runtime.bind_verification(who, face.verification_id)
    return face


def run_to_freeze_question(entry):
    from app.contracts.platform import StartTransferInput

    started = entry.start(trusted(entry.harness.application),
                          StartTransferInput(request_id=uuid4(),
                                             intent_text="给妈妈过生日，安排花和蛋糕"))
    assert started.status is TaskStatus.WAITING_INPUT
    current = entry.resume(trusted(entry.harness.application), {"text": "500元"})
    current = entry.resume(trusted(entry.harness.application), {"text": "2026-10-30"})
    current = entry.resume(trusted(entry.harness.application), {"text": DELIVERY_REF})
    current = entry.resume(trusted(entry.harness.application),
                           {"selected_option_id": option_id(current, "鲜花")})
    current = entry.resume(trusted(entry.harness.application),
                           {"selected_option_id": option_id(current, "蛋糕")})
    current = entry.resume(trusted(entry.harness.application),
                           {"selected_option_id": option_id(current, "就选这些")})
    return entry.resume(trusted(entry.harness.application),
                        {"selected_option_id": option_id(current, "采用并开始办理")})


def test_full_birthday_chain_on_the_real_bank(tmp_path):
    runtime, entry = composition(tmp_path)
    who = trusted(runtime)

    freeze_ask = run_to_freeze_question(entry)
    assert freeze_ask.status is TaskStatus.WAITING_APPROVAL
    assert freeze_ask.interaction.kind == "confirmation"
    confirmation_ref = freeze_ask.interaction.record_ref
    # The §3.5 clause lives on the durable confirmation record itself.
    from app.contracts.security import ActionDescriptor
    from app.contracts.common import Phase

    record = runtime.confirmations.get(runtime._context(who, None, None), confirmation_ref)
    clause = [field.value_text for field in record.display_fields
              if field.name == "release_clause"]
    assert clause and "仅释放" in clause[0] and "未消费" in clause[0]
    amounts = [field.value_text for field in record.display_fields
               if field.name == "amount"]
    assert amounts == ["500.00 元"]

    # Approve (durable record first): the MEDIUM gate then demands the step-up
    # code before any money moves.
    approve_confirmation(runtime, who, confirmation_ref)
    verify_ask = entry.resume(who, {"choice": "approve"})
    assert verify_ask.status is TaskStatus.WAITING_APPROVAL
    assert verify_ask.interaction.kind == "verification"
    answer_verification(runtime, who, "R1", verify_ask.interaction.record_ref)

    # The platform resume continues the same freeze; the bank holds the funds.
    frozen = entry.resume(who, {"choice": "resume"})
    assert frozen.status is not TaskStatus.WAITING_APPROVAL or "验证" not in frozen.message
    freezes = _all_freezes(runtime)
    assert len(freezes) == 1
    assert freezes[0]["original_amount_fen"] == 50000
    account = runtime.gateway._bank.store.get_account("U1", "A1")
    assert account.frozen_balance_fen == 50000
    assert submitted_ledger_count(runtime) == 0  # freezing writes no ledger row

    def drive(current, limit=30):
        for _ in range(limit):
            if current.status.value in ("succeeded", "failed", "cancelled",
                                        "partially_succeeded"):
                return current
            interaction = current.interaction
            if interaction is None:
                current = entry.resume(who, {})
            elif interaction.kind == "confirmation":
                approve_confirmation(runtime, who, interaction.record_ref)
                current = entry.resume(who, {"choice": "approve"})
            elif interaction.kind == "verification":
                answer_verification(runtime, who, "R1", interaction.record_ref)
                current = entry.resume(who, {"choice": "resume"})
            else:
                current = entry.resume(who, {})
        return current

    nxt = drive(frozen)
    assert nxt.status is TaskStatus.SUCCEEDED, nxt.message
    assert "已付款" in nxt.message
    ledger = runtime.gateway._bank.store.list_ledger("U1", "A1")
    paid = [row for row in ledger if row["nature"] == "consumption"
            and not row["operation_id"].startswith("seed:")]
    assert {row["amount_fen"] for row in paid} == {19900, 26800}
    freeze = _single_freeze(runtime)
    assert freeze["captured_total_fen"] == 46700
    assert freeze["released_total_fen"] == 3300
    # The §3.5 ending released the verified remainder: 33.00 yuan.
    assert "33.00" in nxt.message
    app_close(runtime)


def _all_freezes(runtime):
    from app.storage.database import connect

    with connect(runtime.gateway._bank.store.path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM freezes")]


def _single_freeze(runtime):
    rows = _all_freezes(runtime)
    assert len(rows) == 1
    return rows[0]


def app_close(runtime):
    runtime.gateway.close()


def test_stop_after_flower_releases_the_remainder_only(tmp_path):
    runtime, entry = composition(tmp_path)
    who = trusted(runtime)
    freeze_ask = run_to_freeze_question(entry)
    approve_confirmation(runtime, who, freeze_ask.interaction.record_ref)
    verify_ask = entry.resume(who, {"choice": "approve"})
    answer_verification(runtime, who, "R1", verify_ask.interaction.record_ref)
    frozen = entry.resume(who, {"choice": "resume"})

    def paid_amounts():
        ledger = runtime.gateway._bank.store.list_ledger("U1", "A1")
        return {row["amount_fen"] for row in ledger
                if row["nature"] == "consumption"
                and not row["operation_id"].startswith("seed:")}

    def settle_until_cake_asks(current, limit=16):
        for _ in range(limit):
            if current.status.value in ("succeeded", "failed", "cancelled",
                                        "partially_succeeded"):
                return current
            interaction = current.interaction
            if interaction is None:
                current = entry.resume(who, {})
            elif interaction.kind == "confirmation":
                if paid_amounts() == {19900}:
                    return current  # the flower settled; this card is the cake's
                approve_confirmation(runtime, who, interaction.record_ref)
                current = entry.resume(who, {"choice": "approve"})
            elif interaction.kind == "verification":
                answer_verification(runtime, who, "R1", interaction.record_ref)
                current = entry.resume(who, {"choice": "resume"})
            else:
                current = entry.resume(who, {})
        return current

    before_stop = settle_until_cake_asks(frozen)
    assert before_stop.status is TaskStatus.WAITING_APPROVAL
    assert before_stop.interaction.kind == "confirmation"
    assert paid_amounts() == {19900}

    stopped = entry.resume(who, {"cancel": True})
    # Cake unpaid: partial success with the remainder released (D2).
    assert stopped.status is TaskStatus.PARTIALLY_SUCCEEDED, stopped.message
    freeze = _single_freeze(runtime)
    assert freeze["captured_total_fen"] == 19900
    assert freeze["released_total_fen"] == 30100
    assert "已付款" in stopped.message and "301.00" in stopped.message
    app_close(runtime)


def test_unwired_gateway_denies_birthday_writes(tmp_path):
    runtime, entry = composition(tmp_path)
    # A foreign write without any claim: the live-claim authorizer denies it.
    runtime.birthday = None  # detach the wiring: gateway falls back to deny-all
    from app.contracts.bank import FreezeFundsInput, QueryFailure

    denied = runtime.gateway.freeze_funds(trusted(runtime), uuid4(), FreezeFundsInput(
        account_id="A1", amount_fen=50000, reason="生日"))
    assert isinstance(denied, QueryFailure)
    assert denied.error.code == "ACCESS_DENIED"
    assert submitted_ledger_count(runtime) == 0
    assert _all_freezes(runtime) == []
    runtime.gateway.close()
