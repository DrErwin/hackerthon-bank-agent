"""02/L02 deterministic anomaly checks over already-authorized B08 transactions.

Private rule engine, not a public capability or bank/security decision. Callers
must supply complete authenticated lookback facts and trusted family metadata.
It NEVER orders transfers, freezes cards, cancels subscriptions or sends alerts.
Public types come from app.contracts; the task entry owns candidate selection.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")


class TransactionFact(Protocol):
    transaction_id: str
    account_id: str
    occurred_at: datetime
    amount_fen: int
    nature: str
    direction: str
    counterparty_id: str | None


@dataclass(frozen=True)
class RuleCheck:
    rule_id: int
    status: str  # evaluated | insufficient_data
    matched: bool | None
    reason: str | None = None


@dataclass(frozen=True)
class Finding:
    transaction_ids: tuple[str, ...]
    rule_id: int
    attention: str  # notice | high_attention; NOT SecurityGate risk
    evidence: str
    suggestion: str = "请核对是否本人操作；如有疑问，可拨打银行卡背面的客服电话。"


def _outbound(item: TransactionFact) -> bool:
    return item.direction == "outflow" and item.nature in ("consumption", "transfer")


def _eligible_history(rows: Iterable[TransactionFact], target: TransactionFact) -> tuple[TransactionFact, ...]:
    return tuple(x for x in rows if x.occurred_at < target.occurred_at
                 and x.transaction_id != target.transaction_id)


def _large(target: TransactionFact, rows: tuple[TransactionFact, ...]) -> bool | None:
    if not rows:
        return None
    return target.amount_fen > max(x.amount_fen for x in rows) or (
        target.amount_fen * len(rows) > 2 * sum(x.amount_fen for x in rows)
    )


def _check(rule_id: int, result: bool | None, *, reason: str | None = None) -> RuleCheck:
    return RuleCheck(rule_id, "insufficient_data" if result is None else "evaluated", result, reason)


def check_single(target: TransactionFact, previous_three_months: Iterable[TransactionFact], *,
                 lookback_complete: bool, family_transfer: bool | None = None,
                 periodic_history: Iterable[TransactionFact] | None = None,
                 periodic_complete: bool = False) -> tuple[tuple[RuleCheck, ...], tuple[Finding, ...]]:
    """Check one already located bank row. Never treat missing lookback as normal.

    The caller supplies exact 3-month B08 lookback scope; this layer does not
    choose periods or infer trusted kinship from display names.
    """
    history = _eligible_history(previous_three_months, target)
    amount_history = tuple(row for row in history if _outbound(row))
    candidate = _outbound(target)
    large = _large(target, amount_history) if lookback_complete and candidate else None
    checks: list[RuleCheck] = []
    findings: list[Finding] = []
    if candidate and target.nature == "transfer" and family_transfer is None:
        checks.append(_check(1, None, reason="trusted_family_status_required"))
    elif candidate and target.nature == "transfer" and family_transfer:
        checks.append(_check(1, False, reason="family_transfer_exclusion"))
    else:
        checks.append(_check(1, large, reason=None if lookback_complete else "lookback_incomplete"))
        if large:
            findings.append(Finding((target.transaction_id,), 1, "notice", "本笔金额超过近三个月的历史最大单笔或平均单笔两倍。"))

    seen = (bool(target.counterparty_id) and any(x.counterparty_id == target.counterparty_id for x in history))
    if not candidate or not target.counterparty_id or not lookback_complete:
        checks.append(_check(2, None, reason="counterparty_or_lookback_missing"))
    else:
        unusual = not seen and (target.nature == "transfer" or large is True)
        if target.nature == "consumption" and large is None:
            checks.append(_check(2, None, reason="amount_baseline_missing"))
        else:
            checks.append(_check(2, unusual))
            if unusual:
                findings.append(Finding((target.transaction_id,), 2,
                    "high_attention" if target.nature == "transfer" else "notice",
                    "近三个月未见此对手方账户。" if target.nature == "transfer" else "新商户且金额明显高于既往交易。"))

    when = target.occurred_at
    if when.tzinfo is None or when.utcoffset() is None:
        checks.append(_check(3, None, reason="timezone_missing"))
    elif not candidate:
        checks.append(_check(3, False))
    else:
        local = when.astimezone(BEIJING)
        # Issue #132: PM fixed the Beijing interval to [22:00, 06:00)
        # on 2026-10-18. Exactly 06:00 is a checked, non-night transaction.
        night = local.hour >= 22 or local.hour < 6
        checks.append(_check(3, night))
        if night:
            findings.append(Finding((target.transaction_id,), 3, "notice", "该交易发生在北京时间夜间时段，请核对是否本人操作。"))

    if periodic_complete and periodic_history is not None:
        scan_checks, candidates = check_scan(periodic_history, complete=True)
        matched = [item for item in candidates if target.transaction_id in item.transaction_ids]
        checked = scan_checks[0].status == "evaluated"
        checks.append(_check(4, bool(matched) if checked else None, reason=scan_checks[0].reason))
        findings.extend(matched)
    else:
        checks.append(_check(4, None, reason="periodic_history_incomplete"))
    return tuple(checks), tuple(findings)


def _expected_day(anchor_day: int, anchor_last: bool, year: int, month: int) -> int:
    last_day = monthrange(year, month)[1]
    return last_day if anchor_last else min(anchor_day, last_day)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def periodic_groups(rows: Iterable[TransactionFact], *, complete: bool) -> tuple[Finding, ...]:
    """M13: one monthly charge, fixed original day ±3, three contiguous months.

    Nothing is emitted when the caller cannot prove a complete read. This does
    not classify a subscription as unauthorized and never actively notifies.
    """
    if not complete:
        return ()
    by_merchant: dict[tuple[str, int], list[TransactionFact]] = {}
    for item in rows:
        if (item.nature != "consumption" or item.direction != "outflow"
                or not item.counterparty_id or item.occurred_at.tzinfo is None):
            continue
        by_merchant.setdefault((item.counterparty_id, item.amount_fen), []).append(item)
    findings: list[Finding] = []
    for (_, amount), charges in sorted(by_merchant.items()):
        charges.sort(key=lambda r: (r.occurred_at, r.transaction_id))
        used: set[str] = set()
        for anchor in charges:
            if anchor.transaction_id in used:
                continue
            local = anchor.occurred_at.astimezone(BEIJING)
            month, year = local.month, local.year
            anchor_last = local.day == monthrange(year, month)[1]
            sequence = [anchor]
            target_year, target_month = _next_month(year, month)
            while True:
                expected = _expected_day(local.day, anchor_last, target_year, target_month)
                choices = [x for x in charges if x.transaction_id not in used and x not in sequence
                    and x.occurred_at.astimezone(BEIJING).year == target_year
                    and x.occurred_at.astimezone(BEIJING).month == target_month
                    and abs(x.occurred_at.astimezone(BEIJING).day - expected) <= 3]
                if not choices:
                    break
                choices.sort(key=lambda x: (abs(x.occurred_at.astimezone(BEIJING).day - expected),
                    x.occurred_at, x.transaction_id))
                sequence.append(choices[0])
                target_year, target_month = _next_month(target_year, target_month)
            if len(sequence) >= 3:
                used.update(x.transaction_id for x in sequence)
                findings.append(Finding(tuple(x.transaction_id for x in sequence), 4, "notice",
                    f"同一商户有{len(sequence)}个连续自然月出现相同金额（{amount}分）的扣款。"))
    return tuple(findings)


def check_scan(rows: Iterable[TransactionFact], *, complete: bool) -> tuple[tuple[RuleCheck, ...], tuple[Finding, ...]]:
    """Opening a bill scans ONLY rule 4 and does not send push notifications."""
    rows = tuple(rows)
    findings = periodic_groups(rows, complete=complete)
    if complete and any(row.nature == "consumption" and row.direction == "outflow"
                        and not row.counterparty_id for row in rows):
        # Known merchant groups may still yield evidence. Missing identities
        # prevent a complete negative conclusion for the remaining charges.
        return (_check(4, None, reason="merchant_identity_missing"),), findings
    return (_check(4, bool(findings) if complete else None,
                    reason=None if complete else "periodic_history_incomplete"),), findings
