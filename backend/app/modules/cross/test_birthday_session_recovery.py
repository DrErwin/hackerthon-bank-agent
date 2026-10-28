"""Cross09: real Harness/gate/bank recovery; the planner is an explicit stub.

The original 1-fail/1-pass probe is archived unchanged in this ticket's evidence.
The old pending grant may not be rebound: G2 now proves retirement and links a
new attempt before Cross rebuilds its own confirmation/verification wait.
"""

import pytest
from unittest.mock import Mock
from uuid import uuid4

from app.agent_platform.test_birthday_harness_publication import (
    drive_to_freeze_confirmation, harness_env,
)
from app.agent_platform.test_birthday_runtime_wiring import (
    answer_verification, approve_confirmation,
)
from app.agent_platform.test_birthday_session_recovery import target_session
from app.contracts.common import TaskStatus
from app.contracts.bank import OperationNotFound
from app.memory.adapter import MemoryContext


def cross_state(env):
    ref = env.published_ref()
    saver = env.runtime.memory.checkpointer(MemoryContext(
        env.who.user_id, env.who.session_id, env.who.demo_round_id), env.who.task_id)
    saved = saver.get_tuple({"configurable": {
        "thread_id": ref["thread_id"], "checkpoint_ns": ref["checkpoint_ns"],
        "checkpoint_id": ref["checkpoint_id"],
    }})
    return saved.checkpoint["channel_values"]["cross_state"]


STAGES = ("freeze_confirmation", "freeze_verification", "order_confirmation",
          "order_verification", "capture_confirmation", "capture_verification")


def settle(env, card):
    approve_confirmation(env.runtime, env.who, card.interaction.record_ref)
    waiting = env.resume({"choice": "approve"})
    assert waiting.interaction.kind == "verification", waiting.message
    answer_verification(env.runtime, env.who, "R1", waiting.interaction.record_ref)
    return env.resume({"choice": "resume"})


def waiting_at(env, stage):
    current = drive_to_freeze_confirmation(env)
    for _ in range(STAGES.index(stage) // 2):
        current = settle(env, current)
    original = env.runtime.confirmations.get(
        env.runtime._context(env.who, None, None), current.interaction.record_ref)
    if stage.endswith("verification"):
        approve_confirmation(env.runtime, env.who, current.interaction.record_ref)
        current = env.resume({"choice": "approve"})
        assert current.interaction.kind == "verification"
    return current, original


@pytest.mark.parametrize("stage", STAGES)
def test_new_session_reconfirms_then_verifies_and_executes_once(harness_env, stage):
    env = harness_env
    old_card, original = waiting_at(env, stage)
    original_orders = cross_state(env)["birthday"]["orders"]
    caller = target_session(env)

    recovered = env.runtime.harness.recover_session(caller)

    assert recovered.interaction.kind == "confirmation", recovered.message
    assert recovered.interaction.interaction_id != old_card.interaction.interaction_id
    current = env.runtime.confirmations.get(
        env.runtime._context(caller, None, None), recovered.interaction.record_ref)
    assert current.session_id == caller.session_id
    assert current.confirmation_version > original.confirmation_version
    assert current.operation_id != original.operation_id
    assert current.action_name == original.action_name
    assert current.decision == "pending"
    env.who = caller
    assert cross_state(env)["birthday"]["orders"] == original_orders
    assert isinstance(env.runtime.gateway.get_operation(caller, original.operation_id),
                      OperationNotFound)

    card = recovered
    for _ in range(6):
        if card.interaction is None or card.interaction.kind != "confirmation":
            break
        card = settle(env, card)
    assert card.status is TaskStatus.SUCCEEDED, card.message
    facts = cross_state(env)["birthday"]
    assert facts["freeze"]["status"] == "completed"
    assert [row["capture"] for row in facts["orders"]] == ["completed", "completed"]
    assert len({row["order_id"] for row in facts["orders"]}) == 2
    assert len({row["transaction_id"] for row in facts["orders"]}) == 2
    assert isinstance(env.runtime.gateway.get_operation(caller, original.operation_id),
                      OperationNotFound)


@pytest.mark.parametrize("kind", ["freeze", "order", "capture"])
@pytest.mark.parametrize("response_loss", [False, True])
def test_committed_write_is_observed_without_repeating_or_advancing(
    harness_env, kind, response_loss, monkeypatch,
):
    """Real effect before the Cross checkpoint: never call a writer on recovery."""
    from copy import deepcopy
    from .birthday import BirthdayFlow
    from .test_cross_birthday_platform_edit import bank_orders, paid_amounts

    env = harness_env
    card, original = waiting_at(env, kind + "_verification")
    answer_verification(env.runtime, env.who, "R1", card.interaction.record_ref)
    state = cross_state(env)
    flow = BirthdayFlow(None, state, None)
    target = flow.b["pending"]["target"]
    ports = env.runtime.birthday.ports_factory(env.who)
    if response_loss:
        env.runtime.bank.birthday.arm_response_loss(env.who.user_id)
    if kind == "freeze":
        done = ports.freeze_execute(env.who, flow._plan())
        if not response_loss:
            assert ports.bind_freeze(env.who, flow._plan(), str(original.operation_id))
    elif kind == "order":
        done = ports.order_execute(env.who, flow._plan(), flow._order(target[1]))
    else:
        item = flow._order(target[1])
        done = ports.capture_execute(env.who, flow._plan(), item, item["order_id"])
    assert done.state == ("unknown" if response_loss else "completed")
    bank_fact = env.runtime.gateway.get_operation(env.who, original.operation_id)
    orders, paid = bank_orders(env.runtime), paid_amounts(env)
    plan_before = deepcopy(flow.b["orders"])
    caller = target_session(env)
    for method in ("freeze_funds", "create_order", "capture_frozen", "release_frozen"):
        monkeypatch.setattr(env.runtime.gateway, method, Mock(
            side_effect=AssertionError("RECOVERY_MUST_ONLY_QUERY_THE_ORIGINAL")))

    recovered = env.runtime.harness.recover_session(caller)

    env.who = caller
    assert recovered.status is TaskStatus.WAITING_INPUT, recovered.message
    assert recovered.interaction.kind == "input"
    assert "只核实原操作" in recovered.message
    assert cross_state(env)["birthday"]["pending"] is None
    for _ in range(2):
        from app.agent_platform.test_birthday_runtime_wiring import option_id
        recovered = env.resume({"selected_option_id": option_id(recovered, "核实原操作")})
        assert recovered.interaction.kind == "input"
    assert env.runtime.gateway.get_operation(caller, original.operation_id) == bank_fact
    assert bank_orders(env.runtime) == orders
    assert paid_amounts(env) == paid
    rows = cross_state(env)["birthday"]["orders"]
    for before, after in zip(plan_before, rows):
        if before.get("capture") == "completed":
            assert after == before
    assert not any(row.get("order_operation_id") not in
                   {str(original.operation_id), before.get("order_operation_id")}
                   for before, row in zip(plan_before, rows))


@pytest.mark.parametrize("claim_state", ["processing", "unknown", "completed"])
def test_claim_without_bank_receipt_stays_unknown(harness_env, monkeypatch, claim_state):
    """Explicit claim-state fault, not a synthetic success or bank receipt."""
    from types import SimpleNamespace
    from app.contracts.common import Phase
    from app.contracts.security import ActionDescriptor
    from app.security.test_retirement import insert_claim_row

    env = harness_env
    _, original = waiting_at(env, "freeze_verification")
    context = env.runtime._context(env.who, original.operation_id, original.action_revision)
    descriptor = ActionDescriptor(action_name=original.action_name,
        parameters_ref=str(original.operation_id), resource_refs=[], phase=Phase.EXECUTION)
    insert_claim_row(SimpleNamespace(path=env.runtime.application.path), context,
                     descriptor, claim_state)
    caller = target_session(env)
    for method in ("freeze_funds", "create_order", "capture_frozen", "release_frozen"):
        monkeypatch.setattr(env.runtime.gateway, method, Mock(
            side_effect=AssertionError("A_CLAIM_IS_NEVER_A_NEW_ATTEMPT")))

    recovered = env.runtime.harness.recover_session(caller)

    env.who = caller
    assert recovered.status is TaskStatus.WAITING_INPUT
    assert "结果仍待核实" in recovered.message
    assert recovered.interaction.kind == "input"
    assert isinstance(env.runtime.gateway.get_operation(caller, original.operation_id),
                      OperationNotFound)
    assert cross_state(env)["birthday"]["freeze"]["operation_id"] == str(original.operation_id)
    assert cross_state(env)["birthday"]["freeze"]["status"] == "unknown"


@pytest.mark.parametrize("stage", ["freeze_verification", "capture_verification"])
def test_old_callbacks_and_old_session_cannot_approve_the_new_wait(harness_env, stage):
    from app.contracts.security import ConfirmationAnswer
    from app.services.mock_bank.verification import ChallengeRetired

    env = harness_env
    old_card, original = waiting_at(env, stage)
    old_who = env.who
    old_code = env.runtime.gateway.get_demo_code_for_api(old_who, old_card.interaction.record_ref)
    caller = target_session(env)
    recovered = env.runtime.harness.recover_session(caller)
    env.who = caller
    original_result = recovered.model_dump(mode="json")
    before = cross_state(env)["birthday"]
    with pytest.raises(ChallengeRetired):
        env.runtime.gateway.verify_code(old_who, old_card.interaction.record_ref, uuid4(), old_code)
    with pytest.raises(PermissionError, match="ACCESS_DENIED"):
        env.runtime.answer_confirmation(old_who, ConfirmationAnswer(
            confirmation_id=original.confirmation_id,
            confirmation_version=original.confirmation_version, choice="approve"))
    with pytest.raises(PermissionError, match="ACCESS_DENIED"):
        env.runtime.harness.resume(old_who, {"choice": "resume"}, request_id=uuid4())
    with pytest.raises(ValueError, match="INTERACTION_STALE"):
        env.resume({"choice": "approve", "interaction_id": old_card.interaction.interaction_id})
    replayed = env.runtime.harness.recover_session(caller.model_copy(update={"run_id": str(uuid4())}))
    assert replayed.model_dump(mode="json") == {**original_result, "run_id": replayed.run_id}
    assert cross_state(env)["birthday"] == before


@pytest.mark.parametrize("kind", ["freeze", "order", "capture"])
def test_unknown_already_checkpointed_in_old_session_still_only_observes(harness_env, kind):
    from app.agent_platform.test_birthday_runtime_wiring import option_id

    env = harness_env
    waiting, original = waiting_at(env, kind + "_verification")
    answer_verification(env.runtime, env.who, "R1", waiting.interaction.record_ref)
    env.runtime.bank.birthday.arm_response_loss(env.who.user_id)
    old_menu = env.resume({"choice": "resume"})
    assert old_menu.status is TaskStatus.WAITING_INPUT
    caller = target_session(env)
    recovered = env.runtime.harness.recover_session(caller)
    env.who = caller

    queried = env.resume({"selected_option_id": option_id(recovered, "核实原操作")})

    assert queried.status is TaskStatus.WAITING_INPUT
    assert queried.interaction.kind == "input"
    assert "只核实原操作" in queried.message
    observed = cross_state(env)["birthday"]["session_observation"]
    assert observed["operation_id"] == str(original.operation_id)
    assert observed["status"] == "completed"
