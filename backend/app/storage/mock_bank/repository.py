"""Private mock-bank data; callers must go through the bank service boundary."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.storage.database import connect, parameter_digest, transaction


SCHEMA_VERSION = 3
LEDGER_FACT_COLUMNS = (
    "counterparty_id", "counterparty_name", "counterparty_account_masked",
    "channel", "summary", "original_transaction_id", "original_occurred_at",
)
LEDGER_SCHEMA = """
    CREATE TABLE ledger_entries (
        transaction_id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL REFERENCES accounts(account_id),
        user_id TEXT NOT NULL,
        operation_id TEXT NOT NULL,
        amount_fen INTEGER NOT NULL,
        direction TEXT NOT NULL,
        nature TEXT NOT NULL,
        category TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        counterparty_id TEXT,
        counterparty_name TEXT,
        counterparty_account_masked TEXT,
        channel TEXT,
        summary TEXT,
        original_transaction_id TEXT,
        original_occurred_at TEXT
    )
"""


def _require_owned_account(connection, user_id: str, account_id: str) -> None:
    owned = connection.execute(
        "SELECT 1 FROM accounts WHERE account_id = ? AND user_id = ?", (account_id, user_id),
    ).fetchone()
    if owned is None:
        raise ValueError("account is not in scope")


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
    updated_at: str


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
                connection.execute(LEDGER_SCHEMA)
                connection.execute("""
                    CREATE TABLE bank_operations (
                        operation_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        action_name TEXT NOT NULL,
                        parameters_digest TEXT NOT NULL,
                        status TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                version = 2
            elif version == 1:
                connection.execute("ALTER TABLE bank_operations ADD COLUMN updated_at TEXT")
                connection.execute("UPDATE bank_operations SET updated_at = recorded_at")
                version = 2
            if version == 2:
                columns = {row["name"] for row in connection.execute("PRAGMA table_info(ledger_entries)")}
                if not columns:
                    # An early v1 database may predate the ledger table; create it in the v3 shape.
                    connection.execute(LEDGER_SCHEMA)
                else:
                    for column in LEDGER_FACT_COLUMNS:
                        if column not in columns:
                            connection.execute(f"ALTER TABLE ledger_entries ADD COLUMN {column} TEXT")
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

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
            row["recorded_at"], row["updated_at"],
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
        if status not in {"processing", "succeeded", "failed"}:
            raise ValueError("invalid bank operation status")
        if status == "processing" and (account_updates or ledger_entries):
            raise ValueError("processing operation cannot apply ledger effects")
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
            self._apply_effects(connection, user_id, operation_id, account_updates, ledger_entries)
            connection.execute(
                "INSERT INTO bank_operations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (operation_id, user_id, action_name, digest, status,
                 json.dumps(result, ensure_ascii=False), recorded_at, recorded_at),
            )
        return self.get_operation(user_id, operation_id)

    def finalize_operation(
        self, user_id: str, operation_id: str, action_name: str,
        parameters: dict, status: str, result: dict, updated_at: str,
        account_updates: list[tuple[str, int, int, int]],
        ledger_entries: list[tuple[str, str, int, str, str, str, str]],
    ) -> BankOperation:
        """Settle a recorded processing operation and its ledger effects atomically."""
        if status not in {"succeeded", "failed"}:
            raise ValueError("final outcome must be succeeded or failed")
        digest = parameter_digest(parameters)
        with transaction(self.path) as connection:
            existing = connection.execute(
                "SELECT * FROM bank_operations WHERE operation_id = ?", (operation_id,),
            ).fetchone()
            if existing is None or (
                existing["user_id"], existing["action_name"], existing["parameters_digest"]
            ) != (user_id, action_name, digest):
                raise ValueError("processing operation is missing or belongs to a different action")
            if existing["status"] != "processing":
                if existing["status"] != status:
                    raise ValueError("terminal bank outcome cannot be changed")
                return self._operation(existing)
            self._apply_effects(connection, user_id, operation_id, account_updates, ledger_entries)
            connection.execute(
                """UPDATE bank_operations SET status = ?, result_json = ?, updated_at = ?
                   WHERE operation_id = ?""",
                (status, json.dumps(result, ensure_ascii=False), updated_at, operation_id),
            )
        return self.get_operation(user_id, operation_id)

    @staticmethod
    def _apply_effects(connection, user_id, operation_id, account_updates, ledger_entries) -> None:
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
            _require_owned_account(connection, user_id, account_id)
            connection.execute(
                """INSERT INTO ledger_entries (transaction_id, account_id, user_id, operation_id,
                   amount_fen, direction, nature, category, occurred_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (transaction_id, account_id, user_id, operation_id, amount_fen,
                 direction, nature, category, occurred_at),
            )

    def seed_ledger_rows(self, rows: list[dict]) -> int:
        """Insert already-formed bank facts; idempotent per transaction_id.

        Seeded rows have no real operation, so their ``operation_id`` marks the
        origin, and the caller owns the bank clock: ``occurred_at`` arrives as an
        ISO string. Returns how many rows were newly written. A row that the bank
        could not later return as a valid flow fact is refused, not silently lost.
        """
        written = 0
        with transaction(self.path) as connection:
            for row in rows:
                account_id, user_id = row["account_id"], row["user_id"]
                _require_owned_account(connection, user_id, account_id)
                amount_fen = row["amount_fen"]
                if (not isinstance(amount_fen, int) or amount_fen < 0
                        or not row.get("counterparty_name") or not row.get("summary")):
                    raise ValueError(
                        "seeded ledger row needs a non-negative amount, counterparty_name and summary"
                    )
                changed = connection.execute(
                    """INSERT OR IGNORE INTO ledger_entries (
                       transaction_id, account_id, user_id, operation_id, amount_fen, direction,
                       nature, category, occurred_at, counterparty_id, counterparty_name,
                       counterparty_account_masked, channel, summary, original_transaction_id,
                       original_occurred_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row["transaction_id"], account_id, user_id,
                        "seed:" + row["transaction_id"], amount_fen, row["direction"],
                        row["nature"], row["category"], row["occurred_at"],
                        row.get("counterparty_id"), row["counterparty_name"],
                        row.get("counterparty_account_masked"), row.get("channel"),
                        row["summary"], row.get("original_transaction_id"),
                        row.get("original_occurred_at"),
                    ),
                ).rowcount
                if changed == 0 and connection.execute(
                    "SELECT 1 FROM ledger_entries WHERE transaction_id = ?", (row["transaction_id"],),
                ).fetchone() is None:
                    raise ValueError("seeded ledger row was rejected: " + str(row["transaction_id"]))
                written += changed
        return written

    def list_ledger(self, user_id: str, account_id: str) -> list[dict]:
        connection = connect(self.path)
        try:
            _require_owned_account(connection, user_id, account_id)
            return [dict(row) for row in connection.execute(
                """SELECT * FROM ledger_entries WHERE account_id = ? AND user_id = ?
                   ORDER BY occurred_at, transaction_id""", (account_id, user_id),
            )]
        finally:
            connection.close()
