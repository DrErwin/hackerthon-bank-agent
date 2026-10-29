"""Chat resume is a checked suggestion, never a business execution."""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ValidationError

from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from .local_demo import build_runtime
from .model import ContinueProposal, ReplyOnly
from .test_local_demo import ConnectorTestModel, configuration


class ResumeModel(ConnectorTestModel):
    requests: int = 0
    prompt: str = ""
    target: str = "PARENT"
    revision: int = 3

    def _generate(self, messages, **kwargs):
        self.requests += 1
        self.prompt = str(messages[0].content)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[{
            "name": "propose_continuation", "id": "continue-parent", "type": "tool_call",
            "args": {"task_id": self.target, "task_revision": self.revision, "action": "resume"},
        }]))])


def running_parent(tmp_path):
    from datetime import datetime, timedelta, timezone

    model = ResumeModel()
    with patch("app.agent_platform.local_demo.ChatOpenAI", return_value=model):
        runtime = build_runtime(configuration(tmp_path))
    now = datetime.now(timezone.utc)
    runtime.application.create_session("S1", "U1", "D1", now.isoformat(),
        (now + timedelta(days=1)).isoformat())
    snapshot = {"capability_name": "cross.start_task", "intent_text": "处理不用的扣费",
        "config_version": runtime.harness.planner.config_version, "trace_id": str(uuid4()),
        "result": {"task_id": "PARENT", "run_id": "R1", "status": "running", "data": None,
            "message": "子任务已完成，可以继续核实父计划。", "interaction": None, "error": None,
            "allowed_actions": ["resume", "cancel"], "recovery_required": False, "recovery_reason": None}}
    parent = runtime.application.create_task("PARENT", "U1", "S1", "D1", "R1", TaskStatus.RUNNING, snapshot)
    for _ in range(3):
        parent = runtime.application.update_task("U1", "D1", "PARENT", parent.revision, "R1",
            parent.status, None, parent.snapshot)
    trusted = TrustedContext(user_id="U1", session_id="S1", demo_round_id="D1",
        task_id="CHAT", run_id="CHAT-RUN", parent_task_id=None)
    return runtime, model, trusted


def test_real_planner_tool_proposes_plain_resume_without_executing(tmp_path, monkeypatch):
    runtime, model, trusted = running_parent(tmp_path)
    before = runtime.application.get_task("U1", "D1", "PARENT")
    forbidden = []
    for method in ("submit_transfer", "cancel_subscription", "freeze_funds",
                   "create_order", "capture_frozen", "release_frozen"):
        spy = Mock(side_effect=AssertionError("PLANNING_MUST_NOT_EXECUTE"))
        forbidden.append(spy)
        monkeypatch.setattr(runtime.gateway, method, spy)
    try:
        result = runtime.harness.handle_message(trusted, uuid4(), "继续", allow_continuation=True)

        assert isinstance(result, ContinueProposal)
        assert result.action == "resume" and result.task_id == "PARENT" and result.task_revision == 3
        assert all(getattr(result, field) is None for field in (
            "text", "selected_option_id", "payee_hint", "amount_fen", "payer_account_id"))
        assert "task_id=PARENT" in model.prompt and "task_revision=3" in model.prompt
        assert "action=resume" in model.prompt and "不代表授权" in model.prompt
        assert model.requests == 1
        assert runtime.application.get_task("U1", "D1", "PARENT") == before
        assert runtime.application.get_task("U1", "D1", "CHAT") is None
        assert all(spy.call_count == 0 for spy in forbidden)
    finally:
        runtime.gateway.close()


@pytest.mark.parametrize("payload", [
    {"text": "继续"}, {"text": ""}, {"selected_option_id": "menu-choice"},
    {"selected_option_id": ""}, {"payee_hint": "家人"}, {"payer_account_id": "A1"},
    {"amount_fen": 250000}, {"amount_fen": 0},
])
def test_resume_schema_rejects_every_payload(payload):
    with pytest.raises(ValidationError, match="resume takes no payload"):
        ContinueProposal(task_id="PARENT", task_revision=3, action="resume", **payload)


@pytest.mark.parametrize("mode", [
    "stale_revision", "multiple", "not_allowed", "recovery", "input", "confirmation",
    "verification", "running_input", "running_confirmation", "succeeded", "failed",
    "cancelled", "partially_succeeded",
])
def test_chat_resume_rejects_changed_ambiguous_and_protected_tasks(tmp_path, mode):
    runtime, model, trusted = running_parent(tmp_path)
    try:
        task = runtime.application.get_task("U1", "D1", "PARENT")
        snapshot = task.snapshot
        status = task.status
        if mode == "multiple":
            runtime.application.create_task("ANOTHER", "U1", "S1", "D1", "OTHER-RUN", status, snapshot)
        elif mode == "not_allowed":
            snapshot["result"]["allowed_actions"] = ["query", "cancel"]
        elif mode == "recovery":
            snapshot["result"].update(recovery_required=True, recovery_reason="OPERATION_UNKNOWN")
        elif mode in {"input", "confirmation", "verification", "running_input", "running_confirmation"}:
            kind = mode.removeprefix("running_")
            if not mode.startswith("running_"):
                status = TaskStatus.WAITING_INPUT if kind == "input" else TaskStatus.WAITING_APPROVAL
            snapshot["result"]["interaction"] = {"kind": kind}
        elif mode in {"succeeded", "failed", "cancelled", "partially_succeeded"}:
            status = TaskStatus(mode)
        snapshot["result"]["status"] = status.value
        task = runtime.application.update_task("U1", "D1", "PARENT", task.revision,
            "R1", status, None, snapshot)
        model.revision = 3 if mode == "stale_revision" else task.revision

        result = runtime.harness.handle_message(trusted, uuid4(), "继续", allow_continuation=True)

        assert isinstance(result, ReplyOnly)
        assert runtime.application.get_task("U1", "D1", "PARENT") == task
        assert runtime.application.get_task("U1", "D1", "CHAT") is None
    finally:
        runtime.gateway.close()


@pytest.mark.parametrize("scope", ["user", "session", "round"])
def test_resume_cannot_target_another_owner_session_or_round(tmp_path, scope):
    from datetime import datetime, timedelta, timezone

    runtime, model, trusted = running_parent(tmp_path)
    try:
        parent = runtime.application.get_task("U1", "D1", "PARENT")
        user = "U2" if scope == "user" else "U1"
        session = "S2"
        demo_round = "D2" if scope == "round" else "D1"
        now = datetime.now(timezone.utc)
        runtime.application.create_session(session, user, demo_round, now.isoformat(),
            (now + timedelta(days=1)).isoformat())
        foreign = runtime.application.create_task("FOREIGN", user, session, demo_round,
            "FOREIGN-RUN", TaskStatus.RUNNING, parent.snapshot)
        foreign = runtime.application.update_task(user, demo_round, foreign.task_id, foreign.revision,
            foreign.run_id, foreign.status, None, foreign.snapshot)
        model.target, model.revision = foreign.task_id, foreign.revision

        result = runtime.harness.handle_message(trusted, uuid4(), "继续", allow_continuation=True)

        assert isinstance(result, ReplyOnly)
        assert "task_id=FOREIGN" not in model.prompt
        assert runtime.application.get_task("U1", "D1", "PARENT") == parent
        assert runtime.application.get_task(user, demo_round, foreign.task_id) == foreign
    finally:
        runtime.gateway.close()
