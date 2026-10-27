"""Controlled planning failures over real API/Harness; scripted models only."""

import json
from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.api.test_app import enter, make_app, post, start

from .model import DeepAgentPlanner, ModelSettings
from .test_harness import ScriptedChatModel


NOTICE = (
    "这次没能处理好您的消息，请换个说法。"
    "如果是在继续之前的办理，请先查看原任务卡片。"
)


class CountingModel(ScriptedChatModel):
    calls: int = 0

    def _generate(self, *args, **kwargs):
        self.calls += 1
        return super()._generate(*args, **kwargs)


def failing_planner(mode="none"):
    model = CountingModel(response_mode=mode)
    return model, DeepAgentPlanner(ModelSettings(model=model, provider="scripted",
        model_name="transfer-scripted", config_version="protocol-failure-test"))


@pytest.mark.parametrize("mode", ["none", "both"])
def test_protocol_failure_finishes_original_message_once_after_restart(tmp_path, monkeypatch, mode):
    app = make_app(tmp_path)
    api = app.state.api
    model, api.runtime.harness.planner = failing_planner(mode)
    submit = Mock(wraps=api.runtime.gateway.submit_transfer)
    risk = Mock(wraps=api.runtime.assess_risk)
    monkeypatch.setattr(api.runtime.gateway, "submit_transfer", submit)
    monkeypatch.setattr(api.runtime, "assess_risk", risk)
    try:
        with TestClient(app) as client:
            enter(client)
            thread = post(client, "/threads").json()["data"]["thread_id"]
            path = f"/api/v1/threads/{thread}/messages"
            body = {"request_id": str(uuid4()), "text": "请帮我理解这条消息，不办理转账。"}
            first = client.post(path, json=body, headers={"Origin": "http://testserver"})
            cookie = client.cookies.get("bank_session")
            assert first.status_code == 202
            assert first.json()["data"]["task_id"] is None
            for _ in range(2):
                assert client.post(path, json=body, headers={"Origin": "http://testserver"}).json() == first.json()
            history = client.get(path).json()["data"]["items"]
            assert [row["role"] for row in history] == ["user", "assistant"]
            assert all(row["task_ids"] == [] for row in history)
            assert client.get("/api/v1/tasks").json()["data"]["items"] == []
            assert model.calls == 1
            assert submit.call_count == risk.call_count == 0
            assert history[-1]["text"] == NOTICE
            admin, _ = api.enter(None, uuid4(), "test-admin-key")
            reader, viewer = api.audit_reader(admin)
            events = json.loads(reader.export_json(viewer, "D1"))["events"]
            finished = [event for event in events if event["event_type"] == "model.finished"]
            assert len(finished) == 1
            assert finished[0]["outcome"] == "failed"
            assert finished[0]["payload"]["error"]["code"] == "MODEL_UNDERSTANDING_FAILED"
            assert finished[0]["payload"]["response_ref"] is None
            assert not any(event["event_type"] == "task.transition" for event in events)
            assert not any(event["event_type"] == "security.decided" for event in events)
    finally:
        api.runtime.close()

    restarted = make_app(tmp_path)  # A new classification would propose a transfer.
    try:
        with TestClient(restarted) as client:
            client.cookies.set("bank_session", cookie)
            assert client.post(path, json=body, headers={"Origin": "http://testserver"}).json() == first.json()
            assert client.get(path).json()["data"]["items"] == history
            assert client.get("/api/v1/tasks").json()["data"]["items"] == []
            assert restarted.state.api.runtime.harness.planner.calls == 0
    finally:
        restarted.state.api.runtime.close()


def test_protocol_failure_keeps_original_pending_task_and_confirmation(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    api = app.state.api
    try:
        with TestClient(app) as client:
            thread, pending = start(client)
            assert pending["status"] == "waiting_approval"
            task_id = pending["task_id"]
            ref = pending["interaction"]["record_ref"]
            before = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
            confirmation = client.get(f"/api/v1/confirmations/{ref}").json()["data"]
            model, api.runtime.harness.planner = failing_planner()
            submit = Mock(wraps=api.runtime.gateway.submit_transfer)
            risk = Mock(wraps=api.runtime.assess_risk)
            monkeypatch.setattr(api.runtime.gateway, "submit_transfer", submit)
            monkeypatch.setattr(api.runtime, "assess_risk", risk)
            failed = post(client, f"/threads/{thread}/messages", text="请帮我看这件事，不转账。")
            assert failed.status_code == 202
            history = client.get(f"/api/v1/threads/{thread}/messages").json()["data"]["items"]
            assert history[-1]["text"] == NOTICE
            assert history[-1]["task_ids"] == []
            after = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
            assert {k: v for k, v in after.items() if k != "snapshot_at"} == {
                k: v for k, v in before.items() if k != "snapshot_at"}
            assert client.get(f"/api/v1/confirmations/{ref}").json()["data"] == confirmation
            assert len(client.get("/api/v1/tasks").json()["data"]["items"]) == 1
            assert model.calls == 1
            assert submit.call_count == risk.call_count == 0
    finally:
        api.runtime.close()
