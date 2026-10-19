"""Contract §5.9 rules 4/5: flow-only periodic-debit detection for scenario 05.

Same frozen wording as the bills rule: identical integer-fen amount, one debit per
natural month, at least three consecutive months, the first debit anchors every later
expected date (±3 days, never re-anchored), month-end anchors follow each month end,
and every transaction matches at most one series.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime

from app.contracts.bank import Transaction

SUSPECTED_PREFIX = "sus_"
MIN_CONSECUTIVE_MONTHS = 3
DAY_TOLERANCE_DAYS = 3
_PERIODIC_NATURES = frozenset({"consumption"})


@dataclass(frozen=True)
class SuspectedSeries:
    """One flow-only periodic debit series; it is a clue, never a signed mandate."""

    merchant_key: str
    merchant_name: str
    amount_fen: int
    account_id: str
    account_masked: str
    count: int
    total_fen: int
    first_at: datetime
    last_at: datetime
    next_at: datetime
    channel: str | None

    @property
    def subscription_id(self) -> str:
        slug = "".join(char for char in self.merchant_key.lower() if char.isalnum())
        slug = slug.removeprefix("m") or "merchant"
        return f"{SUSPECTED_PREFIX}{slug}_01"


def shift_months(at: datetime, months: int) -> datetime:
    """Calendar months from ``at``, clamped to the target month's length."""

    index = at.month - 1 + months
    year = at.year + index // 12
    month = index % 12 + 1
    return at.replace(year=year, month=month, day=min(at.day, monthrange(year, month)[1]))


def _expected_date(anchor: datetime, months: int, month_end_anchor: bool) -> datetime:
    index = anchor.month - 1 + months
    year = anchor.year + index // 12
    month = index % 12 + 1
    day = monthrange(year, month)[1] if month_end_anchor else min(anchor.day, monthrange(year, month)[1])
    return anchor.replace(year=year, month=month, day=day)


def _debit_rows(rows) -> list[Transaction]:
    return [
        row for row in rows
        if isinstance(row, Transaction)
        and row.direction == "outflow"
        and row.nature in _PERIODIC_NATURES
        and row.counterparty_id is not None
    ]


def _longest_run(rows: list[Transaction]) -> list[Transaction] | None:
    """Greedily grow the series anchored on the earliest unused row; first match wins."""

    for index, anchor in enumerate(rows):
        month_end_anchor = anchor.occurred_at.day == monthrange(
            anchor.occurred_at.year, anchor.occurred_at.month,
        )[1]
        used = {index}
        series = [anchor]
        months = 1
        while True:
            expected = _expected_date(anchor.occurred_at, months, month_end_anchor)
            match = next(
                (position for position, row in enumerate(rows)
                 if position not in used
                 and (row.occurred_at.year, row.occurred_at.month) == (expected.year, expected.month)
                 and abs(row.occurred_at.day - expected.day) <= DAY_TOLERANCE_DAYS),
                None,
            )
            if match is None:
                break
            used.add(match)
            series.append(rows[match])
            months += 1
        if len(series) >= MIN_CONSECUTIVE_MONTHS:
            return sorted(series, key=lambda row: row.occurred_at)
    return None


def find_suspected_series(
    rows, *, excluded_merchants: set[str], account_masked: dict[str, str],
) -> list[SuspectedSeries]:
    """Every merchant without a signed mandate whose own debits form a monthly series."""

    groups: dict[tuple[str, int], list[Transaction]] = {}
    for row in _debit_rows(rows):
        if row.counterparty_id in excluded_merchants:
            continue
        groups.setdefault((row.counterparty_id, row.amount_fen), []).append(row)
    found: list[SuspectedSeries] = []
    for (merchant_key, amount_fen), group in sorted(groups.items()):
        if len(group) < MIN_CONSECUTIVE_MONTHS:
            continue
        series = _longest_run(sorted(group, key=lambda row: row.occurred_at))
        if series is None:
            continue
        first, last = series[0], series[-1]
        found.append(SuspectedSeries(
            merchant_key=merchant_key, merchant_name=last.counterparty_name,
            amount_fen=amount_fen, account_id=last.account_id,
            account_masked=account_masked.get(last.account_id, ""),
            count=len(series), total_fen=amount_fen * len(series),
            first_at=first.occurred_at, last_at=last.occurred_at,
            next_at=shift_months(last.occurred_at, 1),
            channel=last.channel or None,
        ))
    return found


def coverage_months(rows, *, window_end: datetime) -> int:
    """How many natural months of flow facts the scan actually saw (0 when empty)."""

    occurred = [row.occurred_at for row in rows if isinstance(row, Transaction)]
    if not occurred:
        return 0
    earliest = min(occurred)
    return (window_end.year * 12 + window_end.month) - (earliest.year * 12 + earliest.month) + 1


def scan_window(now: datetime, *, months: int = 12) -> tuple[datetime, datetime]:
    """The read window for the suspected scan; half-open, ending at the bank clock."""

    return shift_months(now, -months), now
