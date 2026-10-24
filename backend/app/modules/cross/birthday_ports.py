"""Birthday orchestration ports: what the platform must supply for ticket 03.

The birthday money writes are private bank tools (B10—B13/B20—B22) behind the
security gate that v05-cross-security/01 declared — they are not public
registry capabilities and never go through ``dispatch_child``. This protocol is
the seam the platform (v05-cross-platform/09) implements with the real gate,
the §3.5 release records and the birthday gateway; the cross module only
orchestrates and reports. Every answer the ports return is a bank or gate
fact; nothing here is model-filled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.contracts.bank import (
    CreateOrderInput, FreezeFundsInput, ListProductsInput, OperationResult,
    QueryFailure, QueryOk,
)
from app.contracts.common import SecurityDecisionCode
from app.contracts.platform import TrustedContext
from app.contracts.tasks import InteractionRequest


@dataclass(frozen=True)
class GateAnswer:
    """One gate verdict for a birthday write; confirmation carries the §3.5
    clause on freeze (the platform builds those display fields)."""

    decision: SecurityDecisionCode
    operation_id: str
    interaction: InteractionRequest | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class WriteOutcome:
    """What the bank said about one submitted write; unknown is never success."""

    executed: bool
    state: str  # "completed" | "unknown" | "failed"
    result: OperationResult | QueryFailure | None = None
    operation_id: str | None = None


@dataclass(frozen=True)
class ReleaseOutcome:
    """The §3.5 controlled ending as the user may see it."""

    status: str  # "released" | "nothing_to_release" | "needs_attention" | "blocked"
    released_amount_fen: int | None = None
    remaining_fen: int | None = None
    consumed_total_fen: int | None = None
    release_operation_id: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class BirthdayPlan:
    """The frozen facts one birthday execution runs on."""

    payer_account_id: str
    budget_id: str
    budget_version: int
    budget_limit_fen: int
    freeze_amount_fen: int
    deliver_by: str
    delivery_ref: str
    items: tuple[dict, ...] = field(default_factory=tuple)


class BirthdayPorts(Protocol):
    """Platform-supplied seam over the birthday gateway and security gate."""

    def products(self, context: TrustedContext, request: ListProductsInput):
        """B22 read: the bank's real candidate products for the goal."""

    def freeze_check(self, context: TrustedContext, plan: BirthdayPlan) -> GateAnswer:
        """Gate verdict for one freeze; the confirmation shows the release clause."""

    def freeze_execute(self, context: TrustedContext,
                       plan: BirthdayPlan) -> WriteOutcome:
        """Submit the freeze; the outcome keeps its original operation id."""

    def order_check(self, context: TrustedContext, plan: BirthdayPlan,
                    item: dict) -> GateAnswer:
        ...

    def order_execute(self, context: TrustedContext, plan: BirthdayPlan,
                      item: dict) -> WriteOutcome:
        ...

    def capture_check(self, context: TrustedContext, plan: BirthdayPlan, item: dict,
                      order_id: str) -> GateAnswer:
        ...

    def capture_execute(self, context: TrustedContext, plan: BirthdayPlan, item: dict,
                        order_id: str) -> WriteOutcome:
        """Pay one order from the freeze; the bank binds order and transaction."""

    def grant_release(self, context: TrustedContext, plan: BirthdayPlan,
                      confirmation_ref: str) -> str:
        """Record the §3.5 authorization from the approved freeze confirmation."""

    def bind_freeze(self, context: TrustedContext, plan: BirthdayPlan,
                    operation_id: str) -> str | None:
        """Bind (or re-query by the original id) the bank freeze id."""

    def requery(self, context: TrustedContext, plan: BirthdayPlan,
                target: str) -> WriteOutcome | None:
        """Re-read one submitted write by its original operation id (B05)."""

    def finalize(self, context: TrustedContext, plan: BirthdayPlan,
                 reason: str) -> ReleaseOutcome:
        """The limited ending: release only the bank-verified remainder."""
