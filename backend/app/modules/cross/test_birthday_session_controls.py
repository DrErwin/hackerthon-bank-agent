"""Cross09 continuation/restart and controls on the real local composition."""

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from app.agent_platform.local_demo import build_runtime
from app.agent_platform.test_birthday_harness_publication import harness_env
from app.agent_platform.test_birthday_runtime_wiring import (
    NoopModel, approve_confirmation, option_id,
)
from app.agent_platform.test_birthday_session_recovery import target_session
from app.agent_platform.test_local_demo import configuration
from app.contracts.common import TaskStatus

from app.modules.cross.entry import CrossEntry
from .test_birthday_session_recovery import cross_state, settle, waiting_at
from .test_cross_birthday_platform_edit import bank_orders, begin_edit, paid_amounts


def restart(env):
    directory = env.runtime.application.path.parent
    env.runtime.gateway.close()
    with patch("app.agent_platform.local_demo.ChatOpenAI",
               return_value=NoopModel(response_mode="none")):
        env.runtime = build_runtime(configuration(directory))


@pytest.mark.parametrize("after_save", [False, True])
@pytest.mark.parametrize("stage", ["freeze_verification", "capture_verification"])
def test_interrupted_cross_recovery_restarts_with_one_attempt(harness_env, monkeypatch, stage, after_save):
    env = harness_env
    _, original = waiting_at(env, stage)
    caller = target_session(env)
    save = CrossEntry._save
    seen_operations = []

    def interrupted(entry, context, thread_id, state):
        pending = (state.get("birthday") or {}).get("pending") or {}
        if context.session_id == caller.session_id and pending.get("operation_id"):
            seen_operations.append(pending["operation_id"])
            if len(seen_operations) == 1:
                if after_save:
                    save(entry, context, thread_id, state)
                raise OSError("cross recovery interrupted")
        return save(entry, context, thread_id, state)

    monkeypatch.setattr(CrossEntry, "_save", interrupted)
    with pytest.raises(OSError, match="cross recovery interrupted"):
        env.runtime.harness.recover_session(caller)
    restart(env)
    try:
        recovered = env.runtime.harness.recover_session(caller.model_copy(update={"run_id": str(uuid4())}))
        env.who = caller
        assert recovered.interaction.kind == "confirmation", recovered.message
        confirmation = env.runtime.confirmations.get(
            env.runtime._context(caller, None, None), recovered.interaction.record_ref)
        assert str(confirmation.operation_id) == seen_operations[0]
        assert confirmation.operation_id != original.operation_id
        replayed = env.runtime.harness.recover_session(caller.model_copy(update={"run_id": str(uuid4())}))
        assert replayed.interaction == recovered.interaction
        next_card = settle(env, replayed)
        assert next_card.interaction.kind == "confirmation", next_card.message
        next_confirmation = env.runtime.confirmations.get(
            env.runtime._context(caller, None, None), next_card.interaction.record_ref)
        assert next_confirmation.operation_id != confirmation.operation_id
        assert set(seen_operations[:2]) == {str(confirmation.operation_id)}
    finally:
        env.runtime.gateway.close()


@pytest.mark.parametrize("stage", ["freeze_confirmation", "order_confirmation"])
def test_recovered_wait_can_edit_without_accepting_either_old_card(harness_env, stage):
    env = harness_env
    old_card, _ = waiting_at(env, stage)
    caller = target_session(env)
    recovered = env.runtime.harness.recover_session(caller)
    env.who = caller
    orders, paid = bank_orders(env.runtime), paid_amounts(env)
    edited = begin_edit(env, recovered).result
    assert edited.interaction.kind == "input"
    assert edited.interaction.interaction_id not in {
        old_card.interaction.interaction_id, recovered.interaction.interaction_id}
    for stale in (old_card, recovered):
        with pytest.raises(ValueError, match="INTERACTION_STALE"):
            env.resume({"choice": "approve", "interaction_id": stale.interaction.interaction_id})
    assert bank_orders(env.runtime) == orders
    assert paid_amounts(env) == paid
    assert cross_state(env)["birthday"]["pending"] is None


@pytest.mark.parametrize("stage", ["freeze_verification", "order_verification", "capture_verification"])
def test_cancel_recovered_wait_only_closes_original_funds(harness_env, stage):
    env = harness_env
    _, original = waiting_at(env, stage)
    caller = target_session(env)
    recovered = env.runtime.harness.recover_session(caller)
    env.who = caller
    orders, paid = bank_orders(env.runtime), paid_amounts(env)

    stopped = env.resume({"choice": "cancel", "interaction_id": recovered.interaction.interaction_id})

    assert stopped.status in {TaskStatus.CANCELLED, TaskStatus.PARTIALLY_SUCCEEDED}, stopped.message
    assert bank_orders(env.runtime) == orders
    assert paid_amounts(env) == paid
    assert cross_state(env)["birthday"]["pending"] is None
    original_fact = env.runtime.gateway.get_operation(caller, original.operation_id)
    assert original_fact.lookup == "not_found"


def test_paid_item_survives_recovery_and_stop_of_the_next_item(harness_env):
    from copy import deepcopy

    env = harness_env
    card, _ = waiting_at(env, "capture_confirmation")
    next_item = settle(env, card)
    before = deepcopy(cross_state(env)["birthday"]["orders"][0])
    assert before["capture"] == "completed"
    orders, paid = bank_orders(env.runtime), paid_amounts(env)
    caller = target_session(env)

    recovered = env.runtime.harness.recover_session(caller)

    env.who = caller
    assert recovered.interaction.kind == "confirmation"
    assert recovered.interaction.interaction_id != next_item.interaction.interaction_id
    assert cross_state(env)["birthday"]["orders"][0] == before
    stopped = env.resume({"choice": "cancel"})
    assert stopped.status is TaskStatus.PARTIALLY_SUCCEEDED, stopped.message
    assert bank_orders(env.runtime) == orders
    assert paid_amounts(env) == paid == [19900]
    assert cross_state(env)["birthday"]["orders"][0] == before


@pytest.mark.parametrize("kind", ["freeze", "capture"])
def test_stop_unknown_session_waits_then_only_finishes_original_funds(harness_env, monkeypatch, kind):
    from app.agent_platform.test_birthday_runtime_wiring import answer_verification
    from app.contracts.bank import BankError, QueryFailure
    from app.modules.cross.birthday import BirthdayFlow

    env = harness_env
    card, _ = waiting_at(env, kind + "_verification")
    answer_verification(env.runtime, env.who, "R1", card.interaction.record_ref)
    flow = BirthdayFlow(None, cross_state(env), None)
    ports = env.runtime.birthday.ports_factory(env.who)
    if kind == "freeze":
        ports.freeze_execute(env.who, flow._plan())
    else:
        item = flow._order(flow.b["pending"]["target"][1])
        ports.capture_execute(env.who, flow._plan(), item, item["order_id"])
    orders, paid = bank_orders(env.runtime), paid_amounts(env)
    caller = target_session(env)
    read = env.runtime.gateway.get_operation
    monkeypatch.setattr(env.runtime.gateway, "get_operation", lambda *_: QueryFailure(
        kind="error", error=BankError(code="BANK_UNAVAILABLE", details={})))
    recovered = env.runtime.harness.recover_session(caller)
    env.who = caller
    assert "结果仍待核实" in recovered.message

    stopped = env.resume({"choice": "cancel"})

    assert stopped.status is TaskStatus.WAITING_INPUT
    assert "已停止新增办理" in stopped.message
    assert bank_orders(env.runtime) == orders and paid_amounts(env) == paid
    monkeypatch.setattr(env.runtime.gateway, "get_operation", read)
    settled = env.resume({"selected_option_id": option_id(stopped, "核实原操作")})
    expected = TaskStatus.CANCELLED if kind == "freeze" else TaskStatus.PARTIALLY_SUCCEEDED
    assert settled.status is expected, settled.message
    assert bank_orders(env.runtime) == orders and paid_amounts(env) == paid


def test_pending_personal_budget_moves_only_after_fresh_proof(harness_env):
    """An acknowledged verification wait has a real pending reservation."""
    env = harness_env
    current = env.start()
    current = env.resume({"selected_option_id": option_id(current, "设置本月")})
    current = env.resume({"text": "10000元"})
    adopted = env.runtime.harness.resume_budget_input(env.who,
        input_request_id=uuid4(), interaction_id=current.interaction.interaction_id,
        selected_option_id=option_id(current, "采用个人预算"))
    current = env.resume({"selected_option_id": option_id(adopted.result, "继续生日")})
    from app.agent_platform.test_birthday_harness_publication import drive_to_freeze_confirmation
    freeze = drive_to_freeze_confirmation(env, current)
    approve_confirmation(env.runtime, env.who, freeze.interaction.record_ref)
    waiting = env.resume({"choice": "approve"})
    assert waiting.interaction.kind == "verification"
    record = env.runtime.application.list_adopted_budgets("U1", "D1")[0]
    original = env.runtime.application.list_budget_commitments("U1", "D1", record.budget_id)[0]
    assert original.state == "pending"
    caller = target_session(env)
    recovered = env.runtime.harness.recover_session(caller)
    env.who = caller

    next_card = settle(env, recovered)

    assert next_card.interaction.kind == "confirmation", next_card.message
    assert "下单" in next_card.message
    updated = env.runtime.application.list_budget_commitments("U1", "D1", record.budget_id)[0]
    assert updated.committed_fen == updated.unconsumed_fen == original.committed_fen
    assert original.operation_ids[0] in updated.operation_ids
    confirmation = env.runtime.confirmations.get(
        env.runtime._context(caller, None, None), recovered.interaction.record_ref)
    assert UUID(str(confirmation.operation_id)) in updated.operation_ids
