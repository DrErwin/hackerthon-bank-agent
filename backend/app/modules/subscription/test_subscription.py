"""Scenario-05 module tests: inventory, evidence, disambiguation and the cancel flow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.contracts.bank import (
    AccountList, AccountSummary, BankError, OperationResult, QueryFailure, QueryOk, Transaction,
    TransactionList,
)
from app.contracts.common import SecurityDecisionCode, TaskStatus
from app.contracts.platform import StartTransferInput, TrustedContext
from app.contracts.subscription import SubscriptionCancelReceipt, SubscriptionMandate, SubscriptionMandateList
from app.contracts.tasks import InteractionOption, InteractionRequest
from app.modules.subscription._rules import MIN_CONSECUTIVE_MONTHS, find_suspected_series
from app.modules.subscription.entry import SubscriptionEntry, named_mandate_id, risk_observations, wants_cancel
from app.modules.subscription.ports import CancellationPlan, ExecutionOutcome, GateAnswer
from app.modules.subscription.service import SubscriptionService

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=timezone(timedelta(hours=8)))
FORBIDDEN = ("会员可用至", "还能用到", "先退订再重新订阅", "先解约再重签")


def at(y, m, d, hour=9):
    return datetime(y, m, d, hour, 0, tzinfo=timezone(timedelta(hours=8)))


def mandate(mandate_id, merchant_id, name, service, amount, status="active",
            next_day=None, last=None, cycle="monthly"):
    return SubscriptionMandate(
        mandate_id=mandate_id, account_id="A1", account_masked="****0001",
        merchant_id=merchant_id, merchant_name=name, service_name=service,
        amount_fen=amount, cycle=cycle,
        next_billing_at=None if next_day is None else at(2026, 10, next_day),
        last_billed_at=None if last is None else at(2026, last[0], last[1]),
        status=status, signed_at=at(2025, 1, 5),
        cancelled_at=None if status == "active" else at(2026, 9, 1),
        cancel_operation_id=None if status == "active" else str(uuid4()),
    )


def flow(transaction_id, merchant_id, name, amount, year, month, day, channel="快捷支付"):
    return Transaction(
        transaction_id=transaction_id, account_id="A1", occurred_at=at(year, month, day),
        amount_fen=amount, nature="consumption", category="other", direction="outflow",
        counterparty_id=merchant_id, counterparty_name=name, counterparty_account_masked=None,
        channel=channel, summary=f"{name}自动扣费", original_transaction_id=None,
        original_occurred_at=None,
    )


def seeded_rows():
    rows = []
    for index, month in enumerate((4, 5, 6, 7, 8, 9)):
        rows.append(flow(f"UY{index}", "M_UYUN", "优酷视频", 2500, 2026, month, 25))
    for index, month in enumerate((8, 9, 10)):
        rows.append(flow(f"DR{index}", "M_UDRV", "云端网盘", 3900, 2026, month, 5))
    for index, month in enumerate((5, 6, 7, 8, 9)):
        rows.append(flow(f"OA{index}", "M_OASIS", "绿洲健身", 3900, 2026, month, 28))
    return rows


class FakeBank:
    """Minimal stand-in for the mock bank's B01/B29/B08/B30 answers."""

    def __init__(self, *, rows=None, mandates=None):
        self.rows = list(rows if rows is not None else seeded_rows())
        self.mandates = list(mandates if mandates is not None else [
            mandate("sub_001", "M_UYUN", "优酷视频", "优酷 VIP 连续包月", 2500, next_day=25, last=(9, 25)),
            mandate("sub_002", "M_UDRV", "云端网盘", "超级会员连续包月", 3900, next_day=31, last=(10, 5)),
            mandate("sub_003", "M_XMAL", "喜马拉雅", "巅峰会员连续包月", 1500, status="cancelled",
                    last=(8, 15)),
        ])
        self.cancel_calls = 0

    def accounts(self, context):
        return QueryOk(kind="ok", data=AccountList(accounts=[AccountSummary(
            account_id="A1", account_type="class_i", account_masked="****0001",
            available_balance_fen=1_000_000, display_name="主账户", bank_name="模拟银行")]))

    def mandates_for(self, context, account_id=None, status=None):
        selected = [m for m in self.mandates if account_id in (None, m.account_id)
                    and (status is None or m.status == status)]
        return QueryOk(kind="ok", data=SubscriptionMandateList(mandates=selected, as_of=NOW))

    def transactions(self, context, account_id, start_at, end_at):
        selected = [row for row in self.rows if start_at <= row.occurred_at < end_at]
        return QueryOk(kind="ok", data=TransactionList(transactions=selected, as_of=NOW))

    def cancel(self, context, operation_id, mandate_id):
        self.cancel_calls += 1
        target = next((m for m in self.mandates if m.mandate_id == mandate_id), None)
        if target is None:
            return QueryFailure(kind="error", error=BankError(code="RECORD_NOT_FOUND", details={}))
        if target.status == "cancelled":
            return QueryFailure(kind="error", error=BankError(code="STATE_CONFLICT", details={}))
        stopped = target.next_billing_at
        receipt = SubscriptionCancelReceipt(
            mandate_id=target.mandate_id, account_id=target.account_id,
            account_masked=target.account_masked, merchant_id=target.merchant_id,
            merchant_name=target.merchant_name, service_name=target.service_name,
            amount_fen=target.amount_fen, cycle=target.cycle,
            previous_next_billing_at=stopped, effective_stop_at=stopped, cancelled_at=NOW,
        )
        self.mandates = [mandate(
            m.mandate_id, m.merchant_id, m.merchant_name, m.service_name, m.amount_fen,
            status="cancelled", last=None) if m.mandate_id == mandate_id else m
            for m in self.mandates]
        return OperationResult[SubscriptionCancelReceipt](
            operation_id=operation_id, operation_type="bank.cancel_subscription",
            operation_status="succeeded", recorded_at=NOW, updated_at=NOW,
            receipt=receipt, failure=None,
        )


class FakeGate:
    """Deterministic stand-in for the security gate: confirmation, then verification."""

    def __init__(self, *, blocked=False, verify_required=False, confirmation_answered=False):
        self.blocked, self.verify_required = blocked, verify_required
        self.confirmed, self.verified = confirmation_answered, False
        self.plans: list[CancellationPlan] = []
        self.operation_id = str(uuid4())

    def _interaction(self, kind):
        return InteractionRequest(
            interaction_id=str(uuid4()), kind=kind, prompt="安全步骤",
            required_fields=[],
            options=([InteractionOption(id="approve", label="确认办理"), InteractionOption(id="cancel", label="取消")]
                     if kind == "confirmation" else []),
            record_ref="conf-1" if kind == "confirmation" else "chal-1")

    def check(self, context, plan):
        self.plans.append(plan)
        if self.blocked:
            return GateAnswer(decision=SecurityDecisionCode.BLOCK, reason_code="HIGH_RISK",
                              operation_id=self.operation_id)
        if not self.confirmed:
            return GateAnswer(decision=SecurityDecisionCode.REQUIRE_CONFIRMATION,
                              interaction=self._interaction("confirmation"), operation_id=self.operation_id)
        if self.verify_required and not self.verified:
            return GateAnswer(decision=SecurityDecisionCode.REQUIRE_VERIFICATION,
                              interaction=self._interaction("verification"), operation_id=self.operation_id)
        return GateAnswer(decision=SecurityDecisionCode.ALLOW, operation_id=self.operation_id)


class Ports:
    def __init__(self, bank, gate):
        self.bank, self.gate = bank, gate

    def accounts(self, context):
        return self.bank.accounts(context)

    def mandates(self, context, account_id=None, status=None):
        return self.bank.mandates_for(context, account_id, status)

    def transactions(self, context, account_id, start_at, end_at):
        return self.bank.transactions(context, account_id, start_at, end_at)

    def check_cancel(self, context, plan):
        return self.gate.check(context, plan)

    def execute_cancel(self, context, plan):
        return ExecutionOutcome(
            executed=True, state="completed",
            result=self.bank.cancel(context, UUID(self.gate.operation_id), plan.mandate_id),
            decision=GateAnswer(decision=SecurityDecisionCode.ALLOW, operation_id=self.gate.operation_id),
            operation_id=self.gate.operation_id)


class Saved:
    def __init__(self, config, checkpoint):
        self.config, self.checkpoint = config, checkpoint


class MemorySaver:
    def __init__(self):
        self.rows: dict[str, Saved] = {}

    def get_tuple(self, config):
        return self.rows.get(str(config["configurable"]["thread_id"]))

    def put(self, config, checkpoint, metadata, versions):
        self.rows[str(config["configurable"]["thread_id"])] = Saved(config, checkpoint)
        return config


def context():
    return TrustedContext(user_id="U1", session_id="S1", task_id="T1", run_id="R1",
                          parent_task_id=None, demo_round_id="D1")


def service(bank=None, gate=None):
    return SubscriptionService(Ports(bank or FakeBank(), gate or FakeGate()), lambda: NOW)


def start_request(text, request_id=None):
    return StartTransferInput(request_id=request_id or uuid4(), intent_text=text)


def entry(bank=None, gate=None, saver=None):
    return SubscriptionEntry(service(bank, gate), saver or MemorySaver(), None)


# --------------------------------------------------------------------- read side

def test_inventory_ranks_mandates_evidence_and_clues():
    result = service().inventory(context())
    assert [item.subscription_id for item in result.items] == ["sub_001", "sub_002", "sus_oasis_01", "sub_003"]
    assert [item.subscription_id for item in result.upcoming_renewals] == ["sub_001", "sub_002"]
    assert result.upcoming_total_fen == 2500 + 3900
    assert result.active_count == 2
    assert result.suspected_scan_status == "evaluated" and result.suspected_scan_reason is None
    youku = result.items[0]
    assert (youku.billed_count, youku.billed_total_fen, youku.days_until_renewal) == (6, 15000, 6)
    assert youku.can_cancel_in_bank is True
    clue = result.items[2]
    assert clue.source_type == "suspected_ledger" and clue.mandate_id is None
    assert clue.status == "suspected" and clue.can_cancel_in_bank is False
    assert clue.channel == "快捷支付" and clue.next_billing_at is None and clue.is_upcoming_renewal is False
    assert "微信支付" in clue.external_cancel_guide
    closed = result.items[3]
    assert closed.status == "cancelled" and closed.is_upcoming_renewal is False


def test_scan_keeps_the_cancelled_merchant_out_of_the_clue_section():
    """A historically cancelled mandate is not a "no mandate" clue (PRD T01)."""
    rows = seeded_rows() + [flow(f"XM{index}", "M_XMAL", "喜马拉雅", 1500, 2026, month, 15)
                            for index, month in enumerate((5, 6, 7, 8))]
    result = service(FakeBank(rows=rows)).inventory(context())
    assert "sus_xmal_01" not in {item.subscription_id for item in result.items}


def test_inventory_message_carries_the_elder_friendly_reminder():
    result = service().inventory(context())
    message = service().inventory_message(result)
    assert "7 天内会扣款" in message
    assert "一共 64.00 元" in message
    assert "优酷视频" in message and "已经扣了 6 次共 150.00 元" in message
    assert "需要帮您退订其中某一项吗" in message
    assert not any(phrase in message for phrase in FORBIDDEN)


def test_insufficient_flow_coverage_is_reported_not_denied():
    rows = [flow("UY0", "M_UYUN", "优酷视频", 2500, 2026, 10, 1)]
    result = service(FakeBank(rows=rows)).inventory(context())
    assert result.suspected_scan_status == "insufficient_data"
    assert "不足 3 个月" in (result.suspected_scan_reason or "")
    message = service(FakeBank(rows=rows)).inventory_message(result)
    assert "未发现" not in message


def test_insufficient_coverage_without_mandates_never_says_nothing_was_found():
    bank = FakeBank(rows=[flow("UY0", "M_UYUN", "优酷视频", 2500, 2026, 10, 1)], mandates=[])
    result = entry(bank).start(context(), start_request("帮我查查有哪些自动扣费"))
    assert result.status == TaskStatus.SUCCEEDED
    assert "没有查到自动扣费" not in result.message
    assert "不足 3 个月" in result.message


def test_rule_four_needs_three_consecutive_months_and_identical_amounts():
    exact = [flow(f"E{index}", "M_ZOO", "动物园", 3900, 2026, month, 28)
             for index, month in enumerate((7, 8, 9))]
    assert len(find_suspected_series(exact, excluded_merchants=set(), account_masked={})) == 1
    drifted = exact[:2] + [flow("E9", "M_ZOO", "动物园", 4200, 2026, 9, 28)]
    assert find_suspected_series(drifted, excluded_merchants=set(), account_masked={}) == []
    missing = [exact[0], exact[2]]
    assert find_suspected_series(missing, excluded_merchants=set(), account_masked={}) == []
    assert MIN_CONSECUTIVE_MONTHS == 3


def test_rule_four_day_tolerance_is_inclusive_at_three_days():
    anchor = flow("T0", "M_TOL", "容忍度", 1000, 2026, 7, 10)
    within = [anchor,
              flow("T1", "M_TOL", "容忍度", 1000, 2026, 8, 7),     # 期望 8-10，差 -3 天
              flow("T2", "M_TOL", "容忍度", 1000, 2026, 9, 13)]    # 期望 9-10，差 +3 天
    assert len(find_suspected_series(within, excluded_merchants=set(), account_masked={})) == 1
    beyond = [anchor,
              flow("T3", "M_TOL", "容忍度", 1000, 2026, 8, 10),
              flow("T4", "M_TOL", "容忍度", 1000, 2026, 9, 14)]    # 期望 9-10，差 +4 天
    assert find_suspected_series(beyond, excluded_merchants=set(), account_masked={}) == []


def test_rule_four_keeps_the_first_anchor_on_a_month_end():
    month_end = [flow("M0", "M_END", "月末商户", 1000, 2026, 1, 31),
                 flow("M1", "M_END", "月末商户", 1000, 2026, 2, 28),
                 flow("M2", "M_END", "月末商户", 1000, 2026, 3, 31)]
    found = find_suspected_series(month_end, excluded_merchants=set(), account_masked={})
    assert len(found) == 1 and found[0].next_at.month == 4


# ------------------------------------------------------------------- cancel side

def test_list_mode_returns_the_list_view():
    result = entry().start(context(), start_request("帮我查查有哪些自动扣费"))
    assert result.status == TaskStatus.SUCCEEDED
    assert result.data.action == "list" and result.data.list_result.upcoming_total_fen == 6400


def test_cancel_entry_full_flow_confirmation_then_verification():
    bank, gate = FakeBank(), FakeGate(verify_required=True)
    task = entry(bank, gate)
    first = task.start(context(), start_request("把优酷视频的自动扣费退了"))
    assert first.status == TaskStatus.WAITING_APPROVAL
    assert first.interaction.kind == "confirmation" and first.interaction.record_ref == "conf-1"
    assert "从下一期起不再自动扣费" in first.message
    assert "2026-10-25" in first.message and "之前已经扣掉的钱不退" in first.message
    assert bank.cancel_calls == 0
    plan = gate.plans[-1]
    assert [field.name for field in plan.fields] == [
        "merchant", "account", "amount", "billed", "next_billing", "notice"]
    assert plan.fields[3].value_text == "已经扣了 6 次，共 150.00 元"
    assert plan.fields[5].value_text.startswith("从下一期（2026-10-25）起不再自动扣费")
    gate.confirmed = True
    second = task.resume(context(), {"choice": "approve"})
    assert second.status == TaskStatus.WAITING_APPROVAL and second.interaction.kind == "verification"
    assert "验证码" in second.message
    gate.verified = True
    third = task.resume(context(), {"choice": "resume"})
    assert third.status == TaskStatus.SUCCEEDED
    assert third.data.action == "cancel" and third.data.selected_item.status == "cancelled"
    receipt = third.data.operation.receipt
    assert receipt.mandate_id == "sub_001" and receipt.effective_stop_at.date().isoformat() == "2026-10-25"
    assert "已经退了" in third.message and "2026-10-25" in third.message
    assert "之前已经扣掉的钱不退" in third.message
    # The agreement is stopped: the view must not keep promising a next debit.
    assert third.data.selected_item.next_billing_at is None
    assert third.data.selected_item.is_upcoming_renewal is False
    assert third.data.selected_item.can_cancel_in_bank is False
    assert bank.cancel_calls == 1
    assert not any(phrase in third.message for phrase in FORBIDDEN)


def test_batch_cancel_is_refused_and_offers_one_choice():
    task = entry()
    result = task.start(context(), start_request("把我的所有自动扣费全部关掉"))
    assert result.status == TaskStatus.WAITING_INPUT
    assert "每次只能退订一项" in result.message
    assert [option.id for option in result.interaction.options] == ["sub_001", "sub_002"]
    assert result.interaction.required_fields == ["merchant_hint"]
    chosen = task.resume(context(), {"selected_option_id": "sub_002"})
    assert chosen.status == TaskStatus.WAITING_APPROVAL and chosen.interaction.kind == "confirmation"


def test_batch_words_still_refuse_when_one_merchant_is_named():
    result = entry().start(context(), start_request("全部退掉优酷视频的自动扣费"))
    assert result.status == TaskStatus.WAITING_INPUT
    assert [option.id for option in result.interaction.options] == ["sub_001", "sub_002"]


def test_spec_batch_phrasing_reaches_the_disambiguation_step():
    """SF05's own wording must not fall through to the inventory path."""

    result = entry().start(context(), start_request("把所有自动扣费都关了"))
    assert result.status == TaskStatus.WAITING_INPUT
    assert "每次只能退订一项" in result.message
    assert [option.id for option in result.interaction.options] == ["sub_001", "sub_002"]


def test_short_merchant_prefix_still_identifies_the_target():
    result = entry().start(context(), start_request("把优酷的会员退了"))
    assert result.status == TaskStatus.WAITING_APPROVAL
    assert result.interaction.kind == "confirmation"


def test_text_reply_disambiguates_and_an_unknown_merchant_falls_back_to_the_menu():
    task = entry()
    assert task.start(context(), start_request("把那个会员退了")).status == TaskStatus.WAITING_INPUT
    chosen = task.resume(context(), {"text": "云端网盘"})
    assert chosen.status == TaskStatus.WAITING_APPROVAL
    unknown = entry().start(context(), start_request("把某某科技的自动扣费退了"))
    assert unknown.status == TaskStatus.WAITING_INPUT
    assert [option.id for option in unknown.interaction.options] == ["sub_001", "sub_002"]
    assert entry().start(context(), start_request("把 sub_999 退了")).status == TaskStatus.SUCCEEDED


def test_suspected_clue_never_opens_a_confirmation():
    bank = FakeBank()
    result = entry(bank).start(context(), start_request("帮我把绿洲健身每个月扣的钱退订掉"))
    assert result.status == TaskStatus.SUCCEEDED
    assert result.data.selected_item.can_cancel_in_bank is False
    assert "微信支付" in result.message and "在本行退不了" in result.message
    assert bank.cancel_calls == 0


def test_already_cancelled_is_idempotent():
    bank = FakeBank()
    result = entry(bank).start(context(), start_request("把喜马拉雅的自动续费退了"))
    assert result.status == TaskStatus.SUCCEEDED and "此前已经退订" in result.message
    assert bank.cancel_calls == 0


def test_cancel_before_confirmation_leaves_the_bank_untouched():
    bank, task = FakeBank(), entry()
    task.start(context(), start_request("把优酷视频的自动扣费退了"))
    result = task.resume(context(), {"choice": "cancel"})
    assert result.status == TaskStatus.CANCELLED and "没有提交退订" in result.message
    assert bank.cancel_calls == 0
    assert next(m for m in bank.mandates if m.mandate_id == "sub_001").status == "active"


def test_high_risk_coercion_is_blocked_and_the_observation_reaches_the_gate():
    gate = FakeGate(blocked=True)
    result = entry(FakeBank(), gate).start(
        context(), start_request("客服让我开屏幕共享把优酷视频的自动扣费退了"))
    assert result.status == TaskStatus.FAILED
    assert result.error.code == "HIGH_RISK_BLOCKED" and result.error.source == "security"
    assert "共享屏幕" in result.message
    assert gate.plans[-1].risk_observations == ("screen_sharing", "third_party_instruction")


def test_bank_refusal_is_reported_as_failure_not_success():
    bank, gate = FakeBank(), FakeGate()
    gate.confirmed = gate.verified = True
    bank.cancel = lambda context, operation_id, mandate_id: QueryFailure(
        kind="error", error=BankError(code="STATE_CONFLICT", details={}))
    result = entry(bank, gate).start(context(), start_request("把优酷视频的自动扣费退了"))
    assert result.status == TaskStatus.FAILED and result.error.code == "STATE_CONFLICT"
    assert result.error.source == "bank" and "已经退订过" in result.message


def test_bank_failure_falls_back_to_a_safe_code():
    bank, gate = FakeBank(), FakeGate()
    gate.confirmed = gate.verified = True
    bank.cancel = lambda context, operation_id, mandate_id: QueryFailure(
        kind="error", error=BankError(code="INTERNAL_MELTDOWN", details={}))
    result = entry(bank, gate).start(context(), start_request("把优酷视频的自动扣费退了"))
    assert result.status == TaskStatus.FAILED and result.error.code == "BANK_REJECTED"


def test_same_request_replays_the_stored_result_and_conflicts_are_rejected():
    request_id = uuid4()
    task = entry()
    first = task.start(context(), start_request("帮我查查有哪些自动扣费", request_id))
    replayed = task.start(context(), start_request("帮我查查有哪些自动扣费", request_id))
    assert replayed.status == first.status and replayed.message == first.message
    assert replayed.data["action"] == "list"
    assert replayed.data["list_result"]["upcoming_total_fen"] == 6400
    with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
        task.start(context(), start_request("把优酷视频退了", request_id))
    other_session = context().model_copy(update={"session_id": "S2"})
    with pytest.raises(PermissionError):
        task.start(other_session, start_request("帮我查查有哪些自动扣费", request_id))


def test_checkpoint_state_never_keeps_raw_chat_text():
    saver = MemorySaver()
    task = entry(saver=saver)
    task.start(context(), start_request("把优酷视频的自动扣费退了"))
    state = saver.rows["T1"].checkpoint["channel_values"]["subscription_state"]
    assert "utterance" not in state and "intent_text" not in state
    assert state["selected"] == "sub_001" and state["waiting"] == "confirmation"
    assert len(state["intent_digest"]) == 64 and "优酷" not in state["intent_digest"]


def test_session_recovery_re_checks_the_gate():
    bank, gate, saver = FakeBank(), FakeGate(verify_required=True), MemorySaver()
    task = entry(bank, gate, saver)
    task.start(context(), start_request("把优酷视频的自动扣费退了"))
    gate.confirmed = True
    assert task.resume(context(), {"choice": "approve"}).interaction.kind == "verification"
    gate.verified = True
    # A new login session voids the session-scoped verification: the gate asks again.
    gate.verified = False
    recovered = task.recover_session(
        context().model_copy(update={"session_id": "S2"}), source_session_id="S1")
    assert recovered.status == TaskStatus.WAITING_APPROVAL
    assert recovered.interaction.kind == "verification" and bank.cancel_calls == 0
    assert saver.rows["T1"].checkpoint["channel_values"]["subscription_state"]["session_id"] == "S2"


def test_intent_helpers():
    assert wants_cancel("把优酷视频的自动扣费退了") and not wants_cancel("帮我查查有哪些自动扣费")
    assert named_mandate_id("退掉 sub_002 吧") == "sub_002" and named_mandate_id("退了优酷") is None
    assert risk_observations("客服让我把验证码告诉他") == ["credential_request", "third_party_instruction"]
    assert risk_observations("帮我退了优酷视频") == []
