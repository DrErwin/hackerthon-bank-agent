"""Chat resume is a checked suggestion, never a business execution."""

from unittest.mock import Mock, patch
from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from .local_demo import build_runtime
from .model import ContinueProposal
from .test_local_demo import ConnectorTestModel, configuration


class ResumeModel(ConnectorTestModel):
    requests: int = 0
    prompt: str = ""

    def _generate(self, messages, **kwargs):
        self.requests += 1
        self.prompt = str(messages[0].content)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[{
            "name": "propose_continuation", "id": "continue-parent", "type": "tool_call",
            "args": {"task_id": "PARENT", "task_revision": 3, "action": "resume"},
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
        assert model.requests == 1
        assert runtime.application.get_task("U1", "D1", "PARENT") == before
        assert runtime.application.get_task("U1", "D1", "CHAT") is None
        assert all(spy.call_count == 0 for spy in forbidden)
    finally:
        runtime.gateway.close()
