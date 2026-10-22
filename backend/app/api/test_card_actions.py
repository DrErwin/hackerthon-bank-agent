"""Typed result-card actions bind one source and preserve all sensitive gates."""
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.agent_platform.model import TransferProposal
from app.agent_platform.test_local_demo import app_for, configuration
from app.agent_platform.test_subscription_runtime import bank_operations
from .test_app import approve, post, start


def test_bill_card_keeps_exact_source_and_never_sends_hidden_chat(tmp_path):
    app = app_for(configuration(tmp_path))
    harness = app.state.api.runtime.harness
    with TestClient(app) as client, patch.object(harness.planner, "select", return_value=TransferProposal(
            capability_name="bills.summarize")):
        thread, source = start(client, "2026年9月所有账户账单")
        messages = client.get(f"/api/v1/threads/{thread}/messages").json()["data"]["items"]
        body = dict(request_id=str(uuid4()), source_revision=source["task_revision"], action="bill_details", category="dining")
        with patch.object(harness.planner, "select", side_effect=AssertionError("no replanning")):
            response = post(client, f"/tasks/{source['task_id']}/actions", **body)
            assert response.status_code == 200, response.text
            task = response.json()["data"]
            assert task["status"] == "succeeded"
            assert task["data"]["scope"] == source["data"]["scope"]
            assert task["data"]["category"] == "dining"
            assert post(client, f"/tasks/{source['task_id']}/actions", **body).json() == response.json()
        assert client.get(f"/api/v1/threads/{thread}/messages").json()["data"]["items"] == messages
        assert len(client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"]) == 2
        assert post(client, f"/tasks/{source['task_id']}/actions", **{**body, "category": "shopping"}).status_code == 409
        assert post(client, f"/tasks/{source['task_id']}/actions", **{**body, "request_id": str(uuid4()), "source_revision": 999}).status_code == 409


def test_subscription_row_requires_confirmation_verification_and_one_operation(tmp_path):
    app = app_for(configuration(tmp_path))
    harness = app.state.api.runtime.harness
    with TestClient(app) as client, patch.object(harness.planner, "select", return_value=TransferProposal(
            capability_name="subscription.list_subscriptions")):
        _, source = start(client, "查看我的订阅")
        rows = source["data"]["list_result"]["items"]
        selected = next(row for row in rows if row["can_cancel_in_bank"])
        before = bank_operations(app.state.api.runtime.gateway._bank)
        body = dict(request_id=str(uuid4()), source_revision=source["task_revision"], action="subscription_cancel",
                    subscription_id=selected["subscription_id"])
        for forged in ["missing", *[row["subscription_id"] for row in rows if not row["can_cancel_in_bank"]]]:
            assert post(client, f"/tasks/{source['task_id']}/actions", **{**body, "request_id": str(uuid4()), "subscription_id": forged}).status_code == 400
        with patch.object(harness.planner, "select", side_effect=AssertionError("no model")):
            response = post(client, f"/tasks/{source['task_id']}/actions", **body)
        assert response.status_code == 200, response.text
        task = response.json()["data"]
        assert task["status"] == "waiting_approval" and task["interaction"]["kind"] == "confirmation"
        assert bank_operations(app.state.api.runtime.gateway._bank) == before
        waiting = approve(client, task)
        assert waiting["interaction"]["kind"] == "verification"
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        done = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
        assert done.status_code == 200, done.text
        completed = done.json()["data"]["task"]
        assert completed["status"] == "succeeded"
        assert completed["data"]["selected_item"]["mandate_id"] == selected["mandate_id"]
        assert post(client, f"/tasks/{source['task_id']}/actions", **body).json()["data"]["task_id"] == task["task_id"]
        assert bank_operations(app.state.api.runtime.gateway._bank) == before + 1
        app.state.api.store.write("UPDATE api_tasks SET session_id='old' WHERE task_id=?", (source["task_id"],))
        assert post(client, f"/tasks/{source['task_id']}/actions", **body).status_code == 409
        app.state.api.store.write("UPDATE api_tasks SET user_id='OTHER' WHERE task_id=?", (source["task_id"],))
        assert post(client, f"/tasks/{source['task_id']}/actions", **body).status_code == 404


def test_unknown_card_result_retry_reads_same_task_without_restarting(tmp_path):
    app = app_for(configuration(tmp_path))
    harness = app.state.api.runtime.harness
    with TestClient(app) as client, patch.object(harness.planner, "select", return_value=TransferProposal(
            capability_name="bills.summarize")):
        thread, source = start(client, "2026年9月所有账户账单")
        body = dict(request_id=str(uuid4()), source_revision=source["task_revision"], action="bill_details")
        original = harness.start_selected
        def interrupted(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError("lost response")
        with patch.object(harness, "start_selected", side_effect=interrupted):
            assert post(client, f"/tasks/{source['task_id']}/actions", **body).status_code == 503
        with patch.object(harness, "start_selected", side_effect=AssertionError("must read original")):
            retry = post(client, f"/tasks/{source['task_id']}/actions", **body)
        assert retry.status_code == 200 and retry.json()["data"]["status"] == "succeeded"
        assert len(client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"]) == 2
