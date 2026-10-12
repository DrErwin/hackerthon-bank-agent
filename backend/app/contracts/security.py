"""Trusted confirmation, verification and execution-decision records."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .bank import PayeeDisplay
from .common import (
    ContractModel, DisplayField, ID, Money, NonNegativeInt, OperationId,
    OperationLevel, Phase, PositiveInt, RiskLevel, SecurityDecisionCode, Timestamp,
)
from .tasks import InteractionRequest


class ExecutionSecurityContext(ContractModel):
    user_id: ID
    session_id: ID
    demo_round_id: ID
    task_id: ID
    run_id: ID
    source_task_id: ID | None
    operation_id: OperationId | None
    action_revision: PositiveInt | None
    confirmation_id: ID | None
    confirmation_version: PositiveInt | None
    verification_ids: list[ID]
    release_authorization_id: ID | None


class ActionDescriptor(ContractModel):
    action_name: ID
    parameters_ref: ID
    resource_refs: list[ID]
    phase: Phase


class SecurityDecision(ContractModel):
    decision_id: ID
    task_id: ID
    run_id: ID
    action_name: ID
    parameters_ref: ID
    operation_id: OperationId | None
    action_revision: PositiveInt | None
    phase: Phase
    operation_level: OperationLevel
    risk_level: RiskLevel | None
    decision: SecurityDecisionCode
    reason_codes: list[ID]
    rule_ids: list[ID]
    policy_version: ID
    authorization_snapshot_ref: ID | None
    evidence_refs: list[ID]
    interaction: InteractionRequest | None
    checked_at: Timestamp
    message: str

    @model_validator(mode="after")
    def check_decision_shape(self) -> "SecurityDecision":
        if self.decision == SecurityDecisionCode.ALLOW and self.risk_level is None:
            raise ValueError("allow requires a known risk level")
        if self.decision != SecurityDecisionCode.ALLOW and not self.reason_codes:
            raise ValueError("non-allow decision requires a reason")
        expected = {
            SecurityDecisionCode.REQUIRE_INPUT: "input",
            SecurityDecisionCode.REQUIRE_CONFIRMATION: "confirmation",
            SecurityDecisionCode.REQUIRE_VERIFICATION: "verification",
        }.get(self.decision)
        if expected is None and self.interaction is not None:
            raise ValueError("only require decisions have an interaction")
        if expected is not None and (self.interaction is None or self.interaction.kind != expected):
            raise ValueError("require decision needs its matching interaction")
        if self.decision == SecurityDecisionCode.ALLOW and self.phase == Phase.EXECUTION:
            if self.operation_level == OperationLevel.SENSITIVE and self.authorization_snapshot_ref is None:
                raise ValueError("sensitive execution requires authorization snapshot")
            if self.operation_level == OperationLevel.SENSITIVE and (
                self.operation_id is None or self.action_revision is None
            ):
                raise ValueError("sensitive execution requires an operation and action revision")
        return self


class ConfirmationRecord(ContractModel):
    confirmation_id: ID
    confirmation_version: PositiveInt
    user_id: ID
    session_id: ID
    demo_round_id: ID
    task_id: ID
    operation_id: OperationId
    action_name: ID
    action_revision: PositiveInt
    parameters_ref: ID
    display_fields: list[DisplayField] = Field(min_length=1)
    created_at: Timestamp
    expires_at: Timestamp
    decision: Literal["pending", "approved", "cancelled", "expired", "superseded"]
    decided_at: Timestamp | None

    @model_validator(mode="after")
    def decision_time(self) -> "ConfirmationRecord":
        if self.decision in {"approved", "cancelled"} and self.decided_at is None:
            raise ValueError("user decision requires decided_at")
        if self.decision in {"pending", "expired", "superseded"} and self.decided_at is not None:
            raise ValueError("only a user decision has decided_at")
        return self


class ConfirmationAnswer(ContractModel):
    confirmation_id: ID
    confirmation_version: PositiveInt
    choice: Literal["approve", "cancel"]


class ConfirmationView(ContractModel):
    confirmation_id: ID
    task_id: ID
    confirmation_version: PositiveInt
    display_fields: list[DisplayField] = Field(min_length=1)
    created_at: Timestamp
    expires_at: Timestamp
    decision: Literal["pending", "approved", "cancelled", "expired", "superseded"]


class VerificationSummary(ContractModel):
    operation_id: OperationId
    action_revision: PositiveInt
    source_confirmation_id: ID
    source_confirmation_version: PositiveInt
    action_name: ID
    amount_fen: Money | None
    payee: PayeeDisplay | None
    display_fields: list[DisplayField] = Field(min_length=1)

    @model_validator(mode="after")
    def transfer_has_confirmed_details(self) -> "VerificationSummary":
        if self.action_name == "bank.submit_transfer" and (self.amount_fen is None or self.payee is None):
            raise ValueError("transfer verification requires amount and verified payee")
        if self.action_name == "bank.submit_transfer" and self.amount_fen == 0:
            raise ValueError("transfer verification amount must be positive")
        return self


class VerificationChallenge(ContractModel):
    challenge_id: ID
    user_id: ID
    session_id: ID
    demo_round_id: ID
    task_id: ID
    purpose: Literal["basic_identity", "action_step_up"]
    operation_id: OperationId | None
    action_revision: PositiveInt | None
    summary: VerificationSummary | None
    required_methods: list[Literal["code", "mock_face"]]
    created_at: Timestamp
    code_created_at: Timestamp
    code_expires_at: Timestamp
    face_started_at: Timestamp | None
    face_expires_at: Timestamp | None
    challenge_status: Literal["pending", "passed", "failed", "expired", "superseded", "cancelled"]
    code_result: Literal["pending", "passed", "failed", "expired", "cancelled"]
    face_result: Literal["pending", "passed", "failed", "expired", "cancelled", "not_required"]
    consecutive_code_failures: NonNegativeInt

    @model_validator(mode="after")
    def check_scope(self) -> "VerificationChallenge":
        if self.purpose == "basic_identity":
            if self.operation_id is not None or self.action_revision is not None or self.summary is not None:
                raise ValueError("basic verification has no action summary")
            if self.required_methods != ["code"] or self.face_result != "not_required":
                raise ValueError("basic verification uses code only")
        else:
            if self.operation_id is None or self.action_revision is None or self.summary is None:
                raise ValueError("action verification requires action and summary")
            if self.required_methods != ["code", "mock_face"]:
                raise ValueError("action verification uses code and mock_face")
            if self.summary.operation_id != self.operation_id or self.summary.action_revision != self.action_revision:
                raise ValueError("summary must match the action")
        if (self.face_started_at is None) != (self.face_expires_at is None):
            raise ValueError("face start and expiry must appear together")
        return self


class VerificationRecord(ContractModel):
    verification_id: ID
    user_id: ID
    session_id: ID
    demo_round_id: ID
    scope: Literal["session", "action"]
    operation_id: OperationId | None
    action_revision: PositiveInt | None
    methods: list[Literal["code", "mock_face"]]
    verified_at: Timestamp
    source_challenge_id: ID

    @model_validator(mode="after")
    def check_scope(self) -> "VerificationRecord":
        if self.scope == "session" and (self.operation_id is not None or self.action_revision is not None):
            raise ValueError("session verification has no action")
        if self.scope == "action" and (self.operation_id is None or self.action_revision is None):
            raise ValueError("action verification requires an action")
        if self.scope == "session" and self.methods != ["code"]:
            raise ValueError("session verification uses code only")
        if self.scope == "action" and self.methods != ["code", "mock_face"]:
            raise ValueError("action verification requires both methods")
        return self


class VerificationView(ContractModel):
    challenge_id: ID
    task_id: ID
    created_at: Timestamp
    summary: VerificationSummary | None
    required_methods: list[Literal["code", "mock_face"]]
    code_expires_at: Timestamp
    face_started_at: Timestamp | None
    face_expires_at: Timestamp | None
    code_result: Literal["pending", "passed", "failed", "expired", "cancelled"]
    face_result: Literal["pending", "passed", "failed", "expired", "cancelled", "not_required"]
    challenge_status: Literal["pending", "passed", "failed", "expired", "superseded", "cancelled"]
    consecutive_code_failures: NonNegativeInt
