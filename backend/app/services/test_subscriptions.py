"""B29/B30 subscription mandates: seeds, bank rules, replay and the B14 lookup."""

from __future__ import annotations

from collections import Counter
from contextlib import closing
from datetime import datetime
import time
from uuid import UUID, uuid4

from app.contracts.platform import TrustedContext
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.storage import StoragePaths
from app.storage.database import connect, transaction
from app.storage.mock_bank.repository import MockBankStore

DEMO_SECRET = b"mock-bank-test-secret-32-bytes-minimum"
NOW = datetime.fromisoformat("2026-10-19T13:00:00+08:00")
FIRST_NEXT_BILLING = datetime.fromisoformat("2026-10-24T09:00:00+08:00")


def context(user_id="U1", session_id="S1"):
    return TrustedContext(
        user_id=user_id, session_id=session_id, task_id="T1", run_id="R1",
        parent_task_id=None, demo_round_id="D1",
    )


def ready(tmp_path, *, timeout=2.0, authorize_cancel=lambda *args: True):
    """A bank at a fixed clock, so every seeded date is the same on any demo day."""
    bank = MockBankService(
        MockBankStore(StoragePaths(tmp_path).bank), demo_secret=DEMO_SECRET,
        clock=lambda: NOW,
    )
    gateway = BankGateway(
        bank, transfer_timeout_seconds=timeout,
        authorize_transfer=lambda *args: True, authorize_cancel=authorize_cancel,
    )
    return bank, gateway


def test_b29_lists_the_seeded_mandates_with_relative_dates(tmp_path):
    _, gateway = ready(tmp_path)
    try:
        result = gateway.list_subscriptions(context())
        assert result.kind == "ok"
        assert result.data.as_of == NOW
        youku, netdisk, ximalaya = result.data.mandates
        assert [item.mandate_id for item in result.data.mandates] == ["sub_001", "sub_002", "sub_003"]
        assert (youku.merchant_name, youku.service_name) == ("优酷视频", "优酷 VIP 连续包月")
        assert (youku.merchant_id, youku.account_id, youku.account_masked) == ("M_UYUN", "A1", "****0001")
        assert (youku.amount_fen, youku.cycle, youku.status) == (2500, "monthly", "active")
        assert youku.next_billing_at == FIRST_NEXT_BILLING
        assert youku.last_billed_at == datetime.fromisoformat("2026-09-19T09:00:00+08:00")
        assert youku.signed_at == datetime.fromisoformat("2025-10-19T09:00:00+08:00")
        assert netdisk.mandate_id == "sub_002"
        assert netdisk.next_billing_at == datetime.fromisoformat("2026-10-31T09:00:00+08:00")
        assert ximalaya.status == "cancelled" and ximalaya.next_billing_at is None
        assert ximalaya.cancelled_at == datetime.fromisoformat("2026-08-19T09:00:00+08:00")
        assert ximalaya.cancel_operation_id is not None
        assert [item.mandate_id for item in gateway.list_subscriptions(context(), None, "active").data.mandates] == [
            "sub_001", "sub_002"]
        assert [item.mandate_id for item in gateway.list_subscriptions(context(), "A1").data.mandates] == [
            "sub_001", "sub_002", "sub_003"]
        assert gateway.list_subscriptions(context("U2", "S2")).data.mandates == []
    finally:
        gateway.close()


def test_b29_rejects_blank_user_foreign_account_and_unknown_status(tmp_path):
    bank, gateway = ready(tmp_path)
    try:
        assert bank.list_subscriptions("").error.code == "INVALID_ARGUMENT"
        assert bank.list_subscriptions("   ").error.code == "INVALID_ARGUMENT"
        assert bank.list_subscriptions("U1", "A1", "closed").error.code == "INVALID_ARGUMENT"
        assert bank.list_subscriptions("U1", "U2A1").error.code == "ACCESS_DENIED"
        assert bank.list_subscriptions("U1", "A404").error.code == "ACCESS_DENIED"
        assert bank.list_subscriptions("U2", "A1").error.code == "ACCESS_DENIED"
    finally:
        gateway.close()


def test_b30_cancels_once_and_replays_the_first_receipt(tmp_path):
    bank, gateway = ready(tmp_path)
    try:
        user = context()
        operation_id = uuid4()
        first = gateway.cancel_subscription(user, operation_id, "sub_001")
        assert first.operation_type == "bank.cancel_subscription"
        assert first.operation_status == "succeeded" and first.failure is None
        receipt = first.receipt
        assert receipt.mandate_id == "sub_001" and receipt.amount_fen == 2500
        assert receipt.previous_next_billing_at == FIRST_NEXT_BILLING
        assert receipt.effective_stop_at == receipt.previous_next_billing_at
        assert receipt.cancelled_at == NOW and receipt.status == "cancelled"
        assert gateway.cancel_subscription(user, operation_id, "sub_001") == first
        assert gateway.cancel_subscription(user, operation_id, "sub_002").error.code == "OPERATION_CONFLICT"
        assert gateway.cancel_subscription(user, uuid4(), "sub_001").error.code == "STATE_CONFLICT"
        next_round = user.model_copy(update={"demo_round_id": "D2"})
        assert gateway.cancel_subscription(next_round, operation_id, "sub_001").error.code == "OPERATION_CONFLICT"
        assert gateway.get_operation(next_round, operation_id).error.code == "ACCESS_DENIED"
        with closing(connect(bank.store.path)) as connection:
            cancellations = connection.execute(
                "SELECT COUNT(*) FROM bank_operations WHERE action_name = 'bank.cancel_subscription'",
            ).fetchone()[0]
        assert cancellations == 1
        mandates = {item.mandate_id: item for item in gateway.list_subscriptions(user).data.mandates}
        assert mandates["sub_001"].status == "cancelled"
        assert mandates["sub_001"].next_billing_at is None
        assert mandates["sub_001"].cancelled_at == NOW
        assert mandates["sub_001"].cancel_operation_id == operation_id
        assert mandates["sub_002"].status == "active"
        assert gateway.get_operation(user, operation_id).operation == first
        assert gateway.get_operation(context("U2", "S2"), operation_id).error.code == "ACCESS_DENIED"
        assert gateway.get_operation(user, uuid4()).lookup == "not_found"
    finally:
        gateway.close()


def test_b30_refuses_unknown_foreign_frozen_and_bad_operation_ids(tmp_path):
    bank, gateway = ready(tmp_path)
    try:
        assert gateway.cancel_subscription(context(), uuid4(), "sub_404").error.code == "RECORD_NOT_FOUND"
        assert gateway.cancel_subscription(context("U2", "S2"), uuid4(), "sub_001").error.code == "ACCESS_DENIED"
        assert gateway.cancel_subscription(context(), UUID(int=0), "sub_001").error.code == "INVALID_ARGUMENT"
        assert gateway.cancel_subscription(context(), "not-a-uuid", "sub_001").error.code == "INVALID_ARGUMENT"
        assert gateway.cancel_subscription(context(), None, "sub_001").error.code == "INVALID_ARGUMENT"
        # The demo has no B28 control yet, so freeze the debit account at the bank directly.
        with transaction(bank.store.path) as connection:
            connection.execute("UPDATE accounts SET account_status = 'frozen' WHERE account_id = 'A1'")
        unavailable = gateway.cancel_subscription(context(), uuid4(), "sub_001")
        assert unavailable.error.code == "ACCOUNT_UNAVAILABLE"
        assert unavailable.error.details == {"account_status": "frozen"}
        mandates = {item.mandate_id: item for item in gateway.list_subscriptions(context()).data.mandates}
        assert mandates["sub_001"].status == "active"
    finally:
        gateway.close()


def test_gateway_cancel_is_fail_closed_without_server_authorization(tmp_path):
    bank = MockBankService(
        MockBankStore(StoragePaths(tmp_path).bank), demo_secret=DEMO_SECRET, clock=lambda: NOW,
    )
    gateway = BankGateway(bank, transfer_timeout_seconds=2.0)
    try:
        operation_id = uuid4()
        assert gateway.cancel_subscription(context(), operation_id, "sub_001").error.code == "ACCESS_DENIED"
        assert gateway.get_operation(context(), operation_id).lookup == "not_found"
        assert gateway.list_subscriptions(context()).data.mandates[0].status == "active"
        assert gateway.cancel_subscription(context(), operation_id, "sub_001").error.code == "ACCESS_DENIED"
    finally:
        gateway.close()


def test_gateway_cancel_timeout_is_unknown_and_b14_finds_the_bank_result(tmp_path):
    bank, gateway = ready(tmp_path, timeout=0.02)
    try:
        user = context()
        operation_id = uuid4()
        original = bank.cancel_subscription

        def slow_cancel(*args, **kwargs):
            time.sleep(0.3)
            return original(*args, **kwargs)

        bank.cancel_subscription = slow_cancel
        assert gateway.cancel_subscription(user, operation_id, "sub_001").error.code == "CALL_TIMEOUT"
        deadline = time.monotonic() + 2
        found = gateway.get_operation(user, operation_id)
        while found.lookup == "not_found" and time.monotonic() < deadline:
            time.sleep(0.01)
            found = gateway.get_operation(user, operation_id)
        assert found.lookup == "found"
        assert found.operation.operation_status == "succeeded"
        assert found.operation.receipt.mandate_id == "sub_001"
        # The slow path is gone, so replaying the same number must return the first result,
        # not another timeout and not STATE_CONFLICT for the mandate it already cancelled.
        bank.cancel_subscription = original
        assert gateway.cancel_subscription(user, operation_id, "sub_001") == found.operation
    finally:
        gateway.close()


def test_subscription_seeds_are_idempotent_and_keep_runtime_cancellations(tmp_path):
    bank, gateway = ready(tmp_path)
    try:
        assert bank.seed_subscriptions() == 0
        written = bank.seed_flow_history()
        assert written > 0
        assert bank.seed_flow_history() == 0
        debits = [row for row in bank.store.list_ledger("U1", "A1")
                  if row["counterparty_id"] in {"M_UYUN", "M_UDRV", "M_OASIS"}]
        assert Counter(row["counterparty_id"] for row in debits) == {
            "M_UYUN": 6, "M_UDRV": 3, "M_OASIS": 5}
        assert {row["amount_fen"] for row in debits if row["counterparty_id"] == "M_UYUN"} == {2500}
        assert {row["amount_fen"] for row in debits if row["counterparty_id"] == "M_UDRV"} == {3900}
        oasis = sorted(datetime.fromisoformat(row["occurred_at"]) for row in debits
                       if row["counterparty_id"] == "M_OASIS")
        assert [at.month for at in oasis] == [5, 6, 7, 8, 9]
        assert {at.day for at in oasis} == {19}
        assert all(row["channel"] == "快捷支付" for row in debits
                   if row["counterparty_id"] == "M_OASIS")
        assert all(row["nature"] == "consumption" and row["direction"] == "outflow" for row in debits)
        operation_id = uuid4()
        assert gateway.cancel_subscription(context(), operation_id, "sub_001").operation_status == "succeeded"

        reopened = MockBankService(
            MockBankStore(bank.store.path), demo_secret=DEMO_SECRET, clock=lambda: NOW,
        )
        assert reopened.seed_subscriptions() == 0
        assert reopened.seed_flow_history() == 0
        mandates = {item.mandate_id: item for item in reopened.list_subscriptions("U1").data.mandates}
        assert mandates["sub_001"].status == "cancelled"
        assert mandates["sub_001"].cancel_operation_id == operation_id
        assert len([row for row in reopened.store.list_ledger("U1", "A1")
                    if row["counterparty_id"] == "M_UYUN"]) == 6
    finally:
        gateway.close()
