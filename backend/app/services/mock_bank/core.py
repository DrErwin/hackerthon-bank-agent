"""Deterministic mock-bank facts and transfer decisions for the v0.3 path."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import threading
import time
from uuid import UUID, uuid4

from app.contracts.bank import (
    AccountDetail, AccountList, AccountSummary, BalanceSnapshot, BankError,
    ManualPayee, OperationFound, OperationNotFound, OperationResult, OwnPayee,
    PayeeCandidate, PayeeDisplay, PayeeList, PayeeVerification, QueryFailure, QueryOk,
    SavedPayee, TransferLimits, TransferPrecheck, TransferQuote, TransferReceipt,
)
from app.contracts.platform import TrustedContext
from app.storage.database import connect, parameter_digest, transaction
from app.storage.mock_bank.repository import BankAccount, MockBankStore

from .verification import MockBankVerification


BEIJING = timezone(timedelta(hours=8))
SEEDS_DIR = Path(__file__).parent / "seeds"


def _load_seeds(filename: str) -> list[dict]:
    return json.loads((SEEDS_DIR / filename).read_text(encoding="utf-8"))


ACCOUNT_LABELS = {
    row["account_id"]: (row["user_id"], row["account_masked"], row["display_name"], row["bank_name"])
    for row in _load_seeds("accounts.json")
}
# Keep the existing test seam; the facts themselves live only in JSON.
PAYEES = {
    row["payee_id"]: (row["user_id"], row["name"], row["account_number"],
                      row["remark"], row["bank_name"], row["phone"])
    for row in _load_seeds("payees.json")
}
LIMITS = {
    "class_i": (5_000_000, 5_000_000, None),
    "class_ii": (1_000_000, 1_000_000, 20_000_000),
    "class_iii": (200_000, 200_000, 5_000_000),
}


def _now() -> datetime:
    return datetime.now(BEIJING)


def _error(code: str, **details) -> QueryFailure:
    return QueryFailure(kind="error", error=BankError(code=code, details=details))


class MockBankService:
    """Bank-owned rules; ordinary modules use BankGateway instead."""

    def __init__(self, store: MockBankStore, *, demo_secret: bytes, slow_seconds: float = 6.0):
        self.store = store
        self.slow_seconds = slow_seconds
        self._slow_once: set[str] = set()
        self._slow_lock = threading.Lock()
        self.seed_demo()
        with transaction(self.store.path) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS bank_operation_scopes (
                operation_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                demo_round_id TEXT NOT NULL
            )""")
            unscoped = connection.execute("""SELECT COUNT(*) FROM bank_operations AS b
                LEFT JOIN bank_operation_scopes AS s ON s.operation_id = b.operation_id
                WHERE s.operation_id IS NULL""").fetchone()[0]
            if unscoped:
                raise RuntimeError(
                    "legacy bank operations have no demo round; retain the old database for "
                    "reference and start a fresh demo bank database explicitly"
                )
            # A processing row has no ledger effect until the final settlement transaction.
            # After this single-process demo restarts, its former worker cannot finish it.
            interrupted = connection.execute("""SELECT operation_id, recorded_at FROM bank_operations
                WHERE action_name = 'bank.submit_transfer' AND status = 'processing'""").fetchall()
            for row in interrupted:
                now = _now()
                result = self._result(
                    UUID(row["operation_id"]), "failed",
                    datetime.fromisoformat(row["recorded_at"]), updated_at=now,
                    failure=BankError(code="STATE_CONFLICT", details={"reason": "processing_interrupted"}),
                )
                connection.execute("""UPDATE bank_operations
                    SET status = 'failed', result_json = ?, updated_at = ?
                    WHERE operation_id = ?""", (
                    result.model_dump_json(), now.isoformat(), row["operation_id"],
                ))
        self.verification = MockBankVerification(store.path, demo_secret)

    def seed_demo(self, *, include_evaluation: bool = False) -> None:
        """Add missing JSON accounts without resetting balances or existing state."""
        for row in _load_seeds("accounts.json"):
            if row["evaluation_only"] and not include_evaluation:
                continue
            self.store.seed_account(BankAccount(
                account_id=row["account_id"], user_id=row["user_id"],
                account_type=row["account_type"], account_status=row["account_status"],
                book_balance_fen=row["book_balance_fen"],
                frozen_balance_fen=row["frozen_balance_fen"], version=row["version"],
            ))

    def arm_slow_once(self, user_id: str) -> None:
        """Bank-internal demo control; no ordinary gateway method exposes it."""
        with self._slow_lock:
            self._slow_once.add(user_id)

    def _take_slow(self, user_id: str) -> bool:
        with self._slow_lock:
            if user_id not in self._slow_once:
                return False
            self._slow_once.remove(user_id)
            return True

    @staticmethod
    def _account_view(account: BankAccount, at: datetime) -> AccountDetail:
        _, masked, name, bank_name = ACCOUNT_LABELS.get(
            account.account_id,
            (account.user_id, "尾号 " + account.account_id[-4:], "本人账户", "模拟银行"),
        )
        return AccountDetail(
            account_id=account.account_id, account_type=account.account_type,
            account_masked=masked,
            available_balance_fen=account.book_balance_fen - account.frozen_balance_fen,
            display_name=name, bank_name=bank_name,
            account_status=account.account_status, book_balance_fen=account.book_balance_fen,
            frozen_balance_fen=account.frozen_balance_fen, as_of=at,
        )

    def list_accounts(self, user_id: str):
        at = _now()
        with closing(connect(self.store.path)) as connection:
            rows = connection.execute(
                "SELECT account_id FROM accounts WHERE user_id = ? ORDER BY account_id", (user_id,),
            ).fetchall()
        accounts = [self.store.get_account(user_id, row["account_id"]) for row in rows]
        return QueryOk(kind="ok", data=AccountList(accounts=[
            AccountSummary.model_validate(self._account_view(account, at).model_dump(include={
                "account_id", "account_type", "account_masked", "available_balance_fen",
                "display_name", "bank_name",
            }))
            for account in accounts
        ]))

    def get_account(self, user_id: str, account_id: str):
        account = self.store.get_account(user_id, account_id)
        if account is None:
            return _error("ACCESS_DENIED")
        return QueryOk(kind="ok", data=self._account_view(account, _now()))

    @staticmethod
    def _payee_display(payee_id: str) -> PayeeDisplay:
        _, name, number, remark, bank_name, _ = PAYEES[payee_id]
        masked_name = name[0] + "*" * (len(name) - 1)
        return PayeeDisplay(
            payee_id=payee_id, name_masked=masked_name,
            account_masked="****" + number[-4:], remark=remark, bank_name=bank_name,
        )

    def list_payees(self, user_id: str, search: dict | None = None):
        if search is not None and (
            search.get("kind") not in {"name", "phone", "account_number", "remark"}
            or not isinstance(search.get("value"), str) or not search["value"].strip()
        ):
            return _error("INVALID_ARGUMENT", field="search", reason="invalid search")
        found = []
        for payee_id, (owner, name, number, remark, _, phone) in PAYEES.items():
            if owner != user_id or payee_id == "A7":
                continue
            if search:
                value = search["value"].strip()
                kind = search["kind"]
                candidate = {"name": name.strip(), "phone": phone,
                             "account_number": number, "remark": (remark or "").strip()}[kind]
                matches = value in candidate if kind == "remark" else value == candidate
                if not matches:
                    continue
            found.append(PayeeCandidate(
                **self._payee_display(payee_id).model_dump(), last_transfer_at=None,
            ))
        return QueryOk(kind="ok", data=PayeeList(payees=found))

    def _resolve_payee(self, user_id: str, payee):
        if isinstance(payee, OwnPayee):
            account = self.store.get_account(user_id, payee.account_id)
            if account is None:
                return None
            view = self._account_view(account, _now())
            return PayeeDisplay(
                payee_id=account.account_id, name_masked=view.display_name,
                account_masked=view.account_masked, remark=None, bank_name=view.bank_name,
            ), account.account_id
        if isinstance(payee, SavedPayee):
            row = PAYEES.get(payee.payee_id)
            if row is None or row[0] != user_id:
                return None
            return self._payee_display(payee.payee_id), None
        if isinstance(payee, ManualPayee):
            for payee_id, (owner, name, number, _, _, _) in PAYEES.items():
                if owner == user_id and name == payee.account_name and number == payee.account_number:
                    return self._payee_display(payee_id), None
        return None

    def verify_payee(self, user_id: str, payee):
        resolved = self._resolve_payee(user_id, payee)
        return QueryOk(kind="ok", data=PayeeVerification(
            matched=resolved is not None, payee=resolved[0] if resolved else None,
        ))

    def get_limits(self, user_id: str, account_id: str):
        account = self.store.get_account(user_id, account_id)
        if account is None:
            return _error("ACCESS_DENIED")
        at = _now()
        single, daily, annual = LIMITS[account.account_type]
        outgoing = self.store.list_ledger(user_id, account_id)
        today_spent = sum(row["amount_fen"] for row in outgoing if
                          row["direction"] == "outflow" and row["nature"] == "transfer" and
                          datetime.fromisoformat(row["occurred_at"]).astimezone(BEIJING).date() == at.date())
        year_spent = sum(row["amount_fen"] for row in outgoing if
                         row["direction"] == "outflow" and row["nature"] == "transfer" and
                         datetime.fromisoformat(row["occurred_at"]).astimezone(BEIJING).year == at.year)
        return QueryOk(kind="ok", data=TransferLimits(
            single_limit_fen=single, daily_remaining_fen=max(0, daily - today_spent),
            annual_remaining_fen=None if annual is None else max(0, annual - year_spent),
            as_of=at,
        ))

    def quote_transfer(self, user_id: str, payer_account_id: str, payee, amount_fen: int):
        if self.store.get_account(user_id, payer_account_id) is None:
            return _error("ACCESS_DENIED")
        if amount_fen <= 0:
            return _error("INVALID_ARGUMENT", field="amount_fen", reason="must be positive")
        return QueryOk(kind="ok", data=TransferQuote(fee_fen=0, arrival_mode="instant"))

    def precheck_transfer(self, user_id: str, payer_account_id: str, payee, amount_fen: int):
        account = self.store.get_account(user_id, payer_account_id)
        if account is None:
            return _error("ACCESS_DENIED")
        if amount_fen <= 0:
            return _error("INVALID_ARGUMENT", field="amount_fen", reason="must be positive")
        failure = None
        resolved = self._resolve_payee(user_id, payee)
        available = account.book_balance_fen - account.frozen_balance_fen
        if resolved is None or (isinstance(payee, OwnPayee) and payee.account_id == payer_account_id):
            failure = BankError(code="PAYEE_MISMATCH", details={})
        elif account.account_status != "active":
            failure = BankError(code="ACCOUNT_UNAVAILABLE", details={"account_status": account.account_status})
        elif amount_fen > available:
            failure = BankError(code="INSUFFICIENT_FUNDS", details={
                "available_fen": available, "required_fen": amount_fen,
                "shortfall_fen": amount_fen - available,
            })
        else:
            limits = self.get_limits(user_id, payer_account_id).data
            if amount_fen > limits.single_limit_fen:
                failure = BankError(code="LIMIT_EXCEEDED", details={
                    "scope": "single", "allowed_fen": limits.single_limit_fen,
                    "requested_fen": amount_fen,
                })
            elif amount_fen > limits.daily_remaining_fen:
                failure = BankError(code="LIMIT_EXCEEDED", details={
                    "scope": "day", "allowed_fen": limits.daily_remaining_fen,
                    "requested_fen": amount_fen,
                })
            elif limits.annual_remaining_fen is not None and amount_fen > limits.annual_remaining_fen:
                failure = BankError(code="LIMIT_EXCEEDED", details={
                    "scope": "year", "allowed_fen": limits.annual_remaining_fen,
                    "requested_fen": amount_fen,
                })
            elif resolved[0].payee_id == "A7":
                failure = BankError(code="RISK_REJECTED", details={"reason_code": "fraud_payee"})
        return QueryOk(kind="ok", data=TransferPrecheck(
            can_proceed=failure is None, failure=failure, fee_fen=0,
            arrival_mode="instant", checked_at=_now(),
        ))

    @staticmethod
    def _result(operation_id: UUID, status: str, recorded_at: datetime,
                updated_at: datetime | None = None, receipt=None, failure=None):
        return OperationResult[TransferReceipt](
            operation_id=operation_id, operation_type="bank.submit_transfer",
            operation_status=status, recorded_at=recorded_at,
            updated_at=updated_at or recorded_at,
            receipt=receipt, failure=failure,
        )

    def _stored_result(self, user_id: str, operation_id: UUID, parameters: dict):
        with closing(connect(self.store.path)) as connection:
            row = connection.execute(
                "SELECT user_id FROM bank_operations WHERE operation_id = ?", (str(operation_id),),
            ).fetchone()
        if row is None:
            return None
        if row["user_id"] != user_id:
            return _error("OPERATION_CONFLICT")
        operation = self.store.get_operation(user_id, str(operation_id))
        if operation.parameters_digest != parameter_digest(parameters):
            return _error("OPERATION_CONFLICT")
        return OperationResult[TransferReceipt].model_validate(operation.result)

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

    def submit_transfer(self, context: TrustedContext, operation_id: UUID,
                        payer_account_id: str, payee, amount_fen: int):
        user_id = context.user_id
        if operation_id.version != 4:
            return _error("INVALID_ARGUMENT", field="operation_id", reason="UUID v4 required")
        if not self._reserve_scope(context, operation_id):
            return _error("OPERATION_CONFLICT")
        parameters = {"payer_account_id": payer_account_id,
                      "payee": payee.model_dump(mode="json"), "amount_fen": amount_fen}
        prior = self._stored_result(user_id, operation_id, parameters)
        if prior is not None:
            return prior
        preliminary = self.precheck_transfer(user_id, payer_account_id, payee, amount_fen)
        if preliminary.kind == "error":
            return preliminary
        slow = self._take_slow(user_id) if preliminary.data.can_proceed else False
        at = _now()
        if slow:
            processing = self._result(operation_id, "processing", at)
            try:
                saved = self.store.commit_operation(
                    user_id, str(operation_id), "bank.submit_transfer", parameters,
                    "processing", processing.model_dump(mode="json"), at.isoformat(), [], [],
                )
            except ValueError:
                return _error("OPERATION_CONFLICT")
            if saved.status != "processing":
                return OperationResult[TransferReceipt].model_validate(saved.result)
            time.sleep(self.slow_seconds)
        while True:
            preliminary = self.precheck_transfer(user_id, payer_account_id, payee, amount_fen)
            if preliminary.kind == "error":
                failure = preliminary.error
            else:
                failure = preliminary.data.failure
            if failure is None:
                account = self.store.get_account(user_id, payer_account_id)
                resolved, own_target = self._resolve_payee(user_id, payee)
                changes = [(account.account_id, account.version,
                            account.book_balance_fen - amount_fen, account.frozen_balance_fen)]
                ledger = [(str(uuid4()), account.account_id, amount_fen, "outflow", "transfer",
                           "transfer", _now().isoformat())]
                if own_target:
                    target = self.store.get_account(user_id, own_target)
                    changes.append((target.account_id, target.version,
                                    target.book_balance_fen + amount_fen, target.frozen_balance_fen))
                    ledger.append((str(uuid4()), target.account_id, amount_fen, "inflow", "transfer",
                                   "transfer", ledger[0][-1]))
                completed_at = _now()
                balance = BalanceSnapshot(
                    account_id=account.account_id, book_balance_fen=account.book_balance_fen - amount_fen,
                    frozen_balance_fen=account.frozen_balance_fen,
                    available_balance_fen=account.book_balance_fen - amount_fen - account.frozen_balance_fen,
                    as_of=completed_at,
                )
                receipt = TransferReceipt(
                    transaction_id=ledger[0][0], payer_account_id=account.account_id,
                    payee=resolved, amount_fen=amount_fen, fee_fen=0, arrival_mode="instant",
                    completed_at=completed_at, balance=balance,
                )
                result = self._result(operation_id, "succeeded", at,
                                      updated_at=completed_at, receipt=receipt)
            else:
                changes, ledger = [], []
                result = self._result(operation_id, "failed", at,
                                      updated_at=_now(), failure=failure)
            try:
                if slow:
                    saved = self.store.finalize_operation(
                        user_id, str(operation_id), "bank.submit_transfer", parameters,
                        result.operation_status.value, result.model_dump(mode="json"),
                        _now().isoformat(), changes, ledger,
                    )
                else:
                    saved = self.store.commit_operation(
                        user_id, str(operation_id), "bank.submit_transfer", parameters,
                        result.operation_status.value, result.model_dump(mode="json"),
                        at.isoformat(), changes, ledger,
                    )
                return OperationResult[TransferReceipt].model_validate(saved.result)
            except ValueError:
                prior = self._stored_result(user_id, operation_id, parameters)
                if isinstance(prior, QueryFailure):
                    return prior
                if prior is not None and prior.operation_status != "processing":
                    return prior
                if prior is not None and not slow:
                    return prior
            except sqlite3.Error:
                return _error("BANK_UNAVAILABLE")

    def get_operation(self, context: TrustedContext, operation_id: UUID):
        user_id = context.user_id
        with closing(connect(self.store.path)) as connection:
            owner = connection.execute(
                """SELECT b.user_id, s.demo_round_id FROM bank_operations AS b
                   LEFT JOIN bank_operation_scopes AS s ON s.operation_id = b.operation_id
                   WHERE b.operation_id = ?""", (str(operation_id),),
            ).fetchone()
        if owner is None:
            return OperationNotFound(lookup="not_found", operation=None)
        if (owner["user_id"], owner["demo_round_id"]) != (
            user_id, context.demo_round_id,
        ):
            return _error("ACCESS_DENIED")
        operation = self.store.get_operation(user_id, str(operation_id))
        return OperationFound[TransferReceipt](
            lookup="found", operation=OperationResult[TransferReceipt].model_validate(operation.result),
        )
