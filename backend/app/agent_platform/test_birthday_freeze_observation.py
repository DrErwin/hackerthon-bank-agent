"""Platform23 read-only observation; real Harness/gate/bank, explicit NoopModel."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from app.contracts.bank import BankError, QueryFailure
from app.contracts.common import Phase
from app.contracts.security import ActionDescriptor
from app.modules.cross.birthday_ports import BirthdayPlan
from app.security.test_retirement import insert_claim_row
from app.storage.database import connect

from .test_birthday_harness_publication import drive_to_freeze_confirmation, harness_env
from .test_birthday_runtime_wiring import DELIVERY_REF, answer_verification, approve_confirmation


@pytest.fixture()
def waiting(harness_env):
    env = harness_env
    card = drive_to_freeze_confirmation(env)
    plan = BirthdayPlan("A1", None, None, 50000, 50000, "2026-10-30", DELIVERY_REF)
    return env, env.runtime.birthday.ports_factory(env.who), plan, card


def current(env):
    return env.snapshot()["birthday_actions"]["freeze"]


def claims_and_bank(env):
    with connect(env.runtime.application.path) as connection:
        claims = [tuple(row) for row in connection.execute("SELECT * FROM security_executions ORDER BY operation_id")]
    with connect(env.runtime.bank.store.path) as connection:
        bank = [tuple(row) for row in connection.execute("SELECT * FROM bank_operations ORDER BY operation_id")]
    return env.snapshot(), claims, bank


def observe(waiting, monkeypatch, operation_id=None, who=None, plan=None):
    env, ports, bound_plan, _ = waiting
    before = claims_and_bank(env)
    with monkeypatch.context() as guard:
        forbidden = []
        for method in ("freeze_funds", "create_order", "capture_frozen", "release_frozen"):
            spy = Mock(side_effect=AssertionError("READ_ONLY_PROBE"))
            forbidden.append(spy)
            guard.setattr(env.runtime.gateway, method, spy)
        spy = Mock(side_effect=AssertionError("NO_NEW_CLAIM"))
        forbidden.append(spy)
        guard.setattr(env.runtime.confirmations.state, "claim_execution", spy)
        spy = Mock(side_effect=AssertionError("NO_VERIFICATION_REUSE"))
        forbidden.append(spy)
        guard.setattr(env.runtime, "_reuse_session_verifications", spy)
        for method in ("grant_release", "bind_freeze", "finalize", "requery", "freeze_check", "freeze_execute"):
            spy = Mock(side_effect=AssertionError("NO_AUTHORIZATION_OR_EXECUTION"))
            forbidden.append(spy)
            guard.setattr(ports, method, spy)
        try:
            result = ports.observe_freeze_submission(who or env.who, plan or bound_plan,
                operation_id or current(env)["operation_id"])
        finally:
            assert all(spy.call_count == 0 for spy in forbidden)
            assert claims_and_bank(env) == before
    return result


def put_claim(env, state):
    action = current(env)
    context = env.runtime._context(env.who, UUID(action["operation_id"]), action["action_revision"])
    descriptor = ActionDescriptor(action_name="bank.freeze_funds", parameters_ref=action["operation_id"],
        resource_refs=[], phase=Phase.EXECUTION)
    insert_claim_row(SimpleNamespace(path=env.runtime.application.path), context, descriptor, state)


def execute_freeze(waiting):
    env, ports, plan, card = waiting
    approve_confirmation(env.runtime, env.who, card.interaction.record_ref)
    verification = env.resume({"choice": "approve"})
    answer_verification(env.runtime, env.who, "R1", verification.interaction.record_ref)
    return ports.freeze_execute(env.who, plan)


def test_not_submitted_requires_real_not_found_and_no_claim(waiting, monkeypatch):
    assert observe(waiting, monkeypatch) == "not_submitted"


def test_real_completed_freeze_is_submitted_without_advancing_it(waiting, monkeypatch):
    assert execute_freeze(waiting).state == "completed"
    assert observe(waiting, monkeypatch) == "submitted"


@pytest.mark.parametrize("state", ["processing", "unknown", "completed"])
def test_a_claim_without_a_bank_result_is_unknown(waiting, monkeypatch, state):
    put_claim(waiting[0], state)
    assert observe(waiting, monkeypatch) == "unknown"


@pytest.mark.parametrize("source", ["claim", "bank", "bank_none", "bank_exception", "barrier"])
def test_read_failure_is_unknown(waiting, monkeypatch, source):
    env = waiting[0]
    if source == "claim":
        monkeypatch.setattr(env.runtime.confirmations.state, "get_execution", Mock(side_effect=OSError("read unavailable")))
    elif source == "bank":
        monkeypatch.setattr(env.runtime.gateway, "get_operation", lambda *_: QueryFailure(
            kind="error", error=BankError(code="BANK_UNAVAILABLE", details={})))
    elif source == "bank_none":
        monkeypatch.setattr(env.runtime.gateway, "get_operation", lambda *_: None)
    elif source == "bank_exception":
        monkeypatch.setattr(env.runtime.gateway, "get_operation", Mock(side_effect=OSError("bank unavailable")))
    else:
        monkeypatch.setattr(env.runtime.gateway, "wait_for_inflight", Mock(side_effect=OSError("barrier unavailable")))
    assert observe(waiting, monkeypatch) == "unknown"


@pytest.mark.parametrize("change", [{"user_id": "OTHER"}, {"demo_round_id": "OTHER"},
    {"task_id": "OTHER"}, {"session_id": "OTHER"}])
def test_existing_owned_task_gate_rejects_foreign_context(waiting, monkeypatch, change):
    env = waiting[0]
    lookup = Mock(side_effect=AssertionError("SCOPE_GATE_MUST_RUN_FIRST"))
    monkeypatch.setattr(env.runtime.gateway, "get_operation", lookup)
    with pytest.raises(ValueError if "demo_round_id" in change else PermissionError):
        observe(waiting, monkeypatch, who=env.who.model_copy(update=change))
    assert lookup.call_count == 0


@pytest.mark.parametrize("change", [{"freeze_amount_fen": 50100}, {"payer_account_id": "A2"}])
def test_changed_plan_is_unknown(waiting, monkeypatch, change):
    assert observe(waiting, monkeypatch, plan=replace(waiting[2], **change)) == "unknown"


def test_unbound_operation_is_unknown(waiting, monkeypatch):
    assert observe(waiting, monkeypatch, operation_id=str(uuid4())) == "unknown"


def test_exact_revision_is_not_replaced_with_a_default(waiting, monkeypatch):
    env = waiting[0]
    put_claim(env, "processing")
    task = env.task()
    action = {**current(env), "action_revision": current(env)["action_revision"] + 1}
    env.runtime.application.update_task("U1", "D1", "BIRTHDAY", task.revision, task.run_id,
        task.status, task.checkpoint_id, {**task.snapshot, "birthday_actions": {"freeze": action}})
    assert observe(waiting, monkeypatch) == "unknown"


@pytest.mark.parametrize("field,value", [("action_revision", 0), ("action_revision", True),
    ("parameters", {"__action__": "bank.create_order"})])
def test_missing_or_wrong_current_binding_is_unknown(waiting, monkeypatch, field, value):
    env = waiting[0]
    task = env.task()
    action = {**current(env), field: value}
    env.runtime.application.update_task("U1", "D1", "BIRTHDAY", task.revision, task.run_id,
        task.status, task.checkpoint_id, {**task.snapshot, "birthday_actions": {"freeze": action}})
    assert observe(waiting, monkeypatch) == "unknown"


def test_owned_task_read_failure_is_unknown(waiting, monkeypatch):
    monkeypatch.setattr(waiting[0].runtime, "_task", Mock(side_effect=OSError("task unavailable")))
    assert observe(waiting, monkeypatch) == "unknown"


def test_old_retired_operation_is_never_the_current_replacement(waiting, monkeypatch):
    from .test_birthday_session_proof import recover_cached_card
    from .test_birthday_session_recovery import target_session

    env = waiting[0]
    old_operation = current(env)["operation_id"]
    caller = target_session(env)
    recover_cached_card(env, caller)
    env.who = caller
    assert current(env)["operation_id"] != old_operation
    assert observe(waiting, monkeypatch, operation_id=old_operation) == "unknown"
    read = env.runtime.confirmations.state.get_execution
    seen_sessions = []

    def current_session_only(context, action):
        seen_sessions.append(context.session_id)
        return read(context, action)

    monkeypatch.setattr(env.runtime.confirmations.state, "get_execution", current_session_only)
    assert observe(waiting, monkeypatch) == "not_submitted"
    assert seen_sessions == [caller.session_id, caller.session_id]


@pytest.mark.parametrize("fault", ["processing", "wrong_operation", "wrong_action"])
def test_bank_result_must_be_terminal_and_match_the_current_freeze(waiting, monkeypatch, fault):
    from app.contracts.bank import OperationFound
    from app.contracts.common import OperationStatus

    env = waiting[0]
    execute_freeze(waiting)
    found = env.runtime.gateway.get_operation(env.who, UUID(current(env)["operation_id"]))
    changes = {"operation_status": OperationStatus.PROCESSING, "receipt": None} if fault == "processing" else (
        {"operation_id": uuid4()} if fault == "wrong_operation" else {"operation_type": "bank.create_order"})
    injected = OperationFound(lookup="found", operation=found.operation.model_copy(update=changes))
    monkeypatch.setattr(env.runtime.gateway, "get_operation", lambda *_: injected)
    assert observe(waiting, monkeypatch) == "unknown"


def test_real_response_loss_is_submitted_only_after_bank_terminal_lookup(waiting, monkeypatch):
    env = waiting[0]
    env.runtime.bank.birthday.arm_response_loss(env.who.user_id)
    assert execute_freeze(waiting).state == "unknown"
    assert observe(waiting, monkeypatch) == "submitted"


def test_an_unsettled_gateway_future_prevents_not_submitted(waiting, monkeypatch):
    from threading import Event

    # Real gateway tracking fault: no target claim exists, but one queued
    # gateway worker is still unresolved, so absence cannot be concluded.
    env = waiting[0]
    finish = Event()
    future = env.runtime.gateway._submit_write(lambda: finish.wait(15))
    try:
        assert not env.runtime.gateway.wait_for_inflight(0.0)
        assert observe(waiting, monkeypatch) == "unknown"
    finally:
        finish.set()
        future.result(timeout=15)
    assert env.runtime.gateway.wait_for_inflight(1)
    assert observe(waiting, monkeypatch) == "not_submitted"


def test_a_real_inflight_freeze_stays_unknown_without_a_second_write(waiting, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    env, ports, plan, card = waiting
    approve_confirmation(env.runtime, env.who, card.interaction.record_ref)
    verification = env.resume({"choice": "approve"})
    answer_verification(env.runtime, env.who, "R1", verification.interaction.record_ref)
    entered, finish = Event(), Event()
    original = env.runtime.bank.birthday.freeze_funds

    def blocked(*args, **kwargs):
        entered.set()
        assert finish.wait(15)
        return original(*args, **kwargs)

    monkeypatch.setattr(env.runtime.bank.birthday, "freeze_funds", blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        write = pool.submit(ports.freeze_execute, env.who, plan)
        try:
            assert entered.wait(15)
            assert not env.runtime.gateway.wait_for_inflight(0.0)
            assert observe(waiting, monkeypatch) == "unknown"
        finally:
            finish.set()
        assert write.result(timeout=15).state == "completed"
    assert observe(waiting, monkeypatch) == "submitted"


def test_a_claim_appearing_during_the_barrier_is_not_absent(waiting, monkeypatch):
    env, ports, plan, _ = waiting
    barrier = env.runtime.gateway.wait_for_inflight

    def racing(timeout):
        drained = barrier(timeout)
        put_claim(env, "processing")  # Explicit concurrent claim fault.
        return drained

    monkeypatch.setattr(env.runtime.gateway, "wait_for_inflight", racing)
    before_bank = claims_and_bank(env)[2]
    assert ports.observe_freeze_submission(env.who, plan, current(env)["operation_id"]) == "unknown"
    assert claims_and_bank(env)[2] == before_bank


def test_current_action_drift_during_bank_read_is_unknown(waiting, monkeypatch):
    env, ports, plan, _ = waiting
    operation = current(env)["operation_id"]
    read = env.runtime.gateway.get_operation

    def drifting(*args):
        result = read(*args)
        task = env.task()
        action = {**current(env), "operation_id": str(uuid4())}
        env.runtime.application.update_task("U1", "D1", "BIRTHDAY", task.revision, task.run_id,
            task.status, task.checkpoint_id, {**task.snapshot, "birthday_actions": {"freeze": action}})
        return result

    monkeypatch.setattr(env.runtime.gateway, "get_operation", drifting)
    before = claims_and_bank(env)[1:]
    assert ports.observe_freeze_submission(env.who, plan, operation) == "unknown"
    assert claims_and_bank(env)[1:] == before
