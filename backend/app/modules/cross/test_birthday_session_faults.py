"""Review regressions through the real Harness/G3/budget/security/bank chain."""

from copy import deepcopy
from uuid import uuid4

import pytest

from app.agent_platform.test_birthday_harness_publication import harness_env
from app.agent_platform.test_birthday_runtime_wiring import (
    DELIVERY_REF, approve_confirmation, option_id,
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
    for text in ("500元", "2026-10-30", DELIVERY_REF):
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
