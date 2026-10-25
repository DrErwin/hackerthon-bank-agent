"""旧尝试挑战退役（G2-B）：银行库是「撤离是否先于失败/超时」的唯一权威。

写实现之前的失败模式清单（每条至少一个用例）：
1. pending 挑战退役后，旧挑战随后超时仍触发同 task 的 VerificationTerminated，拖停新尝试。
2. 旧尝试已 passed/failed/expired 仍退役成功并写退役事实，等于用「修改」恢复已终止动作。
3. 退役不幂等：同参重复调用写两份事实；异参调用改写已有事实。
4. 已退役尝试还能经 create_verification/resend_code/verify_code/start_face/verify_face
   迟到恢复，或生成新挑战/提交记录。
5. 无挑战（确认等待）时退役失败，或退役后仍能为旧尝试创建挑战。
6. 跨用户/跨轮次/跨 task 的调用能退役他人尝试，或写错 scope 的退役事实。
7. 退役删除挑战行或改写历史结果/时间戳；被拒退役留下退役事实。
8. 退役只活在进程内：重启后丢失，或并发同参调用产生两份。

这些用例只覆盖隔离银行库；真实跨库联合链路由安全/平台票与本人 E2E 验证。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import uuid4

import pytest

from app.contracts.bank import PayeeDisplay
from app.contracts.common import DisplayField
from app.contracts.platform import TrustedContext
from app.contracts.security import VerificationSummary
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.services.mock_bank.verification import (
    AdminContext, ChallengeNotRetireable, ChallengeRetired, VerificationTerminated,
)
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


def action_summary(operation_id, revision=1):
    return VerificationSummary(
        operation_id=operation_id, action_revision=revision,
        source_confirmation_id="C1", source_confirmation_version=1,
        action_name="bank.submit_transfer", amount_fen=50_000,
        payee=PayeeDisplay(
            payee_id="A2", name_masked="王*", account_masked="****0002",
            remark="妈妈", bank_name="模拟合作银行",
        ),
        display_fields=[DisplayField(name="amount", label="金额", value_text="500 元")],
    )


def retire(bank, user, operation_id, revision=1):
    return bank.verification.retire_action_challenges(user, operation_id, revision)


def retirement_rows(bank):
    connection = sqlite3.connect(bank.store.path)
    connection.row_factory = sqlite3.Row
    try:
        return [
            dict(row) for row in connection.execute(
                "SELECT * FROM bank_verification_retirements",
            ).fetchall()
        ]
    finally:
        connection.close()


def stored_challenge(bank, challenge_id):
    with sqlite3.connect(bank.store.path) as connection:
        row = connection.execute(
            "SELECT challenge_json FROM bank_verification_challenges WHERE challenge_id = ?",
            (challenge_id,),
        ).fetchone()
    return row[0]


def submission_count(bank):
    with sqlite3.connect(bank.store.path) as connection:
        return connection.execute("SELECT COUNT(*) FROM bank_verification_submissions").fetchone()[0]


def test_retire_pending_wins_and_late_expiry_does_not_stop_new_attempt(tmp_path):
    """失败模式 1/4/7：撤离先胜；旧挑战行保留，稍后到期不再拖停新方案。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        challenge = gateway.create_verification(
            user, "action_step_up", operation_id, 1, action_summary(operation_id),
        )
        original = stored_challenge(bank, challenge.challenge_id)

        retirement = gateway.retire_action_challenges(user, operation_id, 1)
        assert retirement.operation_id == operation_id
        assert retirement.action_revision == 1
        assert retirement.retired_challenge_ids == [challenge.challenge_id]
        # 退役只增不改：挑战行（含时间戳/结果）原样保留。
        assert stored_challenge(bank, challenge.challenge_id) == original

        # 已退役的旧尝试不能再创建挑战。
        with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
            gateway.create_verification(
                user, "action_step_up", operation_id, 1, action_summary(operation_id),
            )

        # 旧完全码到期（同一既有 5 分钟规则）后，同 task 新尝试正常。
        clock.advance(301)
        new_operation = uuid4()
        new_challenge = gateway.create_verification(
            user, "action_step_up", new_operation, 1, action_summary(new_operation),
        )
        assert new_challenge.challenge_status == "pending"
        # 同 task 的基础身份验证也不受旧动作退役影响。
        assert gateway.create_verification(user, "basic_identity").challenge_status == "pending"
        # 旧尝试即使过期了也仍不能重建。
        with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
            gateway.create_verification(
                user, "action_step_up", operation_id, 1, action_summary(operation_id),
            )
        # 历史仍可回放：旧行被惰性终态化，而不是被删除或改写。
        assert gateway.get_verification(user, challenge.challenge_id).challenge_status == "expired"
    finally:
        gateway.close()


@pytest.mark.parametrize("mode,reason", [
    ("failed", "ALREADY_FAILED"),
    ("passed", "ALREADY_PASSED"),
    ("expired", "ALREADY_EXPIRED"),
])
def test_retirement_refused_when_attempt_already_terminal(tmp_path, mode, reason):
    """失败模式 2/7：先失败/先过期/已通过必须拒绝，且不写退役事实。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        challenge = gateway.create_verification(
            user, "action_step_up", operation_id, 1, action_summary(operation_id),
        )
        if mode == "failed":
            gateway.verify_code(user, challenge.challenge_id, uuid4(), "000000")
        elif mode == "passed":
            gateway.start_face(user, challenge.challenge_id, uuid4())
            gateway.verify_code(
                user, challenge.challenge_id, uuid4(),
                gateway.get_demo_code_for_api(user, challenge.challenge_id),
            )
            passed = gateway.verify_face(
                AdminContext("admin", True, "D1", "U1"), challenge.challenge_id,
                uuid4(), "passed",
            )
            assert passed.kind == "verified" and passed.verification_id
        else:
            clock.advance(301)  # 退役事务内按既有规则刷新为 expired

        with pytest.raises(ChallengeNotRetireable) as caught:
            gateway.retire_action_challenges(user, operation_id, 1)
        assert caught.value.reason_code == reason
        assert retirement_rows(bank) == []

        # 既有终止规则不变：先失败/先过期仍会终止同 task 的新尝试。
        if mode in {"failed", "expired"}:
            other = uuid4()
            with pytest.raises(VerificationTerminated):
                gateway.create_verification(
                    user, "action_step_up", other, 1, action_summary(other),
                )
    finally:
        gateway.close()


def test_retire_without_challenge_succeeds_and_blocks_late_creation(tmp_path):
    """失败模式 5/8：确认等待态无挑战也成功；随后迟到创建旧尝试被拒；重启后同一事实。"""
    bank, gateway, clock = ready(tmp_path)
    user = context()
    operation_id = uuid4()
    retirement = gateway.retire_action_challenges(user, operation_id, 1)
    assert retirement.retired_challenge_ids == []
    with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
        gateway.create_verification(
            user, "action_step_up", operation_id, 1, action_summary(operation_id),
        )
    # 其它尝试不受影响。
    other = uuid4()
    assert gateway.create_verification(
        user, "action_step_up", other, 1, action_summary(other),
    ).challenge_status == "pending"
    gateway.close()

    reopened = MockBankService(MockBankStore(StoragePaths(tmp_path).bank), demo_secret=DEMO_SECRET)
    assert retire(reopened, user, operation_id, 1).retirement_id == retirement.retirement_id
    assert len(retirement_rows(reopened)) == 1


def test_retirement_idempotent_and_scoped_to_operation_revision(tmp_path):
    """失败模式 3：同参只一份事实；异 operation/revision 互不影响、不改已有记录。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        first_operation, second_operation = uuid4(), uuid4()
        first = gateway.create_verification(
            user, "action_step_up", first_operation, 1, action_summary(first_operation),
        )
        second = gateway.create_verification(
            user, "action_step_up", second_operation, 2, action_summary(second_operation, 2),
        )
        retirement = gateway.retire_action_challenges(user, first_operation, 1)
        assert retirement.retired_challenge_ids == [first.challenge_id]
        assert gateway.retire_action_challenges(user, first_operation, 1) == retirement

        other_revision = gateway.retire_action_challenges(user, first_operation, 3)
        assert other_revision.retirement_id != retirement.retirement_id
        assert other_revision.retired_challenge_ids == []
        # 异参不改变第一条退役事实。
        assert gateway.retire_action_challenges(user, first_operation, 1) == retirement

        # 未被退役的尝试照旧可用。
        assert gateway.create_verification(
            user, "action_step_up", second_operation, 2, action_summary(second_operation, 2),
        ).challenge_id == second.challenge_id
        assert gateway.retire_action_challenges(
            user, second_operation, 2,
        ).retired_challenge_ids == [second.challenge_id]
        assert len(retirement_rows(bank)) == 3
    finally:
        gateway.close()


def test_retire_after_resend_seals_only_current_pending_challenge(tmp_path):
    """失败模式 4：重发后的尝试退役封存当前 pending 挑战（旧 superseded 行保留）。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        original = gateway.create_verification(
            user, "action_step_up", operation_id, 1, action_summary(operation_id),
        )
        replacement = gateway.resend_verification_code(user, original.challenge_id, uuid4())
        retirement = gateway.retire_action_challenges(user, operation_id, 1)
        assert retirement.retired_challenge_ids == [replacement.challenge_id]
        with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
            gateway.resend_verification_code(user, replacement.challenge_id, uuid4())
        with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
            gateway.verify_code(
                user, replacement.challenge_id, uuid4(),
                gateway.get_demo_code_for_api(user, replacement.challenge_id),
            )
    finally:
        gateway.close()


def test_retired_attempt_rejects_late_code_and_face_entries(tmp_path):
    """失败模式 4/7：退役后四个旧入口全部拒绝，挑战状态与提交记录不变。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        challenge = gateway.create_verification(
            user, "action_step_up", operation_id, 1, action_summary(operation_id),
        )
        gateway.start_face(user, challenge.challenge_id, uuid4())
        code = gateway.get_demo_code_for_api(user, challenge.challenge_id)
        # 只过了验证码、人脸未完成：challenge 仍 pending，允许退役。
        gateway.verify_code(user, challenge.challenge_id, uuid4(), code)
        original = stored_challenge(bank, challenge.challenge_id)
        submissions = submission_count(bank)

        retirement = gateway.retire_action_challenges(user, operation_id, 1)
        assert retirement.retired_challenge_ids == [challenge.challenge_id]

        with pytest.raises(ChallengeRetired):
            gateway.resend_verification_code(user, challenge.challenge_id, uuid4())
        with pytest.raises(ChallengeRetired):
            gateway.verify_code(user, challenge.challenge_id, uuid4(), code)
        with pytest.raises(ChallengeRetired):
            gateway.start_face(user, challenge.challenge_id, uuid4())
        with pytest.raises(ChallengeRetired):
            gateway.verify_face(
                AdminContext("admin", True, "D1", "U1"), challenge.challenge_id,
                uuid4(), "passed",
            )
        assert stored_challenge(bank, challenge.challenge_id) == original
        assert submission_count(bank) == submissions
    finally:
        gateway.close()


def test_retirement_scope_rejects_foreign_user_round_and_task(tmp_path):
    """失败模式 6：跨用户/跨轮次/跨 task 不能退役他人尝试，也不写错 scope 的事实。

    会话不属于尝试身份（权威设计 §2：task + operation_id + action_revision）：
    同一 owner 的会话恢复/迁移后仍是同一尝试，返回同一条退役事实。
    """
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        challenge = gateway.create_verification(
            user, "action_step_up", operation_id, 1, action_summary(operation_id),
        )
        for foreign in (context(user="U2"), context(round_id="D9"), context(task="T2")):
            with pytest.raises(ValueError, match="ACCESS_DENIED"):
                gateway.retire_action_challenges(foreign, operation_id, 1)
        assert retirement_rows(bank) == []

        # 同一 owner/task/round 的会话恢复仍是同一尝试。
        recovered = gateway.retire_action_challenges(context(session="S2"), operation_id, 1)
        assert recovered.retired_challenge_ids == [challenge.challenge_id]
        # 退役后外来 scope 仍被拒绝。
        with pytest.raises(ValueError, match="ACCESS_DENIED"):
            gateway.retire_action_challenges(context(user="U2"), operation_id, 1)
        assert len(retirement_rows(bank)) == 1
    finally:
        gateway.close()


def test_concurrent_same_attempt_retirement_returns_single_fact(tmp_path):
    """失败模式 8：跨连接并发同参只产生一份退役事实（银行库 BEGIN IMMEDIATE 串行化）。"""
    bank, gateway, clock = ready(tmp_path)
    user = context()
    operation_id = uuid4()
    gateway.create_verification(
        user, "action_step_up", operation_id, 1, action_summary(operation_id),
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            facts = list(pool.map(
                lambda _: gateway.retire_action_challenges(user, operation_id, 1), range(2),
            ))
        assert facts[0].retirement_id == facts[1].retirement_id
        assert facts[0].retired_challenge_ids == facts[1].retired_challenge_ids
        assert len(retirement_rows(bank)) == 1
    finally:
        gateway.close()
