"""Ticket v05-cross-platform/07: birthday bank service and gateway boundary."""

from datetime import timedelta
from uuid import uuid4

from app.contracts.bank import (
    CaptureFrozenInput, CreateOrderInput, DeliveryInput, FreezeFundsInput, FreezeView,
    QueryFailure, ReleaseFrozenInput,
)
from app.contracts.common import Category, OperationStatus
from app.contracts.platform import TrustedContext
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService, _now
from app.storage.mock_bank.repository import BankAccount, MockBankStore


def context() -> TrustedContext:
    return TrustedContext(user_id="U1", session_id="S1", task_id="T1", run_id="R1",
                          parent_task_id=None, demo_round_id="D1")


def bank_with_account(tmp_path):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite3"), demo_secret=b"s" * 32)
    bank.store.seed_account(BankAccount("BA1", "U1", "class_i", "active", 200000, 0, 0))
    return bank


def gateway(bank, **kwargs):
    return BankGateway(bank, authorize_birthday=lambda *_: True, **kwargs)


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
