"""Same-owner recovery retires an old attempt; it never transfers its authority."""

import json
from datetime import timedelta
from uuid import uuid4

import pytest

from app.contracts.common import TaskStatus
from app.contracts.bank import FreezeFundsInput
from app.contracts.platform import TrustedContext
from app.contracts.security import ConfirmationAnswer, VerificationSummary
from app.security import ConfirmationService, SecurityError
from app.security.birthday_release import (
    authorize_birthday_write, bind_freeze_result, grant_release_authorization,
)
from app.security.state import SQLiteSecurityState, SecurityStateError
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.services.mock_bank.verification import AdminContext, ChallengeNotRetireable, ChallengeRetired
from app.storage.mock_bank.repository import BankAccount, MockBankStore
from app.storage.application import ApplicationStore
from app.storage.database import transaction
from .test_retirement import (
    Rig, allow_decision, context, freeze_action, insert_claim_row, release_confirmation,
)


class RecoveryRig(Rig):
    def __init__(self, tmp_path, action_name="bank.freeze_funds"):
        super().__init__(tmp_path)
        self.source = context()
        self.action = freeze_action().model_copy(update={"action_name": action_name})
        self.confirmation = release_confirmation(self, self.source, self.action)
        self.authorization = grant_release_authorization(
            self.state, self.source, self.confirmation,
            account_id="BA1", amount_fen=50000, now=self.clock()) if action_name == "bank.freeze_funds" else None
        self.target = self.source.model_copy(update={"session_id": "S2", "run_id": "R2"})
        self.application = ApplicationStore(self.path)
        for session_id in ("S1", "S2"):
            self.application.create_session(session_id, "U1", "D1", self.clock().isoformat(),
                                            (self.clock() + timedelta(days=1)).isoformat())
        self.source_binding = {
            "session_id": "S1", "confirmation_id": self.confirmation.confirmation_id,
            "confirmation_version": self.confirmation.confirmation_version,
            "operation_id": str(self.source.operation_id), "action_revision": 1,
            "action_name": self.action.action_name, "parameters_ref": self.action.parameters_ref,
            "resource_refs": self.action.resource_refs, "phase": self.action.phase.value,
        }
        self.application.create_task("T1", "U1", "S2", "D1", "R2", TaskStatus.WAITING_APPROVAL,
                                     {"recovery_source": self.source_binding, "parameters": {"amount_fen": 50000}})
        self.validation_calls = 0

    def validate(self, connection, applicant, binding):
        assert connection.in_transaction
        self.validation_calls += 1
        row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (applicant.task_id,)).fetchone()
        if row is None or (row["user_id"], row["session_id"], row["demo_round_id"], row["revision"]) != (
                applicant.user_id, applicant.session_id, applicant.demo_round_id, 0):
            return False
        snapshot = json.loads(row["snapshot_json"])
        return (row["status"] in {"waiting_approval", "waiting_input"}
                and snapshot["parameters"] == {"amount_fen": 50000}
                and all(binding.get(key) == value for key, value in snapshot["recovery_source"].items()))

    def begin(self, *, applicant=None, action=None, validator=None, **changes):
        fields = {"source_session_id": "S1", "source_confirmation_id": self.confirmation.confirmation_id,
                  "source_confirmation_version": self.confirmation.confirmation_version}
        fields.update(changes)
        return self.state.begin_session_retirement(
            applicant or self.target, action or self.action, self.clock(),
            recovery_validator=validator or self.validate, **fields)

    def seal(self, retirement, *, applicant=None, evidence=None, writer=None, validator=None):
        return self.state.seal_session_retirement(
            applicant or self.target, retirement.retirement_id,
            evidence or self.evidence(self.source), self.clock(),
            audit_writer=writer or self.journal.append_in_transaction,
            recovery_validator=validator or self.validate)


def test_new_session_seals_old_pending_authority_without_rebinding_it(tmp_path):
    rig = RecoveryRig(tmp_path)
    retirement = rig.begin()
    assert retirement.state == "pending_proof"
    assert retirement.original_binding["session_id"] == "S1"
    assert retirement.original_binding["recovery_target_session_id"] == "S2"
    assert rig.state.get_release_authorization(rig.source, rig.authorization.release_authorization_id) == rig.authorization
    sealed = rig.seal(retirement)
    assert sealed.state == "sealed" and sealed.audit_ref
    invalid = rig.state.get_release_authorization(rig.target, rig.authorization.release_authorization_id)
    assert invalid.session_id == "S1"
    assert (invalid.status, invalid.invalid_reason) == ("invalid", "RETIRED_UNSUBMITTED")
    assert rig.validation_calls == 2
    assert rig.begin().retirement_id == retirement.retirement_id
    assert rig.seal(retirement) == sealed


def test_target_task_cas_change_between_begin_and_seal_cannot_issue_proof(tmp_path):
    rig = RecoveryRig(tmp_path)
    retirement = rig.begin()
    with transaction(rig.path) as connection:
        connection.execute("UPDATE tasks SET revision = revision + 1 WHERE task_id = 'T1'")
    with pytest.raises(SecurityStateError, match="RETIREMENT_STALE"):
        rig.seal(retirement)
    assert rig.state.get_retirement(rig.target, "T1", rig.source.operation_id, 1).state == "pending_proof"
    assert rig.state.get_release_authorization(rig.source, rig.authorization.release_authorization_id) == rig.authorization


def test_archived_source_confirmation_is_verified_instead_of_the_new_card(tmp_path):
    rig = RecoveryRig(tmp_path)
    newer = rig.state.create_confirmation(rig.target, rig.action, rig.confirmation.display_fields,
                                          rig.clock(), rig.confirmation.expires_at)
    assert newer.confirmation_version > rig.confirmation.confirmation_version
    sealed = rig.seal(rig.begin())
    assert sealed.original_binding["confirmation_version"] == rig.confirmation.confirmation_version
    history = rig.state.get_confirmation_history(rig.source, rig.confirmation.confirmation_id)
    assert history == [rig.confirmation]


@pytest.mark.parametrize("action_name", ["bank.create_order", "bank.capture_frozen"])
def test_other_unsubmitted_birthday_writes_can_retire_without_migrating_authority(tmp_path, action_name):
    rig = RecoveryRig(tmp_path, action_name)
    assert rig.seal(rig.begin()).original_binding["action_name"] == action_name


@pytest.mark.parametrize("missing", ["operation_id", "action_revision"])
def test_session_seal_requires_the_exact_attempt_context(tmp_path, missing):
    rig = RecoveryRig(tmp_path)
    retirement = rig.begin()
    with pytest.raises(SecurityStateError, match="INPUT_REQUIRED"):
        rig.seal(retirement, applicant=rig.target.model_copy(update={missing: None}))


@pytest.mark.parametrize("changes,expected", [
    ({"user_id": "U2"}, "ACCESS_DENIED"), ({"demo_round_id": "D2"}, "ACCESS_DENIED"),
    ({"task_id": "T2"}, "ACCESS_DENIED"), ({"operation_id": uuid4()}, "OPERATION_CONFLICT"),
    ({"action_revision": 2}, "OPERATION_CONFLICT"), ({"session_id": "S3"}, "RETIREMENT_STALE"),
    ({"confirmation_id": "new-card"}, "INPUT_REQUIRED"),
])
def test_source_scope_and_attempt_cannot_be_changed(tmp_path, changes, expected):
    rig = RecoveryRig(tmp_path)
    with pytest.raises(SecurityStateError, match=expected):
        rig.begin(applicant=rig.target.model_copy(update=changes))
    assert rig.state.get_retirement(rig.target, "T1", rig.source.operation_id, 1) is None


@pytest.mark.parametrize("fields,expected", [
    ({"source_session_id": "another-source"}, "ACCESS_DENIED"),
    ({"source_confirmation_id": "absent"}, "CONFIRMATION_STALE"),
    ({"source_confirmation_version": 99}, "CONFIRMATION_STALE"),
])
def test_source_confirmation_proof_is_not_self_reported(tmp_path, fields, expected):
    rig = RecoveryRig(tmp_path)
    with pytest.raises(SecurityStateError, match=expected):
        rig.begin(**fields)


def test_different_parameters_and_unknown_actions_do_not_get_retirement_proof(tmp_path):
    rig = RecoveryRig(tmp_path)
    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.begin(action=freeze_action("different-snapshot"))
    with pytest.raises(SecurityStateError, match="POLICY_VIOLATION"):
        rig.begin(action=rig.action.model_copy(update={"action_name": "bank.release_frozen"}))
    with pytest.raises(SecurityStateError, match="RETIREMENT_STALE"):
        rig.begin(action=rig.action.model_copy(update={"resource_refs": ["different-resource"]}))


@pytest.mark.parametrize("value,expected", [(False, "RETIREMENT_STALE"), (None, "DEPENDENCY_UNAVAILABLE"),
                                           ("yes", "DEPENDENCY_UNAVAILABLE")])
def test_validator_veto_or_incomplete_proof_never_becomes_safe(tmp_path, value, expected):
    rig = RecoveryRig(tmp_path)
    with pytest.raises(SecurityStateError, match=expected):
        rig.begin(validator=lambda *_: value)
    retirement = rig.begin()
    with pytest.raises(SecurityStateError, match=expected):
        rig.seal(retirement, validator=lambda *_: value)
    assert rig.state.get_release_authorization(rig.source, rig.authorization.release_authorization_id) == rig.authorization


def test_unavailable_validator_and_changed_parameters_fail_closed(tmp_path):
    rig = RecoveryRig(tmp_path)

    def unavailable(*_):
        raise RuntimeError("source lookup unavailable")

    with pytest.raises(SecurityStateError, match="DEPENDENCY_UNAVAILABLE"):
        rig.begin(validator=unavailable)
    retirement = rig.begin()
    with transaction(rig.path) as connection:
        connection.execute("UPDATE tasks SET snapshot_json = ? WHERE task_id = 'T1'",
            (json.dumps({"recovery_source": rig.source_binding, "parameters": {"amount_fen": 60000}}),))
    with pytest.raises(SecurityStateError, match="RETIREMENT_STALE"):
        rig.seal(retirement)


@pytest.mark.parametrize("claim_state", ["processing", "completed", "unknown"])
def test_any_existing_claim_requires_original_operation_observation(tmp_path, claim_state):
    rig = RecoveryRig(tmp_path)
    insert_claim_row(rig, rig.source, rig.action, claim_state)
    with pytest.raises(SecurityStateError, match="OPERATION_UNKNOWN"):
        rig.begin()
    assert rig.state.get_retirement(rig.target, "T1", rig.source.operation_id, 1) is None
    assert rig.state.get_release_authorization(rig.source, rig.authorization.release_authorization_id) == rig.authorization


def test_a_claim_winning_after_begin_prevents_seal_and_new_authority(tmp_path):
    rig = RecoveryRig(tmp_path)
    retirement = rig.begin()
    caller = rig.source.model_copy(update={"confirmation_id": rig.confirmation.confirmation_id,
                                         "confirmation_version": rig.confirmation.confirmation_version})
    rig.state.claim_execution(caller, rig.action, allow_decision(caller, rig.action), rig.clock(), lambda _: False)
    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.seal(retirement)
    assert rig.state.get_retirement(rig.target, "T1", rig.source.operation_id, 1).state == "conflict"
    assert rig.state.get_release_authorization(rig.source, rig.authorization.release_authorization_id) == rig.authorization


def test_active_freeze_cannot_be_retired_as_unsubmitted(tmp_path):
    rig = RecoveryRig(tmp_path)
    active = rig.authorization.model_copy(update={"status": "active", "freeze_id": "F1"})
    rig.state.update_release_authorization(rig.source, active)
    with pytest.raises(SecurityStateError, match="OPERATION_UNKNOWN"):
        rig.begin()
    assert rig.state.get_release_authorization(rig.source, active.release_authorization_id) == active


@pytest.mark.parametrize("after_begin", [False, True])
def test_security_task_termination_refuses_recovery_at_both_boundaries(tmp_path, after_begin):
    rig = RecoveryRig(tmp_path)
    retirement = rig.begin() if after_begin else None
    rig.state.terminate_task(rig.target, "USER_CANCELLED")
    with pytest.raises(SecurityStateError, match="TASK_TERMINATED"):
        rig.seal(retirement) if after_begin else rig.begin()
    assert rig.state.get_release_authorization(rig.source, rig.authorization.release_authorization_id) == rig.authorization


def test_audit_failure_rolls_back_pending_authorization_and_can_resume(tmp_path):
    rig = RecoveryRig(tmp_path)
    retirement = rig.begin()

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    with pytest.raises(SecurityStateError, match="AUDIT_UNAVAILABLE"):
        rig.seal(retirement, writer=unavailable)
    assert rig.state.get_retirement(rig.target, "T1", rig.source.operation_id, 1).state == "pending_proof"
    assert rig.state.get_release_authorization(rig.source, rig.authorization.release_authorization_id) == rig.authorization
    assert rig.events() == []
    sealed = rig.seal(retirement)
    assert sealed.state == "sealed"
    assert len(rig.events()) == 1
    assert rig.events()[0].session_id == "S2"
    assert rig.events()[0].payload.decision.policy_version == "v05-birthday-session-retirement-1"


def test_other_session_or_ordinary_g2_seal_cannot_skip_the_recovery_validator(tmp_path):
    rig = RecoveryRig(tmp_path)
    retirement = rig.begin()
    with pytest.raises(SecurityStateError, match="ACCESS_DENIED"):
        rig.seal(retirement, applicant=rig.target.model_copy(update={"session_id": "S3"}))
    with pytest.raises(SecurityStateError, match="ACCESS_DENIED"):
        rig.state.seal_retirement(rig.source, retirement.retirement_id, rig.evidence(rig.source), rig.clock(),
                                 audit_writer=rig.journal.append_in_transaction, task_state_resolver=lambda _: False)
    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.state.begin_retirement(rig.source, rig.action, rig.clock(), task_state_resolver=lambda _: False)


@pytest.mark.parametrize("changes", [{"operation_id": str(uuid4())}, {"action_revision": 2}])
def test_bank_retirement_must_belong_to_the_original_attempt(tmp_path, changes):
    rig = RecoveryRig(tmp_path)
    retirement = rig.begin()
    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.seal(retirement, evidence=rig.evidence(rig.source, **changes))
    assert rig.events() == []


def trusted(applicant):
    return TrustedContext(user_id=applicant.user_id, session_id=applicant.session_id,
        demo_round_id=applicant.demo_round_id, task_id=applicant.task_id,
        run_id=applicant.run_id, parent_task_id=None)


def summary(applicant, record):
    return VerificationSummary(operation_id=applicant.operation_id, action_revision=applicant.action_revision,
        source_confirmation_id=record.confirmation_id, source_confirmation_version=record.confirmation_version,
        action_name=record.action_name, amount_fen=50000, payee=None, display_fields=record.display_fields)


@pytest.mark.parametrize("terminal", ["passed", "failed", "expired"])
def test_real_bank_terminal_challenge_cannot_be_used_as_retirement_proof(tmp_path, terminal):
    rig = RecoveryRig(tmp_path)
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite3"), demo_secret=b"s" * 32)
    bank.verification.clock = rig.clock
    gateway = BankGateway(bank, authorize_face=lambda *_: True)
    try:
        old = gateway.create_verification(trusted(rig.source), "action_step_up",
            rig.source.operation_id, 1, summary(rig.source, rig.confirmation))
        if terminal == "passed":
            gateway.verify_code(trusted(rig.source), old.challenge_id, uuid4(),
                                gateway.get_demo_code_for_api(trusted(rig.source), old.challenge_id))
            gateway.start_face(trusted(rig.source), old.challenge_id, uuid4())
            gateway.verify_face(AdminContext("admin", True, "D1", "U1"), old.challenge_id, uuid4(), "passed")
        elif terminal == "failed":
            gateway.verify_code(trusted(rig.source), old.challenge_id, uuid4(), "not-the-code")
        else:
            rig.clock.value += timedelta(minutes=6)
        retirement = rig.begin()
        with pytest.raises(ChallengeNotRetireable):
            gateway.retire_action_challenges(trusted(rig.source),
                operation_id=rig.source.operation_id, action_revision=1)
        assert rig.state.get_retirement(rig.target, "T1", rig.source.operation_id, 1) == retirement
        assert rig.state.get_release_authorization(rig.source, rig.authorization.release_authorization_id) == rig.authorization
        assert rig.events() == []
    finally:
        gateway.close()


def test_real_bank_old_challenges_and_callbacks_cannot_revive_a_new_session_attempt(tmp_path):
    rig = RecoveryRig(tmp_path)
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite3"), demo_secret=b"s" * 32)
    bank.verification.clock = rig.clock
    bank.store.seed_account(BankAccount("BA1", "U1", "class_i", "active", 200000, 0, 0))
    gateway = BankGateway(bank, authorize_birthday=authorize_birthday_write(rig.state),
                          authorize_face=lambda *_: True)
    confirmations = ConfirmationService(rig.path, clock=rig.clock)
    try:
        old = gateway.create_verification(trusted(rig.source), "action_step_up",
            rig.source.operation_id, 1, summary(rig.source, rig.confirmation))
        code = gateway.get_demo_code_for_api(trusted(rig.source), old.challenge_id)
        retirement = rig.begin()
        proof = gateway.retire_action_challenges(trusted(rig.source),
            operation_id=rig.source.operation_id, action_revision=1)
        sealed = rig.seal(retirement, evidence=proof)
        assert sealed.bank_evidence["retired_challenge_ids"] == [old.challenge_id]
        assert gateway.get_verification(trusted(rig.source), old.challenge_id) == old
        for late in (
            lambda: gateway.verify_code(trusted(rig.source), old.challenge_id, uuid4(), code),
            lambda: gateway.start_face(trusted(rig.source), old.challenge_id, uuid4()),
            lambda: gateway.create_verification(trusted(rig.source), "action_step_up",
                rig.source.operation_id, 1, summary(rig.source, rig.confirmation)),
        ):
            with pytest.raises(ChallengeRetired):
                late()
        with pytest.raises(SecurityError, match="ACTION_RETIRED"):
            grant_release_authorization(rig.state, rig.source, rig.confirmation,
                                        account_id="BA1", amount_fen=50000, now=rig.clock())
        with pytest.raises(SecurityError, match="ACTION_RETIRED"):
            confirmations.answer(rig.source, ConfirmationAnswer(
                confirmation_id=rig.confirmation.confirmation_id,
                confirmation_version=rig.confirmation.confirmation_version, choice="approve"))
        old_claim = rig.source.model_copy(update={"confirmation_id": rig.confirmation.confirmation_id,
                                                 "confirmation_version": rig.confirmation.confirmation_version})
        with pytest.raises(SecurityStateError, match="ACTION_RETIRED"):
            rig.state.claim_execution(old_claim, rig.action, allow_decision(old_claim, rig.action),
                                      rig.clock(), lambda _: False)

        # Platform's separate consumer creates a new, linked attempt after seal.
        next_context = rig.target.model_copy(update={"operation_id": uuid4(), "action_revision": 2})
        next_action = freeze_action(str(next_context.operation_id))
        pending = confirmations.create(next_context, next_action, rig.confirmation.display_fields)
        with pytest.raises(SecurityError, match="CONFIRMATION_REQUIRED"):
            grant_release_authorization(rig.state, next_context, pending,
                                        account_id="BA1", amount_fen=50000, now=rig.clock())
        approved = confirmations.answer(next_context, ConfirmationAnswer(
            confirmation_id=pending.confirmation_id, confirmation_version=pending.confirmation_version, choice="approve"))
        new_authorization = grant_release_authorization(rig.state, next_context, approved,
                                        account_id="BA1", amount_fen=50000, now=rig.clock())
        new_challenge = gateway.create_verification(trusted(next_context), "action_step_up",
            next_context.operation_id, 2, summary(next_context, approved))
        assert (new_challenge.challenge_id, new_challenge.session_id) != (old.challenge_id, old.session_id)
        gateway.verify_code(trusted(next_context), new_challenge.challenge_id, uuid4(),
                            gateway.get_demo_code_for_api(trusted(next_context), new_challenge.challenge_id))
        gateway.start_face(trusted(next_context), new_challenge.challenge_id, uuid4())
        verified = gateway.verify_face(AdminContext("admin", True, "D1", "U1"),
                                        new_challenge.challenge_id, uuid4(), "passed")
        assert gateway.get_verification_record(trusted(next_context), verified.verification_id).session_id == "S2"
        claimed = next_context.model_copy(update={"confirmation_id": approved.confirmation_id,
            "confirmation_version": approved.confirmation_version, "verification_ids": [verified.verification_id]})
        # This state seam consumes a test ALLOW decision; the gate's independent
        # verification policy remains covered by the existing full security suite.
        rig.state.claim_execution(claimed, next_action, allow_decision(claimed, next_action), rig.clock(), lambda _: False)
        frozen = gateway.freeze_funds(trusted(next_context), next_context.operation_id,
                                     FreezeFundsInput(account_id="BA1", amount_fen=50000, reason="生日"))
        assert frozen.operation_status == "succeeded"
        assert bind_freeze_result(rig.state, next_context, new_authorization.release_authorization_id,
                                  frozen, rig.clock()).status == "active"
        with pytest.raises(SecurityError, match="OPERATION_CONFLICT"):
            bind_freeze_result(rig.state, rig.source, rig.authorization.release_authorization_id,
                                frozen.model_copy(update={"operation_id": rig.source.operation_id}), rig.clock())
        assert gateway.get_operation(trusted(rig.source), rig.source.operation_id).lookup == "not_found"
        assert bank.store.get_account("U1", "BA1").frozen_balance_fen == 50000
        assert rig.state.get_confirmation_history(rig.source, rig.confirmation.confirmation_id) == [rig.confirmation]
        reopened = SQLiteSecurityState(rig.path)
        assert reopened.get_retirement(rig.target, "T1", rig.source.operation_id, 1) == sealed
        assert reopened.get_release_authorization(rig.source, rig.authorization.release_authorization_id).status == "invalid"
    finally:
        gateway.close()
