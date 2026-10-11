"""Planning sees the session's pending business instead of denying it (#84)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pydantic import Field

from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from app.modules.transfer.test_workflow import Ports

from .model import DeepAgentPlanner, ModelSettings, ReplyOnly
from .test_harness import ScriptedChatModel, runtime, trusted


class CapturePlanner:
    provider = "scripted"
    model_name = "transfer-test"
    config_version = "test-v1"

    def __init__(self):
        self.summaries = []

    def select(self, intent_text, trusted, catalog, memory, thread_id, context_summary=None):
        self.summaries.append(context_summary)
        return ReplyOnly(message="您有一笔业务正在等待处理。")


def chat_context(task_id="T2"):
    return TrustedContext(user_id="U1", session_id="S1", task_id=task_id, run_id="R2",
                          parent_task_id=None, demo_round_id="D1")


def active_runtime(tmp_path, planner):
    harness = runtime(tmp_path / "app.sqlite", Ports(), planner)
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    return harness


def waiting_task(harness, status=TaskStatus.WAITING_APPROVAL, interaction_kind="confirmation",
                 intent="给妈妈转 500 元"):
    return harness.application.create_task(
        "T9", "U1", "S1", "D1", "R9", status,
        {
            "request_id": str(uuid4()), "intent_text": intent, "config_version": "test-v1",
            "trace_id": str(uuid4()),
            "result": {
                "task_id": "T9", "run_id": "R9", "status": status.value, "data": None,
                "message": "请在确认单上确认。", "interaction": (
                    {"interaction_id": "I1", "kind": interaction_kind}
                    if interaction_kind else None
                ),
                "error": None, "allowed_actions": ["resume", "cancel"],
                "recovery_required": False, "recovery_reason": None,
            },
        },
    )


def test_waiting_confirmation_reaches_planner(tmp_path):
    planner = CapturePlanner()
    harness = active_runtime(tmp_path, planner)
    waiting_task(harness, interaction_kind="confirmation")
    outcome = harness.handle_message(chat_context(), uuid4(), "嗯")
    assert isinstance(outcome, ReplyOnly)
    summary = planner.summaries[0]
    assert summary is not None
    assert "等待" in summary and "确认" in summary
    assert "给妈妈转 500 元" in summary


def test_waiting_verification_reaches_planner(tmp_path):
    planner = CapturePlanner()
    harness = active_runtime(tmp_path, planner)
    waiting_task(harness, interaction_kind="verification")
    harness.handle_message(chat_context(), uuid4(), "应该可以吧")
    summary = planner.summaries[0]
    assert summary is not None
    assert "验证" in summary


def test_needs_attention_reaches_planner(tmp_path):
    planner = CapturePlanner()
    harness = active_runtime(tmp_path, planner)
    waiting_task(harness, status=TaskStatus.NEEDS_ATTENTION, interaction_kind=None)
    harness.handle_message(chat_context(), uuid4(), "办得怎么样了")
    summary = planner.summaries[0]
    assert summary is not None
    assert "待核实" in summary


def test_no_pending_business_sends_no_summary(tmp_path):
    planner = CapturePlanner()
    harness = active_runtime(tmp_path, planner)
    harness.handle_message(chat_context(), uuid4(), "今天天气不错")
    assert planner.summaries == [None]


def test_terminal_tasks_are_not_summarized(tmp_path):
    planner = CapturePlanner()
    harness = active_runtime(tmp_path, planner)
    waiting_task(harness, status=TaskStatus.SUCCEEDED, interaction_kind=None)
    harness.handle_message(chat_context(), uuid4(), "再转一笔")
    assert planner.summaries == [None]


def test_summary_masks_free_text_secrets(tmp_path):
    planner = CapturePlanner()
    harness = active_runtime(tmp_path, planner)
    waiting_task(harness, intent="给 13800000000 转 500 元")
    harness.handle_message(chat_context(), uuid4(), "嗯")
    summary = planner.summaries[0]
    assert "13800000000" not in summary
    assert "138****" in summary


class ContextCaptureModel(ScriptedChatModel):
    response_mode: str = "reply"
    seen: list = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append([str(getattr(item, "content", "")) for item in messages])
        return super()._generate(messages, stop, run_manager, **kwargs)


def test_context_summary_is_injected_into_the_model_prompt(tmp_path):
    from app.memory.adapter import MemoryAdapter
    from app.storage.application import ApplicationStore

    application = ApplicationStore(tmp_path / "app.sqlite")
    now = datetime.now(timezone.utc)
    application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    model = ContextCaptureModel()
    planner = DeepAgentPlanner(ModelSettings(model, "scripted", model.model_name, "ctx-test"))
    planner.select(
        "嗯", trusted(), [{"name": "transfer.start_transfer"}], memory, "thread",
        context_summary="- 等待用户在确认单上确认办理：给妈妈转 500 元",
    )
    texts = [text for batch in model.seen for text in batch]
    model.seen.clear()
    assert any("当前会话背景" in text and "给妈妈转 500 元" in text for text in texts)
