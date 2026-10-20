"""Scenario-05 security policy: registration, low-risk cancels, coercion blocks.

The policy keeps exactly two outcomes for a cancellation: coercion signals block the
task, and every ordinary own-account cancellation stays low risk (button + session-scoped
basic-identity code), so it can never fall into the medium ``action_step_up`` face path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.contracts.common import DisplayField, OperationLevel, Phase, RiskLevel, SecurityDecisionCode
from app.contracts.platform import TrustedContext
from app.contracts.security import (
    ActionDescriptor, ConfirmationAnswer, ExecutionSecurityContext, VerificationChallenge,
    VerificationRecord,
)
from app.modules.subscription.manifest import MANIFEST as SUBSCRIPTION_MANIFEST
from app.modules.subscription.reads import PRIVATE_TOOLS as SUBSCRIPTION_PRIVATE_TOOLS
from app.security import (
    ConfirmationService, DeterministicExecutor, OperationObservation, SecurityGate, ToolRegistry,
)
from app.security.demo_policy import DemoRiskEvidence, DemoRiskSignal, DemoSecurityPolicy
from app.security.gate import RiskFactsUnavailable

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)
CANCEL = next(item for item in SUBSCRIPTION_PRIVATE_TOOLS
              if item.name == "subscription.bank.cancel_subscription")
READ = next(item for item in SUBSCRIPTION_PRIVATE_TOOLS
            if item.name == "subscription.bank.list_subscriptions")
LOW_SIGNALS = (DemoRiskSignal.FAMILIAR_PAYEE, DemoRiskSignal.FAMILIAR_DEVICE,
               DemoRiskSignal.USUAL_AMOUNT_RANGE, DemoRiskSignal.CLEAR_REQUEST)


def policy_for(signals, *, checked=None):
    return DemoSecurityPolicy(
        demo_user_id="U1", admin_actor_id="ADMIN-1", current_demo_round=lambda: "D1",
        risk_facts=lambda *_: DemoRiskEvidence(
            source="server-demo-fixture", source_version="1", evidence_ref="sub-case-1",
            signals=frozenset(signals),
            checked_signals=frozenset(DemoRiskSignal if checked is None else checked)),
    )


def trusted() -> TrustedContext:
    return TrustedContext(user_id="U1", session_id="S1", demo_round_id="D1",
                          task_id="T1", run_id="R1", parent_task_id=None)


def security_context(**changes) -> ExecutionSecurityContext:
    values = {
        "user_id": "U1", "session_id": "S1", "demo_round_id": "D1", "task_id": "T1",
        "run_id": "R1", "source_task_id": None, "operation_id": uuid4(), "action_revision": 1,
        "confirmation_id": None, "confirmation_version": None, "verification_ids": [],
        "release_authorization_id": None,
    }
    values.update(changes)
    return ExecutionSecurityContext(**values)


def descriptor(name: str = CANCEL.name) -> ActionDescriptor:
    return ActionDescriptor(action_name=name, parameters_ref="P1", resource_refs=[], phase=Phase.EXECUTION)


def build_gate(
    tmp_path, current_policy, declaration, *, records=None, challenges=None,
    snapshot_writer=lambda *_: "AUTH-1", handler=lambda context, payload: payload,
):
    registry = ToolRegistry()
    registry.register(declaration, handler)
    confirmations = ConfirmationService(tmp_path / "subscription.sqlite3", clock=lambda: NOW)
    stored = records if records is not None else {}
    created = challenges if challenges is not None else []

    def prepare_confirmation(context, action):
        return confirmations.create(context, action, [
            DisplayField(name="merchant", label="退订项目", value_text="优酷视频（优酷 VIP 连续包月）"),
            DisplayField(name="notice", label="退订后果",
                         value_text="从下一期（2026-10-25）起不再自动扣费，之前已经扣掉的钱不退。"),
        ])

    def prepare_verification(context, action, confirmation, risk):
        step_up = risk == RiskLevel.MEDIUM
        challenge = VerificationChallenge(
            challenge_id=f"CH-{len(created) + 1}", user_id=context.user_id,
            session_id=context.session_id, demo_round_id=context.demo_round_id,
            task_id=context.task_id,
            purpose="action_step_up" if step_up else "basic_identity",
            operation_id=context.operation_id if step_up else None,
            action_revision=context.action_revision if step_up else None, summary=None,
            required_methods=["code", "mock_face"] if step_up else ["code"],
            created_at=NOW, code_created_at=NOW, code_expires_at=NOW + timedelta(minutes=5),
            face_started_at=None, face_expires_at=None, challenge_status="pending",
            code_result="pending", face_result="pending" if step_up else "not_required",
            consecutive_code_failures=0)
        created.append((challenge, confirmation, risk))
        return challenge

    def resolve(context, verification_id):
        record = stored[verification_id]
        if (record.user_id, record.session_id, record.demo_round_id) != (
                context.user_id, context.session_id, context.demo_round_id):
            raise PermissionError("ACCESS_DENIED")
        return record

    gate = SecurityGate(
        registry, confirmations,
        scope_authorizer=current_policy.authorize_tool,
        task_state_resolver=lambda *_: False,
        risk_assessor=current_policy.assess_risk,
        confirmation_preparer=prepare_confirmation,
        verification_preparer=prepare_verification,
        verification_resolver=resolve,
        challenge_resolver=lambda context, challenge_id: next(
            challenge.model_copy(update={"challenge_status": "passed"})
            for challenge, _, _ in created if challenge.challenge_id == challenge_id),
        decision_sink=lambda decision: None,
        snapshot_writer=snapshot_writer,
        summary_validator=lambda *_: False,
        clock=lambda: NOW,
    )
    return gate, confirmations, stored, created


def approve_created_confirmation(confirmations, context, descriptor, prompt):
    """Answer the very confirmation the gate prepared (a second create would conflict)."""

    record = confirmations.get(context, prompt)
    return context.model_copy(update={
        "confirmation_id": record.confirmation_id,
        "confirmation_version": record.confirmation_version,
    }), confirmations.answer(context, ConfirmationAnswer(
        confirmation_id=record.confirmation_id, confirmation_version=record.confirmation_version,
        choice="approve"))


def session_verification(context, *, session_id="S1"):
    return VerificationRecord(
        verification_id=str(uuid4()), user_id=context.user_id, session_id=session_id,
        demo_round_id=context.demo_round_id, scope="session", operation_id=None,
        action_revision=None, methods=["code"], verified_at=NOW, source_challenge_id="CH-1")


def test_scenario_05_permissions_capabilities_and_declarations_are_registered():
    current = policy_for(LOW_SIGNALS)
    for capability in SUBSCRIPTION_MANIFEST.capabilities:
        assert current.authorize_capability(trusted(), capability) is True
    assert current.authorize_tool(security_context(), descriptor(), CANCEL) is True
    assert current.authorize_tool(security_context(), descriptor(READ.name), READ) is True
    drifted = CANCEL.model_copy(update={"confirmation_policy": "none"})
    assert current.authorize_tool(security_context(), descriptor(), drifted) is False
    other_round = security_context(demo_round_id="D2")
    assert current.authorize_tool(other_round, descriptor(), CANCEL) is False


def test_missing_subscription_permission_denies_the_cancel(monkeypatch):
    current = policy_for(LOW_SIGNALS)
    assert DemoSecurityPolicy._permissions == frozenset({
        "transfer.start", "transfer.read", "transfer.submit", "bills.read",
        "subscription.read", "subscription.cancel"})
    monkeypatch.setattr(
        DemoSecurityPolicy, "_permissions",
        frozenset({"transfer.start", "transfer.read", "transfer.submit", "bills.read"}),
    )
    assert current.authorize_tool(security_context(), descriptor(), CANCEL) is False
    # The capability admission is the only gate left when a module widens its own
    # manifest, so it must deny a capability whose permission is missing.
    assert current.authorize_capability(trusted(), SUBSCRIPTION_MANIFEST.capabilities[1]) is False
    assert current.authorize_capability(trusted(), SUBSCRIPTION_MANIFEST.capabilities[0]) is False
    read_only = frozenset({"transfer.start", "transfer.read", "transfer.submit", "bills.read",
                           "subscription.read"})
    monkeypatch.setattr(DemoSecurityPolicy, "_permissions", read_only)
    assert current.authorize_tool(security_context(), descriptor(), CANCEL) is False
    assert current.authorize_tool(security_context(), descriptor(READ.name), READ) is True
    assert current.authorize_capability(trusted(), SUBSCRIPTION_MANIFEST.capabilities[0]) is True
    assert current.authorize_capability(trusted(), SUBSCRIPTION_MANIFEST.capabilities[1]) is False
    monkeypatch.setattr(
        DemoSecurityPolicy, "_permissions",
        frozenset({*read_only, "subscription.cancel", "admin.all"}),
    )
    assert current.authorize_capability(trusted(), SUBSCRIPTION_MANIFEST.capabilities[1]) is True


def test_ordinary_cancel_is_low_risk_and_never_asks_for_a_face(tmp_path):
    current = policy_for(LOW_SIGNALS)
    gate, confirmations, records, challenges = build_gate(tmp_path, current, CANCEL)
    context = security_context()
    first = gate.check_action(context, descriptor())
    assert first.decision == SecurityDecisionCode.REQUIRE_CONFIRMATION
    assert first.risk_level == RiskLevel.LOW and "demo-risk-low" in first.rule_ids
    assert first.interaction.kind == "confirmation" and first.interaction.record_ref

    confirmed, approved = approve_created_confirmation(
        confirmations, context, descriptor(), first.interaction.record_ref)
    assert approved.decision == "approved"
    second = gate.check_action(confirmed, descriptor())
    assert second.decision == SecurityDecisionCode.REQUIRE_VERIFICATION
    assert second.interaction.kind == "verification"
    challenge = challenges[-1][0]
    assert challenge.purpose == "basic_identity" and challenge.required_methods == ["code"]
    assert challenge.face_result == "not_required" and challenge.summary is None

    basic = session_verification(confirmed)
    records[basic.verification_id] = basic
    allowed = gate.check_action(
        confirmed.model_copy(update={"verification_ids": [basic.verification_id]}), descriptor())
    assert allowed.decision == SecurityDecisionCode.ALLOW
    assert allowed.authorization_snapshot_ref == "AUTH-1"


def test_cancel_executor_writes_snapshot_before_bank_submit(tmp_path):
    events = []

    def write_snapshot(*args):
        events.append("snapshot")
        return "AUTH-1"

    def submit(context, payload):
        events.append("bank")
        return {"operation_id": str(context.operation_id), "receipt": "R1"}

    current = policy_for(LOW_SIGNALS)
    gate, confirmations, records, _ = build_gate(
        tmp_path, current, CANCEL, snapshot_writer=write_snapshot, handler=submit)
    context = security_context()
    first = gate.check_action(context, descriptor())
    confirmed, _ = approve_created_confirmation(
        confirmations, context, descriptor(), first.interaction.record_ref)
    basic = session_verification(confirmed)
    records[basic.verification_id] = basic
    ready = confirmed.model_copy(update={"verification_ids": [basic.verification_id]})
    executor = DeterministicExecutor(
        gate, parameter_resolver=lambda *_: {"mandate_id": "M1"},
        operation_lookup=lambda *_: None,
        result_observer=lambda result: OperationObservation(
            operation_id=ready.operation_id, state="completed", result=result, result_ref="R1"),
    )

    outcome = executor.execute(ready, descriptor())
    assert outcome.executed and outcome.decision.authorization_snapshot_ref == "AUTH-1"
    assert events[-1] == "bank" and events[:-1] == ["snapshot", "snapshot"]


def test_cancel_snapshot_failure_pauses_before_execution(tmp_path):
    current = policy_for(LOW_SIGNALS)
    submissions = []

    def unavailable_snapshot(*args):
        raise OSError("snapshot store unavailable")

    gate, confirmations, records, _ = build_gate(
        tmp_path, current, CANCEL, snapshot_writer=unavailable_snapshot,
        handler=lambda *_: submissions.append(True))
    context = security_context()
    first = gate.check_action(context, descriptor())
    confirmed, _ = approve_created_confirmation(
        confirmations, context, descriptor(), first.interaction.record_ref)
    basic = session_verification(confirmed)
    records[basic.verification_id] = basic

    executor = DeterministicExecutor(
        gate, parameter_resolver=lambda *_: {"mandate_id": "M1"},
        operation_lookup=lambda *_: None, result_observer=lambda *_: None)
    outcome = executor.execute(
        confirmed.model_copy(update={"verification_ids": [basic.verification_id]}), descriptor())
    assert not outcome.executed and submissions == []
    assert outcome.decision.decision == SecurityDecisionCode.PAUSE
    assert outcome.decision.reason_codes == ["AUDIT_UNAVAILABLE"]
    assert outcome.decision.authorization_snapshot_ref is None


def test_transfer_medium_signals_never_escalate_a_cancel_to_step_up(tmp_path):
    current = policy_for([DemoRiskSignal.NEW_PAYEE, DemoRiskSignal.UNUSUAL_AMOUNT])
    assert current.assess_risk(security_context(), descriptor(), CANCEL).risk_level == RiskLevel.LOW
    gate, confirmations, records, challenges = build_gate(tmp_path, current, CANCEL)
    context = security_context()
    first = gate.check_action(context, descriptor())
    assert first.decision == SecurityDecisionCode.REQUIRE_CONFIRMATION
    assert first.risk_level == RiskLevel.LOW and "demo-risk-low" in first.rule_ids
    confirmed, _ = approve_created_confirmation(
        confirmations, context, descriptor(), first.interaction.record_ref)
    assert gate.check_action(confirmed, descriptor()).decision == SecurityDecisionCode.REQUIRE_VERIFICATION
    challenge = challenges[-1][0]
    assert challenge.purpose == "basic_identity" and challenge.required_methods == ["code"]
    assert challenge.face_result == "not_required" and challenge.summary is None
    basic = session_verification(confirmed)
    records[basic.verification_id] = basic
    assert gate.check_action(
        confirmed.model_copy(update={"verification_ids": [basic.verification_id]}), descriptor(),
    ).decision == SecurityDecisionCode.ALLOW


def test_coercion_signals_block_the_cancel_even_after_confirmation(tmp_path):
    current = policy_for([DemoRiskSignal.SCREEN_SHARING])
    assessment = current.assess_risk(security_context(), descriptor(), CANCEL)
    assert assessment.risk_level == RiskLevel.HIGH and assessment.rule_id == "demo-risk-high"
    # The user's own answered confirmation is prepared first: a coercion block must
    # outrank it, not merely ride on an already-terminated task.
    gate, confirmations, _, _ = build_gate(tmp_path, current, CANCEL)
    context = security_context()
    record = confirmations.create(context, descriptor(),
                                  [DisplayField(name="notice", label="退订后果", value_text="不退已扣的钱")])
    approved = confirmations.answer(context, ConfirmationAnswer(
        confirmation_id=record.confirmation_id, confirmation_version=record.confirmation_version,
        choice="approve"))
    answered = context.model_copy(update={"confirmation_id": approved.confirmation_id,
                                          "confirmation_version": approved.confirmation_version})
    blocked = gate.check_action(answered, descriptor())
    assert blocked.decision == SecurityDecisionCode.BLOCK
    assert blocked.reason_codes == ["HIGH_RISK"]
    assert blocked.risk_level == RiskLevel.HIGH


def test_the_same_session_can_reuse_its_basic_identity_verification(tmp_path):
    """A second cancellation in one session reuses the record; only the confirmation is new."""

    current = policy_for(LOW_SIGNALS)
    gate, confirmations, records, challenges = build_gate(tmp_path, current, CANCEL)
    first_context = security_context()
    first = gate.check_action(first_context, descriptor())
    first_confirmed, _ = approve_created_confirmation(
        confirmations, first_context, descriptor(), first.interaction.record_ref)
    basic = session_verification(first_confirmed)
    records[basic.verification_id] = basic
    assert gate.check_action(
        first_confirmed.model_copy(update={"verification_ids": [basic.verification_id]}),
        descriptor()).decision == SecurityDecisionCode.ALLOW

    second_context = security_context(operation_id=uuid4(), action_revision=2)
    second_descriptor = ActionDescriptor(action_name=CANCEL.name, parameters_ref="P2",
                                         resource_refs=[], phase=Phase.EXECUTION)
    second = gate.check_action(second_context, second_descriptor)
    assert second.decision == SecurityDecisionCode.REQUIRE_CONFIRMATION
    second_confirmed, _ = approve_created_confirmation(
        confirmations, second_context, second_descriptor, second.interaction.record_ref)
    assert len(challenges) == 0  # no new challenge was needed for the second cancellation
    assert gate.check_action(
        second_confirmed.model_copy(update={"verification_ids": [basic.verification_id]}),
        second_descriptor).decision == SecurityDecisionCode.ALLOW


def test_incomplete_risk_evidence_fails_closed():
    current = policy_for([DemoRiskSignal.SCREEN_SHARING], checked=[DemoRiskSignal.SCREEN_SHARING])
    with pytest.raises(RiskFactsUnavailable):
        current.assess_risk(security_context(), descriptor(), CANCEL)
    out_of_scope = policy_for(LOW_SIGNALS)
    with pytest.raises(RiskFactsUnavailable):
        out_of_scope.assess_risk(security_context(user_id="U9"), descriptor(), CANCEL)


def test_read_capability_is_allowed_without_any_extra_step(tmp_path):
    current = policy_for(LOW_SIGNALS)
    gate, _, _, _ = build_gate(tmp_path, current, READ)
    context = security_context(operation_id=None, action_revision=None)
    allowed = gate.check_action(context, descriptor(READ.name))
    assert allowed.decision == SecurityDecisionCode.ALLOW
    assert allowed.authorization_snapshot_ref is None


def test_unregistered_write_declaration_is_out_of_the_policy_scope():
    current = policy_for(LOW_SIGNALS)
    stranger = CANCEL.model_copy(update={"name": "subscription.bank.forge_mandate",
                                         "operation_level": OperationLevel.MODIFY})
    assert current.authorize_tool(security_context(), descriptor(stranger.name), stranger) is False
    with pytest.raises(RiskFactsUnavailable):
        current.assess_risk(security_context(), descriptor(stranger.name), stranger)
