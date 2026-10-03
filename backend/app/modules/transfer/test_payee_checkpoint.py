"""Real platform/manual-payee path: ordinary checkpoint writes contain no secret."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.agent_platform.test_transfer_runtime import runtime, trusted
from app.contracts.bank import ManualPayee, SavedPayee, OwnPayee
from app.contracts.common import TaskStatus
from app.contracts.platform import StartTransferInput
from app.contracts.security import ConfirmationAnswer
from app.memory.adapter import MemoryContext
from app.security import SecurityError
from app.services.mock_bank.core import MockBankService
from app.storage.database import connect
from app.storage.mock_bank.repository import MockBankStore


def manual():
    return ManualPayee(kind="manual", account_name="王阿姨", account_number="6222000000000002")


def scan(app):
    connection = connect(app.application.path)
    try:
        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes", "audit_events", "tasks"):
            assert all(manual().account_number.encode() not in str(tuple(row)).encode()
                       for row in connection.execute(f"SELECT * FROM {table}")), table
    finally:
        connection.close()


@pytest.fixture
def setup(tmp_path):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    app = runtime(tmp_path / "application.sqlite", bank)
    at = datetime.now(timezone.utc)
    app.application.create_session("S1", "U1", "D1", at.isoformat(), (at + timedelta(days=1)).isoformat())
    app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    yield app, bank
    app.close()


def test_raw_resume_is_protected_before_command_write_and_restart(setup):
    app, bank = setup
    pending = app.harness.resume(trusted("R2"), {"fields": {"payee_input": manual().model_dump()}})
    assert pending.status == TaskStatus.WAITING_APPROVAL
    assert pending.data.payee.account_masked.endswith("0002")
    scan(app)
    restarted = runtime(app.application.path, bank)
    try:
        resumed = restarted.harness.resume(trusted("R3"), {})
        assert resumed.data.operation_id == pending.data.operation_id
        assert resumed.status == TaskStatus.WAITING_APPROVAL
        scan(restarted)
        assert len(bank.store.list_ledger("U1", "A1")) == 0
    finally:
        restarted.close()


def test_public_start_manual_payee_is_protected_before_first_checkpoint(setup):
    app, bank = setup
    current = trusted().model_copy(update={"task_id": "T2"})
    app.application.create_task("T2", "U1", "S1", "D1", "R1", TaskStatus.RUNNING,
                                {"trace_id": str(uuid4())})
    saver = app.memory.checkpointer(MemoryContext("U1", "S1", "D1"), "T2")
    flow = app._transfer_factory(current, saver, app._trace(current))
    result = flow.start(current, StartTransferInput(request_id=uuid4(), intent_text="普通转账",
        payer_account_id="A1", payee=manual(), amount_fen=50000), thread_id=saver.thread_id)
    assert result.status == TaskStatus.WAITING_APPROVAL
    scan(app)
    assert len(bank.store.list_ledger("U1", "A1")) == 0


def test_manual_change_invalidates_old_confirmation_and_finishes_once(setup):
    app, bank = setup
    first = app.harness.resume(trusted("R2"), {"fields": {"payee_input": manual().model_dump()}})
    second = app.harness.resume(trusted("R3"), {"fields": {"amount_fen": 60000}})
    with pytest.raises(SecurityError, match="CONFIRMATION_STALE"):
        app.answer_confirmation(trusted("R3"), ConfirmationAnswer(
            confirmation_id=first.interaction.record_ref, confirmation_version=1, choice="approve"))
    app.answer_confirmation(trusted("R3"), ConfirmationAnswer(
        confirmation_id=second.interaction.record_ref,
        confirmation_version=app._context(trusted(), second.data.operation_id, 3).confirmation_version,
        choice="approve"))
    waiting = app.harness.resume(trusted("R4"), {"choice": "approve"})
    challenge = waiting.interaction.record_ref
    code = app.gateway.get_demo_code_for_api(trusted(), challenge)
    verified = app.gateway.verify_code(trusted(), challenge, uuid4(), code)
    app.bind_verification(trusted(), verified.verification_id)
    assert app._context(trusted(), second.data.operation_id, 3).verification_ids == [verified.verification_id]
    result = app.harness.resume(trusted("R5"), {"choice": "approve"})
    assert result.status == TaskStatus.SUCCEEDED, (result.error, result.interaction, result.message)
    assert result.data.operation.receipt.amount_fen == 60000
    assert len(bank.store.list_ledger("U1", "A1")) == 1
    assert app.harness.resume(trusted("R6"), {}).data.operation_id == result.data.operation_id
    scan(app)


@pytest.mark.parametrize("payee", [SavedPayee(kind="saved", payee_id="A2"),
                                  OwnPayee(kind="own", account_id="A5")])
def test_existing_payee_kinds_keep_normal_confirmation(setup, payee):
    app, _ = setup
    pending = app.harness.resume(trusted("R2"), {"fields": {"payee_input": payee.model_dump()}})
    assert pending.status == TaskStatus.WAITING_APPROVAL


def test_cross_task_reference_does_not_prepare_operation(setup):
    app, bank = setup
    owner = trusted().model_copy(update={"task_id": "T2"})
    app.application.create_task("T2", "U1", "S1", "D1", "R1", TaskStatus.RUNNING,
                                {"trace_id": str(uuid4())})
    ref = app.payee_references.register(owner, manual(), 1)
    rejected = app.harness.resume(trusted("R2"), {"fields": {"payee_input": {
        "kind": "reference", "reference": ref.reference, "payee_revision": 1}}})
    assert rejected.status != TaskStatus.WAITING_APPROVAL
    assert len(bank.store.list_ledger("U1", "A1")) == 0
    scan(app)
