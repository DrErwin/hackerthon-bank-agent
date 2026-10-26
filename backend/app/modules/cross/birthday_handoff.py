"""Ticket v05-cross-business/08: the Cross side of the platform edit handoff.

Ticket 03 (``app/agent_platform/birthday_edit.py``) owns the frozen order of one
controlled birthday edit: it reserves the exact published source ref and one
candidate ref, retires the unsubmitted original attempt through security 02 and
the bank, then asks this module for the candidate content and lets ticket 05 seal
the first winner and the platform publish it in one task CAS. Cross owns only
the content:

* read the exact source checkpoint the platform verified and hand back a new
  birthday state that is a *new ordinary input interaction*: the retired card is
  gone, the recomputed plan and its editable unsubmitted items are visible;
* never write the saver or the reserved namespace (ticket 05 is the only writer)
  and never grant a new action authority;
* refuse a foreign actor, a non-edit request or a source without a birthday
  state instead of improvising content.

The platform composition attaches this implementation through
``install_cross_handoff`` (``birthday.handoff.cross``); without that one-line
wiring the platform seam keeps its documented ``CROSS_HANDOFF_UNAVAILABLE``
refusal, so the wiring is not faked here.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from app.agent_platform.birthday_edit import (
    BirthdayEditError, CandidateRequest, CrossCandidate,
)
from app.contracts.tasks import (
    InteractionOption, InteractionRequest, ModuleResult,
)
from app.contracts.common import TaskStatus

from . import plan
from .birthday import BirthdayFlow

_CHANNEL = "cross_state"
_EDITABLE_ACTIONS = ("bank.create_order", "bank.capture_frozen")
_FREEZE_ACTION = "bank.freeze_funds"


class BirthdayHandoffAdapter:
    """Implements ``CrossBirthdayHandoff``: read the source, build the candidate.

    The clock is injected so the sealed checkpoint timestamp follows the bank
    clock in tests and the real composition; no other dependency is read.
    """

    def __init__(self, clock):
        self.clock = clock

    # ------------------------------------------------------------- protocol

    def prepare(self, trusted, request: CandidateRequest) -> CrossCandidate:
        state = self._source_state(trusted, request)
        after = self._after(request)
        flow = BirthdayFlow(None, state, None)
        flow.edit_begin(after, {
            "interaction_id": (request.edit or {}).get("interaction_id"),
            "kind": (request.edit or {}).get("kind"),
            "action_name": (request.edit or {}).get("action_name"),
            "item": (request.edit or {}).get("item"),
            "operation_id": (request.edit or {}).get("operation_id"),
            "action_revision": (request.edit or {}).get("action_revision"),
        })
        if after == "freeze":
            # Nothing was submitted before the freeze: the chosen basket is the
            # plan and re-adoption recalculates it (Q01/Q02).
            prompt, choices = flow.pick_menu()
        else:
            prompt, choices = flow.edit_menu()
        result = self._waiting_input(trusted, state, prompt, choices)
        return self._candidate(request, state, result)

    # ------------------------------------------------------------ validations

    def _source_state(self, trusted, request: CandidateRequest) -> dict:
        if request.kind != "edit":
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "only an edit candidate is prepared here")
        if request.edit is None or request.source_checkpoint is None:
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "the edit request or the sealed source is missing")
        values = (request.source_checkpoint.get("channel_values") or {})
        state = deepcopy(values.get(_CHANNEL))
        if not isinstance(state, dict):
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "the source carries no birthday state")
        if tuple(state.get("actor") or ()) != (
                trusted.user_id, trusted.demo_round_id, trusted.task_id):
            # The sealed source is read for exactly this trusted task; a
            # foreign source never becomes this task's new input.
            raise BirthdayEditError("ACCESS_DENIED", "source belongs to another task")
        if state.get("scenario") != "birthday" or not isinstance(
                state.get("birthday"), dict):
            raise BirthdayEditError("CANDIDATE_INVALID",
                                    "the source is not a birthday state")
        return state

    @staticmethod
    def _after(request: CandidateRequest) -> str:
        action_name = (request.edit or {}).get("action_name")
        if action_name == _FREEZE_ACTION:
            return "freeze"
        if action_name in _EDITABLE_ACTIONS:
            return "orders"
        raise BirthdayEditError("CANDIDATE_INVALID",
                                "the original card names no editable action")

    # --------------------------------------------------------------- content

    def _waiting_input(self, trusted, state: dict, prompt: str,
                       choices) -> ModuleResult:
        interaction_id = str(uuid4())
        state["choices"] = {str(uuid4()): value for _label, value in choices}
        state["waiting"] = "ask"
        state["interaction_id"] = interaction_id
        options = [InteractionOption(id=option_id, label=label)
                   for option_id, (label, _value) in zip(state["choices"], choices)]
        result = ModuleResult(
            task_id=trusted.task_id, run_id=trusted.run_id,
            status=TaskStatus.WAITING_INPUT,
            data=plan.build_view(state, prompt) if "steps" in state else None,
            message=prompt,
            interaction=InteractionRequest(
                interaction_id=interaction_id, kind="input", prompt=prompt,
                required_fields=["cross_selection"], options=options,
                record_ref=None),
            error=None, allowed_actions=["provide_input", "cancel"],
            recovery_required=False, recovery_reason=None)
        # Keep the module result inside the sealed state: a later ordinary resume
        # reads it as the current card exactly like any other waiting state.
        state["result"] = result.model_dump(mode="json")
        return result

    def _candidate(self, request: CandidateRequest, state: dict,
                   result: ModuleResult) -> CrossCandidate:
        version = int((request.source_checkpoint.get("channel_versions")
                       or {}).get(_CHANNEL, 0)) + 1
        checkpoint = {
            "v": 1, "id": request.candidate.checkpoint_id,
            "ts": self._now(),
            "channel_values": {_CHANNEL: state},
            "channel_versions": {_CHANNEL: version},
            "versions_seen": {}, "pending_sends": [],
        }
        return CrossCandidate(
            checkpoint=checkpoint,
            metadata={"source": "update", "step": version, "parents": {}},
            new_versions={_CHANNEL: version},
            result=result,
        )

    def _now(self) -> str:
        if self.clock is None:
            return datetime.now(timezone.utc).isoformat()
        return self.clock().isoformat()


def install_cross_handoff(handoff, *, clock):
    """Attach this module's implementation to the platform ``BirthdayHandoff``.

    Called by the composition (``local_demo.build_runtime``) after the birthday
    runtime is built; it is the one Cross-side line platform ticket 03 names
    (``birthday.handoff.cross``). The platform test doubles construct their own
    ``BirthdayHandoff`` with an explicit stand-in, so this never rewires them.
    """
    if getattr(handoff, "cross", None) is None:
        handoff.cross = BirthdayHandoffAdapter(clock)
    return handoff.cross
