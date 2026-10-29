"""Resume consumers use real Cross/Harness/HTTP/bank; only planning is scripted."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.agent_platform.model import ContinueProposal, TransferProposal
from app.agent_platform.test_local_demo import app_for, configuration

from .test_app import approve, bank_counts, post, start


@pytest.fixture
def running_expense(tmp_path, monkeypatch):
    app = app_for(configuration(tmp_path))
    runtime = app.state.api.runtime
    planner = Mock(return_value=TransferProposal(capability_name="cross.start_task"))
    monkeypatch.setattr(runtime.harness.planner, "select", planner)
    with TestClient(app) as client:
        thread, menu = start(client, "最近钱花得快，帮我处理不用的扣费")
        assert menu["status"] == "waiting_input", menu
        options = [item for item in menu["interaction"]["options"] if "优酷" in item["label"]]
        assert len(options) == 1
        response = post(client, f"/tasks/{menu['task_id']}/inputs",
                        interaction_id=menu["interaction"]["interaction_id"],
                        selected_option_id=options[0]["id"])
        assert response.status_code == 200, response.text
        parent = response.json()["data"]
        child_id = parent["data"]["interaction_task_id"]
        children = client.get(f"/api/v1/tasks/{parent['task_id']}/children").json()["data"]
        child = next(item for item in children if item["task_id"] == child_id)
        verifying = approve(client, child)
        challenge = verifying["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        completed = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
        assert completed.status_code == 200, completed.text
        assert completed.json()["data"]["task"]["status"] == "succeeded", completed.text
        parent = client.get(f"/api/v1/tasks/{parent['task_id']}").json()["data"]
        assert parent["status"] == "running" and parent["interaction"] is None
        assert "resume" in parent["allowed_actions"] and not parent["recovery_required"]
        bank_before = bank_counts(tmp_path)
        writes = Mock(wraps=runtime.gateway.cancel_subscription)
        monkeypatch.setattr(runtime.gateway, "cancel_subscription", writes)
        yield SimpleNamespace(app=app, api=app.state.api, client=client, parent=parent,
                              thread=thread, planner=planner, writes=writes,
                              bank_before=bank_before, path=tmp_path)


def current_parent(env):
    return env.client.get(f"/api/v1/tasks/{env.parent['task_id']}").json()["data"]


def propose_resume(env):
    env.planner.return_value = ContinueProposal(task_id=env.parent["task_id"],
        task_revision=env.parent["task_revision"], action="resume")
    return {"request_id": str(uuid4()), "text": "继续"}


def test_public_resume_contract_advances_original_cross_parent(running_expense):
    env = running_expense
    response = post(env.client, f"/tasks/{env.parent['task_id']}/resume")
    assert response.status_code == 200, response.text
    current = response.json()["data"]
    assert current["task_id"] == env.parent["task_id"]
    assert current["status"] == "waiting_input"
    assert current["task_revision"] > env.parent["task_revision"]
    assert env.writes.call_count == 0 and bank_counts(env.path) == env.bank_before


def test_chat_resume_and_duplicate_receipt_advance_original_parent_once(running_expense, monkeypatch):
    env = running_expense
    continuation = Mock(wraps=env.api.continue_task)
    monkeypatch.setattr(env.api, "continue_task", continuation)
    body = propose_resume(env)
    accepted = post(env.client, f"/threads/{env.thread}/messages", **body)
    assert accepted.status_code == 202, accepted.text
    current = current_parent(env)
    assert current["status"] == "waiting_input"
    assert current["task_id"] == env.parent["task_id"]
    assert continuation.call_count == 1
    assert continuation.call_args.args[2] == {"choice": "resume"}
    assert continuation.call_args.kwargs == {"publish": False}
    model_calls = env.planner.call_count
    duplicate = post(env.client, f"/threads/{env.thread}/messages", **body)
    assert duplicate.json() == accepted.json()
    assert current_parent(env)["task_revision"] == current["task_revision"]
    assert env.planner.call_count == model_calls and continuation.call_count == 1
    assert env.writes.call_count == 0 and bank_counts(env.path) == env.bank_before
