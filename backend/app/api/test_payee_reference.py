"""F36 uses a controlled reference before resuming or recording the task."""
from uuid import uuid4
from fastapi.testclient import TestClient
from app.agent_platform.model import TransferProposal
from app.api.test_app import make_app, start, post, approve
from app.storage.database import connect

NUMBER = "6222000000000002"


def form(task, name="王阿姨", request_id=None):
    return {"request_id": request_id or str(uuid4()), "interaction_id": task["interaction"]["interaction_id"],
            "kind": "payee", "fields": {"account_number": NUMBER, "account_name": name}}


def scan(app):
    connection = connect(app.state.api.runtime.application.path)
    try:
        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes", "audit_events", "tasks",
                      "api_messages", "api_requests", "api_events"):
            assert all(NUMBER not in str(tuple(row)) for row in connection.execute(f"SELECT * FROM {table}")), table
    finally:
        connection.close()


def test_f36_reference_idempotence_refresh_restart_and_single_transfer(tmp_path):
    proposal = TransferProposal(amount_fen=50000, payer_account_id="A1")
    app = make_app(tmp_path, proposal=proposal)
    with TestClient(app) as client:
        thread, task = start(client)
        path = f"/api/v1/tasks/{task['task_id']}/details"
        body = form(task)
        first = client.post(path, json=body, headers={"Origin": "http://testserver"})
        assert first.status_code == 200, first.text
        duplicate = client.post(path, json=body, headers={"Origin": "http://testserver"})
        assert duplicate.status_code == 200
        assert duplicate.json() == first.json()
        assert NUMBER not in first.text
        pending = first.json()["data"]["task"]
        assert pending["task_id"] == task["task_id"]
        assert pending["status"] == "waiting_approval"
        refreshed = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert refreshed["data"] == pending["data"]
        assert refreshed["task_revision"] == pending["task_revision"]
        assert NUMBER not in client.get(f"/api/v1/threads/{thread}/messages").text
        cookies = dict(client.cookies)
        scan(app)
    app.state.api.runtime.close()
    restarted = make_app(tmp_path, proposal=proposal)
    with TestClient(restarted) as client:
        client.cookies.update(cookies)
        pending = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        waiting = approve(client, pending)
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        completed = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
        assert completed.status_code == 200, completed.text
        final = completed.json()["data"]["task"]
        assert final["status"] == "succeeded"
        assert final["data"]["operation"]["receipt"]["amount_fen"] == 50000
        assert final["data"]["payee"]["account_masked"].endswith("0002")
        assert NUMBER not in completed.text
        scan(restarted)


def test_f36_mismatch_keeps_original_task_for_correction(tmp_path):
    app = make_app(tmp_path, proposal=TransferProposal(amount_fen=50000, payer_account_id="A1"))
    with TestClient(app) as client:
        _, task = start(client)
        path = f"/api/v1/tasks/{task['task_id']}/details"
        wrong = client.post(path, json=form(task, "错误户名"), headers={"Origin": "http://testserver"})
        assert wrong.status_code == 400
        assert "PAYEE_MISMATCH" in wrong.text
        assert NUMBER not in wrong.text
        pending = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert pending["status"] == "waiting_input"
        assert pending["data"]["operation_id"] is None
        corrected = client.post(path, json=form(pending), headers={"Origin": "http://testserver"})
        assert corrected.status_code == 200, corrected.text
        assert corrected.json()["data"]["task"]["task_id"] == task["task_id"]
        assert corrected.json()["data"]["task"]["status"] == "waiting_approval"
        scan(app)
