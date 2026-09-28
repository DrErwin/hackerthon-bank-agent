"""Private mock-bank data; callers must go through the bank service boundary."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.storage.database import connect, parameter_digest, transaction


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BankAccount:
    account_id: str
    user_id: str
    account_type: str
    account_status: str
    book_balance_fen: int
    frozen_balance_fen: int
    version: int


@dataclass(frozen=True)
class BankOperation:
    operation_id: str
    user_id: str
    action_name: str
    parameters_digest: str
    status: str
    result: dict
    recorded_at: str


class MockBankStore:
    def __init__(self, path: Path):
        self.path = path
        self.initialize()

    def initialize(self) -> None:
        with transaction(self.path) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError("bank database is newer than this code")
            if version == 0:
                connection.execute("""
                    CREATE TABLE accounts (
                        account_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        account_type TEXT NOT NULL,
                        account_status TEXT NOT NULL,
                        book_balance_fen INTEGER NOT NULL,
                        frozen_balance_fen INTEGER NOT NULL,
                        version INTEGER NOT NULL DEFAULT 0
                    )
                """)
                connection.execute("""
                    CREATE TABLE ledger_entries (
                        transaction_id TEXT PRIMARY KEY,
                        account_id TEXT NOT NULL REFERENCES accounts(account_id),
                        user_id TEXT NOT NULL,
                        operation_id TEXT NOT NULL,
                        amount_fen INTEGER NOT NULL,
                        direction TEXT NOT NULL,
                        nature TEXT NOT NULL,
                        category TEXT NOT NULL,
                        occurred_at TEXT NOT NULL
                    )
                """)
                connection.execute("""
                    CREATE TABLE bank_operations (
                        operation_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        action_name TEXT NOT NULL,
                        parameters_digest TEXT NOT NULL,
                        status TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        recorded_at TEXT NOT NULL
                    )
                """)
                connection.execute("PRAGMA user_version = 1")

    def seed_account(self, account: BankAccount) -> None:
        with transaction(self.path) as connection:
            connection.execute(
                """INSERT OR IGNORE INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (account.account_id, account.user_id, account.account_type,
                 account.account_status, account.book_balance_fen,
                 account.frozen_balance_fen, account.version),
            )

    def get_account(self, user_id: str, account_id: str) -> BankAccount | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                "SELECT * FROM accounts WHERE user_id = ? AND account_id = ?",
                (user_id, account_id),
            ).fetchone()
            return BankAccount(**dict(row)) if row else None
        finally:
            connection.close()

    def get_operation(self, user_id: str, operation_id: str) -> BankOperation | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                "SELECT * FROM bank_operations WHERE user_id = ? AND operation_id = ?",
                (user_id, operation_id),
            ).fetchone()
            return self._operation(row) if row else None
        finally:
            connection.close()

    @staticmethod
    def _operation(row) -> BankOperation:
        return BankOperation(
            row["operation_id"], row["user_id"], row["action_name"],
            row["parameters_digest"], row["status"], json.loads(row["result_json"]),
            row["recorded_at"],
        )

    def commit_operation(
        self, user_id: str, operation_id: str, action_name: str,
        parameters: dict, status: str, result: dict, recorded_at: str,
        account_updates: list[tuple[str, int, int, int]],
        ledger_entries: list[tuple[str, str, int, str, str, str, str]],
    ) -> BankOperation:
        """Atomically save a bank decision and its already-decided balance changes.

        account_updates: (account_id, expected_version, book_fen, frozen_fen).
        ledger_entries: (transaction_id, account_id, amount_fen, direction,
        nature, category, occurred_at). Bank rules remain in the bank service.
        """
        digest = parameter_digest(parameters)
        with transaction(self.path) as connection:
            existing = connection.execute(
                "SELECT * FROM bank_operations WHERE operation_id = ?", (operation_id,),
            ).fetchone()
            if existing is not None:
                if (existing["user_id"], existing["action_name"], existing["parameters_digest"]) != (
                    user_id, action_name, digest,
                ):
                    raise ValueError("operation_id conflicts with an existing bank action")
                return self._operation(existing)
            for account_id, expected_version, book_fen, frozen_fen in account_updates:
                changed = connection.execute(
                    """UPDATE accounts SET book_balance_fen = ?, frozen_balance_fen = ?,
                       version = version + 1 WHERE account_id = ? AND user_id = ?
                       AND version = ?""",
                    (book_fen, frozen_fen, account_id, user_id, expected_version),
                ).rowcount
                if changed != 1:
                    raise ValueError("account is out of scope or changed concurrently")
            for transaction_id, account_id, amount_fen, direction, nature, category, occurred_at in ledger_entries:
                owned = connection.execute(
                    "SELECT 1 FROM accounts WHERE account_id = ? AND user_id = ?",
                    (account_id, user_id),
                ).fetchone()
                if owned is None:
                    raise ValueError("ledger account is not in scope")
                connection.execute(
                    "INSERT INTO ledger_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (transaction_id, account_id, user_id, operation_id, amount_fen,
                     direction, nature, category, occurred_at),
                )
            connection.execute(
                "INSERT INTO bank_operations VALUES (?, ?, ?, ?, ?, ?, ?)",
                (operation_id, user_id, action_name, digest, status,
                 json.dumps(result, ensure_ascii=False), recorded_at),
            )
        return self.get_operation(user_id, operation_id)

    def list_ledger(self, user_id: str, account_id: str) -> list[dict]:
        connection = connect(self.path)
        try:
            owned = connection.execute(
                "SELECT 1 FROM accounts WHERE account_id = ? AND user_id = ?",
                (account_id, user_id),
            ).fetchone()
            if owned is None:
                raise ValueError("account is not in scope")
            return [dict(row) for row in connection.execute(
                """SELECT * FROM ledger_entries WHERE account_id = ? AND user_id = ?
                   ORDER BY occurred_at, transaction_id""", (account_id, user_id),
            )]
        finally:
            connection.close()
