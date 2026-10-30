"""Review regressions through the real Harness/G3/budget/security/bank chain."""

from copy import deepcopy
from uuid import uuid4

import pytest

from app.agent_platform.test_birthday_harness_publication import harness_env
from app.agent_platform.test_birthday_runtime_wiring import (
    DELIVER_DATE, DELIVERY_REF, answer_verification, approve_confirmation, option_id,
)
from app.agent_platform.test_birthday_session_recovery import target_session
from app.contracts.bank import BankError, QueryFailure
from app.contracts.common import TaskStatus

from .test_birthday_session_recovery import cross_state, settle
from .test_cross_birthday_platform_edit import bank_orders, paid_amounts


def adopted_budget_freeze(env, products):
    """Adopt via the dedicated G3 input, then choose the real birthday items."""
    current = env.start()
    current = env.resume({"selected_option_id": option_id(current, "设置本月")})
    current = env.resume({"text": "10000元"})
    adopted = env.runtime.harness.resume_budget_input(env.who,
        input_request_id=uuid4(), interaction_id=current.interaction.interaction_id,
        selected_option_id=option_id(current, "采用个人预算"))
    current = env.resume({"selected_option_id": option_id(adopted.result, "继续生日")})
    for text in ("500元", DELIVER_DATE, DELIVERY_REF):
        current = env.resume({"text": text})
    for product in products:
        current = env.resume({"selected_option_id": option_id(current, product)})
    current = env.resume({"selected_option_id": option_id(current, "就选这些")})
    return env.resume({"selected_option_id": option_id(current, "采用并开始办理")})


@pytest.mark.parametrize("products", [("鲜花",), ("鲜花", "蛋糕")], ids=["single", "double"])
@pytest.mark.parametrize("verification_wait", [False, True], ids=["confirmation", "verification"])
def test_capture_recovery_budget_retry_keeps_the_original_order(
    harness_env, monkeypatch, products, verification_wait,
):
    env = harness_env
    freeze = adopted_budget_freeze(env, products)
    capture = settle(env, settle(env, freeze))
    original = env.runtime.confirmations.get(
        env.runtime._context(env.who, None, None), capture.interaction.record_ref)
    assert original.action_name == "bank.capture_frozen"
    if verification_wait:
        approve_confirmation(env.runtime, env.who, capture.interaction.record_ref)
        capture = env.resume({"choice": "approve"})
        assert capture.interaction.kind == "verification"
    before = deepcopy(cross_state(env)["birthday"]["orders"])
    order_id = before[0]["order_id"]
    orders = bank_orders(env.runtime)
    assert len(orders) == 1 and paid_amounts(env) == []
    read = env.runtime.gateway.list_transactions
    monkeypatch.setattr(env.runtime.gateway, "list_transactions", lambda *_: QueryFailure(
        kind="error", error=BankError(code="BANK_UNAVAILABLE", details={})))
    caller = target_session(env)

    paused = env.runtime.harness.recover_session(caller)

    env.who = caller
    assert paused.status is TaskStatus.WAITING_INPUT
    assert "已暂停新增办理" in paused.message
    assert cross_state(env)["birthday"]["orders"] == before
    assert bank_orders(env.runtime) == orders and paid_amounts(env) == []
    monkeypatch.setattr(env.runtime.gateway, "list_transactions", read)
    if verification_wait and len(products) == 1:
        from .test_birthday_session_controls import restart

        restart(env)
    recovered = env.resume({"selected_option_id": option_id(paused, "重新核对预算")})

    assert recovered.status is TaskStatus.WAITING_APPROVAL, recovered.message
    assert recovered.interaction.kind == "confirmation"
    confirmation = env.runtime.confirmations.get(
        env.runtime._context(caller, None, None), recovered.interaction.record_ref)
    assert confirmation.action_name == "bank.capture_frozen"
    assert confirmation.session_id == caller.session_id
    assert confirmation.operation_id != original.operation_id
    assert confirmation.confirmation_version > original.confirmation_version
    assert cross_state(env)["birthday"]["orders"] == before
    assert bank_orders(env.runtime) == orders and paid_amounts(env) == []
    current = settle(env, recovered)
    after_capture = cross_state(env)["birthday"]["orders"][0]
    assert after_capture["order_id"] == order_id
    assert after_capture["capture"] == "completed"
    assert paid_amounts(env) == [19900]
    for _ in range(2):
        if current.status is TaskStatus.SUCCEEDED:
            break
        current = settle(env, current)
    assert current.status is TaskStatus.SUCCEEDED, current.message
    final_orders = cross_state(env)["birthday"]["orders"]
    assert len(final_orders) == len(products)
    assert all(row["capture"] == "completed" for row in final_orders)
    assert final_orders[0]["order_id"] == order_id
    assert len(bank_orders(env.runtime)) == len(products)


def test_cancel_during_recovered_capture_budget_pause_does_not_restart_payment(
    harness_env, monkeypatch,
):
    env = harness_env
    freeze = adopted_budget_freeze(env, ("鲜花", "蛋糕"))
    settle(env, settle(env, freeze))
    before = deepcopy(cross_state(env)["birthday"])
    orders = bank_orders(env.runtime)
    monkeypatch.setattr(env.runtime.gateway, "list_transactions", lambda *_: QueryFailure(
        kind="error", error=BankError(code="BANK_UNAVAILABLE", details={})))
    caller = target_session(env)
    paused = env.runtime.harness.recover_session(caller)
    env.who = caller
    stale_retry = option_id(paused, "重新核对预算")

    stopped = env.resume({"choice": "cancel"})

    assert stopped.status is TaskStatus.CANCELLED, stopped.message
    assert bank_orders(env.runtime) == orders and paid_amounts(env) == []
    assert cross_state(env)["birthday"]["orders"] == before["orders"]
    assert cross_state(env)["birthday"]["session_recovery_target"] is None
    assert env.runtime.gateway.get_freeze(caller, before["freeze"]["freeze_id"]).data.remaining_fen == 0
    replay = env.resume({"selected_option_id": stale_retry})
    assert replay.status is TaskStatus.CANCELLED
    assert bank_orders(env.runtime) == orders and paid_amounts(env) == []


@pytest.mark.parametrize("observation_fault", ["available", "bank_unavailable", "probe_none"])
def test_cancel_reconciles_recovered_freeze_committed_before_cross_snapshot(
    harness_env, monkeypatch, observation_fault,
):
    """An unpublished intent must not hide an actual bank freeze on cancel."""
    from unittest.mock import Mock

    from app.agent_platform.birthday_runtime import BirthdayTaskPorts
    from app.contracts.bank import OperationNotFound, OperationStatus

    env = harness_env
    freeze = adopted_budget_freeze(env, ("鲜花", "蛋糕"))
    old_confirmation = env.runtime.confirmations.get(
        env.runtime._context(env.who, None, None), freeze.interaction.record_ref)
    approve_confirmation(env.runtime, env.who, freeze.interaction.record_ref)
    assert env.resume({"choice": "approve"}).interaction.kind == "verification"
    caller = target_session(env)
    recovered = env.runtime.harness.recover_session(caller)
    env.who = caller
    replacement = env.runtime.confirmations.get(
        env.runtime._context(caller, None, None), recovered.interaction.record_ref)
    assert replacement.operation_id != old_confirmation.operation_id
    approve_confirmation(env.runtime, caller, recovered.interaction.record_ref)
    verification = env.resume({"choice": "approve"})
    assert verification.interaction.kind == "verification"
    answer_verification(env.runtime, caller, "R1", verification.interaction.record_ref)
    published = env.published_ref()
    before = deepcopy(cross_state(env)["birthday"])
    assert before["freeze"] is None
    assert before["freeze_submission"] == "not_submitted_verification"
    budget = env.runtime.application.list_adopted_budgets("U1", "D1")[0]
    hold = env.runtime.application.list_budget_commitments("U1", "D1", budget.budget_id)[0]
    assert hold.operation_ids == [old_confirmation.operation_id, replacement.operation_id]
    execute = BirthdayTaskPorts.freeze_execute
    calls = Mock(wraps=env.runtime.gateway.freeze_funds)
    monkeypatch.setattr(env.runtime.gateway, "freeze_funds", calls)
    releases = Mock(wraps=env.runtime.gateway.release_frozen)
    monkeypatch.setattr(env.runtime.gateway, "release_frozen", releases)

    def after_real_effect(ports, trusted, plan):
        outcome = execute(ports, trusted, plan)
        assert outcome.state == "completed"
        assert outcome.operation_id == str(replacement.operation_id)
        raise OSError("freeze committed before Cross snapshot")

    monkeypatch.setattr(BirthdayTaskPorts, "freeze_execute", after_real_effect)
    request_id = uuid4()
    with pytest.raises(OSError, match="freeze committed before Cross snapshot"):
        env.resume({"choice": "resume"}, request_id=request_id)
    bank_result = env.runtime.gateway.get_operation(caller, replacement.operation_id)
    assert bank_result.operation.operation_status is OperationStatus.SUCCEEDED
    freeze_id = bank_result.operation.receipt.freeze_id
    assert env.runtime.gateway.get_freeze(caller, freeze_id).data.remaining_fen == 50000
    assert isinstance(env.runtime.gateway.get_operation(caller, old_confirmation.operation_id),
                      OperationNotFound)
    assert env.published_ref() == published
    assert cross_state(env)["birthday"] == before

    # Cancellation must reconcile the real new freeze before closing its hold.
    get_operation = env.runtime.gateway.get_operation
    observation = BirthdayTaskPorts.observe_freeze_submission
    if observation_fault == "bank_unavailable":
        monkeypatch.setattr(env.runtime.gateway, "get_operation", lambda *_: QueryFailure(
            kind="error", error=BankError(code="BANK_UNAVAILABLE", details={})))
    elif observation_fault == "probe_none":
        # Explicit provider-read fault, never a fabricated no-submission fact.
        monkeypatch.setattr(BirthdayTaskPorts, "observe_freeze_submission", lambda *_: None)
    stopped = env.resume({"choice": "cancel"})
    if observation_fault != "available":
        assert stopped.status is TaskStatus.WAITING_INPUT, stopped.message
        assert "提交情况仍待核实" in stopped.message
        pending = env.runtime.application.list_budget_commitments("U1", "D1", budget.budget_id)[0]
        assert pending == hold
        assert releases.call_count == 0 and calls.call_count == 1
        assert bank_orders(env.runtime) == [] and paid_amounts(env) == []
        assert env.runtime.gateway.get_freeze(caller, freeze_id).data.remaining_fen == 50000
        monkeypatch.setattr(env.runtime.gateway, "get_operation", get_operation)
        monkeypatch.setattr(BirthdayTaskPorts, "observe_freeze_submission", observation)
        stopped = env.resume({"selected_option_id": option_id(stopped, "重新核对预算")})
    assert stopped.status is TaskStatus.CANCELLED, stopped.message
    assert calls.call_count == releases.call_count == 1
    assert bank_orders(env.runtime) == [] and paid_amounts(env) == []
    assert env.runtime.gateway.get_freeze(caller, freeze_id).data.remaining_fen == 0
    closed = env.runtime.application.list_budget_commitments("U1", "D1", budget.budget_id,
        include_closed=True)[0]
    assert closed.state == "closed" and closed.unconsumed_fen == 0
    assert closed.operation_ids[:2] == [old_confirmation.operation_id, replacement.operation_id]
    facts = deepcopy(cross_state(env)["birthday"])
    repeated = env.resume({"choice": "cancel"})
    assert repeated.status is TaskStatus.CANCELLED
    assert cross_state(env)["birthday"] == facts
    assert calls.call_count == releases.call_count == 1


@pytest.mark.parametrize("claim_state", ["processing", "unknown"])
def test_cancel_keeps_a_recovered_pending_claim_without_a_bank_receipt(
    harness_env, monkeypatch, claim_state,
):
    """An explicit claim-state fault remains uncertain, even on real bank miss."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.contracts.common import Phase
    from app.contracts.security import ActionDescriptor
    from app.security.test_retirement import insert_claim_row

    env = harness_env
    freeze = adopted_budget_freeze(env, ("鲜花",))
    approve_confirmation(env.runtime, env.who, freeze.interaction.record_ref)
    assert env.resume({"choice": "approve"}).interaction.kind == "verification"
    caller = target_session(env)
    recovered = env.runtime.harness.recover_session(caller)
    env.who = caller
    confirmation = env.runtime.confirmations.get(
        env.runtime._context(caller, None, None), recovered.interaction.record_ref)
    approve_confirmation(env.runtime, caller, recovered.interaction.record_ref)
    waiting = env.resume({"choice": "approve"})
    answer_verification(env.runtime, caller, "R1", waiting.interaction.record_ref)
    context = env.runtime._context(caller, confirmation.operation_id, confirmation.action_revision)
    action = ActionDescriptor(action_name="bank.freeze_funds",
        parameters_ref=str(confirmation.operation_id), resource_refs=[], phase=Phase.EXECUTION)
    insert_claim_row(SimpleNamespace(path=env.runtime.application.path), context, action, claim_state)
    budget = env.runtime.application.list_adopted_budgets("U1", "D1")[0]
    hold = env.runtime.application.list_budget_commitments("U1", "D1", budget.budget_id)[0]
    before = env.runtime.gateway.get_operation(caller, confirmation.operation_id)
    assert before.lookup == "not_found"
    forbidden = []
    for method in ("freeze_funds", "create_order", "capture_frozen", "release_frozen"):
        spy = Mock(side_effect=AssertionError("UNRESOLVED_CANCEL_MUST_NOT_WRITE"))
        forbidden.append(spy)
        monkeypatch.setattr(env.runtime.gateway, method, spy)

    paused = env.resume({"choice": "cancel"})

    assert paused.status is TaskStatus.WAITING_INPUT, paused.message
    assert "提交情况仍待核实" in paused.message
    again = env.resume({"selected_option_id": option_id(paused, "重新核对预算")})
    assert again.status is TaskStatus.WAITING_INPUT
    assert env.runtime.application.list_budget_commitments("U1", "D1", budget.budget_id)[0] == hold
    assert env.runtime.gateway.get_operation(caller, confirmation.operation_id) == before
    assert cross_state(env)["birthday"]["freeze"] is None
    assert bank_orders(env.runtime) == [] and paid_amounts(env) == []
    assert all(spy.call_count == 0 for spy in forbidden)


def test_cancel_closes_only_the_proved_unsubmitted_replacement(harness_env):
    env = harness_env
    freeze = adopted_budget_freeze(env, ("鲜花",))
    original = env.runtime.confirmations.get(
        env.runtime._context(env.who, None, None), freeze.interaction.record_ref)
    approve_confirmation(env.runtime, env.who, freeze.interaction.record_ref)
    assert env.resume({"choice": "approve"}).interaction.kind == "verification"
    caller = target_session(env)
    recovered = env.runtime.harness.recover_session(caller)
    env.who = caller
    replacement = env.runtime.confirmations.get(
        env.runtime._context(caller, None, None), recovered.interaction.record_ref)
    budget = env.runtime.application.list_adopted_budgets("U1", "D1")[0]

    stopped = env.resume({"choice": "cancel"})

    assert stopped.status is TaskStatus.CANCELLED, stopped.message
    assert bank_orders(env.runtime) == [] and paid_amounts(env) == []
    assert env.runtime.gateway.get_operation(caller, original.operation_id).lookup == "not_found"
    assert env.runtime.gateway.get_operation(caller, replacement.operation_id).lookup == "not_found"
    hold = env.runtime.application.list_budget_commitments("U1", "D1", budget.budget_id,
        include_closed=True)[0]
    assert hold.operation_ids == [original.operation_id, replacement.operation_id]
    assert hold.state == "closed" and hold.unconsumed_fen == 0
