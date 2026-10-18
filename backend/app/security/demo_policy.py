"""Fail-closed policy callbacks for the fixed v0.3 local transfer demo.

Risk facts must come from a server-owned resolver. This module classifies trusted
signals; it does not inspect chat text, choose amount thresholds, or infer facts
that the runtime cannot provide.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.contracts.common import RiskLevel
from app.contracts.platform import CapabilityDefinition, TrustedContext
from app.contracts.security import ActionDescriptor, ExecutionSecurityContext
from app.modules.bills.manifest import MANIFEST as BILLS_MANIFEST
from app.modules.bills.reads import PRIVATE_TOOLS as BILLS_PRIVATE_TOOLS
from app.modules.transfer.manifest import MANIFEST, PRIVATE_TOOLS
from app.services.mock_bank.verification import AdminContext
from app.security.gate import RiskAssessment, RiskFactsUnavailable


class DemoRiskSignal(StrEnum):
    """Named signals from transfer PRD 01 section 9.2."""

    FAMILIAR_PAYEE = "familiar_payee"
    FAMILIAR_DEVICE = "familiar_device"
    USUAL_AMOUNT_RANGE = "usual_amount_range"
    CLEAR_REQUEST = "clear_request"
    NEW_PAYEE = "new_payee"
    UNUSUAL_AMOUNT = "unusual_amount"
    RAPID_ACCOUNT_CHANGES = "rapid_account_changes"
    HESITATION_OR_UNCLEAR_PURPOSE = "hesitation_or_unclear_purpose"
    IMPERSONATION = "impersonation"
    SECRECY_OR_URGENT_PRESSURE = "secrecy_or_urgent_pressure"
    SCREEN_SHARING = "screen_sharing"
    CREDENTIAL_REQUEST = "credential_request"
    UNFAMILIAR_LINK = "unfamiliar_link"
    UNUSUAL_DEVICE_OR_COUNTERPARTY = "unusual_device_or_counterparty"


_LOW_RISK_EVIDENCE = frozenset({
    DemoRiskSignal.FAMILIAR_PAYEE,
    DemoRiskSignal.FAMILIAR_DEVICE,
    DemoRiskSignal.USUAL_AMOUNT_RANGE,
    DemoRiskSignal.CLEAR_REQUEST,
})
_MEDIUM_RISK_SIGNALS = frozenset({
    DemoRiskSignal.NEW_PAYEE,
    DemoRiskSignal.UNUSUAL_AMOUNT,
    DemoRiskSignal.RAPID_ACCOUNT_CHANGES,
    DemoRiskSignal.HESITATION_OR_UNCLEAR_PURPOSE,
})
_HIGH_RISK_SIGNALS = frozenset({
    DemoRiskSignal.IMPERSONATION,
    DemoRiskSignal.SECRECY_OR_URGENT_PRESSURE,
    DemoRiskSignal.SCREEN_SHARING,
    DemoRiskSignal.CREDENTIAL_REQUEST,
    DemoRiskSignal.UNFAMILIAR_LINK,
    DemoRiskSignal.UNUSUAL_DEVICE_OR_COUNTERPARTY,
})
_ALL_RISK_SIGNALS = frozenset(DemoRiskSignal)


@dataclass(frozen=True)
class DemoRiskEvidence:
    """Server-sourced facts with enough provenance to explain the classification."""

    source: str
    source_version: str
    evidence_ref: str
    signals: frozenset[DemoRiskSignal]
    checked_signals: frozenset[DemoRiskSignal]

    def __post_init__(self) -> None:
        provenance = (self.source, self.source_version, self.evidence_ref)
        if not all(isinstance(value, str) and value for value in provenance) or any(
            char.isspace() for value in provenance if isinstance(value, str) for char in value
        ):
            raise ValueError("risk evidence requires safe source, version, and reference identifiers")
        if not isinstance(self.signals, frozenset) or any(
            not isinstance(signal, DemoRiskSignal) for signal in self.signals
        ):
            raise ValueError("risk evidence must contain known server-side signals")
        if not isinstance(self.checked_signals, frozenset) or any(
            not isinstance(signal, DemoRiskSignal) for signal in self.checked_signals
        ):
            raise ValueError("risk evidence must identify checked signal dimensions")
        if not self.signals <= self.checked_signals:
            raise ValueError("observed risk signals must be covered by checked dimensions")


RiskFactsResolver = Callable[
    [ExecutionSecurityContext, ActionDescriptor, CapabilityDefinition], DemoRiskEvidence,
]
CurrentDemoRound = Callable[[], str]


class DemoSecurityPolicy:
    """Callbacks for a single configured demo user and the server's current round."""

    policy_version = "v03-local-demo-risk-1"
    # Bills read access follows the v0.4 interim policy (Issue #137, PM proxy):
    # low-risk own-account queries; frozen declarations are compared for full
    # equality, so any field drift in the module equals a policy change.
    _permissions = frozenset({"transfer.start", "transfer.read", "transfer.submit", "bills.read"})
    _capabilities = {item.name: item for item in (*MANIFEST.capabilities, *BILLS_MANIFEST.capabilities)}
    _private_tools = {item.name: item for item in (*PRIVATE_TOOLS, *BILLS_PRIVATE_TOOLS)}

    def __init__(
        self,
        *,
        demo_user_id: str,
        admin_actor_id: str,
        current_demo_round: CurrentDemoRound,
        risk_facts: RiskFactsResolver,
    ) -> None:
        if not demo_user_id.strip() or not admin_actor_id.strip():
            raise ValueError("demo and administrator identities must be configured")
        if admin_actor_id == demo_user_id:
            raise ValueError("administrator identity must be separate from the demo user")
        self.demo_user_id = demo_user_id
        self.admin_actor_id = admin_actor_id
        self.current_demo_round = current_demo_round
        self.risk_facts = risk_facts

    def _in_current_scope(self, user_id: str, demo_round_id: str) -> bool:
        try:
            current_round = self.current_demo_round()
        except Exception:
            return False
        return (
            isinstance(current_round, str)
            and bool(current_round)
            and user_id == self.demo_user_id
            and demo_round_id == current_round
        )

    def authorize_capability(
        self, context: TrustedContext, declaration: CapabilityDefinition,
    ) -> bool:
        expected = self._capabilities.get(declaration.name)
        return (
            isinstance(context, TrustedContext)
            and self._in_current_scope(context.user_id, context.demo_round_id)
            and expected is not None
            and declaration == expected
            and set(declaration.required_permissions) <= self._permissions
        )

    def authorize_tool(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        declaration: CapabilityDefinition,
    ) -> bool:
        expected = self._private_tools.get(declaration.name)
        return (
            isinstance(context, ExecutionSecurityContext)
            and isinstance(action, ActionDescriptor)
            and self._in_current_scope(context.user_id, context.demo_round_id)
            and action.action_name == declaration.name
            and expected is not None
            and declaration == expected
            and set(declaration.required_permissions) <= self._permissions
        )

    def authorize_face(
        self, admin: AdminContext, challenge_id: str, submission_id: UUID, result: str,
    ) -> bool:
        return (
            isinstance(admin, AdminContext)
            and admin.actor_id == self.admin_actor_id
            and admin.authorized is True
            and admin.target_user_id == self.demo_user_id
            and self._in_current_scope(admin.target_user_id, admin.demo_round_id)
            and bool(challenge_id)
            and bool(submission_id)
            and result in {"passed", "failed"}
        )

    def assess_risk(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        declaration: CapabilityDefinition,
    ) -> RiskAssessment:
        if not self.authorize_tool(context, action, declaration):
            raise RiskFactsUnavailable("risk assessment is outside the authorized demo scope", rule_id="risk-assessment-out-of-scope", policy_version=self.policy_version)
        evidence = self.risk_facts(context, action, declaration)
        if not isinstance(evidence, DemoRiskEvidence):
            raise RiskFactsUnavailable("trusted risk evidence is unavailable", rule_id="trusted-risk-evidence-required", policy_version=self.policy_version)
        if not _ALL_RISK_SIGNALS <= evidence.checked_signals:
            raise RiskFactsUnavailable("risk evidence does not cover every signal dimension", rule_id="risk-signal-coverage-required", policy_version=self.policy_version)
        evidence_ref = f"{evidence.source}:{evidence.source_version}:{evidence.evidence_ref}"
        if evidence.signals & _HIGH_RISK_SIGNALS:
            return RiskAssessment(
                RiskLevel.HIGH, self.policy_version, "demo-risk-high", evidence_ref,
            )
        if evidence.signals & _MEDIUM_RISK_SIGNALS:
            return RiskAssessment(
                RiskLevel.MEDIUM, self.policy_version, "demo-risk-medium", evidence_ref,
            )
        if _LOW_RISK_EVIDENCE <= evidence.signals:
            return RiskAssessment(
                RiskLevel.LOW, self.policy_version, "demo-risk-low", evidence_ref,
            )
        raise RiskFactsUnavailable(
            "risk evidence is incomplete; refusing to assume low risk",
            rule_id="low-risk-evidence-required",
            policy_version=self.policy_version,
        )
