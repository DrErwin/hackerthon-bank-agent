"""Scenario-05 business rules: inventory, debit evidence, disambiguation, one cancel.

Every bank fact comes from the injected ports (B29 signed mandates, B08 flows); this
module neither stores bank state nor executes anything by itself. The single write is
prepared here and executed through the platform's gate and shared executor.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal
from uuid import uuid4

from pydantic import ValidationError

from app.contracts.bank import AccountList, OperationResult, QueryFailure, QueryOk, Transaction, TransactionList
from app.contracts.common import DisplayField, SecurityDecisionCode, TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.subscription import (
    SubscriptionCancelReceipt, SubscriptionItem, SubscriptionListResult, SubscriptionMandate,
    SubscriptionMandateList, SubscriptionTaskView,
)
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleError, ModuleResult
from ._rules import coverage_months, find_suspected_series, scan_window
from .ports import CancellationPlan, ExecutionOutcome, GateAnswer, SubscriptionPorts


LOGGER = logging.getLogger(__name__)

SCAN_MONTHS = 12
MIN_SCAN_MONTHS = 3
UPCOMING_TAG_DAYS = 7

# The only promise the bank can keep: future debits stop, past money stays.
NOTICE_TEMPLATE = "从下一期（{date}）起不再自动扣费，之前已经扣掉的钱不退。"
GUIDE_TEMPLATE = (
    "「{merchant}」是疑似周期消费：账单上{channel}每月有 {amount} 元支出，连续 {count} 次。"
    "本行没有该商户的签约代扣记录，不能据此确认开通了自动续费。"
    "这笔在本行退不了；实际签约渠道尚未确认，请先向该商户核实是否签约及关闭方式。"
)
BATCH_REFUSAL = "为保障您的账户安全，每次只能退订一项自动扣费，请先选择要退订的项目。"
INSUFFICIENT_SCAN = (
    "账单记录不足 3 个月（当前只有 {months} 个月），暂时看不出有没有未签约的每月自动扣费；"
    "本行签约的项目照常显示。"
)
CYCLE_TEXT = {"monthly": "每月", "yearly": "每年"}
# The gate's own stop reasons: only HIGH_RISK is a coercion block, and a terminated
# verification has its own honest wording instead of the generic refusal.
HIGH_RISK_REASON = "HIGH_RISK"
VERIFICATION_FAILED_REASON = "VERIFICATION_FAILED"

_MESSAGES = {
    "ACCESS_DENIED": "只能查看和退订您本人的自动扣费。",
    "AUTH_REQUIRED": "请重新登录后再查看本人自动扣费。",
    "INVALID_ARGUMENT": "查询条件不完整或格式不正确，请核对后重试。",
    "INCOMPLETE_FACTS": "银行返回的签约或流水事实不完整，暂时不能给出完整清单。",
    "DEPENDENCY_UNAVAILABLE": "签约信息暂时查不到，请稍后再试；这不是「没有签约」。",
    "SECURITY_REJECTED": "本次退订没有通过安全检查，银行未收到解约请求。",
    "SUBSCRIPTION_RESULT_INVALID": "清单结果校验未通过，暂时不能提供。",
    "SUBSCRIPTION_INTERNAL_ERROR": "订阅服务暂时不可用，请稍后再试。",
    "RECORD_NOT_FOUND": "没有找到这笔签约代扣，请重新查看自动扣费清单。",
    "STATE_CONFLICT": "这一笔之前已经退订过，后续不会再自动扣费。",
    "ACCOUNT_UNAVAILABLE": "这个扣款账户状态异常，暂时不能在线退订，请拨打银行卡背面的客服电话。",
    "OPERATION_CONFLICT": "这次解约与既有操作对不上，已停止办理，请重新核对。",
    "BANK_REJECTED": "银行没有受理这次解约，请在银行 App 或拨打银行卡背面客服电话办理。",
    "CALL_TIMEOUT": "这次退订还没拿到银行的最终确认，请先不要重复操作，稍后再查询结果。",
    "HIGH_RISK_BLOCKED": "有人让您共享屏幕、索要验证码或催您马上退订时，我们不能替您办理；请先挂断，再打银行卡背面的客服电话核实。",
    "VERIFICATION_TERMINATED": "验证码连续输错，本次退订已经停止，银行没有收到解约请求；您可以重新办理。",
}
_SAFE_BANK_CODES = frozenset({"ACCESS_DENIED", "AUTH_REQUIRED", "RECORD_NOT_FOUND", "STATE_CONFLICT",
                              "ACCOUNT_UNAVAILABLE", "OPERATION_CONFLICT", "BANK_REJECTED",
                              "CALL_TIMEOUT", "DEPENDENCY_UNAVAILABLE", "INVALID_ARGUMENT"})


class SubscriptionError(ValueError):
    """Only stable codes cross the public boundary, never upstream exception text."""

    def __init__(self, code: str, *, source: str = "subscription", upstream: str | None = None):
        super().__init__(code)
        self.code, self.source, self.upstream = code, source, upstream


@dataclass(frozen=True)
class CancelResolution:
    """What the user's words point at, decided from bank facts only."""

    kind: Literal["target", "candidates", "guide", "already_cancelled", "not_found"]
    item: SubscriptionItem | None = None
    candidates: tuple[SubscriptionItem, ...] = ()
    list_result: SubscriptionListResult | None = None
    reason: str | None = None


def money(fen: int) -> str:
    return f"{fen // 100}.{fen % 100:02d}"


def day_text(at: datetime) -> str:
    return f"{at.month}月{at.day}日"


def account_label(masked: str) -> str:
    """One readable account line: the bank already prefixes ``尾号`` in B01 labels."""

    text = (masked or "").strip()
    text = text.removeprefix("尾号").strip()
    return f"尾号 {text}" if text else masked


def _options(items) -> list[InteractionOption]:
    return [
        InteractionOption(
            id=item.subscription_id,
            label=f"{item.merchant_name}（{item.service_name}） · {CYCLE_TEXT[item.cycle]} {money(item.amount_fen)} 元",
        )
        for item in items
    ]


class SubscriptionService:
    """Public handlers and the wording they are allowed to use (PRD §5.2/§5.3)."""

    def __init__(self, ports: SubscriptionPorts, clock: Callable[[], datetime]):
        self.ports, self.clock = ports, clock

    # ------------------------------------------------------------------ read side

    def _now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise SubscriptionError("INCOMPLETE_FACTS")
        return now

    def _unwrap(self, response: object, model):
        if isinstance(response, QueryFailure):
            upstream = response.error.code if response.error.code in _SAFE_BANK_CODES else "DEPENDENCY_UNAVAILABLE"
            code = upstream if upstream in _MESSAGES else "DEPENDENCY_UNAVAILABLE"
            raise SubscriptionError(code, source="bank", upstream=upstream)
        if not isinstance(response, QueryOk):
            raise SubscriptionError("INCOMPLETE_FACTS", source="bank")
        try:
            payload = response.data.model_dump(mode="python") if hasattr(response.data, "model_dump") else response.data
            return model.model_validate(payload)
        except (ValidationError, TypeError, ValueError):
            raise SubscriptionError("INCOMPLETE_FACTS", source="bank") from None

    def inventory(self, context: TrustedContext, *, reminder_days: int = 30,
                  account_ids: list[str] | None = None,
                  status_filter: str = "all") -> SubscriptionListResult:
        """SOP-1 + SOP-3: signed mandates, their debit evidence and flow-only clues."""

        now = self._now()
        accounts = self._unwrap(self.ports.accounts(context), AccountList)
        owned = {item.account_id: item for item in accounts.accounts}
        selected = list(account_ids) if account_ids else sorted(owned)
        if not set(selected) <= set(owned):
            raise SubscriptionError("ACCESS_DENIED", source="security")
        mandates = self._unwrap(self.ports.mandates(context), SubscriptionMandateList)
        start, end = scan_window(now, months=SCAN_MONTHS)
        rows: list[Transaction] = []
        for account_id in selected:
            facts = self._unwrap(self.ports.transactions(context, account_id, start, end), TransactionList)
            rows.extend(facts.transactions)
        mask = {account_id: owned[account_id].account_masked for account_id in selected}
        items = [
            self._mandate_item(mandate, rows, now, reminder_days)
            for mandate in mandates.mandates if mandate.account_id in owned
        ]
        excluded = {mandate.merchant_id for mandate in mandates.mandates}
        series = find_suspected_series(rows, excluded_merchants=excluded, account_masked=mask)
        items.extend(self._suspected_item(found) for found in series)
        if status_filter != "all":
            items = [item for item in items if
                     item.status == status_filter or (status_filter == "suspected" and item.source_type == "suspected_ledger")]
        covered = coverage_months(rows, window_end=end)
        # Ticket order: signed and active first, then flow-only clues, then already cancelled.
        def rank(item: SubscriptionItem) -> tuple:
            if item.status == "active":
                group = 0
            elif item.source_type == "suspected_ledger":
                group = 1
            else:
                group = 2
            return (group, item.next_billing_at.isoformat() if item.next_billing_at else "9999-12-31",
                    item.subscription_id)
        ordered = sorted(items, key=rank)
        upcoming = [item for item in ordered if item.is_upcoming_renewal]
        return SubscriptionListResult(
            items=ordered, upcoming_renewals=upcoming,
            active_count=len([item for item in ordered if item.status == "active"]),
            upcoming_total_fen=sum(item.amount_fen for item in upcoming), as_of=now,
            suspected_scan_status="evaluated" if covered >= MIN_SCAN_MONTHS else "insufficient_data",
            suspected_scan_reason=None if covered >= MIN_SCAN_MONTHS else INSUFFICIENT_SCAN.format(months=covered),
        )

    def _mandate_item(self, mandate: SubscriptionMandate, rows: list[Transaction], now: datetime,
                      reminder_days: int) -> SubscriptionItem:
        matched = [row for row in rows if row.counterparty_id == mandate.merchant_id]
        last = max((row.occurred_at for row in matched), default=None)
        days = (mandate.next_billing_at - now).days if mandate.next_billing_at is not None else None
        return SubscriptionItem(
            subscription_id=mandate.mandate_id, source_type="mandate", mandate_id=mandate.mandate_id,
            merchant_id=mandate.merchant_id, merchant_name=mandate.merchant_name,
            service_name=mandate.service_name, amount_fen=mandate.amount_fen, cycle=mandate.cycle,
            # The bank's own field for this agreement, so the item, the confirmation card
            # and the B30 receipt all show the same masked account.
            account_id=mandate.account_id, account_masked=mandate.account_masked,
            last_billed_at=last or mandate.last_billed_at, next_billing_at=mandate.next_billing_at,
            status=mandate.status, can_cancel_in_bank=mandate.status == "active",
            days_until_renewal=days,
            is_upcoming_renewal=mandate.status == "active" and days is not None and 0 <= days <= reminder_days,
            external_cancel_guide=None, billed_count=len(matched),
            billed_total_fen=sum(row.amount_fen for row in matched),
            channel=(matched[-1].channel or None) if matched else None,
        )

    @staticmethod
    def _suspected_item(found) -> SubscriptionItem:
        # A clue is never given a promised next charge date: it must not read as a mandate.
        return SubscriptionItem(
            subscription_id=found.subscription_id, source_type="suspected_ledger", mandate_id=None,
            merchant_id=found.merchant_key, merchant_name=found.merchant_name,
            service_name=f"{found.merchant_name}疑似周期消费（流水线索）", amount_fen=found.amount_fen,
            cycle="monthly", account_id=found.account_id, account_masked=found.account_masked,
            last_billed_at=found.last_at, next_billing_at=None, status="suspected",
            can_cancel_in_bank=False, days_until_renewal=None, is_upcoming_renewal=False,
            external_cancel_guide=GUIDE_TEMPLATE.format(
                merchant=found.merchant_name, channel=f"通过{found.channel}" if found.channel else "",
                amount=money(found.amount_fen), count=found.count),
            billed_count=found.count, billed_total_fen=found.total_fen, channel=found.channel,
        )

    def inventory_message(self, result: SubscriptionListResult, *, reminder_days: int = 30) -> str:
        actives = [item for item in result.items if item.status == "active"]
        clues = [item for item in result.items if item.source_type == "suspected_ledger"]
        closed = [item for item in result.items if item.status == "cancelled"]
        parts: list[str] = []
        if actives:
            parts.append(f"您名下现在有 {len(actives)} 笔本行签约的自动扣费：")
            for item in actives:
                text = (f"「{item.merchant_name}（{item.service_name}）」{CYCLE_TEXT[item.cycle]} "
                        f"{money(item.amount_fen)} 元")
                if item.billed_count:
                    text += f"，已经扣了 {item.billed_count} 次共 {money(item.billed_total_fen)} 元"
                if item.next_billing_at is not None:
                    text += f"，下次 {day_text(item.next_billing_at)} 扣"
                    if item.days_until_renewal is not None and item.days_until_renewal <= UPCOMING_TAG_DAYS:
                        text += "【7 天内会扣款】"
                parts.append(text)
        for item in clues:
            parts.append("另外看到 " + (item.external_cancel_guide or item.merchant_name))
        if closed:
            parts.append("已取消的本行签约（该签约不再自动扣费）：" + "、".join(
                f"「{item.merchant_name}」" for item in closed) + "。")
        if not actives and not clues:
            # Never claim "nothing found" when the flow history cannot support that claim.
            parts.append("本行没有查到生效中的自动扣费。"
                         if result.suspected_scan_status == "insufficient_data"
                         else "没有查到自动扣费。" if not closed else "现在没有生效中的自动扣费。")
        if result.upcoming_renewals:
            parts.append(
                f"往后 {reminder_days} 天里还有 {len(result.upcoming_renewals)} 笔会自动扣："
                + "、".join(f"{day_text(item.next_billing_at)}「{item.merchant_name}」{money(item.amount_fen)} 元"
                            for item in result.upcoming_renewals)
                + f"，一共 {money(result.upcoming_total_fen)} 元。这是按签约算的，实际还是以银行当天扣款为准。")
        if result.suspected_scan_status == "insufficient_data":
            parts.append(result.suspected_scan_reason or INSUFFICIENT_SCAN.format(months=0))
        if actives:
            parts.append("请问需要帮您退订其中某一项吗？")
        return "\n".join(parts)

    # ---------------------------------------------------------------- cancel side

    def resolve_cancel(self, context: TrustedContext, *, subscription_id: str | None = None,
                       utterance: str | None = None, batch_requested: bool = False,
                       reminder_days: int = 30) -> CancelResolution:
        """Match the user's words against bank facts; never default to the first item."""

        result = self.inventory(context, reminder_days=reminder_days)
        items = list(result.items)
        if subscription_id:
            matched = [item for item in items if item.subscription_id == subscription_id]
            if not matched:
                return CancelResolution("not_found", list_result=result)
            return self._classify(matched[0], result)
        if utterance and not batch_requested:
            matched = [item for item in items if self._named(item, utterance)]
            if len(matched) == 1:
                return self._classify(matched[0], result)
            actives = [item for item in matched if item.can_cancel_in_bank]
            if len(actives) == 1:
                return self._classify(actives[0], result)
            if actives:
                return CancelResolution("candidates", candidates=tuple(actives), list_result=result)
            if matched:
                # Nothing in this match can be cancelled online; explain instead of offering it.
                return (self._classify(matched[0], result) if len(matched) == 1
                        else CancelResolution("not_found", list_result=result))
        candidates = tuple(item for item in items if item.can_cancel_in_bank)
        if not candidates:
            return CancelResolution("not_found", list_result=result)
        return CancelResolution("candidates", candidates=candidates, list_result=result,
                                reason=BATCH_REFUSAL if batch_requested else None)

    @staticmethod
    def _named(item: SubscriptionItem, utterance: str) -> bool:
        """True when the user's sentence names this merchant (full name or a 2+ char prefix)."""

        for label in (item.merchant_name, item.service_name):
            if label and (label in utterance or (len(label) >= 2 and label[:2] in utterance)):
                return True
        return False

    @staticmethod
    def _classify(item: SubscriptionItem, result: SubscriptionListResult) -> CancelResolution:
        if item.source_type == "suspected_ledger":
            return CancelResolution("guide", item=item, list_result=result)
        if item.status == "cancelled":
            return CancelResolution("already_cancelled", item=item, list_result=result)
        if not item.can_cancel_in_bank:
            return CancelResolution("guide", item=item, list_result=result)
        return CancelResolution("target", item=item, list_result=result)

    def plan_for(self, item: SubscriptionItem, risk_observations: tuple[str, ...] = ()) -> CancellationPlan:
        """The six mandatory confirmation fields, frozen from bank facts (PRD §5)."""

        if item.mandate_id is None or item.next_billing_at is None:
            raise SubscriptionError("INCOMPLETE_FACTS")
        notice = NOTICE_TEMPLATE.format(date=item.next_billing_at.date().isoformat())
        billed = (f"已经扣了 {item.billed_count} 次，共 {money(item.billed_total_fen)} 元"
                  if item.billed_count else "近 12 个月没有查到扣款记录")
        fields = (
            DisplayField(name="merchant", label="退订项目",
                         value_text=f"{item.merchant_name}（{item.service_name}）"),
            DisplayField(name="account", label="扣款账户", value_text=account_label(item.account_masked)),
            DisplayField(name="amount", label="金额与周期",
                         value_text=f"{CYCLE_TEXT[item.cycle]} {money(item.amount_fen)} 元"),
            DisplayField(name="billed", label="已扣记录", value_text=billed),
            DisplayField(name="next_billing", label="原定下一期扣款日",
                         value_text=item.next_billing_at.date().isoformat()),
            DisplayField(name="notice", label="退订后果", value_text=notice),
        )
        return CancellationPlan(
            mandate_id=item.mandate_id, account_id=item.account_id,
            account_masked=item.account_masked, merchant_id=item.merchant_id,
            merchant_name=item.merchant_name, service_name=item.service_name,
            amount_fen=item.amount_fen, cycle=item.cycle, effective_stop_at=item.next_billing_at,
            risk_observations=tuple(risk_observations), fields=fields,
        )

    # ------------------------------------------------------------- gate passthroughs

    def check_cancel(self, context: TrustedContext, plan: CancellationPlan, *,
                     revision: int | None = None) -> GateAnswer:
        """Ask the security gate what this cancellation still needs (nothing is executed)."""

        return self.ports.check_cancel(context, plan, revision=revision)

    def execute_cancel(self, context: TrustedContext, plan: CancellationPlan, *,
                       revision: int | None = None) -> ExecutionOutcome:
        """Run the single write through the shared executor; the gate decides admission."""

        return self.ports.execute_cancel(context, plan, revision=revision)

    @staticmethod
    def confirmation_message(item: SubscriptionItem) -> str:
        return (
            f"请核对退订信息：「{item.merchant_name}（{item.service_name}）」"
            f"扣款账户{account_label(item.account_masked)}，"
            f"{CYCLE_TEXT[item.cycle]} {money(item.amount_fen)} 元，"
            f"原定下一期 {item.next_billing_at.date().isoformat()} 扣款。"
            "请核对后点击确认；如需身份验证，页面会提示您完成。退订成功后从下一期起不再自动扣费，"
            "之前已经扣掉的钱不退。"
        )

    @staticmethod
    def verification_message() -> str:
        return "请填写银行发给您的短信验证码；验证通过后马上办理退订，验证码不要告诉任何人。"

    # -------------------------------------------------------------- result builders

    @staticmethod
    def _view(*, action: str, item: SubscriptionItem | None = None,
              list_result: SubscriptionListResult | None = None,
              operation_id: str | None = None,
              operation: OperationResult[SubscriptionCancelReceipt] | None = None) -> SubscriptionTaskView:
        return SubscriptionTaskView(action=action, list_result=list_result, selected_item=item,
                                    operation_id=operation_id, operation=operation)

    def list_task(self, context: TrustedContext, result: SubscriptionListResult,
                  *, reminder_days: int = 30) -> ModuleResult:
        return ModuleResult(
            task_id=context.task_id, run_id=context.run_id, status=TaskStatus.SUCCEEDED,
            data=self._view(action="list", list_result=result),
            message=self.inventory_message(result, reminder_days=reminder_days), interaction=None,
            error=None, allowed_actions=[], recovery_required=False, recovery_reason=None)

    def completed(self, context: TrustedContext, message: str, *, item: SubscriptionItem | None = None,
                  list_result: SubscriptionListResult | None = None) -> ModuleResult:
        view = (self._view(action="cancel", item=item) if item is not None
                else self._view(action="list", list_result=list_result))
        return ModuleResult(
            task_id=context.task_id, run_id=context.run_id, status=TaskStatus.SUCCEEDED, data=view,
            message=message, interaction=None, error=None, allowed_actions=[],
            recovery_required=False, recovery_reason=None)

    def guide_message(self, item: SubscriptionItem) -> str:
        return item.external_cancel_guide or GUIDE_TEMPLATE.format(
            merchant=item.merchant_name, channel=f"通过{item.channel}" if item.channel else "",
            amount=money(item.amount_fen), count=item.billed_count)

    @staticmethod
    def already_cancelled_message(item: SubscriptionItem) -> str:
        return f"「{item.merchant_name}（{item.service_name}）」此前已经退订，后续不会再自动扣费，无需重复操作。"

    @staticmethod
    def not_found_message() -> str:
        return "名下没有找到这笔签约代扣，请重新查看自动扣费清单。"

    def waiting_input(self, context: TrustedContext, resolution: CancelResolution) -> ModuleResult:
        prompt = resolution.reason or BATCH_REFUSAL
        interaction = InteractionRequest(
            interaction_id=str(uuid4()), kind="input", prompt=prompt,
            required_fields=["merchant_hint"], options=_options(resolution.candidates), record_ref=None)
        return ModuleResult(
            task_id=context.task_id, run_id=context.run_id, status=TaskStatus.WAITING_INPUT,
            data=None, message=prompt, interaction=interaction, error=None,
            allowed_actions=["provide_input", "cancel"], recovery_required=False, recovery_reason=None)

    def waiting_approval(self, context: TrustedContext, answer: GateAnswer, message: str) -> ModuleResult:
        action = "verify" if answer.interaction.kind == "verification" else "confirm"
        return ModuleResult(
            task_id=context.task_id, run_id=context.run_id, status=TaskStatus.WAITING_APPROVAL,
            data=None, message=message, interaction=answer.interaction, error=None,
            allowed_actions=[action, "cancel"], recovery_required=False, recovery_reason=None)

    def cancelled(self, context: TrustedContext, name: str | None = None) -> ModuleResult:
        target = f"「{name}」" if name else "自动扣费"
        return ModuleResult(
            task_id=context.task_id, run_id=context.run_id, status=TaskStatus.CANCELLED, data=None,
            message=f"没有退订，{target}仍会按原计划扣费。", interaction=None, error=None,
            allowed_actions=[], recovery_required=False, recovery_reason=None)

    def failed(self, context: TrustedContext, code: str, *, source: str = "subscription",
               upstream: str | None = None, message: str | None = None) -> ModuleResult:
        text = message or _MESSAGES.get(code, _MESSAGES["SUBSCRIPTION_INTERNAL_ERROR"])
        return ModuleResult(
            task_id=context.task_id, run_id=context.run_id, status=TaskStatus.FAILED, data=None,
            message=text, interaction=None,
            error=ModuleError(code=code, source=source, field=None, reason=text, upstream_code=upstream),
            allowed_actions=[], recovery_required=False, recovery_reason=None)

    def security_stop(self, context: TrustedContext, reason_code: str | None) -> ModuleResult:
        """Only the coercion block gets the anti-fraud wording; other stops stay honest."""

        if reason_code == HIGH_RISK_REASON:
            return self.failed(context, "HIGH_RISK_BLOCKED", source="security", upstream=reason_code)
        if reason_code == VERIFICATION_FAILED_REASON:
            return self.failed(context, "VERIFICATION_TERMINATED", source="security",
                               upstream=reason_code)
        return self.failed(context, "SECURITY_REJECTED", source="security", upstream=reason_code)

    def cancel_task(self, context: TrustedContext, item: SubscriptionItem, plan: CancellationPlan,
                    outcome: ExecutionOutcome) -> ModuleResult:
        """Report exactly what the bank returned; unknown is never written as success."""

        result = outcome.result
        if isinstance(result, OperationResult):
            # A duplicate confirmation or a recovery replay hands back the claimed
            # operation's own result; the bank's receipt stays the truth, never a refusal.
            return self._report_operation(context, item, result)
        if isinstance(result, QueryFailure):
            # The bank's own refusal: only its code is reported, and it is final.
            if result.error.code == "CALL_TIMEOUT":
                return self.needs_attention(context, item=item, operation_id=outcome.operation_id)
            return self._bank_failure(context, result)
        if not outcome.executed:
            answer = outcome.decision
            if answer is not None and answer.decision == SecurityDecisionCode.BLOCK:
                return self.security_stop(context, answer.reason_code)
            if outcome.state in {"unknown", "processing"}:
                # A recovery replay that still has no bank answer: keep waiting.
                return self.needs_attention(context, item=item, operation_id=outcome.operation_id)
            return self.failed(context, "SECURITY_REJECTED", source="security",
                               message=_MESSAGES["SECURITY_REJECTED"])
        if outcome.state in {"unknown", "processing"}:
            # The write was submitted but the bank has not confirmed it: say so, and
            # keep the task open for one B14 lookup instead of reporting a fault.
            return self.needs_attention(context, item=item, operation_id=outcome.operation_id)
        return self.failed(context, "SUBSCRIPTION_INTERNAL_ERROR", source="bank")

    def _bank_failure(self, context: TrustedContext, result: QueryFailure) -> ModuleResult:
        upstream = result.error.code
        code = upstream if upstream in _SAFE_BANK_CODES else "BANK_REJECTED"
        return self.failed(context, code, source="bank", upstream=upstream,
                           message=_MESSAGES.get(code, _MESSAGES["BANK_REJECTED"]))

    def needs_attention(self, context: TrustedContext, *, item: SubscriptionItem | None = None,
                        operation_id: str | None = None,
                        reason: str = "OPERATION_UNKNOWN") -> ModuleResult:
        """The cancel outcome is not known yet; never write it as success or failure."""

        data = (self._view(action="cancel", item=item, operation_id=operation_id)
                if item is not None else None)
        return ModuleResult(
            task_id=context.task_id, run_id=context.run_id, status=TaskStatus.NEEDS_ATTENTION,
            data=data, message=_MESSAGES["CALL_TIMEOUT"], interaction=None, error=None,
            allowed_actions=["query"], recovery_required=True, recovery_reason=reason)

    def _report_operation(self, context: TrustedContext, item: SubscriptionItem,
                          result: OperationResult[SubscriptionCancelReceipt]) -> ModuleResult:
        if result.operation_status == "processing":
            return self.needs_attention(context, item=item, operation_id=result.operation_id,
                                        reason="OPERATION_PROCESSING")
        if result.operation_status != "succeeded" or result.receipt is None:
            reason = result.failure.code if result.failure else "BANK_REJECTED"
            return self.failed(context, reason if reason in _MESSAGES else "BANK_REJECTED",
                               source="bank", upstream=reason)
        receipt = result.receipt
        stopped = self._cancelled_item(item, receipt)
        message = (f"「{receipt.merchant_name}（{receipt.service_name}）」已经退了。"
                   f"从下一期（{receipt.effective_stop_at.date().isoformat()}）起不会再自动扣费；"
                   f"之前已经扣掉的钱不退。")
        return ModuleResult(
            task_id=context.task_id, run_id=context.run_id, status=TaskStatus.SUCCEEDED,
            data=self._view(action="cancel", item=stopped, operation_id=result.operation_id,
                            operation=result),
            message=message, interaction=None, error=None, allowed_actions=[],
            recovery_required=False, recovery_reason=None)

    @staticmethod
    def _cancelled_item(item: SubscriptionItem, receipt: SubscriptionCancelReceipt) -> SubscriptionItem:
        # The bank stopped the agreement; the task view must not keep promising a next debit.
        return item.model_copy(update={
            "status": "cancelled", "can_cancel_in_bank": False, "is_upcoming_renewal": False,
            "days_until_renewal": None, "next_billing_at": None,
        })
