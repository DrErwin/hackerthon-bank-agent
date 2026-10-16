"""L01 public calculation over security-checked B08 facts; no bank storage access."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from datetime import datetime, timedelta
from typing import Callable, Protocol

from pydantic import ValidationError

from app.contracts.bank import AccountList, QueryFailure, QueryOk, Transaction, TransactionList
from app.contracts.bills import (
    AccountSourceAsOf, BillDetails, BillScope, BillSummarizeInput, CategoryTotal,
    SpendingComparison, SpendingSummary,
)
from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.tasks import ModuleError, ModuleResult
from ._statistics import AccountBatch, FactsError, LedgerRow, Period, Snapshot, assemble, compare, select_rows, totals


LOGGER = logging.getLogger(__name__)


class BillsError(ValueError):
    """Only stable codes cross the public boundary, never upstream exception text."""
    def __init__(self, code: str, *, source: str = "bills", upstream: str | None = None):
        super().__init__(code)
        self.code, self.source, self.upstream = code, source, upstream


class BillsReads(Protocol):
    """Production implementations must use the shared security executor and gateway."""
    def accounts(self, context: TrustedContext) -> object: ...
    def transactions(self, context: TrustedContext, account_id: str,
                     start_at: datetime, end_at: datetime) -> object: ...


@dataclass(frozen=True)
class ReadSnapshot:
    arithmetic: Snapshot
    transactions: dict[tuple[str, str], Transaction]


_MESSAGES = {
    "ACCESS_DENIED": "无权读取所选账户的账单。",
    "AUTH_REQUIRED": "请重新登录后查询本人账单。",
    "RANGE_UNSUPPORTED": "银行不支持这个时间范围，请修改范围后再查询。",
    "INVALID_ARGUMENT": "查询条件不完整或格式不正确，请核对账户和时间范围。",
    "INCOMPLETE_FACTS": "账单事实不完整或不一致，暂时不能给出完整统计。",
    "DEPENDENCY_UNAVAILABLE": "暂时没有取得完整账单，请稍后重试。",
    "SECURITY_REJECTED": "当前查询未通过安全检查，没有读取账单。",
    "BILLS_RESULT_INVALID": "账单计算结果校验未通过，暂时不能提供统计。",
    "BILLS_INTERNAL_ERROR": "账单服务暂时不可用，请稍后再试。",
}
_SAFE_BANK_CODES = {"ACCESS_DENIED", "AUTH_REQUIRED", "RANGE_UNSUPPORTED", "INVALID_ARGUMENT",
                    "CALL_TIMEOUT", "DEPENDENCY_UNAVAILABLE", "RECORD_NOT_FOUND"}


def fail(context: TrustedContext, error: BillsError) -> ModuleResult:
    return ModuleResult(
        task_id=context.task_id, run_id=context.run_id, status=TaskStatus.FAILED,
        data=None, message=_MESSAGES.get(error.code, _MESSAGES["DEPENDENCY_UNAVAILABLE"]),
        interaction=None, error=ModuleError(code=error.code, source=error.source,
            field=None, reason=_MESSAGES.get(error.code, _MESSAGES["DEPENDENCY_UNAVAILABLE"]),
            upstream_code=error.upstream), allowed_actions=[],
        recovery_required=False, recovery_reason=None,
    )


def unpack(response: object, model):
    if isinstance(response, QueryFailure):
        upstream = response.error.code if response.error.code in _SAFE_BANK_CODES else "DEPENDENCY_UNAVAILABLE"
        code = upstream if upstream in _MESSAGES else "DEPENDENCY_UNAVAILABLE"
        raise BillsError(code, source="bank", upstream=upstream)
    if not isinstance(response, QueryOk):
        raise BillsError("INCOMPLETE_FACTS", source="bank")
    try:
        payload = response.data.model_dump(mode="python") if hasattr(response.data, "model_dump") else response.data
        return model.model_validate(payload)
    except (ValidationError, TypeError, ValueError):
        raise BillsError("INCOMPLETE_FACTS", source="bank") from None


def _row(transaction: Transaction) -> LedgerRow:
    return LedgerRow(transaction.transaction_id, transaction.account_id, transaction.occurred_at,
        transaction.amount_fen, transaction.nature, transaction.category.value, transaction.direction,
        transaction.original_transaction_id, transaction.original_occurred_at)


def money(value: int) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value) // 100}.{abs(value) % 100:02d}"


class BillsService:
    """Public typed L01 handler. Reads are injected by the platform, never by user JSON."""
    def __init__(self, reads: BillsReads, clock: Callable[[], datetime]):
        self.reads, self.clock = reads, clock

    def accounts(self, context: TrustedContext) -> AccountList:
        return unpack(self.reads.accounts(context), AccountList)

    def _snapshot(self, context: TrustedContext, scope: BillScope, now: datetime) -> ReadSnapshot:
        batches, originals, records = [], [], {}
        period = Period(tuple(scope.account_ids), scope.start_at, scope.end_at)
        for account_id in scope.account_ids:
            response = unpack(self.reads.transactions(context, account_id, scope.start_at, scope.end_at), TransactionList)
            batches.append(AccountBatch(account_id, scope.start_at, scope.end_at,
                                        response.as_of, tuple(_row(t) for t in response.transactions)))
            for t in response.transactions:
                records[(t.account_id, t.transaction_id)] = t
        # Fetch provenance from the SAME authorized account. B08 owns its range policy.
        # De-duplicate requests for originals occurring at the same instant.
        needed = {(t.account_id, t.original_occurred_at) for t in records.values()
                  if t.nature == "refund" and
                  (t.account_id, t.original_transaction_id) not in records}
        for account_id, at in sorted(needed, key=lambda item: (item[0], item[1])):
            end = at + timedelta(microseconds=1)
            response = unpack(self.reads.transactions(context, account_id, at, end), TransactionList)
            originals.append(AccountBatch(account_id, at, end, response.as_of,
                                           tuple(_row(t) for t in response.transactions)))
        # The clock is sampled AFTER reads: a live bank cutoff is normally later
        # than the time at which the request started. Future facts remain rejected.
        completed_at = self.clock()
        snapshot = assemble(period, batches, now=completed_at, original_batches=originals)
        return ReadSnapshot(snapshot, records)

    def summarize(self, context: TrustedContext, request: BillSummarizeInput | dict) -> ModuleResult:
        # Only input-shape rejection is INVALID_ARGUMENT. A later *output*
        # model validation failure is not the user's fault or a bank timeout.
        try:
            request = BillSummarizeInput.model_validate(
                request.model_dump(mode="python") if isinstance(request, BillSummarizeInput) else request)
        except (ValidationError, TypeError, ValueError):
            return fail(context, BillsError("INVALID_ARGUMENT"))
        try:
            now = self.clock()
            if now.tzinfo is None or now.utcoffset() is None:
                raise BillsError("INCOMPLETE_FACTS")
            owned = self.accounts(context)
            ids = [a.account_id for a in owned.accounts]
            if len(ids) != len(set(ids)):
                raise BillsError("INCOMPLETE_FACTS", source="bank")
            if not set(request.scope.account_ids) <= set(ids):
                raise BillsError("ACCESS_DENIED", source="security")
            current = self._snapshot(context, request.scope, now)
            snapshot = current.arithmetic
            sources = [AccountSourceAsOf(account_id=a, as_of=t) for a, t in snapshot.source_as_of]
            if request.mode == "details":
                # Use original bank metadata; only resolve the frozen refund category rule.
                rows = select_rows(snapshot, request.category.value if request.category else None)
                data = BillDetails(scope=request.scope, category=request.category,
                    transactions=[Transaction.model_validate({
                        **current.transactions[(r.account_id, r.transaction_id)].model_dump(mode="python"),
                        "category": r.category}) for r in rows],
                    source_as_of=sources, as_of=snapshot.as_of)
                message = f"查询到 {len(rows)} 笔匹配记录。" if rows else "完整查询后没有匹配记录。"
            else:
                amount = totals(snapshot)
                comparison = None
                if request.comparison_scope is not None:
                    reference = self._snapshot(context, request.comparison_scope, now).arithmetic
                    change = compare(snapshot, reference)
                    comparison = SpendingComparison(scope=request.comparison_scope, as_of=reference.as_of,
                        consumption_net_fen=change.reference_net, delta_fen=change.delta,
                        change_bps=change.change_bps, largest_change_category=change.largest_change_category)
                data = SpendingSummary(scope=request.scope, as_of=snapshot.as_of, source_as_of=sources,
                    transaction_count=amount.record_count, consumption_gross_fen=amount.gross,
                    consumption_refund_fen=amount.refund, consumption_net_fen=amount.net,
                    transfer_out_fen=amount.transfer_out, transfer_in_fen=amount.transfer_in,
                    categories=[CategoryTotal(category=c.category, outflow_fen=c.outflow,
                        refund_fen=c.refund, net_fen=c.net, share_bps=c.share_bps, rank=i)
                        for i, c in enumerate(amount.categories, 1)], comparison=comparison)
                if amount.record_count == 0:
                    message = "这个范围没有查到交易记录。"
                else:
                    message = (f"本人账户共 {amount.record_count} 笔记录，消费支出 {money(amount.gross)} 元，"
                        f"退款 {money(amount.refund)} 元，净消费 {money(amount.net)} 元；"
                        f"转出 {money(amount.transfer_out)} 元、转入 {money(amount.transfer_in)} 元单列。")
                if comparison is not None:
                    message += f"与对照期净消费相差 {money(comparison.delta_fen)} 元。"
                    if comparison.change_bps is None:
                        message += "对照期净消费非正，不显示增长率。"
            return ModuleResult(task_id=context.task_id, run_id=context.run_id, status=TaskStatus.SUCCEEDED,
                data=data, message=message, interaction=None, error=None, allowed_actions=[],
                recovery_required=False, recovery_reason=None)
        except ValidationError:
            # Log only a stable reason and trusted task identifier, not Pydantic's
            # exception (it may embed bank transaction or merchant data).
            LOGGER.warning("bills.result_contract_invalid task_id=%s", context.task_id)
            return fail(context, BillsError("BILLS_RESULT_INVALID"))
        except FactsError:
            return fail(context, BillsError("INCOMPLETE_FACTS"))
        except BillsError as error:
            return fail(context, error)
        except Exception as error:
            # Do not leak raw upstream exception text or a traceback containing
            # user-bank facts into logs or ModuleResult.
            LOGGER.error("bills.internal_failure task_id=%s class=%s",
                         context.task_id, type(error).__name__)
            return fail(context, BillsError("BILLS_INTERNAL_ERROR"))
