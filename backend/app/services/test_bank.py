"""Bank boundary and ordinary-transfer behavior."""

from __future__ import annotations

import time
from uuid import uuid4

from app.contracts.bank import ManualPayee, OwnPayee, SavedPayee
from app.contracts.platform import TrustedContext
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.storage import StoragePaths
from app.storage.mock_bank.repository import MockBankStore


def context(user_id="U1", session_id="S1"):
    return TrustedContext(
        user_id=user_id, session_id=session_id, task_id="T1", run_id="R1",
        parent_task_id=None, demo_round_id="D1",
    )


def ready(tmp_path, *, slow_seconds=0.1, timeout=0.02):
    bank = MockBankService(MockBankStore(StoragePaths(tmp_path).bank), slow_seconds=slow_seconds)
    return bank, BankGateway(bank, transfer_timeout_seconds=timeout)


def test_seeded_transfer_and_replay_keep_one_bank_result(tmp_path):
    bank, gateway = ready(tmp_path)
    user = context()
    payee = SavedPayee(kind="saved", payee_id="A2")
    assert gateway.list_accounts(user).data.accounts[0].available_balance_fen == 6_000_000
    assert gateway.list_payees(user, {"kind": "remark", "value": "妈"}).data.payees[0].payee_id == "A2"
    assert gateway.verify_payee(user, payee).data.matched
    assert gateway.quote_transfer(user, "A1", payee, 50_000).data.fee_fen == 0
    assert gateway.precheck_transfer(user, "A1", payee, 50_000).data.can_proceed
    operation_id = uuid4()
    first = gateway.submit_transfer(user, operation_id, "A1", payee, 50_000)
    assert first.operation_status == "succeeded"
    assert first.receipt.amount_fen == 50_000
    assert first.receipt.payee.account_masked.endswith("0002")
    assert gateway.submit_transfer(user, operation_id, "A1", payee, 50_000) == first
    assert gateway.submit_transfer(user, operation_id, "A1", payee, 60_000).error.code == "OPERATION_CONFLICT"
    assert gateway.submit_transfer(context("U2", "S2"), operation_id, "U2A1", payee, 50_000).error.code == "OPERATION_CONFLICT"
    assert gateway.get_operation(user, operation_id).operation == first
    assert gateway.get_account(user, "A1").data.book_balance_fen == 5_950_000
    assert len(bank.store.list_ledger("U1", "A1")) == 1
    gateway.close()

    reopened = BankGateway(MockBankService(MockBankStore(StoragePaths(tmp_path).bank)))
    assert reopened.get_operation(user, operation_id).operation == first
    assert reopened.get_account(user, "A1").data.book_balance_fen == 5_950_000
    reopened.close()


def test_bank_rejects_scope_balance_limit_payee_and_risk(tmp_path):
    _, gateway = ready(tmp_path)
    user = context()
    other = context("U2", "S2")
    mama = SavedPayee(kind="saved", payee_id="A2")
    assert gateway.get_account(other, "A1").error.code == "ACCESS_DENIED"
    assert gateway.verify_payee(other, mama).data.matched is False
    assert gateway.precheck_transfer(other, "A1", mama, 50_000).error.code == "ACCESS_DENIED"
    assert gateway.precheck_transfer(user, "A1", mama, 6_100_000).data.failure.code == "INSUFFICIENT_FUNDS"
    assert gateway.precheck_transfer(user, "A1", mama, 5_500_000).data.failure.details["scope"] == "single"
    assert gateway.precheck_transfer(
        user, "A1", ManualPayee(kind="manual", account_number="wrong", account_name="王阿姨"), 50_000,
    ).data.failure.code == "PAYEE_MISMATCH"
    assert gateway.precheck_transfer(user, "A1", SavedPayee(kind="saved", payee_id="A7"), 50_000).data.failure.code == "RISK_REJECTED"
    operation_id = uuid4()
    assert gateway.submit_transfer(user, operation_id, "A1", mama, 5_500_000).operation_status == "failed"
    assert gateway.get_operation(other, operation_id).error.code == "ACCESS_DENIED"
    assert gateway.get_operation(user, uuid4()).lookup == "not_found"
    gateway.close()


def test_own_account_transfer_credits_target_once(tmp_path):
    bank, gateway = ready(tmp_path)
    user = context()
    target = OwnPayee(kind="own", account_id="A5")
    operation_id = uuid4()
    result = gateway.submit_transfer(user, operation_id, "A1", target, 12_345)
    assert result.operation_status == "succeeded"
    assert gateway.submit_transfer(user, operation_id, "A1", target, 12_345) == result
    assert gateway.get_account(user, "A5").data.book_balance_fen == 12_345
    assert gateway.get_account(user, "A1").data.book_balance_fen == 6_000_000 - 12_345
    assert len(bank.store.list_ledger("U1", "A5")) == 1
    gateway.close()


def test_day_limit_uses_bank_ledger_and_failure_is_replayable(tmp_path):
    bank, gateway = ready(tmp_path)
    user = context()
    payee = SavedPayee(kind="saved", payee_id="A2")
    first = gateway.submit_transfer(user, uuid4(), "A1", payee, 4_000_000)
    assert first.operation_status == "succeeded"
    assert gateway.get_limits(user, "A1").data.daily_remaining_fen == 1_000_000
    operation_id = uuid4()
    denied = gateway.submit_transfer(user, operation_id, "A1", payee, 2_000_000)
    assert denied.operation_status == "failed"
    assert denied.failure.code == "LIMIT_EXCEEDED"
    assert denied.failure.details["scope"] == "day"
    assert gateway.submit_transfer(user, operation_id, "A1", payee, 2_000_000) == denied
    assert len(bank.store.list_ledger("U1", "A1")) == 1
    gateway.close()


def test_timeout_returns_unknown_then_original_result_becomes_visible(tmp_path):
    bank, gateway = ready(tmp_path)
    bank.arm_slow_once("U1")
    user = context()
    operation_id = uuid4()
    payee = SavedPayee(kind="saved", payee_id="A2")
    response = gateway.submit_transfer(user, operation_id, "A1", payee, 50_000)
    assert response.error.code == "CALL_TIMEOUT"
    assert gateway.get_operation(user, operation_id).operation.operation_status == "processing"
    time.sleep(0.12)
    found = gateway.get_operation(user, operation_id)
    assert found.operation.operation_status == "succeeded"
    assert gateway.submit_transfer(user, operation_id, "A1", payee, 50_000) == found.operation
    assert len(bank.store.list_ledger("U1", "A1")) == 1
    gateway.close()
