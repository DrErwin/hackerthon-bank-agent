"""Scenario-05 platform wiring: one task-scoped gate, the shared executor and the hooks.

The subscription module owns the wording and the business decisions; this file supplies
what only the platform may supply: a real ``SecurityGate`` per task, the shared
executor behind the single B30 write, a stable operation reservation, the bank-side
write authorization hook, and the confirmation/verification hooks an API resume uses.

The confirmation/verification records themselves stay platform-owned shared facts
(``agent_transfer_confirmations`` / ``agent_transfer_verifications``): a subscription
task answers and binds them exactly like a transfer task, so only the audited module
label differs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.contracts.audit import (
    AuthorizationConfirmation, AuthorizationSnapshot, AuthorizationVerification,
    ConfirmationChangedPayload, SecurityDecidedPayload, VerificationChangedPayload,
)
from app.contracts.common import DisplayField, Phase, RiskLevel, SecurityDecisionCode
from app.contracts.platform import TrustedContext
from app.contracts.security import (
    ActionDescriptor, ConfirmationAnswer, ConfirmationRecord, ExecutionSecurityContext,
    SecurityDecision, VerificationRecord, VerificationSummary,
)
from app.modules.subscription.entry import register_subscription as register_module
from app.modules.subscription.reads import GatewaySubscriptionPorts
from app.security import SecurityError, SecurityGate, ToolRegistry
from app.security.demo_policy import DemoRiskEvidence, DemoRiskSignal, DemoSecurityPolicy
from app.security.gate import RiskFactsUnavailable
from app.storage.database import parameter_digest


CANCEL_TOOL = "subscription.bank.cancel_subscription"

# The demo bank can attest these about one routine own-account cancellation; the demo
# policy keeps every ordinary cancellation low risk and only coercion signals block.
_ROUTINE_SIGNALS = frozenset({
    DemoRiskSignal.FAMILIAR_PAYEE,
    DemoRiskSignal.FAMILIAR_DEVICE,
    DemoRiskSignal.USUAL_AMOUNT_RANGE,
    DemoRiskSignal.CLEAR_REQUEST,
})
# Coercion facts the *module* observed in the user's own words (ports.RISK_OBSERVATIONS)
# mapped onto the policy's named demo signals. Unknown names fail closed.
_OBSERVED_SIGNALS = {
    "screen_sharing": DemoRiskSignal.SCREEN_SHARING,
    "credential_request": DemoRiskSignal.CREDENTIAL_REQUEST,
    "third_party_instruction": DemoRiskSignal.IMPERSONATION,
    "secrecy_or_urgency": DemoRiskSignal.SECRECY_OR_URGENT_PRESSURE,
}
_SOURCE = "server-local-demo-fixture"


def subscription_risk_evidence(
    payload: object, *, source_version: str, checked_signals: frozenset[DemoRiskSignal],
) -> DemoRiskEvidence:
    """Server-owned risk facts for one cancellation, or fail closed with no default."""

    if not isinstance(payload, Mapping):
        raise RiskFactsUnavailable(
            "no bound subscription facts for this action",
            rule_id="subscription-binding-required",
            policy_version=DemoSecurityPolicy.policy_version,
        )
    observations = payload.get("risk_observations")
    if not isinstance(observations, (list, tuple)):
        raise RiskFactsUnavailable(
            "subscription facts carry no observed risk signals",
            rule_id="subscription-observations-required",
            policy_version=DemoSecurityPolicy.policy_version,
        )
    signals = set(_ROUTINE_SIGNALS)
    for name in observations:
        signal = _OBSERVED_SIGNALS.get(name) if isinstance(name, str) else None
        if signal is None:
            raise RiskFactsUnavailable(
                "unknown observed risk signal",
                rule_id="subscription-signal-unknown",
                policy_version=DemoSecurityPolicy.policy_version,
            )
        signals.add(signal)
    if not signals <= set(checked_signals):
        raise RiskFactsUnavailable(
            "risk evidence does not cover every signal dimension",
            rule_id="risk-signal-coverage-required",
            policy_version=DemoSecurityPolicy.policy_version,
        )
    return DemoRiskEvidence(
        source=_SOURCE, source_version=source_version,
        evidence_ref="subscription-cancel", signals=frozenset(signals),
        checked_signals=frozenset(checked_signals),
    )


def _payload_dict(payload: object) -> dict | None:
    if isinstance(payload, Mapping):
        return deepcopy(dict(payload))
    dump = getattr(payload, "model_dump", None)
    return deepcopy(dump(mode="json")) if callable(dump) else None


class SubscriptionRuntime:
    """Platform-owned scenario-05 composition attached to one ``TransferRuntime``."""

    def __init__(self, runtime, *, clock: Callable[[], datetime] | None = None) -> None:
        self.runtime = runtime
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        # (task_id, parameters_ref) -> the frozen facts that reference was bound for.
        self._bindings: dict[tuple[str, str], dict] = {}
        # task_id -> (security context of the last write binding, its parameter reference)
        self._writes: dict[str, tuple[ExecutionSecurityContext, str]] = {}
        runtime.subscription = self
        runtime.authorize_cancel = self.authorize_bank_cancel
        register_module(runtime.harness.registry, self.ports_factory, self.clock)

    # ------------------------------------------------------------------- bindings

    def _remember(self, context: ExecutionSecurityContext, action_name: str,
                  parameters_ref: str, payload: object) -> None:
        """``on_bind`` sink: the module's per-call parameter store is not reachable here."""

        binding = _payload_dict(payload)
        if binding is None:
            return
        self._bindings[(context.task_id, parameters_ref)] = binding
        if action_name == CANCEL_TOOL:
            self._writes[context.task_id] = (context.model_copy(deep=True), parameters_ref)

    def binding(self, task_id: str, parameters_ref: str) -> dict | None:
        """The frozen facts one bound action reference stands for (for policy fixtures)."""

        return self._bindings.get((task_id, parameters_ref))

    def authorize_bank_cancel(self, trusted: TrustedContext, operation_id: UUID,
                              mandate_id: str) -> bool:
        """The bank's B30 authority: a live ALLOW claim from the shared executor.

        Called in the caller's thread right before the bank handler, so the reference
        bound for the current execution phase is the one that must hold the claim.
        """

        write = self._writes.get(trusted.task_id)
        if write is None:
            return False
        context, parameters_ref = write
        payload = self._bindings.get((trusted.task_id, parameters_ref))
        if payload is None or payload.get("mandate_id") != mandate_id:
            return False
        if (context.user_id, context.demo_round_id) != (trusted.user_id, trusted.demo_round_id):
            return False
        if context.operation_id is None or str(context.operation_id) != str(operation_id):
            return False
        if context.action_revision is None or context.confirmation_id is None:
            return False
        descriptor = ActionDescriptor(
            action_name=CANCEL_TOOL, parameters_ref=parameters_ref,
            resource_refs=[], phase=Phase.EXECUTION,
        )
        try:
            claim = self.runtime.confirmations.state.get_execution(context, descriptor)
        except Exception:
            return False
        return (
            claim is not None
            and claim.state == "processing"
            and claim.decision.decision == SecurityDecisionCode.ALLOW
        )

    def reserve_operation(self, trusted: TrustedContext, parameters: dict) -> UUID:
        """One B30 operation per frozen fact set, reused across start and resume."""

        digest = parameter_digest(parameters)
        existing = [
            item for item in self.runtime.application.list_task_operations(
                trusted.user_id, trusted.demo_round_id, trusted.task_id,
            )
            if item.action_name == CANCEL_TOOL and item.parameters_digest == digest
        ]
        if existing:
            return UUID(existing[-1].operation_id)
        reservation = self.runtime.application.reserve_operation(
            trusted.user_id, trusted.demo_round_id, trusted.task_id,
            str(uuid4()), CANCEL_TOOL, parameters,
        )
        return UUID(reservation.operation_id)

    # ---------------------------------------------------------------------- wiring

    def ports_factory(self, trusted: TrustedContext, trace) -> GatewaySubscriptionPorts:
        """Build the module's security-checked ports for exactly one task."""

        return GatewaySubscriptionPorts(
            self.runtime.gateway, self._gate(trace), self._context_factory(), trace,
            operation_reserver=self.reserve_operation, on_bind=self._remember,
        )

    def _context_factory(self):
        def security_context(trusted: TrustedContext, operation_id=None, action_revision=None):
            # The task's current confirmation and session verifications come from the
            # platform's own facts, exactly as the transfer path resolves them.
            return self.runtime._context(trusted, operation_id, action_revision)
        return security_context

    def _gate(self, trace) -> SecurityGate:
        pending_snapshots: dict[str, AuthorizationSnapshot] = {}

        def payload_of(context, action) -> dict:
            payload = self.binding(context.task_id, action.parameters_ref)
            if payload is None:
                raise SecurityError("DEPENDENCY_UNAVAILABLE")
            return payload

        def fields_of(context, action) -> list[DisplayField]:
            return [DisplayField.model_validate(item)
                    for item in payload_of(context, action)["display_fields"]]

        def prepare_confirmation(context, action) -> ConfirmationRecord:
            fields = fields_of(context, action)
            record = self.runtime.confirmations.create(context, action, fields)
            self.runtime.application.bind_ref(
                context.user_id, context.demo_round_id, context.task_id,
                "confirmation", record.confirmation_id,
            )
            self.runtime.facts.set_confirmation(record)
            ref = str(uuid4())
            trace.record("confirmation.changed", ConfirmationChangedPayload(
                confirmation_id=record.confirmation_id,
                confirmation_version=record.confirmation_version,
                action_revision=record.action_revision, decision=record.decision,
                display_ref=ref, operation_id=record.operation_id,
            ), "waiting", evidence=[field.model_dump(mode="json") for field in fields],
                evidence_id=ref, module="subscription")
            return record

        def prepare_verification(context, action, confirmation, risk):
            payload = payload_of(context, action)
            fields = [DisplayField.model_validate(item) for item in payload["display_fields"]]
            summary = None
            if risk == RiskLevel.LOW:
                # Ordinary own-account cancellation: button plus session-scoped code,
                # never the medium action-step-up face path.
                purpose, operation_id, action_revision = "basic_identity", None, None
            else:
                purpose = "action_step_up"
                operation_id, action_revision = context.operation_id, context.action_revision
                summary = VerificationSummary(
                    operation_id=context.operation_id,
                    action_revision=context.action_revision,
                    source_confirmation_id=confirmation.confirmation_id,
                    source_confirmation_version=confirmation.confirmation_version,
                    action_name=CANCEL_TOOL, amount_fen=payload["amount_fen"],
                    payee=None, display_fields=fields,
                )
            challenge = self.runtime.gateway.create_verification(
                self.runtime._trusted(context), purpose,
                operation_id, action_revision, summary,
            )
            trace.record("verification.changed", VerificationChangedPayload(
                challenge_id=challenge.challenge_id, method="code", result="pending",
                purpose=challenge.purpose, operation_id=challenge.operation_id,
                verification_id=None,
                consecutive_code_failures=challenge.consecutive_code_failures,
                expires_at=challenge.code_expires_at,
                reason_code="VERIFICATION_REQUIRED",
            ), "waiting", module="subscription")
            return challenge

        def resolve_verification(context, verification_id):
            if not self.runtime.application.has_ref(
                context.user_id, context.demo_round_id, context.task_id,
                "verification", verification_id,
            ):
                raise SecurityError("ACCESS_DENIED")
            try:
                return self.runtime.gateway.get_verification_record(
                    self.runtime._trusted(context), verification_id,
                )
            except ValueError as exc:
                raise SecurityError("ACCESS_DENIED") from exc

        def resolve_challenge(context, challenge_id):
            return self.runtime.gateway.get_verification(
                self.runtime._trusted(context), challenge_id,
            )

        def validate_summary(context, action, confirmation, summary) -> bool:
            payload = payload_of(context, action)
            fields = [DisplayField.model_validate(item) for item in payload["display_fields"]]
            return (
                summary.amount_fen == payload["amount_fen"]
                and summary.display_fields == fields
                and confirmation.display_fields == fields
            )

        def write_snapshot(context, confirmation, verifications, captured_at):
            ref = str(uuid4())
            pending_snapshots[ref] = AuthorizationSnapshot(
                user_id=context.user_id, session_id=context.session_id,
                demo_round_id=context.demo_round_id, task_id=context.task_id,
                operation_id=context.operation_id, action_revision=context.action_revision,
                confirmation=AuthorizationConfirmation(
                    confirmation_id=confirmation.confirmation_id,
                    version=confirmation.confirmation_version,
                    decision=confirmation.decision,
                    decided_at=confirmation.decided_at or captured_at,
                    display_fields=confirmation.display_fields,
                ),
                verifications=[AuthorizationVerification(
                    verification_id=item.verification_id, scope=item.scope,
                    methods=item.methods, verified_at=item.verified_at,
                    operation_id=item.operation_id, action_revision=item.action_revision,
                ) for item in verifications],
                release_authorization_id=None, captured_at=captured_at,
            )
            return ref

        def record_decision(decision: SecurityDecision) -> None:
            # A failing sink stops the gate itself (audit before any bank write). The
            # frozen action parameters are persisted under their own reference, which
            # the journal requires before a side-effect tool may start; RunTrace drops
            # references already written, so repeating a decision cannot collide.
            ref = decision.authorization_snapshot_ref
            snapshot = pending_snapshots.pop(ref, None) if ref else None
            parameters = self.binding(decision.task_id, decision.parameters_ref)
            extra = ({decision.parameters_ref: parameters} if parameters is not None else {})
            trace.record(
                "security.decided", SecurityDecidedPayload(decision=decision),
                "succeeded" if decision.decision == SecurityDecisionCode.ALLOW else "denied",
                evidence=snapshot, evidence_id=ref, snapshots=extra, module="security",
            )

        def in_scope(context, action, declaration) -> bool:
            if self.runtime.authorize_tool(context, action, declaration) is not True:
                return False
            return self.runtime._task_terminated(context) is False

        return SecurityGate(
            ToolRegistry(), self.runtime.confirmations,
            scope_authorizer=in_scope,
            task_state_resolver=self.runtime._task_terminated,
            risk_assessor=self.runtime.assess_risk,
            confirmation_preparer=prepare_confirmation,
            verification_preparer=prepare_verification,
            verification_resolver=resolve_verification,
            challenge_resolver=resolve_challenge,
            decision_sink=record_decision, snapshot_writer=write_snapshot,
            summary_validator=validate_summary,
        )


def register_subscription(runtime, clock: Callable[[], datetime] | None = None) -> SubscriptionRuntime:
    """Attach scenario 05 to a composed runtime (called from ``local_demo.build_runtime``)."""

    return SubscriptionRuntime(runtime, clock=clock)


def answer_confirmation(runtime, trusted: TrustedContext,
                        answer: ConfirmationAnswer) -> ConfirmationRecord:
    """Answer a subscription task's pending confirmation on its own action binding."""

    return runtime.answer_confirmation_for_module(trusted, answer, module="subscription")


def bind_verification(runtime, trusted: TrustedContext, verification_id: str) -> VerificationRecord:
    """Bind a passed verification to a subscription task (same durable facts)."""

    return runtime.bind_verification_for_module(trusted, verification_id, module="subscription")
