"""Ticket v05-cross-business/02: pension arrangement and retention accounting.

Tier one over the real platform seam: typed bills-details and payee children are
contract-shaped stand-ins (the real bills entry does not accept its declared
typed input yet — registered gap); subscriptions, accounts and the dispatch /
resume / D1 storage seams are real. Numbers follow XL-P01..P06.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.contracts.common import TaskStatus
from app.contracts.cross import CrossScenario, CrossStartInput
from app.contracts.platform import StartTransferInput, TrustedContext
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult
from app.memory.adapter import MemoryAdapter, MemoryContext
from app.modules.cross.entry import CrossEntry, register_cross
from app.modules.subscription.entry import register_subscription

from app.agent_platform.harness import AgentHarness
from app.agent_platform.registry import CapabilityRegistry
from app.agent_platform.own_bank_queries import manifest as accounts_manifest
from app.modules.bills.manifest import MANIFEST as BILLS_MANIFEST
from app.modules.transfer.manifest import MANIFEST as TRANSFER_MANIFEST

from app.modules.cross.test_cross_expense import (
    NOW, FakeSubscriptionBank, PlannerStub, ScriptedPorts, parent_trusted,
)


class ScriptedBillsDetails:
    def __init__(self, income_fen):
        self.income_fen = income_fen

    def start(self, trusted, request, *, thread_id=None):
        if isinstance(request, StartTransferInput):
            return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
                status=TaskStatus.SUCCEEDED,
                data={"accounts": [{"account_id": "A1", "account_masked": "尾号 0001",
                                     "display_name": "主账户"}]},
                message="已查到本人账户。", interaction=None, error=None,
                allowed_actions=[], recovery_required=False, recovery_reason=None)
        mode = getattr(request, "mode", "summary")
        if mode == "details":
            data = {"transactions": [
                {"transaction_id": "in_1", "amount_fen": self.income_fen,
                 "direction": "transfer_in", "occurred_at": NOW.isoformat()},
            ]}
            message = "已读取本月流水。"
        else:
            data = {"consumption_net_fen": 0, "comparison": {"delta_fen": 0},
                    "categories": []}
            message = "已对比。"
        return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
            status=TaskStatus.SUCCEEDED, data=data, message=message,
            interaction=None, error=None, allowed_actions=[],
            recovery_required=False, recovery_reason=None)

    def resume(self, trusted, response, *, thread_id=None):
        raise AssertionError("read children never wait")

    def recover_session(self, trusted, *, source_session_id, thread_id=None):
        raise AssertionError("not used here")

    def checkpoint_context(self, trusted, *, thread_id=None):
        return None


class ScriptedTransfer:
    """transfer.start_transfer child with scripted outcomes (confirm -> done)."""

    def __init__(self, script):
        # A shared list makes one queue span every child of the composition.
        self.script = script if isinstance(script, list) else list(script)

    def start(self, trusted, request, *, thread_id=None):
        # A spend always waits for its own confirmation before any outcome.
        return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
            status=TaskStatus.WAITING_APPROVAL, data=None, message="请确认转账。",
            interaction=InteractionRequest(interaction_id=str(uuid4()),
                kind="confirmation", prompt="确认转账", required_fields=[],
                options=[InteractionOption(id="approve", label="确认"),
                         InteractionOption(id="cancel", label="取消")],
                record_ref=str(uuid4())),
            error=None, allowed_actions=["confirm", "cancel"],
            recovery_required=False, recovery_reason=None)

    def resume(self, trusted, response, *, thread_id=None):
        if response.get("cancel") is True or response.get("choice") == "cancel":
            return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
                status=TaskStatus.CANCELLED, data=None, message="已取消转账。",
                interaction=None, error=None, allowed_actions=[],
                recovery_required=False, recovery_reason=None)
        outcome = self.script.pop(0)
        result_status = {"success": TaskStatus.SUCCEEDED,
                         "unknown": TaskStatus.NEEDS_ATTENTION,
                         "failed": TaskStatus.FAILED}[outcome]
        message = {"success": "转账成功。", "unknown": "转账结果未知。",
                   "failed": "转账失败。"}[outcome]
        return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
            status=result_status, data=None, message=message, interaction=None,
            error=None, allowed_actions=[], recovery_required=False,
            recovery_reason=None)

    def recover_session(self, trusted, *, source_session_id, thread_id=None):
        raise AssertionError("not used here")

    def checkpoint_context(self, trusted, *, thread_id=None):
        return None


PAYEES_DATA = {"payees": [
    {"payee_id": "P_MOM", "name_masked": "妈妈", "account_masked": "****8888",
     "remark": None, "bank_name": "模拟银行"},
    {"payee_id": "P_SON", "name_masked": "儿子", "account_masked": "****6666",
     "remark": None, "bank_name": "模拟银行"},
]}


def pension_composition(tmp_path, *, income_fen=500000, transfers=("success", "success"),
                        mandates=None):
    transfer_queue = list(transfers)
    application = __import__("app.storage.application", fromlist=["ApplicationStore"]).ApplicationStore(
        tmp_path / "app.sqlite")
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    harness = AgentHarness(application, memory,
                           __import__("app.audit.journal", fromlist=["AuditJournal"]).AuditJournal(
                               tmp_path / "app.sqlite"),
                           CapabilityRegistry(), PlannerStub(),
                           authorize_capability=lambda _t, _d: True)
    bank = FakeSubscriptionBank(mandates=mandates)
    gate_states: dict = {}
    register_subscription(harness.registry, lambda trusted, trace: ScriptedPorts(bank, gate_states),
                          lambda: NOW)
    harness.registry.register_module(
        BILLS_MANIFEST, lambda trusted, saver, trace: ScriptedBillsDetails(income_fen))
    stubs = accounts_manifest("list_accounts")
    harness.registry.register_module(stubs, lambda trusted, saver, trace: ScriptedBillsDetails(income_fen))
    payees = accounts_manifest("list_payees")

    class PayeesStub(ScriptedBillsDetails):
        def start(self, trusted, request, *, thread_id=None):
            return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
                status=TaskStatus.SUCCEEDED, data=PAYEES_DATA,
                message="已查到收款人。", interaction=None, error=None,
                allowed_actions=[], recovery_required=False, recovery_reason=None)

    harness.registry.register_module(payees, lambda trusted, saver, trace: PayeesStub(0))
    harness.registry.register_transfer(TRANSFER_MANIFEST,
                                       lambda trusted, saver, trace: ScriptedTransfer(transfer_queue))
    register_cross(harness, lambda: NOW)
    real_now = datetime.now(timezone.utc)
    application.create_session("S1", "U1", "D1", real_now.isoformat(),
                               (real_now + timedelta(days=1)).isoformat())
    application.create_task("PARENT", "U1", "S1", "D1", "PR1", "running", {})
    entry = CrossEntry(harness, memory.checkpointer(MemoryContext("U1", "S1", "D1"), "PARENT"),
                       None, lambda: NOW)
    return harness, entry, bank, gate_states


def option_id(result, needle):
    matches = [item for item in result.interaction.options if needle in item.label]
    assert len(matches) == 1, [item.label for item in result.interaction.options]
    return matches[0].id


def run_to_adoption(entry, *, basis_needle="本月实际入账", reserve_text="1500元",
                    debits_needle="算进留存", amounts=("2500元", "1000元")):
    started = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="帮我安排本月养老金"))
    assert started.status is TaskStatus.WAITING_INPUT
    skip_cancel = entry.resume(parent_trusted(),
                               {"selected_option_id": option_id(started, "直接安排资金")})
    basis = entry.resume(parent_trusted(),
                         {"selected_option_id": option_id(skip_cancel, basis_needle)})
    reserve = entry.resume(parent_trusted(), {"text": reserve_text})
    assert basis.status is TaskStatus.WAITING_INPUT and reserve.status is TaskStatus.WAITING_INPUT
    after_debits = entry.resume(parent_trusted(),
                                {"selected_option_id": option_id(reserve, debits_needle)})
    current = after_debits
    for payee, amount in zip(("妈妈", "儿子"), amounts):
        pick = entry.resume(parent_trusted(),
                            {"selected_option_id": option_id(current, payee)})
        assert pick.status is TaskStatus.WAITING_INPUT
        current = entry.resume(parent_trusted(), {"text": amount})
        assert current.status is TaskStatus.WAITING_INPUT
    ready = entry.resume(parent_trusted(),
                         {"selected_option_id": option_id(current, "去向已选好")})
    return entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(ready, "采用并开始办理")})


# ------------------------------------------------------------------- XL-P01


def test_p01_income_basis_reserve_and_two_transfers(tmp_path):
    harness, entry, bank, _ = pension_composition(tmp_path)
    adopting = run_to_adoption(entry)
    assert adopting.status is TaskStatus.RUNNING  # first transfer waits on its child
    steps = {step.step_id: step for step in adopting.data.steps}
    first = steps["transfer:1"]
    assert first.amount_fen == 250000
    # The D1 arrangement is live for this payer while transfers run.
    active = harness.application.get_active_arrangement("U1", "D1", "A1")
    assert active is not None and active.record.source_task_id == "PARENT"
    assert active.record.funds_basis == "selected_income"
    assert active.record.income_transaction_ids == ["in_1"]
    assert active.record.base_fen == 500000 and active.record.living_reserve_fen == 150000

    child_id = adopting.data.interaction_task_id
    confirmed = harness.resume_child(parent_trusted(), child_id, {"choice": "approve"},
                                     plan_revision=adopting.data.plan_revision)
    assert confirmed.status is TaskStatus.SUCCEEDED
    second = entry.resume(parent_trusted(), {})
    assert second.status is TaskStatus.RUNNING
    second_id = second.data.interaction_task_id
    done = harness.resume_child(parent_trusted(), second_id, {"choice": "approve"},
                                plan_revision=second.data.plan_revision)
    assert done.status is TaskStatus.SUCCEEDED

    receipt = entry.resume(parent_trusted(), {})
    assert receipt.status is TaskStatus.SUCCEEDED
    assert "已转给 妈妈 2500.00 元。" in receipt.message
    assert "已转给 儿子 1000.00 元。" in receipt.message
    assert "资金范围 5000.00 元" in receipt.message
    assert "留存 1500.00 元" in receipt.message
    assert "已转出 3500.00 元" in receipt.message
    assert "未转出留在账户 0.00 元" in receipt.message
    assert "资金安排已解除" in receipt.message
    assert harness.application.get_active_arrangement("U1", "D1", "A1") is None


# ------------------------------------------------------------------- XL-P02


def test_p02_claimed_amount_is_corrected_to_bank_facts(tmp_path):
    _, entry, _, _ = pension_composition(tmp_path, income_fen=480000)
    started = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="帮我安排本月养老金，按5000元安排"))
    assert started.status is TaskStatus.WAITING_INPUT
    skip = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(started, "直接安排资金")})
    corrected = entry.resume(parent_trusted(), {"text": "5000元"})
    assert corrected.status is TaskStatus.WAITING_INPUT
    assert "与银行记录不一致" in corrected.message
    assert "4800.00" in corrected.message
    picked = entry.resume(parent_trusted(),
                          {"selected_option_id": option_id(corrected, "本月实际入账")})
    assert picked.status is TaskStatus.WAITING_INPUT  # reserve ask continues on 4800


# ------------------------------------------------------------------- XL-P03


def test_p03_known_debits_calibration_changes_protection(tmp_path):
    _, entry, _, _ = pension_composition(tmp_path)
    started = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="帮我安排本月养老金"))
    skip = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(started, "直接安排资金")})
    basis = entry.resume(parent_trusted(),
                         {"selected_option_id": option_id(skip, "本月实际入账")})
    reserve = entry.resume(parent_trusted(), {"text": "1500元"})
    assert "未来 30 天已知代扣合计 64.00 元" in reserve.message
    included = entry.resume(parent_trusted(),
                            {"selected_option_id": option_id(reserve, "算进留存")})
    # 5000 - 1500 reserve (debits inside): the destination ask shows the room.
    assert "还可安排 3500.00 元" in included.message

    other = pension_composition(tmp_path / "b")
    started = other[1].start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="帮我安排本月养老金"))
    skip = other[1].resume(parent_trusted(),
                           {"selected_option_id": option_id(started, "直接安排资金")})
    basis = other[1].resume(parent_trusted(),
                            {"selected_option_id": option_id(skip, "本月实际入账")})
    reserve = other[1].resume(parent_trusted(), {"text": "1500元"})
    excluded = other[1].resume(parent_trusted(),
                               {"selected_option_id": option_id(reserve, "另加保护")})
    # 5000 - 1500 reserve - 64 protected debits
    assert "还可安排 3436.00 元" in excluded.message


# ------------------------------------------------------------------- XL-P05


def test_p05_cancelling_first_never_inflates_the_funds_scope(tmp_path):
    harness, entry, bank, gate_states = pension_composition(tmp_path)
    started = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="帮我安排本月养老金"))
    look = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(started, "先看看可退订")})
    picked = entry.resume(parent_trusted(),
                          {"selected_option_id": option_id(look, "优酷")})
    child = picked.data.interaction_task_id
    gate_states[child] = str(uuid4())
    harness.resume_child(parent_trusted(), child, {"choice": "approve"},
                         plan_revision=picked.data.plan_revision)
    done = entry.resume(parent_trusted(), {})
    assert done.status is TaskStatus.WAITING_INPUT  # back on the pick menu
    back = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(done, "退订到这里")})
    # Income facts are unchanged by the cancel: still 5000, not 5000+25.
    options = [item.label for item in back.interaction.options]
    assert any("本月实际入账合计 5000.00 元" in label for label in options)
    assert not any("5025.00" in label or "5125.00" in label for label in options)


# ------------------------------------------------------------------- XL-P06


def test_p06_unknown_second_transfer_keeps_the_arrangement_open(tmp_path):
    harness, entry, _, _ = pension_composition(tmp_path,
                                               transfers=("success", "unknown"))
    adopting = run_to_adoption(entry)
    first = harness.resume_child(parent_trusted(), adopting.data.interaction_task_id,
                                 {"choice": "approve"},
                                 plan_revision=adopting.data.plan_revision)
    assert first.status is TaskStatus.SUCCEEDED
    second = entry.resume(parent_trusted(), {})
    second_result = harness.resume_child(parent_trusted(), second.data.interaction_task_id,
                                         {"choice": "approve"},
                                         plan_revision=second.data.plan_revision)
    assert second_result.status is TaskStatus.NEEDS_ATTENTION

    held = entry.resume(parent_trusted(), {})
    assert held.status is TaskStatus.RUNNING
    assert "结果未知" in held.message and "核实" in held.message
    assert entry.resume(parent_trusted(), {}).message == held.message  # no retry
    stopped = entry.resume(parent_trusted(), {"cancel": True})
    assert stopped.status is TaskStatus.RUNNING  # D2: unsettled stays open
    assert "已停止新增办理，资金仍待核实" in stopped.message
    assert "资金安排不解除" in stopped.message
    assert harness.application.get_active_arrangement("U1", "D1", "A1") is not None


def test_p06_partial_success_after_stop_closes_the_arrangement(tmp_path):
    harness, entry, _, _ = pension_composition(tmp_path, transfers=("success", "waiting"))
    adopting = run_to_adoption(entry)
    harness.resume_child(parent_trusted(), adopting.data.interaction_task_id,
                         {"choice": "approve"}, plan_revision=adopting.data.plan_revision)
    stopped = entry.resume(parent_trusted(), {"cancel": True})
    assert stopped.status is TaskStatus.PARTIALLY_SUCCEEDED
    assert stopped.message.startswith("部分完成，后续已停止")
    assert "已转给 妈妈 2500.00 元" in stopped.message
    assert "未办完的转账都没有提交" in stopped.message or "未办理的转账都没有提交" in stopped.message
    assert harness.application.get_active_arrangement("U1", "D1", "A1") is None


# ------------------------------------------------------------------- X03 / D1


def test_x03_conflicting_arrangement_is_refused_with_options(tmp_path):
    from app.contracts.cross import AdoptedArrangement
    from app.modules.cross.test_cross_expense import composition as expense_composition

    harness, entry, _, _ = pension_composition(tmp_path)
    started = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="帮我安排本月养老金"))
    skip = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(started, "直接安排资金")})
    basis = entry.resume(parent_trusted(),
                         {"selected_option_id": option_id(skip, "本月实际入账")})
    reserve = entry.resume(parent_trusted(), {"text": "1500元"})
    after_debits = entry.resume(parent_trusted(),
                                {"selected_option_id": option_id(reserve, "算进留存")})
    pick_mom = entry.resume(parent_trusted(),
                            {"selected_option_id": option_id(after_debits, "妈妈")})
    after_amount = entry.resume(parent_trusted(), {"text": "2500元"})
    # Another task already holds the payer account's arrangement.
    harness.application.create_task("OTHER", "U1", "S1", "D1", "R2", "running", {})
    other = AdoptedArrangement.model_validate({
        "arrangement_id": "arr_OTHER", "user_id": "U1", "demo_round_id": "D1",
        "source_task_id": "OTHER", "plan_revision": 1, "payer_account_id": "A1",
        "funds_basis": "available_balance", "income_transaction_ids": [],
        "base_fen": 1000000, "living_reserve_fen": 0,
        "reserve_includes_known_debits": True,
        "upcoming_debit_scope": {"account_ids": ["A1"],
                                  "start_at": "2026-10-01T00:00:00+08:00",
                                  "end_at": "2026-11-01T00:00:00+08:00"},
        "known_debits_fen": 0, "adopted_at": NOW.isoformat(),
        "adoption_interaction_id": "I1", "status": "active",
    })
    harness.application.acquire_arrangement(other)
    ready = entry.resume(parent_trusted(),
                         {"selected_option_id": option_id(after_amount, "去向已选好")})
    adopting = entry.resume(parent_trusted(),
                            {"selected_option_id": option_id(ready, "采用并开始办理")})
    assert adopting.status is TaskStatus.WAITING_INPUT
    assert "已有正在办理的资金安排" in adopting.message
    stop = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(adopting, "停止本次安排")})
    assert stop.status is TaskStatus.CANCELLED


def test_reserve_over_base_and_amount_over_remaining_are_refused(tmp_path):
    _, entry, _, _ = pension_composition(tmp_path)
    started = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="帮我安排本月养老金"))
    skip = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(started, "直接安排资金")})
    basis = entry.resume(parent_trusted(),
                         {"selected_option_id": option_id(skip, "本月实际入账")})
    too_big = entry.resume(parent_trusted(), {"text": "99999元"})
    assert too_big.status is TaskStatus.WAITING_INPUT  # asked again, never auto-lowered
    reserve = entry.resume(parent_trusted(), {"text": "1500元"})
    debits = entry.resume(parent_trusted(),
                          {"selected_option_id": option_id(reserve, "算进留存")})
    pick = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(debits, "妈妈")})
    over = entry.resume(parent_trusted(), {"text": "99999元"})
    assert over.status is TaskStatus.WAITING_INPUT
    assert "还可安排 3500.00 元" in over.message
