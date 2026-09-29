"""One trusted task entry, public capability dispatch, checkpoint recovery and trace."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock, RLock
from time import monotonic
from typing import Callable
from uuid import UUID, uuid4

from app.audit.journal import AuditJournal
from app.contracts.audit import (
    AuditEvent, ModelFinishedPayload, ModelStartedPayload, ModelUsage,
    RecoveryCheckedPayload, TaskTransitionPayload,
)
from app.contracts.common import TaskStatus
from app.contracts.platform import CapabilityDefinition, StartTransferInput, TrustedContext
from app.contracts.tasks import ModuleError, ModuleResult, TransferTaskView
from app.memory.adapter import MemoryAdapter, MemoryContext
from app.storage.application import ApplicationStore, TaskRecord

from .model import Planner, TransferProposal
from .registry import CapabilityRegistry


_LOCK_GUARD = Lock()
_TASK_LOCKS: dict[str, RLock] = {}


def _task_lock(task_id: str) -> RLock:
    with _LOCK_GUARD:
        return _TASK_LOCKS.setdefault(task_id, RLock())


class RunTrace:
    """Share this writer with future security and tool sinks to keep one event order."""

    def __init__(self, journal: AuditJournal, trusted: TrustedContext,
                 thread_id: str, trace_id: str):
        self.journal = journal
        self.trusted = trusted
        self.thread_id = thread_id
        self.trace_id = trace_id

    def record(self, event_type: str, payload: object, outcome: str, *,
               evidence: object | None = None) -> AuditEvent:
        prior = self.journal._events(self.trusted.demo_round_id, self.trusted.task_id)
        sequence = 1 + max((item.sequence for item in prior
                            if item.run_id == self.trusted.run_id), default=-1)
        if evidence is None:
            evidence_id = None
        elif isinstance(payload, ModelStartedPayload):
            evidence_id = payload.request_ref
        elif isinstance(payload, ModelFinishedPayload):
            evidence_id = payload.response_ref
        else:
            evidence_id = str(uuid4())
        event = AuditEvent(
            event_id=str(uuid4()), trace_id=self.trace_id, span_id=str(uuid4()),
            sequence=sequence, parent_span_id=None,
            demo_round_id=self.trusted.demo_round_id,
            actor_id=self.trusted.user_id, session_id=self.trusted.session_id,
            target_session_id=self.trusted.session_id,
            target_user_id=self.trusted.user_id, thread_id=self.thread_id,
            task_id=self.trusted.task_id, run_id=self.trusted.run_id,
            module="agent_platform", event_type=event_type,
            timestamp=datetime.now(timezone.utc), logical_at=None,
            outcome=outcome, evidence_ref=evidence_id,
            evidence_status="available" if evidence is not None else "missing",
            missing_reason=None if evidence is not None else "event has no content snapshot",
            payload=payload,
        )
        return self.journal.append(event, evidence=evidence)


class AgentHarness:
    def __init__(self, application: ApplicationStore, memory: MemoryAdapter,
                 audit: AuditJournal, registry: CapabilityRegistry, planner: Planner,
                 authorize_capability: Callable[[TrustedContext, CapabilityDefinition], bool]):
        self.application = application
        self.memory = memory
        self.audit = audit
        self.registry = registry
        self.planner = planner
        self.authorize_capability = authorize_capability

    def _authorize(self, trusted: TrustedContext, name: str) -> None:
        definition = self.registry.get(name).definition
        if not self.authorize_capability(trusted, definition):
            raise PermissionError("ACCESS_DENIED")

    def _scope(self, trusted: TrustedContext) -> MemoryContext:
        context = MemoryContext(trusted.user_id, trusted.session_id, trusted.demo_round_id)
        self.memory.agent_backend(context)
        return context

    @staticmethod
    def _check_task(task: TaskRecord, trusted: TrustedContext) -> None:
        if task.session_id != trusted.session_id:
            raise PermissionError("ACCESS_DENIED")

    @staticmethod
    def _result(task: TaskRecord) -> ModuleResult[TransferTaskView]:
        if "result" not in task.snapshot:
            raise ValueError("TASK_NOT_READY")
        return ModuleResult[TransferTaskView].model_validate(task.snapshot["result"])

    def _trace(self, trusted: TrustedContext, task: TaskRecord) -> RunTrace:
        return RunTrace(self.audit, trusted, task.checkpoint_thread_id,
                        task.snapshot["trace_id"])

    def _checkpoint_id(self, context: MemoryContext, task: TaskRecord) -> str | None:
        saver = self.memory.checkpointer(context, task.task_id)
        saved = saver.get_tuple({"configurable": {"thread_id": task.checkpoint_thread_id}})
        return saved.config["configurable"]["checkpoint_id"] if saved else None

    def start(self, trusted: TrustedContext, request_id: UUID,
              intent_text: str) -> ModuleResult[TransferTaskView]:
        with _task_lock(trusted.task_id):
            context = self._scope(trusted)
            self._authorize(trusted, "transfer.start_transfer")
            task = self.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
            if task is None:
                task = self.application.create_task(
                    trusted.task_id, trusted.user_id, trusted.session_id,
                    trusted.demo_round_id, trusted.run_id, TaskStatus.RUNNING,
                    {"request_id": str(request_id), "intent_text": intent_text,
                     "config_version": self.planner.config_version,
                     "trace_id": str(uuid4())},
                )
            self._check_task(task, trusted)
            if task.run_id != trusted.run_id:
                raise ValueError("USE_RESUME_FOR_NEW_RUN")
            snapshot = task.snapshot
            if snapshot["request_id"] != str(request_id) or snapshot["intent_text"] != intent_text:
                raise ValueError("REQUEST_CONFLICT")
            if snapshot["config_version"] != self.planner.config_version:
                raise ValueError("MODEL_CONFIG_CHANGED")
            if "result" in snapshot:
                return self._result(task)

            trace = self._trace(trusted, task)
            if "proposal" not in snapshot:
                model_call_id = str(uuid4())
                trace.record(
                    "model.started",
                    ModelStartedPayload(
                        model_call_id=model_call_id, provider=self.planner.provider,
                        model=self.planner.model_name,
                        config_version=self.planner.config_version,
                        request_ref=str(uuid4()),
                    ),
                    "started",
                    evidence={"intent_text": intent_text,
                              "capabilities": self.registry.public_catalog()},
                )
                started = monotonic()
                try:
                    proposal = self.planner.select(
                        intent_text, trusted, self.registry.public_catalog(),
                        self.memory, task.checkpoint_thread_id,
                    )
                    self.registry.get(proposal.capability_name)
                    StartTransferInput(
                        request_id=request_id, intent_text=intent_text,
                        payer_account_id=proposal.payer_account_id,
                        payee_hint=proposal.payee_hint, amount_fen=proposal.amount_fen,
                    )
                except Exception:
                    model_error = ModuleError(
                        code="MODEL_PROPOSAL_FAILED", source="platform", field=None,
                        reason="模型暂未形成可执行的业务候选", upstream_code=None,
                    )
                    trace.record(
                        "model.finished",
                        ModelFinishedPayload(
                            model_call_id=model_call_id, response_ref=None,
                            duration_ms=int((monotonic() - started) * 1000),
                            usage=ModelUsage(input_tokens=None, output_tokens=None),
                            error=model_error,
                        ), "failed",
                    )
                    failure = ModuleResult[TransferTaskView](
                        task_id=trusted.task_id, run_id=trusted.run_id,
                        status=TaskStatus.FAILED, data=None,
                        message="暂时无法理解这次转账请求，请重新发起并核对信息。",
                        interaction=None, error=model_error, allowed_actions=[],
                        recovery_required=False, recovery_reason=None,
                    )
                    self.application.update_task(
                        trusted.user_id, trusted.demo_round_id, trusted.task_id,
                        task.revision, trusted.run_id, TaskStatus.FAILED, None,
                        {**snapshot, "result": failure.model_dump(mode="json")},
                    )
                    trace.record(
                        "task.transition",
                        TaskTransitionPayload(
                            previous_status=TaskStatus.RUNNING, status=TaskStatus.FAILED,
                            plan_revision=None, step_id=None,
                            reason_code="MODEL_PROPOSAL_FAILED", checkpoint_ref=None,
                        ), "failed",
                    )
                    return failure
                trace.record(
                    "model.finished",
                    ModelFinishedPayload(
                        model_call_id=model_call_id, response_ref=str(uuid4()),
                        duration_ms=int((monotonic() - started) * 1000),
                        usage=ModelUsage(input_tokens=None, output_tokens=None), error=None,
                    ), "succeeded", evidence=proposal.model_dump(mode="json"),
                )
                snapshot = {**snapshot, "proposal": proposal.model_dump(mode="json")}
                task = self.application.update_task(
                    trusted.user_id, trusted.demo_round_id, trusted.task_id,
                    task.revision, trusted.run_id, TaskStatus.RUNNING, None, snapshot,
                )

            proposal = TransferProposal.model_validate(snapshot["proposal"])
            self._authorize(trusted, proposal.capability_name)
            registration = self.registry.get(proposal.capability_name)
            saver = self.memory.checkpointer(context, trusted.task_id)
            entry = registration.factory(trusted, saver)
            result = entry.start(trusted, StartTransferInput(
                request_id=request_id, intent_text=intent_text,
                payer_account_id=proposal.payer_account_id,
                payee_hint=proposal.payee_hint, amount_fen=proposal.amount_fen,
            ), thread_id=task.checkpoint_thread_id)
            updated = {**snapshot, "capability_name": proposal.capability_name,
                       "result": result.model_dump(mode="json")}
            self.application.update_task(
                trusted.user_id, trusted.demo_round_id, trusted.task_id,
                task.revision, trusted.run_id, result.status,
                self._checkpoint_id(context, task), updated,
            )
            trace.record(
                "task.transition",
                TaskTransitionPayload(
                    previous_status=TaskStatus.RUNNING, status=result.status,
                    plan_revision=None, step_id=proposal.capability_name,
                    reason_code="CAPABILITY_SELECTED",
                    checkpoint_ref=self._checkpoint_id(context, task),
                ), "waiting" if result.status in {
                    TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL,
                } else "succeeded",
            )
            return result

    def get(self, trusted: TrustedContext) -> ModuleResult[TransferTaskView]:
        self._scope(trusted)
        task = self.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
        if task is None:
            raise ValueError("TASK_NOT_FOUND")
        self._check_task(task, trusted)
        return self._result(task)

    def resume(self, trusted: TrustedContext, response: dict) -> ModuleResult[TransferTaskView]:
        with _task_lock(trusted.task_id):
            context = self._scope(trusted)
            task = self.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
            if task is None:
                raise ValueError("TASK_NOT_FOUND")
            self._check_task(task, trusted)
            previous = self._result(task)
            if previous.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
                return previous
            if task.snapshot["config_version"] != self.planner.config_version:
                raise ValueError("MODEL_CONFIG_CHANGED")
            self._authorize(trusted, task.snapshot["capability_name"])
            trace = self._trace(trusted, task)
            registration = self.registry.get(task.snapshot["capability_name"])
            saver = self.memory.checkpointer(context, trusted.task_id)
            entry = registration.factory(trusted, saver)
            try:
                result = entry.resume(trusted, response, thread_id=task.checkpoint_thread_id)
                if result.run_id != trusted.run_id:
                    raise ValueError("STALE_RUN_CONTEXT")
            except Exception:
                trace.record(
                    "recovery.checked",
                    RecoveryCheckedPayload(
                        previous_run_id=task.run_id, current_run_id=trusted.run_id,
                        checkpoint_ref=task.checkpoint_id,
                        operation_ids=[previous.data.operation_id] if previous.data.operation_id else [],
                        result="stop", reason_code="PUBLIC_CAPABILITY_RESUME_FAILED",
                    ), "failed",
                )
                raise
            if result.status in {
                TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL,
                TaskStatus.NEEDS_ATTENTION,
            }:
                recovery_result = "wait"
            elif result.status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
                recovery_result = "stop"
            else:
                recovery_result = "continue"
            trace.record(
                "recovery.checked",
                RecoveryCheckedPayload(
                    previous_run_id=task.run_id, current_run_id=trusted.run_id,
                    checkpoint_ref=self._checkpoint_id(context, task),
                    operation_ids=[previous.data.operation_id] if previous.data.operation_id else [],
                    result=recovery_result,
                    reason_code="PUBLIC_CAPABILITY_RESUMED",
                ), "succeeded",
            )
            self.application.update_task(
                trusted.user_id, trusted.demo_round_id, trusted.task_id,
                task.revision, trusted.run_id, result.status,
                self._checkpoint_id(context, task),
                {**task.snapshot, "result": result.model_dump(mode="json")},
            )
            trace.record(
                "task.transition",
                TaskTransitionPayload(
                    previous_status=previous.status, status=result.status,
                    plan_revision=None, step_id=task.snapshot["capability_name"],
                    reason_code="TASK_RESUMED",
                    checkpoint_ref=self._checkpoint_id(context, task),
                ), "waiting" if result.status in {
                    TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL,
                } else "succeeded",
            )
            return result
