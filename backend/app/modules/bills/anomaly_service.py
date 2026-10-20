"""L02 typed business logic over security-checked B01/B08 facts.

The optional located_scope is private task state, never a public-input field.
It lets a selected candidate be re-read without trusting client transaction facts.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta, timezone
import logging
from typing import Callable

from pydantic import ValidationError

from app.contracts.bank import AccountList, QueryFailure, Transaction, TransactionList
from app.contracts.bills import (
    AccountSourceAsOf, AnomalyFinding, AnomalyResult, BillScope,
    DetectAnomaliesInput, RuleCheck as PublicRuleCheck, TransactionCandidates,
    TransactionClues,
)
from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.tasks import ModuleError, ModuleResult
from ._anomalies import BEIJING, check_scan, check_single
from .service import BillsError, BillsReads, fail, unpack

LOGGER = logging.getLogger(__name__)


def minus_months(at: datetime, count: int) -> datetime:
    """Form a calendar query; the bank remains the authority on valid ranges."""
    local = at.astimezone(BEIJING)
    total = local.year * 12 + local.month - 1 - count
    year, month = divmod(total, 12)
    return local.replace(year=year, month=month + 1,
                         day=min(local.day, monthrange(year, month + 1)[1]))


def complete_months(start: datetime, end: datetime) -> int:
    """Count fully observed Beijing months, excluding unobserved future dates."""
    first, last = start.astimezone(BEIJING), end.astimezone(BEIJING)
    first_index = first.year * 12 + first.month - 1
    if first != first.replace(day=1, hour=0, minute=0, second=0, microsecond=0):
        first_index += 1
    return max(0, last.year * 12 + last.month - 1 - first_index)


class BillsAnomalyService:
    def __init__(self, reads: BillsReads, clock: Callable[[], datetime]):
        self.reads, self.clock = reads, clock

    def accounts(self, trusted: TrustedContext) -> AccountList:
        accounts = unpack(self.reads.accounts(trusted), AccountList)
        ids = [account.account_id for account in accounts.accounts]
        if len(ids) != len(set(ids)):
            raise BillsError("INCOMPLETE_FACTS", source="bank")
        return accounts

    def _owned(self, trusted: TrustedContext) -> set[str]:
        return {account.account_id for account in self.accounts(trusted).accounts}

    def _now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise BillsError("INCOMPLETE_FACTS")
        return now

    def _range(self, trusted: TrustedContext, account_id: str,
               start_at: datetime, end_at: datetime) -> tuple[tuple[Transaction, ...], datetime]:
        response = self.reads.transactions(trusted, account_id, start_at, end_at)
        return self._checked_range(response, account_id, start_at, end_at)

    def _checked_range(self, response, account_id, start_at, end_at):
        flows = unpack(response, TransactionList)
        # Sample after the read so a genuine later bank cutoff is accepted.
        if flows.as_of > self._now():
            raise BillsError("INCOMPLETE_FACTS", source="bank")
        if flows.as_of < start_at:
            raise BillsError("RANGE_UNSUPPORTED")
        seen: set[str] = set()
        for row in flows.transactions:
            if (row.account_id != account_id or not start_at <= row.occurred_at < end_at
                    or row.transaction_id in seen or row.occurred_at > flows.as_of):
                raise BillsError("INCOMPLETE_FACTS", source="bank")
            seen.add(row.transaction_id)
        return tuple(flows.transactions), flows.as_of

    def _lookup_id(self, trusted, account_id):
        """Ask B08 for its supported bound, without duplicating bank retention.

        There is no B08 get-by-ID operation. One bounded retry uses only the
        bank's structured range response; an advancing boundary must not turn
        an incomplete lookup into a misleading RECORD_NOT_FOUND.
        """
        start_at, end_at = datetime.min.replace(tzinfo=timezone.utc), self._now()
        for attempt in range(2):
            response = self.reads.transactions(trusted, account_id, start_at, end_at)
            if not (isinstance(response, QueryFailure)
                    and response.error.code == "RANGE_UNSUPPORTED"):
                return self._checked_range(response, account_id, start_at, end_at)
            if attempt:
                break
            bound = response.error.details.get("earliest_supported_at")
            try:
                earliest = datetime.fromisoformat(bound) if isinstance(bound, str) else None
                if (earliest is None or earliest.tzinfo is None or earliest.utcoffset() is None
                        or not start_at < earliest < end_at):
                    break
            except ValueError:
                break
            start_at = earliest
        raise BillsError("BILLS_LOCATE_REQUIRED", upstream="RANGE_UNSUPPORTED")

    def _scope(self, trusted: TrustedContext, scope: BillScope, owned: set[str]):
        if not set(scope.account_ids).issubset(owned):
            raise BillsError("ACCESS_DENIED", source="security")
        records, timestamps = [], []
        for account_id in scope.account_ids:
            rows, at = self._range(trusted, account_id, scope.start_at, scope.end_at)
            records.extend(rows)
            timestamps.append(AccountSourceAsOf(account_id=account_id, as_of=at))
        # Findings identify transactions by ID, so ambiguity cannot be hidden.
        if len({row.transaction_id for row in records}) != len(records):
            raise BillsError("INCOMPLETE_FACTS", source="bank")
        records.sort(key=lambda row: (row.occurred_at, row.account_id, row.transaction_id))
        return records, timestamps

    @staticmethod
    def _to_result(trusted: TrustedContext, payload, *, text: str) -> ModuleResult:
        return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
                            status=TaskStatus.SUCCEEDED, data=payload, message=text,
                            interaction=None, error=None, allowed_actions=[],
                            recovery_required=False, recovery_reason=None)

    def candidates(self, trusted: TrustedContext, scope: BillScope,
                   clues: TransactionClues | None = None) -> ModuleResult:
        """Private workflow listing when the user cannot supply a matching clue.

        Do not invent an empty public TransactionClues to list recent rows.
        Every candidate is still an authorized, complete bank-query result.
        """
        try:
            scope = BillScope.model_validate(
                scope.model_dump(mode="python") if isinstance(scope, BillScope) else scope)
            if clues is not None:
                clues = TransactionClues.model_validate(
                    clues.model_dump(mode="python") if isinstance(clues, TransactionClues) else clues)
        except (ValidationError, TypeError, ValueError):
            return fail(trusted, BillsError("INVALID_ARGUMENT"))
        try:
            records, timestamps = self._scope(trusted, scope, self._owned(trusted))
            if clues is not None:
                records = [row for row in records
                    if (clues.amount_fen is None or row.amount_fen == clues.amount_fen)
                    and (clues.category is None or row.category == clues.category)
                    and (clues.channel is None or row.channel == clues.channel)
                    and (clues.counterparty_hint is None
                         or clues.counterparty_hint.casefold() in row.counterparty_name.casefold())]
            result = TransactionCandidates(scope=scope, candidates=records,
                source_as_of=timestamps, as_of=min(row.as_of for row in timestamps))
            return self._to_result(trusted, result,
                text=f"完整查询后找到 {len(records)} 笔候选流水，请核对具体交易。")
        except BillsError as error:
            return fail(trusted, error)
        except ValidationError:
            return self._invalid_result(trusted)
        except Exception as error:
            return self._unexpected(trusted, error)

    def _single(self, trusted, query, owned, located_scope):
        if query.account_id not in owned:
            raise BillsError("ACCESS_DENIED", source="security")
        if located_scope is not None:
            scope = BillScope.model_validate(located_scope.model_dump(mode="python")
                if isinstance(located_scope, BillScope) else located_scope)
            if query.account_id not in scope.account_ids:
                raise BillsError("ACCESS_DENIED", source="security")
            start_at, end_at = scope.start_at, scope.end_at
            rows, target_as_of = self._range(trusted, query.account_id, start_at, end_at)
        else:
            rows, target_as_of = self._lookup_id(trusted, query.account_id)
        found = [row for row in rows if row.transaction_id == query.transaction_id]
        if len(found) != 1:
            raise BillsError("RECORD_NOT_FOUND", source="bank")
        selected = found[0]
        history_start = minus_months(selected.occurred_at, 3)
        history_end = selected.occurred_at + timedelta(microseconds=1)
        try:
            history, history_as_of = self._range(
                trusted, query.account_id, history_start, history_end)
            if selected not in history or history_as_of < selected.occurred_at:
                raise BillsError("INCOMPLETE_FACTS", source="bank")
            complete = True
        except BillsError as error:
            if error.code != "RANGE_UNSUPPORTED":
                raise
            # A bank retention limit is an unavailable baseline, never zero.
            history, history_as_of, complete = (), target_as_of, False
        checks, findings = check_single(selected, history, lookback_complete=complete,
            family_transfer=None, periodic_history=history, periodic_complete=complete)
        message = (f"本次规则发现 {len(findings)} 条疑似异常线索。" if findings
                   else "本次可评估规则未发现疑似异常线索。")
        if any(check.status == "insufficient_data" for check in checks):
            message += "部分规则数据不足、未判定，不能据此确认正常或盗刷。"
        return self._to_result(trusted,
            self._anomalies(selected, checks, findings, min(target_as_of, history_as_of)),
            text=message)

    def detect(self, trusted: TrustedContext, request: DetectAnomaliesInput | dict,
               *, located_scope: BillScope | None = None) -> ModuleResult:
        try:
            query = DetectAnomaliesInput.model_validate(
                request.model_dump(mode="python")
                if isinstance(request, DetectAnomaliesInput) else request)
        except (ValidationError, TypeError, ValueError):
            return fail(trusted, BillsError("INVALID_ARGUMENT"))
        if query.mode == "locate":
            return self.candidates(trusted, query.scope, query.clues)
        try:
            owned = self._owned(trusted)
            self._now()
            if query.mode == "single":
                return self._single(trusted, query, owned, located_scope)
            records, timestamps = self._scope(trusted, query.scope, owned)
            as_of = min(row.as_of for row in timestamps)
            observed_end = min(query.scope.end_at, as_of)
            enough_history = complete_months(query.scope.start_at, observed_end) >= 3
            # Three observed matching charges are evidence even in a partial
            # first/last month. Absence needs three fully observed months.
            checks, findings = check_scan(records, complete=True)
            if not enough_history and not findings:
                checks, findings = check_scan(records, complete=False)
            message = "仅检查疑似周期扣款，没有代为取消或发送通知。"
            if checks[0].status == "insufficient_data":
                message = ("部分流水缺少商户标识，周期扣款规则的数据不足，不能据此说没有异常。"
                           if checks[0].reason == "merchant_identity_missing" else
                           "当前完整月份不足三个，周期扣款规则的数据不足，不能据此说没有异常。")
            return self._to_result(trusted, self._anomalies(None, checks, findings, as_of),
                                   text=message)
        except BillsError as error:
            if error.code in {"BILLS_LOCATE_REQUIRED", "RECORD_NOT_FOUND"}:
                return self._lookup_error(trusted, error)
            return fail(trusted, error)
        except ValidationError:
            return self._invalid_result(trusted)
        except Exception as error:
            return self._unexpected(trusted, error)

    @staticmethod
    def _lookup_error(trusted, error):
        message = ("目前无法仅凭交易编号完整定位这笔流水，请先指定月份和本人账户，再从银行候选中选择。"
                   if error.code == "BILLS_LOCATE_REQUIRED" else
                   "在本次银行支持的查询范围内没有找到该交易编号，请核对月份或重新选择候选流水。")
        return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
            status=TaskStatus.FAILED, data=None, message=message, interaction=None,
            error=ModuleError(code=error.code, source=error.source, field="transaction_id",
                              reason=message, upstream_code=error.upstream),
            allowed_actions=[], recovery_required=False, recovery_reason=None)

    @staticmethod
    def _invalid_result(trusted):
        LOGGER.warning("bills.anomaly_result_invalid task_id=%s", trusted.task_id)
        return fail(trusted, BillsError("BILLS_RESULT_INVALID"))

    @staticmethod
    def _unexpected(trusted, error):
        LOGGER.error("bills.anomaly_internal_failure task_id=%s class=%s",
                     trusted.task_id, type(error).__name__)
        return fail(trusted, BillsError("BILLS_INTERNAL_ERROR"))

    @staticmethod
    def _anomalies(transaction, checks, findings, as_of):
        return AnomalyResult(transaction=transaction,
            checks=[PublicRuleCheck(rule_id=check.rule_id, status=check.status,
                reason=check.reason or ("matched" if check.matched else "not_matched"
                    if check.matched is False else "insufficient_facts")) for check in checks],
            findings=[AnomalyFinding(transaction_ids=list(item.transaction_ids),
                rule_id=item.rule_id, attention=item.attention,
                evidence=item.evidence, suggestion=item.suggestion) for item in findings], as_of=as_of)
