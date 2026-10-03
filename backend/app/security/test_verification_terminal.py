"""Bank terminal facts stop the original task; technical errors only pause it."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.agent_platform.test_transfer_runtime import runtime, trusted
from app.contracts.common import RiskLevel, SecurityDecisionCode, TaskStatus
from app.contracts.security import ConfirmationAnswer
from app.security.test_gate import Clock
from app.services.mock_bank.core import MockBankService
from app.services.mock_bank.verification import AdminContext
from app.storage.database import connect
from app.storage.mock_bank.repository import MockBankStore


def begin(tmp_path, risk):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    clock = Clock()
    clock.value = datetime.now(timezone.utc)
    bank.verification.clock = clock
    app = runtime(tmp_path / "application.sqlite", bank, risk=risk, authorize_face=lambda *_: True)
    app.application.create_session("S1", "U1", "D1", clock().isoformat(),
                                   (clock() + timedelta(days=1)).isoformat())
    pending = app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    app.answer_confirmation(trusted(), ConfirmationAnswer(
        confirmation_id=pending.interaction.record_ref, confirmation_version=1, choice="approve"))
    waiting = app.harness.resume(trusted("R2"), {"choice": "approve"})
    return app, bank, clock, waiting.interaction.record_ref


@pytest.mark.parametrize("mode,risk", [
    ("three_codes", RiskLevel.LOW), ("three_codes", RiskLevel.MEDIUM),
    ("code_expired", RiskLevel.MEDIUM), ("face_expired", RiskLevel.MEDIUM),
    ("face_failed", RiskLevel.MEDIUM), ("code_then_face_failed", RiskLevel.MEDIUM),
])
def test_bank_terminal_fact_is_durable_and_cannot_resume(tmp_path, mode, risk):
    app, bank, clock, challenge = begin(tmp_path, risk)
    if mode == "three_codes":
        for attempt in range(3 if risk == RiskLevel.LOW else 1):
            outcome = app.gateway.verify_code(trusted(), challenge, uuid4(), "incorrect")
            if risk == RiskLevel.LOW and attempt < 2:
                retry = app.harness.resume(trusted("R3"), {"choice": "resume"})
                assert retry.status == TaskStatus.WAITING_APPROVAL
                assert not app.confirmations.state.is_task_terminated(app._context(trusted(), None, None))
        assert outcome.challenge.challenge_status == "failed"
    elif mode == "code_expired":
        clock.advance(minutes=5)
    else:
        if mode == "face_expired":
            code = app.gateway.get_demo_code_for_api(trusted(), challenge)
            app.gateway.verify_code(trusted(), challenge, uuid4(), code)
        app.gateway.start_face(trusted(), challenge, uuid4())
        if mode == "face_expired":
            clock.advance(minutes=5)
        else:
            if mode == "code_then_face_failed":
                code = app.gateway.get_demo_code_for_api(trusted(), challenge)
                app.gateway.verify_code(trusted(), challenge, uuid4(), code)
            app.gateway.verify_face(AdminContext("admin", True, "D1", "U1"), challenge, uuid4(), "failed")
    failed = app.harness.resume(trusted("R4"), {"choice": "resume"})
    assert failed.status == TaskStatus.FAILED
    assert failed.error.code == "VERIFICATION_FAILED"
    assert app.confirmations.state.is_task_terminated(app._context(trusted(), None, None))
    connection = connect(app.application.path)
    decisions = [row[0] for row in connection.execute("SELECT event_json FROM audit_events")]
    connection.close()
    assert any(challenge in row and "verification-terminal-fact-stops-task" in row for row in decisions)
    with pytest.raises(ValueError):
        app.gateway.resend_verification_code(trusted(), challenge, uuid4())
    with pytest.raises(ValueError):
        app.gateway.verify_code(trusted(), challenge, uuid4(), "incorrect")
    if risk == RiskLevel.MEDIUM:
        with pytest.raises(ValueError):
            app.gateway.verify_face(AdminContext("admin", True, "D1", "U1"), challenge, uuid4(), "passed")
    assert app.harness.resume(trusted("R5"), {"choice": "resume"}).status == TaskStatus.FAILED
    app.close()
    restarted = runtime(tmp_path / "application.sqlite", bank, risk=risk)
    try:
        assert restarted.confirmations.state.is_task_terminated(restarted._context(trusted(), None, None))
        assert restarted.harness.resume(trusted("R6"), {"choice": "resume"}).status == TaskStatus.FAILED
        assert len(bank.store.list_ledger("U1", "A1")) == 0
    finally:
        restarted.close()


def test_basic_expiry_is_not_task_terminal(tmp_path):
    app, bank, clock, _ = begin(tmp_path, RiskLevel.LOW)
    clock.advance(minutes=5)
    try:
        result = app.harness.resume(trusted("R3"), {"choice": "resume"})
        assert result.status == TaskStatus.WAITING_APPROVAL
        assert not app.confirmations.state.is_task_terminated(app._context(trusted(), None, None))
        assert len(bank.store.list_ledger("U1", "A1")) == 0
    finally:
        app.close()


def test_unavailable_challenge_fact_is_pause_not_terminal(tmp_path):
    app, bank, _, _ = begin(tmp_path, RiskLevel.LOW)
    try:
        with patch.object(app.gateway, "get_verification", side_effect=RuntimeError("TASK_TERMINATED")):
            result = app.harness.resume(trusted("R3"), {"choice": "resume"})
        assert result.status == TaskStatus.NEEDS_ATTENTION
        assert result.error.code == "DEPENDENCY_UNAVAILABLE"
        assert not app.confirmations.state.is_task_terminated(app._context(trusted(), None, None))
        assert len(bank.store.list_ledger("U1", "A1")) == 0
    finally:
        app.close()
