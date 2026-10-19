"""Platform and module result envelopes shared by all business modules."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import model_validator

from .bank import OperationResult, PayeeDisplay, TransferReceipt
from .common import ContractModel, ID, NonNegativeInt, OperationId, OperationStatus, PositiveMoney, TaskStatus, Timestamp


class InteractionOption(ContractModel):
    id: ID
    label: str


class InteractionRequest(ContractModel):
    interaction_id: ID
    kind: Literal["input", "confirmation", "verification"]
    prompt: str
    required_fields: list[str]
    options: list[InteractionOption]
    record_ref: ID | None

    @model_validator(mode="after")
    def require_controlled_record(self) -> "InteractionRequest":
        if self.kind != "input" and self.record_ref is None:
            raise ValueError("confirmation and verification require record_ref")
        return self


class ModuleError(ContractModel):
    code: ID
    source: Literal["platform", "security", "bank", "transfer", "bills", "subscription", "cross"]
    field: str | None
    reason: str
    upstream_code: str | None


class RejectedRequest(ContractModel):
    error: ModuleError


T = TypeVar("T")


class ModuleResult(ContractModel, Generic[T]):
    task_id: ID
    run_id: ID
    status: TaskStatus
    data: T | None
    message: str
    interaction: InteractionRequest | None
    error: ModuleError | None
    allowed_actions: list[Literal["provide_input", "confirm", "verify", "query", "cancel", "resume"]]
    recovery_required: bool
    recovery_reason: str | None

    @model_validator(mode="after")
    def match_wait_to_interaction(self) -> "ModuleResult[T]":
        if self.status == TaskStatus.WAITING_INPUT and (self.interaction is None or self.interaction.kind != "input"):
            raise ValueError("waiting_input requires an input interaction")
        if self.status == TaskStatus.WAITING_APPROVAL and (
            self.interaction is None or self.interaction.kind not in {"confirmation", "verification"}
        ):
            raise ValueError("waiting_approval requires confirmation or verification")
        if self.interaction is not None and self.status not in {TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL}:
            raise ValueError("interaction requires a waiting task status")
        if self.recovery_required and self.recovery_reason is None:
            raise ValueError("recovery_required requires a reason")
        return self


class TransferTaskView(ContractModel):
    operation_id: OperationId | None
    payer_account_id: ID | None
    payee: PayeeDisplay | None
    amount_fen: PositiveMoney | None
    operation: OperationResult[TransferReceipt] | None

    @model_validator(mode="after")
    def same_operation(self) -> "TransferTaskView":
        if self.operation is not None and self.operation_id != self.operation.operation_id:
            raise ValueError("operation result must match operation_id")
        return self


class TransferSummary(ContractModel):
    operation_id: OperationId | None
    payee: PayeeDisplay | None
    amount_fen: PositiveMoney | None
    transaction_id: ID | None
    executed_at: Timestamp | None
    operation_status: OperationStatus | None
    as_of: Timestamp


class TaskView(ModuleResult[T], Generic[T]):
    # Which business module owns the task; the frontend picks its slot with it (§6.5).
    # Nullable so views written before the platform fills it stay readable.
    module: Literal["transfer", "bills", "subscription", "cross"] | None = None
    thread_id: ID
    demo_round_id: ID
    snapshot_at: Timestamp
    task_revision: NonNegativeInt
    cancel_requested: bool
