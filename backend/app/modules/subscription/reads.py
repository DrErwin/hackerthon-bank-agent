"""Concrete B01/B08/B29/B30 adapters behind the shared security gate and executor.

The platform supplies a real ``SecurityGate`` and its trusted context resolver; this
module supplies only the private declarations and the gateway handlers. There is no
allow-all policy and no authentication flag here, and a gate instance, its executor and
its parameter registry are task scoped.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from time import monotonic
from typing import Callable, Literal
from uuid import UUID, uuid4

from app.contracts.common import ContractModel, ID, OperationLevel, Phase, SecurityDecisionCode, Timestamp
from app.contracts.platform import CapabilityDefinition, TrustedContext
from app.contracts.tasks import ModuleError
from .ports import CancellationPlan, ExecutionOutcome, GateAnswer


class AccountsReadInput(ContractModel):
    """Private B01 parameter envelope: identity comes only from the trusted context."""


class MandatesReadInput(ContractModel):
    """Private B29 parameters, not a public banking contract."""

    account_id: ID | None = None
    status: Literal["active", "cancelled"] | None = None


class TransactionsReadInput(ContractModel):
    """Private B08 invocation parameters, not a new public banking contract."""

    account_id: ID
    start_at: Timestamp
    end_at: Timestamp


class CancelWriteInput(ContractModel):
    """Private B30 parameters: the frozen facts the user confirmed, nothing inferred."""

    operation_id: UUID
    mandate_id: ID
    account_id: ID
    account_masked: str
    merchant_id: ID
    merchant_name: str
    service_name: str
    amount_fen: int
    cycle: Literal["monthly", "yearly"]
    effective_stop_at: Timestamp
    risk_observations: list[str] = []
    display_fields: list[dict] = []


PRIVATE_TOOLS = (
    CapabilityDefinition(
        name="subscription.bank.list_accounts",
        input_schema_ref="subscription.reads.AccountsReadInput", output_schema_ref="AccountList",
        required_permissions=["subscription.read"], operation_level=OperationLevel.READ,
        side_effect=False, confirmation_policy="none", timeout_ms=10_000, retry_policy="read_only",
        handler_ref="subscription.bank.list_accounts",
    ),
    CapabilityDefinition(
        name="subscription.bank.list_subscriptions",
        input_schema_ref="subscription.reads.MandatesReadInput", output_schema_ref="SubscriptionMandateList",
        required_permissions=["subscription.read"], operation_level=OperationLevel.READ,
        side_effect=False, confirmation_policy="none", timeout_ms=10_000, retry_policy="read_only",
        handler_ref="subscription.bank.list_subscriptions",
    ),
    CapabilityDefinition(
        name="subscription.bank.list_transactions",
        input_schema_ref="subscription.reads.TransactionsReadInput", output_schema_ref="TransactionList",
        required_permissions=["subscription.read"], operation_level=OperationLevel.READ,
        side_effect=False, confirmation_policy="none", timeout_ms=10_000, retry_policy="read_only",
        handler_ref="subscription.bank.list_transactions",
    ),
    CapabilityDefinition(
        name="subscription.bank.cancel_subscription",
        input_schema_ref="subscription.reads.CancelWriteInput",
        output_schema_ref="OperationResult[SubscriptionCancelReceipt]",
        required_permissions=["subscription.cancel"], operation_level=OperationLevel.MODIFY,
        side_effect=True, confirmation_policy="per_action", timeout_ms=8_000, retry_policy="none",
        handler_ref="subscription.bank.cancel_subscription",
    ),
)


def action_revision(payload: dict) -> int:
    """A stable revision of the frozen facts: changing the target invalidates old answers."""

    digest = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) or 1


def parameters_ref(context, action_name: str, payload: dict) -> str:
    """A stable, task-scoped parameter reference.

    A ``per_action`` confirmation freezes the reference of the action it approved, so
    rebuilding the same frozen facts must yield the same reference — only the phase may
    differ between the admission check and the execution claim.
    """

    digest = sha256(json.dumps(
        {"task_id": context.task_id, "action": action_name, "payload": payload},
        sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return f"sub-ref-{digest[:24]}"


class GatewaySubscriptionPorts:
    """Task-scoped implementation of ``ports.SubscriptionPorts``."""

    def __init__(self, gateway, gate, context_factory, trace,
                 operation_reserver: Callable | None = None,
                 on_bind: Callable | None = None):
        from app.security import DeterministicExecutor
        self.gateway, self.gate, self.context_factory, self.trace = gateway, gate, context_factory, trace
        self.operation_reserver = operation_reserver
        # The platform keeps the bound facts reachable for its risk resolver; this
        # module's parameter store is in memory and cleared when one call ends.
        self.on_bind = on_bind
        self._parameters: dict[str, tuple] = {}
        handlers = {
            "subscription.bank.list_accounts": self._accounts_handler,
            "subscription.bank.list_subscriptions": self._mandates_handler,
            "subscription.bank.list_transactions": self._transactions_handler,
            "subscription.bank.cancel_subscription": self._cancel_handler,
        }
        for declaration in PRIVATE_TOOLS:
            if gate.registry.get(declaration.name) is not None:
                raise ValueError("SUBSCRIPTION_TOOL_ALREADY_REGISTERED")
            gate.registry.register(declaration, handlers[declaration.name])
        self.executor = DeterministicExecutor(
            gate, parameter_resolver=self.resolve,
            operation_lookup=self._lookup_operation, result_observer=self._observe_result,
        )

    # ------------------------------------------------------------------ plumbing

    @staticmethod
    def _trusted(context) -> TrustedContext:
        return TrustedContext(
            user_id=context.user_id, session_id=context.session_id,
            demo_round_id=context.demo_round_id, task_id=context.task_id, run_id=context.run_id,
            parent_task_id=context.source_task_id,
        )

    def resolve(self, context, action):
        stored = self._parameters.get(action.parameters_ref)
        if stored is None or stored[0] != context.model_dump(mode="json") or stored[1] != action.action_name:
            raise PermissionError("ACCESS_DENIED")
        return deepcopy(stored[2])

    def _bind(self, context, action_name: str, parameters: dict, *,
              phase=Phase.ADMISSION) -> tuple[str, object]:
        ref = parameters_ref(context, action_name, parameters)
        self._parameters[ref] = (context.model_dump(mode="json"), action_name, deepcopy(parameters))
        if self.on_bind is not None:
            self.on_bind(context, action_name, ref, parameters)
        from app.contracts.security import ActionDescriptor
        return ref, ActionDescriptor(action_name=action_name, parameters_ref=ref,
                                     resource_refs=[], phase=phase)

    @staticmethod
    def _observe_result(result: object):
        from app.contracts.bank import OperationResult, QueryFailure
        from app.security import OperationObservation
        if isinstance(result, QueryFailure):
            raise ValueError(result.error.code)
        if not isinstance(result, OperationResult):
            raise ValueError("unexpected bank result")
        return OperationObservation(
            operation_id=result.operation_id,
            state="processing" if result.operation_status == "processing" else "completed",
            result=result,
            result_ref=None if result.operation_status == "processing" else str(result.operation_id),
        )

    def _lookup_operation(self, context, _action):
        from app.contracts.bank import QueryFailure
        from app.security import OperationObservation
        response = self.gateway.get_operation(self._trusted(context), context.operation_id)
        if isinstance(response, QueryFailure):
            raise ValueError(response.error.code)
        if response.lookup == "not_found":
            return OperationObservation(context.operation_id, "not_found", None, None)
        return self._observe_result(response.operation)

    # ----------------------------------------------------------------- read tools

    def _read(self, trusted: TrustedContext, action_name: str, parameters: dict):
        from app.contracts.audit import ToolFinishedPayload, ToolStartedPayload
        from app.contracts.bank import QueryFailure, QueryOk
        from app.contracts.security import ExecutionSecurityContext
        context = self.context_factory(trusted, None, None)
        if not isinstance(context, ExecutionSecurityContext) or self._trusted(context) != trusted:
            raise ValueError("ACCESS_DENIED")
        if context.operation_id is not None or context.action_revision is not None:
            raise ValueError("SECURITY_REJECTED")
        ref, action = self._bind(context, action_name, parameters)
        # The audit evidence key must be unique per event: the parameter reference is
        # deterministic now, so repeating the same read would collide on it.
        call_id, call_ref, started, event = str(uuid4()), str(uuid4()), monotonic(), None
        try:
            decision = self.gate.check_action(context, action)
            if decision.decision != SecurityDecisionCode.ALLOW:
                raise ValueError("SECURITY_REJECTED")
            event = self.trace.record("tool.started", ToolStartedPayload(
                tool_call_id=call_id, tool_name=action_name, tool_version="0.4.0",
                arguments_ref=ref, decision_id=decision.decision_id, operation_id=None),
                "started", evidence={"parameters": parameters}, evidence_id=call_ref,
                module="subscription")
            outcome = self.executor.execute(context, action)
            if (not outcome.executed or outcome.state != "completed" or outcome.decision is None
                    or outcome.decision.decision != SecurityDecisionCode.ALLOW):
                raise ValueError("SECURITY_REJECTED")
            if not isinstance(outcome.result, (QueryOk, QueryFailure)):
                raise ValueError("INCOMPLETE_FACTS")
            failed = isinstance(outcome.result, QueryFailure)
            result_ref = str(uuid4())
            self.trace.record("tool.finished", ToolFinishedPayload(
                tool_call_id=call_id, operation_id=None, result_ref=result_ref,
                duration_ms=int((monotonic() - started) * 1000),
                error=ModuleError(code="SUBSCRIPTION_BANK_QUERY_FAILED", source="bank", field=None,
                                  reason="银行查询未返回完整事实", upstream_code=None) if failed else None),
                "failed" if failed else "succeeded",
                evidence=({"kind": "error", "code": "SUBSCRIPTION_BANK_QUERY_FAILED"} if failed
                          else outcome.result.model_dump(mode="json")),
                evidence_id=result_ref, module="subscription", parent_span_id=event.span_id)
            return outcome.result
        except Exception:
            if event is not None:
                self.trace.record("tool.finished", ToolFinishedPayload(
                    tool_call_id=call_id, operation_id=None, result_ref=None,
                    duration_ms=int((monotonic() - started) * 1000),
                    error=ModuleError(code="SUBSCRIPTION_READ_FAILED", source="subscription", field=None,
                                      reason="订阅读取未完成", upstream_code=None)),
                    "failed", module="subscription", parent_span_id=event.span_id)
            raise
        finally:
            self._parameters.pop(ref, None)

    def _accounts_handler(self, context, payload):
        AccountsReadInput.model_validate(payload)
        return self.gateway.list_accounts(self._trusted(context))

    def _mandates_handler(self, context, payload):
        request = MandatesReadInput.model_validate(payload)
        return self.gateway.list_subscriptions(self._trusted(context), request.account_id, request.status)

    def _transactions_handler(self, context, payload):
        request = TransactionsReadInput.model_validate(payload)
        return self.gateway.list_transactions(self._trusted(context), request.account_id,
                                              request.start_at, request.end_at)

    def _cancel_handler(self, context, payload):
        request = CancelWriteInput.model_validate(payload)
        return self.gateway.cancel_subscription(self._trusted(context), request.operation_id,
                                                request.mandate_id)

    def accounts(self, context: TrustedContext):
        return self._read(context, "subscription.bank.list_accounts", {})

    def mandates(self, context: TrustedContext, account_id: str | None = None, status: str | None = None):
        return self._read(context, "subscription.bank.list_subscriptions",
                          {"account_id": account_id, "status": status})

    def transactions(self, context: TrustedContext, account_id: str, start_at, end_at):
        return self._read(context, "subscription.bank.list_transactions", {
            "account_id": account_id, "start_at": start_at.isoformat(), "end_at": end_at.isoformat()})

    # ----------------------------------------------------------------- write path

    def _reserve(self, trusted: TrustedContext, plan: CancellationPlan) -> UUID:
        if self.operation_reserver is None:
            raise ValueError("SUBSCRIPTION_OPERATION_RESERVER_REQUIRED")
        return self.operation_reserver(trusted, plan.payload())

    def _write_context(self, trusted: TrustedContext, plan: CancellationPlan, *, phase):
        from app.contracts.security import ExecutionSecurityContext
        operation_id = self._reserve(trusted, plan)
        payload = {**plan.payload(), "operation_id": str(operation_id)}
        revision = action_revision(payload)
        # The platform resolves the task's answered confirmation and its session-scoped
        # verifications here; without them the gate can never see the user's own button.
        context = self.context_factory(trusted, operation_id, revision)
        if (not isinstance(context, ExecutionSecurityContext) or self._trusted(context) != trusted
                or context.operation_id != operation_id or context.action_revision != revision):
            raise ValueError("ACCESS_DENIED")
        ref, action = self._bind(context, "subscription.bank.cancel_subscription", payload, phase=phase)
        return context, action

    def check_cancel(self, trusted: TrustedContext, plan: CancellationPlan) -> GateAnswer:
        context, action = self._write_context(trusted, plan, phase=Phase.ADMISSION)
        decision = self.gate.check_action(context, action)
        return GateAnswer(
            decision=decision.decision, interaction=decision.interaction,
            reason_code=decision.reason_codes[0] if decision.reason_codes else None,
            operation_id=str(context.operation_id),
        )

    def _observed(self, context, outcome, parent_span_id: str | None = None) -> None:
        from app.contracts.audit import BankObservedPayload
        from app.contracts.bank import OperationResult
        result = outcome.result
        if isinstance(result, OperationResult):
            ref = str(uuid4())
            self.trace.record("bank.observed", BankObservedPayload(
                operation_id=context.operation_id, lookup="found",
                operation_status=result.operation_status, transaction_id=None,
                receipt_ref=ref, error=None), "succeeded",
                evidence=result.model_dump(mode="json"), evidence_id=ref,
                module="bank_gateway", parent_span_id=parent_span_id)
        elif outcome.reused or outcome.state in {"unknown", "processing"}:
            self.trace.record("bank.observed", BankObservedPayload(
                operation_id=context.operation_id, lookup="error", operation_status=None,
                transaction_id=None, receipt_ref=None, error=None), "unknown",
                module="bank_gateway", parent_span_id=parent_span_id)

    def execute_cancel(self, trusted: TrustedContext, plan: CancellationPlan) -> ExecutionOutcome:
        from app.contracts.audit import ToolFinishedPayload, ToolStartedPayload
        from app.contracts.bank import OperationResult
        # The shared executor only claims a funds/state-changing handler in the
        # execution phase; the reference stays identical to the approved confirmation.
        context, action = self._write_context(trusted, plan, phase=Phase.EXECUTION)
        decision = self.gate.check_action(context, action)
        call_id, call_ref, started, event = str(uuid4()), str(uuid4()), monotonic(), None
        try:
            event = self.trace.record("tool.started", ToolStartedPayload(
                tool_call_id=call_id, tool_name="subscription.bank.cancel_subscription",
                tool_version="0.4.0", arguments_ref=action.parameters_ref,
                decision_id=decision.decision_id, operation_id=context.operation_id),
                "started", evidence={"mandate_id": plan.mandate_id, "amount_fen": plan.amount_fen},
                evidence_id=call_ref, module="subscription")
            outcome = self.executor.execute(context, action)
            self._observed(context, outcome, event.span_id)
            denied = outcome.decision is not None and outcome.decision.decision != SecurityDecisionCode.ALLOW
            self.trace.record("tool.finished", ToolFinishedPayload(
                tool_call_id=call_id, operation_id=context.operation_id, result_ref=None,
                duration_ms=int((monotonic() - started) * 1000),
                error=ModuleError(code=outcome.decision.reason_codes[0], source="security", field=None,
                                  reason="安全检查未放行", upstream_code=None) if denied else None),
                "denied" if denied else ("succeeded" if isinstance(outcome.result, OperationResult) else "unknown"),
                module="subscription", parent_span_id=event.span_id)
            answer = (GateAnswer(decision=outcome.decision.decision, interaction=outcome.decision.interaction,
                                 reason_code=outcome.decision.reason_codes[0]
                                 if outcome.decision.reason_codes else None,
                                 operation_id=str(context.operation_id))
                      if outcome.decision is not None else None)
            return ExecutionOutcome(executed=outcome.executed, state=outcome.state, result=outcome.result,
                                    decision=answer, operation_id=str(context.operation_id))
        except Exception as error:
            if event is not None:
                self.trace.record("tool.finished", ToolFinishedPayload(
                    tool_call_id=call_id, operation_id=context.operation_id, result_ref=None,
                    duration_ms=int((monotonic() - started) * 1000),
                    error=ModuleError(code="TOOL_FAILED", source="platform", field=None,
                                      reason=type(error).__name__, upstream_code=None)),
                    "failed", module="subscription", parent_span_id=event.span_id)
            raise
        finally:
            self._parameters.pop(action.parameters_ref, None)
