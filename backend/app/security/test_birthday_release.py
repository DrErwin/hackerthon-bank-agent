"""Ticket v05-cross-security/01: limited release authorization and finalization.

Failure modes enumerated before implementation (ticket verification table):

Grant:
1. pending/cancelled confirmation grants nothing;
2. a freeze confirmation without the §3.5 release clause grants nothing;
3. a non-freeze confirmation grants nothing;
4. another user's session/task cannot grant;
5. repeat grant of the same confirmation is idempotent.

Freeze binding:
6. a definitely failed freeze invalidates the authorization;
7. an unknown freeze stays pending and blocks finalization with zero bank writes;
8. a succeeded freeze whose amount differs from the confirmed amount is not activated;
9. a succeeded freeze binds freeze_id and becomes active, recoverable after restart.

Finalization:
10. normal ending releases exactly the bank-verified remainder (XL-B01/B06);
11. repeat finalization never submits a second release;
12. a still-running task cannot release early;
13. unresolved in-flight actions pause the release with zero writes;
14. zero remainder completes without submitting a zero-amount release;
15. bank remainder above the confirmed amount pauses instead of over-releasing;
16. a vanished freeze record invalidates the authorization;
17. a freeze on a different account than the authorization blocks;
18. another user/round/task reference is denied; unknown references are blocked;
19. an audit sink failure pauses before any bank write;
20. a snapshot writer failure pauses before any bank write;
21. a state-store failure at claim time performs no bank write;
22. a lost release response (timeout) records unknown and later resolves by the
    original operation id without resubmitting;
23. a definite bank release failure keeps the original id and needs attention.

Bank authorization callback:
24. no claim, wrong owner, wrong action, replayed completed claim, or non-allow
    decision all deny; only a live allow claim for the same identity passes.

The bank layer is the real MockBankService behind a real BankGateway whose
authorize_birthday is wired to the state-backed authorizer (真实银行层). Freeze
setup calls the bank service directly, which equals a server-side submission.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.contracts.bank import (
    BankError, CaptureFrozenInput, FreezeFundsInput, FreezeView, OperationNotFound,
    OperationResult, OperationStatus, QueryFailure, QueryOk, ReleaseFrozenInput,
)
from app.contracts.common import Category, DisplayField, OperationLevel, Phase, RiskLevel
from app.contracts.platform import TrustedContext
from app.contracts.security import (
    ActionDescriptor, ConfirmationAnswer, ConfirmationRecord,
    ExecutionSecurityContext, SecurityDecision, SecurityDecisionCode,
)
from app.security import ConfirmationService
from app.security.birthday_policy import (
    RELEASE_CLAUSE_FIELD, has_release_clause, with_release_clause,
)
from app.security.birthday_release import (
    LimitedReleaseFinalizer, authorize_birthday_write, bind_freeze_result,
    grant_release_authorization,
)
from app.security.gate import SecurityError
from app.security.state import SecurityStateError, SQLiteSecurityState
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.storage.database import transaction
from app.storage.mock_bank.repository import BankAccount, MockBankStore


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **amount: int) -> None:
        self.value += timedelta(**amount)


def context(**changes) -> ExecutionSecurityContext:
    values = {
        "user_id": "U1",
        "session_id": "S1",
        "demo_round_id": "D1",
        "task_id": "T1",
        "run_id": "R1",
        "source_task_id": None,
        "operation_id": uuid4(),
        "action_revision": 1,
        "confirmation_id": None,
        "confirmation_version": None,
        "verification_ids": [],
        "release_authorization_id": None,
    }
    values.update(changes)
    return ExecutionSecurityContext(**values)


def trusted(source: ExecutionSecurityContext) -> TrustedContext:
    return TrustedContext(
        user_id=source.user_id, session_id=source.session_id,
        demo_round_id=source.demo_round_id, task_id=source.task_id,
        run_id=source.run_id, parent_task_id=source.source_task_id,
    )


def freeze_action(parameters_ref: str) -> ActionDescriptor:
    return ActionDescriptor(
        action_name="bank.freeze_funds",
        parameters_ref=parameters_ref,
        resource_refs=["BA1"],
        phase=Phase.EXECUTION,
    )


def allow_decision(security_context: ExecutionSecurityContext, action: ActionDescriptor):
    return SecurityDecision(
        decision_id=str(uuid4()), task_id=security_context.task_id,
        run_id=security_context.run_id, action_name=action.action_name,
        parameters_ref=action.parameters_ref, operation_id=security_context.operation_id,
        action_revision=security_context.action_revision, phase=action.phase,
        operation_level=OperationLevel.SENSITIVE, risk_level=RiskLevel.LOW,
        decision=SecurityDecisionCode.ALLOW, reason_codes=["SECURITY_CHECK_PASSED"],
        rule_ids=["limited-release-authorized"], policy_version="test",
        authorization_snapshot_ref="AUTH-T", evidence_refs=[], interaction=None,
        checked_at=datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc), message="test",
    )


def approved_freeze_confirmation(
    confirmations: ConfirmationService, applicant: ExecutionSecurityContext,
    *, clause: bool = True,
) -> ConfirmationRecord:
    fields = [DisplayField(name="amount", label="冻结金额", value_text="500 元")]
    if clause:
        fields = with_release_clause(fields)
    record = confirmations.create(
        applicant, freeze_action("birthday:freeze:50000"), fields,
    )
    return confirmations.answer(applicant, ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version,
        choice="approve",
    ))


class Rig:
    """Real bank + gateway + security state wired for release acceptance."""

    def __init__(self, tmp_path, *, ended=True):
        self.clock = Clock()
        self.path = tmp_path / "application.sqlite3"
        self.state = SQLiteSecurityState(self.path)
        self.bank = MockBankService(
            MockBankStore(tmp_path / "bank.sqlite3"), demo_secret=b"s" * 32,
            slow_seconds=0.3,
        )
        self.bank.store.seed_account(
            BankAccount("BA1", "U1", "class_i", "active", 200000, 0, 0),
        )
        self.gateway = BankGateway(
            self.bank, transfer_timeout_seconds=0.15,
            authorize_birthday=authorize_birthday_write(self.state),
        )
        self.decisions: list = []
        self.snapshots: list = []
        self.task_ended = ended
        self.bank_calls: list = []
        self.finalizer = LimitedReleaseFinalizer(
            self.state,
            decision_sink=self.decisions.append,
            snapshot_writer=self._snapshot,
            task_state_resolver=lambda _context: self.task_ended,
            freeze_reader=self.gateway.get_freeze,
            operation_reader=self.gateway.get_operation,
            bank_release=self._bank_release,
            clock=self.clock,
        )

    def _snapshot(self, security_context, confirmation, verifications, checked_at):
        self.snapshots.append((security_context, confirmation, verifications, checked_at))
        return f"AUTH-{len(self.snapshots)}"

    def _bank_release(self, trusted_context, operation_id, request):
        self.bank_calls.append((trusted_context, operation_id, request))
        return self.gateway.release_frozen(trusted_context, operation_id, request)

    def rebuild_finalizer(self, *, freeze_reader=None):
        self.finalizer = LimitedReleaseFinalizer(
            self.state,
            decision_sink=self.decisions.append,
            snapshot_writer=self._snapshot,
            task_state_resolver=lambda _context: self.task_ended,
            freeze_reader=freeze_reader or self.gateway.get_freeze,
            operation_reader=self.gateway.get_operation,
            bank_release=self._bank_release,
            clock=self.clock,
        )

    def grant(self, *, clause: bool = True, amount_fen: int = 50000,
              applicant=None):
        applicant = applicant or context()
        confirmations = ConfirmationService(self.path, clock=self.clock)
        record = approved_freeze_confirmation(confirmations, applicant, clause=clause)
        authorization = grant_release_authorization(
            self.state, applicant, record,
            account_id="BA1", amount_fen=amount_fen, now=self.clock(),
        )
        return record, applicant, authorization

    def freeze_for_real(self, applicant: ExecutionSecurityContext):
        result = self.bank.birthday.freeze_funds(
            trusted(applicant), applicant.operation_id, "BA1", 50000, "生日礼物",
        )
        assert result.operation_status is OperationStatus.SUCCEEDED
        return result

    def active_authorization(self, *, clause: bool = True):
        record, applicant, authorization = self.grant(clause=clause)
        freeze = self.freeze_for_real(applicant)
        authorization = bind_freeze_result(
            self.state, applicant, authorization.release_authorization_id,
            freeze, self.clock(),
        )
        return record, applicant, authorization, freeze

    def capture(self, applicant, freeze_id: str, amount_fen: int):
        result = self.bank.birthday.capture_frozen(
            trusted(applicant), uuid4(), freeze_id, amount_fen,
            "m_flower", "邻里花店", "生日鲜花", Category.SHOPPING, None,
        )
        assert result.operation_status is OperationStatus.SUCCEEDED
        return result

    def ending_context(self, authorization, **changes) -> ExecutionSecurityContext:
        values = {
            "session_id": "SYS-CONTROLLED",
            "operation_id": None,
            "action_revision": None,
            "release_authorization_id": authorization.release_authorization_id,
        }
        values.update(changes)
        return context(**values)


# --- Grant (failure modes 1-5) ---


def test_pending_confirmation_grants_nothing(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    confirmations = ConfirmationService(rig.path, clock=rig.clock)
    fields = with_release_clause(
        [DisplayField(name="amount", label="冻结金额", value_text="500 元")])
    record = confirmations.create(
        applicant, freeze_action("birthday:freeze:50000"), fields,
    )
    assert record.decision == "pending"
    with pytest.raises(SecurityError, match="CONFIRMATION_REQUIRED"):
        grant_release_authorization(rig.state, applicant, record,
                                    account_id="BA1", amount_fen=50000,
                                    now=rig.clock())


def test_clause_free_confirmation_grants_nothing(tmp_path):
    rig = Rig(tmp_path)
    confirmations = ConfirmationService(rig.path, clock=rig.clock)
    record = approved_freeze_confirmation(confirmations, context(), clause=False)
    with pytest.raises(SecurityError, match="POLICY_VIOLATION"):
        grant_release_authorization(rig.state, context(), record,
                                    account_id="BA1", amount_fen=50000,
                                    now=rig.clock())


def test_non_freeze_confirmation_grants_nothing(tmp_path):
    rig = Rig(tmp_path)
    confirmations = ConfirmationService(rig.path, clock=rig.clock)
    applicant = context()
    order_action = ActionDescriptor(
        action_name="bank.create_order", parameters_ref="birthday:order:1",
        resource_refs=["p_flower"], phase=Phase.EXECUTION,
    )
    record = confirmations.create(
        applicant, order_action,
        with_release_clause(
            [DisplayField(name="product", label="商品", value_text="鲜花礼盒")]),
    )
    record = confirmations.answer(applicant, ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version, choice="approve",
    ))
    with pytest.raises(SecurityError, match="POLICY_VIOLATION"):
        grant_release_authorization(rig.state, applicant, record,
                                    account_id="BA1", amount_fen=19900,
                                    now=rig.clock())


def test_other_session_cannot_grant(tmp_path):
    rig = Rig(tmp_path)
    record, applicant, _ = rig.grant()
    intruder = applicant.model_copy(update={"user_id": "U2", "session_id": "S2"})
    with pytest.raises(SecurityError, match="ACCESS_DENIED"):
        grant_release_authorization(
            rig.state, intruder, record,
            account_id="BA1", amount_fen=50000, now=rig.clock(),
        )


def test_repeat_grant_is_idempotent(tmp_path):
    rig = Rig(tmp_path)
    record, applicant, authorization = rig.grant()
    again = grant_release_authorization(
        rig.state, applicant, record,
        account_id="BA1", amount_fen=50000, now=rig.clock(),
    )
    assert again == authorization
    assert again.status == "pending_freeze"
    assert has_release_clause(record.display_fields)
    assert record.display_fields[-1].name == RELEASE_CLAUSE_FIELD


# --- Freeze binding (failure modes 6-9) ---


def test_failed_freeze_invalidates_authorization(tmp_path):
    rig = Rig(tmp_path)
    _, applicant, authorization = rig.grant()
    failed = OperationResult(
        operation_id=applicant.operation_id, operation_type="bank.freeze_funds",
        operation_status=OperationStatus.FAILED, recorded_at=rig.clock(),
        updated_at=rig.clock(), receipt=None,
        failure=BankError(code="INSUFFICIENT_FUNDS", details={}),
    )
    bound = bind_freeze_result(
        rig.state, applicant, authorization.release_authorization_id,
        failed, rig.clock(),
    )
    assert bound.status == "invalid"


def test_unknown_freeze_stays_pending_and_blocks_finalization(tmp_path):
    rig = Rig(tmp_path)
    _, applicant, authorization = rig.grant()
    bound = bind_freeze_result(
        rig.state, applicant, authorization.release_authorization_id,
        OperationNotFound(lookup="not_found", operation=None), rig.clock(),
    )
    assert bound.status == "pending_freeze"
    outcome = rig.finalizer.finalize(rig.ending_context(bound), "user_cancelled")
    assert outcome.status == "needs_attention"
    assert rig.bank_calls == []


def test_amount_mismatch_is_not_activated(tmp_path):
    rig = Rig(tmp_path)
    _, applicant, authorization = rig.grant(amount_fen=40000)
    freeze = rig.freeze_for_real(applicant)  # bank froze 50000, confirmation said 40000
    with pytest.raises(SecurityError, match="POLICY_VIOLATION"):
        bind_freeze_result(
            rig.state, applicant, authorization.release_authorization_id,
            freeze, rig.clock(),
        )


def test_succeeded_freeze_binds_and_survives_restart(tmp_path):
    rig = Rig(tmp_path)
    _, applicant, authorization, freeze = rig.active_authorization()
    assert authorization.status == "active"
    assert authorization.freeze_id == freeze.receipt.freeze_id
    reopened = SQLiteSecurityState(rig.path)
    stored = reopened.get_release_authorization(
        rig.ending_context(authorization), authorization.release_authorization_id,
    )
    assert stored == authorization


# --- Finalization (failure modes 10-23) ---


def test_normal_ending_releases_only_the_remainder(tmp_path):
    rig = Rig(tmp_path)
    _, applicant, authorization, freeze = rig.active_authorization()
    freeze_id = freeze.receipt.freeze_id
    rig.capture(applicant, freeze_id, 19900)
    outcome = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert outcome.status == "released"
    assert outcome.released_amount_fen == 50000 - 19900
    assert outcome.authorization.status == "completed"
    row = rig.bank.store.get_freeze("U1", freeze_id)
    assert row["original_amount_fen"] - row["captured_total_fen"] - row["released_total_fen"] == 0
    account = rig.bank.store.get_account("U1", "BA1")
    assert account.frozen_balance_fen == 0
    assert len(rig.bank_calls) == 1
    assert outcome.decision.operation_id == rig.bank_calls[0][1]


def test_repeat_finalization_never_releases_twice(tmp_path):
    rig = Rig(tmp_path)
    _, _, authorization, _ = rig.active_authorization()
    first = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert first.status == "released"
    second = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert second.status == "released"
    assert second.release_operation_id == first.release_operation_id
    assert len(rig.bank_calls) == 1


def test_ending_context_tolerates_a_new_controlled_session(tmp_path):
    """Session expiry must not strand the frozen funds: the controlled identity
    with a different session still finishes the limited release."""
    rig = Rig(tmp_path)
    _, _, authorization, _ = rig.active_authorization()
    outcome = rig.finalizer.finalize(
        rig.ending_context(authorization, session_id="SYS-LATER"), "security_stop",
    )
    assert outcome.status == "released"


def test_running_task_cannot_release_early(tmp_path):
    rig = Rig(tmp_path, ended=False)
    _, _, authorization, _ = rig.active_authorization()
    outcome = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert outcome.status == "blocked"
    assert "POLICY_VIOLATION" in outcome.decision.reason_codes
    assert rig.bank_calls == []


def test_unresolved_in_flight_pauses_release(tmp_path):
    rig = Rig(tmp_path)
    _, applicant, authorization, freeze = rig.active_authorization()
    rig.capture(applicant, freeze.receipt.freeze_id, 19900)
    stuck = context(operation_id=uuid4(), action_revision=1)
    rig.state.claim_release_execution(
        stuck,
        ActionDescriptor(action_name="bank.capture_frozen",
                         parameters_ref="birthday:capture:pending",
                         resource_refs=[freeze.receipt.freeze_id],
                         phase=Phase.EXECUTION),
        allow_decision(stuck, ActionDescriptor(
            action_name="bank.capture_frozen",
            parameters_ref="birthday:capture:pending", resource_refs=[],
            phase=Phase.EXECUTION)),
    )
    outcome = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert outcome.status == "needs_attention"
    assert rig.bank_calls == []


def test_zero_remainder_completes_without_a_release_write(tmp_path):
    rig = Rig(tmp_path)
    _, applicant, authorization, freeze = rig.active_authorization()
    freeze_id = freeze.receipt.freeze_id
    rig.capture(applicant, freeze_id, 50000)
    outcome = rig.finalizer.finalize(rig.ending_context(authorization), "security_stop")
    assert outcome.status == "nothing_to_release"
    assert outcome.authorization.status == "completed"
    assert rig.bank_calls == []
    from app.storage.database import connect
    with connect(rig.bank.store.path) as connection:
        releases = connection.execute(
            "SELECT * FROM bank_operations WHERE action_name = 'bank.release_frozen'",
        ).fetchall()
    assert releases == []


def test_remainder_above_confirmed_amount_pauses(tmp_path):
    rig = Rig(tmp_path)
    _, _, authorization, _ = rig.active_authorization()
    original = rig.finalizer.freeze_reader

    def inflated(trusted_context, freeze_id):
        real = original(trusted_context, freeze_id)
        if isinstance(real, QueryFailure):
            return real
        return QueryOk(kind="ok", data=real.data.model_copy(update={
            "remaining_fen": real.data.remaining_fen + 100000,
            "original_amount_fen": real.data.original_amount_fen + 100000,
        }))

    rig.rebuild_finalizer(freeze_reader=inflated)
    outcome = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert outcome.status == "needs_attention"
    assert "POLICY_VIOLATION" in outcome.decision.reason_codes
    assert rig.bank_calls == []


def test_freeze_on_another_account_blocks_release(tmp_path):
    rig = Rig(tmp_path)
    _, _, authorization, _ = rig.active_authorization()
    original = rig.finalizer.freeze_reader

    def switched(trusted_context, freeze_id):
        real = original(trusted_context, freeze_id)
        if isinstance(real, QueryFailure):
            return real
        return QueryOk(kind="ok", data=real.data.model_copy(update={
            "account_id": "BA2",
        }))

    rig.rebuild_finalizer(freeze_reader=switched)
    outcome = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert outcome.status == "blocked"
    assert rig.bank_calls == []


def test_vanished_freeze_invalidates_authorization(tmp_path):
    rig = Rig(tmp_path)
    _, _, authorization, _ = rig.active_authorization()
    with transaction(rig.bank.store.path) as connection:
        connection.execute("DELETE FROM freezes WHERE freeze_id = ?",
                           (authorization.freeze_id,))
    outcome = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert outcome.status == "blocked"
    assert outcome.authorization.status == "invalid"
    assert rig.bank_calls == []


def test_foreign_and_unknown_references_are_denied(tmp_path):
    rig = Rig(tmp_path)
    _, _, authorization, _ = rig.active_authorization()
    for changes in (
        {"user_id": "U2"}, {"demo_round_id": "D2"}, {"task_id": "T2"},
    ):
        intruder = rig.ending_context(authorization, **changes)
        with pytest.raises(SecurityStateError, match="ACCESS_DENIED"):
            rig.state.get_release_authorization(intruder, authorization.release_authorization_id)
    outcome = rig.finalizer.finalize(
        rig.ending_context(authorization, release_authorization_id="REL-UNKNOWN"),
        "user_cancelled",
    )
    assert outcome.status == "blocked"


def test_tampered_authorization_record_is_rejected(tmp_path):
    rig = Rig(tmp_path)
    _, _, authorization, _ = rig.active_authorization()
    tampered = authorization.model_copy(update={"account_id": "BA9"})
    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.state.update_release_authorization(
            rig.ending_context(authorization), tampered,
        )


def test_audit_failure_pauses_before_bank_write(tmp_path):
    rig = Rig(tmp_path)
    _, _, authorization, _ = rig.active_authorization()

    def broken_sink(decision):
        raise RuntimeError("audit down")

    rig.finalizer = LimitedReleaseFinalizer(
        rig.state,
        decision_sink=broken_sink,
        snapshot_writer=rig._snapshot,
        task_state_resolver=lambda _context: rig.task_ended,
        freeze_reader=rig.gateway.get_freeze,
        operation_reader=rig.gateway.get_operation,
        bank_release=rig._bank_release,
        clock=rig.clock,
    )
    outcome = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert outcome.status == "needs_attention"
    assert "AUDIT_UNAVAILABLE" in outcome.decision.reason_codes
    assert rig.bank_calls == []


def test_snapshot_failure_pauses_before_bank_write(tmp_path):
    rig = Rig(tmp_path)
    _, _, authorization, _ = rig.active_authorization()

    def broken_snapshot(*_args):
        return ""

    rig.finalizer = LimitedReleaseFinalizer(
        rig.state,
        decision_sink=rig.decisions.append,
        snapshot_writer=broken_snapshot,
        task_state_resolver=lambda _context: rig.task_ended,
        freeze_reader=rig.gateway.get_freeze,
        operation_reader=rig.gateway.get_operation,
        bank_release=rig._bank_release,
        clock=rig.clock,
    )
    outcome = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert outcome.status == "needs_attention"
    assert "AUDIT_UNAVAILABLE" in outcome.decision.reason_codes
    assert rig.bank_calls == []


def test_state_failure_at_claim_time_performs_no_bank_write(tmp_path):
    rig = Rig(tmp_path)
    _, _, authorization, _ = rig.active_authorization()
    finalizer = rig.finalizer
    original = finalizer.state.claim_release_execution

    def broken(*_args, **_kwargs):
        raise SecurityStateError("DEPENDENCY_UNAVAILABLE")

    finalizer.state.claim_release_execution = broken  # type: ignore[method-assign]
    outcome = finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    finalizer.state.claim_release_execution = original  # type: ignore[method-assign]
    assert outcome.status == "needs_attention"
    assert rig.bank_calls == []


def test_lost_release_response_resolves_by_original_id(tmp_path):
    rig = Rig(tmp_path)
    _, _, authorization, _ = rig.active_authorization()
    rig.bank.birthday.arm_response_loss("U1")
    outcome = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert outcome.status == "needs_attention"
    assert len(rig.bank_calls) == 1
    first_operation = rig.bank_calls[0][1]

    resolved = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert resolved.status == "released"
    assert resolved.release_operation_id == first_operation
    assert len(rig.bank_calls) == 1  # resolved by lookup, never resubmitted


def test_definite_release_failure_keeps_original_id(tmp_path):
    rig = Rig(tmp_path)
    _, applicant, authorization, freeze = rig.active_authorization()
    rig.capture(applicant, freeze.receipt.freeze_id, 19900)  # bank remainder is 30100
    original = rig.finalizer.freeze_reader

    def overstated(trusted_context, freeze_id):
        real = original(trusted_context, freeze_id)
        if isinstance(real, QueryFailure):
            return real
        return QueryOk(kind="ok", data=real.data.model_copy(update={
            "remaining_fen": 50000,
            "captured_total_fen": 0,
            "released_total_fen": 0,
        }))

    rig.rebuild_finalizer(freeze_reader=overstated)
    outcome = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert outcome.status == "needs_attention"
    assert len(rig.bank_calls) == 1
    failed_operation = rig.bank_calls[0][1]
    again = rig.finalizer.finalize(rig.ending_context(authorization), "user_cancelled")
    assert again.status == "needs_attention"
    assert again.release_operation_id == failed_operation
    assert len(rig.bank_calls) == 1


def test_finalize_recovers_after_a_restart(tmp_path):
    rig = Rig(tmp_path)
    _, applicant, authorization, freeze = rig.active_authorization()
    rig.capture(applicant, freeze.receipt.freeze_id, 19900)
    ending = rig.ending_context(authorization)
    outcome = rig.finalizer.finalize(ending, "user_cancelled")
    assert outcome.status == "released"
    # A fresh process reopens both stores and observes the completed ending.
    reopened_state = SQLiteSecurityState(rig.path)
    stored = reopened_state.get_release_authorization(ending, ending.release_authorization_id)
    assert stored.status == "completed"
    reopened_bank = MockBankService(
        MockBankStore(rig.bank.store.path), demo_secret=b"s" * 32,
    )
    view = reopened_bank.birthday.get_freeze("U1", freeze.receipt.freeze_id)
    assert isinstance(view, QueryOk) and view.data.remaining_fen == 0


# --- Bank authorization callback (failure mode 24) ---


def test_authorizer_denies_everything_without_a_live_claim(tmp_path):
    rig = Rig(tmp_path)
    authorizer = authorize_birthday_write(rig.state)
    assert authorizer(trusted(context()), uuid4(), "bank.freeze_funds") is False
    _, _, _, freeze = rig.active_authorization()
    release_context = context(operation_id=uuid4(), action_revision=1)
    release_action = ActionDescriptor(
        action_name="bank.release_frozen",
        parameters_ref="release:" + release_context.operation_id.hex,
        resource_refs=[freeze.receipt.freeze_id], phase=Phase.EXECUTION,
    )
    rig.state.claim_release_execution(
        release_context, release_action, allow_decision(release_context, release_action),
    )
    claim_op = release_context.operation_id
    same_identity = trusted(release_context)
    assert authorizer(same_identity, claim_op, "bank.release_frozen") is True
    assert authorizer(same_identity, claim_op, "bank.freeze_funds") is False
    assert authorizer(
        trusted(release_context.model_copy(update={"user_id": "U2"})), claim_op,
        "bank.release_frozen",
    ) is False
    assert authorizer(
        trusted(release_context.model_copy(update={"demo_round_id": "D2"})), claim_op,
        "bank.release_frozen",
    ) is False
    with transaction(rig.path) as connection:
        connection.execute(
            "UPDATE security_executions SET state = 'completed', result_ref = 'r' "
            "WHERE operation_id = ?", (str(claim_op),),
        )
    assert authorizer(same_identity, claim_op, "bank.release_frozen") is False


def test_gateway_denies_birthday_writes_without_the_authorizer(tmp_path):
    """Unwired platforms stay closed: no authorize_birthday means no birthday write."""
    rig = Rig(tmp_path)
    _, _, _, freeze = rig.active_authorization()
    closed = BankGateway(rig.bank)
    denied = closed.release_frozen(
        trusted(context()), uuid4(),
        ReleaseFrozenInput(freeze_id=freeze.receipt.freeze_id, amount_fen=1),
    )
    assert isinstance(denied, QueryFailure)
    assert denied.error.code == "ACCESS_DENIED"
