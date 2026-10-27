"""B26 bank facts: reset only the isolated bank and keep management receipts."""

from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import uuid4

import pytest

from app.contracts.bank import FreezeFundsInput, SavedPayee
from app.contracts.platform import TrustedContext
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.services.mock_bank.verification import AdminContext
from app.storage.database import connect, transaction
from app.storage.mock_bank.repository import MockBankStore


INITIAL = datetime(2026, 10, 27, 9, tzinfo=timezone(timedelta(hours=8)))
SECRET = b"b26-isolated-test-secret-32-bytes-minimum"


def context(round_id="D1"):
    return TrustedContext(user_id="U1", session_id="S1", task_id="T1", run_id="R1",
                          parent_task_id=None, demo_round_id=round_id)


def admin(round_id="D1", *, authorized=True, actor="admin-1"):
    return AdminContext(actor, authorized, round_id, "U1")


def ready(tmp_path, *, timeout=2, **kwargs):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite3"),
                           demo_secret=SECRET, clock=lambda: INITIAL, **kwargs)
    gate = BankGateway(bank, authorize_transfer=lambda *_: True,
                       authorize_birthday=lambda *_: True,
                       authorize_cancel=lambda *_: True,
                       transfer_timeout_seconds=timeout)
    return bank, gate


def rows(bank, table):
    with connect(bank.store.path) as connection:
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]


def reset(bank, operation="reset-1", **kwargs):
    return bank.reset_demo(admin(), operation, "D1", "D2", INITIAL, **kwargs)


def test_reset_restores_seed_facts_and_persists_its_original_result(tmp_path):
    bank, gate = ready(tmp_path)
    try:
        assert bank.current_demo_logical_at is None
        transfer = gate.submit_transfer(context(), uuid4(), "A1", SavedPayee(kind="saved", payee_id="A2"), 50000)
        assert transfer.operation_status == "succeeded"
        frozen = gate.freeze_funds(context(), uuid4(), FreezeFundsInput(
            account_id="A1", amount_fen=30000, reason="生日"))
        assert frozen.operation_status == "succeeded"
        challenge = gate.create_verification(context(), "basic_identity")
        before = bank.store.get_account("U1", "A1")
        assert before.book_balance_fen == 5950000

        result = reset(bank)
        assert result.status == "succeeded"
        assert (result.source_round_id, result.demo_round_id, result.logical_at) == ("D1", "D2", INITIAL)
        assert bank.current_demo_round_id == "D2"
        assert bank.current_demo_logical_at == INITIAL
        restored = bank.store.get_account("U1", "A1")
        assert (restored.book_balance_fen, restored.frozen_balance_fen) == (6000000, 0)
        for table in ("bank_operations", "bank_operation_scopes", "freezes", "orders", "order_payments"):
            assert rows(bank, table) == []
        with pytest.raises(ValueError, match="^ACCESS_DENIED$"):
            gate.get_verification(context(), challenge.challenge_id)
        assert rows(bank, "ledger_entries")
        fresh, fresh_gate = ready(tmp_path / "fresh")
        try:
            fresh.seed_flow_history()
            assert rows(bank, "ledger_entries") == rows(fresh, "ledger_entries")
            assert rows(bank, "bank_subscriptions") == rows(fresh, "bank_subscriptions")
        finally:
            fresh_gate.close()
    finally:
        gate.close()
    reopened, reopened_gate = ready(tmp_path)
    try:
        assert reopened.current_demo_round_id == "D2"
        assert reopened.current_demo_logical_at == INITIAL
        assert reopened.get_demo_management_operation(admin("D2"), "reset-1") == result
    finally:
        reopened_gate.close()


def test_successful_replay_does_not_clear_new_round_activity(tmp_path):
    bank, gate = ready(tmp_path)
    try:
        first = reset(bank)
        assert first.status == "succeeded"
        transferred = gate.submit_transfer(context("D2"), uuid4(), "A1",
            SavedPayee(kind="saved", payee_id="A2"), 10000)
        assert transferred.operation_status == "succeeded"
        assert reset(bank) == first
        assert bank.current_demo_logical_at == INITIAL
        assert bank.store.get_account("U1", "A1").book_balance_fen == 5990000
        assert len(rows(bank, "bank_operations")) == 1
        conflict = bank.reset_demo(admin(), "reset-1", "D1", "D3", INITIAL)
        assert conflict.error.code == "OPERATION_CONFLICT"
        other_actor = bank.reset_demo(admin(actor="admin-2"), "reset-1", "D1", "D2", INITIAL)
        assert other_actor.error.code == "OPERATION_CONFLICT"
        assert bank.store.get_account("U1", "A1").book_balance_fen == 5990000
    finally:
        gate.close()


def test_unauthorized_or_wrong_round_reset_has_no_bank_effect(tmp_path):
    bank, gate = ready(tmp_path)
    try:
        assert bank.reset_demo(admin(authorized=False), "denied", "D1", "D2", INITIAL).error.code == "ACCESS_DENIED"
        assert bank.reset_demo(context(), "ordinary", "D1", "D2", INITIAL).error.code == "ACCESS_DENIED"
        assert bank.reset_demo(admin("other"), "stale", "D1", "D2", INITIAL).error.code == "ACCESS_DENIED"
        assert bank.current_demo_round_id is None
        assert rows(bank, "bank_management_operations") == []
    finally:
        gate.close()


def test_failed_seed_restore_rolls_back_then_the_same_operation_can_retry(tmp_path):
    bank, gate = ready(tmp_path)
    try:
        gate.submit_transfer(context(), uuid4(), "A1", SavedPayee(kind="saved", payee_id="A2"), 50000)
        with transaction(bank.store.path) as connection:
            connection.execute("""CREATE TRIGGER reject_reset_seed BEFORE INSERT ON accounts
                WHEN NEW.account_id = 'A1' BEGIN SELECT RAISE(ABORT, 'seed fault'); END""")
        failed = reset(bank)
        assert failed.status == "failed"
        assert bank.current_demo_round_id == "D1"
        assert bank.current_demo_logical_at is None
        assert bank.store.get_account("U1", "A1").book_balance_fen == 5950000
        assert len(rows(bank, "bank_operations")) == 1
        assert bank.get_demo_management_operation(admin(), "reset-1") == failed
        assert bank.reset_demo(admin(), "different-reset", "D1", "D2", INITIAL).error.code == "STATE_CONFLICT"
        assert bank.reset_demo(admin("other"), "reset-1", "D1", "D2", INITIAL).error.code == "ACCESS_DENIED"
        with transaction(bank.store.path) as connection:
            connection.execute("DROP TRIGGER reject_reset_seed")
        assert reset(bank).status == "succeeded"
        assert bank.store.get_account("U1", "A1").book_balance_fen == 6000000
    finally:
        gate.close()


def test_processing_transfer_keeps_original_reset_running_until_it_finishes(tmp_path, monkeypatch):
    bank, gate = ready(tmp_path, slow_seconds=0.3, timeout=0.02)
    started, release = Event(), Event()

    def wait_for_release(_seconds):
        started.set()
        release.wait()

    monkeypatch.setattr("app.services.mock_bank.core.time.sleep", wait_for_release)
    try:
        bank.arm_slow_once("U1")
        operation = uuid4()
        pending = gate.submit_transfer(context(), operation, "A1", SavedPayee(kind="saved", payee_id="A2"), 50000)
        assert pending.error.code == "CALL_TIMEOUT"
        assert started.wait(2)
        waiting = reset(bank)
        assert waiting.status == "running"
        assert bank.current_demo_logical_at is None
        assert len(rows(bank, "bank_operations")) == 1
        assert bank.reset_demo(admin(), "new-reset", "D1", "D2", INITIAL).error.code == "STATE_CONFLICT"
        release.set()
        gate.close()
        assert bank.get_operation(context(), operation).operation.operation_status == "succeeded"
        assert reset(bank).status == "succeeded"
        assert rows(bank, "bank_operations") == []
    finally:
        release.set()
        gate.close()


def test_later_pending_and_failed_resets_preserve_the_last_successful_origin(tmp_path, monkeypatch):
    bank, gate = ready(tmp_path, slow_seconds=0.3, timeout=0.02)
    started, release = Event(), Event()

    def wait_for_release(_seconds):
        started.set()
        assert release.wait(5)

    try:
        assert reset(bank).status == "succeeded"
        later = INITIAL + timedelta(days=1)
        monkeypatch.setattr("app.services.mock_bank.core.time.sleep", wait_for_release)
        bank.arm_slow_once("U1")
        assert gate.submit_transfer(context("D2"), uuid4(), "A1",
            SavedPayee(kind="saved", payee_id="A2"), 100).error.code == "CALL_TIMEOUT"
        assert started.wait(2)
        assert bank.reset_demo(admin("D2"), "reset-2", "D2", "D3", later).status == "running"
        assert bank.current_demo_logical_at == INITIAL
        release.set()
        assert gate.wait_for_inflight(3.0)
        with transaction(bank.store.path) as connection:
            connection.execute("""CREATE TRIGGER reject_later_seed BEFORE INSERT ON accounts
                WHEN NEW.account_id = 'A1' BEGIN SELECT RAISE(ABORT, 'seed fault'); END""")
        failed = bank.reset_demo(admin("D2"), "reset-2", "D2", "D3", later)
        assert failed.status == "failed"
        assert bank.current_demo_logical_at == INITIAL
        assert reset(bank).status == "succeeded"  # Old success replay is not a new origin.
        assert bank.current_demo_logical_at == INITIAL
        with transaction(bank.store.path) as connection:
            connection.execute("DROP TRIGGER reject_later_seed")
        assert bank.reset_demo(admin("D2"), "reset-2", "D2", "D3", later).status == "succeeded"
        assert bank.current_demo_logical_at == later
        assert reset(bank).status == "succeeded"
        assert bank.current_demo_logical_at == later
    finally:
        release.set()
        gate.close()


def test_old_round_cannot_write_after_reset_but_new_round_can(tmp_path):
    bank, gate = ready(tmp_path)
    try:
        assert reset(bank).status == "succeeded"
        assert gate.submit_transfer(context(), uuid4(), "A1", SavedPayee(kind="saved", payee_id="A2"), 50000).error.code == "ACCESS_DENIED"
        assert gate.freeze_funds(context(), uuid4(), FreezeFundsInput(
            account_id="A1", amount_fen=30000, reason="生日")).error.code == "ACCESS_DENIED"
        assert gate.submit_transfer(context("D2"), uuid4(), "A1", SavedPayee(kind="saved", payee_id="A2"), 50000).operation_status == "succeeded"
    finally:
        gate.close()


@pytest.mark.parametrize("target,at", [("D1", INITIAL), ("", INITIAL), ("D2", INITIAL.replace(tzinfo=None))])
def test_invalid_reset_arguments_cannot_create_a_management_operation(tmp_path, target, at):
    bank, gate = ready(tmp_path)
    try:
        assert bank.reset_demo(admin(), "invalid", "D1", target, at).error.code == "INVALID_ARGUMENT"
        assert bank.current_demo_round_id is None
        assert rows(bank, "bank_management_operations") == []
    finally:
        gate.close()


def test_reset_clears_old_faults_but_replay_keeps_new_faults(tmp_path, monkeypatch):
    bank, gate = ready(tmp_path)
    sleeps = []
    monkeypatch.setattr("app.services.mock_bank.core.time.sleep", sleeps.append)
    try:
        bank.arm_slow_once("U1")
        bank.birthday.arm_response_loss("U1")
        assert reset(bank).status == "succeeded"
        assert gate.submit_transfer(context("D2"), uuid4(), "A1",
            SavedPayee(kind="saved", payee_id="A2"), 10000).operation_status == "succeeded"
        assert sleeps == []
        assert gate.freeze_funds(context("D2"), uuid4(), FreezeFundsInput(
            account_id="A1", amount_fen=30000, reason="生日")).operation_status == "succeeded"
        bank.arm_slow_once("U1")
        assert reset(bank).status == "succeeded"
        assert gate.submit_transfer(context("D2"), uuid4(), "A1",
            SavedPayee(kind="saved", payee_id="A2"), 10000).operation_status == "succeeded"
        assert sleeps == [bank.slow_seconds]
    finally:
        gate.close()
