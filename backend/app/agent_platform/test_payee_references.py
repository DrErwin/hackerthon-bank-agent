"""Controlled payee references use real task scope, storage and bank facts."""

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.contracts.bank import ManualPayee, QueryFailure, BankError
from app.contracts.common import TaskStatus
from app.storage.database import connect

from .payee_references import ControlledPayeeReference
from .test_transfer_runtime import runtime, trusted
from app.services.mock_bank.core import MockBankService
from app.storage.mock_bank.repository import MockBankStore


@pytest.fixture
def setup(tmp_path):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    app = runtime(tmp_path / "application.sqlite", bank)
    now = datetime.now(timezone.utc)
    for user, session, task, round_id in (
        ("U1", "S1", "T1", "D1"), ("U1", "S2", "T2", "D1"),
        ("U2", "S3", "T3", "D1"), ("U1", "S4", "T4", "D2"),
    ):
        app.application.create_session(session, user, round_id, now.isoformat(),
                                       (now + timedelta(days=1)).isoformat())
        app.application.create_task(task, user, session, round_id, "R1", TaskStatus.WAITING_INPUT, {})
    yield app, bank
    app.close()


def manual(name="王阿姨", number="6222000000000002"):
    return ManualPayee(kind="manual", account_name=name, account_number=number)


def test_registration_returns_only_bank_display_and_resolves_after_restart(setup):
    app, bank = setup
    expected = bank.verify_payee("U1", manual()).data.payee
    ref = app.payee_references.register(trusted(), manual(), 1)
    assert isinstance(ref, ControlledPayeeReference)
    assert ref.display == expected
    assert manual().account_number not in str(asdict(ref))
    restarted = runtime(app.application.path, bank)
    try:
        assert restarted.payee_references.resolve(trusted("R2"), ref.reference, 1) == manual()
        resolved = restarted.payee_references.resolve(trusted(), ref.reference, 1)
        assert restarted.gateway.verify_payee(trusted(), resolved).data.matched
        assert restarted.gateway.precheck_transfer(trusted(), "A1", resolved, 50000).data.can_proceed
        assert len(bank.store.list_ledger("U1", "A1")) == 0
        connection = connect(app.application.path)
        try:
            for table in ("tasks", "audit_events", "audit_evidence", "checkpoints",
                          "checkpoint_blobs", "checkpoint_writes"):
                # Report only the table name if a secret is found.
                rows = connection.execute(f"SELECT * FROM {table}").fetchall()
                assert all(manual().account_number not in str(tuple(row)) for row in rows), table
        finally:
            connection.close()
    finally:
        restarted.close()


@pytest.mark.parametrize("updates", [
    {"user_id": "U2", "session_id": "S3", "task_id": "T3"},
    {"session_id": "S2", "task_id": "T2"},
    {"demo_round_id": "D2", "session_id": "S4", "task_id": "T4"},
    {"session_id": "S2"},
])
def test_reference_denies_other_scope(setup, updates):
    app, _ = setup
    ref = app.payee_references.register(trusted(), manual(), 1)
    with pytest.raises((ValueError, PermissionError)):
        app.payee_references.resolve(trusted().model_copy(update=updates), ref.reference, 1)


def test_version_change_and_revocation_deny_old_reference(setup):
    app, _ = setup
    first = app.payee_references.register(trusted(), manual(), 1)
    with pytest.raises(ValueError, match="ACCESS_DENIED"):
        app.payee_references.resolve(trusted(), first.reference, 2)
    second = app.payee_references.register(trusted(), manual("李先生", "6222000000000003"), 2)
    with pytest.raises(ValueError, match="ACCESS_DENIED"):
        app.payee_references.resolve(trusted(), first.reference, 1)
    assert app.payee_references.resolve(trusted(), second.reference, 2).account_name == "李先生"
    app.payee_references.clear(trusted())
    with pytest.raises(ValueError, match="ACCESS_DENIED"):
        app.payee_references.resolve(trusted(), second.reference, 2)


def test_mismatch_invalidates_prior_material_and_creates_no_reference(setup):
    app, _ = setup
    ref = app.payee_references.register(trusted(), manual(), 1)
    unmatched = app.payee_references.register(trusted(), manual("错误户名"), 2)
    assert not unmatched.data.matched
    assert unmatched.data.payee is None
    with pytest.raises(ValueError, match="ACCESS_DENIED"):
        app.payee_references.resolve(trusted(), ref.reference, 1)
    connection = connect(app.application.path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM transfer_snapshots WHERE action_name = ?",
                                  (app.payee_references.action_name,)).fetchone()[0] == 0
    finally:
        connection.close()


def test_bank_or_storage_failure_never_returns_a_reference_or_raw_error(setup):
    app, _ = setup
    for target, method in ((app.gateway, "verify_payee"), (app.snapshots, "save")):
        with patch.object(target, method, side_effect=RuntimeError(manual().account_number)):
            with pytest.raises(RuntimeError, match="PAYEE_REGISTRATION_FAILED") as caught:
                app.payee_references.register(trusted(), manual(), 1)
        assert manual().account_number not in str(caught.value)
    failure = QueryFailure(kind="error", error=BankError(code="BANK_UNAVAILABLE", details={}))
    with patch.object(app.gateway, "verify_payee", return_value=failure):
        assert app.payee_references.register(trusted(), manual(), 1) == failure


def test_round_reset_and_expired_session_deny_reference(setup):
    app, _ = setup
    ref = app.payee_references.register(trusted(), manual(), 1)
    with patch.object(app.memory, "active_round", return_value="D2"):
        with pytest.raises(ValueError, match="STALE_ROUND"):
            app.payee_references.resolve(trusted(), ref.reference, 1)
        with pytest.raises(ValueError, match="STALE_ROUND"):
            app.payee_references.register(trusted(), manual(), 2)
    with patch("app.memory.adapter.datetime") as clock:
        clock.fromisoformat = datetime.fromisoformat
        clock.now.return_value = datetime.now(timezone.utc) + timedelta(days=2)
        with pytest.raises(PermissionError, match="AUTH_REQUIRED"):
            app.payee_references.resolve(trusted(), ref.reference, 1)


def test_unauthorized_registration_does_not_call_bank_or_erase_owner_reference(setup):
    app, _ = setup
    ref = app.payee_references.register(trusted(), manual(), 1)
    with patch.object(app.gateway, "verify_payee") as verify:
        with pytest.raises(PermissionError):
            app.payee_references.register(trusted().model_copy(update={"session_id": "S2"}), manual(), 2)
    verify.assert_not_called()
    assert app.payee_references.resolve(trusted(), ref.reference, 1) == manual()
