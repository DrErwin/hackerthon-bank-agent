"""Real Harness/CAS/checkpoints; the budget business is an explicit stand-in."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.audit.journal import AuditJournal
from app.contracts.common import OperationLevel, TaskStatus
from app.contracts.cross import BudgetView, CrossTaskView
from app.contracts.bills import BillScope
from app.contracts.platform import CapabilityDefinition, ModuleManifest, TrustedContext
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult
from app.memory.adapter import MemoryAdapter
from app.storage.application import ApplicationStore

from .budget_inputs import BudgetInputRecovery
from .harness import AgentHarness
from .registry import CapabilityRegistry


def candidate(who, *, interaction="I1", plan=1, limit=50000):
    now = datetime.now(timezone.utc)
    return ModuleResult(task_id=who.task_id, run_id=who.run_id,
        status=TaskStatus.WAITING_INPUT, data=CrossTaskView(plan_revision=plan, steps=[], summary="候选",
            budget=BudgetView(budget_ref=None, purpose="生日", scope=BillScope(account_ids=["A1"],
                start_at="2026-10-01T00:00:00+08:00", end_at="2026-11-01T00:00:00+08:00"),
                personal_limit_fen=limit, used_fen=0, remaining_fen=limit, facts_as_of=now, adopted=False)),
        message="请选一项", interaction=InteractionRequest(interaction_id=interaction, kind="input",
            prompt="候选", required_fields=["cross_selection"], record_ref=None,
            options=[InteractionOption(id="A", label="一"), InteractionOption(id="M", label="二")]),
        error=None, allowed_actions=["provide_input", "cancel"], recovery_required=False, recovery_reason=None)


@pytest.fixture
def env(tmp_path):
    env = SimpleNamespace(path=tmp_path / "application.sqlite", calls=0, seen=[], reconciles=0,
                          fail=None, copied=None, thread_origin="unset", callbacks=0)
    who = TrustedContext(user_id="U1", session_id="S1", task_id="T1", run_id="R1",
                         demo_round_id="D1", parent_task_id=None)
    env.who = who

    class Entry:
        def __init__(self, saver):
            self.saver = saver

        def state(self, thread_id):
            config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
            saved = self.saver.get_tuple(config)
            return saved, (saved.checkpoint["channel_values"].get("budget", {}) if saved else {})

        def save(self, thread_id, state):
            saved, _ = self.state(thread_id)
            version = saved.checkpoint["channel_versions"]["budget"] + 1 if saved else 1
            config = saved.config if saved else {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
            self.saver.put(config, {"v": 1, "id": str(uuid4()),
                "ts": datetime.now(timezone.utc).isoformat(), "channel_values": {"budget": state},
                "channel_versions": {"budget": version}, "versions_seen": {}, "pending_sends": []},
                {"source": "update", "step": version, "parents": {}}, {"budget": version})

        def resume(self, trusted, response, *, thread_id):
            env.calls += 1
            origin = env.harness.budget_input_origin(trusted)
            env.seen.append(origin)
            if origin is None:
                return candidate(trusted)
            env.copied = copy_context()
            copied = copy_context()
            with ThreadPoolExecutor(max_workers=1) as pool:
                env.thread_origin = pool.submit(copied.run, env.harness.budget_input_origin, trusted).result()
            assert env.harness.budget_input_origin(trusted.model_copy(update={"task_id": "OTHER"})) is None
            if env.fail == "before_attempt":
                raise RuntimeError("before attempt")
            _, state = self.state(thread_id)
            attempt = state.get("attempt")
            if attempt is None:
                attempt = {"origin_id": origin.origin_id, "attempt_ref": str(uuid4()),
                           "expected_revision": origin.dispatch_task_revision,
                           "accepted_at": origin.accepted_at}
                state["attempt"] = attempt
                self.save(thread_id, state)
            assert attempt["origin_id"] == origin.origin_id
            assert attempt["expected_revision"] == origin.dispatch_task_revision
            if env.fail == "after_attempt":
                raise RuntimeError("after attempt")
            # This is not #293 or real adoption. It is a durable stand-in fact
            # proving the platform never asks the module to adopt a second time.
            result = ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
                status=TaskStatus.SUCCEEDED, data={"stand_in": True}, message="原业务结果",
                interaction=None, error=None, allowed_actions=[], recovery_required=False, recovery_reason=None)
            state["adoptions"] = state.get("adoptions", 0) + 1
            state["result"] = result.model_dump(mode="json")
            self.save(thread_id, state)
            if env.fail == "after_adopt":
                raise RuntimeError("after adoption")
            return result

        def reconcile_budget_input(self, trusted, origin, *, thread_id):
            env.reconciles += 1
            assert env.harness.budget_input_origin(trusted) is None
            _, state = self.state(thread_id)
            if state.get("result") is None:
                return None
            assert state["attempt"]["origin_id"] == origin.origin_id
            return BudgetInputRecovery(state["attempt"]["attempt_ref"],
                                       ModuleResult.model_validate(state["result"]))

    def reopen():
        store = ApplicationStore(env.path)
        registry = CapabilityRegistry()
        registry.register_module(ModuleManifest(module_name="cross", version="test", owner="test",
            description="budget provenance stand-in", implementation_kind="workflow", dependencies=[],
            capabilities=[CapabilityDefinition(name="cross.start_task", input_schema_ref="CrossStartInput",
                output_schema_ref="ModuleResult", required_permissions=[], operation_level=OperationLevel.READ,
                side_effect=False, confirmation_policy="none", timeout_ms=1000, retry_policy="read_only",
                handler_ref="test")]), lambda _trusted, saver, _trace: Entry(saver))
        env.harness = AgentHarness(store, MemoryAdapter(store, active_round=lambda: "D1"),
            AuditJournal(env.path), registry, SimpleNamespace(config_version="budget-test"), lambda *_: True)
        env.store = store
        return env.harness

    env.reopen = reopen
    reopen()
    now = datetime.now(timezone.utc)
    env.store.create_session("S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat())
    env.store.create_task("T1", "U1", "S1", "D1", "R1", "waiting_input",
        {"capability_name": "cross.start_task", "config_version": "budget-test", "trace_id": str(uuid4()),
         "result": candidate(who).model_dump(mode="json")})
    env.request = uuid4()
    env.submit = lambda **kwargs: env.harness.resume_budget_input(kwargs.pop("trusted", env.who),
        input_request_id=kwargs.pop("request", env.request), interaction_id=kwargs.pop("interaction", "I1"),
        selected_option_id=kwargs.pop("option", "A"), **kwargs)
    env.record = lambda: env.harness.budget_input_record(env.who, env.request)
    env.task = lambda: env.store.get_task("U1", "D1", "T1")
    yield env


def test_dedicated_source_is_persistent_immutable_and_current_call_only(env):
    result = env.submit()
    origin = env.seen[0]
    assert origin.facts["accepted_task_revision"] == 0
    assert origin.dispatch_task_revision == 1
    assert env.record()["phase"] == "completed"
    assert env.record()["completion"]["task_revision"] == env.task().revision == 2
    assert env.record()["completion"]["attempt_ref"]
    assert env.harness.budget_input_origin(env.who) is None and env.thread_origin is None
    assert env.copied.run(env.harness.budget_input_origin, env.who) is None
    with pytest.raises(FrozenInstanceError):
        origin.origin_id = "forged"
    origin.facts["candidate_snapshot"]["personal_limit_fen"] = 1
    assert env.record()["candidate_snapshot"]["personal_limit_fen"] == 50000
    assert origin.origin_id not in result.result.model_dump_json()
    env.reopen()
    assert env.submit() == result and env.calls == 1


def test_completed_request_replays_original_result_not_current_plan(env):
    first = env.submit()
    task = env.task()
    newer = candidate(env.who, interaction="I2", plan=2, limit=80000)
    env.store.update_task("U1", "D1", "T1", task.revision, "NEW-RUN", newer.status, task.checkpoint_id,
                         {**task.snapshot, "result": newer.model_dump(mode="json")})
    assert env.submit(trusted=env.who.model_copy(update={"run_id": "R99"})) == first
    assert env.calls == 1 and env.task().snapshot["result"] == newer.model_dump(mode="json")
    with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
        env.submit(option="M")


def test_source_write_failure_calls_no_module(env):
    with patch.object(env.store, "update_task", side_effect=OSError("storage unavailable")):
        with pytest.raises(OSError):
            env.submit()
    assert env.calls == 0 and env.record() is None


def test_interruption_before_dispatch_keeps_original_identity_and_retries_once(env):
    with patch.object(env.harness, "_resume", side_effect=RuntimeError("crash before module")):
        with pytest.raises(RuntimeError):
            env.submit()
    original = env.record()
    assert original["phase"] == "accepted" and env.calls == 0
    env.reopen()
    done = env.submit(trusted=env.who.model_copy(update={"run_id": "R2"}))
    assert done.result.run_id == "R1" and env.record()["accepted_at"] == original["accepted_at"]
    assert done.origin_id == original["origin_id"] and env.calls == 1


def test_model_or_ordinary_resume_cannot_borrow_an_accepted_source(env):
    with patch.object(env.harness, "_resume", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            env.submit()
    origin_id = env.record()["origin_id"]
    result = env.harness.resume(env.who, {"choice": "A", "source": "human", "origin_id": origin_id})
    assert result.status is TaskStatus.WAITING_INPUT and env.seen == [None]
    assert env.record()["phase"] == "invalidated"
    with pytest.raises(ValueError, match="BUDGET_INPUT_STALE"):
        env.submit()


@pytest.mark.parametrize("field", ["plan", "limit", "interaction", "prompt"])
def test_replaced_candidate_or_published_binding_cannot_reactivate_source(env, field):
    with patch.object(env.harness, "_resume", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            env.submit()
    task = env.task()
    result = candidate(env.who, plan=2 if field == "plan" else 1,
        limit=60000 if field == "limit" else 50000,
        interaction="I2" if field == "interaction" else "I1")
    if field == "prompt":
        result.interaction.prompt = "另一份展示"
    env.store.update_task("U1", "D1", "T1", task.revision, task.run_id, result.status, task.checkpoint_id,
                         {**task.snapshot, "result": result.model_dump(mode="json")})
    with pytest.raises(ValueError, match="BUDGET_INPUT_STALE"):
        env.submit()
    assert env.calls == 0 and env.record()["phase"] == "invalidated"


@pytest.mark.parametrize("failure", ["before_attempt", "after_attempt"])
def test_fault_result_does_not_refresh_revision_to_attempt_new_adoption(env, failure):
    env.fail = failure
    with pytest.raises(RuntimeError):
        env.submit()
    dispatch_revision = env.record()["dispatch_task_revision"]
    assert env.task().status is TaskStatus.NEEDS_ATTENTION and env.task().revision > dispatch_revision
    env.fail = None
    env.reopen()
    with pytest.raises(ValueError, match="BUDGET_INPUT_STALE"):
        env.submit()
    assert env.calls == 1


@pytest.mark.parametrize("terminal", [False, True])
def test_adopted_history_recovers_from_attention_without_activating_source(env, terminal):
    env.fail = "after_adopt"
    with pytest.raises(RuntimeError):
        env.submit()
    assert env.task().status is TaskStatus.NEEDS_ATTENTION
    assert env.task().snapshot["result"]["interaction"] is None
    if terminal:
        task = env.task()
        env.store.update_task("U1", "D1", "T1", task.revision, task.run_id, TaskStatus.CANCELLED,
            task.checkpoint_id, task.snapshot)
    status, previous = env.task().status, env.task().snapshot["result"]
    env.reopen()
    completed = env.submit(trusted=env.who.model_copy(update={"run_id": "R2"}))
    assert completed.result.status is TaskStatus.SUCCEEDED and completed.result.run_id == "R1"
    assert env.task().status is status and env.task().snapshot["result"] == previous
    assert env.calls == 1 and env.record()["completion"]["attempt_ref"]
    assert env.harness.budget_input_origin(env.who) is None


def test_adoption_before_result_cas_failure_is_history_only_on_retry(env):
    update = env.store.update_task

    def publish_fault(*args, **kwargs):
        snapshot = args[-1]
        if snapshot.get("result", {}).get("status") == "succeeded":
            raise OSError("result CAS unavailable")
        return update(*args, **kwargs)

    with patch.object(env.store, "update_task", side_effect=publish_fault):
        with pytest.raises(OSError):
            env.submit()
    assert env.record()["phase"] == "accepted"
    env.reopen()
    first = env.submit()
    assert env.calls == 1 and env.record()["phase"] == "completed"
    assert env.submit() == first and env.calls == 1


@pytest.mark.parametrize("same_request", [False, True])
def test_two_connections_do_not_create_two_origins(env, same_request):
    first, second = env.request, (env.request if same_request else uuid4())

    def submit(request):
        try:
            return env.submit(request=request)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, [first, second]))
    assert any(result is not None for result in results) and env.calls == 1
    assert len(env.task().snapshot["budget_input_origins"]) == 1
    if same_request:
        assert results[0] == results[1]


@pytest.mark.parametrize("field,value", [("user_id", "OTHER"), ("session_id", "OLD"),
                                          ("demo_round_id", "D2"), ("task_id", "OTHER")])
def test_cross_scope_cannot_submit_or_read(env, field, value):
    other = env.who.model_copy(update={field: value})
    with pytest.raises((ValueError, PermissionError)):
        env.submit(trusted=other)
    with pytest.raises((ValueError, PermissionError)):
        env.harness.budget_input_record(other, env.request)
    assert env.harness.budget_input_origin(other) is None and env.calls == 0


@pytest.mark.parametrize("adopted", [False, True])
def test_new_session_can_only_reconcile_history_not_reauthorize(env, adopted):
    if adopted:
        env.fail = "after_adopt"
        with pytest.raises(RuntimeError):
            env.submit()
    else:
        with patch.object(env.harness, "_resume", side_effect=RuntimeError):
            with pytest.raises(RuntimeError):
                env.submit()
    now = datetime.now(timezone.utc)
    env.store.create_session("S2", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat())
    env.store.transition_task_session("U1", "D1", "T1", "S1", "S2", env.task().revision)
    newer = env.who.model_copy(update={"session_id": "S2", "run_id": "R2"})
    if adopted:
        assert env.submit(trusted=newer).result.run_id == "R1" and env.calls == 1
    else:
        with pytest.raises(ValueError, match="BUDGET_INPUT_STALE"):
            env.submit(trusted=newer)
        assert env.calls == 0
