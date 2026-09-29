"""Deterministic admission, confirmation, and execution checks for v0.3."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generic, Literal, TypeVar
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.contracts.common import DisplayField, OperationLevel, RiskLevel, SecurityDecisionCode
from app.contracts.platform import CapabilityDefinition
from app.contracts.security import (
    ActionDescriptor,
    ConfirmationAnswer,
    ConfirmationRecord,
    ExecutionSecurityContext,
    SecurityDecision,
    VerificationChallenge,
    VerificationRecord,
)
from app.contracts.tasks import InteractionOption, InteractionRequest
from app.security.state import ExecutionClaim, SQLiteSecurityState, SecurityStateError


POLICY_VERSION = "v0.3-minimum-security-gate-1"
CONFIRMATION_TTL = timedelta(hours=1)

ToolHandler = Callable[[ExecutionSecurityContext, object], object]
ScopeAuthorizer = Callable[[ExecutionSecurityContext, ActionDescriptor, CapabilityDefinition], bool]
TaskStateResolver = Callable[[ExecutionSecurityContext], bool]
RiskAssessor = Callable[[ExecutionSecurityContext, ActionDescriptor, CapabilityDefinition], RiskLevel]
ConfirmationPreparer = Callable[[ExecutionSecurityContext, ActionDescriptor], ConfirmationRecord]
VerificationPreparer = Callable[
    [ExecutionSecurityContext, ActionDescriptor, ConfirmationRecord, RiskLevel], VerificationChallenge
]
VerificationResolver = Callable[[ExecutionSecurityContext, str], VerificationRecord]
DecisionSink = Callable[[SecurityDecision], None]
ParameterResolver = Callable[[ExecutionSecurityContext, ActionDescriptor], object]
SnapshotWriter = Callable[
    [ExecutionSecurityContext, ConfirmationRecord, tuple[VerificationRecord, ...], datetime], str
]
Clock = Callable[[], datetime]


class SecurityError(ValueError):
    """A stable security reason that callers can map to their transport."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ToolRegistrationError(SecurityError):
    """A declaration is missing a required, enforceable security property."""


@dataclass(frozen=True)
class RegisteredTool:
    declaration: CapabilityDefinition
    handler: ToolHandler


class ToolRegistry:
    """Registers only tools whose security behavior is explicit."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, declaration: CapabilityDefinition | dict, handler: ToolHandler) -> None:
        try:
            declared = CapabilityDefinition.model_validate(declaration)
        except ValidationError as exc:
            raise ToolRegistrationError("INVALID_TOOL_DECLARATION") from exc
        if not declared.required_permissions:
            raise ToolRegistrationError("PERMISSIONS_REQUIRED")
        if declared.side_effect and declared.confirmation_policy != "per_action":
            raise ToolRegistrationError("CONFIRMATION_POLICY_REQUIRED")
        if declared.operation_level == OperationLevel.SENSITIVE and not declared.side_effect:
            raise ToolRegistrationError("SENSITIVE_TOOL_MUST_DECLARE_SIDE_EFFECT")
        if not callable(handler):
            raise ToolRegistrationError("HANDLER_REQUIRED")
        if declared.name in self._tools:
            raise ToolRegistrationError("TOOL_ALREADY_REGISTERED")
        self._tools[declared.name] = RegisteredTool(declared, handler)

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)


class ConfirmationService:
    """Creates and answers durable, versioned one-hour confirmations."""

    def __init__(self, path: Path, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.state = SQLiteSecurityState(path)

    def create(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        display_fields: list[DisplayField],
    ) -> ConfirmationRecord:
        now = self._clock()
        try:
            return self.state.create_confirmation(
                context, action, display_fields, now, now + CONFIRMATION_TTL,
            )
        except SecurityStateError as exc:
            raise SecurityError(exc.code) from exc

    def get(self, context: ExecutionSecurityContext, confirmation_id: str) -> ConfirmationRecord:
        try:
            return self.state.get_confirmation(context, confirmation_id, self._clock())
        except SecurityStateError as exc:
            raise SecurityError(exc.code) from exc

    def answer(
        self,
        context: ExecutionSecurityContext,
        answer: ConfirmationAnswer,
    ) -> ConfirmationRecord:
        if not isinstance(answer, ConfirmationAnswer):
            raise SecurityError("INVALID_CONFIRMATION_ANSWER")
        try:
            return self.state.answer_confirmation(
                context,
                answer.confirmation_id,
                answer.confirmation_version,
                answer.choice,
                self._clock(),
            )
        except SecurityStateError as exc:
            raise SecurityError(exc.code) from exc


class SecurityGate:
    """Checks trusted facts and emits one frozen-contract decision per action."""

    def __init__(
        self,
        registry: ToolRegistry,
        confirmations: ConfirmationService,
        *,
        scope_authorizer: ScopeAuthorizer,
        task_state_resolver: TaskStateResolver,
        risk_assessor: RiskAssessor,
        confirmation_preparer: ConfirmationPreparer,
        verification_preparer: VerificationPreparer,
        verification_resolver: VerificationResolver,
        decision_sink: DecisionSink,
        snapshot_writer: SnapshotWriter,
        clock: Clock | None = None,
    ) -> None:
        self.registry = registry
        self.confirmations = confirmations
        self.scope_authorizer = scope_authorizer
        self.task_state_resolver = task_state_resolver
        self.risk_assessor = risk_assessor
        self.confirmation_preparer = confirmation_preparer
        self.verification_preparer = verification_preparer
        self.verification_resolver = verification_resolver
        self.decision_sink = decision_sink
        self.snapshot_writer = snapshot_writer
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _interaction(kind: Literal["confirmation", "verification"], record_ref: str) -> InteractionRequest:
        options = (
            [
                InteractionOption(id="approve", label="确认办理"),
                InteractionOption(id="cancel", label="取消"),
            ]
            if kind == "confirmation"
            else []
        )
        return InteractionRequest(
            interaction_id=str(uuid4()),
            kind=kind,
            prompt="请完成当前操作所需的安全步骤。",
            required_fields=[],
            options=options,
            record_ref=record_ref,
        )

    def _decision(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        *,
        operation_level: OperationLevel,
        risk_level: RiskLevel | None,
        decision: SecurityDecisionCode,
        reasons: list[str],
        rules: list[str],
        interaction: InteractionRequest | None = None,
        snapshot_ref: str | None = None,
        message: str,
    ) -> SecurityDecision:
        return SecurityDecision(
            decision_id=str(uuid4()),
            task_id=context.task_id,
            run_id=context.run_id,
            action_name=action.action_name,
            parameters_ref=action.parameters_ref,
            operation_id=context.operation_id,
            action_revision=context.action_revision,
            phase=action.phase,
            operation_level=operation_level,
            risk_level=risk_level,
            decision=decision,
            reason_codes=reasons,
            rule_ids=rules,
            policy_version=POLICY_VERSION,
            authorization_snapshot_ref=snapshot_ref,
            evidence_refs=[],
            interaction=interaction,
            checked_at=self.clock(),
            message=message,
        )

    def _finish(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        declaration: CapabilityDefinition,
        decision: SecurityDecision,
    ) -> SecurityDecision:
        try:
            self.decision_sink(decision)
            return decision
        except Exception:
            if decision.decision != SecurityDecisionCode.ALLOW:
                return decision
            return self._decision(
                context,
                action,
                operation_level=declaration.operation_level,
                risk_level=decision.risk_level,
                decision=SecurityDecisionCode.PAUSE,
                reasons=["AUDIT_UNAVAILABLE"],
                rules=["audit-before-sensitive-execution"],
                message="安全记录暂不可用，操作已暂停。",
            )

    def _stop(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        declaration: CapabilityDefinition,
        *,
        decision: SecurityDecisionCode,
        reason: str,
        rule: str,
        message: str,
        risk: RiskLevel | None = None,
    ) -> SecurityDecision:
        return self._finish(
            context,
            action,
            declaration,
            self._decision(
                context,
                action,
                operation_level=declaration.operation_level,
                risk_level=risk,
                decision=decision,
                reasons=[reason],
                rules=[rule],
                message=message,
            ),
        )

    def _prepare_confirmation(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
    ) -> ConfirmationRecord:
        record = self.confirmation_preparer(context, action)
        expected = (
            context.user_id,
            context.session_id,
            context.demo_round_id,
            context.task_id,
            context.operation_id,
            action.action_name,
            context.action_revision,
            action.parameters_ref,
        )
        actual = (
            record.user_id,
            record.session_id,
            record.demo_round_id,
            record.task_id,
            record.operation_id,
            record.action_name,
            record.action_revision,
            record.parameters_ref,
        )
        if actual != expected or record.decision not in {"pending", "approved"}:
            raise SecurityError("POLICY_VIOLATION")
        return record

    @staticmethod
    def _check_challenge(
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        confirmation: ConfirmationRecord,
        risk: RiskLevel,
        challenge: VerificationChallenge,
    ) -> None:
        if (
            challenge.user_id,
            challenge.session_id,
            challenge.demo_round_id,
            challenge.task_id,
        ) != (
            context.user_id,
            context.session_id,
            context.demo_round_id,
            context.task_id,
        ) or challenge.challenge_status != "pending":
            raise SecurityError("POLICY_VIOLATION")
        if risk == RiskLevel.LOW:
            if challenge.purpose != "basic_identity":
                raise SecurityError("POLICY_VIOLATION")
            return
        summary = challenge.summary
        if (
            challenge.purpose != "action_step_up"
            or challenge.operation_id != context.operation_id
            or challenge.action_revision != context.action_revision
            or summary is None
            or summary.source_confirmation_id != confirmation.confirmation_id
            or summary.source_confirmation_version != confirmation.confirmation_version
            or summary.action_name != action.action_name
        ):
            raise SecurityError("POLICY_VIOLATION")

    def check_action(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
    ) -> SecurityDecision:
        registered = self.registry.get(action.action_name)
        if registered is None:
            placeholder = CapabilityDefinition(
                name=action.action_name,
                input_schema_ref="unknown",
                output_schema_ref="unknown",
                required_permissions=["unknown"],
                operation_level=OperationLevel.SENSITIVE,
                side_effect=True,
                confirmation_policy="per_action",
                timeout_ms=1,
                retry_policy="none",
                handler_ref="unknown",
            )
            return self._stop(
                context,
                action,
                placeholder,
                decision=SecurityDecisionCode.BLOCK,
                reason="POLICY_VIOLATION",
                rule="registered-tools-only",
                message="该操作未获准执行。",
            )
        declaration = registered.declaration

        try:
            scope_result = self.scope_authorizer(context, action, declaration)
            in_scope = scope_result if isinstance(scope_result, bool) else None
        except Exception:
            in_scope = None
        if in_scope is None:
            return self._stop(
                context, action, declaration,
                decision=SecurityDecisionCode.PAUSE,
                reason="DEPENDENCY_UNAVAILABLE",
                rule="trusted-scope-required",
                message="暂时无法核对操作权限。",
            )
        if not in_scope:
            return self._stop(
                context, action, declaration,
                decision=SecurityDecisionCode.BLOCK,
                reason="ACCESS_DENIED",
                rule="trusted-scope-required",
                message="无权执行该操作。",
            )

        try:
            task_result = self.task_state_resolver(context)
            terminated = task_result if isinstance(task_result, bool) else None
        except Exception:
            terminated = None
        if terminated is None:
            return self._stop(
                context, action, declaration,
                decision=SecurityDecisionCode.PAUSE,
                reason="DEPENDENCY_UNAVAILABLE",
                rule="trusted-task-state-required",
                message="暂时无法核对任务状态。",
            )
        if terminated:
            return self._stop(
                context, action, declaration,
                decision=SecurityDecisionCode.BLOCK,
                reason="TASK_TERMINATED",
                rule="terminated-task-cannot-resume",
                message="任务已终止，不能继续执行该操作。",
            )

        if declaration.side_effect and (
            context.operation_id is None or context.action_revision is None
        ):
            return self._finish(
                context,
                action,
                declaration,
                self._decision(
                    context,
                    action,
                    operation_level=declaration.operation_level,
                    risk_level=None,
                    decision=SecurityDecisionCode.REQUIRE_INPUT,
                    reasons=["INPUT_REQUIRED"],
                    rules=["write-action-binding-required"],
                    interaction=InteractionRequest(
                        interaction_id=str(uuid4()),
                        kind="input",
                        prompt="操作信息不完整，请重新核对。",
                        required_fields=["operation_id", "action_revision"],
                        options=[],
                        record_ref=None,
                    ),
                    message="操作信息不完整。",
                ),
            )

        try:
            risk = RiskLevel(self.risk_assessor(context, action, declaration))
        except Exception:
            risk = None
        if risk is None:
            return self._stop(
                context, action, declaration,
                decision=SecurityDecisionCode.PAUSE,
                reason="DEPENDENCY_UNAVAILABLE",
                rule="deterministic-risk-required",
                message="暂时无法完成风险核对。",
            )
        if risk == RiskLevel.HIGH:
            return self._stop(
                context, action, declaration,
                decision=SecurityDecisionCode.BLOCK,
                reason="HIGH_RISK",
                rule="high-risk-terminates-task",
                message="风险过高，任务已终止。",
                risk=risk,
            )

        confirmation: ConfirmationRecord | None = None
        confirmation_error: str | None = None
        if declaration.confirmation_policy == "per_action":
            if context.confirmation_id is not None:
                try:
                    confirmation = self.confirmations.get(context, context.confirmation_id)
                except SecurityError as exc:
                    confirmation_error = exc.code
            if confirmation_error == "ACCESS_DENIED":
                return self._stop(
                    context, action, declaration,
                    decision=SecurityDecisionCode.BLOCK,
                    reason="ACCESS_DENIED",
                    rule="confirmation-owner-must-match",
                    message="无权使用该确认记录。",
                    risk=risk,
                )
            mismatch = confirmation is not None and (
                confirmation.confirmation_version != context.confirmation_version
                or confirmation.operation_id != context.operation_id
                or confirmation.action_name != action.action_name
                or confirmation.action_revision != context.action_revision
                or confirmation.parameters_ref != action.parameters_ref
            )
            if confirmation is not None and confirmation.decision == "cancelled":
                return self._stop(
                    context, action, declaration,
                    decision=SecurityDecisionCode.BLOCK,
                    reason="TASK_TERMINATED",
                    rule="cancelled-action-cannot-resume",
                    message="该操作已取消，不能继续执行。",
                    risk=risk,
                )
            if mismatch or confirmation is None or confirmation.decision != "approved":
                reason = "CONFIRMATION_REQUIRED"
                if mismatch:
                    reason = "CONFIRMATION_STALE"
                elif confirmation_error is not None:
                    reason = confirmation_error
                elif confirmation is not None and confirmation.decision == "expired":
                    reason = "CONFIRMATION_EXPIRED"
                try:
                    prepared = self._prepare_confirmation(context, action)
                except SecurityError as exc:
                    if exc.code == "TASK_TERMINATED":
                        return self._stop(
                            context, action, declaration,
                            decision=SecurityDecisionCode.BLOCK,
                            reason="TASK_TERMINATED",
                            rule="cancelled-action-cannot-resume",
                            message="该操作已取消，不能继续执行。",
                            risk=risk,
                        )
                    return self._stop(
                        context, action, declaration,
                        decision=SecurityDecisionCode.PAUSE,
                        reason=exc.code,
                        rule="trusted-confirmation-record-required",
                        message="确认记录暂不可用，操作已暂停。",
                        risk=risk,
                    )
                except Exception:
                    return self._stop(
                        context, action, declaration,
                        decision=SecurityDecisionCode.PAUSE,
                        reason="DEPENDENCY_UNAVAILABLE",
                        rule="trusted-confirmation-record-required",
                        message="确认记录暂不可用，操作已暂停。",
                        risk=risk,
                    )
                return self._finish(
                    context,
                    action,
                    declaration,
                    self._decision(
                        context,
                        action,
                        operation_level=declaration.operation_level,
                        risk_level=risk,
                        decision=SecurityDecisionCode.REQUIRE_CONFIRMATION,
                        reasons=[reason],
                        rules=["current-button-confirmation-required"],
                        interaction=self._interaction("confirmation", prepared.confirmation_id),
                        message="请核对当前操作并在确认按钮中作答。",
                    ),
                )

        verifications: list[VerificationRecord] = []
        verification_dependency_failed = False
        for verification_id in context.verification_ids:
            try:
                record = self.verification_resolver(context, verification_id)
            except SecurityError as exc:
                if exc.code == "ACCESS_DENIED":
                    return self._stop(
                        context, action, declaration,
                        decision=SecurityDecisionCode.BLOCK,
                        reason="ACCESS_DENIED",
                        rule="verification-owner-must-match",
                        message="无权使用该验证记录。",
                        risk=risk,
                    )
                verification_dependency_failed = True
                continue
            except KeyError:
                continue
            except Exception:
                verification_dependency_failed = True
                continue
            if record.verification_id != verification_id:
                verification_dependency_failed = True
                continue
            if (
                record.user_id,
                record.session_id,
                record.demo_round_id,
            ) != (
                context.user_id,
                context.session_id,
                context.demo_round_id,
            ):
                return self._stop(
                    context, action, declaration,
                    decision=SecurityDecisionCode.BLOCK,
                    reason="ACCESS_DENIED",
                    rule="verification-owner-must-match",
                    message="无权使用该验证记录。",
                    risk=risk,
                )
            verifications.append(record)
        if verification_dependency_failed:
            return self._stop(
                context, action, declaration,
                decision=SecurityDecisionCode.PAUSE,
                reason="DEPENDENCY_UNAVAILABLE",
                rule="trusted-verification-record-required",
                message="验证记录暂不可用，操作已暂停。",
                risk=risk,
            )
        if declaration.side_effect or declaration.operation_level == OperationLevel.SENSITIVE:
            if risk == RiskLevel.MEDIUM:
                verified = any(
                    record.scope == "action"
                    and record.operation_id == context.operation_id
                    and record.action_revision == context.action_revision
                    and record.methods == ["code", "mock_face"]
                    for record in verifications
                )
            else:
                verified = any(
                    record.scope == "session"
                    or (
                        record.scope == "action"
                        and record.operation_id == context.operation_id
                        and record.action_revision == context.action_revision
                    )
                    for record in verifications
                )
            if not verified:
                try:
                    challenge = self.verification_preparer(
                        context, action, confirmation, risk,
                    )
                    self._check_challenge(context, action, confirmation, risk, challenge)
                except Exception:
                    return self._stop(
                        context, action, declaration,
                        decision=SecurityDecisionCode.PAUSE,
                        reason="DEPENDENCY_UNAVAILABLE",
                        rule="trusted-verification-challenge-required",
                        message="验证记录暂不可用，操作已暂停。",
                        risk=risk,
                    )
                return self._finish(
                    context,
                    action,
                    declaration,
                    self._decision(
                        context,
                        action,
                        operation_level=declaration.operation_level,
                        risk_level=risk,
                        decision=SecurityDecisionCode.REQUIRE_VERIFICATION,
                        reasons=["VERIFICATION_REQUIRED"],
                        rules=["funds-action-verification-required"],
                        interaction=self._interaction("verification", challenge.challenge_id),
                        message="请完成当前操作所需的身份验证。",
                    ),
                )

        checked_at = self.clock()
        snapshot_ref = None
        if declaration.operation_level == OperationLevel.SENSITIVE:
            try:
                snapshot_ref = self.snapshot_writer(
                    context, confirmation, tuple(verifications), checked_at,
                )
                if not snapshot_ref:
                    raise ValueError("empty authorization snapshot reference")
            except Exception:
                return self._stop(
                    context, action, declaration,
                    decision=SecurityDecisionCode.PAUSE,
                    reason="AUDIT_UNAVAILABLE",
                    rule="authorization-snapshot-required",
                    message="授权记录暂不可用，操作已暂停。",
                    risk=risk,
                )
        return self._finish(
            context,
            action,
            declaration,
            self._decision(
                context,
                action,
                operation_level=declaration.operation_level,
                risk_level=risk,
                decision=SecurityDecisionCode.ALLOW,
                reasons=[],
                rules=["trusted-scope", "current-confirmation", "required-verification"],
                snapshot_ref=snapshot_ref,
                message="当前操作已通过安全检查。",
            ),
        )

    def check_observation_access(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
    ) -> SecurityDecision | None:
        """Recheck current authority before looking up a previously claimed operation."""
        registered = self.registry.get(action.action_name)
        if registered is None:
            return None
        declaration = registered.declaration
        try:
            scope_result = self.scope_authorizer(context, action, declaration)
            in_scope = scope_result if isinstance(scope_result, bool) else None
        except Exception:
            in_scope = None
        if in_scope is None:
            return self._stop(
                context, action, declaration,
                decision=SecurityDecisionCode.PAUSE,
                reason="DEPENDENCY_UNAVAILABLE",
                rule="current-observation-scope-required",
                message="暂时无法核对原操作查询权限。",
            )
        if not in_scope:
            return self._stop(
                context, action, declaration,
                decision=SecurityDecisionCode.BLOCK,
                reason="ACCESS_DENIED",
                rule="current-observation-scope-required",
                message="无权查询该操作。",
            )
        return None


T = TypeVar("T")


@dataclass(frozen=True)
class OperationObservation(Generic[T]):
    operation_id: UUID
    state: Literal["not_found", "processing", "completed", "unknown"]
    result: T | None
    result_ref: str | None


OperationLookup = Callable[
    [ExecutionSecurityContext, ActionDescriptor], OperationObservation[object]
]
ResultObserver = Callable[[object], OperationObservation[object]]


@dataclass(frozen=True)
class ExecutionOutcome(Generic[T]):
    decision: SecurityDecision | None
    executed: bool
    reused: bool
    state: Literal["not_started", "processing", "completed", "unknown"]
    result: T | None
    result_ref: str | None


class DeterministicExecutor:
    """Claims each side effect once and recovers its bank result by operation ID."""

    def __init__(
        self,
        gate: SecurityGate,
        *,
        parameter_resolver: ParameterResolver,
        operation_lookup: OperationLookup,
        result_observer: ResultObserver,
    ) -> None:
        self.gate = gate
        self.parameter_resolver = parameter_resolver
        self.operation_lookup = operation_lookup
        self.result_observer = result_observer

    @staticmethod
    def _reused(
        claim: ExecutionClaim,
        observation: OperationObservation[object] | None = None,
    ) -> ExecutionOutcome:
        matching_result = (
            observation is not None
            and observation.state == claim.state
            and observation.result_ref == claim.result_ref
        )
        return ExecutionOutcome(
            decision=claim.decision,
            executed=False,
            reused=True,
            state=claim.state,
            result=observation.result if matching_result else None,
            result_ref=claim.result_ref,
        )

    @staticmethod
    def _validate_observation(
        context: ExecutionSecurityContext,
        observation: OperationObservation[object],
    ) -> None:
        if observation.operation_id != context.operation_id:
            raise SecurityError("OPERATION_CONFLICT")
        if observation.state == "completed" and not observation.result_ref:
            raise SecurityError("OPERATION_UNKNOWN")
        if observation.state == "not_found" and (
            observation.result is not None or observation.result_ref is not None
        ):
            raise SecurityError("OPERATION_CONFLICT")

    def _observe_existing(
        self,
        claim: ExecutionClaim,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        observation: OperationObservation[object] | None = None,
    ) -> ExecutionOutcome:
        try:
            observation = observation or self.operation_lookup(context, action)
            self._validate_observation(context, observation)
        except Exception:
            if claim.state == "completed":
                return self._reused(claim)
            try:
                claim = self.gate.confirmations.state.record_execution(
                    context, action, "unknown", claim.result_ref,
                )
            except SecurityStateError:
                latest = self.gate.confirmations.state.get_execution(context, action)
                if latest is None:
                    raise SecurityError("OPERATION_UNKNOWN")
                claim = latest
            return self._reused(claim)
        if claim.state == "completed":
            return self._reused(claim, observation)
        if observation.state == "not_found":
            try:
                claim = self.gate.confirmations.state.record_execution(
                    context, action, "unknown", claim.result_ref,
                )
            except SecurityStateError:
                latest = self.gate.confirmations.state.get_execution(context, action)
                if latest is None:
                    raise SecurityError("OPERATION_UNKNOWN")
                claim = latest
            return self._reused(claim)
        try:
            claim = self.gate.confirmations.state.record_execution(
                context, action, observation.state, observation.result_ref,
            )
        except SecurityStateError:
            latest = self.gate.confirmations.state.get_execution(context, action)
            if latest is None:
                raise SecurityError("OPERATION_UNKNOWN")
            claim = latest
        return self._reused(claim, observation)

    def _invoke_claimed(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        registered: RegisteredTool,
        decision: SecurityDecision,
        payload: object,
    ) -> ExecutionOutcome:
        try:
            result = registered.handler(context, payload)
        except Exception:
            self.gate.confirmations.state.record_execution(
                context, action, "unknown", None,
            )
            return ExecutionOutcome(
                decision=decision,
                executed=True,
                reused=False,
                state="unknown",
                result=None,
                result_ref=None,
            )
        try:
            observation = self.result_observer(result)
            self._validate_observation(context, observation)
            if observation.state == "not_found":
                raise SecurityError("OPERATION_UNKNOWN")
        except Exception:
            observation = OperationObservation(
                operation_id=context.operation_id,
                state="unknown",
                result=None,
                result_ref=None,
            )
        self.gate.confirmations.state.record_execution(
            context, action, observation.state, observation.result_ref,
        )
        return ExecutionOutcome(
            decision=decision,
            executed=True,
            reused=False,
            state=observation.state,
            result=observation.result,
            result_ref=observation.result_ref,
        )

    def execute(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
    ) -> ExecutionOutcome:
        registered = self.gate.registry.get(action.action_name)
        if registered is not None and registered.declaration.side_effect:
            try:
                existing = self.gate.confirmations.state.get_execution(context, action)
            except SecurityStateError as exc:
                raise SecurityError(exc.code) from exc
            if existing is not None:
                access_decision = self.gate.check_observation_access(context, action)
                if access_decision is not None:
                    return ExecutionOutcome(
                        decision=access_decision,
                        executed=False,
                        reused=True,
                        state="unknown",
                        result=None,
                        result_ref=None,
                    )
                return self._observe_existing(existing, context, action)

        decision = self.gate.check_action(context, action)
        if decision.decision != SecurityDecisionCode.ALLOW or registered is None:
            return ExecutionOutcome(
                decision=decision,
                executed=False,
                reused=False,
                state="not_started",
                result=None,
                result_ref=None,
            )
        payload = self.parameter_resolver(context, action)
        if not registered.declaration.side_effect:
            result = registered.handler(context, payload)
            return ExecutionOutcome(
                decision=decision,
                executed=True,
                reused=False,
                state="completed",
                result=result,
                result_ref=None,
            )

        try:
            claim, created = self.gate.confirmations.state.claim_execution(
                context,
                action,
                decision,
                self.gate.clock(),
            )
        except SecurityStateError as exc:
            if exc.code in {
                "CONFIRMATION_REQUIRED",
                "CONFIRMATION_STALE",
                "CONFIRMATION_EXPIRED",
                "TASK_TERMINATED",
            }:
                refreshed = self.gate.check_action(context, action)
                return ExecutionOutcome(
                    decision=refreshed,
                    executed=False,
                    reused=False,
                    state="not_started",
                    result=None,
                    result_ref=None,
                )
            raise SecurityError(exc.code) from exc
        if not created:
            return self._observe_existing(claim, context, action)
        return self._invoke_claimed(context, action, registered, decision, payload)
