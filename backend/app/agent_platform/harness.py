"""One trusted task entry, public capability dispatch, checkpoint recovery and trace."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import errno
from hashlib import sha256
import os
from pathlib import Path
import re
from sqlite3 import Connection
from threading import Lock, RLock, local
from time import monotonic, sleep
from typing import Callable
from uuid import UUID, uuid4

from app.audit.journal import AuditJournal, run_key
from app.contracts.audit import (
    AuditEvent, ModelFinishedPayload, ModelStartedPayload, ModelUsage,
    RecoveryCheckedPayload, TaskTransitionPayload,
)
from app.contracts.common import TaskStatus
from app.contracts.platform import CapabilityDefinition, StartTransferInput, TrustedContext
from app.contracts.tasks import ModuleError, ModuleResult, TransferTaskView
from app.memory.adapter import MemoryAdapter, MemoryContext
from app.storage.application import ApplicationStore, TaskRecord
from app.storage.database import transaction

from .model import Planner, TransferProposal
from .registry import CapabilityRegistry


_LOCK_GUARD = Lock()
_TASK_LOCKS: dict[str, RLock] = {}
_HELD_LOCKS = local()
_CREDENTIAL_IN_REQUEST = re.compile(
    r"(?:验证码|短信码|动态码|一次性密码|otp|password|密码|口令)",
    re.IGNORECASE,
)


@contextmanager
def _bounded_thread_lock(lock: RLock, deadline: float):
    if not lock.acquire(timeout=max(0, deadline - monotonic())):
        raise TimeoutError("TASK_BUSY")
    try:
        yield
    finally:
        lock.release()


@contextmanager
def _task_lock(path: Path, task_id: str):
    deadline = monotonic() + 60
    key = f"{path.resolve()}:{task_id}"
    with _LOCK_GUARD:
        lock = _TASK_LOCKS.setdefault(key, RLock())
    with _bounded_thread_lock(lock, deadline):
        held = getattr(_HELD_LOCKS, "keys", set())
        if key in held:
            yield
            return
        lock_dir = path.parent / f"{path.name}.task-locks"
        lock_dir.mkdir(exist_ok=True)
        lock_path = lock_dir / f"{sha256(key.encode()).hexdigest()}.lock"
        with open(lock_path, "a+b") as handle:
            if handle.seek(0, 2) == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                        raise
                    if monotonic() >= deadline:
                        raise TimeoutError("TASK_BUSY") from exc
                    sleep(0.05)
            _HELD_LOCKS.keys = held | {key}
            try:
                yield
            finally:
                _HELD_LOCKS.keys = held
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class RunTrace:
    """Share this writer with future security and tool sinks to keep one event order."""

    def __init__(self, journal: AuditJournal, trusted: TrustedContext,
                 thread_id: str, trace_id: str):
        self.journal = journal
        self.trusted = trusted
        self.thread_id = thread_id
        self.trace_id = trace_id

    def record(self, event_type: str, payload: object, outcome: str, *,
               evidence: object | None = None, module: str = "agent_platform",
               parent_span_id: str | None = None, evidence_id: str | None = None,
               snapshots: dict[str, object] | None = None,
               target_session_id: str | None = None,
               write: Callable[[Connection, AuditEvent], None] | None = None) -> AuditEvent:
        if evidence is None:
            evidence_id = None
        elif isinstance(payload, ModelStartedPayload):
            evidence_id = evidence_id or payload.request_ref
        elif isinstance(payload, ModelFinishedPayload):
            evidence_id = evidence_id or payload.response_ref
        else:
            evidence_id = evidence_id or str(uuid4())
        base = AuditEvent(
            event_id=str(uuid4()), trace_id=self.trace_id, span_id=str(uuid4()),
            sequence=0, parent_span_id=parent_span_id,
            demo_round_id=self.trusted.demo_round_id,
            actor_id=self.trusted.user_id, session_id=self.trusted.session_id,
            target_session_id=target_session_id or self.trusted.session_id,
            target_user_id=self.trusted.user_id, thread_id=self.thread_id,
            task_id=self.trusted.task_id, run_id=self.trusted.run_id,
            module=module, event_type=event_type,
            timestamp=datetime.now(timezone.utc), logical_at=None,
            outcome=outcome, evidence_ref=evidence_id,
            evidence_status="available" if evidence is not None else "missing",
            missing_reason=None if evidence is not None else "event has no content snapshot",
            payload=payload,
        )
        with transaction(self.journal.path) as connection:
            highest = connection.execute(
                "SELECT MAX(sequence) FROM audit_events WHERE run_key = ?", (run_key(base),),
            ).fetchone()[0]
            event = base.model_copy(update={
                "sequence": highest + 1 if highest is not None else 0,
            })
            fresh = {ref: value for ref, value in (snapshots or {}).items()
                     if connection.execute(
                         "SELECT 1 FROM audit_evidence WHERE evidence_id = ?", (ref,),
                     ).fetchone() is None}
            saved = self.journal.append_in_transaction(
                connection, event, evidence=evidence, snapshots=fresh,
            )
            if write is not None:
                write(connection, saved)
            return saved


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

    @staticmethod
    def _recovery_result(status: TaskStatus) -> str:
        if status in {TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL,
                      TaskStatus.NEEDS_ATTENTION}:
            return "wait"
        if status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return "stop"
        return "continue"

    @staticmethod
    def _check_result_scope(result: ModuleResult[TransferTaskView],
                            trusted: TrustedContext) -> None:
        if result.task_id != trusted.task_id or result.run_id != trusted.run_id:
            raise ValueError("CAPABILITY_CONTEXT_MISMATCH")

    def _trace(self, trusted: TrustedContext, task: TaskRecord) -> RunTrace:
        return RunTrace(self.audit, trusted, task.checkpoint_thread_id,
                        task.snapshot["trace_id"])

    def _checkpoint_id(self, context: MemoryContext, task: TaskRecord) -> str | None:
        saver = self.memory.checkpointer(context, task.task_id)
        saved = saver.get_tuple({"configurable": {"thread_id": task.checkpoint_thread_id}})
        return saved.config["configurable"]["checkpoint_id"] if saved else None

    def start(self, trusted: TrustedContext, request_id: UUID,
              intent_text: str) -> ModuleResult[TransferTaskView]:
        with _task_lock(self.application.path, trusted.task_id):
            context = self._scope(trusted)
            self._authorize(trusted, "transfer.start_transfer")
            if _CREDENTIAL_IN_REQUEST.search(intent_text):
                raise ValueError("CREDENTIAL_IN_REQUEST")
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
                model_started = trace.record(
                    "model.started",
                    ModelStartedPayload(
                        model_call_id=model_call_id, provider=self.planner.provider,
                        model=self.planner.model_name,
                        config_version=self.planner.config_version,
                        request_ref=str(uuid4()),
                    ),
                    "started",
                    evidence={"intent_sha256": sha256(intent_text.encode()).hexdigest(),
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
                        ), "failed", parent_span_id=model_started.span_id,
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
                    ), "succeeded", evidence={
                        "proposal_sha256": sha256(proposal.model_dump_json().encode()).hexdigest(),
                        "capability_name": proposal.capability_name,
                    },
                    parent_span_id=model_started.span_id,
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
            entry = registration.factory(trusted, saver, trace)
            result = entry.start(trusted, StartTransferInput(
                request_id=request_id, intent_text=intent_text,
                payer_account_id=proposal.payer_account_id,
                payee_hint=proposal.payee_hint, amount_fen=proposal.amount_fen,
            ), thread_id=task.checkpoint_thread_id)
            self._check_result_scope(result, trusted)
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

    def _operation_ids(self, task) -> list[UUID]:
        result = task.snapshot.get("result")
        data = result.get("data") if isinstance(result, dict) else None
        operation_id = data.get("operation_id") if isinstance(data, dict) else None
        if operation_id:
            return [UUID(str(operation_id))]
        operations = self.application.list_task_operations(
            task.user_id, task.demo_round_id, task.task_id,
        )
        return [UUID(operations[-1].operation_id)] if operations else []

    def recover_session(self, trusted: TrustedContext) -> ModuleResult[TransferTaskView]:
        """Transfer an owned task to the authenticated session, then resume its public capability."""
        with _task_lock(self.application.path, trusted.task_id):
            self._scope(trusted)
            self._authorize(trusted, "transfer.start_transfer")
            task = self.application.get_task(
                trusted.user_id, trusted.demo_round_id, trusted.task_id,
            )
            if task is None:
                raise PermissionError("ACCESS_DENIED")

            marker = task.snapshot.get("session_recovery")
            marker_matches = (
                isinstance(marker, dict)
                and marker.get("target_session_id") == trusted.session_id
                and marker.get("phase") in {"prepared", "transitioned", "complete"}
            )
            if task.session_id == trusted.session_id and not marker_matches:
                raise ValueError("SESSION_RECOVERY_NOT_REQUIRED")

            if marker_matches:
                source_session_id = marker["source_session_id"]
                previous_run_id = marker["source_run_id"]
                if task.session_id not in {source_session_id, trusted.session_id}:
                    raise PermissionError("ACCESS_DENIED")
                if marker.get("phase") == "complete" and task.run_id == trusted.run_id:
                    return self._result(task)
            else:
                source_session_id = task.session_id
                previous_run_id = task.run_id
                trace = self._trace(trusted, task)
                operation_ids = self._operation_ids(task)
                trace.record(
                    "recovery.checked",
                    RecoveryCheckedPayload(
                        previous_run_id=previous_run_id, current_run_id=trusted.run_id,
                        checkpoint_ref=task.checkpoint_id, operation_ids=operation_ids,
                        result="continue", reason_code="SESSION_RECOVERY_STARTED",
                    ),
                    "started", target_session_id=source_session_id,
                )
                marker = {
                    "source_session_id": source_session_id,
                    "target_session_id": trusted.session_id,
                    "source_run_id": previous_run_id,
                    "target_run_id": trusted.run_id,
                    "expected_revision": task.revision + 1,
                    "phase": "prepared",
                }
                snapshot = {**task.snapshot, "session_recovery": marker}
                task = self.application.update_task(
                    trusted.user_id, trusted.demo_round_id, trusted.task_id,
                    task.revision, task.run_id, task.status, task.checkpoint_id, snapshot,
                )

            if task.session_id == source_session_id:
                task = self.application.transition_task_session(
                    trusted.user_id, trusted.demo_round_id, trusted.task_id,
                    source_session_id, trusted.session_id, marker["expected_revision"],
                )
            elif task.session_id != trusted.session_id:
                raise PermissionError("ACCESS_DENIED")

            if marker.get("phase") != "transitioned":
                marker = {**marker, "phase": "transitioned"}
                snapshot = {**task.snapshot, "session_recovery": marker}
                task = self.application.update_task(
                    trusted.user_id, trusted.demo_round_id, trusted.task_id,
                    task.revision, task.run_id, task.status, task.checkpoint_id, snapshot,
                )

            context = self._scope(trusted)
            trace = self._trace(trusted, task)
            capability_name = task.snapshot.get("capability_name", "transfer.start_transfer")
            registration = self.registry.get(capability_name)
            saver = self.memory.checkpointer(context, task.task_id)
            entry = registration.factory(trusted, saver, trace)
            try:
                checkpoint_context = entry.checkpoint_context(
                    trusted, thread_id=task.checkpoint_thread_id,
                )
                initializing_here = (
                    checkpoint_context is not None
                    and checkpoint_context.session_id == trusted.session_id
                    and marker.get("initializing_checkpoint") is True
                )
                if checkpoint_context is None or initializing_here:
                    if "result" in task.snapshot and checkpoint_context is None:
                        # A model failure can finish a task before business execution starts.
                        result = self._result(task).model_copy(update={"run_id": trusted.run_id})
                    elif initializing_here:
                        # The native target-session graph already exists, including terminal state.
                        result = entry.resume(trusted, {}, thread_id=task.checkpoint_thread_id)
                    else:
                        # Continue the saved request/proposal; no business state has run yet.
                        marker = {**marker, "initializing_checkpoint": True}
                        task = self.application.update_task(
                            trusted.user_id, trusted.demo_round_id, trusted.task_id,
                            task.revision, task.run_id, task.status, task.checkpoint_id,
                            {**task.snapshot, "session_recovery": marker},
                        )
                        result = self.resume(trusted, {})
                        task = self.application.get_task(
                            trusted.user_id, trusted.demo_round_id, trusted.task_id,
                        )
                else:
                    checkpoint_source = marker.get("checkpoint_source_session_id", source_session_id)
                    if checkpoint_context.session_id != trusted.session_id:
                        checkpoint_source = checkpoint_context.session_id
                    marker = {**marker, "checkpoint_source_session_id": checkpoint_source}
                    task = self.application.update_task(
                        trusted.user_id, trusted.demo_round_id, trusted.task_id,
                        task.revision, task.run_id, task.status, task.checkpoint_id,
                        {**task.snapshot, "session_recovery": marker},
                    )
                    result = entry.recover_session(
                        trusted, source_session_id=checkpoint_source,
                        thread_id=task.checkpoint_thread_id,
                    )
                self._check_result_scope(result, trusted)
            except Exception:
                trace.record(
                    "recovery.checked",
                    RecoveryCheckedPayload(
                        previous_run_id=previous_run_id, current_run_id=trusted.run_id,
                        checkpoint_ref=task.checkpoint_id,
                        operation_ids=self._operation_ids(task),
                        result="stop", reason_code="TRANSFER_SESSION_RECOVERY_FAILED",
                    ),
                    "failed", target_session_id=source_session_id,
                )
                raise

            operation_ids = [result.data.operation_id] if result.data and result.data.operation_id else []
            trace.record(
                "recovery.checked",
                RecoveryCheckedPayload(
                    previous_run_id=previous_run_id, current_run_id=trusted.run_id,
                    checkpoint_ref=self._checkpoint_id(context, task),
                    operation_ids=operation_ids, result=self._recovery_result(result.status),
                    reason_code="SESSION_RECOVERY_COMPLETED",
                ),
                "succeeded", target_session_id=source_session_id,
            )
            marker = {**marker, "phase": "complete"}
            snapshot = {
                **task.snapshot, "capability_name": capability_name,
                "session_recovery": marker,
                "result": result.model_dump(mode="json"),
            }
            self.application.update_task(
                trusted.user_id, trusted.demo_round_id, trusted.task_id,
                task.revision, trusted.run_id, result.status,
                self._checkpoint_id(context, task), snapshot,
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
        with _task_lock(self.application.path, trusted.task_id):
            context = self._scope(trusted)
            task = self.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
            if task is None:
                raise ValueError("TASK_NOT_FOUND")
            self._check_task(task, trusted)
            if "result" not in task.snapshot:
                if task.snapshot["config_version"] != self.planner.config_version:
                    raise ValueError("MODEL_CONFIG_CHANGED")
                self._authorize(trusted, "transfer.start_transfer")
                if task.run_id != trusted.run_id:
                    self.application.update_task(
                        trusted.user_id, trusted.demo_round_id, trusted.task_id,
                        task.revision, trusted.run_id, TaskStatus.RUNNING,
                        task.checkpoint_id, task.snapshot,
                    )
                result = self.start(
                    trusted, UUID(task.snapshot["request_id"]), task.snapshot["intent_text"],
                )
                current = self.application.get_task(
                    trusted.user_id, trusted.demo_round_id, trusted.task_id,
                )
                self._trace(trusted, current).record(
                    "recovery.checked",
                    RecoveryCheckedPayload(
                        previous_run_id=task.run_id, current_run_id=trusted.run_id,
                        checkpoint_ref=current.checkpoint_id,
                        operation_ids=[result.data.operation_id] if result.data and result.data.operation_id else [],
                        result=self._recovery_result(result.status),
                        reason_code="UNFINISHED_TASK_RECOVERED",
                    ), "succeeded",
                )
                return result
            previous = self._result(task)
            if previous.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
                return previous
            if task.snapshot["config_version"] != self.planner.config_version:
                raise ValueError("MODEL_CONFIG_CHANGED")
            self._authorize(trusted, task.snapshot["capability_name"])
            trace = self._trace(trusted, task)
            registration = self.registry.get(task.snapshot["capability_name"])
            saver = self.memory.checkpointer(context, trusted.task_id)
            entry = registration.factory(trusted, saver, trace)
            try:
                result = entry.resume(trusted, response, thread_id=task.checkpoint_thread_id)
                self._check_result_scope(result, trusted)
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
            trace.record(
                "recovery.checked",
                RecoveryCheckedPayload(
                    previous_run_id=task.run_id, current_run_id=trusted.run_id,
                    checkpoint_ref=self._checkpoint_id(context, task),
                    operation_ids=[previous.data.operation_id] if previous.data.operation_id else [],
                    result=self._recovery_result(result.status),
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
