"""The sole bank entry point for ordinary business modules."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Callable
from uuid import UUID

from app.contracts.bank import BankError, QueryFailure
from app.contracts.platform import TrustedContext
from app.services.mock_bank.core import MockBankService
from app.services.mock_bank.verification import AdminContext


class BankGateway:
    def __init__(
        self, bank: MockBankService, *, transfer_timeout_seconds: float = 4.0,
        authorize_transfer: Callable[..., bool] | None = None,
        authorize_face: Callable[..., bool] | None = None,
    ):
        self._bank = bank
        self._transfer_timeout_seconds = transfer_timeout_seconds
        self._authorize_transfer = authorize_transfer
        self._authorize_face = authorize_face
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

    def create_verification(self, context: TrustedContext, purpose: str,
                            operation_id=None, action_revision=None, summary=None):
        return self._bank.verification.create_verification(
            context, purpose, operation_id, action_revision, summary,
        )

    def get_verification(self, context: TrustedContext, challenge_id: str):
        return self._bank.verification.get_verification(context, challenge_id)

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
