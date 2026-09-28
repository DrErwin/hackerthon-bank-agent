"""Executable v0.3 ordinary-transfer evaluations for the mock bank."""

from __future__ import annotations

import time
from threading import Event
from uuid import uuid4

import pytest

from app.contracts.bank import ManualPayee, SavedPayee
from app.contracts.common import DisplayField
from app.contracts.platform import TrustedContext
from app.contracts.security import VerificationSummary
from app.services.mock_bank.verification import AdminContext


MAMA = SavedPayee(kind="saved", payee_id="A2")


def _other_user(context: TrustedContext) -> TrustedContext:
    return context.model_copy(update={"user_id": "U2", "session_id": "S2"})


def test_mb001_accounts_and_limits_follow_owned_scope(bank_runtime, user_context):
    """B01/B02/B05: return the user's current account facts and hide other accounts."""
    _, _, _, new_gateway = bank_runtime
    gateway = new_gateway()

    accounts = gateway.list_accounts(user_context).data.accounts
    assert {account.account_id for account in accounts} == {"A1", "A5"}
    assert gateway.get_account(user_context, "A1").data.available_balance_fen == 6_000_000
    assert gateway.get_limits(user_context, "A1").data.single_limit_fen == 5_000_000
    assert gateway.get_limits(user_context, "A1").data.annual_remaining_fen is None
    assert gateway.get_account(_other_user(user_context), "A1").error.code == "ACCESS_DENIED"


def test_mb002_payee_search_and_account_verification_are_scoped(bank_runtime, user_context):
    """B03/B04: find a saved payee, verify supplied details, and return masked facts."""
    _, _, _, new_gateway = bank_runtime
    gateway = new_gateway()

    searches = {
        "remark": "妈妈",
        "name": "王阿姨",
        "phone": "13900000002",
        "account_number": "6222000000000002",
    }
    for kind, value in searches.items():
        candidates = gateway.list_payees(user_context, {"kind": kind, "value": value}).data.payees
        assert [candidate.payee_id for candidate in candidates] == ["A2"]
        assert candidates[0].account_masked == "****0002"
    assert gateway.list_payees(_other_user(user_context), {"kind": "remark", "value": "妈妈"}).data.payees == []

    manual_payee = ManualPayee(
        kind="manual", account_number="6222000000000002", account_name="王阿姨",
    )
    verified = gateway.verify_payee(user_context, manual_payee).data
    assert verified.matched and verified.payee.bank_name == "模拟合作银行"
    assert "6222000000000002" not in str(verified.payee.model_dump())
    outsider = gateway.verify_payee(_other_user(user_context), manual_payee).data
    assert not outsider.matched and outsider.payee is None

    unmatched = gateway.verify_payee(user_context, ManualPayee(
        kind="manual", account_number="not-a-real-account", account_name="未知收款人",
    )).data
    assert not unmatched.matched and unmatched.payee is None


def test_mb003_quote_and_precheck_report_bank_terms(bank_runtime, user_context):
    """B06/B07: a valid transfer quote is free and an eligible transfer can proceed."""
    _, _, _, new_gateway = bank_runtime
    gateway = new_gateway()

    quote = gateway.quote_transfer(user_context, "A1", MAMA, 50_000).data
    precheck = gateway.precheck_transfer(user_context, "A1", MAMA, 50_000).data
    assert (quote.fee_fen, quote.arrival_mode) == (0, "instant")
    assert precheck.can_proceed and precheck.failure is None
    assert (precheck.fee_fen, precheck.arrival_mode) == (0, "instant")
    assert precheck.checked_at.tzinfo is not None


def test_mb004_precheck_refuses_insufficient_funds(bank_runtime, user_context):
    """B07: insufficient funds returns bank-calculated available, required, and shortfall values."""
    _, _, _, new_gateway = bank_runtime
    gateway = new_gateway()

    result = gateway.precheck_transfer(user_context, "A1", MAMA, 6_100_000).data
    assert not result.can_proceed and result.failure.code == "INSUFFICIENT_FUNDS"
    assert result.failure.details == {
        "available_fen": 6_000_000,
        "required_fen": 6_100_000,
        "shortfall_fen": 100_000,
    }


def test_mb005_precheck_refuses_single_limit_exceeded(bank_runtime, user_context):
    """B07: adequate funds do not override the single-transfer limit."""
    _, _, _, new_gateway = bank_runtime
    gateway = new_gateway()

    result = gateway.precheck_transfer(user_context, "A1", MAMA, 5_500_000).data
    assert not result.can_proceed and result.failure.code == "LIMIT_EXCEEDED"
    assert result.failure.details == {
        "scope": "single", "allowed_fen": 5_000_000, "requested_fen": 5_500_000,
    }


def test_mb006_daily_limit_is_recomputed_after_a_transfer(bank_runtime, user_context):
    """B05/B07/B09: submission rechecks a precheck made stale by an earlier transfer."""
    _, _, _, new_gateway = bank_runtime
    gateway = new_gateway()

    stale_operation_id = uuid4()
    before = gateway.precheck_transfer(user_context, "A1", MAMA, 1_000_000).data
    assert before.can_proceed
    first = gateway.submit_transfer(user_context, uuid4(), "A1", MAMA, 4_500_000)
    assert first.operation_status == "succeeded"
    assert gateway.get_limits(user_context, "A1").data.daily_remaining_fen == 500_000
    second = gateway.submit_transfer(user_context, stale_operation_id, "A1", MAMA, 1_000_000)
    assert second.operation_status == "failed" and second.failure.code == "LIMIT_EXCEEDED"
    assert second.failure.details["scope"] == "day"
    assert second.failure.details["allowed_fen"] == 500_000


def test_mb007_fraud_payee_is_rejected_without_a_ledger_entry(bank_runtime, user_context):
    """B07/B09: the bank blocks a blacklisted target and leaves the account unchanged."""
    bank, _, _, new_gateway = bank_runtime
    gateway = new_gateway()
    before = gateway.get_account(user_context, "A1").data.available_balance_fen
    risky_payee = SavedPayee(kind="saved", payee_id="A7")

    precheck = gateway.precheck_transfer(user_context, "A1", risky_payee, 50_000).data
    submitted = gateway.submit_transfer(user_context, uuid4(), "A1", risky_payee, 50_000)
    assert precheck.failure.code == "RISK_REJECTED"
    assert submitted.operation_status == "failed"
    assert submitted.failure.code == "RISK_REJECTED"
    assert gateway.get_account(user_context, "A1").data.available_balance_fen == before
    assert bank.store.list_ledger("U1", "A1") == []


def test_mb008_step_up_verification_needs_code_and_mock_face(bank_runtime, user_context):
    """Verification contract: store a two-factor result tied to this transfer operation."""
    _, _, _, new_gateway = bank_runtime
    gateway = new_gateway()
    operation_id = uuid4()
    summary = VerificationSummary(
        operation_id=operation_id, action_revision=1,
        source_confirmation_id="C1", source_confirmation_version=1,
        action_name="bank.submit_transfer", amount_fen=50_000,
        payee=gateway.verify_payee(user_context, MAMA).data.payee,
        display_fields=[DisplayField(name="amount", label="金额", value_text="500 元")],
    )

    challenge = gateway.create_verification(
        user_context, "action_step_up", operation_id, 1, summary,
    )
    assert not hasattr(challenge, "code")
    assert challenge.required_methods == ["code", "mock_face"]
    gateway.start_face(user_context, challenge.challenge_id, uuid4())
    code = gateway.get_demo_code_for_api(user_context, challenge.challenge_id)
    assert "code" not in challenge.model_dump()
    code_result = gateway.verify_code(user_context, challenge.challenge_id, uuid4(), code)
    assert code_result.kind == "verified" and code_result.verification_id is None

    for admin in (
        AdminContext("demo-admin", False, "D1", "U1"),
        AdminContext("demo-admin", True, "D2", "U1"),
        AdminContext("demo-admin", True, "D1", "U2"),
    ):
        with pytest.raises(ValueError, match="ACCESS_DENIED"):
            gateway.verify_face(admin, challenge.challenge_id, uuid4(), "passed")

    completed = gateway.verify_face(
        AdminContext("demo-admin", True, "D1", "U1"),
        challenge.challenge_id, uuid4(), "passed",
    )
    record = gateway.get_verification_record(user_context, completed.verification_id)
    assert completed.kind == "verified"
    assert record.scope == "action" and record.operation_id == operation_id
    assert record.action_revision == 1 and record.methods == ["code", "mock_face"]
    for changed_context in (
        user_context.model_copy(update={"user_id": "U2"}),
        user_context.model_copy(update={"session_id": "S2"}),
        user_context.model_copy(update={"task_id": "T2"}),
        user_context.model_copy(update={"demo_round_id": "D2"}),
    ):
        with pytest.raises(ValueError, match="ACCESS_DENIED"):
            gateway.get_verification_record(changed_context, completed.verification_id)


def test_mb009_transfer_authorization_denial_does_not_submit(bank_runtime, user_context):
    """Gateway isolation: missing or denied authorization cannot reach the bank write."""
    bank, _, _, new_gateway = bank_runtime
    before = new_gateway().get_account(user_context, "A1").data.available_balance_fen

    for authorized in (None, False):
        gateway = new_gateway(authorized=authorized)
        operation_id = uuid4()
        denied = gateway.submit_transfer(user_context, operation_id, "A1", MAMA, 50_000)
        lookup = gateway.get_operation(user_context, operation_id)
        assert denied.error.code == "ACCESS_DENIED"
        assert lookup.lookup == "not_found"
        assert gateway.get_account(user_context, "A1").data.available_balance_fen == before
    assert bank.store.list_ledger("U1", "A1") == []


def test_mb010_same_operation_and_parameters_return_one_result(bank_runtime, user_context):
    """B09/B14: replaying one operation ID with the same inputs returns the original result."""
    bank, _, _, new_gateway = bank_runtime
    gateway = new_gateway()
    operation_id = uuid4()

    first = gateway.submit_transfer(user_context, operation_id, "A1", MAMA, 50_000)
    replay = gateway.submit_transfer(user_context, operation_id, "A1", MAMA, 50_000)
    lookup = gateway.get_operation(user_context, operation_id)
    assert first.operation_status == "succeeded"
    assert replay == first
    assert lookup.lookup == "found" and lookup.operation == first
    assert gateway.get_account(user_context, "A1").data.book_balance_fen == 5_950_000
    assert len(bank.store.list_ledger("U1", "A1")) == 1


def test_mb011_changed_parameters_conflict_and_other_user_is_denied(bank_runtime, user_context):
    """B09/B14: an ID cannot be reused with changed values or read by another user."""
    bank, _, _, new_gateway = bank_runtime
    gateway = new_gateway()
    operation_id = uuid4()

    original = gateway.submit_transfer(user_context, operation_id, "A1", MAMA, 50_000)
    conflict = gateway.submit_transfer(user_context, operation_id, "A1", MAMA, 60_000)
    outsider_lookup = gateway.get_operation(_other_user(user_context), operation_id)
    assert original.operation_status == "succeeded"
    assert conflict.error.code == "OPERATION_CONFLICT"
    assert outsider_lookup.error.code == "ACCESS_DENIED"
    assert gateway.get_operation(user_context, operation_id).operation == original
    assert len(bank.store.list_ledger("U1", "A1")) == 1


def test_mb012_timeout_is_resolved_by_querying_the_original_operation(
    bank_runtime, user_context, monkeypatch,
):
    """B09/B14: timeout is unknown, then the same operation ID reveals the bank result."""
    bank, _, _, new_gateway = bank_runtime
    processing_saved = Event()
    release_worker = Event()
    original_commit = bank.store.commit_operation

    def commit_and_pause(*args, **kwargs):
        saved = original_commit(*args, **kwargs)
        if saved.status == "processing":
            processing_saved.set()
            assert release_worker.wait(timeout=2), "test did not release the slow bank worker"
        return saved

    monkeypatch.setattr(bank.store, "commit_operation", commit_and_pause)
    bank.arm_slow_once("U1")
    gateway = new_gateway(timeout=0.01)
    operation_id = uuid4()

    timed_out = gateway.submit_transfer(user_context, operation_id, "A1", MAMA, 50_000)
    assert timed_out.error.code == "CALL_TIMEOUT"
    try:
        assert processing_saved.wait(timeout=2), "bank did not persist the processing result"
        in_progress = gateway.get_operation(user_context, operation_id)
        assert in_progress.lookup == "found"
        assert in_progress.operation.operation_status == "processing"
    finally:
        release_worker.set()

    deadline = time.monotonic() + 2
    while True:
        lookup = gateway.get_operation(user_context, operation_id)
        if lookup.lookup == "found" and lookup.operation.operation_status == "succeeded":
            break
        assert time.monotonic() < deadline, "original operation did not reach a final bank result"
        time.sleep(0.01)

    assert lookup.operation.operation_id == operation_id
    assert gateway.get_account(user_context, "A1").data.book_balance_fen == 5_950_000
    assert len(bank.store.list_ledger("U1", "A1")) == 1


def test_mb013_unknown_operation_is_not_reported_as_failed(bank_runtime, user_context):
    """B14: a successful lookup of an unknown ID uses not_found, not a fabricated failure."""
    _, _, _, new_gateway = bank_runtime
    gateway = new_gateway()

    result = gateway.get_operation(user_context, uuid4())
    assert result.lookup == "not_found" and result.operation is None


def test_mb014_seeded_data_and_operation_survive_service_restart(bank_runtime, user_context):
    """Persistence: reopening the disposable bank file preserves seed changes and the receipt."""
    bank, database_path, new_bank, new_gateway = bank_runtime
    gateway = new_gateway()
    operation_id = uuid4()
    result = gateway.submit_transfer(user_context, operation_id, "A1", MAMA, 50_000)
    assert result.operation_status == "succeeded"

    reopened = new_bank()
    reopened_gateway = new_gateway(reopened)
    assert reopened_gateway.get_operation(user_context, operation_id).operation == result
    assert reopened_gateway.get_account(user_context, "A1").data.book_balance_fen == 5_950_000
    assert len(reopened.store.list_ledger("U1", "A1")) == 1
    assert bank.store.path == database_path
