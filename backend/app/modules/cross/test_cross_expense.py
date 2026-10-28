"""Ticket v05-cross-business/01: expense reduction on the shared plan skeleton.

Tier one runs the real platform seam — registry, dispatch_child, resume_child,
durable task relations — with the subscription children being the module's real
entry and service over scripted bank/gate ports, and a contract-shaped bills
stand-in (the real bills entry does not accept its declared typed input yet;
that gap is registered with the bills owner). Tier two composes the real
runtime for one end-to-end cancellation through the real gate and bank.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.audit.journal import AuditJournal
from app.contracts.bank import (
    AccountList, AccountSummary, BankError, OperationResult, QueryFailure, QueryOk, Transaction,
    TransactionList,
)
from app.contracts.bills import BillSummarizeInput
from app.contracts.common import SecurityDecisionCode, TaskStatus
from app.contracts.cross import CrossStartInput, CrossScenario
from app.contracts.platform import StartTransferInput, TrustedContext
from app.contracts.subscription import (
    SubscriptionCancelReceipt, SubscriptionMandate, SubscriptionMandateList,
)
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult
from app.memory.adapter import MemoryAdapter, MemoryContext
from app.modules.cross.entry import CrossEntry, infer_scenario, month_range, register_cross
from app.modules.subscription.entry import register_subscription
from app.modules.subscription.ports import ExecutionOutcome, GateAnswer
from app.storage.application import ApplicationStore

from app.agent_platform.harness import AgentHarness
from app.agent_platform.registry import CapabilityRegistry
from app.agent_platform.own_bank_queries import manifest as accounts_manifest
from app.modules.bills.manifest import MANIFEST as BILLS_MANIFEST

NOW = datetime(2026, 10, 20, 4, 0, tzinfo=timezone.utc)
CHINA = timezone(timedelta(hours=8))
FORBIDDEN = ("会员可用至", "还能用到", "先退订再重新订阅", "先解约再重签")


class PlannerStub:
    provider = "scripted"
    model_name = "cross-test"
    config_version = "test-v1"


def parent_trusted() -> TrustedContext:
    return TrustedContext(user_id="U1", session_id="S1", task_id="PARENT", run_id="PR1",
                          parent_task_id=None, demo_round_id="D1")


# ------------------------------------------------------------------ bank doubles


def at(y, m, d, hour=9):
    return datetime(y, m, d, hour, 0, tzinfo=CHINA)


def mandate(mandate_id, merchant_id, name, service, amount, status="active",
            next_day=None):
    return SubscriptionMandate(
        mandate_id=mandate_id, account_id="A1", account_masked="****0001",
        merchant_id=merchant_id, merchant_name=name, service_name=service,
        amount_fen=amount, cycle="monthly",
        next_billing_at=None if next_day is None else at(2026, 11, next_day),
        last_billed_at=at(2026, 9, 10), status=status, signed_at=at(2025, 1, 5),
        cancelled_at=None if status == "active" else at(2026, 9, 1),
        cancel_operation_id=None if status == "active" else str(uuid4()),
    )


def seeded_mandates():
    return [
        mandate("sub_001", "M_UYUN", "优酷视频", "优酷 VIP 连续包月", 2500, next_day=5),
        mandate("sub_002", "M_UDRV", "云端网盘", "超级会员连续包月", 3900, next_day=12),
        mandate("sub_003", "M_XMAL", "喜马拉雅", "巅峰会员连续包月", 1500, status="cancelled"),
    ]


def flow(transaction_id, merchant_id, name, amount, month):
    return Transaction(
        transaction_id=transaction_id, account_id="A1", occurred_at=at(2026, month, 28),
        amount_fen=amount, nature="consumption", category="other", direction="outflow",
        counterparty_id=merchant_id, counterparty_name=name,
        counterparty_account_masked=None, channel="快捷支付",
        summary=f"{name}自动扣费", original_transaction_id=None, original_occurred_at=None,
    )


def seeded_rows():
    rows = [flow(f"UY{m}", "M_UYUN", "优酷视频", 2500, m) for m in (4, 5, 6, 7, 8, 9)]
    rows += [flow(f"DR{m}", "M_UDRV", "云端网盘", 3900, m) for m in (8, 9)]
    rows += [flow(f"OA{m}", "M_OASIS", "绿洲健身", 3900, m) for m in (5, 6, 7, 8, 9)]
    return rows


class FakeSubscriptionBank:
    def __init__(self, *, mandates=None, rows=None, unknown=()):
        self.mandates = seeded_mandates() if mandates is None else mandates
        self.rows = seeded_rows() if rows is None else rows
        self.unknown = set(unknown)
        self.cancel_calls: list[str] = []

    def accounts(self, context):
        return QueryOk(kind="ok", data=AccountList(accounts=[AccountSummary(
            account_id="A1", account_type="class_i", account_masked="尾号 0001",
            available_balance_fen=1_000_000, display_name="主账户", bank_name="模拟银行")]))

    def mandates_for(self, context, account_id=None, status=None):
        selected = [m for m in self.mandates if account_id in (None, m.account_id)
                    and (status is None or m.status == status)]
        return QueryOk(kind="ok", data=SubscriptionMandateList(mandates=selected, as_of=NOW))

    def transactions(self, context, account_id, start_at, end_at):
        rows = [row for row in self.rows if start_at <= row.occurred_at < end_at]
        return QueryOk(kind="ok", data=TransactionList(transactions=rows, as_of=NOW))

    def cancel(self, context, operation_id, plan, decision):
        self.cancel_calls.append(plan.mandate_id)
        target = next((m for m in self.mandates if m.mandate_id == plan.mandate_id), None)
        stopped = target.next_billing_at
        self.mandates = [
            mandate(m.mandate_id, m.merchant_id, m.merchant_name, m.service_name, m.amount_fen,
                    status="cancelled") if m.mandate_id == plan.mandate_id else m
            for m in self.mandates]
        receipt = SubscriptionCancelReceipt(
            mandate_id=target.mandate_id, account_id=target.account_id,
            account_masked=target.account_masked, merchant_id=target.merchant_id,
            merchant_name=target.merchant_name, service_name=target.service_name,
            amount_fen=target.amount_fen, cycle=target.cycle,
            previous_next_billing_at=stopped, effective_stop_at=stopped, cancelled_at=NOW,
        )
        return OperationResult[SubscriptionCancelReceipt](
            operation_id=operation_id, operation_type="bank.cancel_subscription",
            operation_status="succeeded", recorded_at=NOW, updated_at=NOW,
            receipt=receipt, failure=None,
        )


class ScriptedPorts:
    """Real-entry ports with the gate state kept in a shared dict.

    The real gate keeps its decisions in platform-owned durable facts, so a fresh
    entry per resume still sees them; the shared dict mirrors exactly that seam.
    """

    def __init__(self, bank, gate_states):
        self.bank, self.gate_states = bank, gate_states

    def accounts(self, context):
        return self.bank.accounts(context)

    def mandates(self, context, account_id=None, status=None):
        return self.bank.mandates_for(context, account_id, status)

    def transactions(self, context, account_id, start_at, end_at):
        return self.bank.transactions(context, account_id, start_at, end_at)

    def check_cancel(self, context, plan, *, revision=None):
        if plan.mandate_id in getattr(self.bank, "blocked_mandates", ()):
            return GateAnswer(decision=SecurityDecisionCode.BLOCK,
                              reason_code="HIGH_RISK", operation_id=str(uuid4()))
        state = self.gate_states.get(context.task_id)
        if state is None:
            interaction = InteractionRequest(
                interaction_id=str(uuid4()), kind="confirmation", prompt="确认退订",
                required_fields=[],
                options=[InteractionOption(id="approve", label="确认办理"),
                         InteractionOption(id="cancel", label="取消")],
                record_ref=f"conf-{context.task_id[:8]}")
            return GateAnswer(decision=SecurityDecisionCode.REQUIRE_CONFIRMATION,
                              interaction=interaction, operation_id=str(uuid4()))
        return GateAnswer(decision=SecurityDecisionCode.ALLOW, operation_id=state)

    def execute_cancel(self, context, plan, *, revision=None):
        if plan.mandate_id in self.bank.unknown:
            return ExecutionOutcome(
                executed=True, state="unknown", result=None,
                decision=GateAnswer(decision=SecurityDecisionCode.ALLOW,
                                    operation_id=str(uuid4())),
                operation_id=str(uuid4()))
        return ExecutionOutcome(
            executed=True, state="completed",
            result=self.bank.cancel(context, UUID(self.check_cancel(context, plan).operation_id),
                                    plan, None),
            decision=GateAnswer(decision=SecurityDecisionCode.ALLOW,
                                operation_id=self.check_cancel(context, plan).operation_id),
            operation_id=self.check_cancel(context, plan).operation_id)


BILLS_OK_DATA = {"consumption_net_fen": 360000, "comparison": {"delta_fen": 80000},
                 "categories": [{"category": "dining", "net_fen": 120000},
                                 {"category": "shopping", "net_fen": 90000},
                                 {"category": "other", "net_fen": 60000}]}


class ScriptedBills:
    """Contract-shaped bills stand-in (real manifest, real typed input)."""

    def __init__(self, script):
        self.script = script

    def start(self, trusted, request, *, thread_id=None):
        assert isinstance(request, BillSummarizeInput)
        if self.script == "ok":
            return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
                status=TaskStatus.SUCCEEDED, data=BILLS_OK_DATA,
                message="已对比最近两个完整月。", interaction=None, error=None,
                allowed_actions=[], recovery_required=False, recovery_reason=None)
        return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
            status=TaskStatus.FAILED, data=None, message="银行流水暂时查不到。",
            interaction=None, error=None, allowed_actions=[], recovery_required=False,
            recovery_reason=None)

    def resume(self, trusted, response, *, thread_id=None):
        return self.start(trusted, None, thread_id=thread_id)

    def recover_session(self, trusted, *, source_session_id, thread_id=None):
        return self.start(trusted, None, thread_id=thread_id)

    def checkpoint_context(self, trusted, *, thread_id=None):
        return None


class AccountsStub:
    def start(self, trusted, request, *, thread_id=None):
        assert isinstance(request, StartTransferInput)
        return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
            status=TaskStatus.SUCCEEDED,
            data={"accounts": [{"account_id": "A1", "account_masked": "尾号 0001",
                                 "display_name": "主账户"}]},
            message="已查到本人账户。", interaction=None, error=None,
            allowed_actions=[], recovery_required=False, recovery_reason=None)

    def resume(self, trusted, response, *, thread_id=None):
        return self.start(trusted, request=None)

    def recover_session(self, trusted, *, source_session_id, thread_id=None):
        return self.start(trusted, request=None)

    def checkpoint_context(self, trusted, *, thread_id=None):
        return None


def composition(tmp_path, *, mandates=None, rows=None, bills="ok", unknown=()):
    application = ApplicationStore(tmp_path / "app.sqlite")
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    harness = AgentHarness(application, memory, AuditJournal(tmp_path / "app.sqlite"),
                           CapabilityRegistry(), PlannerStub(),
                           authorize_capability=lambda _trusted, _definition: True)
    bank = FakeSubscriptionBank(mandates=mandates, rows=rows, unknown=unknown)
    gate_states: dict = {}
    register_subscription(harness.registry, lambda trusted, trace: ScriptedPorts(bank, gate_states),
                          lambda: NOW)
    harness.registry.register_module(BILLS_MANIFEST,
                                     lambda trusted, saver, trace: ScriptedBills(bills))
    harness.registry.register_module(accounts_manifest("list_accounts"),
                                     lambda trusted, saver, trace: AccountsStub())
    register_cross(harness, lambda: NOW)
    real_now = datetime.now(timezone.utc)
    application.create_session("S1", "U1", "D1", real_now.isoformat(),
                               (real_now + timedelta(days=1)).isoformat())
    application.create_task("PARENT", "U1", "S1", "D1", "PR1", "running", {})
    context = MemoryContext("U1", "S1", "D1")
    memory.agent_backend(context)
    entry = CrossEntry(harness, memory.checkpointer(context, "PARENT"), None, lambda: NOW)
    return harness, entry, bank, gate_states


def option_id(result, needle: str) -> str:
    options = result.interaction.options
    matches = [item for item in options if needle in item.label]
    assert len(matches) == 1, [item.label for item in options]
    return matches[0].id


def child_confirm(harness, gate_states, running_view, choice="approve"):
    child_id = running_view.data.interaction_task_id
    gate_states[child_id] = str(uuid4())
    return harness.resume_child(parent_trusted(), child_id, {"choice": choice},
                                plan_revision=running_view.data.plan_revision)


# ------------------------------------------------------------------- XL-S01


def test_s01_two_cancellations_one_kept_with_real_receipt(tmp_path):
    harness, entry, bank, gate_states = composition(tmp_path)
    menu = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="最近钱花得快，帮我处理不用的扣费"))
    assert menu.status is TaskStatus.WAITING_INPUT
    assert "3600.00" in menu.message and "多花 800.00" in menu.message
    assert "优酷" in menu.message
    steps = {step.step_id: step for step in menu.data.steps}
    assert [steps[name].status for name in ("accounts", "subscriptions", "bills_compare")] == [
        TaskStatus.SUCCEEDED] * 3
    assert menu.data.plan_revision == 1

    first = entry.resume(parent_trusted(), {"selected_option_id": option_id(menu, "优酷")})
    assert first.status is TaskStatus.RUNNING
    assert first.data.active_step_id == "cancel:sub_001"
    assert first.data.interaction_task_id is not None
    assert first.data.plan_revision == 2
    assert bank.cancel_calls == []
    done = child_confirm(harness, gate_states, first)
    assert done.status is TaskStatus.SUCCEEDED
    assert bank.cancel_calls == ["sub_001"]

    second_menu = entry.resume(parent_trusted(), {})
    assert second_menu.status is TaskStatus.WAITING_INPUT
    assert "喜马拉雅" not in second_menu.message  # already cancelled in the bank
    second = entry.resume(parent_trusted(),
                          {"selected_option_id": option_id(second_menu, "云端网盘")})
    done_two = child_confirm(harness, gate_states, second)
    assert done_two.status is TaskStatus.SUCCEEDED

    # Everything cancellable is now done in the bank: the plan goes straight to
    # the receipt — no menu can offer what the bank already stopped.
    receipt = entry.resume(parent_trusted(), {})
    assert receipt.status is TaskStatus.SUCCEEDED
    assert "已退订 优酷 VIP 连续包月：25.00元/每月，自 2026-11-05 起不再自动扣费。" in receipt.message
    assert "已退订 超级会员连续包月：39.00元/每月" in receipt.message
    assert "从下期起每月合计少扣 64.00元" in receipt.message
    assert "绿洲健身（疑似，银行无签约记录）" in receipt.message
    assert "已扣过的费用不退" in receipt.message
    assert not any(phrase in receipt.message for phrase in FORBIDDEN)
    assert bank.cancel_calls == ["sub_001", "sub_002"]
    final_steps = {step.step_id: step for step in receipt.data.steps}
    assert final_steps["cancel:sub_001"].amount_fen == 2500
    assert final_steps["cancel:sub_002"].status is TaskStatus.SUCCEEDED
    assert len(harness.child_task_summaries(parent_trusted())) == 5


# ------------------------------------------------------------------- XL-S02


def test_s02_bills_failure_is_reported_and_the_flow_still_runs(tmp_path):
    harness, entry, bank, _ = composition(tmp_path, bills="fail")
    menu = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="帮我减少不用的自动扣费"))
    assert menu.status is TaskStatus.WAITING_INPUT
    assert "账单对比暂时不可用" in menu.message
    assert "只基于签约盘点" in menu.message
    assert "0.00" not in menu.message.split("签约")[0]  # no zero-filled comparison
    finish = entry.resume(parent_trusted(), {"selected_option_id": option_id(menu, "保留全部")})
    assert finish.status is TaskStatus.SUCCEEDED
    assert bank.cancel_calls == []


def test_s02_empty_inventory_finishes_honestly(tmp_path):
    harness, entry, bank, _ = composition(tmp_path, mandates=[], rows=[])
    result = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="减少不用的开销"))
    assert result.status is TaskStatus.SUCCEEDED
    assert "当前没有可在线退订的签约" in result.message
    assert bank.cancel_calls == []
    assert len(harness.child_task_summaries(parent_trusted())) == 3


# ------------------------------------------------------------------- XL-S03


def test_s03_suspected_only_never_offers_cancellation(tmp_path):
    harness, entry, bank, _ = composition(tmp_path, mandates=[], rows=seeded_rows())
    result = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="看看哪些扣费不用了"))
    # Nothing here is a bank mandate: the flow says so instead of a menu, and
    # no write was ever dispatched (XL-S03).
    assert result.status is TaskStatus.SUCCEEDED
    assert "当前没有可在线退订的签约" in result.message
    assert "疑似周期扣费线索" in result.message and "绿洲健身" in result.message
    assert "不能在线退订" in result.message
    assert result.interaction is None
    assert bank.cancel_calls == []


# ------------------------------------------------------------------- XL-S04


def test_s04_cancel_before_confirmation_writes_nothing(tmp_path):
    harness, entry, bank, gate_states = composition(tmp_path)
    menu = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="减少不用的扣费"))
    picked = entry.resume(parent_trusted(),
                          {"selected_option_id": option_id(menu, "优酷")})
    assert picked.status is TaskStatus.RUNNING
    stopped = entry.resume(parent_trusted(), {"cancel": True})
    assert stopped.status is TaskStatus.CANCELLED
    assert "没有完成任何退订" in stopped.message
    assert stopped.data.stop_reason == "user_cancelled"
    assert bank.cancel_calls == []
    summaries = {item["step_id"]: item["status"] for item in harness.child_task_summaries(parent_trusted())}
    assert summaries["cancel:sub_001"] == "cancelled"


# ------------------------------------------------------------------- XL-S05


def test_s05_unknown_second_item_stays_pending_and_closes_partially(tmp_path):
    harness, entry, bank, gate_states = composition(tmp_path, unknown={"sub_002"})
    menu = entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(),
                                                          goal="减少不用的扣费"))
    first = entry.resume(parent_trusted(),
                         {"selected_option_id": option_id(menu, "优酷")})
    assert child_confirm(harness, gate_states, first).status is TaskStatus.SUCCEEDED

    second_menu = entry.resume(parent_trusted(), {})
    second = entry.resume(parent_trusted(),
                          {"selected_option_id": option_id(second_menu, "云端网盘")})
    unknown = child_confirm(harness, gate_states, second)
    assert unknown.status is TaskStatus.NEEDS_ATTENTION
    assert unknown.recovery_reason == "OPERATION_UNKNOWN"

    held = entry.resume(parent_trusted(), {})
    assert held.status is TaskStatus.RUNNING
    assert "已暂停" in held.message
    assert unknown.message in held.message
    assert "还没拿到银行的最终确认" in unknown.message
    assert "不要重复操作" in unknown.message
    assert "查询结果" in unknown.message
    assert "处理完成前不会继续办理其他项目" in held.message
    # Repeated resumes never redispatch or retry the unknown write.
    assert entry.resume(parent_trusted(), {}).message == held.message
    assert bank.cancel_calls == ["sub_001"]

    stopped = entry.resume(parent_trusted(), {"cancel": True})
    assert stopped.status is TaskStatus.PARTIALLY_SUCCEEDED
    assert stopped.message.startswith("部分完成，后续已停止")
    assert "已退订 优酷 VIP 连续包月" in stopped.message
    assert "云端网盘·超级会员连续包月 的退订结果还待核实" in stopped.message
    assert "每月合计少扣 25.00元" in stopped.message
    assert "64.00" not in stopped.message  # the unknown one never counts


# ---------------------------------------------------------------- X02 / X04


def test_x02_stale_interactions_and_options_are_refused(tmp_path):
    harness, entry, _, _ = composition(tmp_path)
    menu = entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(),
                                                          goal="减少不用的扣费"))
    old_interaction = menu.interaction.interaction_id
    old_option = menu.interaction.options[0].id
    picked = entry.resume(parent_trusted(),
                          {"selected_option_id": option_id(menu, "优酷")})
    with pytest.raises(ValueError, match="INVALID_OPTION"):
        entry.resume(parent_trusted(), {"selected_option_id": old_option})
    with pytest.raises(ValueError, match="INTERACTION_STALE"):
        entry.resume(parent_trusted(), {"selected_option_id": "whatever",
                                        "interaction_id": old_interaction})
    assert picked.status is TaskStatus.RUNNING


def test_x04_restart_and_repeat_resume_keep_one_child_per_step(tmp_path):
    harness, entry, bank, gate_states = composition(tmp_path)
    menu = entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(),
                                                          goal="减少不用的扣费"))
    picked = entry.resume(parent_trusted(),
                          {"selected_option_id": option_id(menu, "优酷")})
    context = MemoryContext("U1", "S1", "D1")
    restarted = CrossEntry(harness, harness.memory.checkpointer(context, "PARENT"), None,
                           lambda: NOW)
    again = restarted.resume(parent_trusted(), {})
    assert again.status is TaskStatus.RUNNING
    assert again.data.interaction_task_id == picked.data.interaction_task_id
    assert len(harness.child_task_summaries(parent_trusted())) == 4
    with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
        entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(), goal="另一个目标"))


def test_x03_state_belongs_to_its_own_task(tmp_path):
    harness, entry, _, _ = composition(tmp_path)
    entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(), goal="减少不用的扣费"))
    stranger = TrustedContext(user_id="U1", session_id="S1", task_id="OTHER", run_id="R9",
                              parent_task_id=None, demo_round_id="D1")
    with pytest.raises(PermissionError):
        entry.start(stranger, CrossStartInput(request_id=uuid4(), goal="减少不用的扣费"))


# --------------------------------------------------------------- goal routing


def test_ambiguous_goal_is_clarified_and_unsupported_goals_are_honest(tmp_path):
    harness, entry, _, _ = composition(tmp_path)
    unclear = entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(),
                                                             goal="帮我安排一下"))
    assert unclear.status is TaskStatus.WAITING_INPUT
    assert "请选择" in unclear.message

    # Each goal is its own task; a second, different goal on the same task is a
    # conflict (checked in the envelope test below), so run the birthday goal
    # on its own parent task.
    birthday_holder = TrustedContext(user_id="U1", session_id="S1", task_id="B_PARENT",
                                      run_id="PR9", parent_task_id=None, demo_round_id="D1")
    harness.application.create_task("B_PARENT", "U1", "S1", "D1", "PR9", "running", {})
    birthday_entry = CrossEntry(
        harness, harness.memory.checkpointer(MemoryContext("U1", "S1", "D1"), "B_PARENT"),
        None, lambda: NOW)
    birthday = birthday_entry.start(birthday_holder, CrossStartInput(
        request_id=uuid4(), goal="给妈妈过个生日"))
    # Without the platform birthday seam (ticket 09) the flow fails honestly
    # instead of improvising a purchase.
    assert birthday.status is TaskStatus.FAILED
    assert "执行接缝尚未装配" in birthday.message

    # A clarified goal builds the real plan; the clarified choice, not the
    # ambiguous first guess, decides what runs.
    other = composition(tmp_path / "other")
    menu = other[1].start(parent_trusted(), CrossStartInput(request_id=uuid4(),
                                                             goal="帮我省钱过生日"))
    assert menu.status is TaskStatus.WAITING_INPUT  # two goals in one text
    picked = other[1].resume(parent_trusted(),
                             {"selected_option_id": option_id(menu, "减少不用的开销")})
    assert picked.status is TaskStatus.WAITING_INPUT
    steps = {step.step_id: step for step in picked.data.steps}
    assert steps["subscriptions"].status is TaskStatus.SUCCEEDED


def test_envelope_start_and_request_conflict(tmp_path):
    _, entry, _, _ = composition(tmp_path)
    request_id = uuid4()
    menu = entry.start(parent_trusted(), StartTransferInput(
        request_id=request_id, intent_text="减少不用的开销"))
    assert menu.status is TaskStatus.WAITING_INPUT
    same = entry.start(parent_trusted(), StartTransferInput(
        request_id=request_id, intent_text="减少不用的开销"))
    assert same.status is TaskStatus.WAITING_INPUT  # idempotent replay
    with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
        entry.start(parent_trusted(), StartTransferInput(
            request_id=request_id, intent_text="换一个目标"))


def test_scenario_and_month_helpers():
    assert infer_scenario("最近钱花得快，帮我处理不用的扣费") is CrossScenario.EXPENSE_REDUCTION
    assert infer_scenario("给妈妈过生日") is CrossScenario.BIRTHDAY
    assert infer_scenario("帮我省钱过生日") is None  # two goals, one clarification
    assert infer_scenario("帮我安排一下") is None
    start, end = month_range(NOW, 1)
    assert (start.month, end.month) == (9, 10)


# ------------------------------------- real runtime composition (tier two)


def test_real_runtime_child_cancel_through_the_real_gate_and_bank(tmp_path):
    """One end-to-end cancellation: real registry/dispatch, gate, bank, receipt.

    Also covers the G1 seam for real: the cross parent dispatches typed
    subscription inputs through dispatch_child to the real subscription entry.
    The bills child cannot run here (the real bills entry still rejects its
    declared typed input — registered gap), so the flow proves the rest of the
    path with the bills step scripted to fail honestly at the platform seam.
    """
    from app.agent_platform.own_bank_queries import register_own_bank_queries
    from app.agent_platform.subscription_runtime import register_subscription
    from app.agent_platform.test_transfer_runtime import runtime as build_runtime
    from app.modules.bills.manifest import MANIFEST as REAL_BILLS_MANIFEST
    from app.services.mock_bank.core import MockBankService
    from app.storage.mock_bank.repository import MockBankStore

    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"),
                           demo_secret=b"demo-secret" * 4)
    bank.seed_flow_history()
    app = build_runtime(tmp_path / "app.sqlite", bank)
    register_subscription(app, clock=bank.clock)
    register_own_bank_queries(app)
    # The real bills entry cannot accept its typed input yet; a failing
    # contract-shaped stand-in keeps the rest of the composition real.
    app.harness.registry.register_module(REAL_BILLS_MANIFEST,
        lambda trusted, saver, trace: ScriptedBills("fail"))
    register_cross(app.harness, bank.clock)
    now = datetime.now(timezone.utc)
    app.application.create_session("S1", "U1", "D1", now.isoformat(),
                                   (now + timedelta(days=1)).isoformat())
    app.application.create_task("PARENT", "U1", "S1", "D1", "PR1", "running", {})
    holder = parent_trusted()
    context = MemoryContext("U1", "S1", "D1")
    entry = CrossEntry(app.harness, app.memory.checkpointer(context, "PARENT"), None,
                       bank.clock)

    menu = entry.start(holder, CrossStartInput(request_id=uuid4(),
                                               goal="最近钱花得快，帮我处理不用的扣费"))
    assert menu.status is TaskStatus.WAITING_INPUT
    assert "账单对比暂时不可用" in menu.message

    from app.contracts.security import ConfirmationAnswer

    first = entry.resume(holder, {"selected_option_id": option_id(menu, "优酷")})
    assert first.status is TaskStatus.RUNNING
    child_id = first.data.interaction_task_id
    child = app.application.get_task("U1", "D1", child_id)
    child_trusted = TrustedContext(user_id="U1", session_id="S1", task_id=child_id,
                                   run_id=child.run_id, parent_task_id="PARENT",
                                   demo_round_id="D1")
    pending = app.harness.resume(child_trusted, {})
    assert pending.status is TaskStatus.WAITING_APPROVAL
    assert pending.interaction.kind == "confirmation"
    operation_id, revision = None, None
    from app.storage.database import connect as db_connect
    connection = db_connect(app.application.path)
    try:
        row = connection.execute(
            "SELECT operation_id, action_revision FROM agent_transfer_confirmations "
            "WHERE task_id = ?", (child_id,)).fetchone()
        assert row is not None
        operation_id, revision = UUID(row["operation_id"]), row["action_revision"]
    finally:
        connection.close()
    security = app._context(child_trusted, operation_id, revision)
    record = app.confirmations.get(security, security.confirmation_id)
    app.answer_confirmation(child_trusted, ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version, choice="approve"))
    verification = app.harness.resume(child_trusted, {"choice": "approve"})
    assert verification.status is TaskStatus.WAITING_APPROVAL
    assert verification.interaction.kind == "verification"
    code = app.gateway.get_demo_code_for_api(child_trusted, verification.interaction.record_ref)
    verified = app.gateway.verify_code(child_trusted, verification.interaction.record_ref,
                                       uuid4(), code)
    app.bind_verification(child_trusted, verified.verification_id)
    done = app.harness.resume(child_trusted, {"choice": "resume"})
    assert done.status is TaskStatus.SUCCEEDED
    assert done.data.selected_item.status == "cancelled"

    held = entry.resume(holder, {})
    assert held.status is TaskStatus.RUNNING or held.status is TaskStatus.WAITING_INPUT
    receipt = entry.resume(holder, {"cancel": True})
    assert receipt.status is TaskStatus.PARTIALLY_SUCCEEDED
    assert "已退订 优酷 VIP 连续包月" in receipt.message
    assert "从下期起每月合计少扣 25.00元" in receipt.message
    app.close()
