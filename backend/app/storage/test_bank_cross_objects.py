"""Ticket v05-cross-platform/06: birthday bank objects commit atomically with operations."""

import pytest

from app.storage.database import connect
from app.storage.mock_bank.repository import (
    BankAccount, FreezeCapture, FreezeOpening, FreezeRelease, MockBankStore, OrderCreation,
)


NOW = "2026-10-24T10:00:00+08:00"
LATER = "2026-10-24T12:00:00+08:00"


def seeded(tmp_path):
    store = MockBankStore(tmp_path / "bank.sqlite3")
    store.seed_account(BankAccount("A1", "U1", "class_i", "active", 100000, 0, 0))
    return store


def freeze_op(store, operation_id="11111111-1111-4111-8111-111111111111"):
    return store.commit_operation(
        "U1", operation_id, "bank.freeze_funds",
        {"account_id": "A1", "amount_fen": 50000, "reason": "生日"},
        "succeeded", {"freeze_id": "f1"}, NOW,
        [("A1", 0, 100000, 50000)], [],
        (FreezeOpening("f1", "A1", 50000),),
    )


def create_order_op(store, operation_id="22222222-2222-4222-8222-222222222222"):
    return store.commit_operation(
        "U1", operation_id, "bank.create_order",
        {"product_id": "p_flower", "quantity": 1, "expected_total_fen": 19900},
        "succeeded", {"order_id": "o1"}, NOW, [], [],
        (OrderCreation("o1", "p_flower", 1, "m_flower", "花店", 19900, 19900, NOW,
                       LATER, "张*", "****1234", "某市****"),),
    )


def capture_op(store, operation_id="33333333-3333-4333-8333-333333333333",
               amount_fen=46700, order_id="o1", transaction_id="TX1",
               freeze_amount=46700):
    account = store.get_account("U1", "A1")
    book = account.book_balance_fen - amount_fen
    frozen = account.frozen_balance_fen - freeze_amount
    return store.commit_operation(
        "U1", operation_id, "bank.capture_frozen",
        {"freeze_id": "f1", "amount_fen": freeze_amount, "order_id": order_id},
        "succeeded", {"transaction_id": transaction_id}, LATER,
        [("A1", account.version, book, frozen)],
        [(transaction_id, "A1", amount_fen, "outflow", "consumption", "shopping", LATER)],
        (FreezeCapture("f1", freeze_amount, transaction_id, order_id, LATER),),
    )


def test_freeze_capture_release_land_together_or_not_at_all(tmp_path):
    store = seeded(tmp_path)
    assert freeze_op(store).status == "succeeded"
    assert store.get_freeze("U1", "f1")["original_amount_fen"] == 50000
    assert store.get_account("U1", "A1").frozen_balance_fen == 50000

    create_order_op(store)
    assert store.get_order("U1", "o1")["payment_status"] == "unpaid"

    capture_op(store)
    order = store.get_order("U1", "o1")
    assert order["payment_status"] == "paid"
    assert order["payment_transaction_id"] == "TX1"
    freeze = store.get_freeze("U1", "f1")
    assert (freeze["captured_total_fen"], freeze["released_total_fen"]) == (46700, 0)
    account = store.get_account("U1", "A1")
    assert (account.book_balance_fen, account.frozen_balance_fen) == (53300, 3300)

    release = store.commit_operation(
        "U1", "44444444-4444-4444-8444-444444444444", "bank.release_frozen",
        {"freeze_id": "f1", "amount_fen": 3300},
        "succeeded", {"released_amount_fen": 3300}, LATER,
        [("A1", account.version, 53300, 0)], [],
        (FreezeRelease("f1", 3300),),
    )
    assert release.status == "succeeded"
    freeze = store.get_freeze("U1", "f1")
    assert (freeze["captured_total_fen"], freeze["released_total_fen"]) == (46700, 3300)
    assert store.get_account("U1", "A1").frozen_balance_fen == 0
    assert len(store.list_ledger("U1", "A1")) == 1


def test_same_operation_replays_and_different_parameters_are_rejected(tmp_path):
    store = seeded(tmp_path)
    first = freeze_op(store)
    replay = freeze_op(store)
    assert replay.result == first.result
    with pytest.raises(ValueError):
        store.commit_operation(
            "U1", "11111111-1111-4111-8111-111111111111", "bank.freeze_funds",
            {"account_id": "A1", "amount_fen": 60000, "reason": "生日"},
            "succeeded", {"freeze_id": "f1"}, NOW,
            [("A1", 0, 100000, 60000)], [],
            (FreezeOpening("f1", "A1", 60000),),
        )
    # The rejected replay moved nothing: one freeze, account version unchanged.
    assert store.get_freeze("U1", "f1")["original_amount_fen"] == 50000
    assert store.get_account("U1", "A1").version == 1


def test_one_order_pays_once_even_with_a_new_operation_number(tmp_path):
    store = seeded(tmp_path)
    freeze_op(store)
    create_order_op(store)
    capture_op(store)
    account = store.get_account("U1", "A1")
    with pytest.raises(ValueError):
        capture_op(store, operation_id="55555555-5555-4555-8555-555555555555",
                   transaction_id="TX2")
    # The whole second payment rolled back: money, freeze sums, order and ledger.
    assert store.get_account("U1", "A1").version == account.version
    assert store.get_freeze("U1", "f1")["captured_total_fen"] == 46700
    assert store.get_order("U1", "o1")["payment_transaction_id"] == "TX1"
    assert [row["transaction_id"] for row in store.list_ledger("U1", "A1")] == ["TX1"]


def test_processing_unknown_keeps_effects_for_the_finalize(tmp_path):
    store = seeded(tmp_path)
    store.commit_operation(
        "U1", "66666666-6666-4666-8666-666666666666", "bank.freeze_funds",
        {"account_id": "A1", "amount_fen": 50000, "reason": "生日"},
        "processing", {}, NOW, [], [],
    )
    # An unknown outcome never carries half of its effects with it.
    with pytest.raises(ValueError):
        store.commit_operation(
            "U1", "99999999-9999-4999-8999-999999999999", "bank.freeze_funds",
            {"account_id": "A1", "amount_fen": 50000, "reason": "生日"},
            "processing", {}, NOW, [], [],
            (FreezeOpening("f0", "A1", 50000),),
        )
    assert store.get_operation("U1", "66666666-6666-4666-8666-666666666666").status == "processing"
    assert store.get_freeze("U1", "f9") is None
    finalized = store.finalize_operation(
        "U1", "66666666-6666-4666-8666-666666666666", "bank.freeze_funds",
        {"account_id": "A1", "amount_fen": 50000, "reason": "生日"},
        "succeeded", {"freeze_id": "f9"}, LATER,
        [("A1", 0, 100000, 50000)], [],
        (FreezeOpening("f9", "A1", 50000),),
    )
    assert finalized.status == "succeeded"
    assert store.get_freeze("U1", "f9")["original_amount_fen"] == 50000
    again = store.finalize_operation(
        "U1", "66666666-6666-4666-8666-666666666666", "bank.freeze_funds",
        {"account_id": "A1", "amount_fen": 50000, "reason": "生日"},
        "succeeded", {"freeze_id": "f9"}, LATER,
        [("A1", 1, 100000, 50000)], [],
        (FreezeOpening("f9", "A1", 50000),),
    )
    assert again.status == "succeeded"
    assert store.get_account("U1", "A1").version == 1


def test_object_failure_rolls_back_the_money_moves_too(tmp_path):
    store = seeded(tmp_path)
    freeze_op(store)
    create_order_op(store)
    account = store.get_account("U1", "A1")
    with pytest.raises(ValueError):
        store.commit_operation(
            "U1", "77777777-7777-4777-8777-777777777777", "bank.capture_frozen",
            {"freeze_id": "missing", "amount_fen": 100},
            "succeeded", {"transaction_id": "TX9"}, LATER,
            [("A1", account.version, account.book_balance_fen - 100,
              account.frozen_balance_fen - 100)],
            [("TX9", "A1", 100, "outflow", "consumption", "shopping", LATER)],
            (FreezeCapture("missing", 100, "TX9", None, LATER),),
        )
    after = store.get_account("U1", "A1")
    assert (after.version, after.book_balance_fen) == (account.version, account.book_balance_fen)
    assert store.list_ledger("U1", "A1") == []
    # A foreign user reaches neither the freeze nor the order.
    assert store.get_freeze("U2", "f1") is None
    assert store.get_order("U2", "o1") is None
    with pytest.raises(ValueError):
        store.commit_operation(
            "U2", "88888888-8888-4888-8888-888888888888", "bank.capture_frozen",
            {"freeze_id": "f1", "amount_fen": 100},
            "succeeded", {"transaction_id": "TX8"}, LATER, [], [],
            (FreezeCapture("f1", 100, "TX8", None, LATER),),
        )
    assert store.get_freeze("U1", "f1")["captured_total_fen"] == 0


def test_restart_and_v3_upgrade_keep_old_and_new_records_readable(tmp_path):
    path = tmp_path / "bank.sqlite3"
    store = seeded(tmp_path)
    freeze_op(store)
    create_order_op(store)
    capture_op(store)

    reopened = MockBankStore(path)
    assert reopened.get_freeze("U1", "f1")["captured_total_fen"] == 46700
    assert reopened.get_order("U1", "o1")["payment_status"] == "paid"
    assert len(reopened.list_ledger("U1", "A1")) == 1

    with connect(path) as connection:
        connection.execute("DROP TABLE order_payments")
        connection.execute("DROP TABLE orders")
        connection.execute("DROP TABLE freezes")
        connection.execute("PRAGMA user_version = 3")
        connection.commit()
    upgraded = MockBankStore(path)
    assert upgraded.get_operation(
        "U1", "33333333-3333-4333-8333-333333333333",
    ).status == "succeeded"
    assert len(upgraded.list_ledger("U1", "A1")) == 1
    assert upgraded.get_freeze("U1", "f1") is None
