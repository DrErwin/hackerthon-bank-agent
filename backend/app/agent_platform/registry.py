"""Explicit public capability registry; private bank tools never enter the model catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol

from langgraph.checkpoint.base import BaseCheckpointSaver

from app.contracts.platform import CapabilityDefinition, ModuleManifest, StartTransferInput, TrustedContext
from app.contracts.tasks import ModuleResult, TransferTaskView

if TYPE_CHECKING:
    from .harness import RunTrace


class TransferEntry(Protocol):
    def start(self, trusted: TrustedContext, request: StartTransferInput, *,
              thread_id: str | None = None) -> ModuleResult[TransferTaskView]: ...

    def resume(self, trusted: TrustedContext, response: dict, *,
               thread_id: str | None = None) -> ModuleResult[TransferTaskView]: ...

    def recover_session(self, trusted: TrustedContext, *, source_session_id: str,
                        thread_id: str | None = None) -> ModuleResult[TransferTaskView]: ...

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

    def get(self, name: str) -> RegisteredCapability:
        try:
            return self._entries[name]
        except KeyError as exc:
            raise ValueError("CAPABILITY_NOT_REGISTERED") from exc

    def public_catalog(self) -> list[dict[str, str]]:
        return [
            {"name": name, "description": entry.manifest.description,
             "input_schema_ref": "StartTransferInput"}
            for name, entry in self._entries.items()
        ]
