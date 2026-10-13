"""Regression assertions for review #92; arithmetic, not authorization or E2E."""
from dataclasses import replace
from datetime import datetime, timedelta
from fractions import Fraction

import pytest
from app.contracts.common import Category
from app.modules.bills._statistics import (
    AccountBatch, CATEGORIES, FactsError, LedgerRow, Period,
    assemble, compare, display_bps, select_rows, totals,
)

START = datetime.fromisoformat("2026-09-01T00:00:00+08:00")
END = datetime.fromisoformat("2026-10-01T00:00:00+08:00")
NOW = datetime.fromisoformat("2026-10-13T10:00:00+08:00")
PERIOD = Period(("a1",), START, END)


def purchase(id="original", *, category="shopping", at=START, account="a1", amount=50000):
    return LedgerRow(id, account, at, amount, "consumption", category, "outflow")


def refund(original, *, category="dining", at=START+timedelta(days=1), account="a1"):
    return LedgerRow("refund", account, at, 20000, "refund", category, "inflow",
                     original.transaction_id, original.occurred_at)


def snapshot(rows, history=()):
    current = AccountBatch("a1", START, END, NOW, tuple(rows))
    return assemble(PERIOD, [current], now=NOW, original_batches=history)


def history_batch(original, *, as_of=NOW):
    return AccountBatch(original.account_id, original.occurred_at,
                        original.occurred_at+timedelta(seconds=1), as_of, (original,))


def test_category_codes_are_derived_from_the_shared_contract():
    assert CATEGORIES == tuple(item.value for item in Category)


def test_refund_with_a_different_tag_uses_original_and_preserves_reference():
    original = purchase()
    raw_refund = refund(original, category="dining")
    s = snapshot([original, raw_refund])
    result = totals(s)
    amounts = {r.category: r for r in result.categories}
    assert (amounts["shopping"].outflow, amounts["shopping"].refund, amounts["shopping"].net) == (50000, 20000, 30000)
    assert amounts["dining"].net == 0
    resolved = next(r for r in s.rows if r.nature == "refund")
    assert (resolved.category, resolved.original_transaction_id, resolved.original_occurred_at) == ("shopping", original.transaction_id, START)
    assert raw_refund.category == "dining"  # immutable input facts were not edited
    assert [r.transaction_id for r in select_rows(s, "shopping")] == ["original", "refund"]
    assert not select_rows(s, "dining")


def test_prior_month_original_is_provenance_only_and_is_not_counted_again():
    original = purchase(at=START-timedelta(days=8), amount=80000)
    s = snapshot([refund(original)], [history_batch(original)])
    result = totals(s)
    assert (result.record_count, result.gross, result.refund, result.net) == (1, 0, 20000, -20000)
    assert next(r for r in result.categories if r.category == "shopping").refund == 20000
    assert original.amount_fen == 80000


@pytest.mark.parametrize("field,value", [("original_transaction_id", None), ("original_occurred_at", None)])
def test_refund_missing_reference_stops_before_claiming_complete(field, value):
    original = purchase()
    with pytest.raises(FactsError, match="^missing_refund_reference$"):
        snapshot([original, replace(refund(original), **{field: value})])


def test_missing_prior_month_original_is_not_guessed_from_refund_tag():
    original = purchase(at=START-timedelta(days=8))
    with pytest.raises(FactsError, match="^missing_refund_original$"):
        snapshot([refund(original)])


@pytest.mark.parametrize("change", [
    {"nature": "transfer"}, {"direction": "inflow"},
    {"occurred_at": START+timedelta(hours=1)},
])
def test_wrong_original_facts_are_rejected(change):
    original = purchase()
    altered = replace(original, **change)
    with pytest.raises(FactsError, match="^refund_original_mismatch$"):
        snapshot([altered, refund(original)])


def test_same_transaction_id_on_another_account_is_not_the_original():
    original = purchase(account="a2")
    p = Period(("a1", "a2"), START, END)
    batches = [AccountBatch("a1", START, END, NOW, (refund(original),)),
               AccountBatch("a2", START, END, NOW, (original,))]
    with pytest.raises(FactsError, match="^missing_refund_original$"):
        assemble(p, batches, now=NOW)


def test_conflicting_original_across_two_reads_is_not_silently_overwritten():
    original = purchase()
    conflict = replace(original, category="medical")
    with pytest.raises(FactsError, match="^conflicting_refund_original$"):
        snapshot([original, refund(original)], [history_batch(conflict)])


def test_repeated_identical_original_is_not_counted_twice():
    original = purchase()
    s = snapshot([original, refund(original)], [history_batch(original)])
    assert (totals(s).record_count, totals(s).net) == (2, 30000)


@pytest.mark.parametrize("bad", ["foreign_account", "outside_range", "after_cutoff", "future_snapshot"])
def test_supplementary_original_read_is_validated(bad):
    original = purchase(at=START-timedelta(days=8))
    b = history_batch(original)
    code = {"foreign_account": "unexpected_account", "outside_range": "record_outside_range",
            "after_cutoff": "record_after_snapshot", "future_snapshot": "future_snapshot"}[bad]
    if bad == "foreign_account": b = replace(b, account_id="a2")
    elif bad == "outside_range": b = replace(b, start=original.occurred_at+timedelta(seconds=1), end=START)
    elif bad == "after_cutoff": b = replace(b, as_of=original.occurred_at-timedelta(seconds=1))
    else: b = replace(b, as_of=NOW+timedelta(seconds=1))
    with pytest.raises(FactsError, match="^"+code+"$"):
        snapshot([refund(original)], [b])


def test_detail_filter_uses_category_even_when_nature_is_transfer():
    transfer = LedgerRow("t", "a1", START, 700, "transfer", "transport", "outflow")
    s = snapshot([transfer])
    assert select_rows(s, "transport") == (transfer,)
    assert select_rows(s, "transfer") == ()
    assert (totals(s).gross, totals(s).transfer_out) == (0, 700)


def test_detail_filter_preserves_interest_category():
    interest = LedgerRow("i", "a1", START, 10, "interest", "transport", "inflow")
    s = snapshot([interest])
    assert select_rows(s, "transport") == (interest,)
    assert totals(s).gross == 0


def test_zero_categories_have_null_share_to_fit_public_model():
    result = totals(snapshot([purchase()]))
    assert all(r.share is None for r in result.categories if r.net <= 0 or r.category == "transfer")
    assert next(r for r in result.categories if r.category == "shopping").share_bps == 10000


def test_negative_category_hides_all_pie_shares_as_written_in_contract_5_3():
    original = purchase(at=START-timedelta(days=8))
    s = snapshot([purchase("meal", category="dining"), refund(original)], [history_batch(original)])
    assert totals(s).net == 30000
    assert all(r.share_bps is None for r in totals(s).categories)


@pytest.mark.parametrize("ratio,expected", [
    (None, None), (Fraction(1, 3), 3333), (Fraction(1, 20000), 1),
    (Fraction(-1, 20000), -1), (Fraction(7, 4), 17500),
    (Fraction(19999, 20000), 10000),
])
def test_final_bps_rounding_without_floats(ratio, expected):
    assert display_bps(ratio) == expected


@pytest.mark.parametrize("bad", [0.5, "1/2", 1, True])
def test_bps_requires_exact_ratio(bad):
    with pytest.raises(TypeError): display_bps(bad)


def test_individual_rounded_shares_need_not_sum_to_10000():
    rows = [purchase(str(i), category=c, amount=1) for i, c in enumerate(("dining", "transport", "medical"))]
    result = totals(snapshot(rows))
    assert sum(r.share_bps or 0 for r in result.categories) == 9999
    assert [r.category for r in result.categories][:3] == ["dining", "transport", "medical"]


def test_negative_comparison_bps_uses_final_rounding():
    delta = compare(snapshot([purchase(amount=19999)]), snapshot([purchase(amount=20000)]))
    assert delta.change_bps == -1
