"""Explicit public capability registry; private bank tools never enter the model catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol

from langgraph.checkpoint.base import BaseCheckpointSaver

from app.contracts.platform import CapabilityDefinition, ModuleManifest, StartTransferInput, TrustedContext
from app.contracts.tasks import ModuleResult

if TYPE_CHECKING:
    from .harness import RunTrace


class TransferEntry(Protocol):
    # A registered module answers with its own displayable result (§6.5); only the
    # transfer module's payload happens to be the transfer view (Issue #122).
    def start(self, trusted: TrustedContext, request: StartTransferInput, *,
              thread_id: str | None = None) -> ModuleResult: ...

    def resume(self, trusted: TrustedContext, response: dict, *,
               thread_id: str | None = None) -> ModuleResult: ...

    def recover_session(self, trusted: TrustedContext, *, source_session_id: str,
                        thread_id: str | None = None) -> ModuleResult: ...

    def checkpoint_context(self, trusted: TrustedContext, *,
                           thread_id: str | None = None) -> TrustedContext | None: ...


TransferFactory = Callable[[TrustedContext, BaseCheckpointSaver, "RunTrace"], TransferEntry]


@dataclass(frozen=True)
class RegisteredCapability:
    manifest: ModuleManifest
    definition: CapabilityDefinition
    factory: TransferFactory


class CapabilityRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, RegisteredCapability] = {}

    def register_transfer(self, manifest: ModuleManifest, factory: TransferFactory) -> None:
        public = [item for item in manifest.capabilities if item.name == "transfer.start_transfer"]
        if manifest.module_name != "transfer" or len(public) != 1:
            raise ValueError("TRANSFER_CAPABILITY_NOT_DECLARED")
        if public[0].side_effect or public[0].confirmation_policy != "none":
            raise ValueError("INVALID_PUBLIC_CAPABILITY")
        if public[0].name in self._entries:
            raise ValueError("DUPLICATE_CAPABILITY")
        self._entries[public[0].name] = RegisteredCapability(manifest, public[0], factory)

    def register_module(self, manifest: ModuleManifest, factory: TransferFactory) -> None:
        """Register any second business module; names stay module-prefixed and unique."""
        if not manifest.capabilities:
            raise ValueError("NO_PUBLIC_CAPABILITY")
        declared = [definition.name for definition in manifest.capabilities]
        if len(set(declared)) != len(declared):
            # §6.9: capability names are unique — also inside one manifest.
            raise ValueError("DUPLICATE_CAPABILITY")
        for definition in manifest.capabilities:
            if not definition.name.startswith(f"{manifest.module_name}."):
                raise ValueError("CAPABILITY_NOT_IN_MODULE")
            if definition.name in self._entries:
                raise ValueError("DUPLICATE_CAPABILITY")
        for definition in manifest.capabilities:
            self._entries[definition.name] = RegisteredCapability(manifest, definition, factory)

    def get(self, name: str) -> RegisteredCapability:
        try:
            return self._entries[name]
        except KeyError as exc:
            raise ValueError("CAPABILITY_NOT_REGISTERED") from exc

    def public_catalog(self) -> list[dict[str, str]]:
        return [
            {"name": name, "description": entry.manifest.description,
             "input_schema_ref": entry.definition.input_schema_ref}
            for name, entry in self._entries.items()
        ]
