from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest

from app.contracts.common import Phase, RiskLevel
from app.contracts.platform import TrustedContext
from app.contracts.security import ActionDescriptor, ExecutionSecurityContext
from app.modules.transfer.manifest import MANIFEST, PRIVATE_TOOLS
from app.services.mock_bank.verification import AdminContext
from app.security.demo_policy import (
    DemoRiskEvidence,
    DemoRiskSignal,
    DemoSecurityPolicy,
    RiskFactsUnavailable,
)


ROUND = "demo-round-1"
USER = "demo-user-1"
ADMIN = "demo-admin-1"


def make_policy(risk_facts: Callable):
    current_round = [ROUND]
    policy = DemoSecurityPolicy(
        demo_user_id=USER,
        admin_actor_id=ADMIN,
        current_demo_round=lambda: current_round[0],
        risk_facts=risk_facts,
    )
    return policy, current_round


def execution_context(*, user_id=USER, demo_round_id=ROUND):
    return ExecutionSecurityContext(
        user_id=user_id,
        session_id="session-1",
        demo_round_id=demo_round_id,
        task_id="task-1",
        run_id="run-1",
        source_task_id=None,
        operation_id=None,
        action_revision=None,
        confirmation_id=None,
        confirmation_version=None,
        verification_ids=[],
        release_authorization_id=None,
    )


def action_for(name: str):
    return ActionDescriptor(
        action_name=name,
        parameters_ref="params-1",
        resource_refs=[],
        phase=Phase.EXECUTION,
    )


def evidence(*signals: DemoRiskSignal, checked=None):
    return DemoRiskEvidence(
        source="server-demo-fixture",
        source_version="1",
        evidence_ref="fixture:task-1",
        signals=frozenset(signals),
        checked_signals=(
            frozenset(DemoRiskSignal) if checked is None else frozenset(checked)
        ),
    )


def test_all_declared_transfer_tools_are_checked_and_undeclared_tools_fail_closed():
    policy, _ = make_policy(lambda *_: evidence(
        DemoRiskSignal.FAMILIAR_PAYEE,
        DemoRiskSignal.FAMILIAR_DEVICE,
        DemoRiskSignal.USUAL_AMOUNT_RANGE,
        DemoRiskSignal.CLEAR_REQUEST,
    ))
    context = execution_context()

    for declaration in PRIVATE_TOOLS:
        assert policy.authorize_tool(context, action_for(declaration.name), declaration)
        missing_permission = declaration.model_copy(update={"required_permissions": []})
        assert not policy.authorize_tool(context, action_for(declaration.name), missing_permission)

    unknown = PRIVATE_TOOLS[0].model_copy(update={"name": "bank.unknown"})
    assert not policy.authorize_tool(context, action_for(unknown.name), unknown)
    assert not policy.authorize_tool(context, action_for("bank.list_accounts"), PRIVATE_TOOLS[-1])


def test_public_capability_requires_the_fixed_user_current_round_and_declaration():
    policy, current_round = make_policy(lambda *_: evidence())
    declaration = MANIFEST.capabilities[0]
    context = TrustedContext(
        user_id=USER,
        session_id="session-1",
        task_id="task-1",
        run_id="run-1",
        parent_task_id=None,
        demo_round_id=ROUND,
    )

    assert policy.authorize_capability(context, declaration)
    assert not policy.authorize_capability(
        context.model_copy(update={"user_id": "other-user"}), declaration,
    )
    assert not policy.authorize_capability(
        context.model_copy(update={"demo_round_id": "old-round"}), declaration,
    )
    current_round[0] = "next-round"
    assert not policy.authorize_capability(context, declaration)
    assert not policy.authorize_capability(
        context, declaration.model_copy(update={"required_permissions": []}),
    )
    assert not policy.authorize_capability(
        context, declaration.model_copy(update={"name": "transfer.unknown"}),
    )


def test_admin_face_authorization_uses_a_separate_configured_admin_identity():
    policy, _ = make_policy(lambda *_: evidence())
    allowed = AdminContext(ADMIN, True, ROUND, USER)

    assert policy.authorize_face(allowed, "challenge-1", uuid4(), "passed")
    assert not policy.authorize_face(
        AdminContext(USER, True, ROUND, USER), "challenge-1", uuid4(), "passed",
    )
    assert not policy.authorize_face(
        AdminContext(ADMIN, False, ROUND, USER), "challenge-1", uuid4(), "passed",
    )
    assert not policy.authorize_face(
        AdminContext(ADMIN, True, "old-round", USER), "challenge-1", uuid4(), "passed",
    )
    assert not policy.authorize_face(
        AdminContext(ADMIN, True, ROUND, "other-user"), "challenge-1", uuid4(), "passed",
    )


@pytest.mark.parametrize(
    ("signals", "expected", "rule_id"),
    [
        ((DemoRiskSignal.FAMILIAR_PAYEE, DemoRiskSignal.FAMILIAR_DEVICE,
          DemoRiskSignal.USUAL_AMOUNT_RANGE, DemoRiskSignal.CLEAR_REQUEST), RiskLevel.LOW, "demo-risk-low"),
        ((DemoRiskSignal.NEW_PAYEE,), RiskLevel.MEDIUM, "demo-risk-medium"),
        ((DemoRiskSignal.SCREEN_SHARING,), RiskLevel.HIGH, "demo-risk-high"),
        ((DemoRiskSignal.NEW_PAYEE, DemoRiskSignal.CREDENTIAL_REQUEST), RiskLevel.HIGH, "demo-risk-high"),
    ],
)
def test_trusted_prd_signals_have_repeatable_risk_classification(signals, expected, rule_id):
    policy, _ = make_policy(lambda *_: evidence(*signals))
    declaration = PRIVATE_TOOLS[-1]

    assessment = policy.assess_risk(
        execution_context(), action_for(declaration.name), declaration,
    )
    assert assessment.risk_level == expected
    assert assessment.policy_version == policy.policy_version
    assert assessment.rule_id == rule_id
    assert assessment.evidence_ref == "server-demo-fixture:1:fixture:task-1"


def test_missing_facts_and_out_of_scope_actions_do_not_default_to_low_risk():
    source_calls = []

    def no_facts(*args):
        source_calls.append(args)
        return evidence()

    policy, _ = make_policy(no_facts)
    declaration = PRIVATE_TOOLS[-1]
    context = execution_context()

    with pytest.raises(RiskFactsUnavailable, match="incomplete"):
        policy.assess_risk(context, action_for(declaration.name), declaration)

    with pytest.raises(RiskFactsUnavailable, match="authorized demo scope"):
        policy.assess_risk(
            execution_context(user_id="other-user"), action_for(declaration.name), declaration,
        )
    assert len(source_calls) == 1


def test_risk_evidence_requires_known_signals_and_a_provenance_reference():
    with pytest.raises(ValueError, match="source, version, and reference"):
        DemoRiskEvidence("source", "version", "", frozenset(), frozenset())
    with pytest.raises(ValueError, match="known server-side signals"):
        DemoRiskEvidence(
            "source", "version", "evidence-1", frozenset({"low"}), frozenset({"low"}),
        )
    with pytest.raises(ValueError, match="covered by checked dimensions"):
        DemoRiskEvidence(
            "source", "version", "evidence-1",
            frozenset({DemoRiskSignal.NEW_PAYEE}), frozenset(),
        )


def test_partial_risk_signal_coverage_is_not_enough_to_continue():
    policy, _ = make_policy(lambda *_: evidence(
        DemoRiskSignal.NEW_PAYEE, checked={DemoRiskSignal.NEW_PAYEE},
    ))
    declaration = PRIVATE_TOOLS[-1]

    with pytest.raises(RiskFactsUnavailable, match="does not cover every signal dimension"):
        policy.assess_risk(
            execution_context(), action_for(declaration.name), declaration,
        )


def test_unavailable_current_round_fails_closed():
    policy = DemoSecurityPolicy(
        demo_user_id=USER,
        admin_actor_id=ADMIN,
        current_demo_round=lambda: (_ for _ in ()).throw(RuntimeError("unavailable")),
        risk_facts=lambda *_: evidence(),
    )

    assert not policy.authorize_tool(
        execution_context(), action_for(PRIVATE_TOOLS[0].name), PRIVATE_TOOLS[0],
    )


def test_admin_identity_must_be_separate_from_demo_user():
    with pytest.raises(ValueError, match="must be separate"):
        DemoSecurityPolicy(
            demo_user_id=USER,
            admin_actor_id=USER,
            current_demo_round=lambda: ROUND,
            risk_facts=lambda *_: evidence(),
        )
