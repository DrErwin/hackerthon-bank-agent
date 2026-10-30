"""Scope inheritance reads the real bank again; it never edits the old result."""
from uuid import uuid4

import pytest

from app.agent_platform.harness import RunTrace
from app.contracts.bills import BillDetails
from app.contracts.common import TaskStatus
from app.contracts.platform import StartTransferInput
from app.modules.bills.test_public_integration import env, payload, trusted


def followup(env, scope, text, task_id="followup"):
    context = trusted(task_id)
    env.application.create_task(task_id, "U1", "S1", "D1", "R1", TaskStatus.RUNNING, {})
    entry = env.registry.get("bills.summarize").factory(context,
        env.memory.checkpointer(env.harness._scope(context), task_id),
        RunTrace(env.audit, context, task_id, str(uuid4())))
    request = StartTransferInput(request_id=uuid4(), intent_text=text)
    return entry, context, request, entry.start(context, request, inherited_scope=scope,
                                               thread_id=entry.saver.thread_id)


def test_details_keep_account_and_dates_and_recheck_permissions(env):
    original = env.harness.start(trusted(), uuid4(), "2026年9月所有账户账单")
    scope = payload(original).scope
    balances = env.balances()
    entry, context, request, result = followup(env, scope, "看看餐饮明细")
    details = payload(result, BillDetails)
    assert result.status == TaskStatus.SUCCEEDED
    assert details.scope == scope
    assert details.category.value == "dining"
    assert details.transactions
    replay = entry.start(context, request, inherited_scope=scope, thread_id=entry.saver.thread_id)
    assert payload(replay, BillDetails) == details
    assert env.balances() == balances and env.gateway.bank_writes == 0
    env.permission = False
    _, _, _, denied = followup(env, scope, "看看餐饮明细", "denied")
    assert denied.status == TaskStatus.FAILED
    assert denied.data is None


@pytest.mark.parametrize("text,wait", [
    ("最近一周餐饮明细", "月份"), ("换个账户看看餐饮明细", "哪张卡"),
    ("今天餐饮明细", "月份"), ("2026-09-01餐饮明细", "月份"),
    ("上星期餐饮明细", "月份"), ("上礼拜餐饮明细", "月份"),
    ("换张卡看看餐饮明细", "哪张卡"), ("第二张卡餐饮明细", "哪张卡"),
])
def test_new_constraints_are_not_replaced_by_old_scope(env, text, wait):
    scope = payload(env.harness.start(trusted(), uuid4(), "2026年9月所有账户账单")).scope
    _, _, _, result = followup(env, scope, text)
    assert result.status == TaskStatus.WAITING_INPUT
    assert wait in result.interaction.prompt
    assert "L01" not in result.message


def test_explicit_new_month_retains_only_unchanged_accounts(env):
    scope = payload(env.harness.start(trusted(), uuid4(), "2026年9月所有账户账单")).scope
    _, _, _, result = followup(env, scope, "2026年8月餐饮明细")
    details = payload(result, BillDetails)
    assert details.scope.account_ids == scope.account_ids
    assert details.scope.start_at.month == 8
