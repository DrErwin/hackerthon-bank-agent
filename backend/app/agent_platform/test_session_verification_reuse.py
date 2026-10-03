"""Session facts are rebound by the server; each new transfer still confirms."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.agent_platform.test_transfer_runtime import runtime, trusted
from app.contracts.common import RiskLevel, TaskStatus
from app.contracts.security import ConfirmationAnswer
from app.services.mock_bank.core import MockBankService
from app.storage.mock_bank.repository import MockBankStore


def approved(app, owner, pending):
    context = app._context(owner, pending.data.operation_id, 1)
    app.answer_confirmation(owner, ConfirmationAnswer(
        confirmation_id=pending.interaction.record_ref,
        confirmation_version=context.confirmation_version, choice="approve"))
    return app.harness.resume(owner, {"choice": "approve"})


def verified_then_cancelled(tmp_path, risk=RiskLevel.LOW):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    app = runtime(tmp_path / "app.sqlite", bank, risk=risk, authorize_face=lambda *_: True)
    now = datetime.now(timezone.utc)
    for session in ("S1", "S2"):
        app.application.create_session(session, "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat())
    waiting = approved(app, trusted(), app.harness.start(trusted(), uuid4(), "给妈妈转 500 元"))
    challenge = waiting.interaction.record_ref
    code = app.gateway.get_demo_code_for_api(trusted(), challenge)
    outcome = app.gateway.verify_code(trusted(), challenge, uuid4(), code)
    if risk == RiskLevel.MEDIUM:
        from app.services.mock_bank.verification import AdminContext
        app.gateway.start_face(trusted(), challenge, uuid4())
        outcome = app.gateway.verify_face(AdminContext("admin", True, "D1", "U1"), challenge, uuid4(), "passed")
    app.bind_verification(trusted(), outcome.verification_id)
    assert app.harness.resume(trusted(), {"cancel": True}).status == TaskStatus.CANCELLED
    return app, bank, outcome.verification_id


def test_session_verification_survives_restart_and_new_task_confirms_once(tmp_path):
    app, bank, verification_id = verified_then_cancelled(tmp_path)
    app.close()
    app = runtime(tmp_path / "app.sqlite", bank)
    owner = trusted("R2").model_copy(update={"task_id": "T2"})
    try:
        second = app.harness.start(owner, uuid4(), "给妈妈转 500 元")
        assert second.status == TaskStatus.WAITING_APPROVAL
        assert second.interaction.kind == "confirmation"
        assert app._context(owner, second.data.operation_id, 1).verification_ids == [verification_id]
        assert len(bank.store.list_ledger("U1", "A1")) == 0
        result = approved(app, owner, second)
        assert result.status == TaskStatus.SUCCEEDED
        assert result.data.operation.receipt.amount_fen == 50000
        assert len(bank.store.list_ledger("U1", "A1")) == 1
        assert app.harness.resume(owner, {"choice": "resume"}).data.operation_id == result.data.operation_id
    finally:
        app.close()


@pytest.mark.parametrize("risk,session", [(RiskLevel.LOW, "S2"), (RiskLevel.MEDIUM, "S1")])
def test_new_login_or_action_record_cannot_authorize_new_task(tmp_path, risk, session):
    app, bank, old_id = verified_then_cancelled(tmp_path, risk)
    owner = trusted("R2").model_copy(update={"task_id": "T2", "session_id": session})
    try:
        second = app.harness.start(owner, uuid4(), "给妈妈转 500 元")
        assert old_id not in app._context(owner, second.data.operation_id, 1).verification_ids
        waiting = approved(app, owner, second)
        assert waiting.status == TaskStatus.WAITING_APPROVAL
        assert waiting.interaction.kind == "verification"
        assert len(bank.store.list_ledger("U1", "A1")) == 0
    finally:
        app.close()


def test_session_reuse_checks_current_owner_round_and_expiry(tmp_path):
    app, bank, _ = verified_then_cancelled(tmp_path)
    try:
        for updates in ({"user_id": "U2"}, {"demo_round_id": "D2"}):
            owner = trusted().model_copy(update={"task_id": "T2", **updates})
            assert app.facts.session_verification_sources(owner) == []
        expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        from app.storage.database import transaction
        with transaction(app.application.path) as connection:
            connection.execute("UPDATE sessions SET expires_at = ? WHERE session_id = ?", (expired, "S1"))
        owner = trusted().model_copy(update={"task_id": "T2"})
        with pytest.raises(PermissionError):
            app.harness.start(owner, uuid4(), "给妈妈转 500 元")
        assert len(bank.store.list_ledger("U1", "A1")) == 0
    finally:
        app.close()
