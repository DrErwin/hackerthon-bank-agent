"""Subscription / auto-debit models for scenario 05 (public contract §5.5 and §7A)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .bank import OperationResult
from .common import ContractModel, ID, Money, NonNegativeInt, OperationId, RequestId, Timestamp

SubscriptionSourceType = Literal["mandate", "suspected_ledger"]
SubscriptionCycle = Literal["monthly", "yearly"]
SubscriptionStatus = Literal["active", "cancelled", "suspected"]
SubscriptionScanStatus = Literal["evaluated", "insufficient_data"]

# The reminder window stays inside the contract's 1..90 days.
ReminderDays = Annotated[int, Field(strict=True, ge=1, le=90)]


class SubscriptionMandate(ContractModel):
    """One bank-recorded auto-debit agreement (bank fields §7A, B29)."""

    mandate_id: ID
    account_id: ID
    account_masked: str
    merchant_id: ID
    merchant_name: str
    service_name: str
    amount_fen: Money
    cycle: SubscriptionCycle
    next_billing_at: Timestamp | None
    last_billed_at: Timestamp | None
    status: Literal["active", "cancelled"]
    signed_at: Timestamp
    cancelled_at: Timestamp | None
    cancel_operation_id: OperationId | None

    @model_validator(mode="after")
    def match_cancellation_facts(self) -> "SubscriptionMandate":
        if (self.status == "cancelled") != (self.cancelled_at is not None):
            raise ValueError("only a cancelled mandate carries a cancellation time")
        if self.status == "cancelled" and self.next_billing_at is not None:
            raise ValueError("a cancelled mandate has no next billing time")
        return self


class SubscriptionMandateList(ContractModel):
    mandates: list[SubscriptionMandate]
    as_of: Timestamp

    @model_validator(mode="after")
    def require_unique_mandates(self) -> "SubscriptionMandateList":
        ids = [item.mandate_id for item in self.mandates]
        if len(set(ids)) != len(ids):
            raise ValueError("each mandate is listed once")
        return self


class SubscriptionCancelReceipt(ContractModel):
    """What B30 returns for one cancelled mandate; it never promises merchant perks."""

    mandate_id: ID
    account_id: ID
    account_masked: str
    merchant_id: ID
    merchant_name: str
    service_name: str
    amount_fen: Money
    cycle: SubscriptionCycle
    previous_next_billing_at: Timestamp
    effective_stop_at: Timestamp
    status: Literal["cancelled"] = "cancelled"
    cancelled_at: Timestamp

    @model_validator(mode="after")
    def stop_from_the_previous_next_billing(self) -> "SubscriptionCancelReceipt":
        # §7A: the agreement stops from the period that was next due.
        if self.effective_stop_at != self.previous_next_billing_at:
            raise ValueError("effective_stop_at is the previous next billing time")
        return self


class SubscriptionItem(ContractModel):
    """One displayable row: a bank mandate, or a flow-detected suspected debit series."""

    subscription_id: ID
    source_type: SubscriptionSourceType
    mandate_id: ID | None
    merchant_id: ID | None
    merchant_name: str
    service_name: str
    amount_fen: Money
    cycle: SubscriptionCycle
    account_id: ID
    account_masked: str
    last_billed_at: Timestamp | None
    next_billing_at: Timestamp | None
    status: SubscriptionStatus
    can_cancel_in_bank: bool
    days_until_renewal: Annotated[int, Field(strict=True)] | None
    is_upcoming_renewal: bool
    external_cancel_guide: str | None
    # Debit evidence gathered from B08 flows (public contract §5.5, 2026-10-19 addition).
    billed_count: NonNegativeInt = 0
    billed_total_fen: Money = 0
    channel: str | None = None

    @model_validator(mode="after")
    def match_source_status_and_evidence(self) -> "SubscriptionItem":
        if self.source_type == "mandate" and self.mandate_id is None:
            raise ValueError("a mandate row carries its mandate id")
        if self.source_type == "suspected_ledger" and self.mandate_id is not None:
            raise ValueError("a suspected series has no bank mandate")
        if self.source_type == "suspected_ledger" and self.status != "suspected":
            raise ValueError("a flow-only series is never a signed agreement state")
        if self.source_type == "mandate" and self.status == "suspected":
            raise ValueError("a signed mandate is never a flow-only clue")
        if self.can_cancel_in_bank and (self.source_type != "mandate" or self.status != "active"):
            raise ValueError("only an active bank mandate can be cancelled online")
        if self.is_upcoming_renewal and self.status != "active":
            raise ValueError("only an active mandate can be an upcoming renewal")
        if self.billed_count == 0 and self.billed_total_fen != 0:
            raise ValueError("a billed total requires at least one billed debit")
        return self


class SubscriptionListResult(ContractModel):
    items: list[SubscriptionItem]
    upcoming_renewals: list[SubscriptionItem]
    active_count: NonNegativeInt
    upcoming_total_fen: Money
    as_of: Timestamp
    # The rule-4 scan reports its own coverage instead of claiming "nothing found".
    suspected_scan_status: SubscriptionScanStatus = "evaluated"
    suspected_scan_reason: str | None = None

    @model_validator(mode="after")
    def match_summary_to_items(self) -> "SubscriptionListResult":
        ids = [item.subscription_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("each subscription is listed once")
        expected = [item.subscription_id for item in self.items if item.is_upcoming_renewal]
        if [item.subscription_id for item in self.upcoming_renewals] != expected:
            raise ValueError("upcoming_renewals must be the upcoming items in item order")
        if self.upcoming_total_fen != sum(item.amount_fen for item in self.upcoming_renewals):
            raise ValueError("upcoming_total_fen is the sum of the upcoming renewals")
        if self.active_count != len([item for item in self.items if item.status == "active"]):
            raise ValueError("active_count counts the active items")
        if self.suspected_scan_status == "insufficient_data" and self.suspected_scan_reason is None:
            raise ValueError("an insufficient scan states its reason")
        return self


class SubscriptionTaskView(ContractModel):
    """The module's displayable result (§5.5); the platform puts it in TaskView.data."""

    action: Literal["list", "cancel"]
    list_result: SubscriptionListResult | None = None
    selected_item: SubscriptionItem | None = None
    operation_id: OperationId | None = None
    operation: OperationResult[SubscriptionCancelReceipt] | None = None

    @model_validator(mode="after")
    def match_action_to_payload(self) -> "SubscriptionTaskView":
        if self.action == "list":
            if self.list_result is None:
                raise ValueError("a list task carries its list result")
            if self.operation is not None or self.operation_id is not None:
                raise ValueError("a list task performs no cancellation")
            return self
        if self.selected_item is None:
            raise ValueError("a cancel task names the target it acted on")
        if self.operation is not None and self.operation.operation_id != self.operation_id:
            raise ValueError("the operation result must match operation_id")
        return self


class SubscriptionListInput(ContractModel):
    """S01 logical input (§5.5); the platform envelope supplies request_id and text."""

    request_id: RequestId
    intent_text: str
    account_ids: list[ID] | None = None
    status_filter: SubscriptionStatus | Literal["all"] = "all"
    reminder_days: ReminderDays = 30

    @model_validator(mode="after")
    def require_unique_accounts(self) -> "SubscriptionListInput":
        if self.account_ids is not None:
            if not self.account_ids:
                raise ValueError("an explicit account list must not be empty")
            if len(set(self.account_ids)) != len(self.account_ids):
                raise ValueError("account_ids must not repeat")
        return self


class SubscriptionCancelInput(ContractModel):
    """S02 logical input (§5.5); an omitted target means the module must disambiguate."""

    request_id: RequestId
    intent_text: str
    subscription_id: ID | None = None
    merchant_hint: str | None = None
    account_id: ID | None = None

    @model_validator(mode="after")
    def require_usable_hint(self) -> "SubscriptionCancelInput":
        if self.merchant_hint is not None and not self.merchant_hint.strip():
            raise ValueError("merchant_hint must not be blank")
        return self
