"""One trusted task entry, public capability dispatch, checkpoint recovery and trace."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
from hashlib import sha256
from inspect import Parameter, signature
import os
from pathlib import Path
import re
from sqlite3 import Connection, Error as DatabaseError
from threading import Lock, RLock, local
from time import monotonic, sleep
from typing import Callable
from uuid import UUID, uuid4

from app.audit.journal import AuditJournal, redact, run_key
from app.audit.output_guard import probe_output
from app.contracts.audit import (
    AuditEvent, ChatMessagePayload, ContextChangedPayload, ModelFinishedPayload, ModelStartedPayload,
    ModelUsage, RecoveryCheckedPayload, TaskTransitionPayload,
)
from app.contracts.common import OperationLevel, TaskStatus
from app.contracts.bills import AnomalyResult, BillDetails, BillReport, BillScope, SpendingSummary
from pydantic import ValidationError
from app.contracts.cross import CrossStartInput
from app.contracts.platform import CapabilityDefinition, StartTransferInput, TrustedContext
from app.contracts.tasks import ModuleError, ModuleResult, TransferTaskView
from app.memory.adapter import MemoryAdapter, MemoryContext
from app.storage.application import ApplicationStore, ArrangementConflictError, TaskRecord
from app.storage.database import transaction

from .model import ContinueProposal, Planner, ReplyOnly, TransferProposal
from .input_privacy import has_chat_secret
from .risk_conversation import RiskConversation
from .registry import CapabilityRegistry
from .untrusted_data import MAX_ITEMS, UntrustedData, tool_observation, user_material


_LOCK_GUARD = Lock()
_TASK_LOCKS: dict[str, RLock] = {}
_HELD_LOCKS = local()
_SELECTED_CAPABILITIES = frozenset({
    "bills.summarize", "bills.generate_report", "bills.detect_anomalies",
    "subscription.cancel_subscription", "subscription.list_subscriptions",
    "transfer.list_accounts", "transfer.list_payees",
})
# A request that carries outside material may only be analysed. The refusal is
# fixed here, never taken from the model or the material itself (S2 / A03).
_UNTRUSTED_MATERIAL_REFUSAL = (
    "这段资料我只当作线索来分析，不会据此替您发起任何转账或业务办理。"
    "请先通过银行官方渠道核实来源，不要向陌生账户汇款，也不要向他人透露验证码。"
)
# The audit output probe mirrors journal.redact's free-text rules, which do not
# cover an English password/passwd/pwd label. A reply must not widen that gap into
# an actual secret leak, so a label followed by an ASCII value still fails closed
# (v05-observer-seams/07). Prose such as "请不要把 password 告诉别人" has no value
# and stays allowed.
_ENGLISH_SECRET_LABEL = re.compile(
    r"(?:password|passwd|pwd)\s*(?:[:：=]|是|为)\s*[A-Za-z0-9!@#$%^&*()_\-]{4,}",
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


def _task_outcome(status: TaskStatus) -> str:
    """Audit outcome for a task status; denials and failures are never 'succeeded'.

    The frozen audit outcome enum is started/succeeded/failed/waiting/unknown/denied,
    so statuses outside the three mapped ones fall back to 'unknown'.
    """

    if status in {TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL}:
        return "waiting"
    if status == TaskStatus.SUCCEEDED:
        return "succeeded"
    if status == TaskStatus.FAILED:
        return "failed"
    return "unknown"


class RunTrace:
    """Share this writer with future security and tool sinks to keep one event order."""

    def __init__(self, journal: AuditJournal, trusted: TrustedContext,
                 thread_id: str, trace_id: str):
        self.journal = journal
        self.trusted = trusted
        self.thread_id = thread_id
        self.trace_id = trace_id
        self.transfer_data: TransferTaskView | None = None

    def record(self, event_type: str, payload: object, outcome: str, *,
               evidence: object | None = None, module: str = "agent_platform",
               parent_span_id: str | None = None, evidence_id: str | None = None,
               snapshots: dict[str, object] | None = None,
               target_session_id: str | None = None,
               missing_reason: str | None = None,
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
            missing_reason=(None if evidence is not None else
                            missing_reason or "event has no content snapshot"),
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
        self.risk_conversation = RiskConversation(application.path)

    def _authorize(self, trusted: TrustedContext, name: str) -> None:
        definition = self.registry.get(name).definition
        if not self.authorize_capability(trusted, definition):
            raise PermissionError("ACCESS_DENIED")

    def _scope(self, trusted: TrustedContext) -> MemoryContext:
        context = MemoryContext(trusted.user_id, trusted.session_id, trusted.demo_round_id)
        self.memory.agent_backend(context)
        return context

    @staticmethod
    def _check_intent_text(intent_text: str) -> None:
        if has_chat_secret(intent_text):
            raise ValueError("CREDENTIAL_IN_REQUEST")

    @staticmethod
    def _check_task(task: TaskRecord, trusted: TrustedContext) -> None:
        if task.session_id != trusted.session_id:
            raise PermissionError("ACCESS_DENIED")

    @staticmethod
    def _result(task: TaskRecord) -> ModuleResult:
        if "result" not in task.snapshot:
            raise ValueError("TASK_NOT_READY")
        # The transfer path keeps its typed payload — its consumers read the fields.
        # A second module's `data` is its own displayable result (§6.5), which the
        # platform hands back as-is instead of forcing the transfer view (Issue #122).
        # The prefix names the module, not the payload type: a later transfer.*
        # capability returning another view (§5.2 T03/T04) must revisit this dispatch.
        if task.snapshot.get("capability_name", "transfer.start_transfer") == "transfer.start_transfer":
            return ModuleResult[TransferTaskView].model_validate(task.snapshot["result"])
        return ModuleResult.model_validate(task.snapshot["result"])

    @staticmethod
    def _recovery_result(status: TaskStatus) -> str:
        if status in {TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL,
                      TaskStatus.NEEDS_ATTENTION}:
            return "wait"
        if status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return "stop"
        return "continue"

    @staticmethod
    def _check_result_scope(result: ModuleResult,
                            trusted: TrustedContext) -> None:
        if result.task_id != trusted.task_id or result.run_id != trusted.run_id:
            raise ValueError("CAPABILITY_CONTEXT_MISMATCH")

    @staticmethod
    def _operation_ids_from(result: ModuleResult) -> list[UUID]:
        # Today only the transfer payload exposes an operation reference in this
        # envelope; a module whose payload carries one extends this instead of the
        # platform guessing transfer fields on it (Issue #122).
        data = result.data
        if isinstance(data, TransferTaskView) and data.operation_id:
            return [data.operation_id]
        return []

    def _trace(self, trusted: TrustedContext, task: TaskRecord) -> RunTrace:
        return RunTrace(self.audit, trusted, task.checkpoint_thread_id,
                        task.snapshot["trace_id"])

    def _checkpoint_id(self, context: MemoryContext, task: TaskRecord) -> str | None:
        saver = self.memory.checkpointer(context, task.task_id)
        saved = saver.get_tuple({"configurable": {"thread_id": task.checkpoint_thread_id}})
        return saved.config["configurable"]["checkpoint_id"] if saved else None

    def understand(self, trusted: TrustedContext,
                   intent_text: str) -> TransferProposal | ReplyOnly | ContinueProposal:
        """Classify one message without creating a business task or invoking a capability."""
        context = self._scope(trusted)
        self._check_intent_text(intent_text)
        thread_id = self.memory.conversation_thread_id(context)
        trace = RunTrace(self.audit, trusted, thread_id, str(uuid4()))
        return self._understand_with_trace(trusted, intent_text, trace)

    def _select_outcome(self, trusted: TrustedContext, intent_text: str,
                        thread_id: str,
                        untrusted_data: Sequence[UntrustedData] = (),
                        ) -> TransferProposal | ReplyOnly | ContinueProposal:
        context = self._scope(trusted)
        summary = self._session_context_summary(trusted)
        # Only pass a keyword when it carries content: injected planners with the
        # older five/six-argument signature keep working (evaluation seam, #84).
        planning_options: dict[str, object] = {}
        if summary is not None:
            planning_options["context_summary"] = summary
        if untrusted_data and self._accepts_untrusted_data():
            planning_options["untrusted_data"] = untrusted_data
        outcome = self.planner.select(
            intent_text, trusted, self.registry.public_catalog(), self.memory, thread_id,
            **planning_options,
        )
        if not isinstance(outcome, (TransferProposal, ContinueProposal, ReplyOnly)):
            raise ValueError("MODEL_OUTCOME_INVALID")
        if isinstance(outcome, ContinueProposal):
            outcome = self._validate_continuation(trusted, outcome)
        if isinstance(outcome, ReplyOnly) and not outcome.message.strip():
            raise ValueError("MODEL_OUTCOME_INVALID")
        if isinstance(outcome, ReplyOnly):
            # A reply may explain "验证码不要告诉别人" (S1); only a credential value
            # stays fail-closed. User input also checks secret values before planning.
            findings = probe_output(outcome.message).findings
            if (any(finding.kind == "credential" for finding in findings)
                    or _ENGLISH_SECRET_LABEL.search(outcome.message)):
                raise ValueError("CREDENTIAL_IN_REQUEST")
            outcome = ReplyOnly.model_validate(redact(outcome.model_dump(mode="json")))
        return outcome

    def _validate_continuation(self, trusted: TrustedContext, proposal: ContinueProposal):
        tasks = [task for task in self.application.list_session_tasks(
            trusted.user_id, trusted.demo_round_id, trusted.session_id)
            if task.status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}]
        # With several unfinished tasks, the UI must select one explicitly via F10.
        if len(tasks) != 1 or tasks[0].task_id != proposal.task_id:
            return ReplyOnly(message="请先在卡片中选择要继续的那项业务，避免办错。")
        task = tasks[0]
        result = task.snapshot.get("result") or {}
        interaction = result.get("interaction") or {}
        allowed = result.get("allowed_actions") or []
        read_unknown = proposal.action == "query" and result.get("recovery_reason") == "OPERATION_UNKNOWN"
        valid = (not result.get("recovery_required") or read_unknown) and task.revision == proposal.task_revision
        if proposal.action == "revise":
            valid = (valid and task.snapshot.get("capability_name") == "transfer.start_transfer"
                     and task.status == TaskStatus.WAITING_APPROVAL
                     and interaction.get("kind") == "confirmation")
        else:
            valid = valid and proposal.action in allowed
            if proposal.action == "provide_input":
                valid = valid and task.status == TaskStatus.WAITING_INPUT and interaction.get("kind") == "input"
                if proposal.selected_option_id is not None:
                    valid = valid and proposal.selected_option_id in {
                        item.get("id") for item in interaction.get("options", [])}
        if not valid:
            return ReplyOnly(message="任务状态已变化，请查看当前卡片后继续；确认和验证码必须使用专用入口。")
        for field in ("text", "payee_hint", "payer_account_id"):
            value = getattr(proposal, field)
            if value and has_chat_secret(value, numeric_field=field == "text" and interaction.get("required_fields") == ["amount_fen"]):
                raise ValueError("CREDENTIAL_IN_REQUEST")
        self._authorize(trusted, task.snapshot["capability_name"])
        return proposal

    def _accepts_untrusted_data(self) -> bool:
        """Old stand-ins that never declared the keyword must keep working (#84).

        Tool returns exist on ordinary follow-ups too, so data presence alone cannot
        decide compatibility; the planner's own signature says whether it can read
        the blocks. Without the keyword the planner simply never sees them.
        """
        try:
            parameters = signature(self.planner.select).parameters
        except (TypeError, ValueError):
            return False
        return "untrusted_data" in parameters or any(
            parameter.kind is Parameter.VAR_KEYWORD for parameter in parameters.values()
        )

    def _untrusted_blocks(self, trusted: TrustedContext,
                          material: UntrustedData | None = None) -> list[UntrustedData]:
        """The blocks the planner may read this turn; user material keeps the first slot."""
        blocks = [material] if material is not None else []
        blocks.extend(self._tool_return_blocks(trusted, MAX_ITEMS - len(blocks)))
        return blocks

    def _tool_return_blocks(self, trusted: TrustedContext,
                            limit: int) -> list[UntrustedData]:
        """Bank display facts this session's tasks already received, as data (S3)."""
        if limit <= 0:
            return []
        blocks: list[UntrustedData] = []
        for task in self.application.list_session_tasks(
            trusted.user_id, trusted.demo_round_id, trusted.session_id,
        ):
            result = task.snapshot.get("result")
            data = result.get("data") if isinstance(result, dict) else None
            if isinstance(data, dict) and task.snapshot.get("capability_name") in {
                    "transfer.list_accounts", "transfer.list_payees"}:
                block = tool_observation(f"mock-bank.own-query:{task.task_id[:8]}", data)
                if block is not None:
                    blocks.append(block)
                if len(blocks) >= limit:
                    break
                continue
            # Only bank-returned payee display fields are a tool return; other
            # modules' payloads never become prompt data this way.
            payee = data.get("payee") if isinstance(data, dict) else None
            if not isinstance(payee, dict):
                continue
            value = {name: payee[name] for name in
                     ("name_masked", "account_masked", "bank_name", "remark")
                     if payee.get(name)}
            block = tool_observation(f"mock-bank.payee-display:{task.task_id[:8]}", value)
            if block is None:
                continue
            blocks.append(block)
            if len(blocks) >= limit:
                break
        return blocks

    @staticmethod
    def _record_resource_load(trace: RunTrace, blocks: list[UntrustedData]) -> None:
        """Audit what external data entered this prompt before the model sees it."""
        if not blocks:
            return
        after_ref = str(uuid4())
        trace.record(
            "context.changed",
            ContextChangedPayload(
                change="resource_load", before_ref=None, after_ref=after_ref,
                source_refs=[block.source for block in blocks],
            ),
            "succeeded",
            evidence=[{"source": block.source, "kind": block.kind,
                       "content": block.content} for block in blocks],
            evidence_id=after_ref,
            # Source references are auditable IDs of the frozen event; keeping one
            # small snapshot per source lets a replay resolve every reference.
            snapshots={block.source: {"source": block.source, "kind": block.kind}
                       for block in blocks},
        )

    def _deny_untrusted_material(self, trace: RunTrace,
                                 proposal: TransferProposal | ContinueProposal) -> ReplyOnly:
        """A material-bearing request may only be analysed: drop its proposal (S2)."""
        refusal = ReplyOnly(message=_UNTRUSTED_MATERIAL_REFUSAL)
        content_ref = str(uuid4())
        trace.record(
            "chat.message",
            ChatMessagePayload(
                message_id=str(uuid4()), role="assistant",
                content_ref=content_ref, related_task_ids=[],
            ),
            "denied", evidence_id=content_ref,
            # Evidence carries the dropped proposal only; the material text itself
            # stays out of this event.
            evidence={
                "message": refusal.message,
                "reason_code": "UNTRUSTED_MATERIAL_BLOCKED_ACTION",
                "dropped_proposal": proposal.model_dump(mode="json"),
            },
        )
        return refusal

    _SUMMARY_TASK_LIMIT = 3

    def _session_context_summary(self, trusted: TrustedContext) -> str | None:
        """Trusted structured pending-business summary for the planning prompt (#84)."""
        lines: list[str] = []
        for task in self.application.list_session_tasks(
            trusted.user_id, trusted.demo_round_id, trusted.session_id,
        ):
            if task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED,
                               TaskStatus.CANCELLED}:
                continue
            phrase = self._pending_phrase(task)
            if phrase is None:
                continue
            intent = str(redact(str(task.snapshot.get("intent_text") or "").strip(), free_text=True))
            result = task.snapshot.get("result") or {}
            interaction = result.get("interaction") or {}
            options = [{"id": item.get("id"), "label": redact(item.get("label", ""), free_text=True)}
                       for item in interaction.get("options", [])]
            meta = (f"task_id={task.task_id}, task_revision={task.revision}, "
                    f"capability={task.snapshot.get('capability_name')}, "
                    f"allowed_actions={result.get('allowed_actions', [])}, "
                    f"required_fields={interaction.get('required_fields', [])}, options={options}")
            lines.append(f"- {meta}；{phrase}：{intent}")
            if len(lines) >= self._SUMMARY_TASK_LIMIT:
                break
        if not lines:
            return None
        summary = "\n".join(lines)
        return summary or None

    @staticmethod
    def _pending_phrase(task: TaskRecord) -> str | None:
        if task.status is TaskStatus.WAITING_APPROVAL:
            result = task.snapshot.get("result")
            interaction = result.get("interaction") if isinstance(result, dict) else None
            if isinstance(interaction, dict) and interaction.get("kind") == "verification":
                return "有一笔业务等待身份验证，验证须走专用通道，聊天不能代替"
            return "有一笔业务等待用户在确认单上确认办理，聊天确认不算数"
        if task.status is TaskStatus.WAITING_INPUT:
            return "有一笔业务等待用户补充信息"
        if task.status is TaskStatus.RUNNING:
            return "有一笔业务办理中"
        if task.status is TaskStatus.NEEDS_ATTENTION:
            return "有一笔业务结果待核实，只能查询原操作"
        return None

    def _understand_with_trace(self, trusted: TrustedContext, intent_text: str,
                               trace: RunTrace,
                               material: UntrustedData | None = None,
                               ) -> TransferProposal | ReplyOnly | ContinueProposal:
        blocks = self._untrusted_blocks(trusted, material)
        self._record_resource_load(trace, blocks)
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
            missing_reason=("full provider request, including system prompt and "
                            "conversation context, is unavailable at the harness boundary"),
        )
        started = monotonic()
        try:
            outcome = self._select_outcome(trusted, intent_text, trace.thread_id, blocks)
        except Exception:
            model_error = ModuleError(
                code="MODEL_UNDERSTANDING_FAILED", source="platform", field=None,
                reason="模型暂未形成受控回复或业务候选", upstream_code=None,
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
            raise ValueError("MODEL_UNDERSTANDING_FAILED") from None

        if isinstance(outcome, ReplyOnly):
            evidence = {
                "outcome": outcome.kind,
                "response": {"message": outcome.message},
            }
        elif isinstance(outcome, ContinueProposal):
            evidence = {"outcome": outcome.kind, "proposal": outcome.model_dump(mode="json")}
        else:
            evidence = {
                "proposal": {
                    "recipient_name": outcome.payee_hint,
                    "amount_fen": outcome.amount_fen,
                    "payer_account_id": outcome.payer_account_id,
                },
                "capability_name": outcome.capability_name,
            }
        trace.record(
            "model.finished",
            ModelFinishedPayload(
                model_call_id=model_call_id, response_ref=str(uuid4()),
                duration_ms=int((monotonic() - started) * 1000),
                usage=ModelUsage(input_tokens=None, output_tokens=None), error=None,
            ), "succeeded", evidence=evidence,
            parent_span_id=model_started.span_id,
        )
        return outcome

    def _inherited_bill_scope(self, trusted, capability):
        if (not trusted.parent_task_id or capability not in
                {"bills.summarize", "bills.generate_report", "bills.detect_anomalies"}):
            return None
        source = self.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.parent_task_id)
        if source is None or source.session_id != trusted.session_id or source.status != TaskStatus.SUCCEEDED:
            return None
        kind = source.snapshot.get("capability_name")
        data = (source.snapshot.get("result") or {}).get("data")
        if not isinstance(data, dict):
            return None
        try:
            if kind == "bills.generate_report":
                result = BillReport.model_validate(data)
            elif kind == "bills.summarize":
                result = (BillDetails if "transactions" in data else SpendingSummary).model_validate(data)
            elif kind == "bills.detect_anomalies" and source.snapshot.get("completed_bill_scope") is not None:
                AnomalyResult.model_validate(data)
                # The module reports the actual completed range after any date
                # or account changes; the initial inherited range is not a result.
                return BillScope.model_validate(source.snapshot["completed_bill_scope"]).model_dump(mode="json")
            else:
                return None
        except ValidationError:
            return None
        return result.scope.model_dump(mode="json")

    def start(self, trusted: TrustedContext, request_id: UUID,
              intent_text: str) -> ModuleResult:
        result = self.handle_message(trusted, request_id, intent_text)
        if isinstance(result, ReplyOnly):
            raise ValueError("NO_TRANSFER_INTENT")
        return result

    def start_selected(self, trusted: TrustedContext, request_id: UUID,
                       intent_text: str, capability_name: str) -> ModuleResult:
        """Server-validated result-card selection, with the ordinary execution gates."""
        if capability_name not in _SELECTED_CAPABILITIES:
            raise ValueError("INVALID_ARGUMENT")
        return self.handle_message(trusted, request_id, intent_text,
                                   selected_capability=capability_name)

    def handle_message(self, trusted: TrustedContext, request_id: UUID,
                       intent_text: str,
                       untrusted_content: str | None = None,
                       *, allow_continuation: bool = False,
                       selected_capability: str | None = None,
                       ) -> ModuleResult | ReplyOnly | ContinueProposal:
        """Return a controlled chat reply or continue the existing transfer path."""
        with _task_lock(self.application.path, trusted.task_id):
            context = self._scope(trusted)
            self._check_intent_text(intent_text)
            task = self.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
            if task is None:
                pending = [item for item in self.application.list_session_tasks(
                    trusted.user_id, trusted.demo_round_id, trusted.session_id)
                    if item.status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}
                    and item.snapshot.get("capability_name") == "transfer.start_transfer"]
                # Record before understanding, so a failed model call cannot hide
                # newly disclosed coercion from the original task's next approval.
                for item in pending:
                    self.risk_conversation.append(trusted, item.task_id, request_id, intent_text)
            outcome: TransferProposal | ReplyOnly | None = None
            if task is None:
                trace_id = str(uuid4())
                thread_id = self.memory.conversation_thread_id(context)
                trace = RunTrace(self.audit, trusted, thread_id, trace_id)
                material = user_material(untrusted_content) if untrusted_content else None
                if selected_capability is not None:
                    if selected_capability not in _SELECTED_CAPABILITIES:
                        raise ValueError("INVALID_ARGUMENT")
                    outcome = TransferProposal(capability_name=selected_capability)
                else:
                    outcome = self._understand_with_trace(trusted, intent_text, trace, material)
                if material is not None and isinstance(outcome, (TransferProposal, ContinueProposal)):
                    # Deterministic gate: outside material may be read and explained,
                    # never turned into a task, a tool call or a funds action (S2).
                    return self._deny_untrusted_material(trace, outcome)
                if isinstance(outcome, ReplyOnly):
                    return outcome
                if isinstance(outcome, ContinueProposal):
                    return outcome if allow_continuation else ReplyOnly(
                        message="请通过当前任务卡片补充或修改信息，确认与验证必须使用专用入口。")
                self._authorize(trusted, outcome.capability_name)
                if outcome.amount_fen is not None and outcome.amount_fen <= 0:
                    refusal = ReplyOnly(message="转账金额必须大于零，请重新输入有效金额。")
                    content_ref = str(uuid4())
                    trace.record(
                        "chat.message", ChatMessagePayload(
                            message_id=str(uuid4()), role="assistant",
                            content_ref=content_ref, related_task_ids=[],
                        ), "denied", evidence_id=content_ref,
                        evidence={"message": refusal.message, "reason_code": "INVALID_AMOUNT"},
                    )
                    return refusal
                task = self.application.create_task(
                    trusted.task_id, trusted.user_id, trusted.session_id,
                    trusted.demo_round_id, trusted.run_id, TaskStatus.RUNNING,
                    {"request_id": str(request_id), "intent_text": intent_text,
                     "config_version": self.planner.config_version,
                     "selected_capability": selected_capability,
                     "bill_source_task_id": trusted.parent_task_id,
                     "bill_scope": self._inherited_bill_scope(trusted, outcome.capability_name),
                     "trace_id": trace_id},
                )
            else:
                self._check_task(task, trusted)
                self._authorize(trusted, task.snapshot.get("capability_name",
                                                           "transfer.start_transfer"))
            if task.run_id != trusted.run_id:
                raise ValueError("USE_RESUME_FOR_NEW_RUN")
            snapshot = task.snapshot
            if selected_capability is not None and snapshot.get("selected_capability") != selected_capability:
                raise ValueError("REQUEST_CONFLICT")
            if outcome is None and snapshot.get("selected_capability") is not None:
                outcome = TransferProposal(capability_name=snapshot["selected_capability"])
            if snapshot["request_id"] != str(request_id) or snapshot["intent_text"] != intent_text:
                raise ValueError("REQUEST_CONFLICT")
            if snapshot["config_version"] != self.planner.config_version:
                raise ValueError("MODEL_CONFIG_CHANGED")
            if "result" in snapshot:
                return self._result(task)

            trace = self._trace(trusted, task)
            if "proposal" not in snapshot:
                try:
                    if outcome is None:
                        outcome = self._understand_with_trace(trusted, intent_text, trace)
                    if isinstance(outcome, ReplyOnly):
                        raise ValueError("NO_TRANSFER_INTENT")
                    proposal = outcome
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
                    failure = ModuleResult[TransferTaskView](
                        task_id=trusted.task_id, run_id=trusted.run_id,
                        status=TaskStatus.FAILED, data=None,
                        message="暂时无法安全处理这条消息，请重新发起并核对信息。",
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
            bill_options = {}
            if (proposal.capability_name in {"bills.summarize", "bills.generate_report", "bills.detect_anomalies"}
                    and snapshot.get("bill_scope") is not None):
                bill_options["inherited_scope"] = BillScope.model_validate(snapshot["bill_scope"])
            result = entry.start(trusted, StartTransferInput(
                request_id=request_id, intent_text=intent_text,
                payer_account_id=proposal.payer_account_id,
                payee_hint=proposal.payee_hint, amount_fen=proposal.amount_fen,
            ), thread_id=task.checkpoint_thread_id, **bill_options)
            self._check_result_scope(result, trusted)
            updated = {**snapshot, "capability_name": proposal.capability_name,
                       "result": result.model_dump(mode="json")}
            if proposal.capability_name == "bills.detect_anomalies" and result.status == TaskStatus.SUCCEEDED:
                completed = entry.completed_scope(trusted, thread_id=task.checkpoint_thread_id)
                updated["completed_bill_scope"] = completed.model_dump(mode="json") if completed else None
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
                ), _task_outcome(result.status),
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

    def recover_session(self, trusted: TrustedContext) -> ModuleResult:
        """Transfer an owned task to the authenticated session, then resume its public capability."""
        with _task_lock(self.application.path, trusted.task_id):
            self._scope(trusted)
            task = self.application.get_task(
                trusted.user_id, trusted.demo_round_id, trusted.task_id,
            )
            if task is None:
                raise PermissionError("ACCESS_DENIED")
            self._authorize(trusted, task.snapshot.get("capability_name",
                                                       "transfer.start_transfer"))

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

            operation_ids = self._operation_ids_from(result)
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

    def get(self, trusted: TrustedContext) -> ModuleResult:
        self._scope(trusted)
        task = self.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
        if task is None:
            raise ValueError("TASK_NOT_FOUND")
        self._check_task(task, trusted)
        return self._result(task)

    # --- v05-cross-platform/03: controlled child-task dispatch for cross parents ---

    # Public start-input contracts a parent may hand to a child capability; every
    # other input shape is refused before any task is created.
    CHILD_INPUT_CONTRACTS = (StartTransferInput, CrossStartInput)

    def dispatch_child(self, parent: TrustedContext, capability_name: str,
                       request_id: UUID, child_input, *, step_id: str,
                       plan_revision: int) -> ModuleResult:
        """Start one registered child task for a parent plan step.

        The parent decides the step deterministically; the model never picks the
        capability, fills the trusted context or resumes the child. One child step
        that needs a user response or has side effects may be in flight per parent;
        read-only children may interleave. Spends naming a payer account are
        checked against the active arrangement holder (D1) before the task exists.
        """
        registration = self.registry.get(capability_name)
        definition = registration.definition
        self._authorize(parent, capability_name)
        if not isinstance(child_input, self.CHILD_INPUT_CONTRACTS):
            raise ValueError("INVALID_CAPABILITY_INPUT")

        if definition.operation_level != OperationLevel.READ or definition.side_effect:
            for _relation, task, child_definition in self._child_task_states(parent):
                blocking = (
                    task.status not in {
                        TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED,
                    }
                    and (
                        child_definition.operation_level != OperationLevel.READ
                        or child_definition.side_effect
                    )
                )
                if blocking:
                    raise ValueError("CHILD_STEP_ALREADY_ACTIVE")

        payer_account_id = getattr(child_input, "payer_account_id", None)
        if payer_account_id:
            active = self.application.get_active_arrangement(
                parent.user_id, parent.demo_round_id, payer_account_id,
            )
            if active is not None and active.record.source_task_id not in (
                self.application.task_lineage(parent.user_id, parent.demo_round_id, parent.task_id)
            ):
                raise ArrangementConflictError(
                    active.record.source_task_id, active.record.arrangement_id, payer_account_id,
                )

        child_task_id, child_run_id, trace_id = str(uuid4()), str(uuid4()), str(uuid4())
        child_trusted = TrustedContext(
            user_id=parent.user_id, session_id=parent.session_id, task_id=child_task_id,
            run_id=child_run_id, parent_task_id=parent.task_id, demo_round_id=parent.demo_round_id,
        )
        snapshot = {
            "request_id": str(request_id), "intent_text": f"{capability_name}:{step_id}",
            "config_version": self.planner.config_version,
            "capability_name": capability_name, "step_id": step_id,
            "plan_revision": plan_revision, "trace_id": trace_id,
        }
        with _task_lock(self.application.path, child_task_id):
            task = self.application.create_task(
                child_task_id, parent.user_id, parent.session_id, parent.demo_round_id,
                child_run_id, TaskStatus.RUNNING, snapshot,
            )
            self.application.link_child_task(
                parent.user_id, parent.demo_round_id, parent.task_id,
                child_task_id, step_id, plan_revision,
            )
            context = self._scope(child_trusted)
            trace = RunTrace(self.audit, child_trusted, task.checkpoint_thread_id, trace_id)
            saver = self.memory.checkpointer(context, child_task_id)
            entry = registration.factory(child_trusted, saver, trace)
            result = entry.start(child_trusted, child_input, thread_id=task.checkpoint_thread_id)
            self._check_result_scope(result, child_trusted)
            self.application.update_task(
                parent.user_id, parent.demo_round_id, child_task_id,
                task.revision, child_run_id, result.status,
                self._checkpoint_id(context, task),
                {**snapshot, "result": result.model_dump(mode="json")},
            )
        trace.record(
            "task.transition",
            TaskTransitionPayload(
                previous_status=TaskStatus.RUNNING, status=result.status,
                plan_revision=plan_revision, step_id=step_id,
                reason_code="CHILD_STEP_DISPATCHED", checkpoint_ref=None,
            ), _task_outcome(result.status),
        )
        return result

    def resume_child(self, parent: TrustedContext, child_task_id: str, response: dict,
                     *, plan_revision: int) -> ModuleResult:
        """Continue one owned child along its original association and plan version."""
        with _task_lock(self.application.path, child_task_id):
            if self.application.parent_of_task(
                parent.user_id, parent.demo_round_id, child_task_id,
            ) != parent.task_id:
                raise PermissionError("ACCESS_DENIED")
            task = self.application.get_task(parent.user_id, parent.demo_round_id, child_task_id)
            if task is None or task.session_id != parent.session_id:
                raise PermissionError("ACCESS_DENIED")
            if task.snapshot.get("plan_revision") != plan_revision:
                raise ValueError("PLAN_SUPERSEDED")
            child_trusted = TrustedContext(
                user_id=parent.user_id, session_id=parent.session_id, task_id=child_task_id,
                run_id=task.run_id, parent_task_id=parent.task_id,
                demo_round_id=parent.demo_round_id,
            )
        return self.resume(child_trusted, response)

    def child_task_summaries(self, parent: TrustedContext) -> list[dict]:
        """Durable child states for the parent's own progress mapping (§4.3 is business)."""
        return [
            {
                "child_task_id": relation.child_task_id,
                "step_id": relation.step_id,
                "plan_revision": relation.plan_revision,
                "capability_name": task.snapshot.get("capability_name"),
                "status": task.status.value,
            }
            for relation, task, _definition in self._child_task_states(parent)
        ]

    def _child_task_states(self, parent: TrustedContext):
        for relation in self.application.list_child_tasks(
            parent.user_id, parent.demo_round_id, parent.task_id,
        ):
            task = self.application.get_task(
                parent.user_id, parent.demo_round_id, relation.child_task_id,
            )
            if task is None:
                continue
            capability_name = task.snapshot.get("capability_name")
            try:
                definition = self.registry.get(capability_name).definition
            except ValueError:
                # A child whose capability vanished blocks fail-closed, never silently.
                definition = CapabilityDefinition(
                    name=str(capability_name), input_schema_ref="unknown", output_schema_ref="unknown",
                    required_permissions=[], operation_level=OperationLevel.SENSITIVE,
                    side_effect=True, confirmation_policy="per_action", timeout_ms=1,
                    retry_policy="none", handler_ref="unknown",
                )
            yield relation, task, definition

    def resume(self, trusted: TrustedContext, response: dict) -> ModuleResult:
        with _task_lock(self.application.path, trusted.task_id):
            context = self._scope(trusted)
            task = self.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
            if task is None:
                raise ValueError("TASK_NOT_FOUND")
            self._check_task(task, trusted)
            if "result" not in task.snapshot:
                if task.snapshot["config_version"] != self.planner.config_version:
                    raise ValueError("MODEL_CONFIG_CHANGED")
                self._authorize(trusted, task.snapshot.get("capability_name",
                                                           "transfer.start_transfer"))
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
                        operation_ids=self._operation_ids_from(result),
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
            result = None
            completed_scope = None
            try:
                result = entry.resume(trusted, response, thread_id=task.checkpoint_thread_id)
                self._check_result_scope(result, trusted)
                checkpoint_id = self._checkpoint_id(context, task)
                if task.snapshot["capability_name"] == "bills.detect_anomalies" and result.status == TaskStatus.SUCCEEDED:
                    completed = entry.completed_scope(trusted, thread_id=task.checkpoint_thread_id)
                    completed_scope = completed.model_dump(mode="json") if completed else None
            except (RuntimeError, OSError, DatabaseError):
                # The trusted task was checked before entering the capability.
                # Bookkeeping remains possible if its session expires inside it;
                # this does not authorize another bank read or execution.
                if result is None:
                    # Keep the last owned payload readable, whatever module owns it;
                    # forcing the transfer view here would re-raise inside the handler.
                    result = ModuleResult(
                        task_id=trusted.task_id, run_id=trusted.run_id,
                        status=TaskStatus.NEEDS_ATTENTION,
                        data=trace.transfer_data if trace.transfer_data is not None else previous.data,
                        message="流程中断，请核实原任务后继续。", interaction=None,
                        error=ModuleError(code="DEPENDENCY_UNAVAILABLE", source="platform",
                                          field=None, reason="流程推进未完成。", upstream_code=None),
                        allowed_actions=["resume", "cancel"], recovery_required=True,
                        recovery_reason="PUBLIC_CAPABILITY_INTERRUPTED",
                    )
                try:
                    fault_checkpoint_id = self._checkpoint_id(context, task)
                except PermissionError:
                    # Retain the last owned reference when authority expired;
                    # do not bypass the checkpointer's scope check.
                    fault_checkpoint_id = task.checkpoint_id
                self.application.update_task(
                    trusted.user_id, trusted.demo_round_id, trusted.task_id,
                    task.revision, trusted.run_id, result.status, fault_checkpoint_id,
                    {**task.snapshot, "result": result.model_dump(mode="json"),
                     "capability_fault": {"reason_code": "PUBLIC_CAPABILITY_INTERRUPTED",
                                          "audit_evidence": "not_confirmed"}},
                )
                raise
            except Exception:
                trace.record(
                    "recovery.checked",
                    RecoveryCheckedPayload(
                        previous_run_id=task.run_id, current_run_id=trusted.run_id,
                        checkpoint_ref=task.checkpoint_id,
                        operation_ids=self._operation_ids_from(previous),
                        result="stop", reason_code="PUBLIC_CAPABILITY_RESUME_FAILED",
                    ), "failed",
                )
                raise
            # Store the known business result before completion logging. A log
            # failure must not leave an obsolete waiting/approval snapshot.
            self.application.update_task(
                trusted.user_id, trusted.demo_round_id, trusted.task_id,
                task.revision, trusted.run_id, result.status, checkpoint_id,
                {**task.snapshot, "result": result.model_dump(mode="json"),
                 "completed_bill_scope": completed_scope},
            )
            trace.record(
                "recovery.checked",
                RecoveryCheckedPayload(
                    previous_run_id=task.run_id, current_run_id=trusted.run_id,
                    checkpoint_ref=checkpoint_id,
                    operation_ids=self._operation_ids_from(previous),
                    result=self._recovery_result(result.status),
                    reason_code="PUBLIC_CAPABILITY_RESUMED",
                ), "succeeded",
            )
            trace.record(
                "task.transition",
                TaskTransitionPayload(
                    previous_status=previous.status, status=result.status,
                    plan_revision=None, step_id=task.snapshot["capability_name"],
                    reason_code="TASK_RESUMED",
                    checkpoint_ref=checkpoint_id,
                ), _task_outcome(result.status),
            )
            return result
