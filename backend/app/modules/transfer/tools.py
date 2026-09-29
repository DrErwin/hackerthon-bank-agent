"""Controlled bank tools and immutable action parameters for ordinary transfer."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from app.contracts.bank import OperationResult, PayeeInput, QueryFailure
from app.contracts.common import Phase
from app.contracts.platform import TrustedContext
from app.contracts.security import ActionDescriptor, ExecutionSecurityContext, SecurityDecision
from app.security import DeterministicExecutor, ExecutionOutcome, OperationObservation, SecurityGate
from app.services.bank_gateway.gateway import BankGateway
from app.storage.database import connect, transaction

from .manifest import PRIVATE_TOOLS


_PAYEE = TypeAdapter(PayeeInput)
SecurityContextFactory = Callable[[TrustedContext, UUID | None, int | None], ExecutionSecurityContext]


@dataclass(frozen=True)
class TransferAction:
    operation_id: UUID
    action_revision: int
    parameters_ref: str

    def descriptor(self, phase: Phase) -> ActionDescriptor:
        return ActionDescriptor(
            action_name="bank.submit_transfer", parameters_ref=self.parameters_ref,
            resource_refs=[], phase=phase,
        )


class TransferSnapshots:
    """Never edits a snapshot once a confirmation or tool call refers to it."""

    def __init__(self, path: Path):
        self.path = path
        with transaction(path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS transfer_snapshots (
                    ref TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    action_name TEXT NOT NULL,
                    operation_id TEXT,
                    action_revision INTEGER,
                    parameters_json TEXT NOT NULL
                )
            """)

    def save(
        self, trusted: TrustedContext, action_name: str, parameters: dict,
        operation_id: UUID | None = None, action_revision: int | None = None,
    ) -> str:
        ref = str(uuid4())
        with transaction(self.path) as connection:
            connection.execute(
                "INSERT INTO transfer_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ref, trusted.user_id, trusted.demo_round_id, trusted.task_id,
                 action_name, str(operation_id) if operation_id else None,
                 action_revision, json.dumps(parameters, ensure_ascii=False, sort_keys=True)),
            )
        return ref

    def resolve(self, context: ExecutionSecurityContext, action: ActionDescriptor) -> dict:
        connection = connect(self.path)
        try:
            row = connection.execute(
                "SELECT * FROM transfer_snapshots WHERE ref = ?", (action.parameters_ref,),
            ).fetchone()
            if row is None or (
                row["user_id"], row["demo_round_id"], row["task_id"], row["action_name"],
                row["operation_id"], row["action_revision"],
            ) != (
                context.user_id, context.demo_round_id, context.task_id, action.action_name,
                str(context.operation_id) if context.operation_id else None,
                context.action_revision,
            ):
                raise ValueError("ACCESS_DENIED")
            return json.loads(row["parameters_json"])
        finally:
            connection.close()


class GatewayTransferTools:
    """Only exposes registered, security-checked calls to the transfer graph."""

    def __init__(
        self, gateway: BankGateway, gate: SecurityGate, snapshots: TransferSnapshots,
        security_context: SecurityContextFactory,
    ):
        self.gateway = gateway
        self.gate = gate
        self.snapshots = snapshots
        self.security_context = security_context
        handlers = {
            "bank.list_accounts": lambda trusted, _payload: gateway.list_accounts(trusted),
            "bank.list_payees": lambda trusted, payload: gateway.list_payees(trusted, payload),
            "bank.verify_payee": lambda trusted, payload: gateway.verify_payee(
                trusted, _PAYEE.validate_python(payload["payee"]),
            ),
            "bank.precheck_transfer": lambda trusted, payload: gateway.precheck_transfer(
                trusted, payload["payer_account_id"],
                _PAYEE.validate_python(payload["payee"]), payload["amount_fen"],
            ),
            "bank.submit_transfer": lambda trusted, payload: gateway.submit_transfer(
                trusted, UUID(payload["operation_id"]), payload["payer_account_id"],
                _PAYEE.validate_python(payload["payee"]), payload["amount_fen"],
            ),
        }
        for declaration in PRIVATE_TOOLS:
            handler = handlers[declaration.name]
            gate.registry.register(
                declaration,
                lambda context, payload, handler=handler: handler(
                    self._trusted(context), payload,
                ),
            )
        self.executor = DeterministicExecutor(
            gate, parameter_resolver=snapshots.resolve,
            operation_lookup=self._lookup_operation,
            result_observer=self._observe_result,
        )

    @staticmethod
    def _trusted(context: ExecutionSecurityContext) -> TrustedContext:
        return TrustedContext(
            user_id=context.user_id, session_id=context.session_id,
            task_id=context.task_id, run_id=context.run_id,
            parent_task_id=context.source_task_id, demo_round_id=context.demo_round_id,
        )

    @staticmethod
    def _observe_result(result: object) -> OperationObservation:
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

    def _lookup_operation(
        self, context: ExecutionSecurityContext, _action: ActionDescriptor,
    ) -> OperationObservation:
        response = self.gateway.get_operation(self._trusted(context), context.operation_id)
        if isinstance(response, QueryFailure):
            raise ValueError(response.error.code)
        if response.lookup == "not_found":
            return OperationObservation(context.operation_id, "not_found", None, None)
        return self._observe_result(response.operation)

    def read(self, trusted: TrustedContext, action_name: str, parameters: dict) -> ExecutionOutcome:
        if action_name not in {item.name for item in PRIVATE_TOOLS if not item.side_effect}:
            raise ValueError("read tool is not registered")
        ref = self.snapshots.save(trusted, action_name, parameters)
        context = self.security_context(trusted, None, None)
        descriptor = ActionDescriptor(
            action_name=action_name, parameters_ref=ref, resource_refs=[], phase=Phase.ADMISSION,
        )
        return self.executor.execute(context, descriptor)

    def prepare_transfer(
        self, trusted: TrustedContext, operation_id: UUID, action_revision: int,
        payer_account_id: str, payee: PayeeInput, amount_fen: int,
    ) -> TransferAction:
        ref = self.snapshots.save(
            trusted, "bank.submit_transfer",
            {"operation_id": str(operation_id), "payer_account_id": payer_account_id,
             "payee": payee.model_dump(mode="json"), "amount_fen": amount_fen},
            operation_id, action_revision,
        )
        return TransferAction(operation_id, action_revision, ref)

    def check(self, trusted: TrustedContext, action: TransferAction) -> SecurityDecision:
        context = self.security_context(trusted, action.operation_id, action.action_revision)
        return self.gate.check_action(context, action.descriptor(Phase.ADMISSION))

    def execute(self, trusted: TrustedContext, action: TransferAction) -> ExecutionOutcome:
        context = self.security_context(trusted, action.operation_id, action.action_revision)
        return self.executor.execute(context, action.descriptor(Phase.EXECUTION))

    def observe(self, trusted: TrustedContext, action: TransferAction) -> ExecutionOutcome:
        """Look up an already claimed operation; this path can never create a claim."""
        context = self.security_context(trusted, action.operation_id, action.action_revision)
        descriptor = action.descriptor(Phase.EXECUTION)
        claim = self.gate.confirmations.state.get_execution(context, descriptor)
        if claim is None:
            return ExecutionOutcome(None, False, False, "unknown", None, None)
        return self.executor.execute(context, descriptor)
