"""Denials and failures audit as failed task outcomes, never succeeded (v04-platform/11)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.audit.journal import AuditJournal
from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.tasks import InteractionRequest, ModuleError, ModuleResult
from app.memory.adapter import MemoryAdapter
from app.modules.transfer.manifest import MANIFEST
from app.storage.application import ApplicationStore

from .harness import AgentHarness
from .model import TransferProposal
from .registry import CapabilityRegistry


def trusted(run="R1"):
    return TrustedContext(user_id="U1", session_id="S1", task_id="T1", run_id=run,
                          parent_task_id=None, demo_round_id="D1")


class StatusScript:
    """Planner stub plus a capability entry that lands scripted statuses."""

    provider = "scripted"
    model_name = "outcome-test"
    config_version = "test-v1"

    def __init__(self):
        self.calls = 0

    def select(self, intent_text, trusted, catalog, memory, thread_id, context_summary=None):
        self.calls += 1
        return TransferProposal(capability_name="transfer.start_transfer")


class ScriptedStatusEntry:
    """Registered capability whose start/resume return scripted terminal statuses."""

    def __init__(self, statuses):
        self._statuses = list(statuses)

    def start(self, trusted, request, *, thread_id=None):
        return self._result(trusted, self._statuses.pop(0))

    def resume(self, trusted, response, *, thread_id=None):
        return self._result(trusted, self._statuses.pop(0))

    def recover_session(self, trusted, *, source_session_id, thread_id=None):
        return self._result(trusted, self._statuses.pop(0))

    def checkpoint_context(self, trusted, *, thread_id=None):
        return None

    def _result(self, trusted, status):
        waiting = status in {TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL}
        return ModuleResult(
            task_id=trusted.task_id, run_id=trusted.run_id, status=status, data=None,
            message="请补充信息。" if waiting else "脚本状态。",
            interaction=InteractionRequest(
                interaction_id="I1", kind="input", prompt="补充", required_fields=["text"],
                options=[], record_ref=None,
            ) if waiting else None,
            error=None if status != TaskStatus.FAILED else ModuleError(
                code="ACCESS_DENIED", source="security", field=None,
                reason="脚本拒绝", upstream_code=None,
            ),
            allowed_actions=["provide_input", "cancel"] if waiting else [],
            recovery_required=False, recovery_reason=None,
        )


def harness_with(path, statuses):
    application = ApplicationStore(path)
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    registry = CapabilityRegistry()
    # One stateful entry shared across start/resume, like a real module workflow.
    entry = ScriptedStatusEntry(statuses)
    registry.register_transfer(MANIFEST, lambda _trusted, _saver, _trace: entry)
    return AgentHarness(application, memory, AuditJournal(application.path), registry,
                         StatusScript(), lambda *_: True)


def open_session(application):
    at = datetime.now(timezone.utc)
    application.create_session("S1", "U1", "D1", at.isoformat(),
                               (at + timedelta(days=1)).isoformat())


def transitions(harness):
    return [event for event in harness.audit._events("D1", "T1")
            if event.event_type == "task.transition"]


def test_denied_start_audits_as_failed_not_succeeded(tmp_path):
    """PR #131 review §3: a FAILED start used to land outcome="succeeded"."""

    harness = harness_with(tmp_path / "app.sqlite", [TaskStatus.FAILED])
    open_session(harness.application)
    result = harness.start(trusted(), uuid4(), "给妈妈转 100 元")
    assert result.status == TaskStatus.FAILED
    assert [event.outcome for event in transitions(harness)] == ["failed"]


def test_waiting_then_denied_resume_audits_waiting_then_failed(tmp_path):
    harness = harness_with(tmp_path / "app.sqlite",
                           [TaskStatus.WAITING_INPUT, TaskStatus.FAILED])
    open_session(harness.application)
    started = harness.start(trusted(), uuid4(), "给妈妈转 100 元")
    assert started.status == TaskStatus.WAITING_INPUT
    resumed = harness.resume(trusted(run="R2"), {"text": "继续"})
    assert resumed.status == TaskStatus.FAILED
    assert [event.outcome for event in transitions(harness)] == ["waiting", "failed"]


def test_succeeded_paths_keep_their_existing_outcomes(tmp_path):
    harness = harness_with(tmp_path / "app.sqlite",
                           [TaskStatus.WAITING_INPUT, TaskStatus.SUCCEEDED])
    open_session(harness.application)
    assert harness.start(trusted(), uuid4(), "给妈妈转 100 元").status == TaskStatus.WAITING_INPUT
    assert harness.resume(trusted(run="R2"), {"text": "继续"}).status == TaskStatus.SUCCEEDED
    assert [event.outcome for event in transitions(harness)] == ["waiting", "succeeded"]


def test_unmapped_terminal_status_audits_unknown_not_succeeded(tmp_path):
    """Future statuses fall back to the enum's 'unknown' instead of succeeded."""

    harness = harness_with(tmp_path / "app.sqlite", [TaskStatus.CANCELLED])
    open_session(harness.application)
    assert harness.start(trusted(), uuid4(), "给妈妈转 100 元").status == TaskStatus.CANCELLED
    assert [event.outcome for event in transitions(harness)] == ["unknown"]
