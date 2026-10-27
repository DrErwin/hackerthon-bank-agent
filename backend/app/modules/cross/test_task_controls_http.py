"""F11/F13 on real ASGI, Harness, children and bank; no planner calls."""

from contextlib import closing
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.agent_platform.model import TransferProposal
from app.agent_platform.test_local_demo import app_for, configuration
from app.api.test_app import approve, enter, post
from app.contracts.bank import BankError, QueryFailure
from app.contracts.platform import TrustedContext
from app.memory.adapter import MemoryContext
from app.storage.database import connect


@pytest.fixture()
def http_env(tmp_path):
    app = app_for(configuration(tmp_path), response_mode="none")
    api = app.state.api
    api.runtime.harness.planner.select = Mock(side_effect=AssertionError("MODEL_MUST_NOT_RUN"))
    try:
        with TestClient(app) as client:
            enter(client)
            yield client, api
    finally:
        api.runtime.close()


def parent(http_env, goal="最近钱花得快，帮我处理不用的扣费"):
    client, api = http_env
    who = api.identity(client.cookies.get("bank_session"))
    task_id, request_id = str(uuid4()), uuid4()
    thread = post(client, "/threads").json()["data"]["thread_id"]
    trusted = TrustedContext(user_id=who.user_id, session_id=who.session_id,
        demo_round_id=who.demo_round_id, task_id=task_id, run_id="PARENT-RUN", parent_task_id=None)
    api.runtime.application.create_task(task_id, who.user_id, who.session_id,
        who.demo_round_id, trusted.run_id, "running", {
            "capability_name": "cross.start_task", "trace_id": str(uuid4()),
            "request_id": str(request_id), "intent_text": goal,
            "config_version": api.runtime.harness.planner.config_version,
            "proposal": TransferProposal(capability_name="cross.start_task").model_dump(mode="json"),
        })
    api.store.write("INSERT INTO api_tasks (task_id,thread_id,user_id,session_id,demo_round_id,"
                    "run_id,created_at,request_id,intent_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, thread, who.user_id, who.session_id, who.demo_round_id,
         trusted.run_id, datetime.now(timezone.utc).isoformat(), str(request_id), goal))
    api.runtime.harness.handle_message(trusted, request_id, goal)
    api.publish_task(who, task_id)
    return client.get(f"/api/v1/tasks/{task_id}").json()["data"]


def choose(client, task, label):
    option = next(item["id"] for item in task["interaction"]["options"] if label in item["label"])
    return post(client, f"/tasks/{task['task_id']}/inputs",
        interaction_id=task["interaction"]["interaction_id"], selected_option_id=option)


def cancellation(client, menu):
    response = choose(client, menu, "优酷")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "running"
    children = client.get(f"/api/v1/tasks/{menu['task_id']}/children").json()["data"]
    child = next(item for item in children if item["status"] == "waiting_approval")
    return child


def verify(client, child):
    waiting = approve(client, child)
    assert waiting["interaction"]["kind"] == "verification"
    ref = waiting["interaction"]["record_ref"]
    code = client.get(f"/api/v1/verifications/{ref}/demo-code").json()["data"]["code"]
    response = post(client, f"/verifications/{ref}/code", submission_id=str(uuid4()), code=code)
    assert response.status_code == 200, response.text
    return response.json()["data"]["task"]


def operations(api):
    with closing(connect(api.runtime.gateway._bank.store.path)) as connection:
        return [dict(row) for row in connection.execute(
            "SELECT operation_id, status FROM bank_operations WHERE action_name='bank.cancel_subscription'")]


def state(api, task_id):
    task = api.runtime.application.get_task("U1", "D1", task_id)
    saved = api.runtime.memory.checkpointer(MemoryContext("U1", task.session_id,
        "D1"), task_id).get_tuple({"configurable": {"thread_id": task.checkpoint_thread_id}})
    return saved.checkpoint["channel_values"]["cross_state"]


def test_completed_cancel_child_parent_http_resume_reconciles_once(http_env):
    client, api = http_env
    menu = parent(http_env)
    child = cancellation(client, menu)
    assert verify(client, child)["status"] == "succeeded"
    before = operations(api)
    assert len(before) == 1
    request_id = str(uuid4())
    resumed = post(client, f"/tasks/{menu['task_id']}/resume", request_id=request_id)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["data"]["status"] == "waiting_input"
    assert state(api, menu["task_id"])["receipts"][0]["subscription_id"] == "sub_001"
    replay = post(client, f"/tasks/{menu['task_id']}/resume", request_id=request_id)
    assert replay.json() == resumed.json()
    assert operations(api) == before
    api.runtime.harness.planner.select.assert_not_called()


def test_parent_resume_preserves_child_waiting_for_confirmation(http_env):
    client, api = http_env
    menu = parent(http_env)
    child = cancellation(client, menu)
    ref = child["interaction"]["record_ref"]
    confirmation = client.get(f"/api/v1/confirmations/{ref}").json()["data"]
    resumed = post(client, f"/tasks/{menu['task_id']}/resume")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["data"]["data"]["interaction_task_id"] == child["task_id"]
    assert client.get(f"/api/v1/confirmations/{ref}").json()["data"] == confirmation
    assert operations(api) == []


@pytest.mark.parametrize("goal", ["帮我减少不用的开销", "养老金到了，帮我安排本月的钱"])
def test_generic_resume_keeps_current_menu_and_query_cannot_skip_it(http_env, goal):
    client, api = http_env
    menu = parent(http_env, goal)
    assert menu["status"] == "waiting_input"
    resumed = post(client, f"/tasks/{menu['task_id']}/resume")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["data"]["interaction"] == menu["interaction"]
    query = post(client, f"/tasks/{menu['task_id']}/query-result")
    assert query.status_code == 409
    assert operations(api) == []


def test_stale_menu_cancel_and_terminal_query_keep_existing_boundaries(http_env):
    client, api = http_env
    menu = parent(http_env)
    child = cancellation(client, menu)
    stale = choose(client, menu, "优酷")
    assert stale.status_code == 409
    cancelled = post(client, f"/tasks/{menu['task_id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    query = post(client, f"/tasks/{menu['task_id']}/query-result")
    assert query.status_code == 200, query.text
    assert query.json()["data"]["status"] == "cancelled"
    assert operations(api) == []


def test_unknown_child_parent_resume_waits_and_child_query_uses_original_operation(http_env):
    client, api = http_env
    menu = parent(http_env)
    child = cancellation(client, menu)
    original = api.runtime.gateway.cancel_subscription

    def lose_response(*args, **kwargs):
        result = original(*args, **kwargs)
        assert result.operation_status.value == "succeeded"
        return QueryFailure(kind="error", error=BankError(code="CALL_TIMEOUT", details={}))

    with patch.object(api.runtime.gateway, "cancel_subscription", side_effect=lose_response) as write:
        unknown = verify(client, child)
        assert unknown["status"] == "needs_attention"
        original_operations = operations(api)
        assert len(original_operations) == 1
        resumed = post(client, f"/tasks/{menu['task_id']}/resume")
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["data"]["data"]["interaction_task_id"] == child["task_id"]
        assert write.call_count == 1
        assert post(client, f"/tasks/{menu['task_id']}/query-result").status_code == 409
        queried = post(client, f"/tasks/{child['task_id']}/query-result")
        assert queried.status_code == 200, queried.text
        assert queried.json()["data"]["status"] == "succeeded"
        assert write.call_count == 1
    assert post(client, f"/tasks/{menu['task_id']}/resume").status_code == 200
    assert operations(api) == original_operations
