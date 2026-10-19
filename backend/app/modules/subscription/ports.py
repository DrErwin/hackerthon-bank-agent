"""What the platform must supply so this module can read facts and cancel one mandate.

The module owns business decisions and wording; every bank read and the single write
go through a task-scoped security gate built by the platform (see ``reads.py``).
Nothing here defines permissions, limits or bank rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.contracts.common import DisplayField, SecurityDecisionCode
from app.contracts.platform import TrustedContext
from app.contracts.tasks import InteractionRequest

# Coercion phrases are *reported* by the module as observed facts; only the security
# policy turns them into a risk level (scenario 05 stays "low risk" otherwise).
RISK_OBSERVATIONS = (
    "screen_sharing",
    "credential_request",
    "third_party_instruction",
    "secrecy_or_urgency",
)


@dataclass(frozen=True)
class CancellationPlan:
    """One mandate cancellation, rebuilt deterministically before every gate check.

    Rebuilding it from bank facts (never from chat text) keeps the action revision and
    therefore any already-answered confirmation valid across a task's resume steps.
    """

    mandate_id: str
    account_id: str
    account_masked: str
    merchant_id: str
    merchant_name: str
    service_name: str
    amount_fen: int
    cycle: str
    effective_stop_at: datetime
    risk_observations: tuple[str, ...]
    fields: tuple[DisplayField, ...]

    def payload(self) -> dict:
        """The bound action parameters; the display fields travel with them so the gate,
        the risk facts and the confirmation card all read the same frozen facts."""

        return {
            "mandate_id": self.mandate_id,
            "account_id": self.account_id,
            "account_masked": self.account_masked,
            "merchant_id": self.merchant_id,
            "merchant_name": self.merchant_name,
            "service_name": self.service_name,
            "amount_fen": self.amount_fen,
            "cycle": self.cycle,
            "effective_stop_at": self.effective_stop_at.isoformat(),
            "risk_observations": list(self.risk_observations),
            "display_fields": [field.model_dump(mode="json") for field in self.fields],
        }


def plan_from_payload(payload: dict) -> CancellationPlan:
    """Rebuild one frozen plan from its checkpointed payload, byte-for-byte.

    The payload decides the parameter reference and the action revision the executor
    and the answered confirmation are keyed by, so it must round-trip unchanged.
    """

    return CancellationPlan(
        mandate_id=payload["mandate_id"], account_id=payload["account_id"],
        account_masked=payload["account_masked"], merchant_id=payload["merchant_id"],
        merchant_name=payload["merchant_name"], service_name=payload["service_name"],
        amount_fen=payload["amount_fen"], cycle=payload["cycle"],
        effective_stop_at=datetime.fromisoformat(payload["effective_stop_at"]),
        risk_observations=tuple(payload["risk_observations"]),
        fields=tuple(DisplayField.model_validate(field) for field in payload["display_fields"]),
    )


@dataclass(frozen=True)
class GateAnswer:
    """One security-gate answer; ``interaction`` is the gate's own pending step, so the
    module never invents a confirmation or verification reference."""

    decision: SecurityDecisionCode
    interaction: InteractionRequest | None = None
    reason_code: str | None = None
    operation_id: str | None = None


@dataclass(frozen=True)
class ExecutionOutcome:
    """The shared executor's answer; ``result`` is the bank's own receipt or failure."""

    executed: bool
    state: str
    result: object | None = None
    decision: GateAnswer | None = None
    operation_id: str | None = None
    reason_code: str | None = None


class SubscriptionPorts(Protocol):
    """Implemented by ``reads.GatewaySubscriptionPorts`` in production and by a fake
    double in unit tests. All reads are security-checked; the write never bypasses
    the confirmation gate and the shared executor."""

    def accounts(self, context: TrustedContext) -> object: ...

    def mandates(self, context: TrustedContext, account_id: str | None = None,
                 status: str | None = None) -> object: ...

    def transactions(self, context: TrustedContext, account_id: str,
                     start_at: datetime, end_at: datetime) -> object: ...

    def check_cancel(self, context: TrustedContext, plan: CancellationPlan) -> GateAnswer: ...

    def execute_cancel(self, context: TrustedContext, plan: CancellationPlan) -> ExecutionOutcome: ...
