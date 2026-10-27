"""Explicit, bounded P01 demonstration evidence; never a funds authorization."""

from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING

from .demo_policy import DemoRiskEvidence, DemoRiskSignal as Signal, _HIGH_RISK_SIGNALS
from .demo_text_risk import demo_text_risk
from .risk_detector import detect_transfer_risk

if TYPE_CHECKING:
    from app.agent_platform.risk_inputs import RiskInputs


PROFILE_ID = "p01-marked-demo-v1"
_REQUEST = (
    "这月养老金5000元到账了，帮我安排一下：留1500元生活费，"
    "2500元转自己的储蓄账户，1000元给家人，顺便看看没用的扣费。"
)
_FOLLOWUPS = frozenset({"请再列一下可退订项目", "1500元", "2500元", "1000元"})
_TRANSFERS = (
    ({"kind": "own", "account_id": "A5"}, 250_000),
    ({"kind": "saved", "payee_id": "A4"}, 100_000),
)
_SIMULATED_SIGNALS = frozenset({
    Signal.FAMILIAR_DEVICE, Signal.USUAL_AMOUNT_RANGE, Signal.CLEAR_REQUEST,
})
# These twelve were explicitly approved for this profile. A future signal must
# not silently inherit coverage. The two payee dimensions are never simulated.
_SIMULATED_CHECKED = frozenset({
    Signal.FAMILIAR_DEVICE, Signal.USUAL_AMOUNT_RANGE, Signal.CLEAR_REQUEST,
    Signal.UNUSUAL_AMOUNT, Signal.RAPID_ACCOUNT_CHANGES,
    Signal.HESITATION_OR_UNCLEAR_PURPOSE, Signal.IMPERSONATION,
    Signal.SECRECY_OR_URGENT_PRESSURE, Signal.SCREEN_SHARING,
    Signal.CREDENTIAL_REQUEST, Signal.UNFAMILIAR_LINK,
    Signal.UNUSUAL_DEVICE_OR_COUNTERPARTY,
})


def pension_demo_risk(inputs: RiskInputs) -> DemoRiskEvidence:
    """Return marked demo evidence only for the two approved parent-sourced legs.

    The platform must authenticate the user/task/round, immutable action and
    durable parent relation before constructing these inputs. It supplies the
    parent's original text plus all controlled parent/child ordinary followups.
    Missing legacy source fields do not count as a trusted parent.

    Positive threats run first even for unsupported parameters or sources.
    Exact text/parameter matches add twelve simulated dimensions; actual bank
    payee facts remain independent. Missing bank facts therefore still pause.
    This pure provider performs no lookup, grant, confirmation or bank write.
    Runtime use requires the separate, explicit platform opt-in.
    """
    observed = demo_text_risk(inputs, None)
    if observed.signals & _HIGH_RISK_SIGNALS:
        return observed

    source = getattr(inputs, "request_source_task_id", None)
    turns = inputs.request_text.split("\n")
    if (
        not isinstance(source, str) or not source.strip() or source == inputs.task_id
        or turns[0] != _REQUEST or any(turn not in _FOLLOWUPS for turn in turns[1:])
        or inputs.action_name != "bank.submit_transfer" or not inputs.operation_id
        or type(inputs.action_facts.get("amount_fen")) is not int
        or not any(inputs.action_facts == {
            "operation_id": inputs.operation_id, "payer_account_id": "A1",
            "payee": payee, "amount_fen": amount,
        } for payee, amount in _TRANSFERS)
    ):
        return observed

    # This existing pure detector reads already-resolved bank facts, not the
    # bank itself. Its checked values override simulated values in those axes.
    actual = detect_transfer_risk(inputs)
    reference = sha256(f"{inputs.evidence_ref}:{PROFILE_ID}".encode()).hexdigest()[:24]
    return DemoRiskEvidence(
        source="marked-pension-demo", source_version=PROFILE_ID, evidence_ref=reference,
        signals=(_SIMULATED_SIGNALS - actual.checked_signals) | actual.signals,
        checked_signals=_SIMULATED_CHECKED | actual.checked_signals,
    )
