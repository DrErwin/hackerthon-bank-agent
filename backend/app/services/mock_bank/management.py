"""Bank-owned B26 reset receipts; platform admission and app reset stay outside."""

from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Callable, Literal

from app.contracts.bank import BankError
from app.contracts.common import ContractModel
from app.storage.database import connect, parameter_digest, transaction

from . import subscriptions
from .flow_seeds import build_flow_rows
from .verification import AdminContext


class BankDemoManagementResult(ContractModel):
    management_operation_id: str
    status: Literal["running", "succeeded", "failed"]
    source_round_id: str
    demo_round_id: str
    logical_at: datetime
    error: BankError | None


def current_demo_round_id(bank_path: Path) -> str | None:
    """Unmanaged legacy banks have no reset marker; a reset bank owns its round."""
    with closing(connect(bank_path)) as connection:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                              "AND name = 'bank_demo_state'").fetchone() is None:
            return None
        row = connection.execute("SELECT demo_round_id FROM bank_demo_state WHERE singleton = 1").fetchone()
        return row["demo_round_id"] if row else None


class MockBankDemo:
    def __init__(self, bank_path: Path, *, clock: Callable[[], datetime],
                 clear_faults: Callable[[], None]):
        self.path = bank_path
        self.clock = clock
        self.clear_faults = clear_faults
        with transaction(self.path) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS bank_demo_state (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                demo_round_id TEXT NOT NULL,
                logical_at TEXT NOT NULL
            )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS bank_management_operations (
                management_operation_id TEXT PRIMARY KEY,
                actor_id TEXT NOT NULL,
                parameters_digest TEXT NOT NULL,
                result_json TEXT NOT NULL
            )""")

    @staticmethod
    def _authorized(admin) -> bool:
        return isinstance(admin, AdminContext) and admin.authorized and bool(admin.actor_id)

    def _failed(self, operation_id: str, source_round_id: str, code: str):
        return BankDemoManagementResult(
            management_operation_id=operation_id, status="failed",
            source_round_id=source_round_id, demo_round_id=source_round_id,
            logical_at=self.clock(), error=BankError(code=code, details={}),
        )

    @staticmethod
    def _save(connection, result: BankDemoManagementResult) -> None:
        connection.execute("UPDATE bank_management_operations SET result_json = ? "
                           "WHERE management_operation_id = ?",
                           (result.model_dump_json(), result.management_operation_id))

    def get_operation(self, admin: AdminContext, operation_id: str):
        if not self._authorized(admin):
            raise PermissionError("ACCESS_DENIED")
        with closing(connect(self.path)) as connection:
            row = connection.execute("SELECT actor_id, result_json FROM bank_management_operations "
                                     "WHERE management_operation_id = ?", (operation_id,)).fetchone()
        if row is None:
            return None
        if row["actor_id"] != admin.actor_id:
            raise PermissionError("ACCESS_DENIED")
        return BankDemoManagementResult.model_validate_json(row["result_json"])

    def reset_demo(self, admin: AdminContext, management_operation_id: str,
                   source_round_id: str, target_round_id: str,
                   initial_logical_at: datetime) -> BankDemoManagementResult:
        if not self._authorized(admin):
            return self._failed(management_operation_id, source_round_id, "ACCESS_DENIED")
        if (not management_operation_id or not source_round_id or not target_round_id
                or source_round_id == target_round_id
                or initial_logical_at.tzinfo is None or initial_logical_at.utcoffset() is None):
            return self._failed(management_operation_id, source_round_id, "INVALID_ARGUMENT")
        digest = parameter_digest({"source_round_id": source_round_id,
                                   "target_round_id": target_round_id,
                                   "initial_logical_at": initial_logical_at.isoformat()})
        # Bind the original request before touching dynamic bank state. A failed
        # restore can only resume with these parameters, even after a restart.
        with transaction(self.path) as connection:
            previous = connection.execute("SELECT * FROM bank_management_operations "
                "WHERE management_operation_id = ?", (management_operation_id,)).fetchone()
            if previous:
                if (previous["actor_id"] != admin.actor_id
                        or previous["parameters_digest"] != digest):
                    return self._failed(management_operation_id, source_round_id, "OPERATION_CONFLICT")
                result = BankDemoManagementResult.model_validate_json(previous["result_json"])
                if result.status == "succeeded":
                    return result
                if admin.demo_round_id != source_round_id:
                    return self._failed(management_operation_id, source_round_id, "ACCESS_DENIED")
            else:
                if admin.demo_round_id != source_round_id:
                    return self._failed(management_operation_id, source_round_id, "ACCESS_DENIED")
                pending = connection.execute("SELECT result_json FROM bank_management_operations").fetchall()
                if any(BankDemoManagementResult.model_validate_json(row["result_json"]).status != "succeeded"
                       for row in pending):
                    return self._failed(management_operation_id, source_round_id, "STATE_CONFLICT")
                result = BankDemoManagementResult(
                    management_operation_id=management_operation_id, status="running",
                    source_round_id=source_round_id, demo_round_id=source_round_id,
                    logical_at=self.clock(), error=None,
                )
            state = connection.execute("SELECT * FROM bank_demo_state WHERE singleton = 1").fetchone()
            if state and state["demo_round_id"] != source_round_id:
                return self._failed(management_operation_id, source_round_id, "STATE_CONFLICT")
            connection.execute("INSERT OR IGNORE INTO bank_demo_state VALUES (1, ?, ?)",
                               (source_round_id, result.logical_at.isoformat()))
            result = result.model_copy(update={"status": "running", "error": None})
            connection.execute("INSERT OR IGNORE INTO bank_management_operations VALUES (?, ?, ?, ?)",
                (management_operation_id, admin.actor_id, digest, result.model_dump_json()))
            self._save(connection, result)

        try:
            with transaction(self.path) as connection:
                state = connection.execute("SELECT * FROM bank_demo_state WHERE singleton = 1").fetchone()
                if state["demo_round_id"] != source_round_id:
                    # A concurrent repeat may already have committed this reset.
                    stored = connection.execute("SELECT result_json FROM bank_management_operations "
                        "WHERE management_operation_id = ?", (management_operation_id,)).fetchone()
                    return BankDemoManagementResult.model_validate_json(stored["result_json"])
                if connection.execute("SELECT 1 FROM bank_operations WHERE status = 'processing' LIMIT 1").fetchone():
                    return result
                self._restore_seeds(connection, initial_logical_at)
                result = result.model_copy(update={"status": "succeeded", "demo_round_id": target_round_id,
                                                   "logical_at": initial_logical_at})
                connection.execute("UPDATE bank_demo_state SET demo_round_id = ?, logical_at = ? "
                                   "WHERE singleton = 1", (target_round_id, initial_logical_at.isoformat()))
                self._save(connection, result)
        except sqlite3.Error:
            # The restore transaction rolled back; retain both its original
            # binding and the failed fact so the platform can query then resume.
            with transaction(self.path) as connection:
                stored = connection.execute("SELECT result_json FROM bank_management_operations "
                    "WHERE management_operation_id = ?", (management_operation_id,)).fetchone()
                result = BankDemoManagementResult.model_validate_json(stored["result_json"])
                if result.status != "succeeded":
                    result = result.model_copy(update={"status": "failed", "error":
                        BankError(code="BANK_UNAVAILABLE", details={"reason": "reset_incomplete"})})
                    self._save(connection, result)
            return result
        self.clear_faults()
        return result

    @staticmethod
    def _restore_seeds(connection, at: datetime) -> None:
        # Child tables first; management receipts and round state deliberately
        # survive. The platform must have drained every higher-level worker.
        for table in ("bank_verification_submissions", "bank_verification_records",
                      "bank_verification_retirements", "bank_verification_challenges",
                      "bank_subscription_requests", "bank_subscriptions", "order_payments",
                      "orders", "freezes", "ledger_entries", "bank_operation_scopes",
                      "bank_operations", "accounts"):
            connection.execute(f"DELETE FROM {table}")
        seed_file = Path(__file__).parent / "seeds" / "accounts.json"
        for row in json.loads(seed_file.read_text(encoding="utf-8")):
            if not row["evaluation_only"]:
                connection.execute("INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row["account_id"], row["user_id"], row["account_type"], row["account_status"],
                     row["book_balance_fen"], row["frozen_balance_fen"], row["version"]))
        for row in build_flow_rows(at) + build_flow_rows(at, filename=subscriptions.FLOW_SEED_FILE):
            connection.execute("""INSERT INTO ledger_entries (
                transaction_id, account_id, user_id, operation_id, amount_fen, direction,
                nature, category, occurred_at, counterparty_id, counterparty_name,
                counterparty_account_masked, channel, summary, original_transaction_id,
                original_occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["transaction_id"], row["account_id"], row["user_id"], "seed:" + row["transaction_id"],
                 row["amount_fen"], row["direction"], row["nature"], row["category"], row["occurred_at"],
                 row.get("counterparty_id"), row["counterparty_name"], row.get("counterparty_account_masked"),
                 row.get("channel"), row["summary"], row.get("original_transaction_id"),
                 row.get("original_occurred_at")))
        subscriptions.seed(connection, at)
