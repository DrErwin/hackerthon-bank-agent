"""B26 waits for actual gateway futures, including timed-out and queued writes."""

from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest

from app.contracts.bank import (
    CaptureFrozenInput, CreateOrderInput, DeliveryInput, FreezeFundsInput,
    ReleaseFrozenInput, SavedPayee,
)
from app.contracts.common import Category
from app.services.test_demo_reset import INITIAL, context, ready


def write_for(bank, gateway, action, operation):
    who = context()
    if action == "submit_transfer":
        return bank, lambda: gateway.submit_transfer(
            who, operation, "A1", SavedPayee(kind="saved", payee_id="A2"), 100)
    if action == "cancel_subscription":
        return bank, lambda: gateway.cancel_subscription(who, operation, "sub_001")
    if action == "freeze_funds":
        request = FreezeFundsInput(account_id="A1", amount_fen=50000, reason="生日")
    elif action == "create_order":
        request = CreateOrderInput(
            product_id="p_flower", quantity=1, expected_total_fen=19900,
            delivery=DeliveryInput(recipient_name="张三", phone="13800001234",
                address="北京市西城区金融街 1 号", deliver_by=INITIAL + timedelta(days=2)))
    else:
        frozen = bank.birthday.freeze_funds(who, uuid4(), "A1", 50000, "生日")
        freeze_id = frozen.receipt.freeze_id
        request = (ReleaseFrozenInput(freeze_id=freeze_id, amount_fen=50000)
                   if action == "release_frozen" else CaptureFrozenInput(
                       freeze_id=freeze_id, amount_fen=19900, merchant_id="m_flower",
                       merchant_name="邻里花店", purpose="生日鲜花", category=Category.SHOPPING))
    return bank.birthday, lambda: getattr(gateway, action)(who, operation, request)


@pytest.mark.parametrize("action", [
    "submit_transfer", "cancel_subscription", "freeze_funds", "create_order",
    "capture_frozen", "release_frozen",
])
def test_timed_out_write_stays_inflight_before_any_bank_operation_exists(tmp_path, monkeypatch, action):
    bank, gateway = ready(tmp_path, timeout=0.05)
    operation = uuid4()
    target, invoke = write_for(bank, gateway, action, operation)
    started, release = Event(), Event()
    original = getattr(target, action)

    def delayed(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(target, action, delayed)
    try:
        assert gateway.wait_for_inflight(0.0)
        assert invoke().error.code == "CALL_TIMEOUT"
        assert started.wait(2)
        assert gateway.get_operation(context(), operation).lookup == "not_found"
        assert gateway.wait_for_inflight(0.0) is False
        assert gateway.wait_for_inflight(0.01) is False
        release.set()
        assert gateway.wait_for_inflight(3.0)
        assert gateway.get_operation(context(), operation).operation.operation_status == "succeeded"
        monkeypatch.setattr(target, action, original)
        # Waiting must not shut down the executor or prevent the next write.
        following = uuid4()
        gateway.submit_transfer(context(), following, "A1", SavedPayee(kind="saved", payee_id="A2"), 100)
        assert gateway.wait_for_inflight(3.0)
        assert gateway.get_operation(context(), following).operation.operation_status == "succeeded"
    finally:
        release.set()
        gateway.close()


def test_queued_writes_count_until_all_have_really_completed(tmp_path, monkeypatch):
    bank, gateway = ready(tmp_path, timeout=0.01)
    operations = [uuid4() for _ in range(6)]
    releases = {operation: Event() for operation in operations}
    first_four_started = Event()
    started = []
    original = bank.submit_transfer

    def delayed(who, operation, *args):
        started.append(operation)
        if len(started) == 4:
            first_four_started.set()
        assert releases[operation].wait(5)
        return original(who, operation, *args)

    monkeypatch.setattr(bank, "submit_transfer", delayed)
    try:
        for operation in operations:
            result = gateway.submit_transfer(context(), operation, "A1", SavedPayee(kind="saved", payee_id="A2"), 100)
            assert result.error.code == "CALL_TIMEOUT"
        assert first_four_started.wait(2)
        assert len(started) == 4
        assert gateway.wait_for_inflight(0.0) is False
        for operation in operations[:4]:
            releases[operation].set()
        # The remaining two queued/running requests still keep the gateway busy.
        assert gateway.wait_for_inflight(0.01) is False
        for event in releases.values():
            event.set()
        assert gateway.wait_for_inflight(3.0)
        assert all(gateway.get_operation(context(), operation).operation.operation_status == "succeeded"
                   for operation in operations)
    finally:
        for event in releases.values():
            event.set()
        gateway.close()


def test_exceptional_future_does_not_leave_a_phantom_inflight_write(tmp_path, monkeypatch):
    bank, gateway = ready(tmp_path)

    def unavailable(*_args):
        raise RuntimeError("bank unavailable")

    monkeypatch.setattr(bank, "submit_transfer", unavailable)
    try:
        with pytest.raises(RuntimeError, match="bank unavailable"):
            gateway.submit_transfer(context(), uuid4(), "A1", SavedPayee(kind="saved", payee_id="A2"), 100)
        assert gateway.wait_for_inflight(1.0)
    finally:
        gateway.close()
