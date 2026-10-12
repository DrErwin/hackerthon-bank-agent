"""Bank verification facts and dedicated demo controls."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
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

DEMO_SECRET = b"mock-bank-test-secret-32-bytes-minimum"


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
    bank = MockBankService(MockBankStore(StoragePaths(tmp_path).bank), demo_secret=DEMO_SECRET)
    clock = Clock()
    bank.verification.clock = clock
    return bank, BankGateway(bank, authorize_face=lambda *args: True), clock


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

    reopened = MockBankService(MockBankStore(StoragePaths(tmp_path).bank), demo_secret=DEMO_SECRET)
    assert reopened.verification.get_record(user, passed.verification_id).source_challenge_id == challenge.challenge_id


def test_same_submission_id_with_different_code_raises_submission_conflict(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        challenge = gateway.create_verification(user, "basic_identity")
        code = gateway.get_demo_code_for_api(user, challenge.challenge_id)
        wrong1 = "111111" if code != "111111" else "222222"
        wrong2 = "333333" if code != "333333" else "444444"
        submission = uuid4()
        gateway.verify_code(user, challenge.challenge_id, submission, wrong1)
        # 同 submission_id 换不同内容：明确的提交冲突码，而不是通用的范围错误
        with pytest.raises(ValueError, match="VERIFICATION_SUBMISSION_CONFLICT"):
            gateway.verify_code(user, challenge.challenge_id, submission, wrong2)
        # 原提交结果不变，重放仍命中原结果
        assert gateway.verify_code(user, challenge.challenge_id, submission, wrong1).reason_code == "CODE_MISMATCH"
        # 新编号的真实错误正常计数
        assert gateway.verify_code(
            user, challenge.challenge_id, uuid4(), wrong2,
        ).challenge.consecutive_code_failures == 2
    finally:
        gateway.close()


def test_expired_basic_code_can_be_resent_without_losing_failures(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        old = gateway.create_verification(user, "basic_identity")
        code = gateway.get_demo_code_for_api(user, old.challenge_id)
        wrong = "000000" if code != "000000" else "111111"
        submission = uuid4()
        gateway.verify_code(user, old.challenge_id, submission, wrong)
        assert gateway.verify_code(user, old.challenge_id, submission, wrong).challenge.consecutive_code_failures == 1
        clock.advance(300)
        assert gateway.get_verification(user, old.challenge_id).challenge_status == "expired"
        resend = uuid4()
        new = gateway.resend_verification_code(user, old.challenge_id, resend)
        assert new.challenge_status == "pending"
        assert new.code_result == "pending"
        assert new.consecutive_code_failures == 1
        assert new.code_expires_at == clock() + timedelta(minutes=5)
        assert gateway.resend_verification_code(user, old.challenge_id, resend) == new
        with pytest.raises(ValueError):
            gateway.verify_code(user, old.challenge_id, uuid4(), code)
        current = gateway.get_demo_code_for_api(user, new.challenge_id)
        result = gateway.verify_code(user, new.challenge_id, uuid4(), current)
        assert result.verification_id
        with pytest.raises(ValueError, match="TASK_TERMINATED"):
            gateway.resend_verification_code(user, new.challenge_id, uuid4())
    finally:
        gateway.close()

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


def test_code_is_not_persisted_and_failures_survive_expiry(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    user = context()
    challenge = gateway.create_verification(user, "basic_identity")
    code = gateway.get_demo_code_for_api(user, challenge.challenge_id)
    with sqlite3.connect(bank.store.path) as connection:
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'bank_verification_challenges'",
        ).fetchone()[0]
    assert "demo_code" not in schema
    assert code.encode() not in bank.store.path.read_bytes()
    gateway.verify_code(user, challenge.challenge_id, uuid4(), "000000")
    clock.advance(301)
    renewed = gateway.create_verification(user, "basic_identity")
    assert renewed.consecutive_code_failures == 1
    gateway.verify_code(user, renewed.challenge_id, uuid4(), "000000")
    last = gateway.verify_code(user, renewed.challenge_id, uuid4(), "000000")
    assert last.challenge.challenge_status == "failed"
    with pytest.raises(ValueError, match="TASK_TERMINATED"):
        gateway.create_verification(context(session="S2"), "basic_identity")
    gateway.close()


def test_face_is_denied_without_server_admin_authorization(tmp_path):
    bank, gateway, _ = ready(tmp_path)
    user = context()
    operation_id = uuid4()
    challenge = gateway.create_verification(
        user, "action_step_up", operation_id, 1, action_summary(operation_id),
    )
    gateway.start_face(user, challenge.challenge_id, uuid4())
    denied_gateway = BankGateway(bank)
    with pytest.raises(ValueError, match="ACCESS_DENIED"):
        denied_gateway.verify_face(
            AdminContext("admin", True, "D1", "U1"), challenge.challenge_id,
            uuid4(), "passed",
        )
    assert gateway.get_verification(user, challenge.challenge_id).face_result == "pending"
    denied_gateway.close()
    gateway.close()


def test_legacy_plaintext_code_store_fails_closed(tmp_path):
    path = StoragePaths(tmp_path).bank
    MockBankStore(path)
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE bank_verification_challenges (
            challenge_id TEXT PRIMARY KEY, challenge_json TEXT NOT NULL, demo_code TEXT NOT NULL
        )""")
    with pytest.raises(RuntimeError, match="legacy demo codes"):
        MockBankService(MockBankStore(path), demo_secret=DEMO_SECRET)


def test_create_after_resend_failure_exposes_trusted_terminal_fact(tmp_path):
    from app.services.mock_bank.core import MockBankService
    from app.services.mock_bank.verification import VerificationTerminated
    from app.storage.mock_bank.repository import MockBankStore
    from app.contracts.platform import TrustedContext
    bank = MockBankService(MockBankStore(tmp_path / "terminal.sqlite"), demo_secret=b"demo-secret" * 4)
    owner = TrustedContext(user_id="U1", session_id="S1", task_id="T1", run_id="R1",
                           parent_task_id=None, demo_round_id="D1")
    original = bank.verification.create_verification(owner, "basic_identity")
    replacement = bank.verification.resend_code(owner, original.challenge_id, uuid4())
    for _ in range(3):
        bank.verification.verify_code(owner, replacement.challenge_id, uuid4(), "incorrect")
    with pytest.raises(VerificationTerminated) as caught:
        bank.verification.create_verification(owner, "basic_identity")
    assert caught.value.challenge.challenge_id == replacement.challenge_id
    assert caught.value.challenge.challenge_status == "failed"
    assert caught.value.challenge.consecutive_code_failures == 3
    assert "incorrect" not in caught.value.challenge.model_dump_json()


def test_list_task_verifications_is_owner_scoped_and_session_independent(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    old_session = gateway.create_verification(context(session="S1"), "basic_identity")
    other_task = gateway.create_verification(context(session="S2", task="T2"), "basic_identity")
    operation_id = uuid4()
    action = gateway.create_verification(
        context(session="S1"), "action_step_up",
        operation_id=operation_id, action_revision=1, summary=action_summary(operation_id),
    )
    # Replay reads by task owner across sessions: the current session must not
    # hide challenges created before a session recovery.
    listed = gateway.list_verifications(context(session="S2"), "T1")
    assert [c.challenge_id for c in listed] == sorted(
        [old_session.challenge_id, action.challenge_id],
    )  # same clock instant, stable challenge_id order
    assert other_task.challenge_id not in [c.challenge_id for c in listed]
    # Foreign users or rounds see nothing, without leaking existence.
    assert gateway.list_verifications(context(user="U2"), "T1") == []
    assert gateway.list_verifications(context(round_id="D9"), "T1") == []
    gateway.close()


def test_list_task_verifications_expires_stale_pending_like_get(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    challenge = gateway.create_verification(context(), "basic_identity")
    clock.advance(301)
    listed = gateway.list_verifications(context(), "T1")
    assert [c.challenge_id for c in listed] == [challenge.challenge_id]
    assert listed[0].challenge_status == "expired"
    assert listed[0].code_result == "expired"
    assert gateway.get_verification(context(), challenge.challenge_id).challenge_status == "expired"
    gateway.close()


def test_list_task_verifications_does_not_touch_foreign_pending(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    mine = gateway.create_verification(context(task="T1"), "basic_identity")
    foreign = gateway.create_verification(context(user="U2", task="T9"), "basic_identity")
    clock.advance(301)
    listed = gateway.list_verifications(context(task="T1"), "T1")
    assert [c.challenge_id for c in listed] == [mine.challenge_id]
    # 他人挑战不因本次回放被终态化：存储里仍保持 pending 原样。
    with sqlite3.connect(StoragePaths(tmp_path).bank) as connection:
        stored = connection.execute(
            "SELECT challenge_json FROM bank_verification_challenges WHERE challenge_id=?",
            (foreign.challenge_id,),
        ).fetchone()
    assert '"challenge_status":"pending"' in stored[0]
    gateway.close()
