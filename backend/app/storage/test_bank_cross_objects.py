"""Ticket v05-cross-platform/06 + v05-bank-round-objects/01: bank objects."""

import pytest

from app.storage.database import connect
from app.storage.mock_bank.repository import (
    LEDGER_SCHEMA, SCHEMA_VERSION, BankAccount, FreezeCapture, FreezeOpening,
    FreezeRelease, MockBankStore, OrderCreation,
)


NOW = "2026-10-24T10:00:00+08:00"
LATER = "2026-10-24T12:00:00+08:00"


def seeded(tmp_path):
    store = MockBankStore(tmp_path / "bank.sqlite3")
    store.seed_account(BankAccount("A1", "U1", "class_i", "active", 100000, 0, 0))
    return store


def freeze_op(store, operation_id="11111111-1111-4111-8111-111111111111",
              demo_round_id=None):
    return store.commit_operation(
        "U1", operation_id, "bank.freeze_funds",
        {"account_id": "A1", "amount_fen": 50000, "reason": "生日"},
        "succeeded", {"freeze_id": "f1"}, NOW,
        [("A1", 0, 100000, 50000)], [],
        (FreezeOpening("f1", "A1", 50000),),
        demo_round_id=demo_round_id,
    )


def create_order_op(store, operation_id="22222222-2222-4222-8222-222222222222",
                    order_id="o1", demo_round_id=None):
    return store.commit_operation(
        "U1", operation_id, "bank.create_order",
        {"product_id": "p_flower", "quantity": 1, "expected_total_fen": 19900},
        "succeeded", {"order_id": order_id}, NOW, [], [],
        (OrderCreation(order_id=order_id, product_id="p_flower", quantity=1,
                       merchant_id="m_flower", merchant_name="花店",
                       total_fen=19900, expected_total_fen=19900, created_at=NOW,
                       deliver_by=LATER, recipient_name_masked="张*",
                       phone_masked="****1234", address_masked="某市****"),),
        demo_round_id=demo_round_id,
    )


def capture_op(store, operation_id="33333333-3333-4333-8333-333333333333",
               amount_fen=46700, order_id="o1", transaction_id="TX1",
               freeze_amount=46700, annotate=True, demo_round_id=None):
    account = store.get_account("U1", "A1")
    book = account.book_balance_fen - amount_fen
    frozen = account.frozen_balance_fen - freeze_amount
    return store.commit_operation(
        "U1", operation_id, "bank.capture_frozen",
        {"freeze_id": "f1", "amount_fen": freeze_amount, "order_id": order_id},
        "succeeded", {"transaction_id": transaction_id}, LATER,
        [("A1", account.version, book, frozen)],
        [(transaction_id, "A1", amount_fen, "outflow", "consumption", "shopping", LATER)],
        (FreezeCapture(
            freeze_id="f1", amount_fen=freeze_amount, transaction_id=transaction_id,
            order_id=order_id, paid_at=LATER,
            counterparty_id="m_flower" if annotate else None,
            counterparty_name="邻里花店" if annotate else None,
            summary="生日鲜花" if annotate else None,
        ),),
        demo_round_id=demo_round_id,
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
    ledger = store.list_ledger("U1", "A1")
    assert len(ledger) == 1
    # The capture annotated its own consumption row, so B08 can return it whole.
    assert ledger[0]["counterparty_id"] == "m_flower"
    assert ledger[0]["counterparty_name"] == "邻里花店"
    assert ledger[0]["summary"] == "生日鲜花"


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


def test_plain_capture_without_counterparty_facts_stays_bare(tmp_path):
    store = seeded(tmp_path)
    freeze_op(store)
    account = store.get_account("U1", "A1")
    plain = store.commit_operation(
        "U1", "12121212-1212-4121-8121-121212121212", "bank.capture_frozen",
        {"freeze_id": "f1", "amount_fen": 100, "order_id": None},
        "succeeded", {"transaction_id": "TX3"}, LATER,
        [("A1", account.version, account.book_balance_fen - 100,
          account.frozen_balance_fen - 100)],
        [("TX3", "A1", 100, "outflow", "consumption", "shopping", LATER)],
        (FreezeCapture(freeze_id="f1", amount_fen=100, transaction_id="TX3"),),
    )
    assert plain.status == "succeeded"
    row = store.list_ledger("U1", "A1")[0]
    assert row["counterparty_name"] is None and row["summary"] is None


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


def facts(store):
    account = store.get_account("U1", "A1")
    freeze = store.get_freeze("U1", "f1")
    orders = {}
    for order_id in ("o1", "o2"):
        order = store.get_order("U1", order_id)
        if order is not None:
            orders[order_id] = order["payment_status"]
    with connect(store.path) as connection:
        payments = [
            row["order_id"] for row in connection.execute(
                "SELECT order_id FROM order_payments ORDER BY order_id")
        ]
        operations = [
            row["operation_id"] for row in connection.execute(
                "SELECT operation_id FROM bank_operations ORDER BY operation_id")
        ]
    return (
        (account.version, account.book_balance_fen, account.frozen_balance_fen),
        (freeze["captured_total_fen"], freeze["released_total_fen"]),
        orders,
        [row["transaction_id"] for row in store.list_ledger("U1", "A1")],
        payments,
        operations,
    )


def test_objects_carry_the_creating_round_across_restart(tmp_path):
    path = tmp_path / "bank.sqlite3"
    store = seeded(tmp_path)
    freeze_op(store, demo_round_id="D1")
    create_order_op(store, demo_round_id="D1")

    assert store.get_freeze("U1", "f1")["demo_round_id"] == "D1"
    assert store.get_order("U1", "o1")["demo_round_id"] == "D1"
    reopened = MockBankStore(path)
    assert reopened.get_freeze("U1", "f1")["demo_round_id"] == "D1"
    assert reopened.get_order("U1", "o1")["demo_round_id"] == "D1"


def test_another_round_cannot_capture_or_release_the_freeze(tmp_path):
    store = seeded(tmp_path)
    freeze_op(store, demo_round_id="D1")
    create_order_op(store, demo_round_id="D1")
    before = facts(store)
    with pytest.raises(ValueError, match="freeze is not in scope"):
        capture_op(store, demo_round_id="D2")
    # The rejected operation and its effects are fully rolled back.
    assert facts(store) == before
    assert store.get_operation(
        "U1", "33333333-3333-4333-8333-333333333333") is None

    # Same-round control, then a release attempt from another round.
    capture_op(store, demo_round_id="D1")
    freeze = store.get_freeze("U1", "f1")
    account = store.get_account("U1", "A1")
    assert freeze["captured_total_fen"] == 46700
    assert (account.version, account.book_balance_fen, account.frozen_balance_fen) == (
        2, 53300, 3300)
    with pytest.raises(ValueError, match="freeze is not in scope"):
        store.commit_operation(
            "U1", "44444444-4444-4444-8444-444444444444", "bank.release_frozen",
            {"freeze_id": "f1", "amount_fen": 100},
            "succeeded", {"released_amount_fen": 100}, LATER,
            [("A1", account.version, account.book_balance_fen,
              account.frozen_balance_fen - 100)], [],
            (FreezeRelease("f1", 100),), demo_round_id="D2",
        )
    assert store.get_operation(
        "U1", "44444444-4444-4444-8444-444444444444") is None
    assert store.get_freeze("U1", "f1")["released_total_fen"] == 0
    released = store.commit_operation(
        "U1", "44444444-4444-4444-8444-444444444444", "bank.release_frozen",
        {"freeze_id": "f1", "amount_fen": 100},
        "succeeded", {"released_amount_fen": 100}, LATER,
        [("A1", account.version, account.book_balance_fen,
          account.frozen_balance_fen - 100)], [],
        (FreezeRelease("f1", 100),), demo_round_id="D1",
    )
    assert released.status == "succeeded"
    assert store.get_freeze("U1", "f1")["released_total_fen"] == 100


def test_another_round_order_cannot_be_paid_by_a_current_freeze(tmp_path):
    store = seeded(tmp_path)
    freeze_op(store, demo_round_id="D2")
    create_order_op(store, demo_round_id="D1")
    before = facts(store)
    with pytest.raises(ValueError, match="order is not in scope"):
        capture_op(store, demo_round_id="D2")
    assert facts(store) == before

    # Same-round control: a D2 order and the D2 freeze pay together.
    create_order_op(store, operation_id="22222222-2222-4222-8222-222222222223",
                    order_id="o2", demo_round_id="D2")
    capture_op(store, operation_id="33333333-3333-4333-8333-333333333334",
               order_id="o2", demo_round_id="D2")
    assert store.get_order("U1", "o1")["payment_status"] == "unpaid"
    assert store.get_order("U1", "o2")["payment_status"] == "paid"


def test_roundless_legacy_objects_are_outside_any_known_round(tmp_path):
    store = seeded(tmp_path)
    freeze_op(store)  # staged/test seam writes without a round
    assert store.get_freeze("U1", "f1")["demo_round_id"] is None
    account = store.get_account("U1", "A1")
    with pytest.raises(ValueError, match="freeze is not in scope"):
        store.commit_operation(
            "U1", "45454545-4545-4545-8545-454545454545", "bank.release_frozen",
            {"freeze_id": "f1", "amount_fen": 100},
            "succeeded", {"released_amount_fen": 100}, LATER,
            [("A1", account.version, account.book_balance_fen,
              account.frozen_balance_fen - 100)], [],
            (FreezeRelease("f1", 100),), demo_round_id="D1",
        )
    assert store.get_freeze("U1", "f1")["released_total_fen"] == 0


def write_v4_database(path, *, objects: tuple[str, ...] = ()) -> None:
    """Build a pre-round-ownership (user_version=4) bank database."""
    with connect(path) as connection:
        connection.execute("""
            CREATE TABLE accounts (
                account_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                account_type TEXT NOT NULL,
                account_status TEXT NOT NULL,
                book_balance_fen INTEGER NOT NULL,
                frozen_balance_fen INTEGER NOT NULL,
                version INTEGER NOT NULL DEFAULT 0
            )""")
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
            )""")
        connection.execute("""
            CREATE TABLE freezes (
                freeze_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(account_id),
                user_id TEXT NOT NULL,
                operation_id TEXT NOT NULL,
                original_amount_fen INTEGER NOT NULL,
                captured_total_fen INTEGER NOT NULL DEFAULT 0,
                released_total_fen INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
        connection.execute("""
            CREATE TABLE orders (
                order_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                merchant_id TEXT NOT NULL,
                merchant_name TEXT NOT NULL,
                total_fen INTEGER NOT NULL,
                expected_total_fen INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                deliver_by TEXT NOT NULL,
                recipient_name_masked TEXT NOT NULL,
                phone_masked TEXT NOT NULL,
                address_masked TEXT NOT NULL,
                payment_status TEXT NOT NULL DEFAULT 'unpaid'
                    CHECK(payment_status IN ('unpaid', 'paid')),
                payment_transaction_id TEXT,
                payment_operation_id TEXT
            )""")
        connection.execute("""
            CREATE TABLE order_payments (
                order_id TEXT PRIMARY KEY REFERENCES orders(order_id),
                capture_operation_id TEXT NOT NULL,
                transaction_id TEXT NOT NULL,
                paid_at TEXT NOT NULL
            )""")
        connection.execute(
            "INSERT INTO accounts VALUES ('A1', 'U1', 'class_i', 'active', 200000, 0, 0)")
        if "freezes" in objects:
            connection.execute(
                "INSERT INTO freezes VALUES ('f1', 'A1', 'U1', ?, 50000, 0, 0, ?, ?)",
                ("11111111-1111-4111-8111-111111111111", NOW, NOW),
            )
        if "orders" in objects:
            connection.execute(
                """INSERT INTO orders (order_id, user_id, product_id, quantity,
                   merchant_id, merchant_name, total_fen, expected_total_fen, created_at,
                   deliver_by, recipient_name_masked, phone_masked, address_masked,
                   payment_status)
                   VALUES ('o1', 'U1', 'p_flower', 1, 'm_flower', '花店', 19900, 19900,
                           ?, ?, '张*', '****1234', '某市****', 'unpaid')""",
                (NOW, LATER),
            )
        connection.execute("PRAGMA user_version = 4")
        connection.commit()


@pytest.mark.parametrize("objects", [
    ("freezes",), ("orders",), ("freezes", "orders"),
])
def test_v4_database_with_objects_is_refused_and_left_untouched(tmp_path, objects):
    path = tmp_path / "bank.sqlite3"
    write_v4_database(path, objects=objects)
    with pytest.raises(RuntimeError, match="demo round"):
        MockBankStore(path)
    with connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
        freeze = connection.execute("SELECT * FROM freezes").fetchone()
        order = connection.execute("SELECT * FROM orders").fetchone()
        if "freezes" in objects:
            assert (freeze["freeze_id"], freeze["original_amount_fen"]) == ("f1", 50000)
        else:
            assert freeze is None
        if "orders" in objects:
            assert (order["order_id"], order["payment_status"]) == ("o1", "unpaid")
        else:
            assert order is None
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(freezes)")
        }
        assert "demo_round_id" not in columns


def test_v4_database_without_objects_upgrades_to_v5_in_place(tmp_path):
    path = tmp_path / "bank.sqlite3"
    write_v4_database(path)
    store = MockBankStore(path)
    # The in-place upgrade keeps the existing account row untouched.
    assert store.get_account("U1", "A1").book_balance_fen == 200000
    store.seed_account(BankAccount("A1", "U1", "class_i", "active", 100000, 0, 0))
    with connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        tables = {
            row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "order_payments" in tables
        for name in ("freezes", "orders"):
            columns = {
                row["name"] for row in connection.execute(f"PRAGMA table_info({name})")
            }
            assert "demo_round_id" in columns

    assert freeze_op(store, demo_round_id="D1").status == "succeeded"
    assert store.get_freeze("U1", "f1")["demo_round_id"] == "D1"


def test_finalize_operation_writes_and_enforces_the_round(tmp_path):
    store = seeded(tmp_path)
    operation_id = "66666666-6666-4666-8666-666666666666"
    parameters = {"account_id": "A1", "amount_fen": 50000, "reason": "生日"}
    store.commit_operation(
        "U1", operation_id, "bank.freeze_funds", parameters,
        "processing", {}, NOW, [], [],
    )
    finalized = store.finalize_operation(
        "U1", operation_id, "bank.freeze_funds", parameters,
        "succeeded", {"freeze_id": "f9"}, LATER,
        [("A1", 0, 100000, 50000)], [],
        (FreezeOpening("f9", "A1", 50000),), demo_round_id="D1",
    )
    assert finalized.status == "succeeded"
    assert store.get_freeze("U1", "f9")["demo_round_id"] == "D1"

    # A later finalize for another processing operation is round-checked too.
    capture_id = "67676767-6767-4767-8767-676767676767"
    capture_parameters = {"freeze_id": "f9", "amount_fen": 100, "order_id": None}
    store.commit_operation(
        "U1", capture_id, "bank.capture_frozen", capture_parameters,
        "processing", {}, NOW, [], [],
    )
    account = store.get_account("U1", "A1")
    with pytest.raises(ValueError, match="freeze is not in scope"):
        store.finalize_operation(
            "U1", capture_id, "bank.capture_frozen", capture_parameters,
            "succeeded", {"transaction_id": "TX7"}, LATER,
            [("A1", account.version, account.book_balance_fen - 100,
              account.frozen_balance_fen - 100)],
            [("TX7", "A1", 100, "outflow", "consumption", "shopping", LATER)],
            (FreezeCapture(freeze_id="f9", amount_fen=100, transaction_id="TX7"),),
            demo_round_id="D2",
        )
    assert store.get_operation("U1", capture_id).status == "processing"
    assert store.get_freeze("U1", "f9")["captured_total_fen"] == 0
    settled = store.finalize_operation(
        "U1", capture_id, "bank.capture_frozen", capture_parameters,
        "succeeded", {"transaction_id": "TX7"}, LATER,
        [("A1", account.version, account.book_balance_fen - 100,
          account.frozen_balance_fen - 100)],
        [("TX7", "A1", 100, "outflow", "consumption", "shopping", LATER)],
        (FreezeCapture(freeze_id="f9", amount_fen=100, transaction_id="TX7"),),
        demo_round_id="D1",
    )
    assert settled.status == "succeeded"
    assert store.get_freeze("U1", "f9")["captured_total_fen"] == 100
