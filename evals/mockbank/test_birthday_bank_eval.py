"""v05-cross-bank-eval/01: real gateway/service/SQLite bank evidence, no LLM or HTTP.

Authorization callbacks are explicit test grants, not proof of the security gate.
Faults use the bank's response-loss seam and SQLite's own transaction engine.
"""

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import pytest

from app.contracts.bank import (
    CaptureFrozenInput, CreateOrderInput, DeliveryInput, FreezeFundsInput,
    QueryFailure, ReleaseFrozenInput,
)
from app.contracts.common import Category, OperationStatus
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.storage.database import connect
from app.storage.mock_bank.repository import BankAccount, MockBankStore


NOW = datetime(2026, 10, 25, 4, tzinfo=timezone.utc)
ACTIONS = ("freeze_funds", "create_order", "capture_frozen", "release_frozen")
TABLES = ("accounts", "freezes", "orders", "order_payments", "ledger_entries", "bank_operations")


def succeeded(result):
    assert not isinstance(result, QueryFailure), result
    assert result.operation_status is OperationStatus.SUCCEEDED, result
    return result


def failed(result, code):
    if isinstance(result, QueryFailure):
        assert result.error.code == code, result
    else:
        assert result.operation_status is OperationStatus.FAILED, result
        assert result.failure.code == code, result


def state(bank):
    """All persisted business facts, including versions and full stored receipts.

    Scope reservations are separate: a failed commit may still reserve its UUID.
    """
    with closing(connect(bank.store.path)) as connection:
        return {
            table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
            for table in TABLES
        }


@pytest.fixture
def birthday_runtime(tmp_path):
    gateways = []

    def open_bank(path):
        return MockBankService(
            MockBankStore(path), demo_secret=b"birthday-bank-eval-only-secret-32-bytes",
            clock=lambda: NOW, slow_seconds=0.6,
        )

    def fresh_bank(name):
        bank = open_bank(tmp_path / name / "bank.sqlite3")
        # Dedicated seed accounts have no historical consumption to obscure counts.
        for account_id, user in (("EVAL_A", "U1"), ("EVAL_B", "U1"), ("EVAL_U2", "U2")):
            bank.store.seed_account(BankAccount(account_id, user, "class_i", "active", 200000, 0, 0))
        return bank

    def gateway(bank, *, authorized=True, timeout=2.0):
        options = {} if authorized is None else {"authorize_birthday": lambda *_: authorized}
        gate = BankGateway(bank, transfer_timeout_seconds=timeout, **options)
        gateways.append(gate)
        return gate

    bank = fresh_bank("initial")
    yield bank, gateway, fresh_bank, open_bank
    for gate in gateways:
        gate.close()


def freeze(gate, who, *, account="EVAL_A"):
    return succeeded(gate.freeze_funds(who, uuid4(), FreezeFundsInput(
        account_id=account, amount_fen=50000, reason="生日专项",
    )))


def order_request(product="p_flower", total=19900):
    return CreateOrderInput(
        product_id=product, quantity=1, expected_total_fen=total,
        delivery=DeliveryInput(recipient_name="测试收件人", phone="13800001234",
                               address="测试市测试路1号", deliver_by=NOW + timedelta(hours=72)),
    )


def capture_request(freeze_id, order):
    return CaptureFrozenInput(
        freeze_id=freeze_id, order_id=order.order_id, amount_fen=order.total_fen,
        merchant_id=order.merchant_id, merchant_name=order.merchant_name,
        purpose="生日专项", category=Category.SHOPPING,
    )


def prepared_action(action, gate, who):
    """Prepare real prerequisites; return the exact public request to evaluate."""
    if action == "freeze_funds":
        return FreezeFundsInput(account_id="EVAL_A", amount_fen=50000, reason="生日专项")
    if action == "create_order":
        return order_request()
    frozen = freeze(gate, who)
    if action == "release_frozen":
        return ReleaseFrozenInput(freeze_id=frozen.receipt.freeze_id, amount_fen=50000)
    order = succeeded(gate.create_order(who, uuid4(), order_request())).receipt.order
    return capture_request(frozen.receipt.freeze_id, order)


def facts(gate, bank, who, freeze_id):
    view = gate.get_freeze(who, freeze_id).data
    account = bank.store.get_account(who.user_id, "EVAL_A")
    ledger = bank.store.list_ledger(who.user_id, "EVAL_A")
    return {
        "original_fen": view.original_amount_fen, "captured_fen": view.captured_total_fen,
        "released_fen": view.released_total_fen, "remaining_fen": view.remaining_fen,
        "book_fen": account.book_balance_fen, "frozen_fen": account.frozen_balance_fen,
        "available_fen": account.book_balance_fen - account.frozen_balance_fen,
        "ledger_amounts_fen": sorted(row["amount_fen"] for row in ledger),
        "ledger_natures": [row["nature"] for row in ledger],
    }


@pytest.mark.parametrize("products,spent,released", [
    ((('p_flower', 19900), ('p_cake', 26800)), 46700, 3300),
    ((('p_flower', 19900),), 19900, 30100),
], ids=["MB-B01-500-467-33", "MB-B02-199-301"])
def test_birthday_money_and_order_facts(birthday_runtime, user_context, record_property,
                                       products, spent, released):
    bank, gateway, _, reopen = birthday_runtime
    gate = gateway(bank)
    frozen = freeze(gate, user_context)
    freeze_id = frozen.receipt.freeze_id
    operations = [frozen]
    assert facts(gate, bank, user_context, freeze_id)["ledger_amounts_fen"] == []
    assert frozen.receipt.balance.available_balance_fen == 150000
    for payments_so_far, (product, total) in enumerate(products):
        created = succeeded(gate.create_order(user_context, uuid4(), order_request(product, total)))
        operations.append(created)
        unpaid = gate.get_order(user_context, created.receipt.order.order_id).data.order
        assert (unpaid.payment_status, unpaid.payment_transaction_id) == ("unpaid", None)
        before_payment = state(bank)
        assert len(before_payment["order_payments"]) == payments_so_far
        paid = succeeded(gate.capture_frozen(user_context, uuid4(), capture_request(freeze_id, unpaid)))
        operations.append(paid)
        order = gate.get_order(user_context, unpaid.order_id).data.order
        assert (order.payment_status, order.payment_transaction_id) == ("paid", paid.receipt.transaction_id)
    # Every payment is settled and queried before releasing the remainder.
    for operation in operations:
        assert gate.get_operation(user_context, operation.operation_id).operation == operation
    release = succeeded(gate.release_frozen(user_context, uuid4(), ReleaseFrozenInput(
        freeze_id=freeze_id, amount_fen=released,
    )))
    operations.append(release)
    expected = dict(original_fen=50000, captured_fen=spent, released_fen=released,
                    remaining_fen=0, book_fen=200000-spent, frozen_fen=0,
                    available_fen=200000-spent,
                    ledger_amounts_fen=sorted(total for _, total in products),
                    ledger_natures=["consumption"] * len(products))
    assert facts(gate, bank, user_context, freeze_id) == expected
    assert len(state(bank)["order_payments"]) == len(products)
    flows = gate.list_transactions(user_context, "EVAL_A", NOW-timedelta(seconds=1), NOW+timedelta(seconds=1))
    assert flows.kind == "ok", flows
    assert sorted(row.amount_fen for row in flows.data.transactions) == expected["ledger_amounts_fen"]
    assert all(row.nature == "consumption" and row.counterparty_name
               for row in flows.data.transactions)
    # Restart the actual service over the same file; no replay or reseeding of balances.
    restarted = reopen(bank.store.path)
    restarted_gate = gateway(restarted)
    assert facts(restarted_gate, restarted, user_context, freeze_id) == expected
    for operation in operations:
        assert restarted_gate.get_operation(user_context, operation.operation_id).operation == operation
    record_property("bank_facts", json.dumps(expected, ensure_ascii=False))


@pytest.mark.parametrize("action", ACTIONS, ids=lambda a: "MB-B03-" + a)
def test_each_write_replay_conflict_and_unknown_lookup(birthday_runtime, user_context, action):
    bank, gateway, _, _ = birthday_runtime
    gate = gateway(bank)
    request = prepared_action(action, gate, user_context)
    operation_id = uuid4()
    assert gate.get_operation(user_context, operation_id).lookup == "not_found"
    invoke = getattr(gate, action)
    first = succeeded(invoke(user_context, operation_id, request))
    saved = state(bank)
    assert succeeded(invoke(user_context, operation_id, request)) == first
    changes = {"expected_total_fen": 20000} if action == "create_order" else {"amount_fen": 1}
    failed(invoke(user_context, operation_id, request.model_copy(update=changes)), "OPERATION_CONFLICT")
    assert gate.get_operation(user_context, operation_id).operation == first
    assert state(bank) == saved


@pytest.mark.parametrize("action", ACTIONS, ids=lambda a: "MB-B04-" + a)
def test_each_committed_response_loss_queries_original_id(birthday_runtime, user_context, action):
    bank, gateway, _, _ = birthday_runtime
    gate = gateway(bank)
    request = prepared_action(action, gate, user_context)
    before = state(bank)
    operation_id = uuid4()
    bank.birthday.arm_response_loss(user_context.user_id)
    timed_gate = gateway(bank, timeout=0.2)
    failed(getattr(timed_gate, action)(user_context, operation_id, request), "CALL_TIMEOUT")
    found = gate.get_operation(user_context, operation_id)
    assert found.lookup == "found"
    succeeded(found.operation)
    after = state(bank)
    assert len(after["bank_operations"]) == len(before["bank_operations"]) + 1
    assert len(after["ledger_entries"]) - len(before["ledger_entries"]) == (action == "capture_frozen")
    assert len(after["order_payments"]) - len(before["order_payments"]) == (action == "capture_frozen")
    # Repeated read only, never resubmit an uncertain write with any UUID.
    assert gate.get_operation(user_context, operation_id) == found
    assert state(bank) == after
    if action == "capture_frozen":
        order = gate.get_order(user_context, request.order_id).data.order
        assert order.payment_transaction_id == found.operation.receipt.transaction_id
        succeeded(gate.release_frozen(user_context, uuid4(), ReleaseFrozenInput(
            freeze_id=request.freeze_id, amount_fen=30100,
        )))
        assert facts(gate, bank, user_context, request.freeze_id)["released_fen"] == 30100


@pytest.mark.parametrize("action", ACTIONS, ids=lambda a: "MB-B05-" + a)
def test_sqlite_failure_rolls_back_all_business_facts(birthday_runtime, user_context, action):
    bank, gateway, _, _ = birthday_runtime
    gate = gateway(bank)
    request = prepared_action(action, gate, user_context)
    before = state(bank)
    # commit_operation inserts its receipt after applying account/object/ledger effects.
    # A real SQLite abort at that final insert must roll the entire transaction back.
    with closing(connect(bank.store.path)) as connection:
        connection.execute("""CREATE TRIGGER eval_abort_receipt BEFORE INSERT ON bank_operations
                              BEGIN SELECT RAISE(ABORT, 'eval storage failure'); END""")
    operation_id = uuid4()
    failed(getattr(gate, action)(user_context, operation_id, request), "BANK_UNAVAILABLE")
    assert state(bank) == before
    assert gate.get_operation(user_context, operation_id).lookup == "not_found"
    with closing(connect(bank.store.path)) as connection:
        connection.execute("DROP TRIGGER eval_abort_receipt")
    # Here rollback is proven. Explicit recovery uses the original UUID, not a new one.
    recovered = succeeded(getattr(gate, action)(user_context, operation_id, request))
    assert gate.get_operation(user_context, operation_id).operation == recovered
    assert len(state(bank)["bank_operations"]) == len(before["bank_operations"]) + 1


@pytest.mark.parametrize("action", ACTIONS, ids=lambda a: "MB-B06-" + a)
@pytest.mark.parametrize("change", [{"user_id": "U2"}, {"demo_round_id": "D2"}], ids=["user", "round"])
def test_operation_scope_isolation(birthday_runtime, user_context, action, change):
    bank, gateway, _, _ = birthday_runtime
    gate = gateway(bank)
    request = prepared_action(action, gate, user_context)
    operation_id = uuid4()
    succeeded(getattr(gate, action)(user_context, operation_id, request))
    before = state(bank)
    other = user_context.model_copy(update=change)
    failed(gate.get_operation(other, operation_id), "ACCESS_DENIED")
    failed(getattr(gate, action)(other, operation_id, request), "OPERATION_CONFLICT")
    assert state(bank) == before


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "Open round-boundary gap: old objects remain usable with a new UUID and an explicit test grant; "
    "see birthday-evidence.md and .scratch/v05-cross-bank-eval/round-boundary-gap.md"
))
@pytest.mark.parametrize("probe", ("get_freeze", "get_order", "capture_frozen", "release_frozen"))
def test_old_round_objects_with_new_operation_are_denied(
    birthday_runtime, user_context, record_property, probe,
):
    """Unmet package requirement, never counted as a passing isolation check.

    The grant bypasses the real security executor, so this cannot establish a
    product exploit. Keep strict xfail until the owning directories resolve it.
    """
    bank, gateway, _, _ = birthday_runtime
    gate = gateway(bank)
    request = prepared_action("capture_frozen", gate, user_context)
    before = state(bank)
    next_round = user_context.model_copy(update={"demo_round_id": "D2"})
    if probe == "get_freeze":
        result = gate.get_freeze(next_round, request.freeze_id)
    elif probe == "get_order":
        result = gate.get_order(next_round, request.order_id)
    elif probe == "capture_frozen":
        result = gate.capture_frozen(next_round, uuid4(), request)
    else:
        result = gate.release_frozen(next_round, uuid4(), ReleaseFrozenInput(
            freeze_id=request.freeze_id, amount_fen=50000,
        ))
    record_property("round_boundary_probe", json.dumps({
        "from_round": "D1", "to_round": "D2", "probe": probe,
        "observed_kind": getattr(result, "kind", None),
        "observed_operation_status": getattr(result, "operation_status", None),
        "book_fen": bank.store.get_account("U1", "EVAL_A").book_balance_fen,
        "frozen_fen": bank.store.get_account("U1", "EVAL_A").frozen_balance_fen,
    }))
    if probe in ("get_freeze", "get_order"):
        assert isinstance(result, QueryFailure), "Old-round bank object was readable"
    else:
        assert isinstance(result, QueryFailure) or result.operation_status is OperationStatus.FAILED, (
            "New-round write succeeded against old-round bank objects under the test grant"
        )
    assert state(bank) == before


@pytest.mark.parametrize("action", ACTIONS, ids=lambda a: "MB-B07-" + a)
@pytest.mark.parametrize("authorized", [None, False], ids=["missing-grant", "denied-grant"])
def test_unauthorized_writes_never_reach_bank(birthday_runtime, user_context, action, authorized):
    bank, gateway, _, _ = birthday_runtime
    request = prepared_action(action, gateway(bank), user_context)
    before = state(bank)
    operation_id = uuid4()
    gate = gateway(bank, authorized=authorized)
    failed(getattr(gate, action)(user_context, operation_id, request), "ACCESS_DENIED")
    assert state(bank) == before
    assert gate.get_operation(user_context, operation_id).lookup == "not_found"
    with closing(connect(bank.store.path)) as connection:
        assert connection.execute("SELECT * FROM bank_operation_scopes WHERE operation_id = ?",
                                  (str(operation_id),)).fetchone() is None


def test_order_cannot_be_paid_again_or_with_wrong_facts(birthday_runtime, user_context):
    bank, gateway, _, _ = birthday_runtime
    gate = gateway(bank)
    request = prepared_action("capture_frozen", gate, user_context)
    for changed in ({"amount_fen": 19901}, {"merchant_id": "m_cake"}, {"category": Category.OTHER}):
        failed(gate.capture_frozen(user_context, uuid4(), request.model_copy(update=changed)),
               "ORDER_PAYMENT_MISMATCH")
    assert gate.get_order(user_context, request.order_id).data.order.payment_status == "unpaid"
    paid = succeeded(gate.capture_frozen(user_context, uuid4(), request))
    original = facts(gate, bank, user_context, request.freeze_id)
    failed(gate.capture_frozen(user_context, uuid4(), request), "ORDER_PAYMENT_MISMATCH")
    # Even another valid freeze/account and a new UUID cannot pay this order again.
    second = freeze(gate, user_context, account="EVAL_B")
    failed(gate.capture_frozen(user_context, uuid4(), request.model_copy(update={
        "freeze_id": second.receipt.freeze_id,
    })), "ORDER_PAYMENT_MISMATCH")
    assert facts(gate, bank, user_context, request.freeze_id) == original
    assert len(bank.store.list_ledger("U1", "EVAL_B")) == 0
    assert len(state(bank)["order_payments"]) == 1
    assert gate.get_order(user_context, request.order_id).data.order.payment_transaction_id == paid.receipt.transaction_id


@pytest.mark.parametrize("product,price", [("p_flower", 19900), ("p_cake", 26800)])
def test_catalog_price_change_and_delivery_rejections(birthday_runtime, user_context, product, price):
    bank, gateway, _, _ = birthday_runtime
    gate = gateway(bank)
    catalog = {item.product_id: item for item in gate.list_products(user_context).products}
    assert catalog[product].unit_price_fen == price
    for request, code in (
        (order_request(product, price - 100), "PRICE_CHANGED"),
        (order_request(product, price).model_copy(update={"delivery": DeliveryInput(
            recipient_name="测试收件人", phone="13800001234", address="测试地址",
            deliver_by=NOW + timedelta(hours=1),
        )}), "DELIVERY_UNAVAILABLE"),
    ):
        operation_id = uuid4()
        result = gate.create_order(user_context, operation_id, request)
        failed(result, code)
        assert gate.get_operation(user_context, operation_id).operation == result
        before_replay = state(bank)
        assert gate.create_order(user_context, operation_id, request) == result
        assert state(bank) == before_replay
        if code == "PRICE_CHANGED":
            assert result.failure.details["actual_total_fen"] == price
    assert state(bank)["orders"] == []
    assert [p.product_id for p in gate.list_products(user_context, deliver_by=NOW+timedelta(hours=30)).products] == ["p_flower"]


def test_order_delivery_and_action_name_conflicts(birthday_runtime, user_context):
    bank, gateway, _, _ = birthday_runtime
    gate = gateway(bank)
    request = order_request()
    operation_id = uuid4()
    created = succeeded(gate.create_order(user_context, operation_id, request))
    before = state(bank)
    changed_delivery = request.delivery.model_copy(update={"address": "测试市另一条路2号"})
    failed(gate.create_order(user_context, operation_id, request.model_copy(update={
        "delivery": changed_delivery,
    })), "OPERATION_CONFLICT")
    failed(gate.freeze_funds(user_context, operation_id, FreezeFundsInput(
        account_id="EVAL_A", amount_fen=50000, reason="编号不能跨动作复用",
    )), "OPERATION_CONFLICT")
    assert state(bank) == before
    assert gate.get_operation(user_context, operation_id).operation == created


def test_response_loss_is_user_scoped_and_one_shot(birthday_runtime, user_context):
    bank, gateway, _, _ = birthday_runtime
    gate = gateway(bank, timeout=0.2)
    bank.birthday.arm_response_loss("U1")
    other = user_context.model_copy(update={"user_id": "U2"})
    succeeded(gate.freeze_funds(other, uuid4(), FreezeFundsInput(
        account_id="EVAL_U2", amount_fen=100, reason="另一用户未受故障影响",
    )))
    operation_id = uuid4()
    failed(gate.freeze_funds(user_context, operation_id, FreezeFundsInput(
        account_id="EVAL_A", amount_fen=50000, reason="只丢一次响应",
    )), "CALL_TIMEOUT")
    succeeded(gate.get_operation(user_context, operation_id).operation)
    # Wait for this test's worker to return, then another write no longer loses its response.
    gate.close()
    succeeded(gateway(bank).create_order(user_context, uuid4(), order_request()))


def test_wrong_owner_and_exhausted_freeze_cannot_move_money(birthday_runtime, user_context):
    bank, gateway, _, _ = birthday_runtime
    gate = gateway(bank)
    other = user_context.model_copy(update={"user_id": "U2"})
    failed(gate.freeze_funds(other, uuid4(), FreezeFundsInput(
        account_id="EVAL_A", amount_fen=50000, reason="跨用户",
    )), "ACCESS_DENIED")
    request = prepared_action("capture_frozen", gate, user_context)
    failed(gate.get_freeze(other, request.freeze_id), "RECORD_NOT_FOUND")
    failed(gate.get_order(other, request.order_id), "RECORD_NOT_FOUND")
    failed(gate.capture_frozen(other, uuid4(), request), "RECORD_NOT_FOUND")
    failed(gate.release_frozen(other, uuid4(), ReleaseFrozenInput(
        freeze_id=request.freeze_id, amount_fen=50000,
    )), "RECORD_NOT_FOUND")
    assert len(bank.store.list_ledger("U1", "EVAL_A")) == 0
    # An insufficient account cannot borrow another account's balance.
    failed(gate.freeze_funds(user_context, uuid4(), FreezeFundsInput(
        account_id="A5", amount_fen=1, reason="空账户",
    )), "INSUFFICIENT_FUNDS")
    succeeded(gate.release_frozen(user_context, uuid4(), ReleaseFrozenInput(
        freeze_id=request.freeze_id, amount_fen=50000,
    )))
    failed(gate.capture_frozen(user_context, uuid4(), request), "FREEZE_INSUFFICIENT")
    failed(gate.release_frozen(user_context, uuid4(), ReleaseFrozenInput(
        freeze_id=request.freeze_id, amount_fen=1,
    )), "FREEZE_INSUFFICIENT")
    assert facts(gate, bank, user_context, request.freeze_id)["ledger_amounts_fen"] == []
    assert bank.store.get_account("U2", "EVAL_U2").book_balance_fen == 200000


def test_fresh_seed_repeats_results_and_old_resources_are_absent(birthday_runtime, user_context):
    _, gateway, fresh_bank, _ = birthday_runtime
    results = []
    old_freeze = old_order = old_operation = None
    for index in range(2):
        bank = fresh_bank(f"reset-{index}")
        gate = gateway(bank)
        who = user_context.model_copy(update={"demo_round_id": f"RESET-{index}"})
        if old_operation is not None:
            assert gate.get_operation(who, old_operation).lookup == "not_found"
            failed(gate.get_freeze(who, old_freeze), "RECORD_NOT_FOUND")
            failed(gate.get_order(who, old_order), "RECORD_NOT_FOUND")
        frozen = freeze(gate, who)
        order = succeeded(gate.create_order(who, uuid4(), order_request())).receipt.order
        succeeded(gate.capture_frozen(who, uuid4(), capture_request(frozen.receipt.freeze_id, order)))
        succeeded(gate.release_frozen(who, uuid4(), ReleaseFrozenInput(
            freeze_id=frozen.receipt.freeze_id, amount_fen=30100,
        )))
        results.append(facts(gate, bank, who, frozen.receipt.freeze_id))
        old_freeze, old_order, old_operation = frozen.receipt.freeze_id, order.order_id, frozen.operation_id
    assert results[0] == results[1]
