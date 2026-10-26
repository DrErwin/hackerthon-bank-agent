"""Ticket v05-cross-platform/07 + v05-bank-round-objects/02: birthday bank service."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.contracts.bank import (
    BankError, CaptureFrozenInput, CreateOrderInput, DeliveryInput, FreezeFundsInput,
    FreezeView, QueryFailure, ReleaseFrozenInput,
)
from app.contracts.common import Category, OperationStatus
from app.contracts.platform import TrustedContext
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService, _now
from app.storage.database import connect
from app.storage.mock_bank.repository import (
    BankAccount, FreezeOpening, MockBankStore, OrderCreation,
)


def context() -> TrustedContext:
    return TrustedContext(user_id="U1", session_id="S1", task_id="T1", run_id="R1",
                          parent_task_id=None, demo_round_id="D1")


def bank_with_account(tmp_path):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite3"), demo_secret=b"s" * 32)
    bank.store.seed_account(BankAccount("BA1", "U1", "class_i", "active", 200000, 0, 0))
    return bank


def gateway(bank, **kwargs):
    return BankGateway(bank, authorize_birthday=lambda *_: True, **kwargs)


def table_count(store, table):
    with connect(store.path) as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def delivery(deliver_by) -> DeliveryInput:
    return DeliveryInput(recipient_name="张三", phone="13800001234",
                         address="北京市西城区金融街 1 号", deliver_by=deliver_by)


def op() -> "object":
    return uuid4()


def ok_write(result):
    assert not isinstance(result, QueryFailure), result
    assert result.operation_status is OperationStatus.SUCCEEDED
    return result


def test_freeze_capture_release_matches_the_confirmed_amounts(tmp_path):
    bank = bank_with_account(tmp_path)
    gate = gateway(bank)

    frozen = ok_write(gate.freeze_funds(context(), op(), FreezeFundsInput(
        account_id="BA1", amount_fen=50000, reason="生日")))
    freeze_id = frozen.receipt.freeze_id
    assert frozen.receipt.balance.frozen_balance_fen == 50000

    captured = ok_write(gate.capture_frozen(context(), op(), CaptureFrozenInput(
        freeze_id=freeze_id, amount_fen=46700, merchant_id="m_flower",
        merchant_name="邻里花店", purpose="生日鲜花", category=Category.SHOPPING)))
    assert captured.receipt.remaining_fen == 3300
    account = bank.store.get_account("U1", "BA1")
    assert (account.book_balance_fen, account.frozen_balance_fen) == (153300, 3300)

    released = ok_write(gate.release_frozen(context(), op(), ReleaseFrozenInput(
        freeze_id=freeze_id, amount_fen=3300)))
    assert released.receipt.remaining_fen == 0
    account = bank.store.get_account("U1", "BA1")
    assert (account.book_balance_fen, account.frozen_balance_fen) == (153300, 0)

    view = gate.get_freeze(context(), freeze_id).data
    assert isinstance(view, FreezeView)
    assert (view.captured_total_fen, view.released_total_fen, view.remaining_fen) == (46700, 3300, 0)
    # The freeze and its release never became consumption or income rows.
    ledger = bank.store.list_ledger("U1", "BA1")
    assert [row["nature"] for row in ledger] == ["consumption"]
    assert ledger[0]["amount_fen"] == 46700

    # B14 rebuilds each typed receipt for the new write actions.
    for operation_id in (frozen.operation_id, captured.operation_id, released.operation_id):
        lookup = gate.get_operation(context(), operation_id)
        assert lookup.lookup == "found"
        assert lookup.operation.operation_status is OperationStatus.SUCCEEDED


def test_order_pays_once_and_releases_the_rest(tmp_path):
    bank = bank_with_account(tmp_path)
    gate = gateway(bank)
    who = context()
    frozen = ok_write(gate.freeze_funds(who, op(), FreezeFundsInput(
        account_id="BA1", amount_fen=50000, reason="生日")))
    freeze_id = frozen.receipt.freeze_id

    order = ok_write(gate.create_order(who, op(), CreateOrderInput(
        product_id="p_flower", quantity=1, expected_total_fen=19900,
        delivery=delivery(_now() + timedelta(hours=30)))))
    order_view = order.receipt.order
    assert order_view.payment_status == "unpaid"
    assert order_view.recipient_name_masked == "张*"
    assert order_view.phone_masked == "****1234"
    assert "金融街" not in order_view.address_masked

    paid = ok_write(gate.capture_frozen(who, op(), CaptureFrozenInput(
        freeze_id=freeze_id, amount_fen=19900, merchant_id="m_flower",
        merchant_name="邻里花店", purpose="生日鲜花", category=Category.SHOPPING,
        order_id=order_view.order_id)))
    stored = gate.get_order(who, order_view.order_id).data.order
    assert stored.payment_status == "paid"
    assert stored.payment_transaction_id == paid.receipt.transaction_id

    # A second operation number cannot pay the same order again.
    duplicate = gate.capture_frozen(who, op(), CaptureFrozenInput(
        freeze_id=freeze_id, amount_fen=19900, merchant_id="m_flower",
        merchant_name="邻里花店", purpose="生日鲜花", category=Category.SHOPPING,
        order_id=order_view.order_id))
    assert duplicate.operation_status is OperationStatus.FAILED
    assert duplicate.failure.code == "ORDER_PAYMENT_MISMATCH"
    assert bank.store.get_account("U1", "BA1").book_balance_fen == 180100

    released = ok_write(gate.release_frozen(who, op(), ReleaseFrozenInput(
        freeze_id=freeze_id, amount_fen=30100)))
    assert released.receipt.remaining_fen == 0
    assert bank.store.get_account("U1", "BA1").frozen_balance_fen == 0


def test_replay_and_parameter_conflict_behave_like_transfers(tmp_path):
    bank = bank_with_account(tmp_path)
    gate = gateway(bank)
    operation_id = op()
    request = FreezeFundsInput(account_id="BA1", amount_fen=50000, reason="生日")
    first = ok_write(gate.freeze_funds(context(), operation_id, request))
    replay = ok_write(gate.freeze_funds(context(), operation_id, request))
    assert replay.receipt.freeze_id == first.receipt.freeze_id
    conflict = gate.freeze_funds(context(), operation_id, FreezeFundsInput(
        account_id="BA1", amount_fen=60000, reason="生日"))
    assert isinstance(conflict, QueryFailure)
    assert conflict.error.code == "OPERATION_CONFLICT"
    assert bank.store.get_account("U1", "BA1").frozen_balance_fen == 50000


def test_bank_rule_failures_are_recorded_not_guesswork(tmp_path):
    bank = bank_with_account(tmp_path)
    gate = gateway(bank)
    who = context()

    insufficient = gate.freeze_funds(who, op(), FreezeFundsInput(
        account_id="BA1", amount_fen=500000, reason="生日"))
    assert insufficient.operation_status is OperationStatus.FAILED
    assert insufficient.failure.code == "INSUFFICIENT_FUNDS"
    assert bank.store.get_account("U1", "BA1").frozen_balance_fen == 0

    frozen = ok_write(gate.freeze_funds(who, op(), FreezeFundsInput(
        account_id="BA1", amount_fen=50000, reason="生日")))
    freeze_id = frozen.receipt.freeze_id
    over_release = gate.release_frozen(who, op(), ReleaseFrozenInput(
        freeze_id=freeze_id, amount_fen=50001))
    assert over_release.operation_status is OperationStatus.FAILED
    assert over_release.failure.code == "FREEZE_INSUFFICIENT"

    missing = gate.get_freeze(who, "frz_missing")
    assert isinstance(missing, QueryFailure)
    assert missing.error.code == "RECORD_NOT_FOUND"
    missing_order = gate.get_order(who, "ord_missing")
    assert isinstance(missing_order, QueryFailure)
    assert missing_order.error.code == "RECORD_NOT_FOUND"

    unknown_product = gate.create_order(who, op(), CreateOrderInput(
        product_id="p_gold", quantity=1, expected_total_fen=19900,
        delivery=delivery(_now() + timedelta(hours=30))))
    assert unknown_product.operation_status is OperationStatus.FAILED
    assert unknown_product.failure.code == "PRODUCT_UNAVAILABLE"

    price_changed = gate.create_order(who, op(), CreateOrderInput(
        product_id="p_flower", quantity=1, expected_total_fen=19800,
        delivery=delivery(_now() + timedelta(hours=30))))
    assert price_changed.operation_status is OperationStatus.FAILED
    assert price_changed.failure.code == "PRICE_CHANGED"
    assert price_changed.failure.details["actual_total_fen"] == 19900

    too_soon = gate.create_order(who, op(), CreateOrderInput(
        product_id="p_flower", quantity=1, expected_total_fen=19900,
        delivery=delivery(_now() + timedelta(hours=2))))
    assert too_soon.operation_status is OperationStatus.FAILED
    assert too_soon.failure.code == "DELIVERY_UNAVAILABLE"

    order = ok_write(gate.create_order(who, op(), CreateOrderInput(
        product_id="p_flower", quantity=1, expected_total_fen=19900,
        delivery=delivery(_now() + timedelta(hours=30)))))
    wrong_merchant = gate.capture_frozen(who, op(), CaptureFrozenInput(
        freeze_id=freeze_id, amount_fen=19900, merchant_id="m_cake",
        merchant_name="西点蛋糕房", purpose="生日鲜花", category=Category.SHOPPING,
        order_id=order.receipt.order.order_id))
    assert wrong_merchant.operation_status is OperationStatus.FAILED
    assert wrong_merchant.failure.code == "ORDER_PAYMENT_MISMATCH"
    assert bank.store.get_account("U1", "BA1").frozen_balance_fen == 50000


def test_gateway_denies_birthday_writes_without_authorization(tmp_path):
    bank = bank_with_account(tmp_path)
    gate = BankGateway(bank)  # no authorize_birthday wired: default deny
    operation_id = op()
    denied = gate.freeze_funds(context(), operation_id, FreezeFundsInput(
        account_id="BA1", amount_fen=50000, reason="生日"))
    assert isinstance(denied, QueryFailure)
    assert denied.error.code == "ACCESS_DENIED"
    account = bank.store.get_account("U1", "BA1")
    assert (account.book_balance_fen, account.frozen_balance_fen) == (200000, 0)
    # No bank operation was recorded either.
    assert bank.store.get_operation("U1", str(operation_id)) is None
    products = gate.list_products(context())
    assert [item.product_id for item in products.products] == ["p_flower", "p_cake"]
    soon = gate.list_products(context(), deliver_by=_now() + timedelta(hours=30))
    assert [item.product_id for item in soon.products] == ["p_flower"]


def test_capture_keeps_b08_returnable_with_counterparty_facts(tmp_path):
    bank = bank_with_account(tmp_path)
    gate = gateway(bank)
    who = context()
    frozen = ok_write(gate.freeze_funds(who, op(), FreezeFundsInput(
        account_id="BA1", amount_fen=50000, reason="生日")))
    freeze_id = frozen.receipt.freeze_id
    order = ok_write(gate.create_order(who, op(), CreateOrderInput(
        product_id="p_flower", quantity=1, expected_total_fen=19900,
        delivery=delivery(_now() + timedelta(hours=30)))))
    paid = ok_write(gate.capture_frozen(who, op(), CaptureFrozenInput(
        freeze_id=freeze_id, amount_fen=19900, merchant_id="m_flower",
        merchant_name="邻里花店", purpose="生日鲜花", category=Category.SHOPPING,
        order_id=order.receipt.order.order_id)))
    # B08 returns the consumption as a complete fact, not a bank-unavailable gap.
    flows = bank.list_transactions(who.user_id, "BA1", _now() - timedelta(minutes=1),
                                   _now() + timedelta(minutes=1))
    assert flows.kind == "ok"
    row = flows.data.transactions[0]
    assert row.transaction_id == paid.receipt.transaction_id
    assert row.counterparty_name == "邻里花店"
    assert row.summary == "生日鲜花"
    assert row.category is Category.SHOPPING
    assert row.nature == "consumption"
    # A replay with a different address on the same operation number conflicts.
    changed = gate.create_order(who, order.operation_id, CreateOrderInput(
        product_id="p_flower", quantity=1, expected_total_fen=19900,
        delivery=DeliveryInput(recipient_name="李四", phone="13900005678",
                               address="另一个地址 2 号",
                               deliver_by=_now() + timedelta(hours=30))))
    assert isinstance(changed, QueryFailure)
    assert changed.error.code == "OPERATION_CONFLICT"


def test_response_loss_fault_is_recoverable_by_b14(tmp_path):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite3"), demo_secret=b"s" * 32,
                           slow_seconds=0.3)
    bank.store.seed_account(BankAccount("BA1", "U1", "class_i", "active", 200000, 0, 0))
    gate = BankGateway(bank, transfer_timeout_seconds=0.05,
                       authorize_birthday=lambda *_: True)
    who = context()
    bank.birthday.arm_response_loss("U1")
    operation_id = op()
    timed_out = gate.freeze_funds(who, operation_id, FreezeFundsInput(
        account_id="BA1", amount_fen=50000, reason="生日"))
    assert isinstance(timed_out, QueryFailure)
    assert timed_out.error.code == "CALL_TIMEOUT"
    # The bank did execute; only the caller's answer was lost. The original
    # operation number finds the committed fact — never a second submission.
    lookup = gate.get_operation(who, operation_id)
    assert lookup.lookup == "found"
    assert lookup.operation.operation_status is OperationStatus.SUCCEEDED
    assert bank.store.get_account("U1", "BA1").frozen_balance_fen == 50000
    gate.close()


def test_authorize_birthday_receives_the_typed_request(tmp_path):
    """Ticket v05-cross-platform/10: the callback sees the exact submission
    (amount included) and a refusal means zero bank writes."""
    bank = bank_with_account(tmp_path)
    seen = []

    def authorize(trusted_context, operation_id, action, request):
        seen.append((trusted_context, operation_id, action, request))
        amount = getattr(request, "amount_fen", None)
        if amount is None:
            amount = request.expected_total_fen
        return amount == 50000

    gate = BankGateway(bank, authorize_birthday=authorize)
    who = context()

    frozen = ok_write(gate.freeze_funds(who, op(), FreezeFundsInput(
        account_id="BA1", amount_fen=50000, reason="生日")))
    assert seen[-1][2] == "bank.freeze_funds"
    assert seen[-1][3].amount_fen == 50000
    assert seen[-1][3].account_id == "BA1"
    freeze_id = frozen.receipt.freeze_id

    denied = gate.release_frozen(who, op(), ReleaseFrozenInput(
        freeze_id=freeze_id, amount_fen=1))
    assert isinstance(denied, QueryFailure)
    assert denied.error.code == "ACCESS_DENIED"
    assert seen[-1][2] == "bank.release_frozen"
    assert seen[-1][3].amount_fen == 1

    denied_order = gate.create_order(who, op(), CreateOrderInput(
        product_id="p_flower", quantity=1, expected_total_fen=19900,
        delivery=delivery(_now() + timedelta(hours=30))))
    assert isinstance(denied_order, QueryFailure)
    assert denied_order.error.code == "ACCESS_DENIED"
    assert seen[-1][3].expected_total_fen == 19900

    # The refused submissions left the bank untouched.
    account = bank.store.get_account("U1", "BA1")
    assert account.frozen_balance_fen == 50000
    view = gate.get_freeze(who, freeze_id).data
    assert view.released_total_fen == 0
    from app.storage.database import connect
    with connect(bank.store.path) as connection:
        writes = connection.execute(
            "SELECT action_name FROM bank_operations",
        ).fetchall()
    assert [row["action_name"] for row in writes] == ["bank.freeze_funds"]
    gate.close()


def test_cross_round_reads_and_writes_are_denied(tmp_path):
    bank = bank_with_account(tmp_path)
    gate = gateway(bank)
    who = context()
    frozen = ok_write(gate.freeze_funds(who, op(), FreezeFundsInput(
        account_id="BA1", amount_fen=50000, reason="生日")))
    order = ok_write(gate.create_order(who, op(), CreateOrderInput(
        product_id="p_flower", quantity=1, expected_total_fen=19900,
        delivery=delivery(_now() + timedelta(hours=30)))))
    freeze_id = frozen.receipt.freeze_id
    order_id = order.receipt.order.order_id
    other = who.model_copy(update={"demo_round_id": "D2"})

    denied_freeze = gate.get_freeze(other, freeze_id)
    assert isinstance(denied_freeze, QueryFailure)
    assert denied_freeze.error.code == "ACCESS_DENIED"
    denied_order = gate.get_order(other, order_id)
    assert isinstance(denied_order, QueryFailure)
    assert denied_order.error.code == "ACCESS_DENIED"

    denied_capture = gate.capture_frozen(other, op(), CaptureFrozenInput(
        freeze_id=freeze_id, amount_fen=19900, merchant_id="m_flower",
        merchant_name="邻里花店", purpose="生日鲜花", category=Category.SHOPPING,
        order_id=order_id))
    assert denied_capture.operation_status is OperationStatus.FAILED
    assert denied_capture.failure.code == "ACCESS_DENIED"
    denied_release = gate.release_frozen(other, op(), ReleaseFrozenInput(
        freeze_id=freeze_id, amount_fen=30100))
    assert denied_release.operation_status is OperationStatus.FAILED
    assert denied_release.failure.code == "ACCESS_DENIED"

    account = bank.store.get_account("U1", "BA1")
    assert (account.book_balance_fen, account.frozen_balance_fen) == (200000, 50000)
    assert bank.store.get_freeze("U1", freeze_id)["captured_total_fen"] == 0
    assert bank.store.get_freeze("U1", freeze_id)["released_total_fen"] == 0
    assert bank.store.get_order("U1", order_id)["payment_status"] == "unpaid"
    assert table_count(bank.store, "order_payments") == 0
    assert bank.store.list_ledger("U1", "BA1") == []

    # Same-round control still works.
    paid = ok_write(gate.capture_frozen(who, op(), CaptureFrozenInput(
        freeze_id=freeze_id, amount_fen=19900, merchant_id="m_flower",
        merchant_name="邻里花店", purpose="生日鲜花", category=Category.SHOPPING,
        order_id=order_id)))
    assert paid.receipt.captured_amount_fen == 19900
    assert table_count(bank.store, "order_payments") == 1


def test_cross_round_order_cannot_be_paid_by_a_current_round_freeze(tmp_path):
    bank = bank_with_account(tmp_path)
    gate = gateway(bank)
    who = context()
    other = who.model_copy(update={"demo_round_id": "D2"})
    old_order = ok_write(gate.create_order(who, op(), CreateOrderInput(
        product_id="p_flower", quantity=1, expected_total_fen=19900,
        delivery=delivery(_now() + timedelta(hours=30)))))
    current_freeze = ok_write(gate.freeze_funds(other, op(), FreezeFundsInput(
        account_id="BA1", amount_fen=50000, reason="生日")))
    denied = gate.capture_frozen(other, op(), CaptureFrozenInput(
        freeze_id=current_freeze.receipt.freeze_id, amount_fen=19900,
        merchant_id="m_flower", merchant_name="邻里花店", purpose="生日鲜花",
        category=Category.SHOPPING, order_id=old_order.receipt.order.order_id))
    assert denied.operation_status is OperationStatus.FAILED
    assert denied.failure.code == "ACCESS_DENIED"
    assert bank.store.get_order(
        "U1", old_order.receipt.order.order_id)["payment_status"] == "unpaid"
    assert table_count(bank.store, "order_payments") == 0
    assert bank.store.list_ledger("U1", "BA1") == []


@pytest.mark.parametrize("kind", ["freezes", "orders"])
def test_service_startup_refuses_objects_written_without_a_round(tmp_path, kind):
    path = tmp_path / "bank.sqlite3"
    store = MockBankStore(path)
    store.seed_account(BankAccount("BA1", "U1", "class_i", "active", 200000, 0, 0))
    recorded_at = "2026-10-25T04:00:00+08:00"
    operation_id = str(uuid4())
    if kind == "freezes":
        store.commit_operation(
            "U1", operation_id, "bank.freeze_funds",
            {"account_id": "BA1", "amount_fen": 50000, "reason": "生日"},
            "succeeded", {"freeze_id": "f-null"}, recorded_at,
            [("BA1", 0, 200000, 50000)], [],
            (FreezeOpening("f-null", "BA1", 50000),),
        )
        remaining_amount, remaining_frozen = 200000, 50000
        row_table, row_id = "freezes", "f-null"
    else:
        store.commit_operation(
            "U1", operation_id, "bank.create_order",
            {"product_id": "p_flower", "quantity": 1, "expected_total_fen": 19900},
            "succeeded", {"order_id": "o-null"}, recorded_at, [], [],
            (OrderCreation(order_id="o-null", product_id="p_flower", quantity=1,
                           merchant_id="m_flower", merchant_name="花店",
                           total_fen=19900, expected_total_fen=19900,
                           created_at=recorded_at, deliver_by="2026-10-27T04:00:00+08:00",
                           recipient_name_masked="张*", phone_masked="****1234",
                           address_masked="某市****"),),
        )
        remaining_amount, remaining_frozen = 200000, 0
        row_table, row_id = "orders", "o-null"
    # A real pre-02 database also has the operation scope row: the object row is
    # what is missing a round, so the startup guard (not the older operation-scope
    # check) must be the one that refuses it.
    with connect(path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS bank_operation_scopes (
            operation_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
            demo_round_id TEXT NOT NULL)""")
        connection.execute(
            "INSERT OR IGNORE INTO bank_operation_scopes VALUES (?, 'U1', 'D1')",
            (operation_id,),
        )
        connection.commit()
        version_before = connection.execute("PRAGMA user_version").fetchone()[0]
        accounts_before = connection.execute(
            "SELECT * FROM accounts ORDER BY 1").fetchall()
        row_before = connection.execute(
            f"SELECT demo_round_id FROM {row_table} WHERE "
            f"{'freeze_id' if row_table == 'freezes' else 'order_id'} = ?",
            (row_id,),
        ).fetchone()

    with pytest.raises(RuntimeError, match="bank objects without a demo round"):
        MockBankService(store, demo_secret=b"s" * 32)

    assert store.get_account("U1", "BA1").book_balance_fen == remaining_amount
    assert store.get_account("U1", "BA1").frozen_balance_fen == remaining_frozen
    with connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == version_before
        assert [tuple(row) for row in connection.execute(
            "SELECT * FROM accounts ORDER BY 1")] == [tuple(row) for row in accounts_before]
        row_after = connection.execute(
            f"SELECT demo_round_id FROM {row_table} WHERE "
            f"{'freeze_id' if row_table == 'freezes' else 'order_id'} = ?",
            (row_id,),
        ).fetchone()
        assert row_after["demo_round_id"] is None
        assert tuple(row_after) == tuple(row_before)


def test_gateway_passes_trusted_round_to_object_reads(tmp_path):
    class RecordingBirthday:
        def __init__(self):
            self.calls = []

        def get_freeze(self, user_id, freeze_id, demo_round_id=None):
            self.calls.append(("freeze", user_id, freeze_id, demo_round_id))
            return QueryFailure(kind="error", error=BankError(
                code="RECORD_NOT_FOUND", details={}))

        def get_order(self, user_id, order_id, demo_round_id=None):
            self.calls.append(("order", user_id, order_id, demo_round_id))
            return QueryFailure(kind="error", error=BankError(
                code="RECORD_NOT_FOUND", details={}))

    class RecordingBank:
        def __init__(self, birthday):
            self.birthday = birthday

    birthday = RecordingBirthday()
    gate = BankGateway(RecordingBank(birthday))
    who = context()
    assert isinstance(gate.get_freeze(who, "f1"), QueryFailure)
    assert isinstance(gate.get_order(who, "o1"), QueryFailure)
    assert birthday.calls == [
        ("freeze", "U1", "f1", "D1"),
        ("order", "U1", "o1", "D1"),
    ]
    gate.close()
