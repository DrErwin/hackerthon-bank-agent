"""Real recovery gaps; planner is the explicit platform test proposal only."""

from uuid import UUID

import pytest

from app.agent_platform.birthday_edit import BirthdayEditError
from app.agent_platform.test_birthday_harness_publication import (
    drive_to_freeze_confirmation, harness_env,
)
from app.agent_platform.test_birthday_runtime_wiring import approve_confirmation
from app.agent_platform.test_birthday_session_recovery import target_session
from app.agent_platform.test_cross_runtime_wiring import submitted_ledger_count
from app.contracts.common import Phase, SecurityDecisionCode
from app.contracts.security import ActionDescriptor
from app.security.gate import SecurityError

from .birthday import BirthdayFlow
from .test_cross_birthday_platform_edit import cross_state


def test_new_session_rebuilds_the_freeze_confirmation(harness_env):
    env = harness_env
    current = drive_to_freeze_confirmation(env)
    old = env.runtime.confirmations.get(
        env.runtime._context(env.who, None, None), current.interaction.record_ref)
    caller = target_session(env)

    recovered = env.runtime.harness.recover_session(caller)

    new = env.runtime.confirmations.get(
        env.runtime._context(caller, None, None), recovered.interaction.record_ref)
    assert new.session_id == caller.session_id
    assert new.confirmation_version > old.confirmation_version
    assert recovered.interaction.interaction_id != current.interaction.interaction_id
    assert submitted_ledger_count(env.runtime) == 0


def test_old_pending_release_cannot_be_granted_by_a_new_session(harness_env):
    """Diagnostic seam: a fresh card alone cannot migrate the old grant."""
    env = harness_env
    current = drive_to_freeze_confirmation(env)
    old_confirmation = env.runtime.confirmations.get(
        env.runtime._context(env.who, None, None), current.interaction.record_ref)
    approve_confirmation(env.runtime, env.who, current.interaction.record_ref)
    waiting = env.resume({"choice": "approve"})
    assert waiting.interaction.kind == "verification"
    original = env.snapshot()["birthday_actions"]["freeze"]
    operation_id = UUID(original["operation_id"])
    security_context = env.runtime._context(
        env.who, operation_id, original["action_revision"])
    descriptor = ActionDescriptor(
        action_name="bank.freeze_funds", parameters_ref=str(operation_id),
        resource_refs=[], phase=Phase.EXECUTION)
    security = env.runtime.birthday.state
    assert security.get_execution(security_context, descriptor) is None
    old_release_id = env.snapshot()["birthday_release"]
    old_release = security.get_release_authorization(security_context, old_release_id)
    assert old_release.status == "pending_freeze"
    assert old_release.session_id == "S1"
    old_challenge = env.runtime.gateway.get_verification(
        env.who, waiting.interaction.record_ref)
    assert old_challenge.code_result == "pending"
    plan = BirthdayFlow(None, cross_state(env), None)._plan()
    caller = target_session(env)
    # The unpatched consumer still returns its cached card; provider rejects it.
    with pytest.raises(BirthdayEditError, match="DEPENDENCY_UNAVAILABLE"):
        env.runtime.harness.recover_session(caller)

    # Probe only the public ports required by a corrected Cross recovery SOP.
    # No Cross checkpoint, security record or operation identity is rewritten.
    ports = env.runtime.birthday.ports_factory(caller)
    answer = ports.freeze_check(caller, plan)
    assert answer.decision is SecurityDecisionCode.REQUIRE_CONFIRMATION
    assert answer.operation_id == str(operation_id)
    new = env.runtime.confirmations.get(
        env.runtime._context(caller, None, None), answer.interaction.record_ref)
    assert new.session_id == "S2"
    assert new.confirmation_version > old_confirmation.confirmation_version
    approve_confirmation(env.runtime, caller, answer.interaction.record_ref)
    with pytest.raises(SecurityError, match="OPERATION_CONFLICT"):
        ports.grant_release(caller, plan, answer.interaction.record_ref)

    assert security.get_release_authorization(security_context, old_release_id) == old_release
    assert env.runtime.gateway.get_verification(env.who, old_challenge.challenge_id) == old_challenge
    assert security.get_execution(security_context, descriptor) is None
    assert submitted_ledger_count(env.runtime) == 0
