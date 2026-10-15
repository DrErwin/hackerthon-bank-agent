"""Concrete B01/B08 adapter: shared deterministic executor, never direct bank tables.

The platform supplies a real SecurityGate and its trusted context resolver. This
module supplies only two READ declarations and gateway handlers. No allow-all
policy or authentication flag is defined here. A gate instance is task scoped.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from time import monotonic
from uuid import uuid4

from app.contracts.common import ContractModel, ID, OperationLevel, Phase, SecurityDecisionCode, Timestamp
from app.contracts.bank import QueryFailure, QueryOk
from app.contracts.platform import CapabilityDefinition, TrustedContext
from app.contracts.tasks import ModuleError
from .service import BillsError


class AccountsReadInput(ContractModel):
    """Private B01 parameter envelope: identity comes only from trusted context."""


class TransactionsReadInput(ContractModel):
    """Private B08 invocation parameters, not a new public banking contract."""
    account_id: ID
    start_at: Timestamp
    end_at: Timestamp


PRIVATE_TOOLS = tuple(CapabilityDefinition(
    name="bills.bank." + name, input_schema_ref="bills.reads.TransactionsReadInput" if name == "list_transactions" else "bills.reads.AccountsReadInput",
    output_schema_ref="TransactionList" if name == "list_transactions" else "AccountList",
    required_permissions=["bills.read"], operation_level=OperationLevel.READ, side_effect=False,
    confirmation_policy="none", timeout_ms=10_000, retry_policy="read_only",
    handler_ref="bills.bank." + name,
) for name in ("list_accounts", "list_transactions"))


class GatewayBillsReads:
    def __init__(self, gateway, gate, context_factory, trace):
        from app.security import DeterministicExecutor
        self.gateway, self.gate = gateway, gate
        self.context_factory, self.trace = context_factory, trace
        self._parameters = {}
        for declaration in PRIVATE_TOOLS:
            if gate.registry.get(declaration.name) is not None:
                raise ValueError("BILLS_READ_TOOL_ALREADY_REGISTERED")
            gate.registry.register(declaration, self._accounts_handler if declaration.name.endswith("list_accounts")
                                   else self._transactions_handler)
        self.executor = DeterministicExecutor(gate, parameter_resolver=self.resolve,
            operation_lookup=self._no_write, result_observer=self._no_write)

    @staticmethod
    def _no_write(*args):
        raise ValueError("BILLS_READ_HAS_NO_FUNDS_OPERATION")

    @staticmethod
    def _trusted(context):
        return TrustedContext(user_id=context.user_id, session_id=context.session_id,
            demo_round_id=context.demo_round_id, task_id=context.task_id, run_id=context.run_id,
            parent_task_id=context.source_task_id)

    def resolve(self, context, action):
        stored = self._parameters.get(action.parameters_ref)
        if stored is None or stored[0] != context.model_dump(mode="json") or stored[1] != action.action_name:
            raise PermissionError("ACCESS_DENIED")
        return deepcopy(stored[2])

    def _accounts_handler(self, context, payload):
        AccountsReadInput.model_validate(payload)
        return self.gateway.list_accounts(self._trusted(context))

    def _transactions_handler(self, context, payload):
        request = TransactionsReadInput.model_validate(payload)
        return self.gateway.list_transactions(self._trusted(context), request.account_id,
            request.start_at, request.end_at)

    def _read(self, trusted, action_name, parameters):
        from app.contracts.security import ActionDescriptor, ExecutionSecurityContext
        from app.contracts.audit import ToolStartedPayload, ToolFinishedPayload
        context = self.context_factory(trusted)
        if not isinstance(context, ExecutionSecurityContext) or self._trusted(context) != trusted:
            raise BillsError("ACCESS_DENIED", source="security")
        if context.operation_id is not None or context.action_revision is not None:
            raise BillsError("SECURITY_REJECTED", source="security")
        ref, call_id = str(uuid4()), str(uuid4())
        self._parameters[ref] = (context.model_dump(mode="json"), action_name, deepcopy(parameters))
        action = ActionDescriptor(action_name=action_name, parameters_ref=ref, resource_refs=[], phase=Phase.ADMISSION)
        started, event = monotonic(), None
        try:
            decision = self.gate.check_action(context, action)
            if decision.decision != SecurityDecisionCode.ALLOW:
                raise BillsError("SECURITY_REJECTED", source="security")
            event = self.trace.record("tool.started", ToolStartedPayload(tool_call_id=call_id,
                tool_name=action_name, tool_version="0.4.0-l01", arguments_ref=ref,
                decision_id=decision.decision_id, operation_id=None), "started",
                evidence={"parameters": parameters}, evidence_id=ref, module="bills")
            outcome = self.executor.execute(context, action)
            if (not outcome.executed or outcome.state != "completed" or outcome.decision is None
                    or outcome.decision.decision != SecurityDecisionCode.ALLOW):
                raise BillsError("SECURITY_REJECTED", source="security")
            if not isinstance(outcome.result, (QueryOk, QueryFailure)):
                raise BillsError("INCOMPLETE_FACTS", source="bank")
            result_ref = str(uuid4())
            failed = isinstance(outcome.result, QueryFailure)
            error = ModuleError(code="BILLS_BANK_QUERY_FAILED", source="bank", field=None,
                reason="银行查询未返回完整事实", upstream_code=None) if failed else None
            # Shared AuditJournal redacts successful bank facts. Untrusted error
            # details never enter audit; an error result is NOT logged as success.
            evidence = ({"kind": "error", "code": "BILLS_BANK_QUERY_FAILED"} if failed
                        else outcome.result.model_dump(mode="json"))
            self.trace.record("tool.finished", ToolFinishedPayload(tool_call_id=call_id, operation_id=None,
                result_ref=result_ref, duration_ms=int((monotonic() - started) * 1000), error=error),
                "failed" if failed else "succeeded", evidence=evidence, evidence_id=result_ref,
                module="bills", parent_span_id=event.span_id)
            return outcome.result
        except Exception:
            if event is not None:
                self.trace.record("tool.finished", ToolFinishedPayload(tool_call_id=call_id, operation_id=None,
                    result_ref=None, duration_ms=int((monotonic() - started) * 1000),
                    error=ModuleError(code="BILLS_READ_FAILED", source="bills", field=None,
                        reason="账单读取未完成", upstream_code=None)), "failed", module="bills",
                    parent_span_id=event.span_id)
            raise
        finally:
            self._parameters.pop(ref, None)

    def accounts(self, context):
        return self._read(context, "bills.bank.list_accounts", {})

    def transactions(self, context, account_id, start_at, end_at):
        return self._read(context, "bills.bank.list_transactions", {
            "account_id": account_id, "start_at": start_at.isoformat(), "end_at": end_at.isoformat()})
