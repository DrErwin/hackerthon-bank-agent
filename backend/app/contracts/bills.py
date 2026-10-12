"""Bills-facing models for the frozen L01 summary/details path (public contract §5.3)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .bank import Transaction
from .common import (
    Category, ContractModel, ID, Money, NonNegativeInt, PositiveInt, SignedMoney, Timestamp,
)

ShareBps = Annotated[int, Field(strict=True, ge=0, le=10000)]


class AccountSourceAsOf(ContractModel):
    """When the bank data of one account was read; never claimed as an atomic snapshot."""

    account_id: ID
    as_of: Timestamp


class BillScope(ContractModel):
    """Half-open range over the caller's own accounts; the bank clock decides RANGE_UNSUPPORTED."""

    account_ids: Annotated[list[ID], Field(min_length=1)]
    start_at: Timestamp
    end_at: Timestamp

    @model_validator(mode="after")
    def require_unique_accounts_and_a_half_open_range(self) -> "BillScope":
        if len(set(self.account_ids)) != len(self.account_ids):
            raise ValueError("bill scope accounts must not repeat")
        if self.start_at >= self.end_at:
            raise ValueError("bill scope is half-open and needs start_at < end_at")
        return self


class BillSummarizeInput(ContractModel):
    """L01 input; an omitted mode means summary, and each mode keeps its own option."""

    scope: BillScope
    mode: Literal["summary", "details"] = "summary"
    comparison_scope: BillScope | None = None
    category: Category | None = None

    @model_validator(mode="after")
    def match_options_to_mode(self) -> "BillSummarizeInput":
        if self.mode == "summary":
            if self.category is not None:
                raise ValueError("summary mode does not take a category filter")
            if self.comparison_scope is not None and (
                set(self.comparison_scope.account_ids) != set(self.scope.account_ids)
            ):
                raise ValueError("the comparison period reuses the account set of the scope")
        elif self.comparison_scope is not None:
            raise ValueError("details mode does not take a comparison scope")
        return self


def _require_net_equation(net: int, gross: int, refund: int, label: str) -> None:
    if net != gross - refund:
        raise ValueError(f"{label} net must equal gross minus refund")


def _require_complete_source(scope: BillScope, source_as_of: list[AccountSourceAsOf], as_of: Timestamp) -> None:
    """A summary or a details list may only claim completeness over the whole scope (§5.3)."""

    if sorted(item.account_id for item in source_as_of) != sorted(scope.account_ids):
        raise ValueError("source_as_of must cover exactly the accounts in scope")
    if as_of != min(item.as_of for item in source_as_of):
        raise ValueError("as_of must be the earliest account data time")


class CategoryTotal(ContractModel):
    category: Category
    outflow_fen: Money
    refund_fen: Money
    net_fen: SignedMoney
    share_bps: ShareBps | None
    rank: PositiveInt

    @model_validator(mode="after")
    def match_net_and_share_to_facts(self) -> "CategoryTotal":
        _require_net_equation(self.net_fen, self.outflow_fen, self.refund_fen, "category")
        if self.share_bps is not None and (self.category is Category.TRANSFER or self.net_fen <= 0):
            raise ValueError("share_bps stays empty for transfers and non-positive net amounts")
        return self


class SpendingComparison(ContractModel):
    scope: BillScope
    as_of: Timestamp
    consumption_net_fen: SignedMoney
    delta_fen: SignedMoney
    change_bps: Annotated[int, Field(strict=True)] | None
    largest_change_category: Category | None


class SpendingSummary(ContractModel):
    scope: BillScope
    as_of: Timestamp
    source_as_of: list[AccountSourceAsOf]
    transaction_count: NonNegativeInt
    consumption_gross_fen: Money
    consumption_refund_fen: Money
    consumption_net_fen: SignedMoney
    transfer_out_fen: Money
    transfer_in_fen: Money
    categories: list[CategoryTotal]
    comparison: SpendingComparison | None

    @model_validator(mode="after")
    def match_consumption_categories_and_source(self) -> "SpendingSummary":
        _require_net_equation(
            self.consumption_net_fen, self.consumption_gross_fen, self.consumption_refund_fen, "consumption",
        )
        ranks = [item.rank for item in self.categories]
        if len({item.category for item in self.categories}) != len(self.categories):
            raise ValueError("each category is totalled once")
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("categories are listed in rank order and ranked once each")
        _require_complete_source(self.scope, self.source_as_of, self.as_of)
        return self


class BillDetails(ContractModel):
    scope: BillScope
    category: Category | None
    transactions: list[Transaction]
    source_as_of: list[AccountSourceAsOf]
    as_of: Timestamp

    @model_validator(mode="after")
    def match_order_filter_and_source(self) -> "BillDetails":
        _require_complete_source(self.scope, self.source_as_of, self.as_of)
        keys = [(item.occurred_at, item.account_id, item.transaction_id) for item in self.transactions]
        if keys != sorted(keys):
            raise ValueError("details are ordered by occurred_at, account_id and transaction_id")
        if self.category is not None and any(item.category != self.category for item in self.transactions):
            raise ValueError("a category filter must match every returned transaction")
        return self


class BillReport(ContractModel):
    """L03 result and the controlled report an F21 card reads (§5.3); no raw detail list."""

    report_id: ID
    scope: BillScope
    summary: SpendingSummary
    spoken_summary: str
    monthly_average_fen: Money | None
    statistical_days: NonNegativeInt
    average_basis: str
    generated_at: Timestamp
