"""D1 presentation at workflow and real runtime seams; no live-model claim."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.agent_platform.test_child_dispatch import _arrangement
from app.agent_platform.test_transfer_runtime import runtime, trusted
from app.contracts.common import SecurityDecisionCode, TaskStatus
from app.contracts.security import ConfirmationAnswer
from app.modules.transfer.test_workflow import StoppedPorts, request, workflow
from app.modules.transfer.test_workflow import trusted as workflow_trusted
from app.services.mock_bank.core import MockBankService
from app.storage.mock_bank.repository import MockBankStore


MESSAGE = "该付款账户已有正在办理的联动资金安排，请先完成或结束该安排。"


def assert_conflict(result):
    assert result.status == TaskStatus.NEEDS_ATTENTION
    assert result.error.code == "ARRANGEMENT_CONFLICT"
    assert result.error.source == "platform"
    assert result.error.field == "payer_account_id"
    assert result.message == result.error.reason == MESSAGE
    assert result.recovery_required and result.recovery_reason == "ARRANGEMENT_CONFLICT"
    assert result.allowed_actions == [] and result.interaction is None


def test_workflow_preserves_arrangement_conflict_presentation():
    flow, ports = workflow(StoppedPorts(SecurityDecisionCode.PAUSE, ["ARRANGEMENT_CONFLICT"], MESSAGE))
    result = flow.start(workflow_trusted(), request())
    assert_conflict(result)
    assert ports.submissions == 0


def test_real_confirmed_transfer_conflict_keeps_bank_untouched(tmp_path, monkeypatch):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    app = runtime(tmp_path / "application.sqlite", bank)
    try:
        now = datetime.now(timezone.utc)
        app.application.create_session("S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat())
        app.application.create_task("OTHER", "U1", "S1", "D1", "R9", "running", {})
        app.application.acquire_arrangement(_arrangement("OTHER", "A1"))
        before = app.gateway.list_accounts(trusted()).data
        submissions = []
        def unexpected_submit(*args, **kwargs):
            submissions.append(True)
            raise AssertionError("D1 must pause before bank submission")
        monkeypatch.setattr(app.gateway, "submit_transfer", unexpected_submit)
        pending = app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
        assert pending.status == TaskStatus.WAITING_APPROVAL
        context = app._context(trusted(), pending.data.operation_id, 1)
        confirmation = app.confirmations.get(context, pending.interaction.record_ref)
        app.answer_confirmation(trusted(), ConfirmationAnswer(
            confirmation_id=confirmation.confirmation_id, confirmation_version=1, choice="approve"))
        verification_context = trusted("R3")
        verification = app.harness.resume(verification_context, {"choice": "approve"})
        code = app.gateway.get_demo_code_for_api(verification_context, verification.interaction.record_ref)
        verified = app.gateway.verify_code(verification_context, verification.interaction.record_ref, uuid4(), code)
        app.bind_verification(verification_context, verified.verification_id)
        paused = app.harness.resume(trusted("R4"), {"choice": "approve"})
        assert_conflict(paused)
        saved = app.application.get_task("U1", "D1", paused.task_id).snapshot["result"]
        assert saved["error"]["source"] == "platform" and saved["error"]["field"] == "payer_account_id"
        assert saved["message"] == MESSAGE
        assert not submissions and bank.store.list_ledger("U1", "A1") == []
        assert app.gateway.list_accounts(trusted()).data == before
    finally:
        app.close()
