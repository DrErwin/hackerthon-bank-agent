"""Ticket v05-birthday-platform-dependencies/02: atomic retirement of an unsubmitted action.

Failure modes enumerated before implementation (ticket failure list):

Acceptance / begin:
1. no claim -> the attempt is accepted as pending_proof, not yet editable;
2. same task/operation/revision can read the same record back (03 recovery);
3. replayed begin with the same original binding returns the same record;
4. different original parameters for the same attempt conflict;
5. an existing claim in processing/completed/unknown refuses acceptance
   (completed does not prove bank success either);
6. cross user / demo round / task, and a terminated task, are refused;
7. missing operation/revision input is refused.

Seal:
8. a pending_proof record is sealed only with bank evidence for that exact
   attempt, in one application transaction with the audit event;
9. replay with the same evidence is idempotent and writes no second audit event;
10. a claim that appears between begin and seal records conflict and refuses
    sealing; no sealed/editable evidence remains;
11. an audit failure rolls back the whole seal and leaves pending_proof;
12. a retry after the failed audit can still seal the same record;
13. bank evidence for another operation/revision, or malformed evidence,
    refuses sealing without writing sealed;
14. a foreign context cannot seal; a task terminated between begin and seal
    refuses sealing.

Claim ordering:
15. claim_execution refuses ACTION_RETIRED for both pending_proof and sealed;
16. an attempt that was never accepted and other ordinary actions are unaffected.

Confirmation history:
17. before create_confirmation overwrites a record, the complete previous
    ConfirmationRecord is kept verbatim (display_fields, parameters_ref,
    version, decision);
18. history is readable by (confirmation_id, version), ordered, and never
    rewrites the archived decision when a newer version is answered;
19. another identity cannot read the history.

Limited-release retirement (G2-C):
20. a pending_freeze authorization of the sealed attempt becomes invalid with
    reason RETIRED_UNSUBMITTED (never FREEZE_FAILED), and the controlled
    ending reports "nothing to release" instead of a fake bank failure;
21. an unrelated active authorization is never invalidated;
22. a real active authorization for the same attempt is a contradiction:
    sealing refuses and leaves it untouched;
23. a late grant callback after sealing cannot create a new pending_freeze.

Review rework (2026-10-26; authority §2 wins over the first version):
24. a failed edit attempt must not kill the old approved action: pending_proof
    does not block claim_execution, and the successful claim atomically turns
    the accepted retirement into conflict so seal can never sign evidence;
25. the platform task-state resolver (completed/cancelled/partially_succeeded/
    needs_attention) refuses begin/seal inside the transaction; an unavailable
    or non-bool resolver fails closed;
26. sealing requires the original session_id, not only user/round/task;
27. confirmation resend/approval and gate check_action cannot produce
    approved/ALLOW for a sealed (or already claimed/conflict) attempt;
    pending_proof stays executable by the authority §2 rule above;
28. the audit event shell carries the trusted run_id and the next sequence;
29. store_release_authorization matches the sealed retirement's action
    revision so a later attempt sharing the operation id is not misblocked;
30. the bank stand-in shows a retired challenge cannot enable a late
    verification for the same attempt.

All tests use an isolated application database and the real AuditJournal; no
live bank and no model are involved.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.audit.journal import AuditJournal, AuditReader, AuditViewer
from app.contracts.audit import AuditEvent, SecurityDecidedPayload
from app.contracts.common import (
    DisplayField, OperationLevel, Phase, RiskLevel,
)
from app.contracts.platform import CapabilityDefinition
from app.contracts.security import (
    ActionDescriptor, ConfirmationAnswer, ExecutionSecurityContext, SecurityDecision,
    SecurityDecisionCode,
)
from app.security import ConfirmationService, SecurityError, SecurityGate, ToolRegistry
from app.security.birthday_policy import with_release_clause
from app.security.birthday_release import (
    LimitedReleaseFinalizer, grant_release_authorization,
)
from app.security.state import (
    FreezeReleaseAuthorization, SQLiteSecurityState, SecurityStateError,
)
from app.storage.database import transaction


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value


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


def freeze_action(parameters_ref: str = "birthday:freeze:50000") -> ActionDescriptor:
    return ActionDescriptor(
        action_name="bank.freeze_funds",
        parameters_ref=parameters_ref,
        resource_refs=["p_flower"],
        phase=Phase.EXECUTION,
    )


def allow_decision(
    applicant: ExecutionSecurityContext, action: ActionDescriptor,
) -> SecurityDecision:
    return SecurityDecision(
        decision_id=str(uuid4()), task_id=applicant.task_id,
        run_id=applicant.run_id, action_name=action.action_name,
        parameters_ref=action.parameters_ref, operation_id=applicant.operation_id,
        action_revision=applicant.action_revision, phase=action.phase,
        operation_level=OperationLevel.SENSITIVE, risk_level=RiskLevel.MEDIUM,
        decision=SecurityDecisionCode.ALLOW, reason_codes=["SECURITY_CHECK_PASSED"],
        rule_ids=["test"], policy_version="test-retirement",
        authorization_snapshot_ref="AUTH-T", evidence_refs=[], interaction=None,
        checked_at=datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc), message="test",
    )


class Rig:
    def __init__(self, tmp_path) -> None:
        self.path = tmp_path / "application.sqlite3"
        self.clock = Clock()
        self.state = SQLiteSecurityState(self.path)
        self.journal = AuditJournal(self.path)
        self.task_terminated = False

    def task_state(self, _context):
        return self.task_terminated

    def begin(self, applicant, action, *, resolver=None):
        return self.state.begin_retirement(
            applicant, action, self.clock(),
            task_state_resolver=resolver or self.task_state,
        )

    def evidence(self, applicant, **changes):
        values = {
            "retirement_id": "BANK-RET-1",
            "operation_id": str(applicant.operation_id),
            "action_revision": applicant.action_revision,
            "retired_challenge_ids": ["CH-1"],
            "retired_at": self.clock().isoformat(),
        }
        values.update(changes)
        return values

    def seal(self, applicant, retirement, *, evidence=None, writer=None,
             resolver=None):
        return self.state.seal_retirement(
            applicant,
            retirement.retirement_id,
            self.evidence(applicant) if evidence is None else evidence,
            self.clock(),
            audit_writer=writer or self.journal.append_in_transaction,
            task_state_resolver=resolver or self.task_state,
        )

    def stored(self, applicant):
        return self.state.get_retirement(
            applicant, applicant.task_id, applicant.operation_id,
            applicant.action_revision,
        )

    def events(self, task_id: str = "T1"):
        return self.journal._events("D1", task_id)


def approved_confirmation(rig: Rig, applicant, action, *, fields=None):
    service = ConfirmationService(rig.path, clock=rig.clock)
    record = service.create(
        applicant, action,
        fields or [DisplayField(name="amount", label="金额", value_text="500 元")],
    )
    return service.answer(applicant, ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version,
        choice="approve",
    ))


def claim_fields(applicant, record):
    return applicant.model_copy(update={
        "confirmation_id": record.confirmation_id,
        "confirmation_version": record.confirmation_version,
    })


def claim_now(rig: Rig, applicant, action, state="processing"):
    record = approved_confirmation(rig, applicant, action)
    claimed = claim_fields(applicant, record)
    claim, created = rig.state.claim_execution(
        claimed, action, allow_decision(claimed, action), rig.clock(),
        lambda _context: False,
    )
    assert created
    if state != "processing":
        claim = rig.state.record_execution(
            claimed, action, state, None if state == "unknown" else "RESULT-1",
        )
    return claim, claimed


def insert_claim_row(rig: Rig, applicant, action, state="processing"):
    """Simulate another writer claiming between begin and seal."""
    with transaction(rig.path) as connection:
        connection.execute(
            """INSERT INTO security_executions
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
            (
                str(applicant.operation_id), applicant.user_id,
                applicant.demo_round_id, applicant.task_id, action.action_name,
                action.parameters_ref, applicant.action_revision, state,
                allow_decision(applicant, action).model_dump_json(),
            ),
        )


def authorization(
    *, operation_id, status="active", confirmation_id="CONF-Y",
    confirmation_version=1, action_revision=None,
) -> FreezeReleaseAuthorization:
    return FreezeReleaseAuthorization(
        release_authorization_id="rel_" + uuid4().hex[:16],
        user_id="U1", session_id="S1", demo_round_id="D1", task_id="T1",
        account_id="BA1", freeze_operation_id=operation_id,
        freeze_id="F-1" if status in {"active", "completed"} else None,
        confirmation_id=confirmation_id,
        confirmation_version=confirmation_version,
        max_amount_fen=50000,
        granted_at=datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc),
        status=status,
        action_revision=action_revision,
    )


def release_confirmation(rig: Rig, applicant, action):
    fields = with_release_clause([
        DisplayField(name="amount", label="冻结金额", value_text="500 元"),
    ])
    return approved_confirmation(rig, applicant, action, fields=fields)


def finalizer(rig: Rig) -> LimitedReleaseFinalizer:
    def unavailable(*_args, **_kwargs):
        raise AssertionError("the ending must not read the bank for a retired attempt")

    return LimitedReleaseFinalizer(
        rig.state,
        decision_sink=[].append,
        snapshot_writer=unavailable,
        task_state_resolver=lambda _context: True,
        freeze_reader=unavailable,
        operation_reader=unavailable,
        bank_release=unavailable,
        clock=rig.clock,
    )


def ending_context(applicant, release_authorization_id, **changes):
    values = {
        "session_id": "SYS-CONTROLLED",
        "operation_id": None,
        "action_revision": None,
        "release_authorization_id": release_authorization_id,
    }
    values.update(changes)
    return applicant.model_copy(update=values)


def read_action() -> ActionDescriptor:
    return ActionDescriptor(
        action_name="bank.get_freeze",
        parameters_ref="birthday:get:freeze",
        resource_refs=[],
        phase=Phase.EXECUTION,
    )


def build_gate(rig: Rig) -> SecurityGate:
    """A minimal real gate whose READ action is enough to observe ALLOW/BLOCK."""

    registry = ToolRegistry()
    registry.register(CapabilityDefinition(
        name="bank.get_freeze", input_schema_ref="GetFreezeInput",
        output_schema_ref="QueryResult[FreezeView]",
        required_permissions=["cross.birthday.read"], operation_level=OperationLevel.READ,
        side_effect=False, confirmation_policy="none", timeout_ms=1_000,
        retry_policy="read_only", handler_ref="bank_gateway.get_freeze",
    ), lambda _context, payload: payload)
    return SecurityGate(
        registry,
        ConfirmationService(rig.path, clock=rig.clock),
        scope_authorizer=lambda *_args: True,
        task_state_resolver=rig.task_state,
        risk_assessor=lambda *_args: RiskLevel.LOW,
        confirmation_preparer=None,
        verification_preparer=None,
        verification_resolver=None,
        challenge_resolver=None,
        decision_sink=[].append,
        snapshot_writer=lambda *_args: None,
        summary_validator=None,
    )


def prior_run_event(rig: Rig, applicant, action) -> AuditEvent:
    """One earlier security.decided event in the same trusted run."""

    decision = allow_decision(applicant, action).model_copy(update={
        "decision": SecurityDecisionCode.BLOCK,
        "reason_codes": ["TEST_PRIOR_EVENT"],
        "authorization_snapshot_ref": None,
        "risk_level": None,
    })
    event = AuditEvent(
        event_id=str(uuid4()), trace_id=str(uuid4()), span_id=str(uuid4()),
        sequence=0, parent_span_id=None,
        demo_round_id=applicant.demo_round_id, actor_id=applicant.user_id,
        session_id=applicant.session_id, target_session_id=applicant.session_id,
        target_user_id=applicant.user_id, thread_id=None,
        task_id=applicant.task_id, run_id=applicant.run_id, module="security",
        event_type="security.decided", timestamp=rig.clock(), logical_at=None,
        outcome="denied", evidence_ref=None, evidence_status="missing",
        missing_reason="test prior event", payload=SecurityDecidedPayload(decision=decision),
    )
    return rig.journal.append(event)


# --- Acceptance, replay, read-back (failure modes 1-5, 7) ---


def test_accept_then_seal_then_read_back_by_original_task(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()

    retirement = rig.begin(applicant, action)
    assert retirement.state == "pending_proof"
    assert retirement.audit_ref is None and retirement.sealed_at is None
    assert rig.stored(applicant) == retirement

    sealed = rig.seal(applicant, retirement)
    assert sealed.state == "sealed"
    assert sealed.audit_ref and sealed.sealed_at == rig.clock()
    assert sealed.bank_evidence["retirement_id"] == "BANK-RET-1"
    assert rig.stored(applicant) == sealed

    event = rig.journal._event("D1", sealed.audit_ref)
    assert event is not None and event.event_type == "security.decided"
    assert event.payload.decision.decision is SecurityDecisionCode.BLOCK
    assert event.payload.decision.reason_codes == ["RETIRED_UNSUBMITTED"]
    content, _snapshot = rig.journal._evidence(event)
    assert content is not None and "BANK-RET-1" in content

    # The sealed fact replays through the shared audit reader with complete evidence.
    reader = AuditReader(rig.journal, authorize=lambda *_args: True)
    detail = next(
        item for item in reader.timeline(
            AuditViewer(actor_id="auditor", session_id="AS", demo_round_id="D1"),
            "D1", "T1",
        ) if item.event_id == sealed.audit_ref
    )
    assert detail.evidence_status == "available"
    assert detail.evidence is not None and "BANK-RET-1" in detail.evidence


def test_seal_accepts_the_bank_retirement_object_of_ticket_06(tmp_path):
    from app.services.mock_bank.verification import VerificationRetirement

    rig = Rig(tmp_path)
    applicant = context()
    retirement = rig.begin(applicant, freeze_action())
    bank = VerificationRetirement(
        retirement_id="BANK-RET-9",
        operation_id=applicant.operation_id,
        action_revision=1,
        retired_challenge_ids=["CH-9"],
        retired_at=rig.clock(),
    )

    sealed = rig.state.seal_retirement(
        applicant, retirement.retirement_id, bank, rig.clock(),
        audit_writer=rig.journal.append_in_transaction,
        task_state_resolver=rig.task_state,
    )
    assert sealed.state == "sealed"
    assert sealed.bank_evidence["retirement_id"] == "BANK-RET-9"
    assert sealed.bank_evidence["retired_challenge_ids"] == ["CH-9"]


def test_existing_claim_in_any_state_refuses_acceptance(tmp_path):
    for claim_state in ("processing", "completed", "unknown"):
        rig = Rig(tmp_path / claim_state)
        applicant = context()
        action = freeze_action()
        _claim, claimed = claim_now(rig, applicant, action, state=claim_state)

        with pytest.raises(SecurityStateError, match="OPERATION_UNKNOWN"):
            rig.begin(claimed, action)
        assert rig.stored(claimed) is None


def test_replayed_begin_returns_the_same_record_and_different_binding_conflicts(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()

    first = rig.begin(applicant, action)
    assert rig.begin(applicant, action) == first

    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.begin(applicant, freeze_action("birthday:freeze:40000"))
    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.begin(
            applicant.model_copy(update={"confirmation_id": "CONF-OTHER"}),
            action,
        )
    with pytest.raises(SecurityStateError, match="INPUT_REQUIRED"):
        rig.begin(
            applicant.model_copy(update={"operation_id": None}), action,
        )


def test_foreign_identity_and_wrong_task_read_are_denied(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    retirement = rig.begin(applicant, action)

    for change in (
        {"user_id": "U2"},
        {"demo_round_id": "D2"},
        {"task_id": "T2"},
    ):
        foreign = applicant.model_copy(update=change)
        with pytest.raises(SecurityStateError, match="ACCESS_DENIED"):
            rig.begin(foreign, action)
        with pytest.raises(SecurityStateError, match="ACCESS_DENIED"):
            rig.seal(foreign, retirement)
        with pytest.raises(SecurityStateError, match="ACCESS_DENIED"):
            rig.state.get_retirement(
                foreign, applicant.task_id, applicant.operation_id,
                applicant.action_revision,
            )
    with pytest.raises(SecurityStateError, match="ACCESS_DENIED"):
        rig.state.get_retirement(
            applicant, "T2", applicant.operation_id, applicant.action_revision,
        )


def test_terminated_task_refuses_acceptance_and_sealing(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()

    rig.state.terminate_task(applicant, "VERIFICATION_FAILED")
    with pytest.raises(SecurityStateError, match="TASK_TERMINATED"):
        rig.begin(applicant, action)
    # Same table, same priority as claim_execution: a foreign identity does not
    # turn the persistent termination fact into ACCESS_DENIED.
    with pytest.raises(SecurityStateError, match="TASK_TERMINATED"):
        rig.begin(applicant.model_copy(update={"user_id": "U2", "session_id": "S2"}), action)

    rig = Rig(tmp_path / "between")
    applicant = context()
    retirement = rig.begin(applicant, action)
    rig.state.terminate_task(applicant, "VERIFICATION_FAILED")
    with pytest.raises(SecurityStateError, match="TASK_TERMINATED"):
        rig.seal(applicant, retirement)
    assert rig.stored(applicant).state == "pending_proof"


def test_platform_task_state_refuses_begin_and_seal(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    rig.task_terminated = True
    with pytest.raises(SecurityStateError, match="TASK_TERMINATED"):
        rig.begin(applicant, action)
    assert rig.stored(applicant) is None

    rig = Rig(tmp_path / "between")
    applicant = context()
    retirement = rig.begin(applicant, action)
    rig.task_terminated = True
    with pytest.raises(SecurityStateError, match="TASK_TERMINATED"):
        rig.seal(applicant, retirement)
    assert rig.stored(applicant).state == "pending_proof"


def test_unavailable_or_malformed_task_state_fails_closed(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()

    def unavailable(_context):
        raise RuntimeError("task store down")

    with pytest.raises(SecurityStateError, match="DEPENDENCY_UNAVAILABLE"):
        rig.begin(applicant, action, resolver=unavailable)
    with pytest.raises(SecurityStateError, match="DEPENDENCY_UNAVAILABLE"):
        rig.begin(applicant, action, resolver=lambda _context: "not-a-bool")
    assert rig.stored(applicant) is None

    retirement = rig.begin(applicant, action)
    with pytest.raises(SecurityStateError, match="DEPENDENCY_UNAVAILABLE"):
        rig.seal(applicant, retirement, resolver=unavailable)
    assert rig.stored(applicant).state == "pending_proof"


def test_sealing_requires_the_original_session(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    retirement = rig.begin(applicant, action)

    with pytest.raises(SecurityStateError, match="ACCESS_DENIED"):
        rig.seal(applicant.model_copy(update={"session_id": "S2"}), retirement)
    assert rig.stored(applicant).state == "pending_proof"


# --- Seal, audit atomicity, claim race (failure modes 8-14) ---


def test_replayed_seal_is_idempotent_and_other_evidence_conflicts(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    retirement = rig.begin(applicant, action)

    sealed = rig.seal(applicant, retirement)
    assert rig.seal(applicant, retirement) == sealed
    assert len(rig.events()) == 1
    assert rig.begin(applicant, action) == sealed

    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.seal(applicant, retirement, evidence=rig.evidence(
            applicant, retirement_id="BANK-RET-2",
        ))


def test_audit_event_shell_keeps_the_trusted_run_and_next_sequence(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    prior = prior_run_event(rig, applicant, action)
    retirement = rig.begin(applicant, action)
    sealed = rig.seal(applicant, retirement)

    event = rig.journal._event("D1", sealed.audit_ref)
    assert event.run_id == applicant.run_id
    assert event.payload.decision.run_id == applicant.run_id
    assert event.sequence == prior.sequence + 1


def test_claim_appearing_before_seal_records_conflict_without_editable_evidence(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    retirement = rig.begin(applicant, action)
    insert_claim_row(rig, applicant, action)

    with pytest.raises(SecurityStateError, match="OPERATION_UNKNOWN"):
        rig.seal(applicant, retirement)

    stored = rig.stored(applicant)
    assert stored.state == "conflict"
    assert stored.audit_ref is None and stored.sealed_at is None
    assert rig.events() == []
    # The claim now exists, so acceptance goes back to observing the original
    # operation; sealing sees the recorded conflict and never becomes editable.
    with pytest.raises(SecurityStateError, match="OPERATION_UNKNOWN"):
        rig.begin(applicant, action)
    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.seal(applicant, retirement)


def test_audit_failure_rolls_back_seal_and_retry_recovery(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    retirement = rig.begin(applicant, action)

    def unavailable(connection, event, **kwargs):
        raise RuntimeError("audit unavailable")

    with pytest.raises(SecurityStateError, match="AUDIT_UNAVAILABLE"):
        rig.seal(applicant, retirement, writer=unavailable)
    stored = rig.stored(applicant)
    assert stored.state == "pending_proof"
    assert stored.audit_ref is None and stored.sealed_at is None
    assert rig.events() == []

    sealed = rig.seal(applicant, retirement)
    assert sealed.state == "sealed"
    assert len(rig.events()) == 1


def test_seal_reuses_an_action_parameters_snapshot_stored_by_an_earlier_decision(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    retirement = rig.begin(applicant, action)

    # An earlier gate decision already stored this action's parameters as audit
    # evidence; the sealing transaction must not try to insert the same global id.
    with transaction(rig.path) as connection:
        connection.execute(
            "INSERT INTO audit_evidence VALUES (?, ?, ?, ?, ?)",
            (action.parameters_ref, "D1", "T1", "{}", "{}"),
        )

    sealed = rig.seal(applicant, retirement)
    assert sealed.state == "sealed"
    assert rig.journal._event("D1", sealed.audit_ref) is not None


def test_bank_evidence_must_bind_the_same_attempt(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    retirement = rig.begin(applicant, action)

    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.seal(applicant, retirement, evidence=rig.evidence(
            applicant, operation_id=str(uuid4()),
        ))
    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.seal(applicant, retirement, evidence=rig.evidence(
            applicant, action_revision=2,
        ))
    with pytest.raises(SecurityStateError, match="INPUT_REQUIRED"):
        rig.seal(applicant, retirement, evidence={"retirement_id": "BANK-RET-1"})
    with pytest.raises(SecurityStateError, match="RETIREMENT_STALE"):
        rig.seal(applicant, retirement.model_copy(update={"retirement_id": "missing"}))
    assert rig.stored(applicant).state == "pending_proof"


# --- claim_execution ordering (failure modes 15-16, 24-25) ---


def test_claim_after_a_failed_edit_executes_and_marks_conflict(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    record = approved_confirmation(rig, applicant, action)  # approved before the edit request
    claim_context = claim_fields(applicant, record)
    retirement = rig.begin(claim_context, action)

    # Authority §2: a failed edit attempt never kills the approved old action.
    claim, created = rig.state.claim_execution(
        claim_context, action, allow_decision(claim_context, action),
        rig.clock(), lambda _context: False,
    )
    assert created and claim.state == "processing"
    assert rig.state.record_execution(
        claim_context, action, "completed", "RES-1",
    ).state == "completed"

    # The claim wins: the accepted retirement can never become edit evidence.
    stored = rig.stored(claim_context)
    assert stored.state == "conflict"
    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.seal(claim_context, retirement)
    assert rig.stored(claim_context).state == "conflict"
    assert rig.events() == []


def test_sealed_attempt_cannot_be_claimed_and_other_actions_work(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    retirement = rig.begin(applicant, action)
    rig.seal(applicant, retirement)

    claim_context = applicant.model_copy(update={
        "confirmation_id": "CONF-X", "confirmation_version": 1,
    })
    with pytest.raises(SecurityStateError, match="ACTION_RETIRED"):
        rig.state.claim_execution(
            claim_context, action, allow_decision(claim_context, action),
            rig.clock(), lambda _context: False,
        )

    other = context(operation_id=uuid4())
    record = approved_confirmation(rig, other, action)
    other_claim = claim_fields(other, record)
    claim, created = rig.state.claim_execution(
        other_claim, action, allow_decision(other_claim, action),
        rig.clock(), lambda _context: False,
    )
    assert created and claim.state == "processing"


def test_bank_standin_retired_challenge_cannot_enable_a_late_verification(tmp_path):
    from app.contracts.platform import TrustedContext
    from app.contracts.security import VerificationSummary
    from app.services.mock_bank.verification import ChallengeRetired, MockBankVerification

    rig = Rig(tmp_path)
    bank = MockBankVerification(
        tmp_path / "bank.sqlite3", demo_secret=b"s" * 32, clock=rig.clock,
    )
    applicant = context()
    trusted = TrustedContext(
        user_id=applicant.user_id, session_id=applicant.session_id,
        demo_round_id=applicant.demo_round_id, task_id=applicant.task_id,
        run_id=applicant.run_id, parent_task_id=None,
    )
    summary = VerificationSummary(
        operation_id=applicant.operation_id,
        action_revision=applicant.action_revision,
        source_confirmation_id="CONF-1", source_confirmation_version=1,
        action_name="bank.freeze_funds", amount_fen=50000, payee=None,
        display_fields=[DisplayField(name="amount", label="金额", value_text="500 元")],
    )
    bank.create_verification(
        trusted, "action_step_up", applicant.operation_id,
        applicant.action_revision, summary,
    )
    bank.retire_action_challenges(
        trusted,
        operation_id=applicant.operation_id,
        action_revision=applicant.action_revision,
    )

    # Once the bank has retired the attempt, a late verification cannot be
    # re-created, so a claim for that attempt cannot pass verification afterwards.
    with pytest.raises(ChallengeRetired):
        bank.create_verification(
            trusted, "action_step_up", applicant.operation_id,
            applicant.action_revision, summary,
        )


# --- gate must not fabricate ALLOW after a sealed/claimed attempt (M4) ---


def test_gate_never_allows_a_sealed_attempt(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = read_action()
    retirement = rig.begin(applicant, action)
    rig.seal(applicant, retirement)

    decision = build_gate(rig).check_action(applicant, action)
    assert decision.decision is SecurityDecisionCode.BLOCK
    assert "ACTION_RETIRED" in decision.reason_codes


def test_gate_still_allows_the_old_action_while_proof_is_pending(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = read_action()
    rig.begin(applicant, action)

    decision = build_gate(rig).check_action(applicant, action)
    assert decision.decision is SecurityDecisionCode.ALLOW


def test_gate_does_not_fake_allow_after_the_claim_won(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = read_action()
    record = approved_confirmation(rig, applicant, action)
    claim_context = claim_fields(applicant, record)
    rig.begin(claim_context, action)
    _claim, created = rig.state.claim_execution(
        claim_context, action, allow_decision(claim_context, action),
        rig.clock(), lambda _context: False,
    )
    assert created

    decision = build_gate(rig).check_action(claim_context, action)
    assert decision.decision is SecurityDecisionCode.BLOCK
    assert "OPERATION_UNKNOWN" in decision.reason_codes


# --- confirmation resend/approval must not produce approved (M4) ---


def test_confirmation_resend_and_approval_are_refused_during_retirement(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    fields = [DisplayField(name="amount", label="金额", value_text="500 元")]
    service = ConfirmationService(rig.path, clock=rig.clock)
    pending = service.create(applicant, action, fields)
    retirement = rig.begin(applicant, action)

    with pytest.raises(SecurityError, match="ACTION_RETIRED"):
        service.create(applicant, action, fields)
    with pytest.raises(SecurityError, match="ACTION_RETIRED"):
        service.answer(applicant, ConfirmationAnswer(
            confirmation_id=pending.confirmation_id,
            confirmation_version=pending.confirmation_version,
            choice="approve",
        ))
    assert rig.stored(applicant).state == "pending_proof"

    rig.seal(applicant, retirement)
    with pytest.raises(SecurityError, match="ACTION_RETIRED"):
        service.create(applicant, action, fields)
    with pytest.raises(SecurityError, match="ACTION_RETIRED"):
        service.answer(applicant, ConfirmationAnswer(
            confirmation_id=pending.confirmation_id,
            confirmation_version=pending.confirmation_version,
            choice="approve",
        ))

    # Ordinary actions of the same task are not affected (a new sequential
    # action uses the next revision, as the ordinary confirmation flow does).
    other = context(operation_id=uuid4(), action_revision=2)
    assert service.create(other, action, fields).decision == "pending"


# --- confirmation history (failure modes 17-19) ---


def test_confirmation_history_keeps_the_overwritten_record_verbatim(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    service = ConfirmationService(rig.path, clock=rig.clock)
    fields = [
        DisplayField(name="amount", label="金额", value_text="500 元"),
        DisplayField(name="product", label="商品", value_text="鲜花礼盒"),
    ]
    first = service.create(applicant, action, fields)
    approved = service.answer(applicant, ConfirmationAnswer(
        confirmation_id=first.confirmation_id,
        confirmation_version=first.confirmation_version,
        choice="approve",
    ))

    second_ctx = context(operation_id=uuid4(), action_revision=2)
    second = service.create(
        second_ctx, freeze_action("birthday:freeze:40000"),
        [DisplayField(name="amount", label="金额", value_text="400 元")],
    )
    assert second.confirmation_id == first.confirmation_id
    assert second.confirmation_version == 2

    history = rig.state.get_confirmation_history(applicant, first.confirmation_id)
    assert [item.confirmation_version for item in history] == [1]
    assert history[0] == approved
    assert history[0].decision == "approved"
    assert history[0].display_fields == fields
    assert history[0].parameters_ref == action.parameters_ref
    assert rig.state.get_confirmation_history(
        applicant, first.confirmation_id, 1,
    ) == history
    assert rig.state.get_confirmation_history(
        applicant, first.confirmation_id, 99,
    ) == []

    # Answer the second version, then overwrite it: the archived decision for
    # version 1 must stay the original one, and version 2 is kept as approved.
    service.answer(second_ctx, ConfirmationAnswer(
        confirmation_id=second.confirmation_id,
        confirmation_version=second.confirmation_version,
        choice="approve",
    ))
    third_ctx = context(operation_id=uuid4(), action_revision=3)
    service.create(
        third_ctx, freeze_action("birthday:freeze:30000"),
        [DisplayField(name="amount", label="金额", value_text="300 元")],
    )
    history = rig.state.get_confirmation_history(applicant, first.confirmation_id)
    assert [item.confirmation_version for item in history] == [1, 2]
    assert history[0].decision == "approved"
    assert history[1].decision == "approved"
    assert history[0].display_fields == fields

    intruder = context(user_id="U2", session_id="S2")
    with pytest.raises(SecurityStateError, match="ACCESS_DENIED"):
        rig.state.get_confirmation_history(intruder, first.confirmation_id)


# --- warm pending_freeze retirement and the controlled ending (20-23) ---


def test_pending_freeze_authorization_is_invalidated_with_new_reason(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    record = release_confirmation(rig, applicant, action)
    authorization_record = grant_release_authorization(
        rig.state, applicant, record, account_id="BA1", amount_fen=50000,
        now=rig.clock(),
    )
    assert authorization_record.status == "pending_freeze"

    retirement = rig.begin(applicant, action)
    rig.seal(applicant, retirement)

    stored = rig.state.get_release_authorization(
        applicant, authorization_record.release_authorization_id,
    )
    assert stored is not None and stored.status == "invalid"
    assert stored.invalid_reason == "RETIRED_UNSUBMITTED"

    outcome = finalizer(rig).finalize(
        ending_context(applicant, authorization_record.release_authorization_id),
        "user_cancelled",
    )
    assert outcome.status == "nothing_to_release"
    assert "RETIRED_UNSUBMITTED" in outcome.decision.reason_codes
    assert "FREEZE_FAILED" not in outcome.decision.reason_codes


def test_unrelated_active_authorization_is_never_invalidated(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()

    other_operation = uuid4()
    active = authorization(operation_id=other_operation, status="active")
    rig.state.store_release_authorization(active)

    record = release_confirmation(rig, applicant, action)
    pending = grant_release_authorization(
        rig.state, applicant, record, account_id="BA1", amount_fen=50000,
        now=rig.clock(),
    )
    retirement = rig.begin(applicant, action)
    rig.seal(applicant, retirement)

    assert rig.state.get_release_authorization(
        applicant, pending.release_authorization_id,
    ).status == "invalid"
    unchanged = rig.state.get_release_authorization(
        applicant, active.release_authorization_id,
    )
    assert unchanged is not None and unchanged.status == "active"
    assert unchanged.freeze_id == "F-1"


def test_active_authorization_of_the_same_attempt_blocks_sealing(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    active = authorization(operation_id=applicant.operation_id, status="active")
    rig.state.store_release_authorization(active)
    retirement = rig.begin(applicant, action)

    with pytest.raises(SecurityStateError, match="OPERATION_CONFLICT"):
        rig.seal(applicant, retirement)
    assert rig.stored(applicant).state == "pending_proof"
    kept = rig.state.get_release_authorization(
        applicant, active.release_authorization_id,
    )
    assert kept is not None and kept.status == "active"


def test_sealed_guard_matches_the_attempt_revision(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    retirement = rig.begin(applicant, action)
    rig.seal(applicant, retirement)

    # A later attempt sharing the operation id but another action revision is not
    # misblocked by the sealed retirement of the earlier revision.
    later = authorization(
        operation_id=applicant.operation_id, status="pending_freeze",
        action_revision=2,
    )
    assert rig.state.store_release_authorization(later) == later

    same = authorization(
        operation_id=applicant.operation_id, status="pending_freeze",
        action_revision=1,
    )
    with pytest.raises(ValueError, match="ACTION_RETIRED"):
        rig.state.store_release_authorization(same)


def test_late_grant_after_sealing_cannot_create_a_pending_authorization(tmp_path):
    rig = Rig(tmp_path)
    applicant = context()
    action = freeze_action()
    record = release_confirmation(rig, applicant, action)
    retirement = rig.begin(applicant, action)
    rig.seal(applicant, retirement)

    with pytest.raises(ValueError, match="ACTION_RETIRED"):
        grant_release_authorization(
            rig.state, applicant, record, account_id="BA1", amount_fen=50000,
            now=rig.clock(),
        )
    assert rig.state.get_release_authorization(applicant, "rel_missing") is None
