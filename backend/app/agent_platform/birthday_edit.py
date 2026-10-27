"""Ticket v05-birthday-platform-dependencies/03: the controlled birthday handoff.

One G3 publication seam, two duties (spec §4.3 and g3-reconciliation):

A. The dedicated backend entry for a birthday card that is waiting for a
   confirmation or a verification. It accepts only the trusted context and the
   backend-published edit option of the *current* F10 interaction; user identity,
   target, parameters and versions come from the original task. The frozen order
   is: reserve the edit_ref and the exact published source through the task CAS →
   security accepts the retirement → the bank retires the old attempt's
   challenges → security seals the retirement with its audit → Cross prepares one
   isolated candidate → ticket 05 seals the first winner → this module publishes
   it in one strict task CAS. Nothing here is a new purchase authority.

B. The same publication boundary for states that are not edits. A new birthday
   task (or a scenario clarification that later becomes one) reserves a
   predecessor-less root candidate before Cross writes any state; an ordinary
   input/fact/exception successor binds the last sealed *published* source and
   reserves a new isolated candidate. In both cases ticket 05 seals the first
   complete winner and this module publishes the full ref, the result, the new
   revision and completion projection in one task CAS. Default-latest reads are
   never the source: an old task without a published ref stays blocked, and a
   normal successor without a published source cannot pose as a new root.

C. The Harness wiring that actually calls B. ``AgentHarness`` wraps the cross
   entry's saver with ``BirthdayTransition``: reads answer the last sealed
   published ref, writes stay in memory, and after the entry returns the
   platform reserves, seals ticket-05 content built from that buffered Cross
   state and publishes it with the reserved strict revision. No Cross state ever
   reaches the default latest namespace, and the entry-internal task writes no
   longer make the harness result CAS use a stale revision.

Cross owns no publication: the Cross side of edit candidate preparation is the
narrow ``CrossBirthdayHandoff`` Protocol below and ticket 08 implements it. It
reads the exact source ref, builds the complete candidate content and returns
it; it must never ``put`` into the reserved namespace itself (ticket 05's seal is
the single writer). Until ticket 08 lands the edit entry refuses with
``CROSS_HANDOFF_UNAVAILABLE`` instead of improvising. This module is
backend-only: it is not a registered model tool and accepts no client-reported
actor/editable/operation/candidate-hash markers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Literal, Protocol
from uuid import UUID, uuid4

from langgraph.checkpoint.base import CheckpointTuple

from app.contracts.common import Phase, TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.security import ActionDescriptor
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult
from app.memory.adapter import MemoryContext
from app.security.state import SecurityStateError
from app.services.mock_bank.verification import ChallengeNotRetireable
from app.storage.checkpoints import (
    CandidateBindingConflictError, CheckpointRef, SealedCandidate,
)

from .harness import _task_lock

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .transfer_runtime import TransferRuntime


# The one user-visible control this module publishes onto a birthday card. The
# option id is unique per publication and bound server-side to the task, item,
# original operation/attempt and confirmation version; an old card's id never
# matches the current publication record.
EDIT_OPTION_LABEL = "修改尚未提交的部分"
_EDIT_OPTION_PREFIX = "birthday-edit-"
# The published ModuleResult is sealed next to the candidate content so a retry
# republishes the first winner's new-input projection instead of a fresh one.
RESULT_METADATA_KEY = "birthday_platform_result"
_EDITABLE_CARD_KINDS = ("confirmation", "verification")
_ROOT = "root"
_NORMAL = "normal"
_EDIT = "edit"
_TERMINAL = {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED,
             TaskStatus.PARTIALLY_SUCCEEDED}
# An edit needs a defensible current card; needs-attention and every terminal or
# partially settled state is not an editable one (no "current progress" claim).
_EDIT_BLOCKED = _TERMINAL | {TaskStatus.NEEDS_ATTENTION}
_CONVERSION_KINDS = ("input", "fact", "exception")
# The one cross capability whose states are published through the G3 seam.
_CROSS_CAPABILITY = "cross.start_task"
# Completed conversion projections kept for a lost-receipt replay. The current
# publication is `published_ref`; older entries only answer the exact original
# request, they never make an old conversion active again.
_COMPLETED_LIMIT = 8
_KEEP = object()


class BirthdayEditError(ValueError):
    """A truthful refusal: the platform never fakes a published new input."""

    def __init__(self, code: str, reason: str | None = None):
        super().__init__(code)
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class CrossCandidate:
    """What ticket 08 hands back for one reserved candidate ref.

    ``checkpoint``/``metadata``/``new_versions`` are exactly the content ticket
    05 seals; ``writes`` are the associated (channel, value) rows and their
    ``writes_task_id`` must be this trusted task's id (ticket 05 stores them in
    that task's rows only). ``result`` is the module result this state publishes;
    the platform seals a private copy in the metadata and publishes that copy on
    every retry.
    """

    checkpoint: dict
    metadata: dict
    new_versions: dict
    result: ModuleResult
    writes: tuple[tuple[str, Any], ...] = ()
    writes_task_id: str = ""
    writes_task_path: str = ""


@dataclass(frozen=True)
class CandidateRequest:
    """Trusted description of the one candidate Cross may prepare."""

    kind: Literal["root", "normal", "edit"]
    candidate: CheckpointRef
    conversion_digest: str
    accepted_version: int
    source: CheckpointRef | None = None
    source_checkpoint: dict | None = None
    edit_ref: str | None = None
    edit: dict | None = None
    association: dict = field(default_factory=dict)


class CrossBirthdayHandoff(Protocol):
    """Ticket 08's side of the seam; read the source, build the candidate only."""

    def prepare(self, trusted: TrustedContext, request: CandidateRequest) -> CrossCandidate:
        """Return the complete candidate for exactly ``request.candidate``."""


@dataclass(frozen=True)
class EditOutcome:
    """One accepted edit, either freshly published or the frozen first winner."""

    result: ModuleResult
    task_revision: int
    published_ref: CheckpointRef
    content_digest: str
    edit_ref: str


@dataclass(frozen=True)
class PublicationOutcome:
    """One root/normal state published through the same task CAS."""

    result: ModuleResult
    task_revision: int
    published_ref: CheckpointRef
    content_digest: str
    kind: str


def publish_edit_option(runtime, trusted: TrustedContext, *,
                        interaction: InteractionRequest | None, item: str,
                        action_name: str, operation_id: str, action_revision: int,
                        confirmation_id: str | None,
                        confirmation_version: int | None) -> InteractionRequest | None:
    """Append the controlled edit option and persist its publication fact.

    Called by the birthday ports exactly when they hand a confirmation or a
    verification card to the cross module. The published fact is bound to the
    card (interaction/option), the execution item and the original
    operation/attempt/confirmation version; the task CAS makes the fact durable
    before the card can be shown. A failing CAS refuses the card instead of
    showing an option the platform cannot prove.
    """
    if interaction is None or interaction.kind not in _EDITABLE_CARD_KINDS:
        return interaction
    if not confirmation_id or confirmation_version is None:
        # Without the exact confirmation version the retirement binding is
        # incomplete; do not offer an edit path that could retire the wrong fact.
        return interaction
    option = InteractionOption(id=f"{_EDIT_OPTION_PREFIX}{uuid4()}",
                              label=EDIT_OPTION_LABEL)
    record = {
        "interaction_id": interaction.interaction_id,
        "kind": interaction.kind,
        "record_ref": interaction.record_ref,
        "option_id": option.id,
        "item": item,
        "action_name": action_name,
        "operation_id": str(operation_id),
        "action_revision": int(action_revision),
        "confirmation_id": confirmation_id,
        "confirmation_version": int(confirmation_version),
        "published_at": _clock(runtime).isoformat(),
    }
    task = runtime.application.get_task(
        trusted.user_id, trusted.demo_round_id, trusted.task_id,
    )
    if task is None:
        raise BirthdayEditError("TASK_NOT_FOUND")
    try:
        runtime.application.update_task(
            trusted.user_id, trusted.demo_round_id, trusted.task_id,
            task.revision, task.run_id, task.status, task.checkpoint_id,
            {**task.snapshot, "birthday_edit_option": record},
        )
    except ValueError as exc:
        # A concurrent task write is a stale-request conflict, never a raw
        # dependency failure; the card is not shown without its durable fact.
        raise BirthdayEditError(
            "REQUEST_CONFLICT",
            "the option publication lost its task CAS",
        ) from exc
    return interaction.model_copy(update={
        "options": [*interaction.options, option],
    })


class BirthdayHandoff:
    """Platform side of tickets 03/05: controlled edits and G3 state publishing.

    Ticket 08 wires its implementation in as ``cross`` (``birthday.handoff.cross``
    in the local composition); without it every candidate publication refuses.
    """

    def __init__(self, runtime: "TransferRuntime", *,
                 cross: CrossBirthdayHandoff | None = None):
        self.runtime = runtime
        self.cross = cross

    # ------------------------------------------------------------ trusted facts

    def _task(self, trusted: TrustedContext):
        task = self.runtime.application.get_task(
            trusted.user_id, trusted.demo_round_id, trusted.task_id,
        )
        if task is None:
            raise BirthdayEditError("TASK_NOT_FOUND")
        if task.session_id != trusted.session_id:
            # A stale/foreign session never seals edit evidence.
            raise BirthdayEditError("ACCESS_DENIED")
        return task

    def _saver(self, trusted: TrustedContext):
        try:
            return self.runtime.memory.checkpointer(
                MemoryContext(trusted.user_id, trusted.session_id,
                              trusted.demo_round_id),
                trusted.task_id,
            )
        except PermissionError as exc:
            raise BirthdayEditError("ACCESS_DENIED") from exc
        except ValueError as exc:
            raise BirthdayEditError("DEPENDENCY_UNAVAILABLE", str(exc)) from exc

    def _update_task(self, trusted: TrustedContext, task, snapshot: dict, *,
                     status: TaskStatus | None = None, checkpoint_id=_KEEP,
                     run_id: str | None = None,
                     expected_revision: int | None = None):
        return self.runtime.application.update_task(
            trusted.user_id, trusted.demo_round_id, trusted.task_id,
            task.revision if expected_revision is None else expected_revision,
            task.run_id if run_id is None else run_id,
            task.status if status is None else status,
            task.checkpoint_id if checkpoint_id is _KEEP else checkpoint_id,
            snapshot,
        )

    def _read_published_source(self, trusted: TrustedContext, record: dict):
        """Read the exact immutable ref; latest/parent refs are never a fallback."""
        task = self._task(trusted)
        return self._read_source(self._saver(trusted), record,
                                 task.checkpoint_thread_id)

    @staticmethod
    def _read_source(saver, record: dict, thread_id: str):
        ref = _ref_from(record, "SOURCE_UNAVAILABLE")
        if ref.thread_id != thread_id:
            raise BirthdayEditError("SOURCE_UNAVAILABLE", "source is in another thread")
        saved = saver.get_tuple({"configurable": {
            "thread_id": ref.thread_id,
            "checkpoint_ns": ref.checkpoint_ns,
            "checkpoint_id": ref.checkpoint_id,
        }})
        if saved is None:
            raise BirthdayEditError("SOURCE_UNAVAILABLE", "source checkpoint is missing")
        digest = _content_digest(
            saved.checkpoint, saved.metadata, saved.pending_writes,
            code="SOURCE_UNAVAILABLE",
        )
        if digest != record.get("content_digest"):
            raise BirthdayEditError("SOURCE_UNAVAILABLE", "source content changed")
        return saved

    def check_session_recovery(self, trusted: TrustedContext, conversion: dict):
        """Check the owned immutable source before moving its session.

        The Harness has authenticated the target session and authorized the
        capability. The old session may have expired, so this read uses the
        application's task-scoped saver; it does not open a write path or use
        the expired session's memory authority.
        """
        task = self.runtime.application.get_task(
            trusted.user_id, trusted.demo_round_id, trusted.task_id)
        if task is None or task.snapshot.get("capability_name") != _CROSS_CAPABILITY:
            raise BirthdayEditError("ACCESS_DENIED")
        g3 = task.snapshot.get("birthday_g3") or {}
        published = g3.get("published_ref")
        if not isinstance(published, dict):
            raise BirthdayEditError("SOURCE_UNAVAILABLE")
        edit = task.snapshot.get("birthday_edit")
        if isinstance(edit, dict) and edit.get("published") is None:
            raise BirthdayEditError("TRANSITION_PENDING")
        digest = _digest({"kind": _NORMAL,
                          "conversion": _checked_conversion(conversion)})
        pending = g3.get("pending")
        if isinstance(pending, dict) and pending.get("conversion_digest") != digest:
            raise BirthdayEditError("TRANSITION_PENDING")
        saver = self.runtime.application.checkpoint_saver(
            trusted.user_id, trusted.demo_round_id, trusted.task_id)
        saved = self._read_source(saver, published, task.checkpoint_thread_id)
        from .birthday_session import freeze_source

        return freeze_source(self.runtime, trusted, task, published, saved)

    def _prepare_session_recovery(self, trusted: TrustedContext, frozen_source):
        from .birthday_session import prepare

        return prepare(self.runtime, trusted, frozen_source)

    def session_recovery_status(self, trusted: TrustedContext) -> dict[str, object] | None:
        from .birthday_session import status

        return status(self.runtime, trusted)

    def check_recovered_interaction(self, trusted: TrustedContext,
                                    result: ModuleResult) -> None:
        """A resumed sensitive card must belong to the authenticated session."""
        interaction = result.interaction
        if interaction is None:
            return
        try:
            option = self._task(trusted).snapshot.get("birthday_edit_option") or {}
            if (interaction.kind in {"confirmation", "verification"}
                    and (option.get("interaction_id") != interaction.interaction_id
                         or option.get("kind") != interaction.kind
                         or option.get("record_ref") != interaction.record_ref
                         or option.get("option_id") not in {item.id for item in interaction.options})):
                raise ValueError("INTERACTION_STALE")
            if interaction.kind == "confirmation":
                confirmation = self.runtime.confirmations.get(
                    self.runtime._context(trusted, None, None),
                    interaction.record_ref)
                if (confirmation.confirmation_id != option.get("confirmation_id")
                        or confirmation.confirmation_version != option.get("confirmation_version")
                        or str(confirmation.operation_id) != option.get("operation_id")
                        or confirmation.action_revision != option.get("action_revision")):
                    raise ValueError("CONFIRMATION_STALE")
            elif interaction.kind == "verification":
                self.runtime.gateway.get_verification(
                    trusted, interaction.record_ref)
        except (PermissionError, ValueError) as exc:
            raise BirthdayEditError(
                "DEPENDENCY_UNAVAILABLE",
                "the recovered interaction belongs to the old session") from exc

    def find_input_conversion(self, trusted: TrustedContext, request_id: UUID
                              ) -> PublicationOutcome | Literal["pending"] | None:
        """Read this F10 input's frozen publication or its pending association.

        API retries still have to match their original request body. Merely
        having a published birthday task is never proof for another request.
        """
        task = self._task(trusted)
        g3 = task.snapshot.get("birthday_g3") or {}
        conversion = {"kind": "input", "request_id": str(request_id)}
        digest = _digest({"kind": _NORMAL, "conversion": conversion})
        pending = g3.get("pending")
        if (isinstance(pending, dict)
                and pending.get("kind") == _NORMAL
                and pending.get("conversion_digest") == digest):
            return "pending"
        return _completed_publication(g3, digest)

    # ------------------------------------------------------- published edit option

    def published_option(self, trusted: TrustedContext, *, interaction_id: str,
                         option_id: str) -> dict | None:
        """Read-only lookup for the API router; never mutates or grants anything."""
        task = self._task(trusted)
        return _current_option(task, interaction_id, option_id)

    def is_published_edit_option(self, trusted: TrustedContext, *,
                                 interaction_id: str, option_id: str) -> bool:
        try:
            return self.published_option(
                trusted, interaction_id=interaction_id, option_id=option_id,
            ) is not None
        except BirthdayEditError:
            return False

    # ------------------------------------------------------------- A. edit entry

    def begin_birthday_edit(self, trusted: TrustedContext, *, request_id,
                            interaction_id: str,
                            option_id: str) -> EditOutcome:
        """Enter the edit of the current birthday card, once, safely.

        Same request replays the frozen first winner; a different request on the
        same card conflicts; a card that is not the platform's current published
        option is stale; a claimed/unknown original is observed, never edited.
        """
        with _task_lock(self.runtime.application.path, trusted.task_id):
            task = self._task(trusted)
            request_ref = str(request_id)
            record = self._edit_record(task)
            option = _current_option(task, interaction_id, option_id)
            if (record is not None
                    and record.get("interaction_id") == interaction_id
                    and record.get("option_id") == option_id):
                if record.get("published"):
                    # A lost HTTP receipt replays the original completion; no new
                    # publication and no new interaction id.
                    return self._replay_edit(record)
                if option is None:
                    raise BirthdayEditError("INTERACTION_STALE",
                                            "the accepted card is no longer current")
                # Recovery stays on the accepted binding; a new HTTP request id
                # is the caller's receipt concern, not a second edit.
            else:
                if option is None:
                    raise BirthdayEditError("INTERACTION_STALE",
                                            "no current published edit option")
                if (record is not None
                        and record.get("interaction_id") == interaction_id):
                    raise BirthdayEditError("REQUEST_CONFLICT",
                                            "another request already owns this card")
                if task.status in _EDIT_BLOCKED:
                    # needs_attention / partially settled / ended states carry no
                    # defensible "current progress" for an edit.
                    raise BirthdayEditError("TASK_TERMINATED",
                                            f"status {task.status.value} is not editable")
                record = self._accept_edit(
                    trusted, task, request_ref, interaction_id, option_id, option,
                )
            self._retire_original(trusted, record)
            sealed = self._seal_edit_candidate(trusted, record)
            return self._publish_edit(trusted, record, sealed)

    @staticmethod
    def _edit_record(task) -> dict | None:
        record = (task.snapshot or {}).get("birthday_edit")
        return record if isinstance(record, dict) else None

    def _accept_edit(self, trusted: TrustedContext, task, request_ref: str,
                     interaction_id: str, option_id: str,
                     option: dict) -> dict:
        snapshot = task.snapshot or {}
        # When the platform's own public result is a waiting card, it must still
        # be this card. A not-yet-published result (input/running) is not used as
        # the card authority: the published option record below is.
        result = snapshot.get("result")
        if isinstance(result, dict):
            card = result.get("interaction")
            if (isinstance(card, dict)
                    and card.get("kind") in _EDITABLE_CARD_KINDS
                    and card.get("interaction_id") != interaction_id):
                raise BirthdayEditError("INTERACTION_STALE", "the card was replaced")
        item = option.get("item")
        operation_id = option.get("operation_id")
        # The live attempt of that exact item must still be the published one.
        live = (snapshot.get("birthday_actions") or {}).get(item)
        if (not isinstance(live, dict)
                or live.get("operation_id") != operation_id
                or live.get("action_revision") != option.get("action_revision")):
            raise BirthdayEditError("INTERACTION_STALE", "the original attempt was replaced")
        if not option.get("confirmation_id") or option.get("confirmation_version") is None:
            raise BirthdayEditError("INTERACTION_STALE", "the confirmation binding is missing")
        context = self._security_context(trusted, option)
        if (context.confirmation_id, context.confirmation_version) != (
            option["confirmation_id"], option["confirmation_version"],
        ):
            raise BirthdayEditError("INTERACTION_STALE", "the confirmation advanced")
        g3 = snapshot.get("birthday_g3") or {}
        if g3.get("pending") is not None:
            # One accepted conversion at a time; an unpublished successor is
            # never crossed by an edit.
            raise BirthdayEditError("TRANSITION_PENDING")
        published = g3.get("published_ref")
        if not isinstance(published, dict):
            raise BirthdayEditError("SOURCE_UNAVAILABLE", "the task has no published source")
        source = _ref_from(published, "SOURCE_UNAVAILABLE")
        if source.thread_id != task.checkpoint_thread_id:
            raise BirthdayEditError("SOURCE_UNAVAILABLE", "source is in another thread")
        self._read_published_source(trusted, published)
        edit_ref = str(uuid4())
        candidate = CheckpointRef(
            task.checkpoint_thread_id, f"birthday/edit/{edit_ref}", str(uuid4()),
        )
        record = {
            "edit_ref": edit_ref,
            "request_id": request_ref,
            "interaction_id": interaction_id,
            "option_id": option_id,
            "kind": option.get("kind"),
            "record_ref": option.get("record_ref"),
            "item": item,
            "action_name": option["action_name"],
            "operation_id": str(operation_id),
            "action_revision": int(option["action_revision"]),
            "confirmation_id": option["confirmation_id"],
            "confirmation_version": int(option["confirmation_version"]),
            "source": _ref_dict(source),
            "source_digest": published["content_digest"],
            # Strict publication revision: the reservation CAS below leaves the
            # task at this revision; any other write before publication makes the
            # publication CAS fail instead of overwriting it.
            "accepted_version": task.revision + 1,
            "candidate": _ref_dict(candidate),
            "conversion_digest": _digest({
                "kind": _EDIT, "edit_ref": edit_ref, "request_id": request_ref,
                "interaction_id": interaction_id, "option_id": option_id,
                "operation_id": str(operation_id),
                "action_revision": int(option["action_revision"]),
                "source": _ref_dict(source),
            }),
            "accepted_at": _clock(self.runtime).isoformat(),
            "published": None,
        }
        try:
            updated = self._update_task(
                trusted, task, {**snapshot, "birthday_edit": record},
            )
        except ValueError as exc:
            current = self.runtime.application.get_task(
                trusted.user_id, trusted.demo_round_id, trusted.task_id,
            )
            existing = self._edit_record(current) if current is not None else None
            if (existing is not None
                    and existing.get("interaction_id") == interaction_id
                    and existing.get("option_id") == option_id):
                return existing
            raise BirthdayEditError("TASK_CHANGED") from exc
        return (updated.snapshot or {}).get("birthday_edit") or record

    def _security_context(self, trusted: TrustedContext, record: dict):
        try:
            return self.runtime._context(
                trusted, UUID(str(record["operation_id"])),
                int(record["action_revision"]),
            )
        except BirthdayEditError:
            raise
        except PermissionError as exc:
            raise BirthdayEditError("ACCESS_DENIED") from exc
        except Exception as exc:  # noqa: BLE001 - dependency failure is a refusal
            raise BirthdayEditError("DEPENDENCY_UNAVAILABLE", type(exc).__name__) from exc

    @staticmethod
    def _descriptor(record: dict) -> ActionDescriptor:
        return ActionDescriptor(
            action_name=record["action_name"],
            parameters_ref=str(record["operation_id"]),
            resource_refs=[],
            phase=Phase.EXECUTION,
        )

    def _retire_original(self, trusted: TrustedContext, record: dict):
        """Frozen order: security accept → bank retire → security seal."""
        context = self._security_context(trusted, record)
        descriptor = self._descriptor(record)
        try:
            retirement = self.runtime.confirmations.state.begin_retirement(
                context, descriptor, datetime.now(timezone.utc),
                task_state_resolver=self.runtime._task_terminated,
            )
        except SecurityStateError as exc:
            raise BirthdayEditError(_begin_code(exc.code), exc.code) from exc
        try:
            evidence = self.runtime.gateway.retire_action_challenges(
                trusted,
                operation_id=UUID(str(record["operation_id"])),
                action_revision=int(record["action_revision"]),
            )
        except ChallengeNotRetireable as exc:
            # A passed/failed/expired challenge means the bank cannot prove the
            # old attempt lost; editing pauses and the old action keeps its rules.
            raise BirthdayEditError("EDIT_NOT_PROVABLE", exc.reason_code) from exc
        except BirthdayEditError:
            raise
        except Exception as exc:  # noqa: BLE001 - bank/dependency failures refuse
            code = str(exc)
            if code in {"ACCESS_DENIED", "TASK_TERMINATED"}:
                raise BirthdayEditError(code, code) from exc
            raise BirthdayEditError("DEPENDENCY_UNAVAILABLE", code) from exc
        try:
            return self.runtime.confirmations.state.seal_retirement(
                context, retirement.retirement_id, evidence, datetime.now(timezone.utc),
                audit_writer=self.runtime.audit.append_in_transaction,
                task_state_resolver=self.runtime._task_terminated,
            )
        except SecurityStateError as exc:
            raise BirthdayEditError(_seal_code(exc.code), exc.code) from exc

    def _seal_edit_candidate(self, trusted: TrustedContext,
                             record: dict) -> SealedCandidate:
        source_record = record["source"]
        saved = self._read_published_source(trusted, {
            **source_record, "content_digest": record["source_digest"],
        })
        return self._seal_candidate(
            trusted,
            kind=_EDIT,
            candidate_ref=_ref_from(record["candidate"], "CANDIDATE_INVALID"),
            conversion_digest=record["conversion_digest"],
            accepted_version=int(record["accepted_version"]),
            source=_ref_from(source_record, "SOURCE_UNAVAILABLE"),
            source_digest=record["source_digest"],
            source_checkpoint=saved.checkpoint,
            edit_ref=record["edit_ref"],
            edit=record,
            association={
                "request_id": record["request_id"],
                "interaction_id": record["interaction_id"],
                "option_id": record["option_id"],
            },
        )

    def _publish_edit(self, trusted: TrustedContext, record: dict,
                      sealed: SealedCandidate) -> EditOutcome:
        result = self._sealed_result(sealed, "CANDIDATE_INVALID").model_copy(
            update={"run_id": trusted.run_id},
        )
        task = self._task(trusted)
        current = self._edit_record(task)
        if current is None or current.get("edit_ref") != record["edit_ref"]:
            raise BirthdayEditError("REQUEST_CONFLICT", "the accepted edit was replaced")
        if current.get("published"):
            return self._replay_edit(current)
        if task.status in _EDIT_BLOCKED:
            raise BirthdayEditError("TASK_TERMINATED")
        g3 = task.snapshot.get("birthday_g3") or {}
        if not _same_ref(g3.get("published_ref"), record["source"]):
            raise BirthdayEditError("PUBLISH_CONFLICT", "the published source advanced")
        if g3.get("pending") is not None:
            raise BirthdayEditError("TRANSITION_PENDING")
        content_digest = _content_digest(
            sealed.checkpoint, sealed.metadata, sealed.writes,
            code="CANDIDATE_INVALID",
        )
        revision = int(record["accepted_version"]) + 1
        result_json = result.model_dump(mode="json")
        published = {
            **_ref_dict(sealed.ref), "kind": _EDIT,
            "conversion_digest": record["conversion_digest"],
            "content_digest": content_digest,
            "task_revision": revision,
            "published_at": _clock(self.runtime).isoformat(),
        }
        snapshot = {
            **task.snapshot,
            "birthday_edit": {**current, "published": {
                **_ref_dict(sealed.ref), "task_revision": revision,
                "content_digest": content_digest, "result": result_json,
            }},
            "birthday_g3": _record_publication(g3, published, result_json),
            "result": result_json,
        }
        try:
            updated = self._update_task(
                trusted, task, snapshot, status=result.status,
                checkpoint_id=sealed.ref.checkpoint_id, run_id=trusted.run_id,
                expected_revision=int(record["accepted_version"]),
            )
        except ValueError as exc:
            raise BirthdayEditError("PUBLISH_CONFLICT",
                                    "task changed after acceptance") from exc
        return EditOutcome(
            result=result, task_revision=updated.revision,
            published_ref=sealed.ref, content_digest=content_digest,
            edit_ref=record["edit_ref"],
        )

    def _replay_edit(self, record: dict) -> EditOutcome:
        published = record.get("published") or {}
        result = _validated_result(published.get("result"), "CANDIDATE_INVALID")
        try:
            ref = _ref_from(published, "CANDIDATE_INVALID")
            revision = int(published["task_revision"])
            digest = published["content_digest"]
        except (KeyError, TypeError, ValueError) as exc:
            raise BirthdayEditError("CANDIDATE_INVALID") from exc
        return EditOutcome(result=result, task_revision=revision,
                           published_ref=ref, content_digest=digest,
                           edit_ref=record["edit_ref"])

    # ------------------------------------------------- B. initial/normal publish

    def publish_initial_state(self, trusted: TrustedContext) -> PublicationOutcome:
        """Reserve, seal and publish the predecessor-less first birthday state.

        Must run before Cross writes any state for the task. The association is
        the original accepted start request kept on the task; a task without it,
        with a published ref, or with any predecessor state is refused (an old or
        ordinary state never poses as a new root).
        """
        with _task_lock(self.runtime.application.path, trusted.task_id):
            task = self._task(trusted)
            snapshot = task.snapshot or {}
            request_id = snapshot.get("request_id")
            intent_text = snapshot.get("intent_text")
            if (not isinstance(request_id, str) or not request_id
                    or not isinstance(intent_text, str)):
                raise BirthdayEditError("INITIAL_REQUEST_UNKNOWN")
            digest = _digest({
                "kind": _ROOT, "task_id": task.task_id,
                "request_id": request_id, "intent_text": intent_text,
            })
            g3 = snapshot.get("birthday_g3") or {}
            replay = _completed_publication(g3, digest)
            if replay is not None:
                return replay
            if isinstance(g3.get("published_ref"), dict):
                raise BirthdayEditError("INITIAL_ALREADY_PUBLISHED")
            pending = g3.get("pending")
            if isinstance(pending, dict):
                if (pending.get("kind") != _ROOT
                        or pending.get("conversion_digest") != digest):
                    raise BirthdayEditError("ROOT_CONFLICT")
            else:
                if task.status in _TERMINAL:
                    raise BirthdayEditError("TASK_TERMINATED")
                if task.checkpoint_id is not None:
                    raise BirthdayEditError("INITIAL_ALREADY_STARTED")
                pending = {
                    "kind": _ROOT, "conversion_digest": digest,
                    "candidate": _ref_dict(CheckpointRef(
                        task.checkpoint_thread_id, f"birthday/root/{uuid4()}",
                        str(uuid4()),
                    )),
                    "accepted_version": task.revision + 1,
                    "association": {"request_id": request_id,
                                    "intent_text": intent_text},
                    "started_at": _clock(self.runtime).isoformat(),
                }
                task = self._reserve(trusted, task, {**g3, "pending": pending})
            sealed = self._seal_candidate(
                trusted, kind=_ROOT,
                candidate_ref=_ref_from(pending["candidate"], "CANDIDATE_INVALID"),
                conversion_digest=pending["conversion_digest"],
                accepted_version=int(pending["accepted_version"]),
                association=pending.get("association") or {},
            )
            return self._publish_successor(trusted, pending, sealed, _ROOT)

    def publish_normal_state(self, trusted: TrustedContext, *,
                             conversion: dict) -> PublicationOutcome:
        """Publish one ordinary successor from the last sealed published source.

        ``conversion`` is the original association: an accepted F10 request for an
        input, or the original run event for a fact read / exception transition.
        It never creates an edit_ref and never reads the latest checkpoint.
        """
        conversion = _checked_conversion(conversion)
        digest = _digest({"kind": _NORMAL, "conversion": conversion})
        with _task_lock(self.runtime.application.path, trusted.task_id):
            task = self._task(trusted)
            edit = (task.snapshot or {}).get("birthday_edit")
            if isinstance(edit, dict) and edit.get("published") is None:
                # An accepted edit is one conversion too: a normal successor may
                # not cross its original acceptance while it is unpublished.
                raise BirthdayEditError("TRANSITION_PENDING",
                                        "an accepted edit is still in flight")
            g3 = (task.snapshot or {}).get("birthday_g3") or {}
            replay = _completed_publication(g3, digest)
            if replay is not None:
                # A lost receipt replays its own projection; a later conversion
                # never rewrites it and no external write is redone.
                return replay
            published = g3.get("published_ref")
            if not isinstance(published, dict):
                # A normal successor without a published source is not a root.
                raise BirthdayEditError("SOURCE_UNAVAILABLE",
                                        "the task has no published source")
            pending = g3.get("pending")
            if isinstance(pending, dict):
                if (pending.get("kind") != _NORMAL
                        or pending.get("conversion_digest") != digest):
                    raise BirthdayEditError("TRANSITION_PENDING")
            else:
                if task.status in _TERMINAL:
                    raise BirthdayEditError("TASK_TERMINATED")
                self._read_published_source(trusted, published)
                pending = {
                    "kind": _NORMAL, "conversion_digest": digest,
                    "conversion": conversion,
                    "candidate": _ref_dict(CheckpointRef(
                        task.checkpoint_thread_id, f"birthday/normal/{uuid4()}",
                        str(uuid4()),
                    )),
                    "accepted_version": task.revision + 1,
                    "source": dict(published),
                    "started_at": _clock(self.runtime).isoformat(),
                }
                task = self._reserve(trusted, task, {**g3, "pending": pending})
            source_record = pending.get("source")
            if not isinstance(source_record, dict):
                raise BirthdayEditError("SOURCE_UNAVAILABLE",
                                        "the reserved source is missing")
            saved = self._read_published_source(trusted, source_record)
            sealed = self._seal_candidate(
                trusted, kind=_NORMAL,
                candidate_ref=_ref_from(pending["candidate"], "CANDIDATE_INVALID"),
                conversion_digest=pending["conversion_digest"],
                accepted_version=int(pending["accepted_version"]),
                source=_ref_from(source_record, "SOURCE_UNAVAILABLE"),
                source_digest=source_record["content_digest"],
                source_checkpoint=saved.checkpoint,
                association=pending.get("conversion") or {},
            )
            return self._publish_successor(trusted, pending, sealed, _NORMAL)

    def _reserve(self, trusted: TrustedContext, task, g3: dict):
        try:
            return self._update_task(
                trusted, task, {**task.snapshot, "birthday_g3": g3},
            )
        except ValueError as exc:
            raise BirthdayEditError("TASK_CHANGED",
                                    "task changed before the reservation") from exc

    # ------------------------------------------------------ candidate and publish

    def _seal_candidate(self, trusted: TrustedContext, *, kind: str,
                        candidate_ref: CheckpointRef, conversion_digest: str,
                        accepted_version: int, source: CheckpointRef | None = None,
                        source_digest: str | None = None,
                        source_checkpoint: dict | None = None,
                        edit_ref: str | None = None, edit: dict | None = None,
                        association: dict | None = None) -> SealedCandidate:
        if self.cross is None:
            raise BirthdayEditError("CROSS_HANDOFF_UNAVAILABLE")
        request = CandidateRequest(
            kind=kind, candidate=candidate_ref,
            conversion_digest=conversion_digest,
            accepted_version=accepted_version, source=source,
            source_checkpoint=source_checkpoint, edit_ref=edit_ref,
            edit=edit, association=association or {},
        )
        try:
            candidate = self.cross.prepare(trusted, request)
        except BirthdayEditError:
            raise
        except Exception as exc:  # noqa: BLE001 - no candidate means no publication
            raise BirthdayEditError("CROSS_UNAVAILABLE",
                                    type(exc).__name__) from exc
        self._check_candidate(trusted, request, candidate)
        return self._seal_content(
            trusted, kind=kind, candidate_ref=candidate_ref,
            conversion_digest=conversion_digest, accepted_version=accepted_version,
            checkpoint=candidate.checkpoint, metadata=candidate.metadata,
            new_versions=candidate.new_versions, result=candidate.result,
            source=source, source_digest=source_digest, edit_ref=edit_ref,
            writes=tuple(candidate.writes),
            writes_task_id=candidate.writes_task_id,
            writes_task_path=candidate.writes_task_path,
        )

    def _seal_content(self, trusted: TrustedContext, *, kind: str,
                      candidate_ref: CheckpointRef, conversion_digest: str,
                      accepted_version: int, checkpoint: dict, metadata: dict,
                      new_versions: dict, result: ModuleResult,
                      source: CheckpointRef | None = None,
                      source_digest: str | None = None,
                      edit_ref: str | None = None,
                      writes: tuple[tuple[str, Any], ...] = (),
                      writes_task_id: str = "",
                      writes_task_path: str = "") -> SealedCandidate:
        """Seal one complete candidate content exactly once (ticket 05)."""
        if kind not in {_ROOT, _NORMAL, _EDIT}:
            raise BirthdayEditError("CANDIDATE_INVALID", "unsupported candidate kind")
        if kind == _ROOT:
            if source is not None or source_digest is not None or edit_ref is not None:
                raise BirthdayEditError("CANDIDATE_INVALID",
                                        "a root candidate has no source or edit")
        else:
            if source is None or not source_digest:
                raise BirthdayEditError("CANDIDATE_INVALID",
                                        "a successor requires its sealed source")
            if kind == _EDIT and not edit_ref:
                raise BirthdayEditError("CANDIDATE_INVALID",
                                        "an edit candidate requires its edit_ref")
        if not isinstance(result, ModuleResult):
            raise BirthdayEditError("CANDIDATE_INVALID", "candidate result is missing")
        if result.task_id != trusted.task_id:
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "candidate result belongs to another task")
        if checkpoint.get("id") != candidate_ref.checkpoint_id:
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "candidate content is addressed to another ref")
        if writes and writes_task_id != trusted.task_id:
            # Associated writes stay inside this task's own scope.
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "associated writes belong to another task")
        from .birthday_session import ACTION_METADATA_KEY, publication_binding

        sealed_metadata = {
            **metadata,
            RESULT_METADATA_KEY: result.model_dump(mode="json"),
            ACTION_METADATA_KEY: publication_binding(self._task(trusted), result),
        }
        try:
            return self._saver(trusted).seal_candidate(
                trusted.user_id, trusted.demo_round_id, trusted.task_id,
                kind=kind, candidate=candidate_ref,
                accepted_version=accepted_version,
                conversion_digest=conversion_digest,
                checkpoint=checkpoint, metadata=sealed_metadata,
                new_versions=new_versions, source=source,
                source_digest=source_digest, edit_ref=edit_ref,
                writes=writes, writes_task_id=writes_task_id,
                writes_task_path=writes_task_path,
            )
        except CandidateBindingConflictError as exc:
            raise BirthdayEditError("CANDIDATE_CONFLICT") from exc
        except ValueError as exc:
            if kind == _ROOT:
                # The task already published state or the thread holds a
                # predecessor: an old/ordinary task cannot become a new root.
                raise BirthdayEditError("INITIAL_NOT_FIRST", str(exc)) from exc
            raise BirthdayEditError("CANDIDATE_INVALID", str(exc)) from exc

    @staticmethod
    def _check_candidate(trusted: TrustedContext, request: CandidateRequest,
                         candidate: CrossCandidate) -> None:
        if not isinstance(candidate, CrossCandidate):
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "the handoff must return a candidate")
        if (not isinstance(candidate.checkpoint, dict)
                or not isinstance(candidate.metadata, dict)
                or not isinstance(candidate.new_versions, dict)):
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "candidate content must be mappings")
        result = candidate.result
        if not isinstance(result, ModuleResult):
            raise BirthdayEditError("CANDIDATE_INVALID", "candidate result is missing")
        if result.task_id != trusted.task_id:
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "candidate result belongs to another task")
        if candidate.checkpoint.get("id") != request.candidate.checkpoint_id:
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "candidate content is addressed to another ref")
        if candidate.writes and candidate.writes_task_id != trusted.task_id:
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "associated writes belong to another task")
        if request.kind == _ROOT and not (
            result.status is TaskStatus.WAITING_INPUT
            and result.interaction is not None
            and result.interaction.kind == "input"
        ):
            # A failed/empty initialization is presented by the existing
            # failure path, never sealed and published as a fresh root.
            raise BirthdayEditError("INITIAL_NOT_READY",
                                    "the initial state is not a waiting input")
        if request.kind == _EDIT:
            previous = (request.edit or {}).get("interaction_id")
            if not (result.status is TaskStatus.WAITING_INPUT
                    and result.interaction is not None
                    and result.interaction.kind == "input"
                    and result.interaction.interaction_id != previous):
                raise BirthdayEditError(
                    "CANDIDATE_INVALID",
                    "an edit must publish a new input interaction",
                )

    def _publish_successor(self, trusted: TrustedContext, pending: dict,
                           sealed: SealedCandidate, kind: str) -> PublicationOutcome:
        result = self._sealed_result(sealed, "CANDIDATE_INVALID").model_copy(
            update={"run_id": trusted.run_id},
        )
        task = self._task(trusted)
        if task.status in _TERMINAL:
            # A terminal status that was already present at reservation time is
            # this conversion's own closeout (e.g. partially succeeded stop); a
            # terminal status with no such record is a foreign winner.
            if pending.get("terminal_at_reservation") != task.status.value:
                raise BirthdayEditError("PUBLISH_CONFLICT", "the task ended")
        g3 = task.snapshot.get("birthday_g3") or {}
        current = g3.get("pending")
        if (not isinstance(current, dict)
                or current.get("conversion_digest") != pending["conversion_digest"]):
            raise BirthdayEditError("PUBLISH_CONFLICT",
                                    "the reserved conversion changed")
        if kind == _ROOT:
            if g3.get("published_ref") is not None:
                raise BirthdayEditError("PUBLISH_CONFLICT",
                                        "another source was published first")
            if task.checkpoint_id is not None:
                raise BirthdayEditError("PUBLISH_CONFLICT",
                                        "the task already published a checkpoint")
        else:
            if not _same_ref(g3.get("published_ref"), pending.get("source")):
                raise BirthdayEditError("PUBLISH_CONFLICT",
                                        "the published source advanced")
        content_digest = _content_digest(
            sealed.checkpoint, sealed.metadata, sealed.writes,
            code="CANDIDATE_INVALID",
        )
        # A known Harness fault record may advance only this conversion's
        # publication guard. The seal still binds the original admission.
        publication_version = int(pending.get(
            "publication_version", pending["accepted_version"]))
        revision = publication_version + 1
        result_json = result.model_dump(mode="json")
        published = {
            **_ref_dict(sealed.ref), "kind": kind,
            "conversion_digest": pending["conversion_digest"],
            "content_digest": content_digest,
            "task_revision": revision,
            "published_at": _clock(self.runtime).isoformat(),
        }
        snapshot = {
            **task.snapshot,
            "birthday_g3": _record_publication(g3, published, result_json),
            "result": result_json,
        }
        try:
            updated = self._update_task(
                trusted, task, snapshot, status=result.status,
                checkpoint_id=sealed.ref.checkpoint_id, run_id=trusted.run_id,
                expected_revision=publication_version,
            )
        except ValueError as exc:
            raise BirthdayEditError("PUBLISH_CONFLICT",
                                    "task changed after the reservation") from exc
        return PublicationOutcome(
            result=result, task_revision=updated.revision,
            published_ref=sealed.ref, content_digest=content_digest, kind=kind,
        )

    # ------------------------------------------- C. harness publication adapter

    def begin_transition(self, trusted: TrustedContext, *, capability: str,
                         conversion: dict | None,
                         allow_root: bool) -> "BirthdayTransition | None":
        """Reserve the harness-driven publication of one Cross state transition.

        The harness wraps the Cross entry's saver with ``BirthdayTransition.
        attach`` so nothing reaches the default namespace; after the entry
        returns, ``publish`` seals that content once and publishes it by the same
        task CAS rules as tickets 03/05. Only the cross entry (birthday, or a
        clarification that may become one) is intercepted; every other module and
        the clearly non-birthday cross goals keep the legacy saver path.
        """
        if capability != _CROSS_CAPABILITY:
            return None
        task = self._task(trusted)
        snapshot = task.snapshot or {}
        g3 = snapshot.get("birthday_g3") or {}
        published = g3.get("published_ref")
        if isinstance(published, dict):
            if conversion is None:
                # A published G3 task never falls back to a latest/direct write;
                # a transition without its trusted association is refused.
                raise BirthdayEditError("INVALID_CONVERSION",
                                        "a published task requires its association")
            conversion = _checked_conversion(conversion)
            digest = _digest({"kind": _NORMAL, "conversion": conversion})
            replay = _completed_publication(g3, digest)
            edit = snapshot.get("birthday_edit")
            if isinstance(edit, dict) and edit.get("published") is None:
                raise BirthdayEditError("TRANSITION_PENDING",
                                        "an accepted edit is still in flight")
            pending = g3.get("pending")
            if isinstance(pending, dict) and pending.get("conversion_digest") != digest:
                raise BirthdayEditError("TRANSITION_PENDING",
                                        "an unpublished conversion is in flight")
            if replay is None and isinstance(pending, dict):
                candidate = _ref_from(pending["candidate"], "CANDIDATE_INVALID")
                saved = self._saver(trusted).get_tuple({"configurable": {
                    "thread_id": candidate.thread_id,
                    "checkpoint_ns": candidate.checkpoint_ns,
                    "checkpoint_id": candidate.checkpoint_id,
                }})
                content = ({"checkpoint": saved.checkpoint,
                            "metadata": saved.metadata, "new_versions": {}}
                           if saved is not None else pending.get("staged_content"))
                if isinstance(content, dict):
                    # Re-check the original seal binding and publish its first
                    # winner; a lost publication must not run Cross again. An
                    # unsealed occupied namespace is refused by seal_candidate.
                    source = pending["source"]
                    sealed = self._seal_content(
                        trusted, kind=_NORMAL, candidate_ref=candidate,
                        conversion_digest=digest,
                        accepted_version=int(pending["accepted_version"]),
                        checkpoint={**content["checkpoint"], "id": candidate.checkpoint_id},
                        metadata=content["metadata"],
                        new_versions=content["new_versions"], result=_validated_result(
                            content["metadata"].get(RESULT_METADATA_KEY), "CANDIDATE_INVALID"),
                        source=_ref_from(source, "SOURCE_UNAVAILABLE"),
                        source_digest=source["content_digest"],
                    )
                    replay = self._publish_successor(trusted, pending, sealed, _NORMAL)
            return BirthdayTransition(
                self, trusted, kind=_NORMAL, digest=digest,
                conversion=conversion, replayed=replay,
            )
        if not allow_root:
            # A legacy task (already has state but no published ref) stays on the
            # old path; its edit is blocked instead of pretending a fresh root.
            return None
        request_id = snapshot.get("request_id")
        intent_text = snapshot.get("intent_text")
        if (not isinstance(request_id, str) or not request_id
                or not isinstance(intent_text, str)):
            raise BirthdayEditError("INITIAL_REQUEST_UNKNOWN")
        from app.modules.cross.entry import infer_scenario

        scenario = infer_scenario(intent_text)
        if scenario is not None and getattr(scenario, "value", None) != "birthday":
            return None  # clearly another life goal keeps the legacy path
        digest = _digest({
            "kind": _ROOT, "task_id": task.task_id,
            "request_id": request_id, "intent_text": intent_text,
        })
        replay = _completed_publication(g3, digest)
        if replay is not None:
            return BirthdayTransition(self, trusted, kind=_ROOT, digest=digest,
                                      conversion=None, replayed=replay)
        if task.checkpoint_id is not None:
            # State exists without a published ref: an old task, not a new root.
            return None
        pending = g3.get("pending")
        if isinstance(pending, dict) and (
                pending.get("kind") != _ROOT
                or pending.get("conversion_digest") != digest):
            raise BirthdayEditError("ROOT_CONFLICT")
        return BirthdayTransition(self, trusted, kind=_ROOT, digest=digest,
                                  conversion=None)

    def _published_reader(self, trusted: TrustedContext) -> Callable[[], CheckpointTuple | None]:
        def read() -> CheckpointTuple | None:
            task = self._task(trusted)
            g3 = (task.snapshot or {}).get("birthday_g3") or {}
            published = g3.get("published_ref")
            if not isinstance(published, dict):
                return None
            return self._read_published_source(trusted, published)
        return read

    def published_saver(self, trusted, base_saver, *, publication=None):
        """Read an owned sealed source, including an original historical winner."""
        if publication is None:
            read = self._published_reader(trusted)
        else:
            source = {**_ref_dict(publication.published_ref),
                      "content_digest": publication.content_digest}
            read = lambda: self._read_published_source(trusted, source)
        return _BufferedCheckpointSaver(base_saver, read, trusted.task_id)

    def publish_transition(self, trusted: TrustedContext, *, kind: str,
                           digest: str, conversion: dict | None,
                           buffer: "_BufferedContent | None",
                           result: ModuleResult,
                           source_revision: int | None = None) -> PublicationOutcome | None:
        if kind == _ROOT and not _publishable_initial(result):
            # N1: a non-publishable initial conversion is not an error. No root
            # is published; the existing failure/"pending verification" result
            # still reaches the task through the harness result CAS below.
            return None
        if buffer is None:
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "the cross entry produced no candidate content")
        task = self._task(trusted)
        if source_revision is not None and task.revision != source_revision:
            raise BirthdayEditError("PUBLISH_CONFLICT", "the dedicated input source changed")
        snapshot = task.snapshot or {}
        g3 = snapshot.get("birthday_g3") or {}
        edit = snapshot.get("birthday_edit")
        if isinstance(edit, dict) and edit.get("published") is None:
            raise BirthdayEditError("TRANSITION_PENDING",
                                    "an accepted edit is still in flight")
        pending = g3.get("pending")
        if isinstance(pending, dict):
            if (pending.get("kind") != kind
                    or pending.get("conversion_digest") != digest):
                raise BirthdayEditError("TRANSITION_PENDING")
        else:
            if kind == _ROOT:
                if isinstance(g3.get("published_ref"), dict):
                    raise BirthdayEditError("INITIAL_ALREADY_PUBLISHED")
                if task.checkpoint_id is not None:
                    raise BirthdayEditError("INITIAL_ALREADY_STARTED")
                request_id = snapshot.get("request_id")
                intent_text = snapshot.get("intent_text")
                association = {"request_id": request_id, "intent_text": intent_text}
                source_record = None
            else:
                published = g3.get("published_ref")
                if not isinstance(published, dict):
                    raise BirthdayEditError("SOURCE_UNAVAILABLE")
                self._read_published_source(trusted, published)
                association = dict(conversion or {})
                source_record = dict(published)
            checkpoint_id = buffer.checkpoint.get("id")
            if not isinstance(checkpoint_id, str) or not checkpoint_id:
                raise BirthdayEditError("CANDIDATE_INVALID",
                                        "the cross entry wrote no checkpoint")
            candidate = CheckpointRef(
                task.checkpoint_thread_id,
                f"birthday/{kind}/{uuid4()}", str(uuid4()),
            )
            pending = {
                "kind": kind, "conversion_digest": digest,
                "candidate": _ref_dict(candidate),
                "accepted_version": task.revision + 1,
                "association": association,
                # A terminal status written by this same entry call (e.g. the
                # birthday closeout) is part of the conversion we are publishing;
                # an earlier/foreign terminal status has no such record.
                "terminal_at_reservation": (
                    task.status.value if task.status in _TERMINAL else None),
                "started_at": _clock(self.runtime).isoformat(),
            }
            if source_record is not None:
                pending["source"] = source_record
            task = self._reserve(trusted, task, {**g3, "pending": pending})
        candidate_ref = _ref_from(pending["candidate"], "CANDIDATE_INVALID")
        # The reserved candidate ref owns the checkpoint id; the Cross content is
        # addressed to it so a retry republishes the identical first winner.
        checkpoint = {**buffer.checkpoint, "id": candidate_ref.checkpoint_id}
        if kind == _ROOT:
            source = None
            source_digest = None
        else:
            source_record = pending.get("source")
            if not isinstance(source_record, dict):
                raise BirthdayEditError("SOURCE_UNAVAILABLE")
            source = _ref_from(source_record, "SOURCE_UNAVAILABLE")
            source_digest = source_record["content_digest"]
        sealed = self._seal_content(
            trusted, kind=kind, candidate_ref=candidate_ref,
            conversion_digest=pending["conversion_digest"],
            accepted_version=int(pending["accepted_version"]),
            checkpoint=checkpoint, metadata=dict(buffer.metadata),
            new_versions=dict(buffer.new_versions), result=result,
            source=source, source_digest=source_digest,
        )
        return self._publish_successor(trusted, pending, sealed, kind)

    @staticmethod
    def _sealed_result(sealed: SealedCandidate, code: str) -> ModuleResult:
        return _validated_result(sealed.metadata.get(RESULT_METADATA_KEY), code)


@dataclass
class _BufferedContent:
    """The one Cross checkpoint an entry call produced, held until publication."""

    checkpoint: dict
    metadata: dict
    new_versions: dict


class BirthdayTransition:
    """One harness-driven Cross transition, published only after the entry runs.

    ``attach(base_saver)`` wraps the entry's saver: reads answer the last sealed
    published ref (never latest) and writes are buffered in memory, so a Cross
    state never reaches the default namespace. ``publish(result)`` then reserves,
    seals and publishes the buffered content in one task CAS; it returns ``None``
    when the conversion is a non-publishable initial state (N1), leaving the
    existing result/failure card to the harness result CAS. A replayed conversion
    never re-runs the entry: the harness returns the frozen winner.
    """

    def __init__(self, handoff: BirthdayHandoff, trusted: TrustedContext, *,
                 kind: str, digest: str, conversion: dict | None,
                 replayed: PublicationOutcome | None = None):
        self._handoff = handoff
        self._trusted = trusted
        self._kind = kind
        self._digest = digest
        self._conversion = conversion
        self._saver: _BufferedCheckpointSaver | None = None
        self.replayed = replayed

    @property
    def kind(self) -> str:
        return self._kind

    def attach(self, base_saver) -> "_BufferedCheckpointSaver":
        self._saver = self._handoff.published_saver(self._trusted, base_saver)
        return self._saver

    def publish(self, result: ModuleResult, *, source_revision: int | None = None) -> PublicationOutcome | None:
        if self.replayed is not None:
            return self.replayed
        if self._kind == _ROOT and not _publishable_initial(result):
            # N1: a failed/empty first Cross state is presented by the existing
            # failure card; it is never a published root and must not block the
            # result CAS (no candidate content is required here).
            return None
        if self._saver is None or self._saver.buffer is None:
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "the cross entry produced no candidate content")
        return self._handoff.publish_transition(
            self._trusted, kind=self._kind, digest=self._digest,
            conversion=self._conversion, buffer=self._saver.buffer,
            result=result, source_revision=source_revision,
        )

    def interrupted_snapshot(self, task, result: ModuleResult | None) -> dict:
        """Persist this accepted candidate with the Harness fault, not as activity.

        A storage failure before sealing must not force a retry to run Cross
        again (it may already have created a confirmation or bank operation).
        This private pending content is retained by the same task CAS as the
        fault; only the normal seal/publication path can make it visible.
        """
        snapshot = task.snapshot
        g3 = snapshot.get("birthday_g3") or {}
        pending = g3.get("pending")
        if not isinstance(pending, dict) or pending.get("conversion_digest") != self._digest:
            return snapshot
        guard = int(pending.get("publication_version", pending["accepted_version"]))
        if (task.revision != guard
                or self._kind == _NORMAL
                and not _same_ref(g3.get("published_ref"), pending.get("source"))):
            raise BirthdayEditError("PUBLISH_CONFLICT",
                                    "the accepted conversion changed before its fault record")
        pending = {**pending, "publication_version": task.revision + 1}
        if ("staged_content" not in pending and self._saver is not None
                and self._saver.buffer is not None and result is not None):
            buffer = self._saver.buffer
            pending["staged_content"] = {
                "checkpoint": buffer.checkpoint,
                "metadata": {**buffer.metadata,
                             RESULT_METADATA_KEY: result.model_dump(mode="json")},
                "new_versions": buffer.new_versions,
            }
        return {**snapshot, "birthday_g3": {**g3, "pending": pending}}


class _BufferedCheckpointSaver:
    """Saver-shaped adapter: read the published ref, buffer the new state.

    Used only for a cross birthday task published through this seam (the harness
    creates it only for ``cross.start_task`` birthday/ambiguous tasks with a G3
    published ref or root eligibility; clearly other life goals keep the legacy
    saver). CrossEntry only calls ``get_tuple``/``put`` here, and no LangGraph
    machinery runs on this saver, so those two methods are enough. Reads always
    answer the exact sealed published ref with its content digest verified (the
    config's thread/ns are intentionally ignored: the adapter is bound to this
    one task's published ref, never to a latest/default namespace). Writes are
    buffered for ``BirthdayTransition.publish`` and never touch the default
    namespace.
    """

    def __init__(self, base, read_published: Callable[[], CheckpointTuple | None],
                 task_id: str):
        self.base = base
        self.read_published = read_published
        self.task_id = task_id
        self.thread_id = getattr(base, "thread_id", None)
        self.buffer: _BufferedContent | None = None
        self._buffered_tuple: CheckpointTuple | None = None

    def get_tuple(self, config: dict) -> CheckpointTuple | None:
        if self._buffered_tuple is not None:
            return self._buffered_tuple
        return self.read_published()

    def put(self, config: dict, checkpoint: dict, metadata: dict,
            new_versions: dict) -> dict:
        self.buffer = _BufferedContent(
            checkpoint=checkpoint, metadata=metadata, new_versions=new_versions,
        )
        configurable = dict((config or {}).get("configurable") or {})
        configurable["checkpoint_id"] = checkpoint["id"]
        self._buffered_tuple = CheckpointTuple(
            config={"configurable": configurable}, checkpoint=checkpoint,
            metadata=metadata, parent_config=None, pending_writes=[],
        )
        return {"configurable": configurable}


# --------------------------------------------------------------------- helpers


def _current_option(task, interaction_id: str, option_id: str) -> dict | None:
    record = (task.snapshot or {}).get("birthday_edit_option")
    if not isinstance(record, dict):
        return None
    if (record.get("interaction_id") != interaction_id
            or record.get("option_id") != option_id):
        return None
    return record


def _begin_code(code: str) -> str:
    if code in {"OPERATION_UNKNOWN", "TASK_TERMINATED", "ACCESS_DENIED",
                "DEPENDENCY_UNAVAILABLE"}:
        return code
    if code == "OPERATION_CONFLICT":
        return "REQUEST_CONFLICT"
    return "INTERACTION_STALE"


def _seal_code(code: str) -> str:
    if code in {"ACCESS_DENIED", "TASK_TERMINATED", "DEPENDENCY_UNAVAILABLE",
                "AUDIT_UNAVAILABLE", "RETIREMENT_STALE"}:
        return code
    # A claim appeared between acceptance and sealing: the original operation
    # must be observed from now on, never edited.
    if code in {"OPERATION_UNKNOWN", "OPERATION_CONFLICT"}:
        return "OPERATION_UNKNOWN"
    return "INTERACTION_STALE"


def _checked_conversion(conversion: dict) -> dict:
    """Validate one trusted conversion association (shape only, no client entry).

    An ordinary input is identified either by the explicit F10 request id (the
    best receipt identity, passed by API04) or, when that is unavailable, by the
    current waiting card plus the accepted publication revision and the answer
    digest (see AgentHarness._resume_conversion). Both are stable across retries
    under different F10 run ids.
    """
    if not isinstance(conversion, dict):
        raise BirthdayEditError("INVALID_CONVERSION")
    if set(conversion) - {"kind", "request_id", "interaction_id",
                          "accepted_version", "answer_digest", "event_ref",
                          "run_id"}:
        raise BirthdayEditError("INVALID_CONVERSION")
    kind = conversion.get("kind")
    if kind not in _CONVERSION_KINDS:
        raise BirthdayEditError("INVALID_CONVERSION")
    if kind == "input":
        request_id = conversion.get("request_id")
        if request_id is not None:
            if not isinstance(request_id, str) or not request_id:
                raise BirthdayEditError("INVALID_CONVERSION")
            if "event_ref" in conversion or "interaction_id" in conversion:
                raise BirthdayEditError("INVALID_CONVERSION")
        else:
            interaction_id = conversion.get("interaction_id")
            accepted = conversion.get("accepted_version")
            answer = conversion.get("answer_digest")
            if (not isinstance(interaction_id, str) or not interaction_id
                    or not isinstance(answer, str) or not answer
                    or not isinstance(accepted, int) or isinstance(accepted, bool)
                    or accepted < 0):
                raise BirthdayEditError("INVALID_CONVERSION")
            if "event_ref" in conversion:
                raise BirthdayEditError("INVALID_CONVERSION")
    else:
        event_ref = conversion.get("event_ref")
        if not isinstance(event_ref, str) or not event_ref:
            raise BirthdayEditError("INVALID_CONVERSION")
        if set(conversion) - {"kind", "event_ref", "run_id"}:
            raise BirthdayEditError("INVALID_CONVERSION")
    run_id = conversion.get("run_id")
    if run_id is not None and (not isinstance(run_id, str) or not run_id):
        raise BirthdayEditError("INVALID_CONVERSION")
    return dict(conversion)


def _completed_publication(g3: dict, digest: str) -> PublicationOutcome | None:
    for entry in g3.get("completed") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("conversion_digest") != digest:
            continue
        return _publication_from_entry(entry)
    return None


def _publication_from_entry(entry: dict) -> PublicationOutcome:
    result = _validated_result(entry.get("result"), "CANDIDATE_INVALID")
    try:
        ref = _ref_from(entry, "CANDIDATE_INVALID")
        revision = int(entry["task_revision"])
        digest = entry["content_digest"]
    except (KeyError, TypeError, ValueError) as exc:
        raise BirthdayEditError("CANDIDATE_INVALID") from exc
    return PublicationOutcome(
        result=result, task_revision=revision, published_ref=ref,
        content_digest=digest, kind=str(entry.get("kind")),
    )


def _record_publication(g3: dict, published: dict, result: dict) -> dict:
    """Keep the current ref plus bounded per-conversion completion projections."""
    completed = [entry for entry in (g3.get("completed") or [])
                 if isinstance(entry, dict)]
    entry = {**published, "result": result}
    return {
        **g3, "published_ref": published, "pending": None,
        "completed": [entry, *completed][:_COMPLETED_LIMIT],
    }


def _publishable_initial(result: ModuleResult) -> bool:
    """Only an actual waiting-input first card becomes the published root."""
    return (result.status is TaskStatus.WAITING_INPUT
            and result.interaction is not None
            and result.interaction.kind == "input")


def _validated_result(value: object, code: str) -> ModuleResult:
    if not isinstance(value, dict):
        raise BirthdayEditError(code, "the sealed result is missing")
    try:
        return ModuleResult.model_validate(value)
    except Exception as exc:  # noqa: BLE001 - a broken stored result is refused
        raise BirthdayEditError(code, "the sealed result is invalid") from exc


def _clock(runtime) -> datetime:
    return runtime.gateway._bank.clock()


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _digest(value: object) -> str:
    try:
        encoded = _canonical(value)
    except (TypeError, ValueError) as exc:
        raise BirthdayEditError("INVALID_CONVERSION",
                                "the association is not canonical") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _content_digest(checkpoint: dict, metadata: dict, writes, *,
                    code: str) -> str:
    """One stable logical digest over the sealed content.

    Ticket 05's own content digest is over its private serde blobs; this one is
    the readable equivalent the platform records on publication and re-checks on
    every exact read (a sealed namespace is immutable, latest is never used).
    """
    payload = {
        "checkpoint": checkpoint,
        "metadata": metadata,
        "writes": [list(item) for item in writes],
    }
    try:
        encoded = _canonical(payload)
    except (TypeError, ValueError) as exc:
        raise BirthdayEditError(code, "the content is not canonical") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _ref_dict(ref: CheckpointRef) -> dict:
    return {
        "thread_id": ref.thread_id,
        "checkpoint_ns": ref.checkpoint_ns,
        "checkpoint_id": ref.checkpoint_id,
    }


def _ref_from(record: dict, code: str) -> CheckpointRef:
    try:
        thread_id = record["thread_id"]
        checkpoint_ns = record["checkpoint_ns"]
        checkpoint_id = record["checkpoint_id"]
    except (KeyError, TypeError) as exc:
        raise BirthdayEditError(code, "a checkpoint ref is missing") from exc
    if not all(isinstance(value, str) and value
               for value in (thread_id, checkpoint_ns, checkpoint_id)):
        raise BirthdayEditError(code, "a checkpoint ref is invalid")
    return CheckpointRef(thread_id, checkpoint_ns, checkpoint_id)


def _same_ref(left: object, right: object) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    return (left.get("thread_id"), left.get("checkpoint_ns"),
            left.get("checkpoint_id")) == (
        right.get("thread_id"), right.get("checkpoint_ns"),
        right.get("checkpoint_id"),
    )
