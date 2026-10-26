"""The sole bank entry point for ordinary business modules."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Callable
from uuid import UUID

from app.contracts.bank import (
    BankError, CaptureFrozenInput, CreateOrderInput, FreezeFundsInput, QueryFailure,
    ReleaseFrozenInput,
)
from app.contracts.platform import TrustedContext
from app.services.mock_bank.core import MockBankService
from app.services.mock_bank.verification import AdminContext


class BankGateway:
    def __init__(
        self, bank: MockBankService, *, transfer_timeout_seconds: float = 4.0,
        authorize_transfer: Callable[..., bool] | None = None,
        authorize_face: Callable[..., bool] | None = None,
        authorize_cancel: Callable[..., bool] | None = None,
        authorize_birthday: Callable[..., bool] | None = None,
    ):
        self._bank = bank
        self._transfer_timeout_seconds = transfer_timeout_seconds
        self._authorize_transfer = authorize_transfer
        self._authorize_face = authorize_face
        self._authorize_cancel = authorize_cancel
        self._authorize_birthday = authorize_birthday
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mock-bank")

    def close(self) -> None:
        self._executor.shutdown(wait=True)

    def list_accounts(self, context: TrustedContext):
        return self._bank.list_accounts(context.user_id)

    def get_account(self, context: TrustedContext, account_id: str):
        return self._bank.get_account(context.user_id, account_id)

    def list_payees(self, context: TrustedContext, search: dict | None = None):
        return self._bank.list_payees(context.user_id, search)

    def verify_payee(self, context: TrustedContext, payee):
        return self._bank.verify_payee(context.user_id, payee)

    def get_limits(self, context: TrustedContext, account_id: str):
        return self._bank.get_limits(context.user_id, account_id)

    def list_transactions(self, context: TrustedContext, account_id: str, start_at, end_at):
        return self._bank.list_transactions(context.user_id, account_id, start_at, end_at)

    def quote_transfer(self, context: TrustedContext, payer_account_id: str, payee, amount_fen: int):
        return self._bank.quote_transfer(context.user_id, payer_account_id, payee, amount_fen)

    def precheck_transfer(self, context: TrustedContext, payer_account_id: str, payee, amount_fen: int):
        return self._bank.precheck_transfer(context.user_id, payer_account_id, payee, amount_fen)

    def submit_transfer(
        self, context: TrustedContext, operation_id: UUID,
        payer_account_id: str, payee, amount_fen: int,
    ):
        if self._authorize_transfer is None or not self._authorize_transfer(
            context, operation_id, payer_account_id, payee, amount_fen,
        ):
            return QueryFailure(kind="error", error=BankError(code="ACCESS_DENIED", details={}))
        future = self._executor.submit(
            self._bank.submit_transfer, context, operation_id,
            payer_account_id, payee, amount_fen,
        )
        try:
            return future.result(timeout=self._transfer_timeout_seconds)
        except TimeoutError:
            return QueryFailure(kind="error", error=BankError(code="CALL_TIMEOUT", details={}))

    def get_operation(self, context: TrustedContext, operation_id: UUID):
        return self._bank.get_operation(context, operation_id)

    # --- Birthday capabilities (B10—B13, B20—B22); writes are denied without
    # the executor's authorization, exactly like an ordinary transfer. The
    # authorize_birthday callback receives the typed request (amount and
    # resource ids included) so security can verify the exact submission
    # behind the operation id; it must stay a plain callable boundary. ---

    def _birthday_write(self, context: TrustedContext, operation_id: UUID,
                        action: str, request, invoke: Callable[[], object]):
        if self._authorize_birthday is None or not self._authorize_birthday(
            context, operation_id, action, request,
        ):
            return QueryFailure(kind="error", error=BankError(code="ACCESS_DENIED", details={}))
        future = self._executor.submit(invoke)
        try:
            return future.result(timeout=self._transfer_timeout_seconds)
        except TimeoutError:
            return QueryFailure(kind="error", error=BankError(code="CALL_TIMEOUT", details={}))
        except ValueError:
            return QueryFailure(kind="error", error=BankError(code="OPERATION_CONFLICT", details={}))
        except sqlite3.Error:
            return QueryFailure(kind="error", error=BankError(code="BANK_UNAVAILABLE", details={}))

    def freeze_funds(self, context: TrustedContext, operation_id: UUID, request: FreezeFundsInput):
        birthday = self._bank.birthday
        return self._birthday_write(context, operation_id, "bank.freeze_funds", request, lambda: (
            birthday.freeze_funds(context, operation_id, request.account_id,
                                  request.amount_fen, request.reason)
        ))

    def capture_frozen(self, context: TrustedContext, operation_id: UUID, request: CaptureFrozenInput):
        birthday = self._bank.birthday
        return self._birthday_write(context, operation_id, "bank.capture_frozen", request, lambda: (
            birthday.capture_frozen(context, operation_id, request.freeze_id,
                                    request.amount_fen, request.merchant_id,
                                    request.merchant_name, request.purpose,
                                    request.category, request.order_id)
        ))

    def release_frozen(self, context: TrustedContext, operation_id: UUID, request: ReleaseFrozenInput):
        birthday = self._bank.birthday
        return self._birthday_write(context, operation_id, "bank.release_frozen", request, lambda: (
            birthday.release_frozen(context, operation_id, request.freeze_id, request.amount_fen)
        ))

    def create_order(self, context: TrustedContext, operation_id: UUID, request: CreateOrderInput):
        birthday = self._bank.birthday
        return self._birthday_write(context, operation_id, "bank.create_order", request, lambda: (
            birthday.create_order(context, operation_id, request.product_id,
                                  request.quantity, request.expected_total_fen, request.delivery)
        ))

    def get_freeze(self, context: TrustedContext, freeze_id: str):
        return self._bank.birthday.get_freeze(
            context.user_id, freeze_id, context.demo_round_id)

    def get_order(self, context: TrustedContext, order_id: str):
        return self._bank.birthday.get_order(
            context.user_id, order_id, context.demo_round_id)

    def list_products(self, context: TrustedContext, merchant_id: str | None = None,
                      purpose: str | None = None, deliver_by=None):
        return self._bank.birthday.list_products(merchant_id, purpose, deliver_by)

    def list_subscriptions(self, context: TrustedContext, account_id: str | None = None,
                           status: str | None = None):
        return self._bank.list_subscriptions(context.user_id, account_id, status)

    def cancel_subscription(self, context: TrustedContext, operation_id: UUID, mandate_id: str):
        """B30 under the same server authorization and write budget as a transfer."""
        if self._authorize_cancel is None or not self._authorize_cancel(
            context, operation_id, mandate_id,
        ):
            return QueryFailure(kind="error", error=BankError(code="ACCESS_DENIED", details={}))
        future = self._executor.submit(
            self._bank.cancel_subscription, context, operation_id, mandate_id,
        )
        try:
            return future.result(timeout=self._transfer_timeout_seconds)
        except TimeoutError:
            return QueryFailure(kind="error", error=BankError(code="CALL_TIMEOUT", details={}))

    def create_verification(self, context: TrustedContext, purpose: str,
                            operation_id=None, action_revision=None, summary=None):
        return self._bank.verification.create_verification(
            context, purpose, operation_id, action_revision, summary,
        )

    def retire_action_challenges(self, context: TrustedContext, *, operation_id: UUID,
                                 action_revision: int):
        """Bank-side winner for an unsubmitted attempt; protocol only, no business rules."""
        return self._bank.verification.retire_action_challenges(
            context, operation_id=operation_id, action_revision=action_revision,
        )

    def retirement_for(self, context: TrustedContext, operation_id: UUID,
                       action_revision: int):
        """Read-only retirement fact; never mutates the bank's challenge rows."""
        return self._bank.verification.retirement_for(context, operation_id, action_revision)

    def get_verification(self, context: TrustedContext, challenge_id: str):
        return self._bank.verification.get_verification(context, challenge_id)

    def list_verifications(self, context: TrustedContext, task_id: str):
        """Read-only, session-independent challenge replay for the task owner."""
        return self._bank.verification.list_task_challenges(context, task_id)

    def get_demo_code_for_api(self, context: TrustedContext, challenge_id: str) -> str:
        """Dedicated F19 display path; never register as an Agent capability."""
        return self._bank.verification.get_demo_code(context, challenge_id)

    def resend_verification_code(self, context: TrustedContext, challenge_id: str,
                                 submission_id: UUID):
        return self._bank.verification.resend_code(context, challenge_id, submission_id)

    def verify_code(self, context: TrustedContext, challenge_id: str,
                    submission_id: UUID, code: str):
        return self._bank.verification.verify_code(context, challenge_id, submission_id, code)

    def start_face(self, context: TrustedContext, challenge_id: str, submission_id: UUID):
        return self._bank.verification.start_face(context, challenge_id, submission_id)

    def verify_face(self, admin: AdminContext, challenge_id: str,
                    submission_id: UUID, result: str):
        if self._authorize_face is None or not self._authorize_face(
            admin, challenge_id, submission_id, result,
        ):
            raise ValueError("ACCESS_DENIED")
        return self._bank.verification.verify_face(admin, challenge_id, submission_id, result)

    def get_verification_record(self, context: TrustedContext, verification_id: str):
        return self._bank.verification.get_record(context, verification_id)
