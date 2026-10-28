"""Review: actual failed/succeeded freezes before an unpublished G3 snapshot."""

from unittest.mock import Mock

import pytest

from app.agent_platform.birthday_runtime import BirthdayTaskPorts
from app.agent_platform.test_birthday_harness_publication import (
    drive_to_freeze_confirmation, harness_env,
)
from app.agent_platform.test_birthday_runtime_wiring import (
    answer_verification, approve_confirmation, option_id,
)
from app.agent_platform.test_birthday_session_recovery import target_session
from app.contracts.common import OperationStatus, TaskStatus
from app.storage.database import connect

from .test_birthday_session_faults import adopted_budget_freeze
from .test_birthday_session_recovery import cross_state
from .test_cross_birthday_platform_edit import bank_orders, paid_amounts


def interrupted_freeze(env, monkeypatch, *, personal_budget, failed):
    card = (adopted_budget_freeze(env, ("鲜花", "蛋糕")) if personal_budget
            else drive_to_freeze_confirmation(env))
    original = env.runtime.confirmations.get(
        env.runtime._context(env.who, None, None), card.interaction.record_ref)
    approve_confirmation(env.runtime, env.who, card.interaction.record_ref)
    assert env.resume({"choice": "approve"}).interaction.kind == "verification"
    caller = target_session(env)
    recovered = env.runtime.harness.recover_session(caller)
    env.who = caller
    replacement = env.runtime.confirmations.get(
        env.runtime._context(caller, None, None), recovered.interaction.record_ref)
    assert replacement.operation_id != original.operation_id
    approve_confirmation(env.runtime, caller, recovered.interaction.record_ref)
    verification = env.resume({"choice": "approve"})
    answer_verification(env.runtime, caller, "R1", verification.interaction.record_ref)
    if failed:
        # Isolated fixture change; the real bank decides ACCOUNT_UNAVAILABLE.
        with connect(env.runtime.bank.store.path) as connection:
            changed = connection.execute(
                "UPDATE accounts SET account_status='closed' WHERE user_id='U1' AND account_id='A1'").rowcount
        assert changed == 1
    before = env.published_ref()
    execute = BirthdayTaskPorts.freeze_execute

    def after_real_result(ports, trusted, plan):
        outcome = execute(ports, trusted, plan)
        assert outcome.state == ("failed" if failed else "completed")
        assert outcome.operation_id == str(replacement.operation_id)
        raise OSError("real freeze returned before Cross snapshot")

    monkeypatch.setattr(BirthdayTaskPorts, "freeze_execute", after_real_result)
    with pytest.raises(OSError, match="real freeze returned before Cross snapshot"):
        env.resume({"choice": "resume"})
    result = env.runtime.gateway.get_operation(caller, replacement.operation_id).operation
    assert result.operation_type == "bank.freeze_funds"
    if failed:
        assert result.operation_status is OperationStatus.FAILED
        assert result.receipt is None and result.failure.code == "ACCOUNT_UNAVAILABLE"
    else:
        assert result.operation_status is OperationStatus.SUCCEEDED
        assert result.receipt.frozen_amount_fen == 50000
    assert env.published_ref() == before
    assert cross_state(env)["birthday"]["freeze"] is None
    assert env.runtime.gateway.get_operation(caller, original.operation_id).lookup == "not_found"
    return original, replacement, result


@pytest.mark.parametrize("personal_budget,failed", [(True, True), (False, False), (False, True)],
    ids=["budget-failed", "no-budget-succeeded", "no-budget-failed"])
def test_cancel_reconciles_the_exact_bank_terminal_freeze(
    harness_env, monkeypatch, personal_budget, failed,
):
    env = harness_env
    original, replacement, result = interrupted_freeze(env, monkeypatch,
        personal_budget=personal_budget, failed=failed)
    assert len(env.runtime.application.list_adopted_budgets("U1", "D1")) == int(personal_budget)
    forbidden = []
    for name in ("freeze_funds", "create_order", "capture_frozen"):
        spy = Mock(side_effect=AssertionError("CANCEL_MUST_NOT_CREATE_A_NEW_WRITE"))
        forbidden.append(spy)
        monkeypatch.setattr(env.runtime.gateway, name, spy)
    release = Mock(side_effect=AssertionError("FAILED_FREEZE_MUST_NOT_RELEASE")) if failed else Mock(
        wraps=env.runtime.gateway.release_frozen)
    monkeypatch.setattr(env.runtime.gateway, "release_frozen", release)

    stopped = env.resume({"choice": "cancel"})

    assert stopped.status is TaskStatus.CANCELLED, stopped.message
    assert bank_orders(env.runtime) == [] and paid_amounts(env) == []
    if failed:
        assert release.call_count == 0
    else:
        assert env.runtime.gateway.get_freeze(env.who, result.receipt.freeze_id).data.remaining_fen == 0
        assert release.call_count == 1
    assert all(spy.call_count == 0 for spy in forbidden)
    if personal_budget:
        budget = env.runtime.application.list_adopted_budgets("U1", "D1")[0]
        hold = env.runtime.application.list_budget_commitments("U1", "D1", budget.budget_id,
            include_closed=True)[0]
        assert hold.state == "closed" and hold.unconsumed_fen == 0
        assert hold.operation_ids[:2] == [original.operation_id, replacement.operation_id]
    repeated = env.resume({"choice": "cancel"})
    assert repeated.status is TaskStatus.CANCELLED
    assert env.runtime.gateway.get_operation(env.who, replacement.operation_id).operation == result
    assert release.call_count == int(not failed)
    assert all(spy.call_count == 0 for spy in forbidden)


@pytest.mark.parametrize("observation_fault", ["bank_unavailable", "probe_none"])
def test_unbudgeted_unknown_freeze_keeps_its_original_id_until_read_recovers(
    harness_env, monkeypatch, observation_fault,
):
    from app.contracts.bank import BankError, QueryFailure

    env = harness_env
    _, replacement, result = interrupted_freeze(env, monkeypatch,
        personal_budget=False, failed=False)
    assert env.runtime.application.list_adopted_budgets("U1", "D1") == []
    read = env.runtime.gateway.get_operation
    observe = BirthdayTaskPorts.observe_freeze_submission
    if observation_fault == "bank_unavailable":
        monkeypatch.setattr(env.runtime.gateway, "get_operation", lambda *_: QueryFailure(
            kind="error", error=BankError(code="BANK_UNAVAILABLE", details={})))
    else:
        monkeypatch.setattr(BirthdayTaskPorts, "observe_freeze_submission", lambda *_: None)
    release = Mock(wraps=env.runtime.gateway.release_frozen)
    monkeypatch.setattr(env.runtime.gateway, "release_frozen", release)

    paused = env.resume({"choice": "cancel"})

    assert paused.status is TaskStatus.WAITING_INPUT, paused.message
    assert "提交情况仍待核实" in paused.message
    state = cross_state(env)["birthday"]
    assert state["freeze_submission_operation_id"] == str(replacement.operation_id)
    assert state["pending"] is None and state["freeze"] is None
    labels = [option.label for option in paused.interaction.options]
    assert not any("候选" in label or "调整" in label for label in labels)
    assert env.runtime.gateway.get_freeze(env.who, result.receipt.freeze_id).data.remaining_fen == 50000
    assert release.call_count == 0
    monkeypatch.setattr(env.runtime.gateway, "get_operation", read)
    monkeypatch.setattr(BirthdayTaskPorts, "observe_freeze_submission", observe)
    if observation_fault == "bank_unavailable":
        # The saved operation, not a budget hold or in-memory variable, survives.
        from .test_birthday_session_controls import restart

        restart(env)
        release = Mock(wraps=env.runtime.gateway.release_frozen)
        monkeypatch.setattr(env.runtime.gateway, "release_frozen", release)
    forbidden = []
    for name in ("freeze_funds", "create_order", "capture_frozen"):
        spy = Mock(side_effect=AssertionError("UNKNOWN_CLOSEOUT_MUST_ONLY_OBSERVE_ORIGINAL"))
        forbidden.append(spy)
        monkeypatch.setattr(env.runtime.gateway, name, spy)

    stopped = env.resume({"selected_option_id": option_id(paused, "重新核对预算")})

    assert stopped.status is TaskStatus.CANCELLED, stopped.message
    assert env.runtime.gateway.get_freeze(env.who, result.receipt.freeze_id).data.remaining_fen == 0
    assert cross_state(env)["birthday"]["freeze"]["operation_id"] == str(replacement.operation_id)
    assert cross_state(env)["birthday"]["freeze_submission_operation_id"] is None
    assert env.runtime.application.list_adopted_budgets("U1", "D1") == []
    assert bank_orders(env.runtime) == [] and paid_amounts(env) == []
    assert release.call_count == 1 and all(spy.call_count == 0 for spy in forbidden)
    assert env.resume({"choice": "cancel"}).status is TaskStatus.CANCELLED
    assert release.call_count == 1 and all(spy.call_count == 0 for spy in forbidden)


def test_explicit_stop_closes_the_observed_original_failed_freeze(harness_env, monkeypatch):
    """Real failed bank reply loss -> published unknown -> first S2 observation."""
    env = harness_env
    card = adopted_budget_freeze(env, ("鲜花", "蛋糕"))
    original = env.runtime.confirmations.get(
        env.runtime._context(env.who, None, None), card.interaction.record_ref)
    approve_confirmation(env.runtime, env.who, card.interaction.record_ref)
    verification = env.resume({"choice": "approve"})
    answer_verification(env.runtime, env.who, "R1", verification.interaction.record_ref)
    with connect(env.runtime.bank.store.path) as connection:
        assert connection.execute(
            "UPDATE accounts SET account_status='closed' WHERE user_id='U1' AND account_id='A1'").rowcount == 1
    freeze = env.runtime.gateway.freeze_funds

    def lost_failed_response(*args):
        result = freeze(*args)
        assert result.operation_status is OperationStatus.FAILED
        assert result.receipt is None and result.failure.code == "ACCOUNT_UNAVAILABLE"
        raise OSError("lost the real failed freeze response")

    monkeypatch.setattr(env.runtime.gateway, "freeze_funds", lost_failed_response)
    unknown = env.resume({"choice": "resume"})
    assert unknown.status is TaskStatus.WAITING_INPUT, unknown.message
    assert cross_state(env)["birthday"]["holding"] == "unknown_freeze"
    original_fact = env.runtime.gateway.get_operation(env.who, original.operation_id)
    assert original_fact.operation.operation_status is OperationStatus.FAILED
    budget = env.runtime.application.list_adopted_budgets("U1", "D1")[0]
    hold = env.runtime.application.list_budget_commitments("U1", "D1", budget.budget_id)[0]
    assert hold.state == "unknown" and hold.unconsumed_fen == 50000
    forbidden = []
    for name in ("freeze_funds", "create_order", "capture_frozen", "release_frozen"):
        spy = Mock(side_effect=AssertionError("FAILED_OBSERVATION_MUST_NOT_WRITE"))
        forbidden.append(spy)
        monkeypatch.setattr(env.runtime.gateway, name, spy)
    caller = target_session(env)

    observed = env.runtime.harness.recover_session(caller)

    env.who = caller
    assert observed.status is TaskStatus.WAITING_INPUT, observed.message
    observation = cross_state(env)["birthday"]["session_observation"]
    assert observation["operation_id"] == str(original.operation_id)
    assert observation["status"] == "failed"
    assert env.runtime.application.list_budget_commitments("U1", "D1", budget.budget_id)[0] == hold
    assert all(spy.call_count == 0 for spy in forbidden)
    stopped = env.resume({"choice": "cancel"})
    if stopped.status is not TaskStatus.CANCELLED:
        stopped = env.resume({"selected_option_id": option_id(stopped, "核实原操作")})
    assert stopped.status is TaskStatus.CANCELLED, stopped.message
    closed = env.runtime.application.list_budget_commitments("U1", "D1", budget.budget_id,
        include_closed=True)[0]
    assert closed.state == "closed" and closed.unconsumed_fen == 0
    assert closed.operation_ids == hold.operation_ids == [original.operation_id]
    assert bank_orders(env.runtime) == [] and paid_amounts(env) == []
    assert env.runtime.gateway.get_operation(caller, original.operation_id) == original_fact
    assert env.resume({"choice": "cancel"}).status is TaskStatus.CANCELLED
    assert all(spy.call_count == 0 for spy in forbidden)
