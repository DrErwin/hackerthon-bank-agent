"""Typed append-only audit events from the frozen safety appendix."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .bank import BankError
from .common import ContractModel, DisplayField, ID, NonNegativeInt, OperationId, PositiveInt, TaskStatus, Timestamp
from .security import SecurityDecision
from .tasks import ModuleError


class ChatMessagePayload(ContractModel):
    message_id: ID
    role: Literal["user", "assistant"]
    content_ref: ID
    related_task_ids: list[ID]


class ModelStartedPayload(ContractModel):
    model_call_id: ID
    provider: str
    model: str
    config_version: ID
    request_ref: ID


class ModelUsage(ContractModel):
    input_tokens: NonNegativeInt | None
    output_tokens: NonNegativeInt | None


class ModelFinishedPayload(ContractModel):
    model_call_id: ID
    response_ref: ID | None
    duration_ms: NonNegativeInt
    usage: ModelUsage
    error: ModuleError | None


class ContextChangedPayload(ContractModel):
    change: Literal["memory_load", "compression", "resource_load"]
    before_ref: ID | None
    after_ref: ID
    source_refs: list[ID]


class TaskTransitionPayload(ContractModel):
    previous_status: TaskStatus | None
    status: TaskStatus
    plan_revision: NonNegativeInt | None
    step_id: ID | None
    reason_code: ID
    checkpoint_ref: ID | None


class ToolStartedPayload(ContractModel):
    tool_call_id: ID
    tool_name: ID
    tool_version: ID
    arguments_ref: ID
    decision_id: ID
    operation_id: OperationId | None
    release_authorization_id: ID | None = None
    freeze_id: ID | None = None


class ToolFinishedPayload(ContractModel):
    tool_call_id: ID
    operation_id: OperationId | None
    result_ref: ID | None
    duration_ms: NonNegativeInt
    error: ModuleError | None
    release_authorization_id: ID | None = None
    freeze_id: ID | None = None


class SecurityDecidedPayload(ContractModel):
    decision: SecurityDecision
    release_authorization_id: ID | None = None
    freeze_id: ID | None = None


class ConfirmationChangedPayload(ContractModel):
    confirmation_id: ID
    confirmation_version: PositiveInt
    action_revision: PositiveInt
    decision: str
    display_ref: ID
    operation_id: OperationId | None


class VerificationChangedPayload(ContractModel):
    challenge_id: ID
    method: Literal["code", "mock_face"]
    result: str
    purpose: str
    operation_id: OperationId | None
    verification_id: ID | None
    consecutive_code_failures: NonNegativeInt
    expires_at: Timestamp
    reason_code: ID


class BankObservedPayload(ContractModel):
    operation_id: OperationId
    lookup: Literal["found", "not_found", "error"]
    operation_status: Literal["succeeded", "failed", "processing"] | None
    transaction_id: ID | None
    receipt_ref: ID | None
    error: BankError | None
    release_authorization_id: ID | None = None
    freeze_id: ID | None = None

    @model_validator(mode="after")
    def no_invented_operation_result(self) -> "BankObservedPayload":
        if self.lookup != "found" and (
            self.operation_status is not None or self.transaction_id is not None or self.receipt_ref is not None
        ):
            raise ValueError("missing or failed lookup cannot contain operation facts")
        if self.lookup == "found" and self.operation_status is None:
            raise ValueError("found operation requires operation_status")
        return self


class RecoveryCheckedPayload(ContractModel):
    previous_run_id: ID
    current_run_id: ID
    checkpoint_ref: ID | None
    operation_ids: list[OperationId]
    result: Literal["continue", "wait", "stop"]
    reason_code: ID


class AdminChangedPayload(ContractModel):
    management_operation_id: ID
    action: str
    target_ref: ID | None
    source_round_id: ID
    resulting_round_id: ID | None
    before_ref: ID | None
    after_ref: ID | None
    error: ModuleError | None


class AuditAccessedPayload(ContractModel):
    action: Literal["list", "read", "export", "download"]
    filter_ref: ID | None
    target_refs: list[ID]
    export_id: ID | None
    permitted: bool
    reason_code: ID


AuditPayload = (
    ChatMessagePayload | ModelStartedPayload | ModelFinishedPayload | ContextChangedPayload
    | TaskTransitionPayload | ToolStartedPayload | ToolFinishedPayload | SecurityDecidedPayload
    | ConfirmationChangedPayload | VerificationChangedPayload | BankObservedPayload
    | RecoveryCheckedPayload | AdminChangedPayload | AuditAccessedPayload
)

PAYLOAD_TYPES = {
    "chat.message": ChatMessagePayload,
    "model.started": ModelStartedPayload,
    "model.finished": ModelFinishedPayload,
    "context.changed": ContextChangedPayload,
    "task.transition": TaskTransitionPayload,
    "tool.started": ToolStartedPayload,
    "tool.finished": ToolFinishedPayload,
    "security.decided": SecurityDecidedPayload,
    "confirmation.changed": ConfirmationChangedPayload,
    "verification.changed": VerificationChangedPayload,
    "bank.observed": BankObservedPayload,
    "recovery.checked": RecoveryCheckedPayload,
    "admin.changed": AdminChangedPayload,
    "audit.accessed": AuditAccessedPayload,
}


class AuditEvent(ContractModel):
    event_id: ID
    trace_id: ID
    span_id: ID
    sequence: NonNegativeInt
    parent_span_id: ID | None
    demo_round_id: ID
    actor_id: ID
    session_id: ID | None
    target_session_id: ID | None
    target_user_id: ID | None
    thread_id: ID | None
    task_id: ID | None
    run_id: ID | None
    module: ID
    event_type: Literal[
        "chat.message", "model.started", "model.finished", "context.changed",
        "task.transition", "tool.started", "tool.finished", "security.decided",
        "confirmation.changed", "verification.changed", "bank.observed",
        "recovery.checked", "admin.changed", "audit.accessed",
    ]
    timestamp: Timestamp
    logical_at: Timestamp | None
    outcome: Literal["started", "succeeded", "failed", "waiting", "unknown", "denied"]
    evidence_ref: ID | None
    evidence_status: Literal["available", "missing", "restricted"]
    missing_reason: str | None
    payload: AuditPayload

    @model_validator(mode="after")
    def check_payload_and_evidence(self) -> "AuditEvent":
        if not isinstance(self.payload, PAYLOAD_TYPES[self.event_type]):
            raise ValueError("payload does not match event_type")
        if self.evidence_status != "available" and self.missing_reason is None:
            raise ValueError("missing or restricted evidence requires a reason")
        return self


class EvidenceSnapshot(ContractModel):
    evidence_id: ID
    media_type: ID
    content_ref: ID
    redaction_version: ID
    content_hash: ID
    created_at: Timestamp


class AuthorizationConfirmation(ContractModel):
    confirmation_id: ID
    version: PositiveInt
    decision: str
    decided_at: Timestamp
    display_fields: list[DisplayField]


class AuthorizationVerification(ContractModel):
    verification_id: ID
    scope: Literal["session", "action"]
    methods: list[str]
    verified_at: Timestamp
    operation_id: OperationId | None
    action_revision: PositiveInt | None


class AuthorizationSnapshot(ContractModel):
    user_id: ID
    session_id: ID
    demo_round_id: ID
    task_id: ID
    operation_id: OperationId
    action_revision: PositiveInt
    confirmation: AuthorizationConfirmation | None
    verifications: list[AuthorizationVerification]
    release_authorization_id: ID | None
    captured_at: Timestamp


class AuditEventSummary(ContractModel):
    event_id: ID
    sequence: NonNegativeInt
    trace_id: ID
    parent_span_id: ID | None
    span_id: ID
    thread_id: ID | None
    task_id: ID | None
    run_id: ID | None
    module: ID
    event_type: ID
    timestamp: Timestamp
    outcome: Literal["started", "succeeded", "failed", "waiting", "unknown", "denied"]
    evidence_ref: ID | None
    demo_round_id: ID
    actor_id: ID
    target_user_id: ID | None
    session_id: ID | None
    target_session_id: ID | None


class AuditEventDetail(AuditEventSummary):
    payload: AuditPayload
    evidence: str | None
    evidence_status: Literal["available", "missing", "restricted"]
    missing_reason: str | None

    @model_validator(mode="after")
    def check_detail(self) -> "AuditEventDetail":
        if self.event_type not in PAYLOAD_TYPES or not isinstance(self.payload, PAYLOAD_TYPES[self.event_type]):
            raise ValueError("payload does not match event_type")
        if self.evidence_status != "available" and self.missing_reason is None:
            raise ValueError("missing or restricted evidence requires a reason")
        return self
