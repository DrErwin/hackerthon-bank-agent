"""F10 over real HTTP/Harness/checkpoints; budget business is a durable stand-in.

No real AdoptedBudget, external model or money action is used in this file.
"""

from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import socket
from types import SimpleNamespace
import threading
import time
from uuid import uuid4

import httpx
import pytest
import uvicorn

from app.agent_platform.budget_inputs import BudgetInputRecovery
from app.agent_platform.model import ContinueProposal
from app.agent_platform.test_budget_inputs import candidate
from app.contracts.common import OperationLevel, TaskStatus
from app.contracts.platform import CapabilityDefinition, ModuleManifest, TrustedContext
from app.contracts.tasks import ModuleResult

from .service import ApiService, Identity
from .test_app import bank_counts, enter, make_app, post


ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def budget_api(tmp_path):
    env = SimpleNamespace(calls=0, origins=[], reconciles=0, fail=None, path=tmp_path)

    class BudgetStandIn:
        def __init__(self, saver):
            self.saver = saver

        def load(self, thread):
            saved = self.saver.get_tuple({"configurable": {"thread_id": thread}})
            return saved, saved.checkpoint["channel_values"].get("budget", {}) if saved else {}

        def save(self, thread, state):
            saved, _ = self.load(thread)
            version = saved.checkpoint["channel_versions"]["budget"] + 1 if saved else 1
            self.saver.put(saved.config if saved else {"configurable": {"thread_id": thread}},
                {"v": 1, "id": str(uuid4()), "ts": datetime.now(timezone.utc).isoformat(),
                 "channel_values": {"budget": state}, "channel_versions": {"budget": version},
                 "versions_seen": {}, "pending_sends": []},
                {"source": "update", "step": version, "parents": {}}, {"budget": version})

        def resume(self, trusted, response, *, thread_id):
            env.calls += 1
            origin = env.api.runtime.harness.budget_input_origin(trusted)
            env.origins.append(origin)
            if origin is None:
                return candidate(trusted)
            if response["choice"] == "M":
                return candidate(trusted, interaction="I2", plan=2)
            if env.fail == "before_attempt":
                raise RuntimeError("stand-in before attempt")
            _, state = self.load(thread_id)
            if "attempt" not in state:
                state["attempt"] = {"origin_id": origin.origin_id, "attempt_ref": str(uuid4())}
                self.save(thread_id, state)
            assert state["attempt"]["origin_id"] == origin.origin_id
            if env.fail == "after_attempt":
                raise RuntimeError("stand-in after attempt")
            result = ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
                status="succeeded", data={"stand_in": True}, message="测试替身的原结果",
                interaction=None, error=None, allowed_actions=[],
                recovery_required=False, recovery_reason=None)
            state.update(result=result.model_dump(mode="json"), adoptions=state.get("adoptions", 0) + 1)
            self.save(thread_id, state)
            if env.fail == "after_adopt":
                raise RuntimeError("stand-in after adopted fact")
            return result

        def reconcile_budget_input(self, trusted, origin, *, thread_id):
            env.reconciles += 1
            assert env.api.runtime.harness.budget_input_origin(trusted) is None
            _, state = self.load(thread_id)
            if "result" not in state:
                return None
            assert state["attempt"]["origin_id"] == origin.origin_id
            return BudgetInputRecovery(state["attempt"]["attempt_ref"],
                                       ModuleResult.model_validate(state["result"]))

    def prepare(runtime):
        runtime.harness.registry.register_module(ModuleManifest(module_name="cross", version="test",
            owner="test", description="durable budget stand-in", implementation_kind="workflow",
            dependencies=[], capabilities=[CapabilityDefinition(name="cross.start_task",
                input_schema_ref="CrossStartInput", output_schema_ref="ModuleResult",
                required_permissions=[], operation_level=OperationLevel.READ, side_effect=False,
                confirmation_policy="none", timeout_ms=1000, retry_policy="read_only", handler_ref="test")]),
            lambda _trusted, saver, _trace: BudgetStandIn(saver))

    app = make_app(tmp_path, prepare=prepare)
    env.app, env.api = app, app.state.api
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    worker = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    worker.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{sock.getsockname()[1]}", timeout=10) as client:
            env.client = client
            session = enter(client)
            env.identity = Identity("U1", session["session_id"], "D1", "user")
            env.thread = post(client, "/threads").json()["data"]["thread_id"]
            env.who = TrustedContext(user_id="U1", session_id=session["session_id"],
                task_id="T1", run_id="R1", demo_round_id="D1", parent_task_id=None)
            initial = candidate(env.who)
            snapshot = {"capability_name": "cross.start_task", "config_version": "test-v1",
                        "trace_id": str(uuid4()), "intent_text": "budget stand-in",
                        "result": initial.model_dump(mode="json")}
            store = env.api.runtime.application
            task = store.create_task("T1", "U1", session["session_id"], "D1", "R1", initial.status, snapshot)
            store.update_task("U1", "D1", "T1", task.revision, "R1", initial.status, None, snapshot)
            env.api.store.write("""INSERT INTO api_tasks
                (task_id,thread_id,user_id,session_id,demo_round_id,run_id,created_at,request_id,intent_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("T1", env.thread, "U1", session["session_id"], "D1", "R1",
                 datetime.now(timezone.utc).isoformat(), str(uuid4()), "budget stand-in"))
            env.request_id = str(uuid4())
            env.body = {"request_id": env.request_id, "interaction_id": "I1", "selected_option_id": "A"}
            env.task = lambda: env.api.runtime.application.get_task("U1", "D1", "T1")
            env.record = lambda: env.api.runtime.harness.budget_input_record(env.who, env.request_id)
            env.answer = lambda **changes: post(client, "/tasks/T1/inputs", **(env.body | changes))
            env.business = lambda: BudgetStandIn(env.api.runtime.memory.checkpointer(
                env.api.memory_context(env.identity), "T1")).load(env.task().checkpoint_thread_id)[1]
            yield env
            assert bank_counts(tmp_path) == (0, 0)
    finally:
        server.should_exit = True
        worker.join(timeout=5)


def test_f10_has_real_durable_source_and_replays_same_response(budget_api):
    e = budget_api
    first = e.answer()
    assert first.status_code == 200, first.text
    assert first.json()["data"]["data"] == {"stand_in": True}
    assert first.json()["data"]["task_revision"] == e.record()["completion"]["task_revision"]
    assert e.record()["input_request_id"] == e.request_id
    assert e.origins[0] is not None and e.business()["adoptions"] == 1
    assert e.answer().json() == first.json() and e.calls == 1
    assert "origin_id" not in first.text and "budget_input_origins" not in first.text
    assert e.answer(selected_option_id="M").status_code == 409
    assert e.answer(request_id=str(uuid4())).status_code == 409


def test_model_choice_and_forged_source_never_get_current_origin(budget_api):
    e = budget_api
    assert e.answer(source="human").status_code == 400
    assert e.answer(origin_id=str(uuid4())).status_code == 400
    e.api.runtime.harness.planner.proposal = ContinueProposal(task_id="T1", task_revision=e.task().revision,
        action="provide_input", selected_option_id="A")
    sent = post(e.client, f"/threads/{e.thread}/messages", text="继续")
    assert sent.status_code == 202
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = e.api.store.rows("SELECT status FROM api_message_jobs WHERE user_message_id=?",
                              (sent.json()["data"]["message_id"],))[0]
        if job["status"] == "task_completed":
            break
        time.sleep(0.02)
    assert job["status"] == "task_completed"
    assert e.origins == [None] and e.record() is None and not e.business()
    assert e.answer().status_code == 200 and e.business()["adoptions"] == 1


@pytest.mark.parametrize("changes", [{"interaction_id": "old"}, {"selected_option_id": "forged"},
                                      {"text": "采用"}])
def test_stale_or_mixed_answers_have_no_source(budget_api, changes):
    e = budget_api
    response = e.answer(**changes)
    assert response.status_code in {400, 409}
    assert e.record() is None and e.calls == 0


def test_lost_receipt_without_origin_is_not_retryable(budget_api):
    e = budget_api
    e.api.store.receipt(e.identity, "/api/v1/tasks/T1/inputs", e.request_id, e.body)
    assert e.answer().status_code == 409
    assert e.record() is None and e.calls == 0


def test_origin_saved_before_dispatch_recovers_after_service_reopen(budget_api, monkeypatch):
    e = budget_api
    with monkeypatch.context() as m:
        m.setattr(e.api.runtime.harness, "_resume", lambda *_: (_ for _ in ()).throw(OSError("before module")))
        assert e.answer().status_code == 503
    original = e.record()
    e.api = ApiService(e.api.runtime, e.api.config)
    e.app.state.api = e.api
    assert e.answer().status_code == 200
    assert e.calls == 1 and e.business()["adoptions"] == 1
    assert e.record()["origin_id"] == original["origin_id"]
    assert e.record()["accepted_at"] == original["accepted_at"]


@pytest.mark.parametrize("stage", ["before_attempt", "after_attempt"])
def test_unadopted_fault_cannot_refresh_old_revision_to_write(budget_api, stage):
    e = budget_api
    e.fail = stage
    assert e.answer().status_code == 503
    e.fail = None
    assert e.answer().status_code == 409
    assert e.calls == 1 and e.business().get("adoptions", 0) == 0


@pytest.mark.parametrize("cancelled", [False, True])
def test_historical_fact_recovers_before_current_input_validation(budget_api, cancelled):
    e = budget_api
    e.fail = "after_adopt"
    assert e.answer().status_code == 503
    assert e.task().status is TaskStatus.NEEDS_ATTENTION
    assert e.task().snapshot["result"]["interaction"] is None
    if cancelled:
        task = e.task()
        result = ModuleResult.model_validate(task.snapshot["result"]).model_copy(update={
            "status": TaskStatus.CANCELLED, "allowed_actions": [],
            "recovery_required": False, "recovery_reason": None})
        e.api.runtime.application.update_task("U1", "D1", "T1", task.revision, task.run_id,
            result.status, task.checkpoint_id, {**task.snapshot, "result": result.model_dump(mode="json")})
        e.api.store.write("UPDATE api_tasks SET cancel_requested=1 WHERE task_id='T1'")
    e.fail = None
    done = e.answer()
    assert done.status_code == 200 and done.json()["data"]["status"] == "succeeded"
    assert e.task().status is (TaskStatus.CANCELLED if cancelled else TaskStatus.NEEDS_ATTENTION)
    assert e.calls == 1 and e.business()["adoptions"] == 1
    assert e.api.runtime.harness.budget_input_origin(e.who) is None


@pytest.mark.parametrize("stage", ["publication", "receipt"])
def test_completed_source_survives_api_publication_faults(budget_api, monkeypatch, stage):
    e = budget_api
    with monkeypatch.context() as m:
        target = e.api.store
        method = "publish_budget_input" if stage == "publication" else "finish"
        m.setattr(target, method, lambda *_: (_ for _ in ()).throw(OSError("publication interrupted")))
        assert e.answer().status_code == 503
    assert e.record()["phase"] == "completed"
    first = e.answer()
    assert first.status_code == 200 and e.answer().json() == first.json()
    assert e.calls == 1 and e.business()["adoptions"] == 1
    assert len(e.api.store.rows("SELECT * FROM api_messages WHERE thread_id=?", (e.thread,))) == 1


@pytest.mark.parametrize("lost_at", ["receipt", "publication"])
def test_original_completion_does_not_publish_old_plan_as_current(budget_api, monkeypatch, lost_at):
    e = budget_api
    with monkeypatch.context() as m:
        method = "finish" if lost_at == "receipt" else "publish_budget_input"
        m.setattr(e.api.store, method, lambda *_: (_ for _ in ()).throw(OSError("publication lost")))
        assert e.answer().status_code == 503
    initial_events = e.api.store.rows("SELECT event_id,event_json FROM api_events ORDER BY sequence")
    task = e.task()
    newer = candidate(e.who, interaction="NEW", plan=8, limit=90000)
    e.api.runtime.application.update_task("U1", "D1", "T1", task.revision, "R2", newer.status,
        task.checkpoint_id, {**task.snapshot, "result": newer.model_dump(mode="json")})
    reply = e.answer()
    assert reply.status_code == 200 and reply.json()["data"]["status"] == "succeeded"
    current = e.client.get("/api/v1/tasks/T1").json()["data"]
    assert current["data"]["plan_revision"] == 8
    assert reply.json()["data"]["task_revision"] < current["task_revision"]
    assert e.business()["adoptions"] == e.calls == 1
    events = e.api.store.rows("SELECT event_id,event_json FROM api_events ORDER BY sequence")
    if lost_at == "receipt":
        assert events == initial_events  # Whole published batch, not per-event deduplication.
    else:
        published = [json.loads(row["event_json"]) for row in events]
        updated = next(item for item in published if item["event_type"] == "task_updated")
        interaction = next(item for item in published if item["event_type"] == "interaction_required")
        assert updated["payload"]["data"]["plan_revision"] == 8
        assert interaction["payload"]["interaction"]["interaction_id"] == "NEW"


def test_wrong_actor_round_task_and_expired_session_cannot_use_source(budget_api):
    e = budget_api
    assert e.answer().status_code == 200
    assert post(e.client, "/tasks/MISSING/inputs", **e.body).status_code == 404
    original_cookie = e.client.cookies.get("bank_session")
    now = datetime.now(timezone.utc)
    for user, round_id, session in [("U2", "D1", "S2"), ("U1", "D2", "S3")]:
        e.api.runtime.application.create_session(session, user, round_id, now.isoformat(),
                                                (now + timedelta(hours=1)).isoformat())
        e.api.store.write("INSERT INTO api_sessions VALUES (?, ?)", (session, "user"))
        e.client.cookies.clear()
        e.client.cookies.set("bank_session", e.api.cookie(session))
        assert e.answer().status_code in {401, 404}
    e.client.cookies.clear()
    e.client.cookies.set("bank_session", original_cookie)
    e.api.store.write("UPDATE sessions SET expires_at=? WHERE session_id=?",
                      ((now - timedelta(hours=1)).isoformat(), e.identity.session_id))
    assert e.answer().status_code == 401 and e.calls == 1


@pytest.mark.parametrize("text", ["1500", "2026-10-30", "配送引用 ref-demo"])
def test_ordinary_cross_text_keeps_original_protocol(budget_api, text):
    e = budget_api
    response = post(e.client, "/tasks/T1/inputs", interaction_id="I1", text=text)
    assert response.status_code == 200
    assert e.origins == [None] and e.record() is None


def test_competing_http_requests_accept_one_origin(budget_api):
    e = budget_api
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda req: e.answer(request_id=req), [str(uuid4()), str(uuid4())]))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert len(e.task().snapshot["budget_input_origins"]) == e.calls == e.business()["adoptions"] == 1


def test_modify_and_old_interaction_cannot_adopt_the_new_plan(budget_api):
    e = budget_api
    assert e.answer(selected_option_id="M").status_code == 200
    assert not e.business()
    assert e.answer(selected_option_id="M").status_code == 200 and e.calls == 1
    assert e.answer(selected_option_id="A").status_code == 409
    assert e.answer(request_id=str(uuid4())).status_code == 409
    assert e.answer(request_id=str(uuid4()), interaction_id="I2").status_code == 200
    assert e.business()["adoptions"] == 1
    assert len(e.task().snapshot["budget_input_origins"]) == 2


def test_publication_transaction_rolls_back_partial_messages_and_events(budget_api):
    e = budget_api
    e.api.store.write("""CREATE TRIGGER fail_budget_publication BEFORE INSERT ON api_events
        WHEN NEW.event_json LIKE '%message_completed%'
        BEGIN SELECT RAISE(ABORT, 'publication fault'); END""")
    assert e.answer().status_code == 503
    assert not e.api.store.rows("SELECT * FROM api_messages WHERE thread_id=?", (e.thread,))
    assert not e.api.store.rows("SELECT * FROM api_events WHERE event_json LIKE '%T1%'")
    e.api.store.write("DROP TRIGGER fail_budget_publication")
    assert e.answer().status_code == 200
    assert e.calls == e.business()["adoptions"] == 1
    assert len(e.api.store.rows("SELECT * FROM api_messages WHERE thread_id=?", (e.thread,))) == 1


def test_pending_old_session_origin_is_not_new_session_permission(budget_api, monkeypatch):
    e = budget_api
    with monkeypatch.context() as m:
        m.setattr(e.api.runtime.harness, "_resume", lambda *_: (_ for _ in ()).throw(OSError("before module")))
        assert e.answer().status_code == 503
    e.client.cookies.clear()
    new_session = enter(e.client)["session_id"]
    assert e.answer().status_code == 409  # Existing API recovery gate.
    task = e.task()
    e.api.runtime.application.transition_task_session("U1", "D1", "T1",
        e.identity.session_id, new_session, task.revision)
    e.api.store.write("UPDATE api_tasks SET session_id=? WHERE task_id='T1'", (new_session,))
    e.identity = Identity("U1", new_session, "D1", "user")
    assert e.answer().status_code == 409
    assert e.calls == 0 and not e.business()
