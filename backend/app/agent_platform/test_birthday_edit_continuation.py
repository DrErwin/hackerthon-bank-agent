"""Ticket v05-birthday-platform-dependencies/09: same-parameter attempts after a proven retirement.

Ticket 08 reported the gap on the real composition: ticket 03 retires the waiting
attempt, then the unchanged plan re-checks the same action with identical
parameters (the freeze keeps its account/cap; an order/capture card keeps its
item), so the ports handed the retired operation back to the gate and the real
"continue after editing" stopped as ``ACTION_RETIRED``. With a freeze already
submitted that stop could also close the task through the limited-release ending.

Failure modes pinned here first:

1. The ports must never reuse a sealed-retired operation: identical parameters
   build a new attempt/operation with a strictly rising revision, and the gate
   evaluates it normally (a real confirmation/verification card), not BLOCK.
2. The retirement proof is ticket 02's sealed record (read-only here): no extra
   task write is needed next to the platform's strict edit-publish CAS, and a
   duplicate edit click still replays the one published result only.
3. The replacement is a genuine new attempt: the old operation is never executed
   and stays readable in ``birthday_attempts`` and at the security layer
   (``ACTION_RETIRED``).
4. None of the three continuation cards may close the task or release funds just
   because the retired attempt was detected.

The composition is the real one (harness, security gate, mock bank, stores, G3
publication, real Cross flow); ticket 08's assembly (``register_cross`` ->
``install_cross_handoff``) mounts its real adapter there, and this test never
assigns or stands in for it.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.contracts.common import Phase, TaskStatus
from app.contracts.security import ActionDescriptor
from app.security.state import SecurityStateError
from app.storage.database import connect

from .birthday_edit import EDIT_OPTION_LABEL
from .test_birthday_edit_handoff import allow_decision
from .test_birthday_harness_publication import (  # noqa: F401 - pytest fixture
    drive_to_freeze_confirmation, harness_env,
)
from .test_birthday_runtime_wiring import (
    _all_freezes, answer_verification, approve_confirmation, option_id,
)


@pytest.fixture()
def continuation_env(harness_env):
    """The real composition, with ticket 08's assembly mounting the real handoff.

    The mount itself is asserted here so a composition that forgets it can never
    silently fall back to the documented ``CROSS_HANDOFF_UNAVAILABLE`` refusal.
    """
    handoff = harness_env.runtime.birthday.handoff
    assert handoff.cross is not None
    assert callable(handoff.cross.prepare)
    return harness_env


# ------------------------------------------------------------------- helpers


def actions(env) -> dict:
    return env.snapshot().get("birthday_actions") or {}


def attempts(env) -> list[dict]:
    return list(env.snapshot().get("birthday_attempts") or [])


def key_for(env, prefix: str) -> str:
    matches = [key for key in actions(env) if key.startswith(prefix)]
    assert len(matches) == 1, [key for key in actions(env)]
    return matches[0]


def begin_edit(env, card):
    option = next(item for item in card.interaction.options
                  if item.label == EDIT_OPTION_LABEL)
    return env.runtime.birthday.handoff.begin_birthday_edit(
        env.who, request_id=uuid4(),
        interaction_id=card.interaction.interaction_id, option_id=option.id)


def settle_confirmation(env, card):
    """Approve one confirmation, answer its real step-up code, continue."""
    assert card.interaction.kind == "confirmation", card.message
    approve_confirmation(env.runtime, env.who, card.interaction.record_ref)
    waiting = env.resume({"choice": "approve"})
    assert waiting.interaction.kind == "verification", waiting.message
    answer_verification(env.runtime, env.who, "R1", waiting.interaction.record_ref)
    return env.resume({"choice": "resume"})


def retirement_of(env, action: dict):
    """The security record for this exact attempt (ticket 02 read-only seam)."""
    context = env.runtime._context(
        env.who, UUID(action["operation_id"]),
        int(action["action_revision"]))
    return env.runtime.confirmations.state.get_retirement(
        context, env.who.task_id, UUID(action["operation_id"]),
        int(action["action_revision"]))


def retired_claim_code(env, action: dict, binding: dict) -> str:
    """Re-try the sealed-retired operation once; the security layer must refuse.

    The context carries the original confirmation binding explicitly: after the
    continuation a new confirmation exists for the new operation, so the generic
    "current confirmation" lookup no longer names the retired attempt's record.
    The sealed retirement row is still readable and is what refuses the claim.
    """
    context = env.runtime._context(
        env.who, UUID(action["operation_id"]),
        int(action["action_revision"])).model_copy(update={
            "confirmation_id": binding["confirmation_id"],
            "confirmation_version": int(binding["confirmation_version"]),
        })
    record = {
        "operation_id": action["operation_id"],
        "action_revision": action["action_revision"],
        "action_name": action["parameters"]["__action__"],
    }
    descriptor = ActionDescriptor(
        action_name=record["action_name"], parameters_ref=record["operation_id"],
        resource_refs=[], phase=Phase.EXECUTION)
    with pytest.raises(SecurityStateError) as refused:
        env.runtime.confirmations.state.claim_execution(
            context, descriptor, allow_decision(record),
            datetime.now(timezone.utc), env.runtime._task_terminated)
    retirement = env.runtime.confirmations.state.get_retirement(
        context, env.who.task_id, UUID(record["operation_id"]),
        int(record["action_revision"]))
    assert retirement is not None and retirement.state == "sealed"
    return refused.value.code


def assert_new_attempt(env, old: dict, new: dict, binding: dict) -> None:
    """Ticket 09: identical binding, brand-new operation, old one non-reusable."""
    assert new["parameters"] == old["parameters"]  # the plan did not change
    assert new["operation_id"] != old["operation_id"]
    assert new["action_revision"] == old["action_revision"] + 1
    history = [item for item in attempts(env)
               if item["operation_id"] == old["operation_id"]]
    assert len(history) == 1
    assert history[0]["parameters"] == old["parameters"]
    assert history[0]["action_revision"] == old["action_revision"]
    assert retired_claim_code(env, old, binding) == "ACTION_RETIRED"


def assert_still_running(env) -> None:
    """The continuation is a live task, not a blocked/closed settlement."""
    assert env.task().status is TaskStatus.WAITING_APPROVAL
    assert env.snapshot()["result"]["status"] == "waiting_approval"


def bank_operation(env, operation_id: str):
    return env.runtime.gateway.get_operation(env.who, UUID(operation_id))


def orders(env) -> list[dict]:
    with connect(env.runtime.gateway._bank.store.path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM orders")]


def paid_amounts(env) -> list[int]:
    with connect(env.runtime.gateway._bank.store.path) as connection:
        rows = [dict(row) for row in connection.execute(
            "SELECT amount_fen FROM ledger_entries WHERE user_id = 'U1' "
            "AND account_id = 'A1' AND nature = 'consumption' "
            "AND operation_id NOT LIKE 'seed:%' ORDER BY rowid")]
    return [row["amount_fen"] for row in rows]


def freeze_row(env) -> dict:
    rows = _all_freezes(env.runtime)
    assert len(rows) == 1
    return rows[0]


# ---------------------------------------------------- freeze-card continuation


def test_identical_freeze_after_edit_is_a_new_operation_not_a_retired_block(
    continuation_env,
):
    env = continuation_env
    card = drive_to_freeze_confirmation(env)
    old = actions(env)["freeze"]
    binding = env.snapshot()["birthday_edit_option"]
    outcome = begin_edit(env, card)
    assert outcome.result.status is TaskStatus.WAITING_INPUT
    assert retirement_of(env, old).state == "sealed"

    # A duplicate edit click replays the one published edit: same winner, the
    # same sealed retirement, and the live attempt is still the retired one until
    # the flow actually re-checks the binding.
    replay = env.runtime.birthday.handoff.begin_birthday_edit(
        env.who, request_id=uuid4(),
        interaction_id=card.interaction.interaction_id,
        option_id=next(item.id for item in card.interaction.options
                       if item.label == EDIT_OPTION_LABEL))
    assert replay.published_ref == outcome.published_ref
    assert replay.result.interaction.interaction_id == (
        outcome.result.interaction.interaction_id)
    assert retirement_of(env, old).state == "sealed"
    assert actions(env)["freeze"]["operation_id"] == old["operation_id"]

    # Continue the unchanged plan: the same freeze parameters must become a new
    # operation and reach a fresh confirmation instead of ACTION_RETIRED.
    current = env.resume({"selected_option_id": option_id(outcome.result, "就选这些")})
    current = env.resume(
        {"selected_option_id": option_id(current, "采用并开始办理")})

    assert current.interaction is not None
    assert current.interaction.kind == "confirmation", current.message
    assert_still_running(env)
    new = actions(env)["freeze"]
    assert_new_attempt(env, old, new, binding)
    # A duplicate same-binding evaluation reuses that one new attempt: the
    # retired operation is not resurrected and no third operation appears.
    ports = env.runtime.birthday.ports_factory(env.who)
    again = ports._action(env.who, "freeze", new["parameters"])
    assert again["operation_id"] == new["operation_id"]
    assert actions(env)["freeze"] == new
    assert len([item for item in attempts(env)
                if item["parameters"]["__action__"] == "bank.freeze_funds"]) == 1
    # Nothing moved and the task was not settled by the retirement.
    assert _all_freezes(env.runtime) == []
    assert paid_amounts(env) == []
    assert orders(env) == []

    # The new attempt is a real write under its own confirmation/verification.
    frozen = settle_confirmation(env, current)
    assert frozen.interaction.kind == "confirmation"  # first order card
    freeze = freeze_row(env)
    assert freeze["original_amount_fen"] == 50000
    assert freeze["released_total_fen"] == 0
    assert bank_operation(env, old["operation_id"]).lookup == "not_found"
    assert bank_operation(env, new["operation_id"]).lookup == "found"


# ----------------------------------------------------- order-card continuation


def test_identical_order_after_edit_is_a_new_operation_and_creates_one_order(
    continuation_env,
):
    env = continuation_env
    freeze_card = drive_to_freeze_confirmation(env)
    order_card = settle_confirmation(env, freeze_card)
    assert order_card.interaction.kind == "confirmation"
    key = key_for(env, "order:item/")
    old = actions(env)[key]
    binding = env.snapshot()["birthday_edit_option"]

    outcome = begin_edit(env, order_card)
    assert outcome.result.status is TaskStatus.WAITING_INPUT
    assert retirement_of(env, old).state == "sealed"
    current = env.resume(
        {"selected_option_id": option_id(outcome.result, "按新方案继续")})

    assert current.interaction is not None
    assert current.interaction.kind == "confirmation", current.message
    assert_still_running(env)
    new = actions(env)[key]
    assert_new_attempt(env, old, new, binding)
    # The retired order attempt never created an order; the freeze stays intact
    # and nothing was released by the interruption.
    assert orders(env) == []
    assert paid_amounts(env) == []
    assert freeze_row(env)["released_total_fen"] == 0

    placed = settle_confirmation(env, current)
    assert placed.interaction.kind == "confirmation"  # the same item's capture
    rows = orders(env)
    assert len(rows) == 1
    assert rows[0]["quantity"] == 1 and rows[0]["total_fen"] == 19900
    assert paid_amounts(env) == []
    assert freeze_row(env)["captured_total_fen"] == 0
    assert bank_operation(env, old["operation_id"]).lookup == "not_found"
    assert bank_operation(env, new["operation_id"]).lookup == "found"


# --------------------------------------------------- capture-card continuation


def test_identical_capture_after_edit_is_a_new_operation_and_pays_once(
    continuation_env,
):
    env = continuation_env
    freeze_card = drive_to_freeze_confirmation(env)
    order_card = settle_confirmation(env, freeze_card)
    capture_card = settle_confirmation(env, order_card)
    assert capture_card.interaction.kind == "confirmation"
    key = key_for(env, "capture:item/")
    old = actions(env)[key]
    binding = env.snapshot()["birthday_edit_option"]

    outcome = begin_edit(env, capture_card)
    assert outcome.result.status is TaskStatus.WAITING_INPUT
    assert retirement_of(env, old).state == "sealed"
    current = env.resume(
        {"selected_option_id": option_id(outcome.result, "按新方案继续")})

    assert current.interaction is not None
    assert current.interaction.kind == "confirmation", current.message
    assert_still_running(env)
    new = actions(env)[key]
    assert_new_attempt(env, old, new, binding)
    # The created (unpaid) order and the freeze are untouched; no charge and no
    # release happened while the retired payment attempt was replaced.
    assert len(orders(env)) == 1
    assert paid_amounts(env) == []
    assert freeze_row(env)["captured_total_fen"] == 0
    assert freeze_row(env)["released_total_fen"] == 0

    paid = settle_confirmation(env, current)
    assert paid.interaction.kind == "confirmation"  # the second item's order
    assert paid_amounts(env) == [19900]
    assert len(orders(env)) == 1
    assert freeze_row(env)["captured_total_fen"] == 19900
    assert freeze_row(env)["released_total_fen"] == 0
    assert bank_operation(env, old["operation_id"]).lookup == "not_found"
    assert bank_operation(env, new["operation_id"]).lookup == "found"
