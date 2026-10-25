"""Ticket v05-cross-platform/04: parent-child task API over the generic endpoints."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.contracts.common import OperationLevel, TaskStatus
from app.contracts.platform import (
    CapabilityDefinition, ModuleManifest, StartTransferInput, TrustedContext,
)
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult

from .service import Identity
from .store import ApiProblem
from .test_app import enter, make_app, post


NOW = datetime.now(timezone.utc)
ORIGIN = {"Origin": "http://testserver"}

# Ticket 11: responses the scripted modules actually received. Cleared by the
# tests that assert on it so a shared list cannot hide a wrong payload.
RESUMED: list[dict] = []


class ScriptedEntry:
    def __init__(self, script):
        self.script = script

    def _next(self, trusted):
        return self.script.pop(0).model_copy(
            update={"task_id": trusted.task_id, "run_id": trusted.run_id},
        )

    def start(self, trusted, request, *, thread_id=None):
        return self._next(trusted)

    def resume(self, trusted, response, *, thread_id=None):
        RESUMED.append(response)
        return self._next(trusted)

    def recover_session(self, trusted, *, source_session_id, thread_id=None):
        return self._next(trusted)

    def checkpoint_context(self, trusted, *, thread_id=None):
        return None


def _manifest(module: str, capability: str, level: OperationLevel, side_effect: bool) -> ModuleManifest:
    return ModuleManifest(
        module_name=module, version="v1", owner="test", description=module,
        implementation_kind="workflow", capabilities=[CapabilityDefinition(
            name=capability, input_schema_ref="StartTransferInput#1",
            output_schema_ref="ModuleResult#1", required_permissions=[],
            operation_level=level, side_effect=side_effect,
            confirmation_policy="per_action" if side_effect else "none",
            timeout_ms=60000, retry_policy="none", handler_ref="test",
        )], dependencies=[],
    )


def register_scripted(runtime, module: str, capability: str, script,
                      level=OperationLevel.SENSITIVE, side_effect=True):
    def factory(_trusted, _saver, _trace):
        return ScriptedEntry(script)

    runtime.harness.registry.register_module(
        _manifest(module, capability, level, side_effect), factory,
    )


def waiting_input():
    return "waiting_input", ModuleResult(
        task_id="c", run_id="c", status=TaskStatus.WAITING_INPUT, data=None,
        message="请补充金额。", interaction=InteractionRequest(
            interaction_id="CI1", kind="input", prompt="金额",
            required_fields=["amount_fen"], options=[], record_ref=None,
        ), error=None, allowed_actions=["provide_input", "cancel"],
        recovery_required=False, recovery_reason=None,
    )


def succeeded():
    return ModuleResult(
        task_id="c", run_id="c", status=TaskStatus.SUCCEEDED, data=None,
        message="办好了。", interaction=None, error=None, allowed_actions=[],
        recovery_required=False, recovery_reason=None,
    )


def cancelled_result(task_id="c"):
    return ModuleResult(
        task_id=task_id, run_id="c", status=TaskStatus.CANCELLED, data=None,
        message="已停止后续步骤。", interaction=None, error=None,
        allowed_actions=[], recovery_required=False, recovery_reason=None,
    )


def waiting_approval(kind: str, record_ref: str, interaction_id: str):
    """A dispatched child whose next answer belongs to the security service."""
    return ModuleResult(
        task_id="c", run_id="c", status=TaskStatus.WAITING_APPROVAL, data=None,
        message="请确认。" if kind == "confirmation" else "请验证。",
        interaction=InteractionRequest(
            interaction_id=interaction_id, kind=kind, prompt="请确认。",
            required_fields=[], options=[], record_ref=record_ref,
        ),
        error=None,
        allowed_actions=["confirm", "cancel"] if kind == "confirmation" else ["verify", "cancel"],
        recovery_required=False, recovery_reason=None,
    )


def cross_waiting_input(interaction_id="CX1", option_id="OPT_APPLY"):
    """Ticket 11 G2: a cross parent menu (options plus free-text answers)."""
    return ModuleResult(
        task_id="XPARENT", run_id="PR1", status=TaskStatus.WAITING_INPUT, data=None,
        message="采用这个安排吗？",
        interaction=InteractionRequest(
            interaction_id=interaction_id, kind="input", prompt="采用这个安排吗？",
            required_fields=["cross_selection"],
            options=[InteractionOption(id=option_id, label="采用这个安排")], record_ref=None,
        ),
        error=None, allowed_actions=["provide_input", "cancel"],
        recovery_required=False, recovery_reason=None,
    )


@pytest.fixture
def cross_app(tmp_path):
    import socket
    import threading
    import time

    import httpx
    import uvicorn

    child_script: list[ModuleResult] = []
    parent_script: list[ModuleResult] = []

    def prepare(runtime):
        register_scripted(runtime, "cross", "cross.test_write", child_script)
        register_scripted(
            runtime, "cross", "cross.test_parent", parent_script,
            level=OperationLevel.READ, side_effect=False,
        )

    application = make_app(tmp_path, prepare=prepare)
    # TestClient stalls on this app's SSE endpoint on Windows, so like the
    # existing SSE tests, drive a real local server and stop it afterwards.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(application, log_level="error", access_log=False))
    worker = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    worker.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10) as client:
            session = enter(client)
            api = application.state.api
            thread = post(client, "/threads").json()["data"]["thread_id"]

            def add_parent(task_id="XPARENT", *, result=None):
                api.runtime.application.create_task(
                    task_id, "U1", session["session_id"], "D1", "PR1", "running",
                    {"capability_name": "cross.test_parent", "trace_id": str(uuid4()),
                     "request_id": str(uuid4()), "intent_text": "parent goal",
                     "config_version": "test-v1",
                     **({"result": result.model_dump(mode="json")} if result else {})},
                )
                api.store.write(
                    "INSERT INTO api_tasks (task_id,thread_id,user_id,session_id,demo_round_id,"
                    "run_id,created_at,request_id,intent_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (task_id, thread, "U1", session["session_id"], "D1", "PR1",
                     NOW.isoformat(), str(uuid4()), "parent goal"),
                )
                return TrustedContext(user_id="U1", session_id=session["session_id"],
                                      task_id=task_id, run_id="PR1", parent_task_id=None,
                                      demo_round_id="D1")

            yield client, api, child_script, parent_script, add_parent, thread
    finally:
        server.should_exit = True
        worker.join(timeout=5)


def test_children_endpoint_binds_submissions_to_the_real_child(cross_app):
    client, api, child_script, _parent_script, add_parent, thread = cross_app
    parent = add_parent()
    child_script.append(waiting_input()[1])
    child = api.runtime.harness.dispatch_child(
        parent, "cross.test_write", uuid4(),
        StartTransferInput(request_id=uuid4(), intent_text="child pay"),
        step_id="pay_1", plan_revision=1,
    )
    assert child.interaction.interaction_id == "CI1"

    listed = client.get(f"/api/v1/tasks/{parent.task_id}/children", headers=ORIGIN)
    assert listed.status_code == 200
    items = listed.json()["data"]
    assert [item["task_id"] for item in items] == [child.task_id]
    assert items[0]["status"] == "waiting_input"
    # The registered child answers on the generic task path and appears in listings.
    single = client.get(f"/api/v1/tasks/{child.task_id}", headers=ORIGIN)
    assert single.status_code == 200 and single.json()["data"]["status"] == "waiting_input"
    tasks = client.get("/api/v1/tasks", headers=ORIGIN).json()["data"]["items"]
    assert child.task_id in {item["task_id"] for item in tasks}

    child_script.append(succeeded())
    request_id = str(uuid4())
    answered = client.post(
        f"/api/v1/tasks/{child.task_id}/inputs",
        json={"request_id": request_id, "interaction_id": "CI1", "text": "100 元"},
        headers=ORIGIN,
    )
    assert answered.status_code == 200
    assert answered.json()["data"]["status"] == "succeeded"
    # A duplicate submission replays the saved receipt and never advances twice.
    replay = client.post(
        f"/api/v1/tasks/{child.task_id}/inputs",
        json={"request_id": request_id, "interaction_id": "CI1", "text": "100 元"},
        headers=ORIGIN,
    )
    assert replay.status_code == 200 and replay.json() == answered.json()
    assert child_script == []
    assert client.get(
        f"/api/v1/tasks/{parent.task_id}/children", headers=ORIGIN,
    ).json()["data"][0]["status"] == "succeeded"

    # HTTP and SSE agree on the child's state.
    import json as _json
    updated = []
    with client.stream("GET", f"/api/v1/threads/{thread}/events", headers=ORIGIN) as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                event = _json.loads(line[6:])
                payload = event.get("payload", {})
                if event["event_type"] == "task_updated" and payload.get("task_id") == child.task_id:
                    updated.append(payload)
                    if payload["status"] == "succeeded":
                        break
    assert updated and updated[-1]["status"] == "succeeded"


def test_stale_interaction_wrong_owner_and_relogin_are_rejected(cross_app):
    client, api, child_script, _parent_script, add_parent, _thread = cross_app
    parent = add_parent()
    child_script.append(waiting_input()[1])
    child = api.runtime.harness.dispatch_child(
        parent, "cross.test_write", uuid4(),
        StartTransferInput(request_id=uuid4(), intent_text="child pay"),
        step_id="pay_1", plan_revision=1,
    )
    # The page first reads the parent's children, which registers the child.
    assert client.get(
        f"/api/v1/tasks/{parent.task_id}/children", headers=ORIGIN,
    ).status_code == 200
    stale = client.post(
        f"/api/v1/tasks/{child.task_id}/inputs",
        json={"request_id": str(uuid4()), "interaction_id": "CI9", "text": "100 元"},
        headers=ORIGIN,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "INTERACTION_STALE"
    assert len(child_script) == 0
    # A child nobody has registered yet answers with the generic 404.
    assert client.post(
        "/api/v1/tasks/never-registered/inputs",
        json={"request_id": str(uuid4()), "interaction_id": "CI1", "text": "1"},
        headers=ORIGIN,
    ).status_code == 404

    # A parent outside this user/round scope is invisible, not merely forbidden.
    foreign = client.get("/api/v1/tasks/XPARENT2/children", headers=ORIGIN)
    assert foreign.status_code == 404

    # A fresh session must not submit on the child directly.
    client.cookies.clear()
    reentered = enter(client)
    assert reentered["session_id"] != parent.session_id
    moved = client.post(
        f"/api/v1/tasks/{child.task_id}/inputs",
        json={"request_id": str(uuid4()), "interaction_id": "CI1", "text": "100 元"},
        headers=ORIGIN,
    )
    assert moved.status_code == 409
    assert moved.json()["error"]["code"] == "SESSION_RECONFIRMATION_REQUIRED"
    assert len(child_script) == 0


def test_parent_cancel_stops_new_steps_and_keeps_children_visible(cross_app):
    client, api, child_script, parent_script, add_parent, _thread = cross_app
    parent_result = ModuleResult(
        task_id="XPARENT", run_id="PR1", status=TaskStatus.RUNNING, data=None,
        message="进行中", interaction=None, error=None,
        allowed_actions=["cancel"], recovery_required=False, recovery_reason=None,
    )
    parent = add_parent(result=parent_result)
    child_script.append(waiting_input()[1])
    child = api.runtime.harness.dispatch_child(
        parent, "cross.test_write", uuid4(),
        StartTransferInput(request_id=uuid4(), intent_text="child pay"),
        step_id="pay_1", plan_revision=1,
    )

    parent_script.append(cancelled_result("XPARENT"))
    cancelled = post(client, f"/tasks/{parent.task_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"

    items = client.get(f"/api/v1/tasks/{parent.task_id}/children", headers=ORIGIN).json()["data"]
    assert [item["task_id"] for item in items] == [child.task_id]
    assert items[0]["status"] == "waiting_input"
    # After the parent stops, no further child step may be dispatched.
    child_script.append(waiting_input()[1])
    with pytest.raises(ValueError, match="CHILD_STEP_ALREADY_ACTIVE"):
        api.runtime.harness.dispatch_child(
            parent, "cross.test_write", uuid4(),
            StartTransferInput(request_id=uuid4(), intent_text="child pay 2"),
            step_id="pay_2", plan_revision=1,
        )
    assert len(child_script) == 1


def test_child_confirmation_and_verification_records_reach_the_generic_endpoints(cross_app):
    """Ticket 11 G1: a dispatched child's record must be readable through F14—F17.

    The child is only published by the API when the parent's children are read,
    so registering its interaction record is the missing half of §6.5.
    """

    client, api, child_script, _parent_script, add_parent, _thread = cross_app
    parent = add_parent()
    identity = Identity("U1", parent.session_id, "D1", "user")

    child_script.append(waiting_approval("confirmation", "CONF-CHILD", "CA1"))
    confirmation_child = api.runtime.harness.dispatch_child(
        parent, "cross.test_write", uuid4(),
        StartTransferInput(request_id=uuid4(), intent_text="child cancel subscription"),
        step_id="cancel_1", plan_revision=1,
    )
    # Before the parent's children are read, the record is unknown to the API.
    with pytest.raises(ApiProblem) as missing:
        api.record_context(identity, "confirmation", "CONF-CHILD")
    assert missing.value.status == 404
    assert missing.value.code == "NOT_FOUND"

    assert client.get(
        f"/api/v1/tasks/{parent.task_id}/children", headers=ORIGIN,
    ).status_code == 200
    trusted = api.record_context(identity, "confirmation", "CONF-CHILD")
    assert trusted.task_id == confirmation_child.task_id
    # The public route now reaches the security service instead of the missing
    # record registry, so it answers 409 (stale/unknown) rather than the old 404.
    routed = client.get("/api/v1/confirmations/CONF-CHILD", headers=ORIGIN)
    assert routed.status_code == 409
    assert routed.json()["error"]["code"].startswith("CONFIRMATION_")

    # Reading the children again is idempotent and never re-binds the record.
    assert client.get(
        f"/api/v1/tasks/{parent.task_id}/children", headers=ORIGIN,
    ).status_code == 200
    rows = api.store.rows(
        "SELECT task_id FROM api_records WHERE kind=? AND record_id=?",
        ("confirmation", "CONF-CHILD"),
    )
    assert [row["task_id"] for row in rows] == [confirmation_child.task_id]

    # The same seam covers a waiting verification challenge.
    other = add_parent(task_id="XPARENT3")
    child_script.append(waiting_approval("verification", "CHAL-CHILD", "CV1"))
    verification_child = api.runtime.harness.dispatch_child(
        other, "cross.test_write", uuid4(),
        StartTransferInput(request_id=uuid4(), intent_text="child transfer"),
        step_id="pay_3", plan_revision=1,
    )
    assert client.get(
        f"/api/v1/tasks/{other.task_id}/children", headers=ORIGIN,
    ).status_code == 200
    assert api.record_context(
        identity, "verification", "CHAL-CHILD",
    ).task_id == verification_child.task_id


def test_cross_parent_text_answer_reaches_the_module(cross_app):
    """Ticket 11 G2: amounts, dates and references typed by the user get through.

    The cross module owns the grammar (parse and clarify); the API only forwards
    the text, so an amount like "1500" is no longer rejected as a chat code.
    """

    client, _api, _child_script, parent_script, add_parent, _thread = cross_app
    parent = add_parent(result=cross_waiting_input())
    RESUMED.clear()
    parent_script.append(succeeded())
    answered = client.post(
        f"/api/v1/tasks/{parent.task_id}/inputs",
        json={"request_id": str(uuid4()), "interaction_id": "CX1", "text": "1500"},
        headers=ORIGIN,
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["data"]["status"] == "succeeded"
    assert RESUMED == [{"text": "1500"}]


def test_cross_text_answer_still_rejects_labelled_verification_codes(cross_app):
    """Ticket 11: forwarding cross text must not become a code-entry backdoor.

    The cross branch only relaxes the bare 4—8 digit guard; a labelled credential
    is still refused before the module sees it and the task does not move.
    """

    client, _api, _child_script, parent_script, add_parent, _thread = cross_app
    parent = add_parent(result=cross_waiting_input())
    RESUMED.clear()
    rejected = client.post(
        f"/api/v1/tasks/{parent.task_id}/inputs",
        json={"request_id": str(uuid4()), "interaction_id": "CX1", "text": "验证码是 123456"},
        headers=ORIGIN,
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "USE_VERIFICATION_ENDPOINT"
    assert RESUMED == []
    assert parent_script == []
    current = client.get(f"/api/v1/tasks/{parent.task_id}", headers=ORIGIN).json()["data"]
    assert current["status"] == "waiting_input"
    assert current["interaction"]["interaction_id"] == "CX1"


def test_cross_parent_option_answer_keeps_the_choice_contract(cross_app):
    """The option path still answers exactly as before; text and option never mix."""

    client, _api, _child_script, parent_script, add_parent, _thread = cross_app
    parent = add_parent(result=cross_waiting_input())
    RESUMED.clear()
    conflicted = client.post(
        f"/api/v1/tasks/{parent.task_id}/inputs",
        json={
            "request_id": str(uuid4()), "interaction_id": "CX1",
            "selected_option_id": "OPT_APPLY", "text": "1500",
        },
        headers=ORIGIN,
    )
    assert conflicted.status_code == 400
    assert conflicted.json()["error"]["code"] == "INVALID_OPTION"
    assert parent_script == []
    assert RESUMED == []

    RESUMED.clear()
    parent_script.append(succeeded())
    chosen = client.post(
        f"/api/v1/tasks/{parent.task_id}/inputs",
        json={"request_id": str(uuid4()), "interaction_id": "CX1",
              "selected_option_id": "OPT_APPLY"},
        headers=ORIGIN,
    )
    assert chosen.status_code == 200, chosen.text
    assert RESUMED == [{"choice": "OPT_APPLY"}]
