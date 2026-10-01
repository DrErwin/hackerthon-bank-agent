"""Acceptance tests for the v0.3 deterministic security gate."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from app.contracts.common import DisplayField, OperationLevel, Phase, RiskLevel, SecurityDecisionCode
from app.contracts.bank import PayeeDisplay
from app.contracts.platform import CapabilityDefinition
from app.contracts.security import (
    ActionDescriptor,
    ConfirmationAnswer,
    ExecutionSecurityContext,
    VerificationChallenge,
    VerificationRecord,
    VerificationSummary,
)
from app.modules.transfer.manifest import PRIVATE_TOOLS
from app.security.demo_policy import DemoRiskEvidence, DemoRiskSignal, DemoSecurityPolicy
from app.security.gate import POLICY_VERSION
from app.security import (
    ConfirmationService,
    DeterministicExecutor,
    OperationObservation,
    SecurityError,
    SecurityGate,
    ToolRegistrationError,
    ToolRegistry,
)


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)

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


def action(parameters_ref: str = "PARAM-1") -> ActionDescriptor:
    return ActionDescriptor(
        action_name="bank.submit_transfer",
        parameters_ref=parameters_ref,
        resource_refs=["A1", "A2"],
        phase=Phase.EXECUTION,
    )


def transfer_declaration() -> CapabilityDefinition:
    return CapabilityDefinition(
        name="bank.submit_transfer",
        input_schema_ref="TransferRequest",
        output_schema_ref="TransferReceipt",
        required_permissions=["transfer"],
        operation_level=OperationLevel.SENSITIVE,
        side_effect=True,
        confirmation_policy="per_action",
        timeout_ms=4_000,
        retry_policy="none",
        handler_ref="bank_gateway.submit_transfer",
    )


def verification(
    security_context: ExecutionSecurityContext,
    *,
    scope: str = "session",
    operation_id=None,
    action_revision=None,
    source_challenge_id: str = "CH1",
) -> VerificationRecord:
    return VerificationRecord(
        verification_id=str(uuid4()),
        user_id=security_context.user_id,
        session_id=security_context.session_id,
        demo_round_id=security_context.demo_round_id,
        scope=scope,
        operation_id=operation_id,
        action_revision=action_revision,
        methods=["code"] if scope == "session" else ["code", "mock_face"],
        verified_at=datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc),
        source_challenge_id=source_challenge_id,
    )


def approved_confirmation(
    confirmations: ConfirmationService,
    security_context: ExecutionSecurityContext,
    descriptor: ActionDescriptor,
):
    record = confirmations.create(
        security_context,
        descriptor,
        [DisplayField(name="amount", label="金额", value_text="500 元")],
    )
    approved = confirmations.answer(
        security_context,
        ConfirmationAnswer(
            confirmation_id=record.confirmation_id,
            confirmation_version=record.confirmation_version,
            choice="approve",
        ),
    )
    return security_context.model_copy(update={
        "confirmation_id": approved.confirmation_id,
        "confirmation_version": approved.confirmation_version,
    }), approved


def build_gate(
    path: Path,
    *,
    clock: Clock,
    records: dict[str, VerificationRecord] | None = None,
    risk: RiskLevel = RiskLevel.LOW,
    scope_allowed=True,
    task_terminated=False,
    decisions: list | None = None,
    snapshots: list | None = None,
    challenges: list | None = None,
    handler=lambda _context, payload: payload,
    risk_assessor=None,
    declaration=None,
    scope_authorizer=None,
):
    registry = ToolRegistry()
    registry.register(declaration or transfer_declaration(), handler)
    confirmations = ConfirmationService(path, clock=clock)
    stored_records = records if records is not None else {}
    emitted = decisions if decisions is not None else []
    written_snapshots = snapshots if snapshots is not None else []
    created_challenges = challenges if challenges is not None else []

    def resolve(security_context, verification_id):
        record = stored_records[verification_id]
        if (record.user_id, record.session_id, record.demo_round_id) != (
            security_context.user_id,
            security_context.session_id,
            security_context.demo_round_id,
        ):
            raise SecurityError("ACCESS_DENIED")
        return record

    def prepare_confirmation(security_context, descriptor):
        return confirmations.create(
            security_context,
            descriptor,
            [DisplayField(name="amount", label="金额", value_text="500 元")],
        )

    def prepare_verification(security_context, descriptor, confirmation, current_risk):
        challenge_id = f"CH-{len(created_challenges) + 1}"
        action_step_up = current_risk == RiskLevel.MEDIUM
        summary = None
        if action_step_up:
            summary = VerificationSummary(
                operation_id=security_context.operation_id,
                action_revision=security_context.action_revision,
                source_confirmation_id=confirmation.confirmation_id,
                source_confirmation_version=confirmation.confirmation_version,
                action_name=descriptor.action_name,
                amount_fen=50_000,
                payee=PayeeDisplay(
                    payee_id="A2",
                    name_masked="张*",
                    account_masked="****1234",
                    remark=None,
                    bank_name="模拟银行",
                ),
                display_fields=[DisplayField(name="amount", label="金额", value_text="500 元")],
            )
        challenge = VerificationChallenge(
            challenge_id=challenge_id,
            user_id=security_context.user_id,
            session_id=security_context.session_id,
            demo_round_id=security_context.demo_round_id,
            task_id=security_context.task_id,
            purpose="action_step_up" if action_step_up else "basic_identity",
            operation_id=security_context.operation_id if action_step_up else None,
            action_revision=security_context.action_revision if action_step_up else None,
            summary=summary,
            required_methods=["code", "mock_face"] if action_step_up else ["code"],
            created_at=clock(),
            code_created_at=clock(),
            code_expires_at=clock() + timedelta(minutes=5),
            face_started_at=None,
            face_expires_at=None,
            challenge_status="pending",
            code_result="pending",
            face_result="pending" if action_step_up else "not_required",
            consecutive_code_failures=0,
        )
        created_challenges.append((challenge, confirmation, current_risk))
        return challenge

    def write_snapshot(security_context, confirmation, verifications, checked_at):
        written_snapshots.append((security_context, confirmation, verifications, checked_at))
        return f"AUTH-{len(written_snapshots)}"

    gate = SecurityGate(
        registry,
        confirmations,
        scope_authorizer=(scope_authorizer if scope_authorizer is not None else lambda *_: scope_allowed),
        task_state_resolver=lambda *_: task_terminated,
        risk_assessor=(risk_assessor if risk_assessor is not None else lambda *_: risk),
        confirmation_preparer=prepare_confirmation,
        verification_preparer=prepare_verification,
        verification_resolver=resolve,
        challenge_resolver=lambda _context, challenge_id: next(
            challenge.model_copy(update={"challenge_status": "passed"})
            for challenge, _, _ in created_challenges
            if challenge.challenge_id == challenge_id
        ),
        decision_sink=emitted.append,
        snapshot_writer=write_snapshot,
        summary_validator=lambda _context, _action, confirmation, summary: (
            summary.display_fields == confirmation.display_fields
            and summary.amount_fen == 50_000
            and summary.payee is not None
            and summary.payee.payee_id == "A2"
        ),
        clock=clock,
    )
    return (
        gate,
        confirmations,
        stored_records,
        emitted,
        written_snapshots,
        created_challenges,
    )


def ready_context(confirmations, records, security_context, descriptor):
    confirmed, _ = approved_confirmation(confirmations, security_context, descriptor)
    basic = verification(confirmed)
    records[basic.verification_id] = basic
    return confirmed.model_copy(update={"verification_ids": [basic.verification_id]})


def executor(gate, bank_results, *, parameter_resolver, result_observer=None):
    def lookup(security_context, _descriptor):
        result = bank_results.get(str(security_context.operation_id))
        if result is None:
            return OperationObservation(
                operation_id=security_context.operation_id,
                state="processing",
                result=None,
                result_ref=None,
            )
        return OperationObservation(
            operation_id=security_context.operation_id,
            state="completed",
            result=result,
            result_ref=result["transaction_id"],
        )

    def observe(result):
        if result_observer is not None:
            return result_observer(result)
        bank_results[result["operation_id"]] = result
        return OperationObservation(
            operation_id=uuid4() if result.get("wrong_operation") else UUID(result["operation_id"]),
            state="completed",
            result=result,
            result_ref=result["transaction_id"],
        )

    return DeterministicExecutor(
        gate,
        parameter_resolver=parameter_resolver,
        operation_lookup=lookup,
        result_observer=observe,
    )


def test_registry_rejects_missing_or_unsafe_tool_declarations():
    registry = ToolRegistry()
    raw = transfer_declaration().model_dump(mode="json")

    for missing in ("required_permissions", "side_effect", "confirmation_policy", "operation_level"):
        invalid = raw.copy()
        invalid.pop(missing)
        with pytest.raises(ToolRegistrationError, match="INVALID_TOOL_DECLARATION"):
            registry.register(invalid, lambda *_: None)

    with pytest.raises(ToolRegistrationError, match="PERMISSIONS_REQUIRED"):
        registry.register(raw | {"required_permissions": []}, lambda *_: None)
    with pytest.raises(ToolRegistrationError, match="CONFIRMATION_POLICY_REQUIRED"):
        registry.register(raw | {"confirmation_policy": "none"}, lambda *_: None)


def test_confirmation_is_durable_button_only_versioned_and_one_hour(tmp_path):
    clock = Clock()
    path = tmp_path / "application.sqlite3"
    confirmations = ConfirmationService(path, clock=clock)
    original = context()
    descriptor = action()
    record = confirmations.create(
        original,
        descriptor,
        [DisplayField(name="amount", label="金额", value_text="500 元")],
    )

    assert record.expires_at - record.created_at == timedelta(hours=1)
    with pytest.raises(SecurityError, match="INVALID_CONFIRMATION_ANSWER"):
        confirmations.answer(original, True)  # type: ignore[arg-type]
    with pytest.raises(SecurityError, match="ACCESS_DENIED"):
        confirmations.answer(
            original.model_copy(update={"user_id": "U2"}),
            ConfirmationAnswer(
                confirmation_id=record.confirmation_id,
                confirmation_version=record.confirmation_version,
                choice="approve",
            ),
        )

    answer = ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version,
        choice="approve",
    )
    approved = confirmations.answer(original, answer)
    assert ConfirmationService(path, clock=clock).answer(original, answer) == approved

    changed = original.model_copy(update={"operation_id": uuid4(), "action_revision": 2})
    replacement = confirmations.create(
        changed,
        action("PARAM-2"),
        [DisplayField(name="amount", label="金额", value_text="600 元")],
    )
    assert replacement.confirmation_version == approved.confirmation_version + 1
    with pytest.raises(SecurityError, match="CONFIRMATION_STALE"):
        confirmations.answer(original, answer)

    clock.advance(hours=1)
    with pytest.raises(SecurityError, match="CONFIRMATION_EXPIRED"):
        confirmations.answer(
            changed,
            ConfirmationAnswer(
                confirmation_id=replacement.confirmation_id,
                confirmation_version=replacement.confirmation_version,
                choice="approve",
            ),
        )
    with sqlite3.connect(path) as connection:
        stored = connection.execute(
            "SELECT confirmation_json FROM security_confirmations WHERE confirmation_id = ?",
            (replacement.confirmation_id,),
        ).fetchone()[0]
    assert json.loads(stored)["decision"] == "expired"


def test_expired_execution_claim_persists_confirmation_state(tmp_path):
    clock = Clock()
    path = tmp_path / "application.sqlite3"
    gate, confirmations, records, _, _, _ = build_gate(path, clock=clock)
    descriptor = action()
    ready = ready_context(confirmations, records, context(), descriptor)
    decision = gate.check_action(ready, descriptor)
    clock.advance(hours=1)

    with pytest.raises(ValueError, match="CONFIRMATION_EXPIRED"):
        confirmations.state.claim_execution(
            ready, descriptor, decision, clock(), lambda _context: False,
        )
    with sqlite3.connect(path) as connection:
        stored = connection.execute(
            "SELECT confirmation_json FROM security_confirmations WHERE confirmation_id = ?",
            (ready.confirmation_id,),
        ).fetchone()[0]
        claims = connection.execute("SELECT COUNT(*) FROM security_executions").fetchone()[0]
    assert json.loads(stored)["decision"] == "expired"
    assert claims == 0


def test_new_session_reissues_confirmation_and_rejects_old_session(tmp_path):
    clock = Clock()
    confirmations = ConfirmationService(tmp_path / "application.sqlite3", clock=clock)
    original = context()
    record = confirmations.create(
        original,
        action(),
        [DisplayField(name="amount", label="金额", value_text="500 元")],
    )
    new_session = original.model_copy(update={"session_id": "S2"})
    replacement = confirmations.create(
        new_session,
        action(),
        [DisplayField(name="amount", label="金额", value_text="500 元")],
    )
    assert replacement.confirmation_version == record.confirmation_version + 1
    assert replacement.session_id == "S2"
    with pytest.raises(SecurityError, match="ACCESS_DENIED"):
        confirmations.get(original, record.confirmation_id)


def test_approved_unclaimed_confirmation_expires_and_is_reissued(tmp_path):
    clock = Clock()
    gate, confirmations, _, _, _, _ = build_gate(
        tmp_path / "application.sqlite3", clock=clock,
    )
    security_context = context()
    confirmed, approved = approved_confirmation(confirmations, security_context, action())
    clock.advance(hours=1)

    expired = gate.check_action(confirmed, action())
    replacement = confirmations.get(
        security_context, expired.interaction.record_ref,
    )
    assert expired.decision == SecurityDecisionCode.REQUIRE_CONFIRMATION
    assert expired.reason_codes == ["CONFIRMATION_EXPIRED"]
    assert replacement.decision == "pending"
    assert replacement.confirmation_version == approved.confirmation_version + 1


def test_gate_uses_real_confirmation_and_verification_record_refs(tmp_path):
    clock = Clock()
    gate, confirmations, records, decisions, snapshots, challenges = build_gate(
        tmp_path / "application.sqlite3", clock=clock,
    )
    security_context = context()
    descriptor = action()

    waiting_confirmation = gate.check_action(security_context, descriptor)
    stored = confirmations.get(
        security_context, waiting_confirmation.interaction.record_ref,
    )
    assert waiting_confirmation.decision == SecurityDecisionCode.REQUIRE_CONFIRMATION
    assert waiting_confirmation.interaction.record_ref == stored.confirmation_id

    confirmed_context, approved = approved_confirmation(confirmations, security_context, descriptor)
    waiting_verification = gate.check_action(confirmed_context, descriptor)
    assert waiting_verification.decision == SecurityDecisionCode.REQUIRE_VERIFICATION
    assert waiting_verification.interaction.record_ref == challenges[0][0].challenge_id
    assert challenges[0][1].decision == "approved"

    basic = verification(confirmed_context)
    records[basic.verification_id] = basic
    ready = confirmed_context.model_copy(update={"verification_ids": [basic.verification_id]})
    allowed = gate.check_action(ready, descriptor)
    assert allowed.decision == SecurityDecisionCode.ALLOW
    assert allowed.reason_codes == ["SECURITY_CHECK_PASSED"]
    assert allowed.authorization_snapshot_ref == "AUTH-1"
    assert snapshots[0][1].decision == "approved"
    assert [item.decision for item in decisions] == [
        SecurityDecisionCode.REQUIRE_CONFIRMATION,
        SecurityDecisionCode.REQUIRE_VERIFICATION,
        SecurityDecisionCode.ALLOW,
    ]


def test_foreign_verification_blocks_and_invalid_challenge_pauses(tmp_path):
    clock = Clock()
    gate, confirmations, records, _, _, challenges = build_gate(
        tmp_path / "application.sqlite3", clock=clock,
    )
    security_context = context()
    confirmed, _ = approved_confirmation(confirmations, security_context, action())
    foreign = verification(confirmed.model_copy(update={"user_id": "U2"}))
    records[foreign.verification_id] = foreign
    denied = gate.check_action(
        confirmed.model_copy(update={"verification_ids": [foreign.verification_id]}),
        action(),
    )
    assert denied.decision == SecurityDecisionCode.BLOCK
    assert denied.reason_codes == ["ACCESS_DENIED"]

    waiting = gate.check_action(confirmed, action())
    assert waiting.decision == SecurityDecisionCode.REQUIRE_VERIFICATION
    invalid = challenges[-1][0].model_copy(update={"user_id": "U2"})
    gate.verification_preparer = lambda *_: invalid
    paused = gate.check_action(confirmed, action())
    assert paused.decision == SecurityDecisionCode.PAUSE
    assert paused.reason_codes == ["DEPENDENCY_UNAVAILABLE"]


def test_stale_cancelled_cross_user_and_changed_parameters_never_allow(tmp_path):
    clock = Clock()
    gate, confirmations, records, _, _, _ = build_gate(
        tmp_path / "application.sqlite3", clock=clock,
    )
    security_context = context()
    descriptor = action()
    confirmed_context, approved = approved_confirmation(confirmations, security_context, descriptor)
    basic = verification(confirmed_context)
    records[basic.verification_id] = basic

    stale = gate.check_action(
        confirmed_context.model_copy(update={
            "verification_ids": [basic.verification_id],
            "operation_id": uuid4(),
            "action_revision": 2,
        }),
        action("PARAM-2"),
    )
    assert stale.decision == SecurityDecisionCode.BLOCK
    assert stale.reason_codes == ["CONFIRMATION_STALE"]

    other_user = confirmed_context.model_copy(update={
        "user_id": "U2",
        "verification_ids": [basic.verification_id],
    })
    denied = gate.check_action(other_user, descriptor)
    assert denied.decision == SecurityDecisionCode.BLOCK
    assert denied.reason_codes == ["ACCESS_DENIED"]

    cancelled_context = context(task_id="T2", operation_id=uuid4())
    cancelled = confirmations.create(
        cancelled_context,
        descriptor,
        [DisplayField(name="amount", label="金额", value_text="500 元")],
    )
    confirmations.answer(
        cancelled_context,
        ConfirmationAnswer(
            confirmation_id=cancelled.confirmation_id,
            confirmation_version=cancelled.confirmation_version,
            choice="cancel",
        ),
    )
    cancelled_context = cancelled_context.model_copy(update={
        "confirmation_id": cancelled.confirmation_id,
        "confirmation_version": cancelled.confirmation_version,
    })
    refused = gate.check_action(cancelled_context, descriptor)
    assert refused.decision == SecurityDecisionCode.BLOCK
    assert refused.reason_codes == ["TASK_TERMINATED"]
    assert approved.parameters_ref == "PARAM-1"


def test_risk_verification_rules_and_dependency_fail_closed(tmp_path):
    clock = Clock()
    gate, confirmations, records, _, _, _ = build_gate(
        tmp_path / "medium.sqlite3", clock=clock, risk=RiskLevel.MEDIUM,
    )
    security_context = context()
    descriptor = action()
    confirmed_context, approved = approved_confirmation(confirmations, security_context, descriptor)
    basic = verification(confirmed_context)
    records[basic.verification_id] = basic
    with_basic = confirmed_context.model_copy(update={"verification_ids": [basic.verification_id]})
    assert gate.check_action(with_basic, descriptor).decision == SecurityDecisionCode.REQUIRE_VERIFICATION

    action_record = verification(
        confirmed_context,
        scope="action",
        operation_id=confirmed_context.operation_id,
        action_revision=confirmed_context.action_revision,
        source_challenge_id=gate.verification_preparer(
            confirmed_context, descriptor, approved, RiskLevel.MEDIUM,
        ).challenge_id,
    )
    records[action_record.verification_id] = action_record
    with_action = confirmed_context.model_copy(update={"verification_ids": [action_record.verification_id]})
    assert gate.check_action(with_action, descriptor).decision == SecurityDecisionCode.ALLOW

    high_gate, _, _, _, _, _ = build_gate(
        tmp_path / "high.sqlite3", clock=clock, risk=RiskLevel.HIGH,
    )
    blocked = high_gate.check_action(security_context, descriptor)
    assert blocked.decision == SecurityDecisionCode.BLOCK
    assert blocked.reason_codes == ["HIGH_RISK"]

    broken_gate, _, _, _, _, _ = build_gate(
        tmp_path / "broken.sqlite3", clock=clock, scope_allowed=None,
    )
    assert broken_gate.check_action(security_context, descriptor).decision == SecurityDecisionCode.PAUSE



def _demo_policy_for(signals):
    evidence = DemoRiskEvidence(
        source="server-demo-fixture",
        source_version="1",
        evidence_ref="case-1",
        signals=frozenset(signals),
        checked_signals=frozenset(DemoRiskSignal),
    )
    return DemoSecurityPolicy(
        demo_user_id="U1",
        admin_actor_id="ADMIN-1",
        current_demo_round=lambda: "D1",
        risk_facts=lambda *_: evidence,
    )


def test_demo_policy_is_connected_to_gate_confirmation_verification_and_audit(tmp_path):
    descriptor = action()
    declaration = PRIVATE_TOOLS[-1]
    low_policy = _demo_policy_for({
        DemoRiskSignal.FAMILIAR_PAYEE,
        DemoRiskSignal.FAMILIAR_DEVICE,
        DemoRiskSignal.USUAL_AMOUNT_RANGE,
        DemoRiskSignal.CLEAR_REQUEST,
    })
    low_gate, confirmations, records, _, _, _ = build_gate(
        tmp_path / "demo-low.sqlite3",
        clock=Clock(),
        risk_assessor=low_policy.assess_risk,
        declaration=declaration,
        scope_authorizer=low_policy.authorize_tool,
    )
    security_context = context()
    waiting_confirmation = low_gate.check_action(security_context, descriptor)
    assert waiting_confirmation.decision == SecurityDecisionCode.REQUIRE_CONFIRMATION
    assert waiting_confirmation.policy_version == f"{POLICY_VERSION}+{low_policy.policy_version}"
    assert waiting_confirmation.evidence_refs == ["server-demo-fixture:1:case-1"]
    assert "demo-risk-low" in waiting_confirmation.rule_ids

    confirmed, _ = approved_confirmation(confirmations, security_context, descriptor)
    waiting_verification = low_gate.check_action(confirmed, descriptor)
    assert waiting_verification.decision == SecurityDecisionCode.REQUIRE_VERIFICATION
    basic = verification(confirmed)
    records[basic.verification_id] = basic
    allowed = low_gate.check_action(
        confirmed.model_copy(update={"verification_ids": [basic.verification_id]}), descriptor,
    )
    assert allowed.decision == SecurityDecisionCode.ALLOW
    assert allowed.evidence_refs == waiting_confirmation.evidence_refs

    medium_policy = _demo_policy_for({DemoRiskSignal.NEW_PAYEE})
    medium_gate, medium_confirmations, medium_records, _, _, challenges = build_gate(
        tmp_path / "demo-medium.sqlite3",
        clock=Clock(),
        risk_assessor=medium_policy.assess_risk,
        declaration=declaration,
        scope_authorizer=medium_policy.authorize_tool,
    )
    medium_waiting = medium_gate.check_action(security_context, descriptor)
    assert medium_waiting.decision == SecurityDecisionCode.REQUIRE_CONFIRMATION
    assert medium_waiting.risk_level == RiskLevel.MEDIUM
    assert "demo-risk-medium" in medium_waiting.rule_ids
    medium_confirmed, medium_confirmation = approved_confirmation(
        medium_confirmations, security_context, descriptor,
    )
    basic = verification(medium_confirmed)
    medium_records[basic.verification_id] = basic
    step_up = medium_gate.check_action(
        medium_confirmed.model_copy(update={"verification_ids": [basic.verification_id]}),
        descriptor,
    )
    assert step_up.decision == SecurityDecisionCode.REQUIRE_VERIFICATION
    assert challenges[-1][0].purpose == "action_step_up"
    action_verification = verification(
        medium_confirmed,
        scope="action",
        operation_id=medium_confirmed.operation_id,
        action_revision=medium_confirmed.action_revision,
        source_challenge_id=challenges[-1][0].challenge_id,
    )
    medium_records[action_verification.verification_id] = action_verification
    medium_allowed = medium_gate.check_action(
        medium_confirmed.model_copy(update={
            "verification_ids": [action_verification.verification_id],
        }),
        descriptor,
    )
    assert medium_allowed.decision == SecurityDecisionCode.ALLOW
    assert "demo-risk-medium" in medium_allowed.rule_ids

    high_policy = _demo_policy_for({DemoRiskSignal.SCREEN_SHARING})
    high_gate, high_confirmations, _, _, _, _ = build_gate(
        tmp_path / "demo-high.sqlite3",
        clock=Clock(),
        risk_assessor=high_policy.assess_risk,
        declaration=declaration,
        scope_authorizer=high_policy.authorize_tool,
    )
    approved_high_context, _ = approved_confirmation(
        high_confirmations, security_context, descriptor,
    )
    high_blocked = high_gate.check_action(approved_high_context, descriptor)
    assert high_blocked.decision == SecurityDecisionCode.BLOCK
    assert high_blocked.reason_codes == ["HIGH_RISK"]
    assert high_blocked.evidence_refs == ["server-demo-fixture:1:case-1"]
    assert "demo-risk-high" in high_blocked.rule_ids


def test_demo_policy_records_specific_fail_closed_risk_blocker(tmp_path):
    policy = _demo_policy_for(set())
    gate, _, _, _, _, _ = build_gate(
        tmp_path / "demo-missing-risk.sqlite3",
        clock=Clock(),
        risk_assessor=policy.assess_risk,
        declaration=PRIVATE_TOOLS[-1],
        scope_authorizer=policy.authorize_tool,
    )

    paused = gate.check_action(context(), action())
    assert paused.decision == SecurityDecisionCode.PAUSE
    assert paused.reason_codes == ["DEPENDENCY_UNAVAILABLE"]
    assert paused.policy_version == f"{POLICY_VERSION}+{policy.policy_version}"
    assert "low-risk-evidence-required" in paused.rule_ids


def test_audit_failure_preserves_risk_provenance_and_never_executes(tmp_path):
    policy = _demo_policy_for({
        DemoRiskSignal.FAMILIAR_PAYEE,
        DemoRiskSignal.FAMILIAR_DEVICE,
        DemoRiskSignal.USUAL_AMOUNT_RANGE,
        DemoRiskSignal.CLEAR_REQUEST,
    })
    calls = []
    gate, confirmations, records, _, _, _ = build_gate(
        tmp_path / "demo-audit-failure.sqlite3",
        clock=Clock(),
        risk_assessor=policy.assess_risk,
        declaration=PRIVATE_TOOLS[-1],
        scope_authorizer=policy.authorize_tool,
        handler=lambda *_: calls.append(True),
    )
    ready = ready_context(confirmations, records, context(), action())
    attempted = []

    def unavailable_sink(decision):
        attempted.append(decision)
        raise RuntimeError("audit unavailable")

    gate.decision_sink = unavailable_sink
    outcome = executor(gate, {}, parameter_resolver=lambda *_: {}).execute(ready, action())
    paused = outcome.decision
    assert paused.decision == SecurityDecisionCode.PAUSE
    assert paused.reason_codes == ["AUDIT_UNAVAILABLE"]
    assert paused.policy_version == f"{POLICY_VERSION}+{policy.policy_version}"
    assert paused.evidence_refs == ["server-demo-fixture:1:case-1"]
    assert set(attempted[0].rule_ids) <= set(paused.rule_ids)
    assert "demo-risk-low" in paused.rule_ids
    assert "audit-before-sensitive-execution" in paused.rule_ids
    assert not outcome.executed
    assert calls == []
    assert gate.confirmations.state.get_execution(ready, action()) is None

def test_scope_and_task_checks_precede_missing_binding(tmp_path):
    clock = Clock()
    missing = context(operation_id=None, action_revision=None)
    denied_gate, _, _, _, _, _ = build_gate(
        tmp_path / "denied.sqlite3", clock=clock, scope_allowed=False,
    )
    denied = denied_gate.check_action(missing, action())
    assert denied.decision == SecurityDecisionCode.BLOCK
    assert denied.reason_codes == ["ACCESS_DENIED"]

    terminated_gate, _, _, _, _, _ = build_gate(
        tmp_path / "terminated.sqlite3", clock=clock, task_terminated=True,
    )
    terminated = terminated_gate.check_action(missing, action())
    assert terminated.decision == SecurityDecisionCode.BLOCK
    assert terminated.reason_codes == ["TASK_TERMINATED"]

    input_gate, _, _, _, _, _ = build_gate(
        tmp_path / "input.sqlite3", clock=clock,
    )
    required = input_gate.check_action(missing, action())
    assert required.decision == SecurityDecisionCode.REQUIRE_INPUT

    input_gate.task_state_resolver = lambda *_: (_ for _ in ()).throw(RuntimeError())
    paused = input_gate.check_action(context(), action())
    assert paused.decision == SecurityDecisionCode.PAUSE


def test_audit_failure_pauses_before_handler(tmp_path):
    clock = Clock()
    calls = []
    gate, confirmations, records, _, _, _ = build_gate(
        tmp_path / "application.sqlite3",
        clock=clock,
        decisions=[],
        handler=lambda *_: calls.append(True),
    )
    gate.decision_sink = lambda _decision: (_ for _ in ()).throw(RuntimeError("audit down"))
    ready = ready_context(confirmations, records, context(), action())
    basic = records[ready.verification_ids[0]]
    gate.verification_resolver = lambda *_: basic
    paused = gate.check_action(ready, action())
    assert paused.decision == SecurityDecisionCode.PAUSE
    assert paused.reason_codes == ["AUDIT_UNAVAILABLE"]
    assert calls == []
    with pytest.raises(SecurityError, match="AUDIT_UNAVAILABLE"):
        gate.check_action(ready.model_copy(update={"user_id": "U2"}), action())


def test_cancel_before_claim_blocks_and_cancel_after_claim_conflicts(tmp_path):
    clock = Clock()
    calls = []

    def handler(security_context, payload):
        calls.append(payload)
        return {
            "operation_id": str(security_context.operation_id),
            "transaction_id": "TX-1",
        }

    gate, confirmations, records, _, _, _ = build_gate(
        tmp_path / "application.sqlite3", clock=clock, handler=handler,
    )
    security_context = context()
    descriptor = action()
    ready = ready_context(confirmations, records, security_context, descriptor)
    cancel_answer = ConfirmationAnswer(
        confirmation_id=ready.confirmation_id,
        confirmation_version=ready.confirmation_version,
        choice="cancel",
    )
    confirmations.answer(ready, cancel_answer)
    blocked = executor(
        gate, {}, parameter_resolver=lambda *_: {"amount_fen": 50_000},
    ).execute(ready, descriptor)
    assert blocked.decision.decision == SecurityDecisionCode.BLOCK
    assert calls == []

    second = context(task_id="T2", operation_id=uuid4())
    ready_second = ready_context(confirmations, records, second, descriptor)
    run = executor(gate, {}, parameter_resolver=lambda *_: {"amount_fen": 60_000})
    assert run.execute(ready_second, descriptor).executed
    with pytest.raises(SecurityError, match="CONFIRMATION_CONFLICT"):
        confirmations.answer(
            ready_second,
            ConfirmationAnswer(
                confirmation_id=ready_second.confirmation_id,
                confirmation_version=ready_second.confirmation_version,
                choice="cancel",
            ),
        )


def test_duplicate_and_restart_recover_without_reinvoking_handler(tmp_path):
    clock = Clock()
    calls = []
    bank_results = {}

    def handler(security_context, payload):
        calls.append(payload)
        return {
            "operation_id": str(security_context.operation_id),
            "transaction_id": "TX-1",
            "payload": payload,
        }

    path = tmp_path / "application.sqlite3"
    gate, confirmations, records, _, _, _ = build_gate(
        path, clock=clock, handler=handler,
    )
    descriptor = action()
    ready = ready_context(confirmations, records, context(), descriptor)
    payloads = {"PARAM-1": {"amount_fen": 50_000}}
    first_executor = executor(
        gate,
        bank_results,
        parameter_resolver=lambda _context, current: payloads[current.parameters_ref],
    )
    first = first_executor.execute(ready, descriptor)
    replay = first_executor.execute(ready, descriptor)
    assert first.executed and first.state == "completed"
    assert replay.reused and replay.result == first.result
    assert calls == [{"amount_fen": 50_000}]

    clock.advance(hours=2)
    restarted_gate, _, restarted_records, _, _, _ = build_gate(
        path, clock=clock, handler=handler,
    )
    restarted_records.update(records)
    restarted = executor(
        restarted_gate,
        bank_results,
        parameter_resolver=lambda *_: (_ for _ in ()).throw(AssertionError("must not resolve")),
    ).execute(ready, descriptor)
    assert restarted.reused and restarted.result == first.result
    assert calls == [{"amount_fen": 50_000}]

    lookup_failed = DeterministicExecutor(
        restarted_gate,
        parameter_resolver=lambda *_: (_ for _ in ()).throw(AssertionError()),
        operation_lookup=lambda *_: (_ for _ in ()).throw(TimeoutError()),
        result_observer=lambda result: result,
    ).execute(ready, descriptor)
    assert lookup_failed.reused and lookup_failed.state == "completed"
    assert lookup_failed.result_ref == "TX-1"

    weaker_observation = DeterministicExecutor(
        restarted_gate,
        parameter_resolver=lambda *_: (_ for _ in ()).throw(AssertionError()),
        operation_lookup=lambda *_: OperationObservation(
            operation_id=ready.operation_id,
            state="processing",
            result=None,
            result_ref=None,
        ),
        result_observer=lambda result: result,
    ).execute(ready, descriptor)
    assert weaker_observation.reused and weaker_observation.state == "completed"
    assert weaker_observation.result_ref == "TX-1"

    with pytest.raises(SecurityError, match="OPERATION_CONFLICT"):
        first_executor.execute(ready, action("PARAM-2"))
    with pytest.raises(SecurityError, match="ACCESS_DENIED"):
        first_executor.execute(ready.model_copy(update={"user_id": "U2"}), descriptor)


def test_concurrent_duplicate_clicks_claim_one_handler_call(tmp_path):
    clock = Clock()
    calls = []
    rendezvous = Barrier(2)

    def handler(security_context, payload):
        calls.append(payload)
        return {
            "operation_id": str(security_context.operation_id),
            "transaction_id": "TX-1",
        }

    path = tmp_path / "application.sqlite3"
    records = {}
    gate, confirmations, records, _, _, _ = build_gate(
        path, clock=clock, handler=handler, records=records,
    )
    second_gate, _, _, _, _, _ = build_gate(
        path, clock=clock, handler=handler, records=records,
    )
    descriptor = action()
    ready = ready_context(confirmations, records, context(), descriptor)
    bank_results = {}

    def resolve_parameters(*_):
        rendezvous.wait()
        return {"amount_fen": 50_000}

    first_executor = executor(
        gate,
        bank_results,
        parameter_resolver=resolve_parameters,
    )
    second_executor = executor(
        second_gate,
        bank_results,
        parameter_resolver=resolve_parameters,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            pool.submit(first_executor.execute, ready, descriptor),
            pool.submit(second_executor.execute, ready, descriptor),
        ]
        outcomes = [future.result() for future in outcomes]

    assert sum(outcome.executed for outcome in outcomes) == 1
    assert sum(outcome.reused for outcome in outcomes) == 1
    assert calls == [{"amount_fen": 50_000}]


def test_cancel_and_claim_race_has_one_winner(tmp_path):
    clock = Clock()
    calls = []
    rendezvous = Barrier(2)
    path = tmp_path / "application.sqlite3"
    records = {}

    def handler(security_context, _payload):
        calls.append(True)
        return {
            "operation_id": str(security_context.operation_id),
            "transaction_id": "TX-1",
        }

    gate, confirmations, records, _, _, _ = build_gate(
        path, clock=clock, handler=handler, records=records,
    )
    other_gate, other_confirmations, _, _, _, _ = build_gate(
        path, clock=clock, handler=handler, records=records,
    )
    descriptor = action()
    ready = ready_context(confirmations, records, context(), descriptor)
    run = executor(
        gate,
        {},
        parameter_resolver=lambda *_: (rendezvous.wait(), {"amount_fen": 50_000})[1],
    )

    def cancel():
        rendezvous.wait()
        try:
            other_confirmations.answer(
                ready,
                ConfirmationAnswer(
                    confirmation_id=ready.confirmation_id,
                    confirmation_version=ready.confirmation_version,
                    choice="cancel",
                ),
            )
            return "cancelled"
        except SecurityError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        execution_future = pool.submit(run.execute, ready, descriptor)
        cancel_future = pool.submit(cancel)
        outcome = execution_future.result()
        cancel_result = cancel_future.result()

    assert (outcome.executed, cancel_result, len(calls)) in {
        (True, "CONFIRMATION_CONFLICT", 1),
        (False, "cancelled", 0),
    }
    if not outcome.executed:
        assert outcome.decision.decision == SecurityDecisionCode.BLOCK


def test_abandoned_claim_not_found_never_redelivers_handler(tmp_path):
    clock = Clock()
    calls = []
    path = tmp_path / "application.sqlite3"

    def handler(security_context, _payload):
        calls.append(True)
        return {
            "operation_id": str(security_context.operation_id),
            "transaction_id": "TX-1",
        }

    gate, confirmations, records, _, _, _ = build_gate(
        path, clock=clock, handler=handler,
    )
    descriptor = action()
    ready = ready_context(confirmations, records, context(), descriptor)
    decision = gate.check_action(ready, descriptor)
    now = clock()
    confirmations.state.claim_execution(
        ready,
        descriptor,
        decision,
        now,
        lambda _context: False,
    )

    restarted_gate, _, restarted_records, _, _, _ = build_gate(
        path, clock=clock, handler=handler,
    )
    restarted_records.update(records)
    run = DeterministicExecutor(
        restarted_gate,
        parameter_resolver=lambda *_: {"amount_fen": 50_000},
        operation_lookup=lambda security_context, _action: OperationObservation(
            operation_id=security_context.operation_id,
            state="not_found",
            result=None,
            result_ref=None,
        ),
        result_observer=lambda result: OperationObservation(
            operation_id=UUID(result["operation_id"]),
            state="completed",
            result=result,
            result_ref=result["transaction_id"],
        ),
    )
    first_lookup = run.execute(ready, descriptor)
    assert first_lookup.reused and first_lookup.state == "unknown"
    assert calls == []

    clock.advance(hours=1)
    later_lookup = run.execute(ready, descriptor)
    assert later_lookup.reused and later_lookup.state == "unknown"
    assert calls == []


def test_handler_exception_becomes_unknown_and_replay_only_queries(tmp_path):
    clock = Clock()
    calls = []
    lookups = []

    def handler(_context, _payload):
        calls.append(True)
        raise TimeoutError("submission outcome unknown")

    path = tmp_path / "application.sqlite3"
    gate, confirmations, records, _, _, _ = build_gate(
        path, clock=clock, handler=handler,
    )
    ready = ready_context(confirmations, records, context(), action())

    def lookup(_context, _descriptor):
        lookups.append(True)
        return OperationObservation(
            operation_id=_context.operation_id,
            state="processing",
            result=None,
            result_ref=None,
        )

    run = DeterministicExecutor(
        gate,
        parameter_resolver=lambda *_: {"amount_fen": 50_000},
        operation_lookup=lookup,
        result_observer=lambda result: result,
    )
    first = run.execute(ready, action())
    replay = run.execute(ready, action())
    assert first.executed and first.state == "unknown"
    assert replay.reused and replay.state == "processing"
    assert calls == [True]
    assert lookups == [True]

    restarted_gate, _, restarted_records, _, _, _ = build_gate(
        path, clock=clock, handler=handler,
    )
    restarted_records.update(records)
    restarted = DeterministicExecutor(
        restarted_gate,
        parameter_resolver=lambda *_: (_ for _ in ()).throw(AssertionError()),
        operation_lookup=lookup,
        result_observer=lambda result: result,
    ).execute(ready, action())
    assert restarted.reused and restarted.state == "processing"
    assert calls == [True]
    assert lookups == [True, True]


def test_operation_lookup_rechecks_current_scope(tmp_path):
    clock = Clock()
    lookups = []

    def handler(security_context, _payload):
        return {
            "operation_id": str(security_context.operation_id),
            "transaction_id": "TX-1",
        }

    gate, confirmations, records, _, _, _ = build_gate(
        tmp_path / "application.sqlite3", clock=clock, handler=handler,
    )
    ready = ready_context(confirmations, records, context(), action())
    run = DeterministicExecutor(
        gate,
        parameter_resolver=lambda *_: {"amount_fen": 50_000},
        operation_lookup=lambda security_context, _action: (
            lookups.append(True),
            OperationObservation(
                operation_id=security_context.operation_id,
                state="completed",
                result={"transaction_id": "TX-1"},
                result_ref="TX-1",
            ),
        )[1],
        result_observer=lambda result: OperationObservation(
            operation_id=ready.operation_id,
            state="completed",
            result=result,
            result_ref=result["transaction_id"],
        ),
    )
    assert run.execute(ready, action()).executed

    gate.scope_authorizer = lambda *_: False
    denied = run.execute(ready, action())
    assert denied.decision.decision == SecurityDecisionCode.BLOCK
    assert denied.decision.reason_codes == ["ACCESS_DENIED"]
    assert denied.state == "unknown"
    assert denied.result is None and denied.result_ref is None
    assert lookups == []

    gate.scope_authorizer = lambda *_: (_ for _ in ()).throw(RuntimeError())
    paused = run.execute(ready, action())
    assert paused.decision.decision == SecurityDecisionCode.PAUSE
    assert paused.decision.reason_codes == ["DEPENDENCY_UNAVAILABLE"]
    assert paused.state == "unknown"
    assert paused.result is None and paused.result_ref is None
    assert lookups == []


def test_new_operation_supersedes_old_confirmation_and_same_id_cannot_change_content(tmp_path):
    clock = Clock()
    gate, confirmations, records, _, _, _ = build_gate(
        tmp_path / "application.sqlite3", clock=clock,
    )
    original = context()
    old_context, old_record = approved_confirmation(confirmations, original, action())
    new_context = original.model_copy(update={"operation_id": uuid4(), "action_revision": 2})
    replacement = confirmations.create(
        new_context, action("PARAM-2"),
        [DisplayField(name="amount", label="金额", value_text="600 元")],
    )
    assert replacement.confirmation_id == old_record.confirmation_id
    assert replacement.confirmation_version == old_record.confirmation_version + 1
    with pytest.raises(SecurityError, match="CONFIRMATION_STALE"):
        confirmations.answer(
            old_context,
            ConfirmationAnswer(
                confirmation_id=old_record.confirmation_id,
                confirmation_version=old_record.confirmation_version,
                choice="approve",
            ),
        )
    basic = verification(old_context)
    records[basic.verification_id] = basic
    denied = gate.check_action(
        old_context.model_copy(update={"verification_ids": [basic.verification_id]}), action(),
    )
    assert denied.decision != SecurityDecisionCode.ALLOW
    with pytest.raises(SecurityError, match="OPERATION_CONFLICT"):
        confirmations.create(
            new_context, action("PARAM-3"),
            [DisplayField(name="amount", label="金额", value_text="700 元")],
        )


def test_high_risk_termination_is_durable(tmp_path):
    path = tmp_path / "application.sqlite3"
    clock = Clock()
    high_gate, _, _, _, _, _ = build_gate(path, clock=clock, risk=RiskLevel.HIGH)
    original = context()
    assert high_gate.check_action(original, action()).reason_codes == ["HIGH_RISK"]
    low_gate, _, _, _, _, _ = build_gate(path, clock=clock, risk=RiskLevel.LOW)
    after_restart = low_gate.check_action(original, action())
    assert after_restart.decision == SecurityDecisionCode.BLOCK
    assert after_restart.reason_codes == ["TASK_TERMINATED"]


def test_executor_requires_execution_phase_and_rechecks_termination_before_claim(tmp_path):
    clock = Clock()
    calls = []
    gate, confirmations, records, decisions, _, _ = build_gate(
        tmp_path / "application.sqlite3", clock=clock,
        handler=lambda *_: calls.append(True),
    )
    ready = ready_context(confirmations, records, context(), action())
    terminated = [False]
    gate.task_state_resolver = lambda *_: terminated[0]

    def resolve_parameters(*_):
        terminated[0] = True
        return {"amount_fen": 50_000}

    run = executor(gate, {}, parameter_resolver=resolve_parameters)
    admission = run.execute(ready, action().model_copy(update={"phase": Phase.ADMISSION}))
    assert admission.decision.decision == SecurityDecisionCode.BLOCK
    assert calls == []
    stopped = run.execute(ready, action())
    assert stopped.decision.decision == SecurityDecisionCode.BLOCK
    assert stopped.decision.reason_codes == ["TASK_TERMINATED"]
    assert calls == []

    second = ready_context(
        confirmations, records, context(task_id="T2", operation_id=uuid4()), action(),
    )
    checks = [0]

    def terminate_at_claim(*_):
        checks[0] += 1
        return checks[0] == 3

    gate.task_state_resolver = terminate_at_claim
    at_claim = executor(
        gate, {}, parameter_resolver=lambda *_: {"amount_fen": 50_000},
    ).execute(second, action())
    assert checks == [3]
    assert at_claim.decision.reason_codes == ["TASK_TERMINATED"]
    assert calls == []

    third = ready_context(
        confirmations, records, context(task_id="T3", operation_id=uuid4()), action(),
    )
    checks = [0]

    def unavailable_at_claim(*_):
        checks[0] += 1
        return None if checks[0] == 3 else False

    gate.task_state_resolver = unavailable_at_claim
    paused = executor(
        gate, {}, parameter_resolver=lambda *_: {"amount_fen": 50_000},
    ).execute(third, action())
    assert paused.decision.decision == SecurityDecisionCode.PAUSE
    assert paused.decision.reason_codes == ["DEPENDENCY_UNAVAILABLE"]
    assert decisions[-1] == paused.decision
    assert calls == []


def test_mismatched_medium_risk_summary_cannot_authorize(tmp_path):
    clock = Clock()
    gate, confirmations, records, _, _, challenges = build_gate(
        tmp_path / "application.sqlite3", clock=clock, risk=RiskLevel.MEDIUM,
    )
    ready, _ = approved_confirmation(confirmations, context(), action())
    original_preparer = gate.verification_preparer

    def mismatched_summary(*args):
        challenge = original_preparer(*args)
        wrong = challenge.summary.model_copy(update={"amount_fen": 60_000})
        return challenge.model_copy(update={"summary": wrong})

    gate.verification_preparer = mismatched_summary
    refused = gate.check_action(ready, action())
    assert refused.decision != SecurityDecisionCode.ALLOW
    wrong_challenge = mismatched_summary(ready, action(), confirmations.get(ready, ready.confirmation_id), RiskLevel.MEDIUM)
    challenges[-1] = (wrong_challenge, challenges[-1][1], RiskLevel.MEDIUM)
    passed = verification(
        ready, scope="action", operation_id=ready.operation_id,
        action_revision=ready.action_revision, source_challenge_id=wrong_challenge.challenge_id,
    )
    records[passed.verification_id] = passed
    after_verification = gate.check_action(
        ready.model_copy(update={"verification_ids": [passed.verification_id]}), action(),
    )
    assert after_verification.decision != SecurityDecisionCode.ALLOW
