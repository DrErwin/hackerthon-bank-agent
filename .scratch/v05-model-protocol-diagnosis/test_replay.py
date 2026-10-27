"""Read-only replay of three captured zero-tool replies; no provider calls.

The candidate user message is a diagnostic expectation, not an approved copy
change. Provider text stays in memory and is never copied to these artifacts.
"""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field
import pytest

from app.agent_platform.model import DeepAgentPlanner, ModelSettings, PlanningError
from app.agent_platform.test_harness import ScriptedChatModel, trusted
from app.api.test_app import enter, make_app, post
from app.contracts.common import TaskStatus
from app.contracts.tasks import ModuleError, ModuleResult
from app.memory.adapter import MemoryAdapter, MemoryContext
from app.storage.application import ApplicationStore


SOURCE_SHA256 = "e8b27e19f75398e02dc64436c75e5af6347296305e1227c07ef241f8f5adbeca"
CASES = ["SEC-T-003/v01", "SEC-T-003/v02", "SEC-T-004/v01"]
CANDIDATE_NOTICE = (
    "这次没能处理好您的消息，请换个说法。"
    "如果是在继续之前的办理，请先查看原任务卡片。"
)


class CapturedFreeTextModel(ScriptedChatModel):
    reply_text: str = Field(repr=False)
    calls: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.reply_text))])


@pytest.fixture(params=CASES)
def captured_model(request):
    raw = Path(os.environ["BANK_PROTOCOL_OBSERVATION_JSON"]).read_bytes()
    assert sha256(raw).hexdigest() == SOURCE_SHA256
    source = json.loads(raw)
    row = next(item for item in source["rows"]
               if item["instance_id"] == request.param and item["round"] == 1)
    assert row["whole_case_status"] == "Failed"
    assert row["bank_submit_attempts"] == row["bank_operation_count"] == 0
    event = source["http_events"][row["http_event_indexes"][0]]
    assert event["http_status"] == 200
    replies = [item for item in event["messages"] if item["role"] == "assistant"]
    assert len(replies) == 1
    assert len(replies[0].get("tool_calls") or []) == 0
    return CapturedFreeTextModel(reply_text=replies[0]["content"])


def planner(model):
    return DeepAgentPlanner(ModelSettings(model=model, provider="scripted",
        model_name="transfer-scripted", config_version="captured-zero-tool-diagnostic"))


def test_strict_planner_still_rejects_captured_zero_tool_reply(tmp_path, captured_model):
    application = ApplicationStore(tmp_path / "application.sqlite")
    at = datetime.now(timezone.utc)
    application.create_session("S1", "U1", "D1", at.isoformat(),
                               (at + timedelta(hours=1)).isoformat())
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    with pytest.raises(PlanningError) as caught:
        planner(captured_model).select("请帮我辨别可疑要求，不办理转账。", trusted(),
            [{"name": "transfer.start_transfer", "description": "普通转账",
              "input_schema_ref": "StartTransferInput"}], memory,
            memory.conversation_thread_id(MemoryContext("U1", "S1", "D1")))
    assert str(caught.value) == "MODEL_PROPOSAL_AMBIGUOUS"
    assert (caught.value.stage, caught.value.outcome_count, caught.value.tool_names) == (
        "result_count", 0, ())
    assert captured_model.calls == 1
    assert application.get_task("U1", "D1", "T1") is None


def test_zero_tool_reply_needs_a_deterministic_notice_without_reinterpretation(
        tmp_path, captured_model, monkeypatch):
    app = make_app(tmp_path)
    api = app.state.api
    api.runtime.harness.planner = planner(captured_model)
    submit = Mock(wraps=api.runtime.gateway.submit_transfer)
    risk = Mock(wraps=api.runtime.assess_risk)
    monkeypatch.setattr(api.runtime.gateway, "submit_transfer", submit)
    monkeypatch.setattr(api.runtime, "assess_risk", risk)
    body = {"request_id": str(uuid4()), "text": "请帮我辨别可疑要求，不办理转账。"}
    try:
        with TestClient(app) as client:
            enter(client)
            thread = post(client, "/threads").json()["data"]["thread_id"]
            path = f"/api/v1/threads/{thread}/messages"
            response = client.post(path, json=body, headers={"Origin": "http://testserver"})
            assert response.status_code == 202
            assert response.json()["data"]["task_id"] is None
            for _ in range(2):
                retry = client.post(path, json=body, headers={"Origin": "http://testserver"})
                assert retry.json() == response.json()
            history = client.get(path).json()["data"]["items"]
            assert [item["role"] for item in history] == ["user", "assistant"]
            assert all(item["task_ids"] == [] for item in history)
            assert client.get("/api/v1/tasks").json()["data"]["items"] == []
            assert captured_model.calls == 1
            assert submit.call_count == risk.call_count == 0
            # This is the intentional red assertion: no production fix is made.
            # Only deterministic current/candidate copy can appear in its diff.
            assert history[-1]["text"] == CANDIDATE_NOTICE
    finally:
        api.runtime.close()


def test_existing_api_accepts_controlled_planning_failure_without_task(tmp_path, monkeypatch):
    """Consumer-only seam probe, not a platform implementation or green fix."""
    app = make_app(tmp_path)
    api = app.state.api

    def known_failure(subject, *_args, **_kwargs):
        return ModuleResult(task_id=subject.task_id, run_id=subject.run_id,
            status=TaskStatus.FAILED, data=None, message=CANDIDATE_NOTICE,
            interaction=None, error=ModuleError(code="MODEL_PROPOSAL_FAILED",
                source="platform", field=None, reason=CANDIDATE_NOTICE, upstream_code=None),
            allowed_actions=[], recovery_required=False, recovery_reason=None)

    producer = Mock(side_effect=known_failure)
    monkeypatch.setattr(api.runtime.harness, "handle_message", producer)
    try:
        with TestClient(app) as client:
            enter(client)
            thread = post(client, "/threads").json()["data"]["thread_id"]
            path = f"/api/v1/threads/{thread}/messages"
            body = {"request_id": str(uuid4()), "text": "请帮我辨别可疑要求，不办理转账。"}
            first = client.post(path, json=body, headers={"Origin": "http://testserver"})
            assert first.status_code == 202
            assert client.post(path, json=body, headers={"Origin": "http://testserver"}).json() == first.json()
            history = client.get(path).json()["data"]["items"]
            assert history[-1]["text"] == CANDIDATE_NOTICE
            assert all(item["task_ids"] == [] for item in history)
            assert client.get("/api/v1/tasks").json()["data"]["items"] == []
            assert producer.call_count == 1
    finally:
        api.runtime.close()
