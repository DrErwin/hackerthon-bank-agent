"""Shared plan skeleton for the cross life goals (v05-cross-business/01).

The plan is plain checkpointed state and deterministic code owns every
transition. Children run through the platform's controlled dispatch seam with
inputs this module builds from verified facts; each child keeps its own
confirmation and verification, so adopting a plan never approves a sensitive
action. The three life goals differ in their step definitions and receipts,
not in how a plan advances, pauses, resumes or closes out.
"""

from __future__ import annotations


from datetime import datetime, timedelta, timezone
from uuid import uuid4

BEIJING = timezone(timedelta(hours=8))

# The one checkpoint channel the cross state lives in (ticket v05-cross-business/
# 08): the ordinary saver and the platform edit handoff build the same envelope.
CHANNEL = "cross_state"


def money(fen: int) -> str:
    return f"{fen / 100:.2f}"


def month_range(now: datetime, months_ago: int) -> tuple[datetime, datetime]:
    """One complete calendar month in Beijing time, counted back from ``now``."""

    local = now.astimezone(BEIJING)
    index = local.year * 12 + local.month - 1 - months_ago
    next_index = index + 1
    start = datetime(index // 12, index % 12 + 1, 1, tzinfo=BEIJING)
    end = datetime(next_index // 12, next_index % 12 + 1, 1, tzinfo=BEIJING)
    return start, end

from app.contracts.common import TaskStatus
from app.contracts.cross import BudgetView, CrossStep, CrossTaskView
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult

# Statuses that hold the parent's single user-response or side-effect slot.
HOLDING = frozenset({
    TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL, TaskStatus.NEEDS_ATTENTION,
    TaskStatus.RUNNING,
})
TERMINAL = frozenset({TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED,
                      TaskStatus.PARTIALLY_SUCCEEDED})


def item_key(item: dict) -> str:
    """A plan row's stable execution identity, separate from the product id.

    The legacy shape (an old checkpoint whose rows carry no ``item_id``) keeps
    the product key; a new row is always addressed by its own item id, so a
    same-product replacement is a different execution item.
    """
    return item.get("item_id") or item["product_id"]


def checkpoint_envelope(checkpoint_id: str, ts: str, state: dict,
                        version: int) -> dict:
    """One Cross checkpoint envelope for the saver and the edit handoff."""
    return {
        "v": 1, "id": checkpoint_id, "ts": ts,
        "channel_values": {CHANNEL: state},
        "channel_versions": {CHANNEL: version},
        "versions_seen": {}, "pending_sends": [],
    }


def ask_result(context, state: dict, prompt: str, choices,
               *, view: bool | None = None) -> ModuleResult:
    """One server-built input menu, shared by the entry and the edit handoff.

    ``view`` defaults to the entry's historical rule (a CrossTaskView only once
    there is something to show); the edit handoff always asks for it.
    """
    if view is None:
        view = bool((state.get("birthday") or {}).get("write_facts")
                    or (state.get("personal_budget") or {}).get("view"))
    interaction_id = str(uuid4())
    state["choices"] = {str(uuid4()): value for _label, value in choices}
    state["waiting"] = "ask"
    state["interaction_id"] = interaction_id
    options = [InteractionOption(id=option_id, label=label)
               for option_id, (label, _value) in zip(state["choices"], choices)]
    return ModuleResult(
        task_id=context.task_id, run_id=context.run_id,
        status=TaskStatus.WAITING_INPUT,
        data=build_view(state, prompt) if ("steps" in state and view) else None,
        message=prompt,
        interaction=InteractionRequest(
            interaction_id=interaction_id, kind="input", prompt=prompt,
            required_fields=["cross_selection"], options=options,
            record_ref=None),
        error=None, allowed_actions=["provide_input", "cancel"],
        recovery_required=False, recovery_reason=None)


def new_state(trusted, request_id: str, scenario: str, goal_digest: str,
              steps: list[dict]) -> dict:
    return {
        "actor": [trusted.user_id, trusted.demo_round_id, trusted.task_id],
        "session_id": trusted.session_id,
        "request_id": request_id,
        "goal_digest": goal_digest,
        "scenario": scenario,
        "plan_revision": 1,
        "steps": steps,
        "step_state": {step["step_id"]: {} for step in steps},
        "waiting": None,
        "choices": {},
        "interaction_id": None,
        "receipts": [],
        "unknown": [],
        "stop_reason": None,
    }


def step_ids(state: dict) -> list[str]:
    return [step["step_id"] for step in state["steps"]]


def add_step(state: dict, step: dict) -> None:
    """Append one step the user just chose; the plan version moves on with it.

    A new step under a bumped revision is what makes an older child resume
    refuse with PLAN_SUPERSEDED: an answered interaction can never approve an
    action that was added after it.
    """

    if step["step_id"] in step_ids(state):
        raise ValueError("STEP_ALREADY_PLANNED")
    state["steps"].append(step)
    state["step_state"][step["step_id"]] = {}
    state["plan_revision"] += 1


def step_state(state: dict, step_id: str) -> dict:
    return state["step_state"].get(step_id, {})


def deps_met(state: dict, step: dict) -> bool:
    return all(
        step_state(state, dep).get("status") is TaskStatus.SUCCEEDED
        for dep in step.get("depends_on", ())
    )


def next_step(state: dict) -> dict | None:
    """The first planned step whose dependencies succeeded and that has not run."""

    for step in state["steps"]:
        record = step_state(state, step["step_id"])
        if record.get("status") is None and deps_met(state, step):
            return step
    return None


def holding_step(state: dict) -> dict | None:
    for step in state["steps"]:
        if step_state(state, step["step_id"]).get("status") in HOLDING:
            return step
    return None


def reconcile(state: dict, harness, trusted) -> None:
    """Refresh step records from the durable child states; facts stay bank-true.

    A step's status is whatever its child task last reported — the parent never
    reinterprets a waiting child as done, a failed child as skippable silence,
    or an unknown child as anything but unknown.
    """

    summaries = {
        summary["step_id"]: summary
        for summary in harness.child_task_summaries(trusted)
    }
    for step in state["steps"]:
        record = step_state(state, step["step_id"])
        child_id = record.get("child_task_id")
        if child_id is None:
            continue
        summary = summaries.get(step["step_id"])
        if summary is None:
            continue
        status = TaskStatus(summary["status"])
        record["status"] = status
        record["child_task_id"] = summary["child_task_id"]
        if status in TERMINAL and "result" not in record:
            child = harness.application.get_task(
                trusted.user_id, trusted.demo_round_id, child_id)
            result = (child.snapshot.get("result") or {}) if child else {}
            record["result"] = result.get("data")
            record["error"] = (result.get("error") or {}).get("code")
            record["message"] = result.get("message")


def build_steps(state: dict) -> list[CrossStep]:
    steps = []
    for step in state["steps"]:
        record = step_state(state, step["step_id"])
        steps.append(CrossStep(
            step_id=step["step_id"], action=step["action"],
            child_task_id=record.get("child_task_id"),
            status=record.get("status"),
            amount_fen=record.get("amount_fen"),
            error=None,
            depends_on=list(step.get("depends_on", ())),
        ))
    return steps


def build_view(state: dict, summary: str, *, active_step_id: str | None = None,
               interaction_task_id: str | None = None) -> CrossTaskView:
    steps = build_steps(state)
    if state.get("birthday"):
        from .birthday_view import build_birthday_steps
        steps.extend(build_birthday_steps(state["birthday"]))
    return CrossTaskView(
        scenario=state["scenario"],
        plan_revision=state["plan_revision"],
        steps=steps,
        summary=summary,
        plan_step_ids=[step.step_id for step in steps],
        active_step_id=active_step_id,
        interaction_task_id=interaction_task_id,
        arrangement=None,
        budget=BudgetView.model_validate(state["personal_budget"]["view"])
            if (state.get("personal_budget") or {}).get("view") else None,
        stop_reason=state.get("stop_reason"),
    )
