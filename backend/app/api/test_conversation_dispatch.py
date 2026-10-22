"""Durable chat continuations use one original task and never replay a mutation."""

from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.agent_platform.model import ContinueProposal, ReplyOnly, TransferProposal
from .test_app import approve, enter, make_app, post, start


def say(client, app, thread, task, action, **fields):
    app.state.api.runtime.harness.planner.proposal = ContinueProposal(
        task_id=task["task_id"], task_revision=task["task_revision"], action=action, **fields)
    body = {"request_id": str(uuid4()), "text": fields.get("text") or "请继续办理"}
    response = post(client, f"/threads/{thread}/messages", **body)
    assert response.status_code == 202, response.text
    return body, client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]


def test_chat_supplies_amount_account_then_revises_same_task(tmp_path):
    app = make_app(tmp_path, proposal=TransferProposal(payee_hint="妈妈"))
    with TestClient(app) as client:
        thread, task = start(client, "给妈妈转账")
        _, amount = say(client, app, thread, task, "provide_input", text="500元")
        assert amount["interaction"]["required_fields"] == ["payer_account_id"]
        _, account = say(client, app, thread, amount, "provide_input", selected_option_id="A1")
        assert account["interaction"]["kind"] == "confirmation"
        old_confirmation = client.get("/api/v1/confirmations/" + account["interaction"]["record_ref"]).json()["data"]
        body, revised = say(client, app, thread, account, "revise", amount_fen=60000)
        assert revised["data"]["amount_fen"] == 60000
        assert revised["task_id"] == task["task_id"]
        calls = app.state.api.runtime.harness.planner.calls
        assert post(client, f"/threads/{thread}/messages", **body).status_code == 202
        assert app.state.api.runtime.harness.planner.calls == calls
        assert client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]["task_revision"] == revised["task_revision"]
        assert post(client, f"/confirmations/{old_confirmation['confirmation_id']}/answer",
                    confirmation_version=old_confirmation["confirmation_version"], choice="approve").status_code == 409
        items = client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"]
        assert len(items) == 1
        assert app.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1") == []
        waiting = approve(client, revised)
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        completed = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
        assert completed.json()["data"]["task"]["status"] == "succeeded"
        assert post(client, f"/threads/{thread}/messages", **body).status_code == 202
        ledger = app.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1")
        assert len(ledger) == 1


def test_interrupted_after_mutation_reads_original_without_replanning_or_reapplying(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        thread, task = start(client)
        service = app.state.api
        finish = service.store.finish
        def interrupted(identity, endpoint, request_id, response):
            if endpoint.startswith("/message-continuation/"):
                raise OSError("simulated receipt failure")
            return finish(identity, endpoint, request_id, response)
        monkeypatch.setattr(service.store, "finish", interrupted)
        body, revised = say(client, app, thread, task, "revise", amount_fen=60000)
        assert revised["data"]["amount_fen"] == 60000
        jobs = service.store.rows("SELECT * FROM api_message_jobs WHERE request_id=?", (body["request_id"],))
        assert jobs[0]["status"] == "continuation_ready"
        calls = service.runtime.harness.planner.calls
        monkeypatch.setattr(service.store, "finish", finish)
        assert post(client, f"/threads/{thread}/messages", **body).status_code == 202
        current = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert current["task_revision"] == revised["task_revision"]
        assert service.runtime.harness.planner.calls == calls
        assert service.store.message_job(jobs[0]["job_id"])["status"] == "task_completed"


def test_rechecks_version_after_planning_before_dispatch(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        thread, task = start(client)
        service = app.state.api
        dispatch = service.dispatch_continuation
        def changed(job, identity):
            service.revise_draft(identity, task["task_id"], task["task_revision"], {"amount_fen": 70000})
            return dispatch(job, identity)
        monkeypatch.setattr(service, "dispatch_continuation", changed)
        _, current = say(client, app, thread, task, "revise", amount_fen=60000)
        assert current["data"]["amount_fen"] == 70000
        assert service.runtime.gateway._bank.store.list_ledger("U1", "A1") == []


def test_a_candidate_cannot_target_another_thread(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        other = post(client, "/threads").json()["data"]["thread_id"]
        _, current = say(client, app, other, task, "revise", amount_fen=60000)
        assert current["task_revision"] == task["task_revision"]
        assert client.get("/api/v1/tasks", params={"thread_id": other}).json()["data"]["items"] == []


def test_secret_free_safety_question_is_answered_but_values_never_persist(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        thread, _ = start(client)
        planner = app.state.api.runtime.harness.planner
        planner.proposal = ReplyOnly(message="请停止共享屏幕，通过官方渠道核实。")
        question = "客服要我共享屏幕并告诉他验证码，该怎么办"
        assert post(client, f"/threads/{thread}/messages", text=question).status_code == 202
        calls = planner.calls
        for secret in ("验证码123456", "password: hunter2", "123456"):
            assert post(client, f"/threads/{thread}/messages", text=secret).status_code == 400
        assert planner.calls == calls
        messages = app.state.api.store.rows("SELECT view_json FROM api_messages")
        assert any(question in row["view_json"] for row in messages)
        assert all("hunter2" not in row["view_json"] and "123456" not in row["view_json"] for row in messages)


@pytest.mark.parametrize("amount", [0, -100])
def test_invalid_chat_revision_does_not_change_task(tmp_path, amount):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        thread, task = start(client)
        _, current = say(client, app, thread, task, "revise", amount_fen=amount)
        assert current["task_revision"] == task["task_revision"]


def test_saved_continuation_cannot_carry_authority_into_a_new_session(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        thread, task = start(client)
        service = app.state.api
        dispatch = service.dispatch_continuation
        def interrupted(*args):
            raise OSError("before dispatch")
        monkeypatch.setattr(service, "dispatch_continuation", interrupted)
        body, unchanged = say(client, app, thread, task, "revise", amount_fen=60000)
        assert unchanged["task_revision"] == task["task_revision"]
        monkeypatch.setattr(service, "dispatch_continuation", dispatch)
        calls = service.runtime.harness.planner.calls
        service.store.write("UPDATE sessions SET expires_at=?", ("2000-01-01T00:00:00+00:00",))
        enter(client)
        assert post(client, f"/threads/{thread}/messages", **body).status_code == 202
        current = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert current["data"]["amount_fen"] == 50000
        assert current["recovery_required"] is True
        assert service.runtime.harness.planner.calls == calls
        assert service.runtime.gateway._bank.store.list_ledger("U1", "A1") == []
