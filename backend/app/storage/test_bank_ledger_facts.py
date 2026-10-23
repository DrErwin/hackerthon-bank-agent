"""Bank ledger fact columns and idempotent seeding for the frozen B08 seam (Issue #91)."""

import sqlite3

import pytest

from app.storage import StoragePaths
from app.storage.mock_bank.repository import (
    LEDGER_FACT_COLUMNS, SCHEMA_VERSION, BankAccount, MockBankStore,
)

NOW = "2026-10-01T09:00:00+08:00"
EARLIER = "2026-09-12T12:30:00+08:00"


def ledger_row(**overrides):
    return {
        "transaction_id": "TX1", "account_id": "A1", "user_id": "U1",
        "amount_fen": 3200, "direction": "outflow", "nature": "consumption",
        "category": "dining", "occurred_at": NOW,
        "counterparty_id": "M1", "counterparty_name": "楼下面馆",
        "counterparty_account_masked": None, "channel": "快捷支付", "summary": "午餐",
        "original_transaction_id": None, "original_occurred_at": None,
    } | overrides


def seeded_store(tmp_path):
    store = MockBankStore(StoragePaths(tmp_path).bank)
    store.seed_account(BankAccount("A1", "U1", "class_i", "active", 100000, 0, 0))
    store.seed_account(BankAccount("A5", "U1", "class_i", "active", 0, 0, 0))
    return store


def test_seed_ledger_rows_keeps_facts_and_existing_order(tmp_path):
    store = seeded_store(tmp_path)
    assert store.seed_ledger_rows([
        ledger_row(transaction_id="TX2", occurred_at=EARLIER),
        ledger_row(transaction_id="TX1", occurred_at=NOW),
    ]) == 2
    rows = store.list_ledger("U1", "A1")
    assert [row["transaction_id"] for row in rows] == ["TX2", "TX1"]
    assert (rows[0]["counterparty_id"], rows[0]["counterparty_name"],
            rows[0]["channel"], rows[0]["summary"]) == ("M1", "楼下面馆", "快捷支付", "午餐")
    assert rows[0]["counterparty_account_masked"] is None
    assert rows[0]["original_transaction_id"] is None
    assert rows[0]["operation_id"] == "seed:TX2"


def test_seeded_refund_keeps_its_original_occurrence(tmp_path):
    store = seeded_store(tmp_path)
    store.seed_ledger_rows([ledger_row(
        transaction_id="TX9", nature="refund", direction="inflow", amount_fen=3200,
        original_transaction_id="TX1", original_occurred_at=EARLIER,
    )])
    row = store.list_ledger("U1", "A1")[0]
    assert (row["nature"], row["direction"], row["original_transaction_id"],
            row["original_occurred_at"]) == ("refund", "inflow", "TX1", EARLIER)


def test_seed_ledger_rows_is_idempotent_and_scoped_to_owned_accounts(tmp_path):
    store = seeded_store(tmp_path)
    rows = [ledger_row(), ledger_row(transaction_id="TX2", account_id="A5")]
    assert store.seed_ledger_rows(rows) == 2
    assert store.seed_ledger_rows(rows) == 0
    assert len(store.list_ledger("U1", "A1")) == 1
    assert len(store.list_ledger("U1", "A5")) == 1
    with pytest.raises(ValueError, match="not in scope"):
        store.seed_ledger_rows([ledger_row(transaction_id="TX3", user_id="U2")])
    assert len(store.list_ledger("U1", "A1")) == 1
    assert MockBankStore(store.path).list_ledger("U1", "A1")[0]["counterparty_name"] == "楼下面馆"


def test_fresh_bank_database_is_created_at_the_fact_schema(tmp_path):
    path = StoragePaths(tmp_path).bank
    MockBankStore(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        columns = {row[1] for row in connection.execute("PRAGMA table_info(ledger_entries)")}
    assert set(LEDGER_FACT_COLUMNS) <= columns


def test_bank_v1_database_without_ledger_table_reaches_the_fact_schema(tmp_path):
    path = StoragePaths(tmp_path).bank
    with sqlite3.connect(path) as connection:
        connection.executescript(f"""
            CREATE TABLE bank_operations (
                operation_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, action_name TEXT NOT NULL,
                parameters_digest TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            );
            INSERT INTO bank_operations VALUES
                ('old', 'U1', 'bank.submit_transfer', 'digest', 'processing', '{{}}', '{NOW}');
            PRAGMA user_version = 1;
        """)
    store = MockBankStore(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        columns = {row[1] for row in connection.execute("PRAGMA table_info(ledger_entries)")}
    assert set(LEDGER_FACT_COLUMNS) <= columns
    assert store.get_operation("U1", "old").updated_at == NOW


def test_newer_bank_database_is_refused(tmp_path):
    path = StoragePaths(tmp_path).bank
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    with pytest.raises(RuntimeError, match="newer"):
        MockBankStore(path)


def test_seed_ledger_rows_does_not_mistake_a_rejected_row_for_an_existing_one(tmp_path):
    store = seeded_store(tmp_path)
    with pytest.raises(ValueError, match="rejected"):
        store.seed_ledger_rows([ledger_row(nature=None)])
    assert store.list_ledger("U1", "A1") == []


def test_seeded_rows_must_be_able_to_become_bank_facts(tmp_path):
    store = seeded_store(tmp_path)
    missing_summary = {key: value for key, value in ledger_row().items() if key != "summary"}
    for incomplete in (ledger_row(summary=None), ledger_row(counterparty_name=None),
                       ledger_row(amount_fen=-1), missing_summary):
        with pytest.raises(ValueError, match="seeded ledger row"):
            store.seed_ledger_rows([incomplete])
    assert store.list_ledger("U1", "A1") == []


def test_bank_v2_ledger_migrates_to_v3_without_losing_rows(tmp_path):
    path = StoragePaths(tmp_path).bank
    with sqlite3.connect(path) as connection:
        connection.executescript(f"""
            CREATE TABLE accounts (
                account_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, account_type TEXT NOT NULL,
                account_status TEXT NOT NULL, book_balance_fen INTEGER NOT NULL,
                frozen_balance_fen INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE ledger_entries (
                transaction_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(account_id),
                user_id TEXT NOT NULL, operation_id TEXT NOT NULL, amount_fen INTEGER NOT NULL,
                direction TEXT NOT NULL, nature TEXT NOT NULL, category TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            );
            CREATE TABLE bank_operations (
                operation_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, action_name TEXT NOT NULL,
                parameters_digest TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            INSERT INTO accounts VALUES ('A1', 'U1', 'class_i', 'active', 100000, 0, 0);
            INSERT INTO ledger_entries VALUES
                ('TX1', 'A1', 'U1', 'OP1', 3200, 'outflow', 'consumption', 'dining', '{EARLIER}');
            PRAGMA user_version = 2;
        """)

    store = MockBankStore(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert store.list_ledger("U1", "A1") == [{
        "transaction_id": "TX1", "account_id": "A1", "user_id": "U1", "operation_id": "OP1",
        "amount_fen": 3200, "direction": "outflow", "nature": "consumption",
        "category": "dining", "occurred_at": EARLIER, "counterparty_id": None,
        "counterparty_name": None, "counterparty_account_masked": None, "channel": None,
        "summary": None, "original_transaction_id": None, "original_occurred_at": None,
    }]
    assert store.seed_ledger_rows([ledger_row(transaction_id="TX2")]) == 1
    assert MockBankStore(path).list_ledger("U1", "A1")[1]["summary"] == "午餐"


def test_existing_operation_writes_leave_ledger_facts_empty(tmp_path):
    store = seeded_store(tmp_path)
    store.commit_operation(
        "U1", "OP1", "bank.submit_transfer", {"amount_fen": 3200}, "succeeded",
        {"operation_status": "succeeded"}, NOW, [("A1", 0, 96800, 0)],
        [("TX1", "A1", 3200, "outflow", "transfer", "transfer", NOW)],
    )
    row = store.list_ledger("U1", "A1")[0]
    assert row["summary"] is None and row["counterparty_name"] is None
    assert row["operation_id"] == "OP1"
