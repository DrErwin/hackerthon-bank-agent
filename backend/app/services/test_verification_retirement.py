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
9. 退役事实不可读：调用方只能看到 pending，无法从银行侧确认「该尝试已退役」。
10. 已退役尝试仍能从 demo 取码入口拿到验证码。
11. 同 submission_id 的既有幂等重放因退役守卫改抛异常（破坏既有幂等）。

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


def create(gateway, user, operation_id, revision=1):
    return gateway.create_verification(
        user, "action_step_up", operation_id, revision, action_summary(operation_id, revision),
    )


def retire(gateway, user, operation_id, revision=1):
    return gateway.retire_action_challenges(
        user, operation_id=operation_id, action_revision=revision,
    )


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
        challenge = create(gateway, user, operation_id)
        original = stored_challenge(bank, challenge.challenge_id)

        retirement = retire(gateway, user, operation_id)
        assert retirement.operation_id == operation_id
        assert retirement.action_revision == 1
        assert retirement.retired_challenge_ids == [challenge.challenge_id]
        # 退役只增不改：挑战行（含时间戳/结果）原样保留。
        assert stored_challenge(bank, challenge.challenge_id) == original

        # 已退役的旧尝试不能再创建挑战。
        with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
            create(gateway, user, operation_id)

        # 旧完全码到期（同一既有 5 分钟规则）后，同 task 新尝试正常。
        clock.advance(301)
        new_operation = uuid4()
        assert create(gateway, user, new_operation).challenge_status == "pending"
        # 同 task 的基础身份验证也不受旧动作退役影响。
        assert gateway.create_verification(user, "basic_identity").challenge_status == "pending"
        # 旧尝试即使过期了也仍不能重建。
        with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
            create(gateway, user, operation_id)
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
        challenge = create(gateway, user, operation_id)
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
            retire(gateway, user, operation_id)
        assert caught.value.reason_code == reason
        assert retirement_rows(bank) == []

        # 既有终止规则不变：先失败/先过期仍会终止同 task 的新尝试。
        if mode in {"failed", "expired"}:
            other = uuid4()
            with pytest.raises(VerificationTerminated):
                create(gateway, user, other)
    finally:
        gateway.close()


def test_refused_retirement_rolls_back_lazy_expiry_until_next_read(tmp_path):
    """失败模式 2 + 回滚语义：被拒退役整笔回滚，行仍 pending，下一次读取才终态化。

    退役判定用的 `_expire` 刷新在同一事务内，拒绝时整笔回滚，所以过期不落库；
    这不是「永远 pending」，而是留给下一次读取/扫描按既有规则终态化。
    """
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        challenge = create(gateway, user, operation_id)
        clock.advance(301)
        with pytest.raises(ChallengeNotRetireable) as caught:
            retire(gateway, user, operation_id)
        assert caught.value.reason_code == "ALREADY_EXPIRED"
        assert '"challenge_status":"pending"' in stored_challenge(bank, challenge.challenge_id)
        assert retirement_rows(bank) == []
        # 下一次读取按既有规则把同一行终态化。
        assert gateway.get_verification(user, challenge.challenge_id).challenge_status == "expired"
        assert '"challenge_status":"expired"' in stored_challenge(bank, challenge.challenge_id)
    finally:
        gateway.close()


def test_retire_without_challenge_succeeds_and_blocks_late_creation(tmp_path):
    """失败模式 5/8：确认等待态无挑战也成功；随后迟到创建旧尝试被拒；重启后同一事实。

    已知残留风险（登记，不在本票解决）：该 operation 在银行库尚无任何挑战时，
    银行无法区分「合法新尝试」与「错 task 自报 operation」，因此这里仍写退役行、
    防迟到创建；operation 归属与调用授权必须由 02/03 用可信上下文把关，不能
    依赖银行侧认 operation 归属。
    """
    bank, gateway, clock = ready(tmp_path)
    user = context()
    operation_id = uuid4()
    retirement = retire(gateway, user, operation_id)
    assert retirement.retired_challenge_ids == []
    # 无挑战分支同样写退役事实（防迟到创建）。
    assert len(retirement_rows(bank)) == 1
    assert gateway.retirement_for(user, operation_id, 1) == retirement
    with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
        create(gateway, user, operation_id)
    # 其它尝试不受影响。
    other = uuid4()
    assert create(gateway, user, other).challenge_status == "pending"
    gateway.close()

    reopened = MockBankService(MockBankStore(StoragePaths(tmp_path).bank), demo_secret=DEMO_SECRET)
    assert reopened.verification.retire_action_challenges(
        user, operation_id=operation_id, action_revision=1,
    ).retirement_id == retirement.retirement_id
    assert len(retirement_rows(reopened)) == 1


def test_retirement_for_reads_fact_with_correct_ownership(tmp_path):
    """失败模式 9：退役事实可从银行侧只读读出；跨 scope 读不到（不泄露存在性）。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        challenge = create(gateway, user, operation_id)
        # 未退役时读不到，且只读调用不产生事实。
        assert gateway.retirement_for(user, operation_id, 1) is None
        assert retirement_rows(bank) == []

        retirement = retire(gateway, user, operation_id)
        # 读与写同一银行库：返回同一事实，不产生新行。
        assert gateway.retirement_for(user, operation_id, 1) == retirement
        assert bank.verification.retirement_for(user, operation_id, 1) == retirement
        assert len(retirement_rows(bank)) == 1
        # 只读调用不动挑战状态。
        assert gateway.retirement_for(user, operation_id, 1).retired_challenge_ids == [
            challenge.challenge_id,
        ]
        assert '"challenge_status":"pending"' in stored_challenge(bank, challenge.challenge_id)

        # 跨用户/轮次/task 读不到，不泄露他人退役事实。
        for foreign in (context(user="U2"), context(round_id="D9"), context(task="T2")):
            assert gateway.retirement_for(foreign, operation_id, 1) is None
        # 同一 owner/task/round 的会话恢复仍是同一尝试（只读也不受 session 影响）。
        assert gateway.retirement_for(context(session="S2"), operation_id, 1) == retirement
    finally:
        gateway.close()


def test_get_demo_code_refused_after_retirement_without_state_change(tmp_path):
    """失败模式 10：demo 取码入口对已退役尝试拒绝，且不改挑战状态。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        challenge = create(gateway, user, operation_id)
        assert gateway.get_demo_code_for_api(user, challenge.challenge_id)
        original = stored_challenge(bank, challenge.challenge_id)
        retire(gateway, user, operation_id)
        with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
            gateway.get_demo_code_for_api(user, challenge.challenge_id)
        assert stored_challenge(bank, challenge.challenge_id) == original
    finally:
        gateway.close()


def test_retirement_idempotent_and_scoped_to_operation_revision(tmp_path):
    """失败模式 3：同参只一份事实；异 operation/revision 互不影响、不改已有记录。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        first_operation, second_operation = uuid4(), uuid4()
        first = create(gateway, user, first_operation)
        second = create(gateway, user, second_operation, 2)
        retirement = retire(gateway, user, first_operation)
        assert retirement.retired_challenge_ids == [first.challenge_id]
        assert retire(gateway, user, first_operation) == retirement

        other_revision = retire(gateway, user, first_operation, 3)
        assert other_revision.retirement_id != retirement.retirement_id
        assert other_revision.retired_challenge_ids == []
        # 异参不改变第一条退役事实。
        assert retire(gateway, user, first_operation) == retirement

        # 未被退役的尝试照旧可用。
        assert create(gateway, user, second_operation, 2).challenge_id == second.challenge_id
        assert retire(gateway, user, second_operation, 2).retired_challenge_ids == [
            second.challenge_id,
        ]
        assert len(retirement_rows(bank)) == 3
    finally:
        gateway.close()


def test_retire_after_resend_seals_only_current_pending_challenge(tmp_path):
    """失败模式 4/11：重发后的尝试退役封存当前 pending 挑战；同 submission 重放仍幂等。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        original = create(gateway, user, operation_id)
        resend_submission = uuid4()
        replacement = gateway.resend_verification_code(
            user, original.challenge_id, resend_submission,
        )
        retirement = retire(gateway, user, operation_id)
        assert retirement.retired_challenge_ids == [replacement.challenge_id]
        # 退役前已记录的重发：同一 submission_id 重放返回原记录，不因退役改抛。
        assert gateway.resend_verification_code(
            user, original.challenge_id, resend_submission,
        ) == replacement
        with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
            gateway.resend_verification_code(user, replacement.challenge_id, uuid4())
        with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
            gateway.verify_code(
                user, replacement.challenge_id, uuid4(),
                gateway.get_demo_code_for_api(user, replacement.challenge_id),
            )
    finally:
        gateway.close()


def test_submission_replay_survives_retirement_but_new_submission_is_rejected(tmp_path):
    """失败模式 11：退役前已记录的提交按既有幂等重放；只有新提交被拒。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        challenge = create(gateway, user, operation_id)
        code = gateway.get_demo_code_for_api(user, challenge.challenge_id)
        submission = uuid4()
        recorded = gateway.verify_code(user, challenge.challenge_id, submission, code)
        assert recorded.kind == "verified" and recorded.verification_id is None
        retire(gateway, user, operation_id)
        # 同一 submission_id 重放命中既有记录，不因退役改抛。
        assert gateway.verify_code(user, challenge.challenge_id, submission, code) == recorded
        assert submission_count(bank) == 1
        # 新提交（无该 submission 记录）才被退役守卫拒绝，且不新增记录。
        with pytest.raises(ChallengeRetired, match="CHALLENGE_RETIRED"):
            gateway.verify_code(user, challenge.challenge_id, uuid4(), code)
        assert submission_count(bank) == 1
    finally:
        gateway.close()


def test_retired_attempt_rejects_late_code_and_face_entries(tmp_path):
    """失败模式 4/7：退役后各旧入口全部拒绝，挑战状态与提交记录不变。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        challenge = create(gateway, user, operation_id)
        gateway.start_face(user, challenge.challenge_id, uuid4())
        code = gateway.get_demo_code_for_api(user, challenge.challenge_id)
        # 只过了验证码、人脸未完成：challenge 仍 pending，允许退役。
        gateway.verify_code(user, challenge.challenge_id, uuid4(), code)
        original = stored_challenge(bank, challenge.challenge_id)
        submissions = submission_count(bank)

        retirement = retire(gateway, user, operation_id)
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
        with pytest.raises(ChallengeRetired):
            gateway.get_demo_code_for_api(user, challenge.challenge_id)
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
        challenge = create(gateway, user, operation_id)
        for foreign in (context(user="U2"), context(round_id="D9"), context(task="T2")):
            with pytest.raises(ValueError, match="ACCESS_DENIED"):
                retire(gateway, foreign, operation_id)
        assert retirement_rows(bank) == []

        # 同一 owner/task/round 的会话恢复仍是同一尝试。
        recovered = retire(gateway, context(session="S2"), operation_id)
        assert recovered.retired_challenge_ids == [challenge.challenge_id]
        # 退役后外来 scope 仍被拒绝。
        with pytest.raises(ValueError, match="ACCESS_DENIED"):
            retire(gateway, context(user="U2"), operation_id)
        assert len(retirement_rows(bank)) == 1
    finally:
        gateway.close()


def test_retire_action_challenges_requires_keyword_arguments(tmp_path):
    """审查建议 5：新写接缝为 keyword-only，位置参数直接 TypeError。"""
    bank, gateway, clock = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        create(gateway, user, operation_id)
        with pytest.raises(TypeError):
            gateway.retire_action_challenges(user, operation_id, 1)
        with pytest.raises(TypeError):
            bank.verification.retire_action_challenges(user, operation_id, 1)
        assert gateway.retire_action_challenges(
            user, operation_id=operation_id, action_revision=1,
        )
    finally:
        gateway.close()


def test_concurrent_same_attempt_retirement_returns_single_fact(tmp_path):
    """失败模式 8：跨连接并发同参只产生一份退役事实（银行库 BEGIN IMMEDIATE 串行化）。"""
    bank, gateway, clock = ready(tmp_path)
    user = context()
    operation_id = uuid4()
    create(gateway, user, operation_id)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            facts = list(pool.map(
                lambda _: retire(gateway, user, operation_id), range(2),
            ))
        assert facts[0].retirement_id == facts[1].retirement_id
        assert facts[0].retired_challenge_ids == facts[1].retired_challenge_ids
        assert len(retirement_rows(bank)) == 1
        assert gateway.retirement_for(user, operation_id, 1) == facts[0]
    finally:
        gateway.close()
