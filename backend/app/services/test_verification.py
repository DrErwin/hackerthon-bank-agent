"""Bank verification facts and dedicated demo controls."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.contracts.common import DisplayField
from app.contracts.bank import PayeeDisplay
from app.contracts.platform import TrustedContext
from app.contracts.security import VerificationSummary
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.services.mock_bank.verification import AdminContext
from app.storage import StoragePaths
from app.storage.mock_bank.repository import MockBankStore


class Clock:
    def __init__(self):
        self.value = datetime(2026, 9, 28, 10, 0, tzinfo=timezone(timedelta(hours=8)))

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


def context(user="U1", session="S1", task="T1", round_id="D1"):
    return TrustedContext(
        user_id=user, session_id=session, task_id=task, run_id="R1",
        parent_task_id=None, demo_round_id=round_id,
    )


def ready(tmp_path):
    bank = MockBankService(MockBankStore(StoragePaths(tmp_path).bank))
    clock = Clock()
    bank.verification.clock = clock
    return bank, BankGateway(bank), clock


def action_summary(operation_id):
    return VerificationSummary(
        operation_id=operation_id, action_revision=1,
        source_confirmation_id="C1", source_confirmation_version=1,
        action_name="bank.submit_transfer", amount_fen=50_000,
        payee=PayeeDisplay(
            payee_id="A2", name_masked="王*", account_masked="****0002",
            remark="妈妈", bank_name="模拟合作银行",
        ),
        display_fields=[DisplayField(name="amount", label="金额", value_text="500 元")],
    )


def test_basic_code_scope_retries_and_persistent_record(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    user = context()
    challenge = gateway.create_verification(user, "basic_identity")
    assert gateway.create_verification(user, "basic_identity").challenge_id == challenge.challenge_id
    assert not hasattr(challenge, "code")
    code = gateway.get_demo_code_for_api(user, challenge.challenge_id)
    with pytest.raises(ValueError):
        gateway.get_demo_code_for_api(context(user="U2"), challenge.challenge_id)
    wrong_id = uuid4()
    wrong = gateway.verify_code(user, challenge.challenge_id, wrong_id, "000000")
    assert wrong.reason_code == "CODE_MISMATCH"
    assert gateway.verify_code(user, challenge.challenge_id, wrong_id, "000000") == wrong
    with pytest.raises(ValueError):
        gateway.verify_code(user, challenge.challenge_id, wrong_id, "111111")
    assert gateway.verify_code(user, challenge.challenge_id, uuid4(), "000000").challenge.consecutive_code_failures == 2
    passed = gateway.verify_code(user, challenge.challenge_id, uuid4(), code)
    assert passed.kind == "verified"
    assert passed.verification_id
    assert gateway.get_verification_record(context(task="T2"), passed.verification_id).scope == "session"
    with pytest.raises(ValueError):
        gateway.get_verification_record(context(session="S2"), passed.verification_id)
    gateway.close()

    reopened = MockBankService(MockBankStore(StoragePaths(tmp_path).bank))
    assert reopened.verification.get_record(user, passed.verification_id).source_challenge_id == challenge.challenge_id


def test_action_needs_both_factors_and_admin_scope(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    user = context()
    operation_id = uuid4()
    summary = action_summary(operation_id)
    challenge = gateway.create_verification(user, "action_step_up", operation_id, 1, summary)
    face = gateway.start_face(user, challenge.challenge_id, uuid4())
    assert gateway.start_face(user, challenge.challenge_id, uuid4()).face_expires_at == face.face_expires_at
    code = gateway.get_demo_code_for_api(user, challenge.challenge_id)
    first = gateway.verify_code(user, challenge.challenge_id, uuid4(), code)
    assert first.kind == "verified" and first.verification_id is None
    with pytest.raises(ValueError):
        gateway.verify_face(AdminContext("admin", False, "D1", "U1"), challenge.challenge_id,
                            uuid4(), "passed")
    with pytest.raises(ValueError):
        gateway.verify_face(AdminContext("admin", True, "D1", "U2"), challenge.challenge_id,
                            uuid4(), "passed")
    verified = gateway.verify_face(AdminContext("admin", True, "D1", "U1"), challenge.challenge_id,
                                   uuid4(), "passed")
    assert verified.kind == "verified" and verified.verification_id
    record = gateway.get_verification_record(user, verified.verification_id)
    assert record.scope == "action" and record.operation_id == operation_id
    with pytest.raises(ValueError):
        gateway.get_verification_record(context(task="T2"), verified.verification_id)
    gateway.close()


def test_resend_inherits_action_deadline_and_terminal_failure(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    user = context()
    operation_id = uuid4()
    challenge = gateway.create_verification(
        user, "action_step_up", operation_id, 1, action_summary(operation_id),
    )
    old_code = gateway.get_demo_code_for_api(user, challenge.challenge_id)
    clock.advance(4 * 60 + 50)
    submission_id = uuid4()
    replacement = gateway.resend_verification_code(user, challenge.challenge_id, submission_id)
    assert replacement.code_expires_at == challenge.code_expires_at
    assert gateway.resend_verification_code(user, challenge.challenge_id, submission_id) == replacement
    with pytest.raises(ValueError):
        gateway.verify_code(user, challenge.challenge_id, uuid4(), old_code)
    clock.advance(11)
    assert gateway.get_verification(user, replacement.challenge_id).challenge_status == "expired"
    with pytest.raises(ValueError):
        gateway.verify_code(user, replacement.challenge_id, uuid4(), old_code)
    gateway.close()


def test_basic_third_wrong_code_terminates_and_cannot_cross_user(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    user = context()
    challenge = gateway.create_verification(user, "basic_identity")
    with pytest.raises(ValueError):
        gateway.get_verification(context(user="U2"), challenge.challenge_id)
    for attempt in range(3):
        outcome = gateway.verify_code(user, challenge.challenge_id, uuid4(), "000000")
        assert outcome.challenge.consecutive_code_failures == attempt + 1
    assert outcome.challenge.challenge_status == "failed"
    with pytest.raises(ValueError):
        gateway.verify_code(user, challenge.challenge_id, uuid4(), "000000")
    gateway.close()


def test_resend_keeps_basic_failure_count_and_action_wrong_code_ends(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    user = context()
    basic = gateway.create_verification(user, "basic_identity")
    gateway.verify_code(user, basic.challenge_id, uuid4(), "000000")
    replacement = gateway.resend_verification_code(user, basic.challenge_id, uuid4())
    assert replacement.consecutive_code_failures == 1
    gateway.verify_code(user, replacement.challenge_id, uuid4(), "000000")
    last = gateway.verify_code(user, replacement.challenge_id, uuid4(), "000000")
    assert last.challenge.challenge_status == "failed"

    operation_id = uuid4()
    action = gateway.create_verification(
        context(task="T2"), "action_step_up", operation_id, 1, action_summary(operation_id),
    )
    failed = gateway.verify_code(context(task="T2"), action.challenge_id, uuid4(), "000000")
    assert failed.challenge.challenge_status == "failed"
    with pytest.raises(ValueError):
        gateway.start_face(context(task="T2"), action.challenge_id, uuid4())
    gateway.close()


def test_failed_face_never_creates_action_verification(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    user = context()
    operation_id = uuid4()
    challenge = gateway.create_verification(
        user, "action_step_up", operation_id, 1, action_summary(operation_id),
    )
    gateway.start_face(user, challenge.challenge_id, uuid4())
    gateway.verify_code(user, challenge.challenge_id, uuid4(),
                        gateway.get_demo_code_for_api(user, challenge.challenge_id))
    failed = gateway.verify_face(
        AdminContext("admin", True, "D1", "U1"), challenge.challenge_id,
        uuid4(), "failed",
    )
    assert failed.kind == "rejected"
    assert failed.verification_id is None
    assert failed.challenge.challenge_status == "failed"
    with pytest.raises(ValueError):
        gateway.create_verification(user, "action_step_up", operation_id, 1, action_summary(operation_id))
    gateway.close()
