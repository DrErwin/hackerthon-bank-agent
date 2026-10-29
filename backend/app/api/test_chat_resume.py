"""Resume consumers use real Cross/Harness/HTTP/bank; only planning is scripted."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.agent_platform.model import ContinueProposal, TransferProposal
from app.agent_platform.test_local_demo import app_for, configuration

from app.contracts.bank import BankError, QueryFailure
from app.contracts.common import TaskStatus
from app.contracts.tasks import InteractionRequest

from .test_app import approve, enter, make_app, post, start


def bank_counts(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return tuple(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                     for table in ("bank_operations", "ledger_entries"))
    finally:
        connection.close()


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
        bank_before = bank_counts(runtime.bank.store.path)
        writes = Mock(wraps=runtime.gateway.cancel_subscription)
        monkeypatch.setattr(runtime.gateway, "cancel_subscription", writes)
        yield SimpleNamespace(app=app, api=app.state.api, client=client, parent=parent,
                              thread=thread, planner=planner, writes=writes,
                              bank_before=bank_before, path=runtime.bank.store.path)


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


def test_interrupted_resume_receipt_reads_original_without_advancing_again(running_expense, monkeypatch):
    env = running_expense
    continuation = Mock(wraps=env.api.continue_task)
    monkeypatch.setattr(env.api, "continue_task", continuation)
    finish = env.api.store.finish

    def fail_after_module(identity, endpoint, request_id, response):
        if endpoint.startswith("/message-continuation/"):
            raise OSError("test interrupted after original resume")
        return finish(identity, endpoint, request_id, response)

    monkeypatch.setattr(env.api.store, "finish", fail_after_module)
    body = propose_resume(env)
    assert post(env.client, f"/threads/{env.thread}/messages", **body).status_code == 202
    current = current_parent(env)
    assert current["status"] == "waiting_input"
    job = env.api.store.rows("SELECT * FROM api_message_jobs WHERE request_id=?", (body["request_id"],))[0]
    assert job["status"] == "continuation_ready" and continuation.call_count == 1
    model_calls = env.planner.call_count
    monkeypatch.setattr(env.api.store, "finish", finish)
    assert post(env.client, f"/threads/{env.thread}/messages", **body).status_code == 202
    assert current_parent(env)["task_revision"] == current["task_revision"]
    assert env.api.store.message_job(job["job_id"])["status"] == "task_completed"
    assert continuation.call_count == 1 and env.planner.call_count == model_calls
    assert env.writes.call_count == 0 and bank_counts(env.path) == env.bank_before


def test_dispatch_rechecks_latest_projection_after_planner_approved_resume(running_expense, monkeypatch):
    env = running_expense
    continuation = Mock(wraps=env.api.continue_task)
    monkeypatch.setattr(env.api, "continue_task", continuation)
    dispatch, task_view = env.api.dispatch_continuation, env.api.task_view
    interaction = lambda kind: InteractionRequest(interaction_id="CURRENT", kind=kind,
        prompt="current test interaction", required_fields=[], options=[], record_ref="CURRENT")
    changes = [
        {"allowed_actions": []},
        {"recovery_required": True, "recovery_reason": "OPERATION_UNKNOWN", "allowed_actions": ["resume", "query"]},
        {"status": TaskStatus.WAITING_INPUT, "interaction": interaction("input")},
        {"status": TaskStatus.WAITING_APPROVAL, "interaction": interaction("confirmation")},
        {"status": TaskStatus.WAITING_APPROVAL, "interaction": interaction("verification")},
    ]
    for latest in changes:
        # The provider validated the real running parent first. Simulate a later
        # authoritative API projection so the consumer's own gates are exercised.
        def changed(job, identity):
            with monkeypatch.context() as patch:
                patch.setattr(env.api, "task_view", lambda who, task_id:
                    task_view(who, task_id).model_copy(update=latest))
                return dispatch(job, identity)

        monkeypatch.setattr(env.api, "dispatch_continuation", changed)
        body = propose_resume(env)
        assert post(env.client, f"/threads/{env.thread}/messages", **body).status_code == 202
        assert current_parent(env)["task_revision"] == env.parent["task_revision"]
        assert continuation.call_count == 0, latest
        job = env.api.store.rows("SELECT status FROM api_message_jobs WHERE request_id=?", (body["request_id"],))[0]
        assert job["status"] == "reply_completed", latest
    assert env.writes.call_count == 0 and bank_counts(env.path) == env.bank_before


def test_chat_resume_cannot_target_another_thread(running_expense, monkeypatch):
    env = running_expense
    continuation = Mock(wraps=env.api.continue_task)
    monkeypatch.setattr(env.api, "continue_task", continuation)
    other = post(env.client, "/threads").json()["data"]["thread_id"]
    body = propose_resume(env)
    assert post(env.client, f"/threads/{other}/messages", **body).status_code == 202
    assert current_parent(env)["task_revision"] == env.parent["task_revision"]
    assert continuation.call_count == 0
    replies = env.client.get(f"/api/v1/threads/{other}/messages").json()["data"]["items"]
    assert any(item["role"] == "assistant" and "原对话" in item["text"] for item in replies)
    assert env.writes.call_count == 0 and bank_counts(env.path) == env.bank_before


def test_chat_resume_rechecks_revision_after_an_explicit_card_action(running_expense, monkeypatch):
    env = running_expense
    original_continue = env.api.continue_task
    continuation = Mock(wraps=original_continue)
    monkeypatch.setattr(env.api, "continue_task", continuation)
    dispatch = env.api.dispatch_continuation

    def card_won_before_dispatch(job, identity):
        original_continue(identity, env.parent["task_id"], {"choice": "resume"})
        return dispatch(job, identity)

    monkeypatch.setattr(env.api, "dispatch_continuation", card_won_before_dispatch)
    body = propose_resume(env)
    assert post(env.client, f"/threads/{env.thread}/messages", **body).status_code == 202
    current = current_parent(env)
    assert current["status"] == "waiting_input"
    assert current["task_revision"] > env.parent["task_revision"]
    assert continuation.call_count == 0  # Only the explicit card action progressed.
    assert env.writes.call_count == 0 and bank_counts(env.path) == env.bank_before


def test_saved_chat_resume_cannot_recover_authority_in_a_new_session(running_expense, monkeypatch):
    env = running_expense
    dispatch = env.api.dispatch_continuation

    def interrupted(*args):
        raise OSError("test before dispatch")

    monkeypatch.setattr(env.api, "dispatch_continuation", interrupted)
    body = propose_resume(env)
    assert post(env.client, f"/threads/{env.thread}/messages", **body).status_code == 202
    assert current_parent(env)["task_revision"] == env.parent["task_revision"]
    model_calls = env.planner.call_count
    monkeypatch.setattr(env.api, "dispatch_continuation", dispatch)
    env.api.store.write("UPDATE sessions SET expires_at=?", ("2000-01-01T00:00:00+00:00",))
    enter(env.client)
    continuation = Mock(wraps=env.api.continue_task)
    monkeypatch.setattr(env.api, "continue_task", continuation)
    assert post(env.client, f"/threads/{env.thread}/messages", **body).status_code == 202
    assert current_parent(env)["recovery_required"] is True
    assert continuation.call_count == 0 and env.planner.call_count == model_calls
    assert env.writes.call_count == 0 and bank_counts(env.path) == env.bank_before


def test_chat_resume_does_not_resubmit_an_unknown_transfer(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    runtime = app.state.api.runtime
    bank = runtime.bank
    bank.slow_seconds = 12.0
    bank.arm_slow_once("U1")
    runtime.gateway._transfer_timeout_seconds = 0.01
    submissions = Mock(wraps=bank.submit_transfer)
    monkeypatch.setattr(bank, "submit_transfer", submissions)
    monkeypatch.setattr(runtime.gateway, "get_operation", lambda *_args:
        QueryFailure(kind="error", error=BankError(code="CALL_TIMEOUT", details={})))
    with TestClient(app) as client:
        thread, task = start(client)
        verifying = approve(client, task)
        challenge = verifying["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        response = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
        assert response.status_code == 200, response.text
        unknown = response.json()["data"]["task"]
        assert unknown["recovery_reason"] == "OPERATION_UNKNOWN"
        assert unknown["allowed_actions"] == ["query"] and submissions.call_count == 1
        runtime.harness.planner.proposal = ContinueProposal(task_id=task["task_id"],
            task_revision=unknown["task_revision"], action="resume")
        continuation = Mock(wraps=app.state.api.continue_task)
        monkeypatch.setattr(app.state.api, "continue_task", continuation)
        assert post(client, f"/threads/{thread}/messages", text="继续").status_code == 202
        retained = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert retained["data"]["operation_id"] == unknown["data"]["operation_id"]
        assert retained["allowed_actions"] == ["query"]
        assert submissions.call_count == 1 and continuation.call_count == 0
