"""Task-scoped manual payee material kept outside ordinary checkpoints."""

from dataclasses import dataclass
from typing import Callable

from app.contracts.bank import ManualPayee, PayeeDisplay, PayeeVerification, QueryFailure, QueryOk
from app.contracts.common import Phase
from app.contracts.platform import TrustedContext
from app.contracts.security import ActionDescriptor, ExecutionSecurityContext
from app.modules.transfer.tools import TransferSnapshots
from app.services.bank_gateway.gateway import BankGateway
from app.storage.database import transaction

from .harness import _task_lock


@dataclass(frozen=True)
class ControlledPayeeReference:
    reference: str
    display: PayeeDisplay


class ControlledPayeeReferences:
    """Only the trusted backend may register and resolve these opaque references."""

    action_name = "transfer.controlled_payee"

    def __init__(self, snapshots: TransferSnapshots, gateway: BankGateway,
                 check_task: Callable[[TrustedContext], object]):
        self.snapshots, self.gateway, self.check_task = snapshots, gateway, check_task

    def clear(self, trusted: TrustedContext) -> None:
        """Retire this task's material before changing or abandoning manual input."""
        with _task_lock(self.snapshots.path, trusted.task_id):
            self.check_task(trusted)
            with transaction(self.snapshots.path) as connection:
                connection.execute("""DELETE FROM transfer_snapshots
                    WHERE action_name = ? AND user_id = ? AND task_id = ? AND demo_round_id = ?""",
                    (self.action_name, trusted.user_id, trusted.task_id, trusted.demo_round_id))

    def register(self, trusted: TrustedContext, payee: ManualPayee,
                 payee_revision: int) -> ControlledPayeeReference | QueryOk[PayeeVerification] | QueryFailure:
        # Validate the trusted version before retiring any existing material.
        self._context(trusted, payee_revision)
        with _task_lock(self.snapshots.path, trusted.task_id):
            self.clear(trusted)
            try:
                verified = self.gateway.verify_payee(trusted, payee)
                if isinstance(verified, QueryFailure) or not verified.data.matched:
                    return verified
                # Recheck session/round after the bank call and before persisting.
                self.check_task(trusted)
                reference = self.snapshots.save(
                    trusted, self.action_name, {"payee": payee.model_dump(mode="json")},
                    action_revision=payee_revision,
                )
            except Exception:
                # This dedicated secret boundary must not expose upstream error text.
                raise RuntimeError("PAYEE_REGISTRATION_FAILED") from None
            return ControlledPayeeReference(reference, verified.data.payee)

    @staticmethod
    def _context(trusted: TrustedContext, payee_revision: int) -> ExecutionSecurityContext:
        return ExecutionSecurityContext(
            **trusted.model_dump(exclude={"parent_task_id"}),
            source_task_id=trusted.parent_task_id, operation_id=None,
            action_revision=payee_revision, confirmation_id=None, confirmation_version=None,
            verification_ids=[], release_authorization_id=None,
        )

    def resolve(self, trusted: TrustedContext, reference: str, payee_revision: int) -> ManualPayee:
        """Read only inside deterministic bank preparation, never into model state."""
        with _task_lock(self.snapshots.path, trusted.task_id):
            self.check_task(trusted)
            parameters = self.snapshots.resolve(
                self._context(trusted, payee_revision),
                ActionDescriptor(action_name=self.action_name, parameters_ref=reference,
                                 resource_refs=[], phase=Phase.ADMISSION),
            )
            return ManualPayee.model_validate(parameters["payee"])
