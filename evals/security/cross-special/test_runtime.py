"""Real birthday composition probes. No planner, provider request, or browser.

Reuse the platform's isolated composition fixture, never its test conclusions.
The new probes check confirmations against bank objects, rather than text replies.
"""

import json

import pytest

from app.agent_platform.test_birthday_runtime_wiring import (
    RAW_DELIVERY, DELIVERY_REF, NoopModel, answer_verification,
    approve_confirmation, composition, run_to_freeze_question, trusted,
)
from app.contracts.common import TaskStatus
from app.contracts.security import ConfirmationAnswer
from app.security.gate import SecurityError
from app.storage.database import connect


def bank_facts(runtime):
    """Only non-secret, numeric facts enter pytest evidence."""
    with connect(runtime.gateway._bank.store.path) as db:
        counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("freezes", "orders", "order_payments")}
        counts["bank_operations"] = db.execute(
            "SELECT COUNT(*) FROM bank_operations WHERE operation_id NOT LIKE 'seed:%'",
        ).fetchone()[0]
    counts["frozen_fen"] = runtime.gateway._bank.store.get_account(
        "U1", "A1").frozen_balance_fen
    return counts


@pytest.fixture
def birthday(tmp_path, monkeypatch):
    def forbidden_model(*_args, **_kwargs):
        pytest.fail("MODEL_CALL_FORBIDDEN_IN_BACKEND_SPECIAL")

    monkeypatch.setattr(NoopModel, "_generate", forbidden_model)
    runtime, entry = composition(tmp_path)
    try:
        yield runtime, entry
    finally:
        runtime.close()


def test_chat_approval_without_durable_answer_writes_nothing(birthday, record_property):
    runtime, entry = birthday
    pending = run_to_freeze_question(entry)
    assert pending.status is TaskStatus.WAITING_APPROVAL
    before = bank_facts(runtime)
    # The workflow response alone must not answer the trusted confirmation.
    with pytest.raises(SecurityError, match="^CONFIRMATION_REQUIRED$"):
        entry.resume(trusted(runtime), {"choice": "approve"})
    assert bank_facts(runtime) == before
    assert before["freezes"] == before["orders"] == before["order_payments"] == 0
    record_property("bank_facts", json.dumps(before, sort_keys=True))


@pytest.mark.parametrize("scope", ["user", "session", "task", "round"])
def test_foreign_confirmation_cannot_write(birthday, scope, record_property):
    runtime, entry = birthday
    pending = run_to_freeze_question(entry)
    context = runtime._context(trusted(runtime), None, None)
    changes = {"user": {"user_id": "U2"}, "session": {"session_id": "S-OTHER"},
               "task": {"task_id": "OTHER"}, "round": {"demo_round_id": "D-OLD"}}
    foreign = context.model_copy(update=changes[scope])
    original = runtime.confirmations.get(context, pending.interaction.record_ref)
    before = bank_facts(runtime)
    with pytest.raises(SecurityError):
        runtime.confirmations.answer(foreign, ConfirmationAnswer(
            confirmation_id=original.confirmation_id,
            confirmation_version=original.confirmation_version, choice="approve",
        ))
    assert runtime.confirmations.get(context, pending.interaction.record_ref) == original
    assert bank_facts(runtime) == before
    record_property("bank_facts", json.dumps(before, sort_keys=True))


def test_cancel_after_freeze_only_releases_original_balance(birthday, record_property):
    runtime, entry = birthday
    who = trusted(runtime)
    pending = run_to_freeze_question(entry)
    approve_confirmation(runtime, who, pending.interaction.record_ref)
    verify = entry.resume(who, {"choice": "approve"})
    assert verify.interaction.kind == "verification"
    answer_verification(runtime, who, "R1", verify.interaction.record_ref)
    entry.resume(who, {"choice": "resume"})
    before = bank_facts(runtime)
    assert before["freezes"] == 1 and before["frozen_fen"] == 50000
    result = entry.resume(who, {"cancel": True})
    assert result.status is TaskStatus.CANCELLED
    after = bank_facts(runtime)
    assert after["frozen_fen"] == 0
    assert after["orders"] == after["order_payments"] == 0
    with connect(runtime.gateway._bank.store.path) as db:
        freeze = dict(db.execute("SELECT * FROM freezes").fetchone())
    assert freeze["captured_total_fen"] == 0
    assert freeze["released_total_fen"] == freeze["original_amount_fen"] == 50000
    # Ordinary resume after cancellation cannot resurrect a purchase or release.
    entry.resume(who, {"choice": "approve"})
    assert bank_facts(runtime) == after
    record_property("bank_before", json.dumps(before, sort_keys=True))
    record_property("bank_after", json.dumps(after, sort_keys=True))


def test_delivery_raw_text_stays_out_of_birthday_result_and_audit(birthday, caplog):
    runtime, entry = birthday
    pending = run_to_freeze_question(entry)
    who = trusted(runtime)
    approve_confirmation(runtime, who, pending.interaction.record_ref)
    verification = entry.resume(who, {"choice": "approve"})
    assert verification.interaction.kind == "verification"
    # Inspect ordinary event/evidence sinks, not the permitted controlled store.
    with connect(runtime.application.path) as db:
        events = [row[0] for row in db.execute("SELECT event_json FROM audit_events")]
        evidence = [row[0] for row in db.execute("SELECT content FROM audit_evidence")]
    visible = json.dumps([pending.model_dump(mode="json"),
                          verification.model_dump(mode="json"), events, evidence,
                          caplog.text], ensure_ascii=False)
    for raw in (RAW_DELIVERY["phone"], RAW_DELIVERY["address"]):
        assert raw not in visible
    stored = runtime.application.get_controlled_detail("U1", "D1", DELIVERY_REF)
    assert stored.payload == RAW_DELIVERY
    assert runtime.application.get_controlled_detail("U2", "D1", DELIVERY_REF) is None
    assert runtime.application.get_controlled_detail("U1", "D2", DELIVERY_REF) is None
