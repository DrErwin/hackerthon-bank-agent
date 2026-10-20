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

from app.contracts.common import OperationLevel, RiskLevel
from app.contracts.platform import CapabilityDefinition, TrustedContext
from app.contracts.security import ActionDescriptor, ExecutionSecurityContext
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


_TRANSFER_CAPABILITIES = (
    CapabilityDefinition(
        name="transfer.start_transfer", input_schema_ref="StartTransferInput",
        output_schema_ref="ModuleResult[TransferTaskView]", required_permissions=["transfer.start"],
        operation_level=OperationLevel.MODIFY, side_effect=False, confirmation_policy="none",
        timeout_ms=30_000, retry_policy="none", handler_ref="transfer.workflow.start",
    ),
)
_TRANSFER_PRIVATE_TOOLS = (
    *(CapabilityDefinition(
        name=name, input_schema_ref=input_ref, output_schema_ref=output_ref,
        required_permissions=["transfer.read"], operation_level=OperationLevel.READ,
        side_effect=False, confirmation_policy="none", timeout_ms=4_000,
        retry_policy="read_only", handler_ref="bank_gateway." + name.removeprefix("bank."),
    ) for name, input_ref, output_ref in (
        ("bank.list_accounts", "TrustedContext", "AccountList"),
        ("bank.list_payees", "PayeeSearch", "PayeeList"),
        ("bank.verify_payee", "PayeeInput", "PayeeVerification"),
        ("bank.precheck_transfer", "TransferDraft", "TransferPrecheck"),
    )),
    CapabilityDefinition(
        name="bank.submit_transfer", input_schema_ref="TransferDraft",
        output_schema_ref="OperationResult[TransferReceipt]", required_permissions=["transfer.submit"],
        operation_level=OperationLevel.SENSITIVE, side_effect=True, confirmation_policy="per_action",
        timeout_ms=4_000, retry_policy="none", handler_ref="bank_gateway.submit_transfer",
    ),
)

# Security-owned snapshots, deliberately independent of module declarations.
# A new module release must not silently change the set of authorized tools.
_BILLS_READ_TOOLS = tuple(CapabilityDefinition(
    name="bills.bank." + name,
    input_schema_ref=("bills.reads.TransactionsReadInput" if name == "list_transactions"
                      else "bills.reads.AccountsReadInput"),
    output_schema_ref="TransactionList" if name == "list_transactions" else "AccountList",
    required_permissions=["bills.read"], operation_level=OperationLevel.READ,
    side_effect=False, confirmation_policy="none", timeout_ms=10_000,
    retry_policy="read_only", handler_ref="bills.bank." + name,
) for name in ("list_accounts", "list_transactions"))
_BILLS_READ_CAPABILITY = CapabilityDefinition(
    name="bills.summarize", input_schema_ref="BillSummarizeInput",
    output_schema_ref="SpendingSummary", required_permissions=["bills.read"],
    operation_level=OperationLevel.READ, side_effect=False, confirmation_policy="none",
    timeout_ms=10_000, retry_policy="read_only", handler_ref="bills.summarize",
)
_BILLS_REPORT_CAPABILITY = CapabilityDefinition(
    name="bills.generate_report", input_schema_ref="GenerateReportInput",
    output_schema_ref="BillReport", required_permissions=["bills.read"],
    operation_level=OperationLevel.READ, side_effect=False, confirmation_policy="none",
    timeout_ms=10_000, retry_policy="read_only", handler_ref="bills.generate_report",
)
_BILLS_ANOMALY_CAPABILITY = CapabilityDefinition(
    name="bills.detect_anomalies", input_schema_ref="DetectAnomaliesInput",
    output_schema_ref="AnomalyResult", required_permissions=["bills.read"],
    operation_level=OperationLevel.READ, side_effect=False, confirmation_policy="none",
    timeout_ms=10_000, retry_policy="read_only", handler_ref="bills.detect_anomalies",
)
_BILLS_READ_NAMES = frozenset(item.name for item in _BILLS_READ_TOOLS)


_SUBSCRIPTION_CAPABILITIES = (
    CapabilityDefinition(
        name="subscription.list_subscriptions", input_schema_ref="SubscriptionListInput",
        output_schema_ref="ModuleResult[SubscriptionTaskView]",
        required_permissions=["subscription.read"], operation_level=OperationLevel.READ,
        side_effect=False, confirmation_policy="none", timeout_ms=30_000,
        retry_policy="read_only", handler_ref="subscription.list_subscriptions",
    ),
    CapabilityDefinition(
        name="subscription.cancel_subscription", input_schema_ref="SubscriptionCancelInput",
        output_schema_ref="ModuleResult[SubscriptionTaskView]",
        required_permissions=["subscription.cancel"], operation_level=OperationLevel.SENSITIVE,
        side_effect=True, confirmation_policy="per_action", timeout_ms=60_000,
        retry_policy="none", handler_ref="subscription.cancel_subscription",
    ),
)
_SUBSCRIPTION_PRIVATE_TOOLS = (
    *(CapabilityDefinition(
        name="subscription.bank." + name, input_schema_ref="subscription.reads." + input_ref,
        output_schema_ref=output_ref, required_permissions=["subscription.read"],
        operation_level=OperationLevel.READ, side_effect=False, confirmation_policy="none",
        timeout_ms=10_000, retry_policy="read_only", handler_ref="subscription.bank." + name,
    ) for name, input_ref, output_ref in (
        ("list_accounts", "AccountsReadInput", "AccountList"),
        ("list_subscriptions", "MandatesReadInput", "SubscriptionMandateList"),
        ("list_transactions", "TransactionsReadInput", "TransactionList"),
    )),
    CapabilityDefinition(
        name="subscription.bank.cancel_subscription", input_schema_ref="subscription.reads.CancelWriteInput",
        output_schema_ref="OperationResult[SubscriptionCancelReceipt]",
        required_permissions=["subscription.cancel"], operation_level=OperationLevel.SENSITIVE,
        side_effect=True, confirmation_policy="per_action", timeout_ms=8_000,
        retry_policy="none", handler_ref="subscription.bank.cancel_subscription",
    ),
)


class DemoSecurityPolicy:
    """Callbacks for a single configured demo user and the server's current round."""

    policy_version = "v04-main-declarations-l02-sensitive-5"
    # Bills read access follows the v0.4 interim policy (Issue #137, PM proxy):
    # low-risk own-account queries; frozen declarations are compared for full
    # equality, so any field drift in the module equals a policy change.
    # Issues #177 and #187 add separate frozen L03 and L02 declarations.
    # Issue #191 classifies both subscription cancellation boundaries as
    # sensitive so every allow decision must carry an authorization snapshot.
    _permissions = frozenset({"transfer.start", "transfer.read", "transfer.submit", "bills.read",
                              "subscription.read", "subscription.cancel"})
    _capabilities = {item.name: item for item in (
        *_TRANSFER_CAPABILITIES, _BILLS_READ_CAPABILITY, _BILLS_REPORT_CAPABILITY,
        _BILLS_ANOMALY_CAPABILITY,
        *_SUBSCRIPTION_CAPABILITIES)}
    _private_tools = {item.name: item for item in (
        *_TRANSFER_PRIVATE_TOOLS, *_BILLS_READ_TOOLS, *_SUBSCRIPTION_PRIVATE_TOOLS)}

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
        if declaration.name in _BILLS_READ_NAMES:
            # Issue #137: LOW is a reviewed read-policy classification, not a
            # claim that transfer fraud signals were detected or checked.
            # The bank still checks each requested account against trusted identity.
            return RiskAssessment(
                RiskLevel.LOW, self.policy_version, "bills-own-account-read",
                "policy:issue-137:pm-interim-20261018",
            )
        evidence = self.risk_facts(context, action, declaration)
        if not isinstance(evidence, DemoRiskEvidence):
            raise RiskFactsUnavailable("trusted risk evidence is unavailable", rule_id="trusted-risk-evidence-required", policy_version=self.policy_version)
        if not _ALL_RISK_SIGNALS <= evidence.checked_signals:
            raise RiskFactsUnavailable("risk evidence does not cover every signal dimension", rule_id="risk-signal-coverage-required", policy_version=self.policy_version)
        evidence_ref = f"{evidence.source}:{evidence.source_version}:{evidence.evidence_ref}"
        if declaration.name == "subscription.bank.cancel_subscription":
            # Scenario 05 keeps two outcomes only (PRD §五): coercion blocks, and every
            # ordinary own-account cancellation stays low risk so it goes through the
            # confirmation button plus a session-scoped basic-identity code — never the
            # medium action-step-up face path, whatever transfer-style signals arrive.
            level = RiskLevel.HIGH if evidence.signals & _HIGH_RISK_SIGNALS else RiskLevel.LOW
            rule = "demo-risk-high" if level == RiskLevel.HIGH else "demo-risk-low"
            return RiskAssessment(level, self.policy_version, rule, evidence_ref)
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

