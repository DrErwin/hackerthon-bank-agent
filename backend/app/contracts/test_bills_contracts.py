"""Frozen-contract examples and invalid inputs for the B08 flow query and the L01 bills path."""

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts import (
    BillDetails, BillScope, BillSummarizeInput, Category, CategoryTotal, QueryResult,
    SpendingComparison, SpendingSummary, Transaction, TransactionList,
)
from app.contracts import bank as bank_contracts
from app.contracts import bills as bills_contracts
from app.contracts.common import SignedMoney

START = "2026-09-01T00:00:00+08:00"
END = "2026-10-01T00:00:00+08:00"
BEFORE_START = "2026-08-01T00:00:00+08:00"
BEFORE_END = "2026-09-01T00:00:00+08:00"
AS_OF = "2026-10-01T00:00:00+08:00"
EARLIER = "2026-09-30T23:00:00+08:00"


def scope(**overrides):
    return {"account_ids": ["A1", "A5"], "start_at": START, "end_at": END} | overrides


def source_as_of(*pairs):
    return [{"account_id": account_id, "as_of": as_of} for account_id, as_of in pairs]


def transaction(**overrides):
    return {
        "transaction_id": "TX1", "account_id": "A1",
        "occurred_at": "2026-09-05T12:30:00+08:00", "amount_fen": 3200,
        "nature": "consumption", "category": "dining", "direction": "outflow",
        "counterparty_id": "M1", "counterparty_name": "楼下面馆",
        "counterparty_account_masked": None, "channel": "快捷支付",
        "summary": "午餐", "original_transaction_id": None, "original_occurred_at": None,
    } | overrides


def category_total(**overrides):
    return {
        "category": "dining", "outflow_fen": 50000, "refund_fen": 3000,
        "net_fen": 47000, "share_bps": 10000, "rank": 1,
    } | overrides


def summary(**overrides):
    return {
        "scope": scope(), "as_of": EARLIER,
        "source_as_of": source_as_of(("A1", AS_OF), ("A5", EARLIER)),
        "transaction_count": 12,
        "consumption_gross_fen": 50000, "consumption_refund_fen": 3000,
        "consumption_net_fen": 47000, "transfer_out_fen": 20000, "transfer_in_fen": 0,
        "categories": [category_total()], "comparison": None,
    } | overrides


def details(**overrides):
    return {
        "scope": scope(), "category": None, "transactions": [transaction()],
        "source_as_of": source_as_of(("A1", AS_OF), ("A5", EARLIER)), "as_of": EARLIER,
    } | overrides


def test_transaction_carries_bank_facts_without_guessing_unknowns():
    row = Transaction.model_validate(transaction())
    assert Transaction.model_validate_json(row.model_dump_json()) == row
    assert row.direction == "outflow" and row.amount_fen == 3200
    unknown = Transaction.model_validate(transaction(
        counterparty_id=None, counterparty_account_masked=None, channel=None,
    ))
    assert unknown.channel is None and unknown.counterparty_name == "楼下面馆"
    refund = Transaction.model_validate(transaction(
        transaction_id="TX9", nature="refund", direction="inflow",
        original_transaction_id="TX1", original_occurred_at="2026-09-05T12:30:00+08:00",
    ))
    assert refund.original_transaction_id == "TX1"


@pytest.mark.parametrize("broken", [
    {"nature": "refund"},
    {"nature": "refund", "original_transaction_id": "TX1"},
    {"nature": "refund", "original_occurred_at": "2026-09-05T12:30:00+08:00"},
    {"original_transaction_id": "TX1", "original_occurred_at": "2026-09-05T12:30:00+08:00"},
    {"nature": "payment"},
    {"category": "food"},
    {"direction": "in"},
    {"amount_fen": -1},
    {"amount_fen": "3200"},
    {"transaction_id": ""},
    {"occurred_at": "2026-09-05T12:30:00"},
    {"channel": 1},
    {"unexpected_fact": True},
])
def test_transaction_rejects_broken_facts_and_refund_origin(broken):
    with pytest.raises(ValidationError):
        Transaction.model_validate(transaction() | broken)


def test_transaction_list_separates_empty_success_from_query_failure():
    adapter = TypeAdapter(QueryResult[TransactionList])
    empty = adapter.validate_python({"kind": "ok", "data": {"transactions": [], "as_of": AS_OF}})
    assert empty.data.transactions == []
    assert adapter.validate_json(adapter.dump_json(empty)) == empty
    failure = adapter.validate_python({
        "kind": "error", "error": {"code": "RANGE_UNSUPPORTED", "details": {}},
    })
    assert failure.kind == "error" and failure.error.code == "RANGE_UNSUPPORTED"
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "ok", "data": None})


@pytest.mark.parametrize("broken", [
    {"account_ids": []},
    {"account_ids": ["A1", "A1"]},
    {"account_ids": ["A1", ""]},
    {"start_at": END, "end_at": END},
    {"start_at": "2026-10-01T00:00:00+08:00", "end_at": START},
    {"start_at": "2026-09-01T00:00:00", "end_at": END},
])
def test_bill_scope_requires_unique_accounts_and_a_half_open_range(broken):
    with pytest.raises(ValidationError):
        BillScope.model_validate(scope() | broken)
    with pytest.raises(ValidationError):
        BillScope.model_validate({"account_ids": ["A1"], "start_at": START})


def test_bill_scope_leaves_the_24_month_bank_rule_to_the_bank_clock():
    old = BillScope.model_validate(scope(start_at="2000-01-01T00:00:00+08:00", end_at="2001-01-01T00:00:00+08:00"))
    assert str(old.start_at).startswith("2000")
    valid = BillScope.model_validate(scope())
    assert BillScope.model_validate_json(valid.model_dump_json()) == valid


def test_summarize_input_defaults_to_summary_and_keeps_mode_options_apart():
    default = BillSummarizeInput.model_validate({"scope": scope()})
    assert default.mode == "summary" and default.comparison_scope is None and default.category is None
    comparison_scope = scope(start_at=BEFORE_START, end_at=BEFORE_END)
    with_comparison = BillSummarizeInput.model_validate(
        {"scope": scope(), "mode": "summary", "comparison_scope": comparison_scope}
    )
    assert with_comparison.comparison_scope == BillScope.model_validate(comparison_scope)
    with_details = BillSummarizeInput.model_validate(
        {"scope": scope(), "mode": "details", "category": "dining"}
    )
    assert with_details.category is Category.DINING
    assert BillSummarizeInput.model_validate(
        {"scope": scope(), "mode": "details"}
    ).category is None
    for broken in (
        {"scope": scope(), "mode": "report"},
        {"scope": scope(), "category": "dining"},
        {"scope": scope(), "mode": "summary", "category": "dining"},
        {"scope": scope(), "mode": "details", "comparison_scope": comparison_scope},
        {"scope": scope(), "mode": "details", "category": "餐饮"},
        {"scope": scope(), "mode": "summary", "unexpected_option": 1},
    ):
        with pytest.raises(ValidationError):
            BillSummarizeInput.model_validate(broken)


def test_spending_summary_equals_gross_minus_refund_and_covers_each_account():
    model = SpendingSummary.model_validate(summary())
    assert SpendingSummary.model_validate_json(model.model_dump_json()) == model
    assert model.as_of == model.source_as_of[1].as_of
    negative = SpendingSummary.model_validate(summary(
        consumption_gross_fen=0, consumption_refund_fen=3000, consumption_net_fen=-3000,
    ))
    assert negative.consumption_net_fen == -3000
    for broken in (
        {"consumption_net_fen": 50000},
        {"consumption_net_fen": "47000"},
        {"as_of": AS_OF},
        {"source_as_of": source_as_of(("A1", AS_OF))},
        {"source_as_of": source_as_of(("A1", AS_OF), ("A5", EARLIER), ("A9", EARLIER))},
        {"source_as_of": source_as_of(("A1", AS_OF), ("A5", EARLIER), ("A5", EARLIER))},
        {"transaction_count": -1},
        {"transaction_count": True},
    ):
        with pytest.raises(ValidationError):
            SpendingSummary.model_validate(summary() | broken)


def test_category_total_keeps_the_signed_equation_and_share_bounds():
    assert CategoryTotal.model_validate(category_total(net_fen=-300, outflow_fen=0, refund_fen=300)).net_fen == -300
    assert CategoryTotal.model_validate(category_total(share_bps=None, category="transfer")).share_bps is None
    for broken in (
        {"net_fen": 50000},
        {"share_bps": 10001},
        {"share_bps": -1},
        {"share_bps": "10000"},
        {"rank": 0},
        {"category": "餐饮"},
        {"category": "interest"},
    ):
        with pytest.raises(ValidationError):
            CategoryTotal.model_validate(category_total() | broken)


def test_spending_comparison_allows_signed_delta_and_missing_percentage():
    comparison = SpendingComparison.model_validate({
        "scope": scope(start_at=BEFORE_START, end_at=BEFORE_END), "as_of": AS_OF,
        "consumption_net_fen": 47000, "delta_fen": -3000, "change_bps": None,
        "largest_change_category": "dining",
    })
    assert comparison.delta_fen == -3000 and comparison.change_bps is None
    assert SpendingComparison.model_validate({
        "scope": scope(), "as_of": AS_OF, "consumption_net_fen": 47000,
        "delta_fen": 3000, "change_bps": 682, "largest_change_category": None,
    }).change_bps == 682
    for broken in (
        {"change_bps": "682"},
        {"largest_change_category": "餐饮"},
        {"delta_fen": "3000"},
    ):
        with pytest.raises(ValidationError):
            SpendingComparison.model_validate({
                "scope": scope(), "as_of": AS_OF, "consumption_net_fen": 47000,
                "delta_fen": 3000, "change_bps": 682, "largest_change_category": None,
            } | broken)


def test_bill_details_orders_rows_and_honours_the_category_filter():
    first = transaction(transaction_id="TX1", occurred_at="2026-09-05T09:00:00+08:00")
    second = transaction(transaction_id="TX2", occurred_at="2026-09-05T10:00:00+08:00")
    assert len(BillDetails.model_validate(details(transactions=[first, second])).transactions) == 2
    same_time = transaction(transaction_id="TX2", account_id="A5", occurred_at=first["occurred_at"])
    assert BillDetails.model_validate(details(transactions=[first, same_time])).transactions[1].account_id == "A5"
    for broken in (
        {"transactions": [second, first]},
        {"transactions": [same_time, first]},
        {"transactions": [dict(first, transaction_id="TX2"), first]},
        {"category": "transport"},
        {"as_of": AS_OF},
        {"source_as_of": source_as_of(("A1", AS_OF))},
    ):
        with pytest.raises(ValidationError):
            BillDetails.model_validate(details() | broken)
    transport = transaction(transaction_id="TX3", category="transport", nature="transfer", direction="outflow")
    filtered = BillDetails.model_validate(details(category="transport", transactions=[transport]))
    assert filtered.category is Category.TRANSPORT


def test_public_import_paths_and_signed_money_are_available():
    assert bank_contracts.Transaction is Transaction
    assert bank_contracts.TransactionList is TransactionList
    assert bills_contracts.BillScope is BillScope
    assert bills_contracts.SpendingSummary is SpendingSummary
    assert bills_contracts.BillDetails is BillDetails
    adapter = TypeAdapter(SignedMoney)
    assert adapter.validate_python(-3000) == -3000 and adapter.validate_python(0) == 0
    with pytest.raises(ValidationError):
        adapter.validate_python("-3000")
