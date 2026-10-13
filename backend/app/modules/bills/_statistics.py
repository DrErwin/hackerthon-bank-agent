"""Private, side-effect-free arithmetic for frozen bills L01/M05/M11/M12.

This is NOT a bank adapter or a registered Agent capability. The caller must
obtain authorized, complete B08 facts via the public gateway. Shared wire
models remain in app.contracts. The B08/L01 seam from Issue #91 is available;
this increment has no registered entry point and performs no I/O.
The dataclasses below are internal value objects, not a second HTTP contract.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta, timezone
from fractions import Fraction
from typing import Iterable

from app.contracts.common import Category

BEIJING = timezone(timedelta(hours=8))
CATEGORIES = tuple(category.value for category in Category)
SPENDING_CATEGORIES = tuple(c for c in CATEGORIES if c != Category.TRANSFER.value)


def _category_code(value: str) -> str:
    """Normalize only unknown bank tags; transaction nature is not a category."""
    try:
        return Category(value).value
    except ValueError:
        return Category.OTHER.value


def display_bps(value: Fraction | None) -> int | None:
    """Contract §6.11: round the final display ratio, half away from zero."""
    if value is None:
        return None
    if not isinstance(value, Fraction):
        raise TypeError("display ratios must remain exact Fractions")
    numerator = value.numerator * 10000
    rounded = (2 * abs(numerator) + value.denominator) // (2 * value.denominator)
    return rounded if numerator >= 0 else -rounded


class FactsError(ValueError):
    """A fixed diagnostic code; never include raw bank or personal data."""


def _aware(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise FactsError("timezone_required")


def _money(value: int) -> None:
    if type(value) is not int or value < 0:
        raise FactsError("invalid_money")


@dataclass(frozen=True)
class Period:
    """A resolved internal period; account selection/24-month policy is upstream."""
    accounts: tuple[str, ...]
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        _aware(self.start)
        _aware(self.end)
        if self.start >= self.end:
            raise FactsError("invalid_period")
        if (not self.accounts or any(not isinstance(a, str) or not a for a in self.accounts)
                or len(set(self.accounts)) != len(self.accounts)):
            raise FactsError("invalid_accounts")


@dataclass(frozen=True)
class LedgerRow:
    """Minimal private arithmetic projection, produced from validated bank facts.

    No name, account number, address, free text or model-supplied category
    inference is needed to compute money. Category comes from the bank tag.
    """
    transaction_id: str
    account_id: str
    occurred_at: datetime
    amount_fen: int
    nature: str
    category: str
    direction: str
    original_transaction_id: str | None = None
    original_occurred_at: datetime | None = None

    def __post_init__(self) -> None:
        _aware(self.occurred_at)
        _money(self.amount_fen)
        if not self.transaction_id or not self.account_id:
            raise FactsError("missing_record_identity")
        if self.nature not in ("consumption", "transfer", "refund", "interest"):
            raise FactsError("invalid_transaction_nature")
        if self.direction not in ("inflow", "outflow"):
            raise FactsError("invalid_direction")
        if not isinstance(self.category, str):
            raise FactsError("invalid_category")
        if self.original_occurred_at is not None:
            _aware(self.original_occurred_at)


@dataclass(frozen=True)
class AccountBatch:
    """Internal record of one successful B08 call and its requested range.

    A failure must NOT be converted to an empty AccountBatch. There is no
    caller-supplied 'approved' or 'complete' flag. Completeness against the
    actual bank remains the gateway's responsibility; this layer checks that
    all expected calls/ranges and their returned records are present.
    """
    account_id: str
    start: datetime
    end: datetime
    as_of: datetime
    rows: tuple[LedgerRow, ...]


@dataclass(frozen=True)
class Snapshot:
    period: Period
    rows: tuple[LedgerRow, ...]
    source_as_of: tuple[tuple[str, datetime], ...]
    as_of: datetime


def _validate_batch(batch: AccountBatch, period: Period, now: datetime) -> None:
    """Check a successful, already-authorized read; never turn failure into []."""
    if batch.account_id not in period.accounts:
        raise FactsError("unexpected_account")
    _aware(batch.start)
    _aware(batch.end)
    _aware(batch.as_of)
    if batch.start >= batch.end:
        raise FactsError("invalid_period")
    if batch.as_of > now:
        raise FactsError("future_snapshot")
    seen: set[tuple[str, str]] = set()
    for row in batch.rows:
        if row.account_id != batch.account_id:
            raise FactsError("record_account_mismatch")
        if not batch.start <= row.occurred_at < batch.end:
            raise FactsError("record_outside_range")
        if row.occurred_at > batch.as_of:
            raise FactsError("record_after_snapshot")
        identity = (row.account_id, row.transaction_id)
        if identity in seen:
            raise FactsError("duplicate_record")
        seen.add(identity)


def _resolved_row(row: LedgerRow, origins: dict[tuple[str, str], LedgerRow]) -> LedgerRow:
    """M11: a refund uses the original consumption category, never its own tag."""
    category = _category_code(row.category)
    if row.nature == "refund":
        if not row.original_transaction_id or row.original_occurred_at is None:
            raise FactsError("missing_refund_reference")
        original = origins.get((row.account_id, row.original_transaction_id))
        if original is None:
            raise FactsError("missing_refund_original")
        if (original.nature != "consumption" or original.direction != "outflow"
                or original.occurred_at != row.original_occurred_at
                or original.occurred_at > row.occurred_at):
            raise FactsError("refund_original_mismatch")
        category = _category_code(original.category)
    return replace(row, category=category)


def assemble(
    period: Period, batches: Iterable[AccountBatch], *, now: datetime,
    original_batches: Iterable[AccountBatch] = (),
) -> Snapshot:
    """Assemble complete scoped reads and resolve refunds using bank facts.

    All batches must be successful authorized B08 results supplied by the caller.
    Original purchases outside the requested period use separate original_batches
    from the same authorized account. They are evidence ONLY, never counted in
    this period. Missing/conflicting originals stop arithmetic rather than guessing
    a category. No network, bank, auth, retries, persistence or funds action here.
    """
    _aware(now)
    seen_accounts: set[str] = set()
    rows: list[LedgerRow] = []
    dates: dict[str, datetime] = {}
    origins: dict[tuple[str, str], LedgerRow] = {}
    for batch in batches:
        _validate_batch(batch, period, now)
        if batch.account_id in seen_accounts:
            raise FactsError("duplicate_account_batch")
        seen_accounts.add(batch.account_id)
        if batch.start != period.start or batch.end != period.end:
            raise FactsError("incomplete_range")
        dates[batch.account_id] = batch.as_of
        for row in batch.rows:
            origins[(row.account_id, row.transaction_id)] = row
            rows.append(row)
    if seen_accounts != set(period.accounts):
        raise FactsError("missing_account_batch")
    for batch in original_batches:
        _validate_batch(batch, period, now)
        # Supplemental provenance reads also constrain this account's cutoff.
        dates[batch.account_id] = min(dates[batch.account_id], batch.as_of)
        for row in batch.rows:
            identity = (row.account_id, row.transaction_id)
            previous = origins.get(identity)
            if previous is not None and previous != row:
                raise FactsError("conflicting_refund_original")
            origins[identity] = row
    resolved = [_resolved_row(row, origins) for row in rows]
    sources = tuple((a, dates[a]) for a in period.accounts)
    return Snapshot(
        period,
        tuple(sorted(resolved, key=lambda r: (r.occurred_at, r.account_id, r.transaction_id))),
        sources, min(dates.values()),
    )


@dataclass(frozen=True)
class CategoryAmounts:
    category: str
    outflow: int
    refund: int
    net: int
    # Exact private ratio; public share_bps serialization belongs to the adapter.
    share: Fraction | None

    @property
    def share_bps(self) -> int | None:
        return display_bps(self.share)


@dataclass(frozen=True)
class Totals:
    record_count: int
    gross: int
    refund: int
    net: int
    transfer_out: int
    transfer_in: int
    categories: tuple[CategoryAmounts, ...]


def totals(snapshot: Snapshot) -> Totals:
    """Consumption outflow minus refund inflow; transfers/interest stay separate."""
    gross = refund = transfer_out = transfer_in = 0
    amounts = {c: [0, 0] for c in CATEGORIES}
    for row in snapshot.rows:
        if row.nature == "transfer":
            if row.direction == "outflow":
                transfer_out += row.amount_fen
            else:
                transfer_in += row.amount_fen
            continue
        category = row.category if row.category in SPENDING_CATEGORIES else Category.OTHER.value
        if row.nature == "consumption" and row.direction == "outflow":
            gross += row.amount_fen
            amounts[category][0] += row.amount_fen
        elif row.nature == "refund" and row.direction == "inflow":
            refund += row.amount_fen
            amounts[category][1] += row.amount_fen
        # Interest and non-consumption inflow never inflate spending.
    net = gross - refund
    valid_shares = net > 0 and all(amounts[c][0] >= amounts[c][1] for c in SPENDING_CATEGORIES)
    amounts["transfer"] = [transfer_out, 0]
    categories = tuple(CategoryAmounts(c, amounts[c][0], amounts[c][1], amounts[c][0] - amounts[c][1],
                                      Fraction(amounts[c][0] - amounts[c][1], net)
                                      if valid_shares and c != Category.TRANSFER.value
                                      and amounts[c][0] > amounts[c][1] else None)
                       for c in CATEGORIES)
    # Deterministic tie order is only internal display ordering, not a bank rule.
    categories = tuple(sorted(categories, key=lambda c: (-c.net, CATEGORIES.index(c.category))))
    return Totals(len(snapshot.rows), gross, refund, net, transfer_out, transfer_in, categories)


def select_rows(snapshot: Snapshot, category: str | None = None) -> tuple[LedgerRow, ...]:
    """Private filtering; not a display/export path and carries no new authority."""
    if category is None:
        return snapshot.rows
    if category not in CATEGORIES:
        raise FactsError("invalid_category_filter")
    # Contract M16: filter by the (refund-resolved) bank category, not nature.
    return tuple(row for row in snapshot.rows if row.category == category)


@dataclass(frozen=True)
class Difference:
    reference_net: int
    delta: int
    change: Fraction | None
    largest_change_category: str | None

    @property
    def change_bps(self) -> int | None:
        return display_bps(self.change)


def compare(current: Snapshot, reference: Snapshot) -> Difference:
    """Net-spending comparison. A complete empty reference is not a failed read."""
    if set(current.period.accounts) != set(reference.period.accounts):
        raise FactsError("comparison_accounts_mismatch")
    c, r = totals(current), totals(reference)
    cm = {a.category: a.net for a in c.categories}
    rm = {a.category: a.net for a in r.categories}
    differences = {k: cm[k] - rm[k] for k in SPENDING_CATEGORIES}
    largest = max(SPENDING_CATEGORIES, key=lambda k: abs(differences[k]))
    return Difference(r.net, c.net - r.net, Fraction(c.net - r.net, r.net) if r.net > 0 else None,
                      largest if differences[largest] else None)


def statistical_days(snapshot: Snapshot, *, now: datetime) -> int:
    """Contract §5.9: Beijing calendar dates, midnight-exclusive, no future days."""
    _aware(now)
    start = snapshot.period.start.astimezone(BEIJING)
    end = min(snapshot.period.end, snapshot.as_of, now).astimezone(BEIJING)
    if end <= start:
        return 0
    last_day = end.date() - timedelta(days=1) if end.timetz().replace(tzinfo=None) == time(0) else end.date()
    return max(0, (last_day - start.date()).days + 1)


def monthly_average(snapshot: Snapshot, *, now: datetime) -> int | None:
    """Round half-up to fen after multiplying gross by 30; never use float."""
    days = statistical_days(snapshot, now=now)
    if days == 0:
        return None
    numerator = totals(snapshot).gross * 30
    return (2 * numerator + days) // (2 * days)
