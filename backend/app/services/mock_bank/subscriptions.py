"""Bank-owned auto-debit mandates: a self-contained table, relative seeds and row access.

Scenario 05 (B29/B30) needs signed-agreement facts that no other bank capability owns.
The table is created and read only from this module, so the shared storage layer stays
unaware of subscriptions and the bank database keeps one writer per table.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3

from app.contracts.subscription import SubscriptionMandate

from .flow_seeds import shift_months


SEEDS_DIR = Path(__file__).parent / "seeds"
MANDATE_SEED_FILE = "subscriptions.json"
FLOW_SEED_FILE = "subscription_flows.json"
# Auto-debits happen at the bank's own debit hour, never at the instant of the query.
BILLING_HOUR = 9

SCHEMA = """CREATE TABLE IF NOT EXISTS bank_subscriptions (
    mandate_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    account_masked TEXT NOT NULL,
    merchant_id TEXT NOT NULL,
    merchant_name TEXT NOT NULL,
    service_name TEXT NOT NULL,
    amount_fen INTEGER NOT NULL,
    cycle TEXT NOT NULL,
    next_billing_at TEXT,
    last_billed_at TEXT,
    status TEXT NOT NULL,
    signed_at TEXT NOT NULL,
    cancelled_at TEXT,
    cancel_operation_id TEXT
)"""


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(SCHEMA)


def _billing_at(value: datetime) -> datetime:
    return value.replace(hour=BILLING_HOUR, minute=0, second=0, microsecond=0)


def _months_back(at: datetime, months: int | None) -> datetime | None:
    return None if months is None else _billing_at(shift_months(at, months))


def _seed_mandate(seed: dict, at: datetime) -> SubscriptionMandate:
    """Resolve one relative seed row into a contracted bank fact.

    Offsets are relative to the bank clock, so a demo run on any date gets the same
    relative story (next debit in a few days, last debit a month ago) and the test
    only has to inject a fixed clock.
    """
    next_days = seed.get("next_billing_day_offset")
    return SubscriptionMandate(
        mandate_id=seed["mandate_id"], account_id=seed["account_id"],
        account_masked=seed["account_masked"], merchant_id=seed["merchant_id"],
        merchant_name=seed["merchant_name"], service_name=seed["service_name"],
        amount_fen=seed["amount_fen"], cycle=seed["cycle"],
        next_billing_at=(None if next_days is None
                         else _billing_at(at + timedelta(days=next_days))),
        last_billed_at=_months_back(at, seed.get("last_billed_month_offset")),
        status=seed["status"], signed_at=_months_back(at, seed["signed_month_offset"]),
        cancelled_at=_months_back(at, seed.get("cancelled_month_offset")),
        cancel_operation_id=seed.get("cancel_operation_id"),
    )


def seed(connection: sqlite3.Connection, at: datetime) -> int:
    """Write the seeded mandates once and report how many rows were new.

    An existing row is never overwritten: a cancellation made during the demo must
    survive every later restart, and the JSON stays the only definition of the rest.
    """
    seeds = json.loads((SEEDS_DIR / MANDATE_SEED_FILE).read_text(encoding="utf-8"))
    written = 0
    for seed_row in seeds:
        mandate = _seed_mandate(seed_row, at)
        written += connection.execute(
            """INSERT OR IGNORE INTO bank_subscriptions (
               mandate_id, user_id, account_id, account_masked, merchant_id, merchant_name,
               service_name, amount_fen, cycle, next_billing_at, last_billed_at, status,
               signed_at, cancelled_at, cancel_operation_id)
               VALUES (:mandate_id, :user_id, :account_id, :account_masked, :merchant_id,
               :merchant_name, :service_name, :amount_fen, :cycle, :next_billing_at,
               :last_billed_at, :status, :signed_at, :cancelled_at, :cancel_operation_id)""",
            {"user_id": seed_row["user_id"], **mandate.model_dump(mode="json")},
        ).rowcount
    return written


def _mandate(row: sqlite3.Row) -> SubscriptionMandate:
    return SubscriptionMandate(
        mandate_id=row["mandate_id"], account_id=row["account_id"],
        account_masked=row["account_masked"], merchant_id=row["merchant_id"],
        merchant_name=row["merchant_name"], service_name=row["service_name"],
        amount_fen=row["amount_fen"], cycle=row["cycle"], next_billing_at=row["next_billing_at"],
        last_billed_at=row["last_billed_at"], status=row["status"], signed_at=row["signed_at"],
        cancelled_at=row["cancelled_at"], cancel_operation_id=row["cancel_operation_id"],
    )


def list_mandates(connection: sqlite3.Connection, user_id: str, account_id: str | None = None,
                  status: str | None = None) -> list[SubscriptionMandate]:
    """This user's mandates in mandate_id order, narrowed by the filters that were passed."""
    query = "SELECT * FROM bank_subscriptions WHERE user_id = ?"
    parameters: list[str] = [user_id]
    if account_id is not None:
        query += " AND account_id = ?"
        parameters.append(account_id)
    if status is not None:
        query += " AND status = ?"
        parameters.append(status)
    return [_mandate(row) for row in connection.execute(query + " ORDER BY mandate_id", parameters)]


def get_mandate(connection: sqlite3.Connection,
                mandate_id: str) -> tuple[str, SubscriptionMandate] | None:
    """One mandate with its owner, whoever asks; the bank decides who may see it."""
    row = connection.execute(
        "SELECT * FROM bank_subscriptions WHERE mandate_id = ?", (mandate_id,),
    ).fetchone()
    return None if row is None else (row["user_id"], _mandate(row))


def cancel_mandate(connection: sqlite3.Connection, user_id: str, mandate_id: str,
                   operation_id: str, at: datetime) -> None:
    """Stop the next and later debits of this user's active mandate; history is untouched."""
    connection.execute(
        """UPDATE bank_subscriptions
           SET status = 'cancelled', next_billing_at = NULL, cancelled_at = ?,
               cancel_operation_id = ?
           WHERE mandate_id = ? AND user_id = ? AND status = 'active'""",
        (at.isoformat(), operation_id, mandate_id, user_id),
    )
