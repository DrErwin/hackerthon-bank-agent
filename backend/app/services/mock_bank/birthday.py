"""Birthday bank capabilities B10—B13 and B20—B22 (bank fields §4/§6).

Rules stay here: the store only commits decided effects atomically. The fixed
catalog is the mock fact base — no inventory or logistics engine (§6).
"""

from __future__ import annotations

from contextlib import closing
from datetime import timedelta
import threading
import time
from uuid import UUID, uuid4

from app.contracts.bank import (
    BalanceSnapshot, BankError, CaptureReceipt, FreezeReceipt, FreezeView, OperationResult,
    OrderResult, OrderView, Product, ProductList, QueryFailure, QueryOk, ReleaseReceipt,
)
from app.contracts.common import Category, OperationStatus
from app.contracts.platform import TrustedContext
from app.storage.database import connect, parameter_digest, transaction
from app.storage.mock_bank.repository import (
    FreezeCapture, FreezeOpening, FreezeRelease, MockBankStore, OrderCreation,
)


def _error(code: str, **details) -> QueryFailure:
    return QueryFailure(kind="error", error=BankError(code=code, details=details))


# Fixed price list; earliest_delivery_at is the bank clock plus each lead time.
PRODUCT_CATALOG = (
    {"product_id": "p_flower", "merchant_id": "m_flower", "merchant_name": "邻里花店",
     "product_name": "鲜花礼盒", "unit_price_fen": 19900, "category": Category.SHOPPING,
     "lead": timedelta(hours=24)},
    {"product_id": "p_cake", "merchant_id": "m_cake", "merchant_name": "西点蛋糕房",
     "product_name": "生日蛋糕", "unit_price_fen": 26800, "category": Category.SHOPPING,
     "lead": timedelta(hours=48)},
)

# B14 needs each write action's receipt type to rebuild the typed lookup.
BIRTHDAY_RECEIPTS = {
    "bank.freeze_funds": FreezeReceipt,
    "bank.capture_frozen": CaptureReceipt,
    "bank.release_frozen": ReleaseReceipt,
    "bank.create_order": OrderResult,
}


def _mask_name(name: str) -> str:
    return (name[:1] + "*") if name else "*"


def _mask_phone(phone: str) -> str:
    return "****" + phone[-4:] if len(phone) >= 4 else "****"


def _mask_address(address: str) -> str:
    return (address[:2] + "****") if len(address) >= 2 else "****"


class MockBirthdayBank:
    """Freeze → order → capture → release over the atomic store seams."""

    def __init__(self, store: MockBankStore, *, clock, slow_seconds: float = 6.0):
        self.store = store
        self.clock = clock
        self.slow_seconds = slow_seconds
        self._response_loss: set[str] = set()
        self._fault_lock = threading.Lock()

    # --- demo-only isolated fault (B28 wiring lands with ticket 09) ---

    def arm_response_loss(self, user_id: str) -> None:
        """Next write commits in the bank but loses its response to the caller."""
        with self._fault_lock:
            self._response_loss.add(user_id)

    def _after_write(self, user_id: str, result):
        with self._fault_lock:
            if user_id in self._response_loss:
                self._response_loss.discard(user_id)
                time.sleep(self.slow_seconds)
        return result

    # --- shared write plumbing ---

    def _prepare(self, context: TrustedContext, operation_id: UUID):
        if operation_id.version != 4:
            return _error("INVALID_ARGUMENT", field="operation_id", reason="UUID v4 required")
        if not self._reserve_scope(context, operation_id):
            return _error("OPERATION_CONFLICT")
        return None

    def _reserve_scope(self, context: TrustedContext, operation_id: UUID) -> bool:
        with transaction(self.store.path) as connection:
            row = connection.execute(
                "SELECT user_id, demo_round_id FROM bank_operation_scopes WHERE operation_id = ?",
                (str(operation_id),),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO bank_operation_scopes VALUES (?, ?, ?)",
                    (str(operation_id), context.user_id, context.demo_round_id),
                )
                return True
            return (row["user_id"], row["demo_round_id"]) == (
                context.user_id, context.demo_round_id,
            )

    def _stored(self, user_id: str, operation_id: UUID, action: str, parameters: dict):
        with closing(connect(self.store.path)) as connection:
            row = connection.execute(
                "SELECT user_id FROM bank_operations WHERE operation_id = ?", (str(operation_id),),
            ).fetchone()
        if row is None:
            return None
        if row["user_id"] != user_id:
            return _error("OPERATION_CONFLICT")
        operation = self.store.get_operation(user_id, str(operation_id))
        if operation.action_name != action or operation.parameters_digest != parameter_digest(parameters):
            return _error("OPERATION_CONFLICT")
        return OperationResult[BIRTHDAY_RECEIPTS[action]].model_validate(operation.result)

    @staticmethod
    def _operation_result(operation_id: UUID, action: str, status, at, receipt=None, failure=None):
        return OperationResult(
            operation_id=operation_id, operation_type=action,
            operation_status=status, recorded_at=at, updated_at=at,
            receipt=receipt, failure=failure,
        )

    def _require_active_account(self, user_id: str, account_id: str):
        account = self.store.get_account(user_id, account_id)
        if account is None:
            return None, _error("ACCESS_DENIED")
        if account.account_status != "active":
            return None, _error("ACCOUNT_UNAVAILABLE", account_status=account.account_status)
        return account, None

    @staticmethod
    def _snapshot(account_id: str, book: int, frozen: int, at) -> BalanceSnapshot:
        return BalanceSnapshot(
            account_id=account_id, book_balance_fen=book, frozen_balance_fen=frozen,
            available_balance_fen=book - frozen, as_of=at,
        )

    def _product(self, product_id: str):
        return next((item for item in PRODUCT_CATALOG if item["product_id"] == product_id), None)

    # --- B10 freeze ---

    def freeze_funds(self, context: TrustedContext, operation_id: UUID,
                     account_id: str, amount_fen: int, reason: str):
        rejected = self._prepare(context, operation_id)
        if rejected is not None:
            return rejected
        parameters = {"account_id": account_id, "amount_fen": amount_fen, "reason": reason}
        action = "bank.freeze_funds"
        prior = self._stored(context.user_id, operation_id, action, parameters)
        if prior is not None:
            return prior
        account, failure = self._require_active_account(context.user_id, account_id)
        at = self.clock()
        if failure is not None:
            return self._store_failure(context, operation_id, action, parameters, failure, at)
        available = account.book_balance_fen - account.frozen_balance_fen
        if amount_fen > available:
            return self._store_failure(context, operation_id, action, parameters, _error(
                "INSUFFICIENT_FUNDS", available_fen=available, required_fen=amount_fen,
                shortfall_fen=amount_fen - available,
            ), at)
        freeze_id = "frz_" + operation_id.hex[:16]
        book, frozen = account.book_balance_fen, account.frozen_balance_fen + amount_fen
        receipt = FreezeReceipt(
            freeze_id=freeze_id, frozen_amount_fen=amount_fen, remaining_fen=amount_fen,
            balance=self._snapshot(account_id, book, frozen, at),
        )
        result = self._operation_result(operation_id, action, OperationStatus.SUCCEEDED, at, receipt=receipt)
        self.store.commit_operation(
            context.user_id, str(operation_id), action, parameters,
            OperationStatus.SUCCEEDED.value, result.model_dump(mode="json"), at.isoformat(),
            [(account_id, account.version, book, frozen)], [],
            (FreezeOpening(freeze_id, account_id, amount_fen),),
            demo_round_id=context.demo_round_id,
        )
        return self._after_write(context.user_id, result)

    def _store_failure(self, context: TrustedContext, operation_id: UUID, action: str,
                       parameters: dict, failure: QueryFailure, at):
        result = self._operation_result(
            operation_id, action, OperationStatus.FAILED, at, failure=failure.error,
        )
        self.store.commit_operation(
            context.user_id, str(operation_id), action, parameters,
            OperationStatus.FAILED.value, result.model_dump(mode="json"), at.isoformat(), [], [],
        )
        return result

    # --- B11 capture / B12 release ---

    def _freeze_row(self, context: TrustedContext, freeze_id: str):
        row = self.store.get_freeze(context.user_id, freeze_id)
        if row is None:
            return None, _error("RECORD_NOT_FOUND")
        if row["demo_round_id"] != context.demo_round_id:
            return None, _error("ACCESS_DENIED")
        remaining = (row["original_amount_fen"] - row["captured_total_fen"]
                     - row["released_total_fen"])
        return (row, remaining), None

    def capture_frozen(self, context: TrustedContext, operation_id: UUID, freeze_id: str,
                       amount_fen: int, merchant_id: str, merchant_name: str, purpose: str,
                       category: Category, order_id: str | None):
        rejected = self._prepare(context, operation_id)
        if rejected is not None:
            return rejected
        parameters = {"freeze_id": freeze_id, "amount_fen": amount_fen, "merchant_id": merchant_id,
                      "merchant_name": merchant_name, "purpose": purpose,
                      "category": category.value, "order_id": order_id}
        action = "bank.capture_frozen"
        prior = self._stored(context.user_id, operation_id, action, parameters)
        if prior is not None:
            return prior
        found, failure = self._freeze_row(context, freeze_id)
        at = self.clock()
        if failure is not None:
            return self._store_failure(context, operation_id, action, parameters, failure, at)
        row, remaining = found
        if amount_fen > remaining:
            return self._store_failure(context, operation_id, action, parameters, _error(
                "FREEZE_INSUFFICIENT", remaining_fen=remaining, requested_fen=amount_fen,
            ), at)
        order = None
        if order_id is not None:
            order = self.store.get_order(context.user_id, order_id)
            if order is None:
                return self._store_failure(context, operation_id, action, parameters,
                                           _error("RECORD_NOT_FOUND"), at)
            if order["demo_round_id"] != context.demo_round_id:
                return self._store_failure(context, operation_id, action, parameters,
                                           _error("ACCESS_DENIED"), at)
            product = self._product(order["product_id"])
            # Amount, merchant and category must match the bank's own order facts.
            if (amount_fen != order["total_fen"] or merchant_id != order["merchant_id"]
                    or product is None or category != product["category"]
                    or order["payment_status"] != "unpaid"):
                return self._store_failure(context, operation_id, action, parameters, _error(
                    "ORDER_PAYMENT_MISMATCH", reason="amount_or_merchant_or_category_or_state",
                ), at)
        account, failure = self._require_active_account(context.user_id, row["account_id"])
        if failure is not None:
            return self._store_failure(context, operation_id, action, parameters, failure, at)
        transaction_id = "tx_" + uuid4().hex[:16]
        book = account.book_balance_fen - amount_fen
        frozen = account.frozen_balance_fen - amount_fen
        receipt = CaptureReceipt(
            transaction_id=transaction_id, freeze_id=freeze_id,
            captured_amount_fen=amount_fen, remaining_fen=remaining - amount_fen,
            balance=self._snapshot(row["account_id"], book, frozen, at),
        )
        result = self._operation_result(operation_id, action, OperationStatus.SUCCEEDED, at, receipt=receipt)
        self.store.commit_operation(
            context.user_id, str(operation_id), action, parameters,
            OperationStatus.SUCCEEDED.value, result.model_dump(mode="json"), at.isoformat(),
            [(row["account_id"], account.version, book, frozen)],
            [(transaction_id, row["account_id"], amount_fen, "outflow", "consumption",
              category.value, at.isoformat())],
            (FreezeCapture(
                freeze_id=freeze_id, amount_fen=amount_fen, transaction_id=transaction_id,
                order_id=order_id, paid_at=at.isoformat(), counterparty_id=merchant_id,
                counterparty_name=merchant_name, summary=purpose,
            ),),
            demo_round_id=context.demo_round_id,
        )
        return self._after_write(context.user_id, result)

    def release_frozen(self, context: TrustedContext, operation_id: UUID,
                       freeze_id: str, amount_fen: int):
        rejected = self._prepare(context, operation_id)
        if rejected is not None:
            return rejected
        parameters = {"freeze_id": freeze_id, "amount_fen": amount_fen}
        action = "bank.release_frozen"
        prior = self._stored(context.user_id, operation_id, action, parameters)
        if prior is not None:
            return prior
        found, failure = self._freeze_row(context, freeze_id)
        at = self.clock()
        if failure is not None:
            return self._store_failure(context, operation_id, action, parameters, failure, at)
        row, remaining = found
        if amount_fen > remaining:
            return self._store_failure(context, operation_id, action, parameters, _error(
                "FREEZE_INSUFFICIENT", remaining_fen=remaining, requested_fen=amount_fen,
            ), at)
        account, failure = self._require_active_account(context.user_id, row["account_id"])
        if failure is not None:
            return self._store_failure(context, operation_id, action, parameters, failure, at)
        # A release returns frozen funds; it is neither consumption nor income.
        book = account.book_balance_fen
        frozen = account.frozen_balance_fen - amount_fen
        receipt = ReleaseReceipt(
            freeze_id=freeze_id, released_amount_fen=amount_fen,
            remaining_fen=remaining - amount_fen,
            balance=self._snapshot(row["account_id"], book, frozen, at),
        )
        result = self._operation_result(operation_id, action, OperationStatus.SUCCEEDED, at, receipt=receipt)
        self.store.commit_operation(
            context.user_id, str(operation_id), action, parameters,
            OperationStatus.SUCCEEDED.value, result.model_dump(mode="json"), at.isoformat(),
            [(row["account_id"], account.version, book, frozen)], [],
            (FreezeRelease(freeze_id, amount_fen),),
            demo_round_id=context.demo_round_id,
        )
        return self._after_write(context.user_id, result)

    # --- B13 / B20 / B21 / B22 ---

    def get_freeze(self, user_id: str, freeze_id: str, demo_round_id: str | None = None):
        """demo_round_id is required by the gateway; None is only the test seam."""
        row = self.store.get_freeze(user_id, freeze_id)
        if row is None:
            return _error("RECORD_NOT_FOUND")
        if demo_round_id is not None and row["demo_round_id"] != demo_round_id:
            return _error("ACCESS_DENIED")
        return QueryOk(kind="ok", data=FreezeView(
            freeze_id=row["freeze_id"], account_id=row["account_id"],
            original_amount_fen=row["original_amount_fen"],
            captured_total_fen=row["captured_total_fen"],
            released_total_fen=row["released_total_fen"],
            remaining_fen=row["original_amount_fen"] - row["captured_total_fen"]
            - row["released_total_fen"],
            as_of=self.clock(),
        ))

    def list_products(self, merchant_id: str | None = None, purpose: str | None = None,
                      deliver_by=None) -> ProductList:
        at = self.clock()
        products = []
        for item in PRODUCT_CATALOG:
            if merchant_id is not None and item["merchant_id"] != merchant_id:
                continue
            earliest = at + item["lead"]
            if deliver_by is not None and deliver_by < earliest:
                continue
            products.append(Product(
                product_id=item["product_id"], merchant_id=item["merchant_id"],
                merchant_name=item["merchant_name"], product_name=item["product_name"],
                unit_price_fen=item["unit_price_fen"], category=item["category"],
                earliest_delivery_at=earliest,
            ))
        return ProductList(products=products)

    def create_order(self, context: TrustedContext, operation_id: UUID, product_id: str,
                     quantity: int, expected_total_fen: int, delivery) :
        rejected = self._prepare(context, operation_id)
        if rejected is not None:
            return rejected
        # The digest covers the raw delivery facts too: the same operation number
        # with a different address is a conflict, never a silent replay (§2).
        parameters = {"product_id": product_id, "quantity": quantity,
                      "expected_total_fen": expected_total_fen,
                      "deliver_by": delivery.deliver_by.isoformat(),
                      "delivery": {"recipient_name": delivery.recipient_name,
                                   "phone": delivery.phone, "address": delivery.address}}
        action = "bank.create_order"
        prior = self._stored(context.user_id, operation_id, action, parameters)
        if prior is not None:
            return prior
        at = self.clock()
        item = self._product(product_id)
        if item is None or quantity <= 0:
            return self._store_failure(context, operation_id, action, parameters, _error(
                "PRODUCT_UNAVAILABLE", product_id=product_id), at)
        actual_total = item["unit_price_fen"] * quantity
        if actual_total != expected_total_fen:
            return self._store_failure(context, operation_id, action, parameters, _error(
                "PRICE_CHANGED", expected_total_fen=expected_total_fen,
                actual_total_fen=actual_total), at)
        if delivery.deliver_by < at + item["lead"]:
            return self._store_failure(context, operation_id, action, parameters, _error(
                "DELIVERY_UNAVAILABLE",
                earliest_delivery_at=(at + item["lead"]).isoformat()), at)
        order_id = "ord_" + operation_id.hex[:16]
        order = OrderView(
            order_id=order_id, product_id=product_id, quantity=quantity,
            merchant_id=item["merchant_id"], merchant_name=item["merchant_name"],
            total_fen=actual_total, created_at=at, deliver_by=delivery.deliver_by,
            recipient_name_masked=_mask_name(delivery.recipient_name),
            phone_masked=_mask_phone(delivery.phone),
            address_masked=_mask_address(delivery.address),
            payment_status="unpaid", payment_transaction_id=None,
        )
        result = self._operation_result(
            operation_id, action, OperationStatus.SUCCEEDED, at,
            receipt=OrderResult(order=order),
        )
        self.store.commit_operation(
            context.user_id, str(operation_id), action, parameters,
            OperationStatus.SUCCEEDED.value, result.model_dump(mode="json"), at.isoformat(),
            [], [],
            (OrderCreation(order_id=order_id, product_id=product_id, quantity=quantity,
                           merchant_id=item["merchant_id"],
                           merchant_name=item["merchant_name"], total_fen=actual_total,
                           created_at=at.isoformat(),
                           deliver_by=delivery.deliver_by.isoformat(),
                           recipient_name_masked=order.recipient_name_masked,
                           phone_masked=order.phone_masked,
                           address_masked=order.address_masked,
                           expected_total_fen=expected_total_fen),),
            demo_round_id=context.demo_round_id,
        )
        return self._after_write(context.user_id, result)

    def get_order(self, user_id: str, order_id: str, demo_round_id: str | None = None):
        """demo_round_id is required by the gateway; None is only the test seam."""
        row = self.store.get_order(user_id, order_id)
        if row is None:
            return _error("RECORD_NOT_FOUND")
        if demo_round_id is not None and row["demo_round_id"] != demo_round_id:
            return _error("ACCESS_DENIED")
        return QueryOk(kind="ok", data=OrderResult(order=OrderView(
            order_id=row["order_id"], product_id=row["product_id"], quantity=row["quantity"],
            merchant_id=row["merchant_id"], merchant_name=row["merchant_name"],
            total_fen=row["total_fen"], created_at=row["created_at"],
            deliver_by=row["deliver_by"], recipient_name_masked=row["recipient_name_masked"],
            phone_masked=row["phone_masked"], address_masked=row["address_masked"],
            payment_status=row["payment_status"],
            payment_transaction_id=row["payment_transaction_id"],
        )))
