"""Capability registration and the ordinary-transfer public call shape."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import model_validator

from .bank import PayeeInput
from .common import ContractModel, ID, Money, NonNegativeInt, OperationId, OperationLevel, PositiveInt, RequestId, Timestamp


class CapabilityDefinition(ContractModel):
    name: ID
    input_schema_ref: ID
    output_schema_ref: ID
    required_permissions: list[ID]
    operation_level: OperationLevel
    side_effect: bool
    confirmation_policy: Literal["none", "per_action"]
    timeout_ms: PositiveInt
    retry_policy: Literal["none", "read_only"]
    handler_ref: ID

    @model_validator(mode="after")
    def no_write_auto_retry(self) -> "CapabilityDefinition":
        if self.retry_policy == "read_only" and (self.side_effect or self.operation_level != OperationLevel.READ):
            raise ValueError("read_only retry is only valid for read-only capabilities")
        return self


ToolDeclaration = CapabilityDefinition


class ModuleManifest(ContractModel):
    module_name: ID
    version: ID
    owner: ID
    description: str
    implementation_kind: Literal["workflow", "agent"]
    capabilities: list[CapabilityDefinition]
    dependencies: list[ID]


class TrustedContext(ContractModel):
    user_id: ID
    session_id: ID
    task_id: ID
    run_id: ID
    parent_task_id: ID | None
    demo_round_id: ID


T = TypeVar("T")


class CapabilityCall(ContractModel, Generic[T]):
    capability_name: ID
    input: T
    trusted_context: TrustedContext


class StartTransferInput(ContractModel):
    request_id: RequestId
    intent_text: str
    payer_account_id: ID | None = None
    payee: PayeeInput | None = None
    payee_hint: str | None = None
    amount_fen: Money | None = None
    execute_at: Timestamp | None = None

    @model_validator(mode="after")
    def positive_if_given(self) -> "StartTransferInput":
        if self.amount_fen == 0:
            raise ValueError("transfer amount must be greater than zero")
        return self


class GetTransferStatusInput(ContractModel):
    task_id: ID | None = None
    operation_id: OperationId | None = None

    @model_validator(mode="after")
    def exactly_one_reference(self) -> "GetTransferStatusInput":
        if (self.task_id is None) == (self.operation_id is None):
            raise ValueError("exactly one of task_id or operation_id is required")
        return self


class GetTransferSummaryInput(ContractModel):
    task_id: ID
    purpose: str


class ResourceRef(ContractModel):
    resource_id: ID
    owner_user_id: ID
    task_id: ID
    purpose: str
    media_type: str
    size_bytes: NonNegativeInt
