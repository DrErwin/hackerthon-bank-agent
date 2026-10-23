"""Bank-facing facts for the ordinary-transfer path and the read-only queries (B01—B08)."""

from __future__ import annotations

from typing import Annotated, Generic, Literal, TypeVar

from pydantic import Field, JsonValue, model_validator
from typing_extensions import TypeAliasType

from .common import (
    Category, ContractModel, ID, Money, OperationId, OperationStatus, PositiveInt, PositiveMoney, Timestamp,
)


class OwnPayee(ContractModel):
    kind: Literal["own"]
    account_id: ID


class SavedPayee(ContractModel):
    kind: Literal["saved"]
    payee_id: ID


class ManualPayee(ContractModel):
    kind: Literal["manual"]
    account_number: str
    account_name: str


PayeeInput = Annotated[OwnPayee | SavedPayee | ManualPayee, Field(discriminator="kind")]


class PayeeDisplay(ContractModel):
    payee_id: ID | None
    name_masked: str
    account_masked: str
    remark: str | None
    bank_name: str


class PayeeCandidate(PayeeDisplay):
    last_transfer_at: Timestamp | None


class PayeeList(ContractModel):
    payees: list[PayeeCandidate]


class PayeeVerification(ContractModel):
    matched: bool
    payee: PayeeDisplay | None

    @model_validator(mode="after")
    def match_payee_to_result(self) -> "PayeeVerification":
        if self.matched != (self.payee is not None):
            raise ValueError("matched payee requires a display result")
        return self


class BankError(ContractModel):
    code: ID
    details: dict[str, JsonValue]


T = TypeVar("T")


class QueryOk(ContractModel, Generic[T]):
    kind: Literal["ok"]
    data: T


class QueryFailure(ContractModel):
    kind: Literal["error"]
    error: BankError


QueryResult = TypeAliasType(
    "QueryResult", Annotated[QueryOk[T] | QueryFailure, Field(discriminator="kind")], type_params=(T,),
)


class OperationResult(ContractModel, Generic[T]):
    operation_id: OperationId
    operation_type: ID
    operation_status: OperationStatus
    recorded_at: Timestamp
    updated_at: Timestamp
    receipt: T | None
    failure: BankError | None

    @model_validator(mode="after")
    def match_status_to_result(self) -> "OperationResult[T]":
        if self.operation_status == OperationStatus.SUCCEEDED and (self.receipt is None or self.failure is not None):
            raise ValueError("successful operation requires receipt and no failure")
        if self.operation_status == OperationStatus.FAILED and (self.failure is None or self.receipt is not None):
            raise ValueError("failed operation requires failure and no receipt")
        if self.operation_status == OperationStatus.PROCESSING and (self.receipt is not None or self.failure is not None):
            raise ValueError("processing operation has no final receipt or failure")
        return self


class OperationFound(ContractModel, Generic[T]):
    lookup: Literal["found"]
    operation: OperationResult[T]


class OperationNotFound(ContractModel):
    lookup: Literal["not_found"]
    operation: None


OperationLookup = TypeAliasType(
    "OperationLookup", Annotated[OperationFound[T] | OperationNotFound, Field(discriminator="lookup")], type_params=(T,),
)
BankWriteResponse = TypeAliasType("BankWriteResponse", OperationResult[T] | QueryFailure, type_params=(T,))


class AccountSummary(ContractModel):
    account_id: ID
    account_type: Literal["class_i", "class_ii", "class_iii"]
    account_masked: str
    available_balance_fen: Money
    display_name: str
    bank_name: str


class AccountList(ContractModel):
    accounts: list[AccountSummary]


class AccountDetail(AccountSummary):
    account_status: Literal["active", "frozen", "closed"]
    book_balance_fen: Money
    frozen_balance_fen: Money
    as_of: Timestamp


class BalanceSnapshot(ContractModel):
    account_id: ID
    book_balance_fen: Money
    frozen_balance_fen: Money
    available_balance_fen: Money
    as_of: Timestamp


class TransferLimits(ContractModel):
    single_limit_fen: Money
    daily_remaining_fen: Money
    annual_remaining_fen: Money | None
    as_of: Timestamp


class TransferQuote(ContractModel):
    fee_fen: Literal[0]
    arrival_mode: Literal["instant"]


class TransferPrecheck(TransferQuote):
    can_proceed: bool
    failure: BankError | None
    checked_at: Timestamp

    @model_validator(mode="after")
    def match_failure_to_decision(self) -> "TransferPrecheck":
        if self.can_proceed == (self.failure is not None):
            raise ValueError("failure is required exactly when precheck cannot proceed")
        return self


class TransferReceipt(ContractModel):
    transaction_id: ID
    payer_account_id: ID
    payee: PayeeDisplay
    amount_fen: PositiveMoney
    fee_fen: Literal[0]
    arrival_mode: Literal["instant"]
    completed_at: Timestamp
    balance: BalanceSnapshot


class Transaction(ContractModel):
    """One bank-recorded flow row as B08 returns it (bank fields §3)."""

    transaction_id: ID
    account_id: ID
    occurred_at: Timestamp
    amount_fen: Money
    nature: Literal["consumption", "transfer", "refund", "interest"]
    category: Category
    direction: Literal["inflow", "outflow"]
    counterparty_id: ID | None
    counterparty_name: str
    counterparty_account_masked: str | None
    channel: str | None
    summary: str
    original_transaction_id: ID | None
    original_occurred_at: Timestamp | None

    @model_validator(mode="after")
    def match_refund_to_its_original(self) -> "Transaction":
        if self.nature == "refund" and (
            self.original_transaction_id is None or self.original_occurred_at is None
        ):
            raise ValueError("a refund carries the original transaction id and time")
        return self


class TransactionList(ContractModel):
    transactions: list[Transaction]
    as_of: Timestamp


# --- Freeze, capture and release (B10—B13, bank fields §4) ---


class FreezeFundsInput(ContractModel):
    account_id: ID
    amount_fen: PositiveMoney
    reason: str


class FreezeReceipt(ContractModel):
    freeze_id: ID
    frozen_amount_fen: PositiveMoney
    remaining_fen: Money
    balance: BalanceSnapshot


class CaptureFrozenInput(ContractModel):
    freeze_id: ID
    amount_fen: PositiveMoney
    merchant_id: ID
    merchant_name: str
    purpose: str
    category: Category
    order_id: ID | None = None


class CaptureReceipt(ContractModel):
    transaction_id: ID
    freeze_id: ID
    captured_amount_fen: PositiveMoney
    remaining_fen: Money
    balance: BalanceSnapshot


class ReleaseFrozenInput(ContractModel):
    freeze_id: ID
    amount_fen: PositiveMoney


class ReleaseReceipt(ContractModel):
    freeze_id: ID
    released_amount_fen: PositiveMoney
    remaining_fen: Money
    balance: BalanceSnapshot


class GetFreezeInput(ContractModel):
    freeze_id: ID


class FreezeView(ContractModel):
    freeze_id: ID
    account_id: ID
    original_amount_fen: PositiveMoney
    captured_total_fen: Money
    released_total_fen: Money
    remaining_fen: Money
    as_of: Timestamp

    @model_validator(mode="after")
    def match_amounts(self) -> "FreezeView":
        if self.original_amount_fen != self.captured_total_fen + self.released_total_fen + self.remaining_fen:
            raise ValueError("original_amount_fen must equal captured plus released plus remaining")
        return self


# --- Products and orders (B20—B22, bank fields §6) ---


class ListProductsInput(ContractModel):
    merchant_id: ID | None = None
    purpose: str | None = None
    deliver_by: Timestamp | None = None


class Product(ContractModel):
    product_id: ID
    merchant_id: ID
    merchant_name: str
    product_name: str
    unit_price_fen: Money
    category: Category
    earliest_delivery_at: Timestamp


class ProductList(ContractModel):
    products: list[Product]


class DeliveryInput(ContractModel):
    """Controlled-bank-path delivery facts; repr hides the raw text from logs and debugging."""

    recipient_name: str = Field(repr=False)
    phone: str = Field(repr=False)
    address: str = Field(repr=False)
    deliver_by: Timestamp


class CreateOrderInput(ContractModel):
    product_id: ID
    quantity: PositiveInt
    expected_total_fen: Money
    delivery: DeliveryInput


class OrderView(ContractModel):
    order_id: ID
    product_id: ID
    quantity: PositiveInt
    merchant_id: ID
    merchant_name: str
    total_fen: Money
    created_at: Timestamp
    deliver_by: Timestamp
    recipient_name_masked: str
    phone_masked: str
    address_masked: str
    payment_status: Literal["unpaid", "paid"]
    payment_transaction_id: ID | None

    @model_validator(mode="after")
    def match_payment_link(self) -> "OrderView":
        if self.payment_status == "paid" and self.payment_transaction_id is None:
            raise ValueError("a paid order carries its payment transaction id")
        if self.payment_status == "unpaid" and self.payment_transaction_id is not None:
            raise ValueError("an unpaid order has no payment transaction id")
        return self


class OrderResult(ContractModel):
    order: OrderView


class GetOrderInput(ContractModel):
    order_id: ID
