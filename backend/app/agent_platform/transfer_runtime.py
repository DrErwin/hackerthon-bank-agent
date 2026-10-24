"""Wire the public transfer graph to real security, bank and audit services."""

from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Callable
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from langgraph.errors import GraphInterrupt

from app.audit.journal import AuditJournal
from app.contracts.audit import (
    AuthorizationConfirmation, AuthorizationSnapshot, AuthorizationVerification,
    BankObservedPayload, ConfirmationChangedPayload, SecurityDecidedPayload,
    TaskTransitionPayload, ToolFinishedPayload, ToolStartedPayload,
    VerificationChangedPayload,
)
from app.contracts.bank import BankError, OperationResult, PayeeDisplay, PayeeInput, QueryFailure
from app.contracts.common import DisplayField, OperationLevel, Phase, RiskLevel, SecurityDecisionCode, TaskStatus
from app.contracts.platform import CapabilityDefinition, TrustedContext
from app.contracts.security import (
    ActionDescriptor, ConfirmationAnswer, ConfirmationRecord,
    ExecutionSecurityContext, SecurityDecision, VerificationRecord,
    VerificationSummary,
)
from app.contracts.tasks import ModuleError, TransferTaskView
from app.memory.adapter import MemoryAdapter, MemoryContext
from app.modules.transfer.manifest import MANIFEST, PRIVATE_TOOLS
from app.modules.transfer.tools import GatewayTransferTools, TransferAction, TransferSnapshots
from app.modules.transfer.workflow import TransferWorkflow
from app.security import ConfirmationService, SecurityGate, ToolRegistry
from app.security.gate import (
    ExecutionOutcome, RiskAssessment, RiskAssessor, ScopeAuthorizer, SecurityError,
)
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore
from app.storage.database import connect, parameter_digest, transaction

from .harness import AgentHarness, RunTrace
from .model import Planner
from .payee_references import ControlledPayeeReferences
from .registry import CapabilityRegistry


_PAYEE = TypeAdapter(PayeeInput)


class TracedTransferWorkflow(TransferWorkflow):
    """Record each deterministic graph step without putting private state in audit."""

    def __init__(self, ports, saver, trace: RunTrace, node_span: ContextVar):
        self.trace = trace
        self.node_span = node_span
        super().__init__(ports, saver)

    def _step(self, name: str, state, run):
        # Node input is the last committed graph state, not an uncommitted
        # return value. Keep only the existing public, masked task data in
        # this platform-owned observer, before any audit write can fail.
        self.trace.transfer_data = TransferTaskView(
            operation_id=state.get("operation_id"),
            payer_account_id=state.get("payer_account_id"),
            payee={key: value for key, value in state["payee_display"].items()
                   if key in PayeeDisplay.model_fields} if state.get("payee_display") else None,
            amount_fen=state.get("amount_fen"),
            operation=state.get("operation"),
        )
        previous = TaskStatus(state.get("status", TaskStatus.RUNNING.value))
        started = self.trace.record("task.transition", TaskTransitionPayload(
            previous_status=previous, status=previous, plan_revision=None,
            step_id=name, reason_code="NODE_STARTED", checkpoint_ref=None,
        ), "started", module="transfer")
        token = self.node_span.set(started.span_id)
        try:
            result = run(state)
        except GraphInterrupt:
            self.trace.record("task.transition", TaskTransitionPayload(
                previous_status=previous, status=TaskStatus.WAITING_APPROVAL
                if state.get("wait_kind") == "security" else TaskStatus.WAITING_INPUT,
                plan_revision=None, step_id=name, reason_code="NODE_WAITING",
                checkpoint_ref=None,
            ), "waiting", module="transfer", parent_span_id=started.span_id)
            raise
        except Exception:
            self.trace.record("task.transition", TaskTransitionPayload(
                previous_status=previous, status=previous, plan_revision=None,
                step_id=name, reason_code="NODE_FAILED", checkpoint_ref=None,
            ), "failed", module="transfer", parent_span_id=started.span_id)
            raise
        else:
            status = TaskStatus(result.get("status", previous.value))
            self.trace.record("task.transition", TaskTransitionPayload(
                previous_status=previous, status=status, plan_revision=None,
                step_id=name, reason_code="NODE_FINISHED", checkpoint_ref=None,
            ), "succeeded", module="transfer", parent_span_id=started.span_id)
            return result
        finally:
            self.node_span.reset(token)

    def _collect(self, state): return self._step("collect", state, super()._collect)
    def _find_payee(self, state): return self._step("find_payee", state, super()._find_payee)
    def _verify_payee(self, state): return self._step("verify_payee", state, super()._verify_payee)
    def _precheck(self, state): return self._step("precheck", state, super()._precheck)
    def _security(self, state): return self._step("security", state, super()._security)
    def _submit(self, state): return self._step("submit", state, super()._submit)
    def _reconcile(self, state): return self._step("reconcile", state, super()._reconcile)
    def _manual_reconcile(self, state): return self._step("manual_reconcile", state, super()._manual_reconcile)
    def _await_query(self, state): return self._step("await_query", state, super()._await_query)
    def _wait(self, state): return self._step("wait", state, super()._wait)


class TransferFacts:
    """Platform-owned links to current, bank- and security-issued records."""

    def __init__(self, application: ApplicationStore):
        self.application = application
        self.path = application.path
        with transaction(self.path) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS agent_transfer_confirmations (
                task_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, demo_round_id TEXT NOT NULL,
                operation_id TEXT NOT NULL, action_revision INTEGER NOT NULL,
                confirmation_id TEXT NOT NULL, confirmation_version INTEGER NOT NULL
            )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS agent_transfer_verifications (
                task_id TEXT NOT NULL, user_id TEXT NOT NULL, demo_round_id TEXT NOT NULL,
                verification_id TEXT NOT NULL, scope TEXT NOT NULL,
                operation_id TEXT, action_revision INTEGER,
                PRIMARY KEY(task_id, verification_id)
            )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS agent_transfer_results (
                event_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL,
                task_id TEXT NOT NULL, user_id TEXT NOT NULL,
                demo_round_id TEXT NOT NULL, result_json TEXT NOT NULL
            )""")

    def set_confirmation(self, record: ConfirmationRecord) -> None:
        with transaction(self.path) as connection:
            connection.execute("""INSERT INTO agent_transfer_confirmations VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                user_id=excluded.user_id, demo_round_id=excluded.demo_round_id,
                operation_id=excluded.operation_id, action_revision=excluded.action_revision,
                confirmation_id=excluded.confirmation_id,
                confirmation_version=excluded.confirmation_version""", (
                    record.task_id, record.user_id, record.demo_round_id,
                    str(record.operation_id), record.action_revision,
                    record.confirmation_id, record.confirmation_version,
                ))

    def confirmation(self, trusted: TrustedContext, operation_id: UUID | None,
                     action_revision: int | None) -> tuple[str, int] | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                "SELECT * FROM agent_transfer_confirmations WHERE task_id = ?",
                (trusted.task_id,),
            ).fetchone()
            if row is None:
                return None
            if (row["user_id"], row["demo_round_id"]) != (
                trusted.user_id, trusted.demo_round_id,
            ):
                raise PermissionError("ACCESS_DENIED")
            if (row["operation_id"], row["action_revision"]) != (
                str(operation_id) if operation_id else None, action_revision,
            ):
                return None
            if not self.application.has_ref(
                trusted.user_id, trusted.demo_round_id, trusted.task_id,
                "confirmation", row["confirmation_id"],
            ):
                return None
            return row["confirmation_id"], row["confirmation_version"]
        finally:
            connection.close()

    def add_verification(self, trusted: TrustedContext, record: VerificationRecord) -> None:
        with transaction(self.path) as connection:
            connection.execute("""INSERT OR IGNORE INTO agent_transfer_verifications
                VALUES (?, ?, ?, ?, ?, ?, ?)""", (
                    trusted.task_id, trusted.user_id, trusted.demo_round_id,
                    record.verification_id, record.scope,
                    str(record.operation_id) if record.operation_id else None,
                    record.action_revision,
                ))

    def session_verification_sources(self, trusted: TrustedContext) -> list[tuple[str, str]]:
        connection = connect(self.path)
        try:
            rows = connection.execute("""SELECT DISTINCT task_id, verification_id
                FROM agent_transfer_verifications WHERE user_id = ? AND demo_round_id = ?
                AND scope = 'session' AND task_id != ? AND verification_id NOT IN (
                    SELECT verification_id FROM agent_transfer_verifications WHERE task_id = ?)
                """, (trusted.user_id, trusted.demo_round_id, trusted.task_id, trusted.task_id)).fetchall()
            return [(row["task_id"], row["verification_id"]) for row in rows]
        finally:
            connection.close()

    def verification_ids(self, trusted: TrustedContext, operation_id: UUID | None,
                         action_revision: int | None) -> list[str]:
        connection = connect(self.path)
        try:
            rows = connection.execute("""SELECT verification_id FROM agent_transfer_verifications
                WHERE task_id = ? AND user_id = ? AND demo_round_id = ? AND
                (scope = 'session' OR (operation_id = ? AND action_revision = ?))""", (
                    trusted.task_id, trusted.user_id, trusted.demo_round_id,
                    str(operation_id) if operation_id else None, action_revision,
                )).fetchall()
            return [row["verification_id"] for row in rows if self.application.has_ref(
                trusted.user_id, trusted.demo_round_id, trusted.task_id,
                "verification", row["verification_id"],
            )]
        finally:
            connection.close()


class AuditedTransferPorts:
    def __init__(self, tools: GatewayTransferTools, trace: RunTrace,
                 activate: Callable[[TrustedContext, TransferAction, TransferWorkflow], object],
                 record_result: Callable,
                 decision_spans: dict[str, str],
                 payee_references: ControlledPayeeReferences,
                 workflow: TransferWorkflow | None = None,
                 arrangement_guard: Callable[[TrustedContext, str, TransferAction], object] | None = None):
        self.tools = tools
        self.trace = trace
        self.activate = activate
        self.record_result = record_result
        self.decision_spans = decision_spans
        self.workflow = workflow
        self.payee_references = payee_references
        self.arrangement_guard = arrangement_guard

    def protect_payee(self, trusted, payee, payee_revision):
        """Public port used before business input can enter its checkpoint."""
        return self.payee_references.register(trusted, payee, payee_revision)

    def clear_payee(self, trusted):
        self.payee_references.clear(trusted)

    def read(self, trusted: TrustedContext, action_name: str, parameters: dict | None):
        registered = self.tools.gate.registry.get(action_name)
        if registered is None or registered.declaration.side_effect:
            raise ValueError("read tool is not registered")
        parameter_ref = self.tools.snapshots.save(trusted, action_name, parameters)
        context = self.tools.security_context(trusted, None, None)
        action = ActionDescriptor(
            action_name=action_name, parameters_ref=parameter_ref,
            resource_refs=[], phase=Phase.ADMISSION,
        )
        decision = self.tools.gate.check_action(context, action)
        if decision.decision != SecurityDecisionCode.ALLOW:
            return self.tools.executor.execute(context, action)
        started = monotonic()
        call_id, ref = str(uuid4()), str(uuid4())
        started_event = self.trace.record("tool.started", ToolStartedPayload(
            tool_call_id=call_id, tool_name=action_name, tool_version=MANIFEST.version,
            arguments_ref=ref, decision_id=decision.decision_id,
            operation_id=None,
        ), "started", evidence={"parameters_sha256": parameter_digest(parameters)},
            evidence_id=ref, module="transfer",
            parent_span_id=self.decision_spans.get(decision.decision_id))
        try:
            outcome = self.tools.executor.execute(context, action)
        except Exception as exc:
            self.trace.record("tool.finished", ToolFinishedPayload(
                tool_call_id=call_id, operation_id=None, result_ref=None,
                duration_ms=int((monotonic() - started) * 1000),
                error=ModuleError(code="TOOL_FAILED", source="platform", field=None,
                                  reason=type(exc).__name__, upstream_code=None),
            ), "failed", module="transfer", parent_span_id=started_event.span_id)
            raise
        self.trace.record("tool.finished", ToolFinishedPayload(
            tool_call_id=call_id, operation_id=None, result_ref=None,
            duration_ms=int((monotonic() - started) * 1000), error=None,
        ), "succeeded" if outcome.decision.decision == SecurityDecisionCode.ALLOW else "denied",
            module="transfer", parent_span_id=started_event.span_id)
        return outcome

    def prepare_transfer(self, trusted, operation_id, action_revision,
                         payer_account_id, payee, amount_fen):
        return self.tools.prepare_transfer(
            trusted, operation_id, action_revision, payer_account_id, payee, amount_fen,
        )

    def check(self, trusted, action):
        return self.tools.check(trusted, action)

    def _observed(self, action: TransferAction, outcome,
                  parent_span_id: str | None = None) -> None:
        result = outcome.result
        if isinstance(result, OperationResult):
            ref = str(uuid4())
            self.trace.record("bank.observed", BankObservedPayload(
                operation_id=action.operation_id, lookup="found",
                operation_status=result.operation_status,
                transaction_id=result.receipt.transaction_id if result.receipt else None,
                receipt_ref=ref, error=None,
            ), "succeeded", evidence=result.model_dump(mode="json"),
                evidence_id=ref, module="bank_gateway",
                parent_span_id=parent_span_id,
                write=lambda connection, event: self.record_result(
                    connection, event, result,
                ))
        elif outcome.reused or outcome.state in {"unknown", "processing"}:
            self.trace.record("bank.observed", BankObservedPayload(
                operation_id=action.operation_id, lookup="error",
                operation_status=None, transaction_id=None, receipt_ref=None,
                error=None,
            ), "unknown", module="bank_gateway",
                parent_span_id=parent_span_id)

    def execute(self, trusted: TrustedContext, action: TransferAction):
        context = self.tools.security_context(trusted, action.operation_id, action.action_revision)
        descriptor = action.descriptor(Phase.EXECUTION)
        if self.tools.gate.confirmations.state.get_execution(context, descriptor) is not None:
            outcome = self.tools.execute(trusted, action)
            self._observed(action, outcome)
            return outcome
        decision = self.tools.gate.check_action(context, descriptor)
        if decision.decision != SecurityDecisionCode.ALLOW:
            return self.tools.execute(trusted, action)
        if self.arrangement_guard is not None:
            # D1 pauses an ordinary spend before submission while another task's
            # arrangement holds the payer account; the pause is an application-side
            # decision, never a bank rejection.
            payload = self.tools.snapshots.resolve(context, descriptor)
            payer_account_id = payload.get("payer_account_id")
            if payer_account_id:
                pause = self.arrangement_guard(trusted, payer_account_id, action)
                if pause is not None:
                    self.trace.record(
                        "security.decided", SecurityDecidedPayload(decision=pause),
                        "denied", module="security",
                        parent_span_id=self.decision_spans.get(decision.decision_id),
                    )
                    return ExecutionOutcome(
                        decision=pause, executed=False, reused=False,
                        state="not_started", result=None, result_ref=None,
                    )
        call_id = str(uuid4())
        started_event = self.trace.record("tool.started", ToolStartedPayload(
            tool_call_id=call_id, tool_name="bank.submit_transfer",
            tool_version=MANIFEST.version, arguments_ref=action.parameters_ref,
            decision_id=decision.decision_id, operation_id=action.operation_id,
        ), "started", module="transfer",
            parent_span_id=self.decision_spans.get(decision.decision_id))
        started = monotonic()
        token = self.activate(trusted, action, self.workflow)
        try:
            outcome = self.tools.execute(trusted, action)
        except Exception as exc:
            self.trace.record("tool.finished", ToolFinishedPayload(
                tool_call_id=call_id, operation_id=action.operation_id, result_ref=None,
                duration_ms=int((monotonic() - started) * 1000),
                error=ModuleError(code="TOOL_FAILED", source="platform", field=None,
                                  reason=type(exc).__name__, upstream_code=None),
            ), "failed", module="transfer", parent_span_id=started_event.span_id)
            raise
        finally:
            token()
        self._observed(action, outcome, started_event.span_id)
        denied = (outcome.decision is not None
                  and outcome.decision.decision != SecurityDecisionCode.ALLOW)
        self.trace.record("tool.finished", ToolFinishedPayload(
            tool_call_id=call_id, operation_id=action.operation_id,
            result_ref=None, duration_ms=int((monotonic() - started) * 1000),
            error=ModuleError(code=outcome.decision.reason_codes[0], source="security",
                              field=None, reason="安全检查未放行", upstream_code=None)
            if denied else None,
        ), "denied" if denied else
            "succeeded" if isinstance(outcome.result, OperationResult) else "unknown",
            module="transfer", parent_span_id=started_event.span_id)
        return outcome

    def observe(self, trusted, action):
        outcome = self.tools.observe(trusted, action)
        self._observed(action, outcome)
        return outcome


class TransferRuntime:
    """Real v0.3 composition; policy decisions remain injected by their owner."""

    def __init__(self, application: ApplicationStore, memory: MemoryAdapter,
                 audit: AuditJournal, bank: MockBankService, planner: Planner,
                 authorize_capability: Callable[[TrustedContext, CapabilityDefinition], bool],
                 authorize_tool: ScopeAuthorizer, assess_risk: RiskAssessor,
                 authorize_face: Callable[..., bool] | None = None):
        self.application, self.memory, self.audit = application, memory, audit
        self.authorize_tool, self.assess_risk = authorize_tool, assess_risk
        self.facts = TransferFacts(application)
        self.snapshots = TransferSnapshots(application.path)
        self.confirmations = ConfirmationService(application.path)
        self._active: ContextVar[tuple | None] = ContextVar("active_transfer", default=None)
        # A second module attaches its scenario wiring here (see subscription_runtime):
        # both stay fail-closed, so an unwired runtime can neither answer as another
        # module nor authorize that module's bank write.
        self.subscription = None
        self.authorize_cancel: Callable[..., bool] | None = None
        # v05-cross-platform/09: the birthday wiring (BirthdayRuntime) attaches
        # its live-claim authorizer here; unwired stays deny-all at the gateway.
        self.birthday = None
        self.gateway = BankGateway(
            bank, authorize_transfer=self._authorize_bank, authorize_face=authorize_face,
            authorize_cancel=self._authorize_bank_cancel,
            authorize_birthday=self._authorize_birthday,
        )
        self.payee_references = ControlledPayeeReferences(
            self.snapshots, self._verify_controlled_payee, self._task,
        )
        registry = CapabilityRegistry()
        registry.register_transfer(MANIFEST, self._transfer_factory)
        self.harness = AgentHarness(
            application, memory, audit, registry, planner, authorize_capability,
        )

    def close(self) -> None:
        self.gateway.close()

    def read_transfer_choices(self, trusted, kind):
        """Read owned banking facts without resuming or modifying the transfer."""
        if kind not in {"accounts", "payees"}:
            raise ValueError("INVALID_ARGUMENT")
        saver = self.memory.checkpointer(MemoryContext(
            trusted.user_id, trusted.session_id, trusted.demo_round_id,
        ), trusted.task_id)
        flow = self._transfer_factory(trusted, saver, self._trace(trusted))
        outcome = flow.ports.read(trusted, "bank.list_" + kind,
                                  None if kind == "payees" else {})
        if not outcome.executed or outcome.result is None or isinstance(outcome.result, QueryFailure):
            raise ValueError("DEPENDENCY_UNAVAILABLE")
        return outcome.result.data

    def _verify_controlled_payee(self, trusted, payee):
        # Reuse registered read tools, permissions, termination checks and audit.
        # Building the workflow does not start it or put the input in its saver.
        saver = self.memory.checkpointer(MemoryContext(
            trusted.user_id, trusted.session_id, trusted.demo_round_id,
        ), trusted.task_id)
        flow = self._transfer_factory(trusted, saver, self._trace(trusted))
        outcome = flow.ports.read(trusted, "bank.verify_payee", {
            "payee": payee.model_dump(mode="json"),
        })
        if outcome.decision.decision != SecurityDecisionCode.ALLOW:
            return QueryFailure(kind="error", error=BankError(
                code=outcome.decision.reason_codes[0], details={},
            ))
        return outcome.result

    def _task(self, trusted: TrustedContext):
        self.memory.agent_backend(MemoryContext(
            trusted.user_id, trusted.session_id, trusted.demo_round_id,
        ))
        task = self.application.get_task(
            trusted.user_id, trusted.demo_round_id, trusted.task_id,
        )
        if task is None or task.session_id != trusted.session_id:
            raise PermissionError("ACCESS_DENIED")
        return task

    def _trace(self, trusted: TrustedContext) -> RunTrace:
        task = self._task(trusted)
        return RunTrace(self.audit, trusted, task.checkpoint_thread_id,
                        task.snapshot["trace_id"])

    @staticmethod
    def _trusted(context: ExecutionSecurityContext) -> TrustedContext:
        return TrustedContext(
            user_id=context.user_id, session_id=context.session_id,
            demo_round_id=context.demo_round_id, task_id=context.task_id,
            run_id=context.run_id, parent_task_id=context.source_task_id,
        )

    def _reuse_session_verifications(self, trusted: TrustedContext) -> None:
        self._task(trusted)
        rebound = set()
        for source_task, verification_id in self.facts.session_verification_sources(trusted):
            if verification_id in rebound:
                continue
            try:
                record = self.gateway.get_verification_record(trusted, verification_id)
            except ValueError:
                # Another session's bank record grants no authority here.
                continue
            if record.scope != "session" or (record.user_id, record.session_id, record.demo_round_id) != (
                trusted.user_id, trusted.session_id, trusted.demo_round_id
            ):
                continue
            source = trusted.model_copy(update={"task_id": source_task})
            # The task may have moved sessions since this bank session fact was issued.
            if self.application.get_task(trusted.user_id, trusted.demo_round_id, source_task) is None:
                continue
            try:
                challenge = self.gateway.get_verification(source, record.source_challenge_id)
            except ValueError:
                # A task that reused this record is not necessarily the owner of
                # its original challenge. Keep looking for the issuing task;
                # never relax the bank's challenge ownership check.
                continue
            if challenge.challenge_status != "passed" or challenge.purpose != "basic_identity":
                continue
            self.application.bind_ref(trusted.user_id, trusted.demo_round_id, trusted.task_id,
                                      "verification", verification_id)
            self.facts.add_verification(trusted, record)
            rebound.add(verification_id)
            self._trace(trusted).record("verification.changed", VerificationChangedPayload(
                challenge_id=challenge.challenge_id, method="code", result="passed",
                purpose=challenge.purpose, operation_id=None, verification_id=verification_id,
                consecutive_code_failures=challenge.consecutive_code_failures,
                expires_at=challenge.code_expires_at, reason_code="SESSION_VERIFICATION_REUSED",
            ), "succeeded", module="bank_gateway")

    def _context(self, trusted: TrustedContext, operation_id: UUID | None,
                 action_revision: int | None) -> ExecutionSecurityContext:
        if operation_id is not None:
            self._reuse_session_verifications(trusted)
        current = self.facts.confirmation(trusted, operation_id, action_revision)
        return ExecutionSecurityContext(
            user_id=trusted.user_id, session_id=trusted.session_id,
            demo_round_id=trusted.demo_round_id, task_id=trusted.task_id,
            run_id=trusted.run_id, source_task_id=trusted.parent_task_id,
            operation_id=operation_id, action_revision=action_revision,
            confirmation_id=current[0] if current else None,
            confirmation_version=current[1] if current else None,
            verification_ids=self.facts.verification_ids(
                trusted, operation_id, action_revision,
            ), release_authorization_id=None,
        )

    def _bank_authorized(self, trusted, operation_id, payer_account_id, payee, amount_fen):
        if self._arrangement_holder_conflict(trusted, payer_account_id) is not None:
            # D1 backstop at the one shared bank-write authorization seam.
            return False
        active = self._active.get()
        if active is None:
            return False
        expected, action, workflow, gate = active
        if trusted != expected or operation_id != action.operation_id:
            return False
        context = self._context(trusted, operation_id, action.action_revision)
        descriptor = action.descriptor(Phase.EXECUTION)
        declaration = gate.registry.get("bank.submit_transfer").declaration
        if not self._scope(context, descriptor, declaration, workflow):
            return False
        claim = self.confirmations.state.get_execution(context, descriptor)
        if claim is None or claim.state != "processing" or (
            claim.decision.decision != SecurityDecisionCode.ALLOW
        ):
            return False
        payload = self.snapshots.resolve(context, descriptor)
        return (
            payload["operation_id"] == str(operation_id)
            and payload["payer_account_id"] == payer_account_id
            and _PAYEE.validate_python(payload["payee"]) == payee
            and payload["amount_fen"] == amount_fen
        )

    def _authorize_birthday(self, *args):
        # Unwired stays deny-all at the gateway; BirthdayRuntime attaches the
        # live-claim authorizer (v05-cross-platform/09).
        if self.birthday is None:
            return False
        return self.birthday.authorize_birthday(*args)

    def _authorize_bank(self, *args) -> bool:
        try:
            return self._bank_authorized(*args) is True
        except Exception:
            return False

    def _authorize_bank_cancel(self, *args) -> bool:
        """Second modules register their B30 authority hook; None stays fail-closed."""
        authorize = self.authorize_cancel
        if authorize is None:
            return False
        try:
            return authorize(*args) is True
        except Exception:
            return False

    def _scope(self, context, action, declaration, workflow) -> bool:
        trusted = self._trusted(context)
        self._task(trusted)
        if self.authorize_tool(context, action, declaration) is not True:
            return False
        return not declaration.side_effect or workflow.is_current_action(context, action)

    def _task_terminated(self, context) -> bool:
        task = self._task(self._trusted(context))
        return task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}

    @staticmethod
    def _record_result(connection, event, result: OperationResult) -> None:
        connection.execute(
            "INSERT INTO agent_transfer_results VALUES (?, ?, ?, ?, ?, ?)",
            (event.event_id, str(result.operation_id), event.task_id,
             event.target_user_id, event.demo_round_id, result.model_dump_json()),
        )

    def _display(self, context, action):
        payload = self.snapshots.resolve(context, action)
        verified = self.gateway.verify_payee(
            self._trusted(context), _PAYEE.validate_python(payload["payee"]),
        )
        if isinstance(verified, QueryFailure) or not verified.data.matched:
            raise SecurityError("PAYEE_MISMATCH")
        payee = verified.data.payee
        trusted = self._trusted(context)
        payer = self.gateway.get_account(trusted, payload["payer_account_id"])
        quote = self.gateway.quote_transfer(
            trusted, payload["payer_account_id"], _PAYEE.validate_python(payload["payee"]), payload["amount_fen"],
        )
        if isinstance(payer, QueryFailure) or isinstance(quote, QueryFailure):
            raise SecurityError("CONFIRMATION_FACTS_UNAVAILABLE")
        declaration = next(item for item in PRIVATE_TOOLS if item.name == action.action_name)
        assessed = self.assess_risk(context, action, declaration)
        risk = RiskLevel(assessed.risk_level if isinstance(assessed, RiskAssessment) else assessed)
        risk_message = {
            RiskLevel.LOW: "低风险；请核对收款人和金额。",
            RiskLevel.MEDIUM: "中风险；需验证码和模拟人脸双因子验证。",
            RiskLevel.HIGH: "高风险；停止办理。",
        }[risk]
        fields = [
            DisplayField(name="payer_account_id", label="转出账户",
                         value_text=f"{payer.data.display_name} {payer.data.account_masked}"),
            DisplayField(name="amount", label="金额",
                         value_text=f"{payload['amount_fen'] / 100:.2f} 元"),
            DisplayField(name="payee", label="收款人",
                         value_text=f"{payee.name_masked} {payee.account_masked}"),
            DisplayField(name="bank", label="收款银行", value_text=payee.bank_name),
            DisplayField(name="fee", label="手续费", value_text=f"{quote.data.fee_fen / 100:.2f} 元"),
            DisplayField(name="arrival", label="到账方式", value_text="即时到账" if quote.data.arrival_mode == "instant" else quote.data.arrival_mode),
            DisplayField(name="risk", label="风险提示", value_text=risk_message),
        ]
        return payload, payee, fields

    def _transfer_factory(self, trusted, saver, trace):
        flow_ref = [None]
        pending_snapshots: dict[str, AuthorizationSnapshot] = {}
        decision_spans: dict[str, str] = {}
        node_span: ContextVar[str | None] = ContextVar("transfer_node_span", default=None)

        def prepare_confirmation(context, action):
            _, _, fields = self._display(context, action)
            record = self.confirmations.create(context, action, fields)
            self.application.bind_ref(context.user_id, context.demo_round_id,
                                      context.task_id, "confirmation", record.confirmation_id)
            self.facts.set_confirmation(record)
            ref = str(uuid4())
            trace.record("confirmation.changed", ConfirmationChangedPayload(
                confirmation_id=record.confirmation_id,
                confirmation_version=record.confirmation_version,
                action_revision=record.action_revision, decision=record.decision,
                display_ref=ref, operation_id=record.operation_id,
            ), "waiting", evidence=[field.model_dump(mode="json") for field in fields],
                evidence_id=ref, module="security")
            return record

        def prepare_verification(context, action, confirmation, risk):
            if risk == RiskLevel.LOW:
                purpose, summary = "basic_identity", None
            else:
                _, payee, fields = self._display(context, action)
                purpose = "action_step_up"
                summary = VerificationSummary(
                    operation_id=context.operation_id,
                    action_revision=context.action_revision,
                    source_confirmation_id=confirmation.confirmation_id,
                    source_confirmation_version=confirmation.confirmation_version,
                    action_name=action.action_name,
                    amount_fen=self.snapshots.resolve(context, action)["amount_fen"],
                    payee=payee, display_fields=fields,
                )
            challenge = self.gateway.create_verification(
                self._trusted(context), purpose,
                context.operation_id if summary else None,
                context.action_revision if summary else None, summary,
            )
            trace.record("verification.changed", VerificationChangedPayload(
                challenge_id=challenge.challenge_id, method="code", result="pending",
                purpose=challenge.purpose, operation_id=challenge.operation_id,
                verification_id=None,
                consecutive_code_failures=challenge.consecutive_code_failures,
                expires_at=challenge.code_expires_at,
                reason_code="VERIFICATION_REQUIRED",
            ), "waiting", module="bank_gateway")
            return challenge

        def resolve_verification(context, verification_id):
            if not self.application.has_ref(context.user_id, context.demo_round_id,
                                            context.task_id, "verification", verification_id):
                raise SecurityError("ACCESS_DENIED")
            try:
                return self.gateway.get_verification_record(
                    self._trusted(context), verification_id,
                )
            except ValueError as exc:
                raise SecurityError("ACCESS_DENIED") from exc

        def validate_summary(context, action, confirmation, summary):
            payload, payee, fields = self._display(context, action)
            return (summary.amount_fen == payload["amount_fen"]
                    and summary.payee == payee
                    and summary.display_fields == fields
                    and confirmation.display_fields == fields)

        def write_snapshot(context, confirmation, verifications, captured_at):
            ref = str(uuid4())
            pending_snapshots[ref] = AuthorizationSnapshot(
                user_id=context.user_id, session_id=context.session_id,
                demo_round_id=context.demo_round_id, task_id=context.task_id,
                operation_id=context.operation_id,
                action_revision=context.action_revision,
                confirmation=AuthorizationConfirmation(
                    confirmation_id=confirmation.confirmation_id,
                    version=confirmation.confirmation_version,
                    decision=confirmation.decision, decided_at=confirmation.decided_at,
                    display_fields=confirmation.display_fields,
                ),
                verifications=[AuthorizationVerification(
                    verification_id=item.verification_id, scope=item.scope,
                    methods=item.methods, verified_at=item.verified_at,
                    operation_id=item.operation_id,
                    action_revision=item.action_revision,
                ) for item in verifications],
                release_authorization_id=None, captured_at=captured_at,
            )
            return ref

        def record_decision(decision: SecurityDecision):
            ref = decision.authorization_snapshot_ref
            snapshot = pending_snapshots.pop(ref, None) if ref else None
            extra = {}
            if snapshot is not None:
                context = self._context(trusted, decision.operation_id,
                                        decision.action_revision)
                action = ActionDescriptor(
                    action_name=decision.action_name,
                    parameters_ref=decision.parameters_ref,
                    resource_refs=[], phase=decision.phase,
                )
                extra[decision.parameters_ref] = self.snapshots.resolve(context, action)
            event = trace.record(
                "security.decided", SecurityDecidedPayload(decision=decision),
                "succeeded" if decision.decision == SecurityDecisionCode.ALLOW else "denied",
                evidence=snapshot, evidence_id=ref, snapshots=extra, module="security",
                parent_span_id=node_span.get(),
            )
            decision_spans[decision.decision_id] = event.span_id

        gate = SecurityGate(
            ToolRegistry(), self.confirmations,
            scope_authorizer=lambda context, action, declaration: self._scope(
                context, action, declaration, flow_ref[0],
            ),
            task_state_resolver=self._task_terminated,
            risk_assessor=self.assess_risk,
            confirmation_preparer=prepare_confirmation,
            verification_preparer=prepare_verification,
            verification_resolver=resolve_verification,
            challenge_resolver=lambda context, challenge_id: self.gateway.get_verification(
                self._trusted(context), challenge_id,
            ),
            decision_sink=record_decision, snapshot_writer=write_snapshot,
            summary_validator=validate_summary,
        )
        def reserve_operation(current, operation_id, action_revision, parameters):
            reservation_parameters = {
                key: value for key, value in parameters.items() if key != "operation_id"
            }
            reservation_parameters["action_revision"] = action_revision
            parameters_digest = parameter_digest(reservation_parameters)
            existing = [
                item for item in self.application.list_task_operations(
                    current.user_id, current.demo_round_id, current.task_id,
                )
                if item.action_name == "bank.submit_transfer"
                and item.parameters_digest == parameters_digest
            ]
            if existing:
                return UUID(existing[-1].operation_id)
            reservation = self.application.reserve_operation(
                current.user_id, current.demo_round_id, current.task_id,
                str(operation_id), "bank.submit_transfer",
                reservation_parameters,
            )
            return UUID(reservation.operation_id)

        tools = GatewayTransferTools(
            self.gateway, gate, self.snapshots, self._context,
            operation_reserver=reserve_operation,
        )

        def activate(trusted, action, workflow):
            token = self._active.set((trusted, action, workflow, gate))
            return lambda: self._active.reset(token)

        ports = AuditedTransferPorts(
            tools, trace, activate, self._record_result, decision_spans, self.payee_references,
            arrangement_guard=self._arrangement_guard,
        )
        flow = TracedTransferWorkflow(ports, saver, trace, node_span)
        ports.workflow = flow
        flow_ref[0] = flow
        return flow

    def _arrangement_holder_conflict(self, trusted: TrustedContext, payer_account_id: str):
        """The active D1 arrangement held outside this task's lineage, if any.

        Reads, cancellations and the limited release never reach this check; only
        the shared submit authorization seam does.
        """
        active = self.application.get_active_arrangement(
            trusted.user_id, trusted.demo_round_id, payer_account_id,
        )
        if active is None:
            return None
        if active.record.source_task_id in self.application.task_lineage(
            trusted.user_id, trusted.demo_round_id, trusted.task_id,
        ):
            return None
        return active

    def _arrangement_guard(self, trusted: TrustedContext, payer_account_id: str,
                           action: TransferAction):
        conflict = self._arrangement_holder_conflict(trusted, payer_account_id)
        if conflict is None:
            return None
        return SecurityDecision(
            decision_id=str(uuid4()), task_id=trusted.task_id, run_id=trusted.run_id,
            action_name="bank.submit_transfer", parameters_ref=action.parameters_ref,
            operation_id=action.operation_id, action_revision=action.action_revision,
            phase=Phase.EXECUTION, operation_level=OperationLevel.SENSITIVE,
            risk_level=None, decision=SecurityDecisionCode.PAUSE,
            reason_codes=["ARRANGEMENT_CONFLICT"], rule_ids=["D1_ACCOUNT_EXCLUSIVITY"],
            policy_version="v05-cross-platform-03", authorization_snapshot_ref=None,
            evidence_refs=[], interaction=None,
            checked_at=datetime.now(timezone.utc),
            message="该付款账户已有正在办理的联动资金安排，请先完成或结束该安排。",
        )

    def _task_module(self, trusted: TrustedContext) -> str:
        """Contract §6.5: the capability prefix names the module that owns the task."""

        capability = str(self._task(trusted).snapshot.get(
            "capability_name", "transfer.start_transfer",
        ))
        return capability.split(".", 1)[0]

    def answer_confirmation(self, trusted: TrustedContext,
                            answer: ConfirmationAnswer) -> ConfirmationRecord:
        # The API resumes whichever module owns the task; only the audited module
        # label and the owning implementation differ, the durable facts are shared.
        if self._task_module(trusted) == "subscription":
            from .subscription_runtime import answer_confirmation
            return answer_confirmation(self, trusted, answer)
        return self.answer_confirmation_for_module(trusted, answer, module="security")

    def answer_confirmation_for_module(self, trusted: TrustedContext, answer: ConfirmationAnswer,
                                       *, module: str) -> ConfirmationRecord:
        self._task(trusted)
        # Resolve by the existing record; only the current action may be answered.
        connection = connect(self.application.path)
        try:
            row = connection.execute(
                "SELECT operation_id, action_revision FROM agent_transfer_confirmations WHERE task_id = ?",
                (trusted.task_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise SecurityError("CONFIRMATION_STALE")
        context = self._context(trusted, UUID(row["operation_id"]), row["action_revision"])
        if (context.confirmation_id, context.confirmation_version) != (
            answer.confirmation_id, answer.confirmation_version,
        ):
            raise SecurityError("CONFIRMATION_STALE")
        record = self.confirmations.answer(context, answer)
        ref = str(uuid4())
        self._trace(trusted).record("confirmation.changed", ConfirmationChangedPayload(
            confirmation_id=record.confirmation_id,
            confirmation_version=record.confirmation_version,
            action_revision=record.action_revision, decision=record.decision,
            display_ref=ref, operation_id=record.operation_id,
        ), "succeeded", evidence=[item.model_dump(mode="json")
                                  for item in record.display_fields],
            evidence_id=ref, module=module)
        return record

    def bind_verification(self, trusted: TrustedContext,
                          verification_id: str) -> VerificationRecord:
        if self._task_module(trusted) == "subscription":
            from .subscription_runtime import bind_verification
            return bind_verification(self, trusted, verification_id)
        return self.bind_verification_for_module(
            trusted, verification_id, module="bank_gateway")

    def bind_verification_for_module(self, trusted: TrustedContext, verification_id: str,
                                     *, module: str) -> VerificationRecord:
        self._task(trusted)
        record = self.gateway.get_verification_record(trusted, verification_id)
        challenge = self.gateway.get_verification(trusted, record.source_challenge_id)
        if challenge.challenge_status != "passed":
            raise SecurityError("VERIFICATION_REQUIRED")
        self.application.bind_ref(trusted.user_id, trusted.demo_round_id,
                                  trusted.task_id, "verification", verification_id)
        self.facts.add_verification(trusted, record)
        self._trace(trusted).record("verification.changed", VerificationChangedPayload(
            challenge_id=challenge.challenge_id,
            method="code" if record.scope == "session" else "mock_face",
            result="passed", purpose=challenge.purpose,
            operation_id=record.operation_id,
            verification_id=record.verification_id,
            consecutive_code_failures=challenge.consecutive_code_failures,
            expires_at=challenge.code_expires_at,
            reason_code="VERIFICATION_PASSED",
        ), "succeeded", module=module)
        return record
