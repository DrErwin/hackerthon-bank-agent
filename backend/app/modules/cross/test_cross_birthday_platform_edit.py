"""Ticket v05-cross-business/08 on the real platform composition.

The Cross edit side is exercised through the *real* Harness publication seam
(platform 03), the real ticket-05 seal, the real security gate, the real mock
bank and the real Cross flow; only the chat planner is the composition's fixed
test model. This is the layer that proves the quantity and stable-item work is
not a scripted-port illusion:

1. The controlled edit from a freeze wait publishes a new ordinary input with a
   recomputed plan (quantity 2 = 398) and no dropped old confirmation.
2. After a completed freeze, a quantity edit re-confirms the *same stable item*
   and reaches the real bank as quantity=2 / total 398 with a fresh operation;
   the retired confirmation stays readable by its original operation id.
3. A same-product replacement is a new stable execution item with its own order
   and payment; the already paid item and its operation numbers are untouched.
4. Known platform gap (reported, not patched from Cross): when the retired
   attempt is re-checked with identical parameters (a freeze keeps the same
   account/cap/reason), the security gate refuses it as retired and Cross stops
   honestly with no second freeze; a new-attempt seam belongs to the platform
   directory.
"""

from uuid import uuid4

import pytest

from app.agent_platform.birthday_edit import EDIT_OPTION_LABEL
from app.agent_platform.test_birthday_runtime_wiring import (
    DELIVERY_REF, answer_verification, approve_confirmation, composition, option_id,
    trusted,
)
from app.contracts.common import TaskStatus
from app.storage.database import connect

from .birthday_handoff import BirthdayHandoffAdapter

INTENT = "给妈妈过生日，安排花和蛋糕"
ORDER_PREFIX = "order:item/"
_UNSET = object()


class HarnessEnvironment:
    def __init__(self, runtime, request_id):
        self.runtime = runtime
        self.request_id = request_id
        self.who = trusted(runtime)
        self.last_run_id = self.who.run_id

    def task(self):
        return self.runtime.application.get_task("U1", "D1", "BIRTHDAY")

    def snapshot(self) -> dict:
        return self.task().snapshot or {}

    def published_ref(self) -> dict:
        return self.snapshot()["birthday_g3"]["published_ref"]

    def start(self):
        return self.runtime.harness.handle_message(self.who, self.request_id, INTENT)

    def resume(self, response: dict, *, request_id=_UNSET):
        who = self.who.model_copy(update={"run_id": str(uuid4())})
        self.last_run_id = who.run_id
        return self.runtime.harness.resume(
            who, response,
            request_id=uuid4() if request_id is _UNSET else request_id)


@pytest.fixture()
def env(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    request_id = uuid4()
    task = runtime.application.get_task("U1", "D1", "BIRTHDAY")
    runtime.application.update_task(
        "U1", "D1", "BIRTHDAY", task.revision, task.run_id, task.status,
        task.checkpoint_id,
        {
            **task.snapshot,
            "request_id": str(request_id),
            "intent_text": INTENT,
            "config_version": runtime.harness.planner.config_version,
            "proposal": {"capability_name": "cross.start_task"},
            "bill_source_task_id": None,
            "bill_scope": None,
            "selected_capability": None,
        },
    )
    runtime.birthday.handoff.cross = BirthdayHandoffAdapter(
        runtime.gateway._bank.clock)
    environment = HarnessEnvironment(runtime, request_id)
    try:
        yield environment
    finally:
        runtime.gateway.close()


# ------------------------------------------------------------------- helpers


def start_to_freeze(env, *, budget="500元"):
    current = env.start()
    assert current.status is TaskStatus.WAITING_INPUT, current.message
    assert "预算" in current.message
    current = env.resume({"text": budget})
    current = env.resume({"text": "2026-10-30"})
    current = env.resume({"text": DELIVERY_REF})
    current = env.resume({"selected_option_id": option_id(current, "鲜花")})
    current = env.resume({"selected_option_id": option_id(current, "蛋糕")})
    current = env.resume({"selected_option_id": option_id(current, "就选这些")})
    current = env.resume(
        {"selected_option_id": option_id(current, "采用并开始办理")})
    assert current.interaction is not None
    assert current.interaction.kind == "confirmation"
    return current


def settle_confirmation(env, card):
    """Approve one confirmation, answer its step-up code, continue the write."""
    assert card.interaction.kind == "confirmation", card.message
    approve_confirmation(env.runtime, env.who, card.interaction.record_ref)
    waiting = env.resume({"choice": "approve"})
    assert waiting.interaction.kind == "verification", waiting.message
    answer_verification(env.runtime, env.who, "R1",
                        waiting.interaction.record_ref)
    return env.resume({"choice": "resume"})


def edit_option(card):
    matches = [item for item in card.interaction.options
               if item.label == EDIT_OPTION_LABEL]
    assert len(matches) == 1, [item.label for item in card.interaction.options]
    return matches[0]


def begin_edit(env, card):
    return env.runtime.birthday.handoff.begin_birthday_edit(
        env.who, request_id=uuid4(),
        interaction_id=card.interaction.interaction_id,
        option_id=edit_option(card).id)


def actions(env) -> dict:
    return env.snapshot().get("birthday_actions") or {}


def attempts(env) -> list[dict]:
    return env.snapshot().get("birthday_attempts") or []


def cross_state(env) -> dict:
    """The exact published Cross state (the only readable source after G3)."""
    from app.memory.adapter import MemoryContext

    ref = env.published_ref()
    saved = env.runtime.memory.checkpointer(
        MemoryContext("U1", "S1", "D1"), "BIRTHDAY").get_tuple(
        {"configurable": {"thread_id": ref["thread_id"],
                          "checkpoint_ns": ref["checkpoint_ns"],
                          "checkpoint_id": ref["checkpoint_id"]}})
    assert saved is not None
    return saved.checkpoint["channel_values"]["cross_state"]


def paid_amounts(env) -> list[int]:
    with connect(env.runtime.gateway._bank.store.path) as connection:
        rows = [dict(row) for row in connection.execute(
            "SELECT amount_fen FROM ledger_entries WHERE user_id = 'U1' "
            "AND account_id = 'A1' AND nature = 'consumption' "
            "AND operation_id NOT LIKE 'seed:%' ORDER BY rowid")]
    return [row["amount_fen"] for row in rows]


def orders(env) -> list[dict]:
    with connect(env.runtime.gateway._bank.store.path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM orders")]


def freezes(env) -> list[dict]:
    with connect(env.runtime.gateway._bank.store.path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM freezes")]


def confirmation_fields(env, record_ref):
    record = env.runtime.confirmations.get(
        env.runtime._context(env.who, None, None), record_ref)
    return {field.name: field.value_text for field in record.display_fields}


# ------------------------------------------------ edit input from a freeze


def test_freeze_wait_edit_publishes_a_new_recomputed_input(env):
    card = start_to_freeze(env, budget="800元")
    outcome = begin_edit(env, card)
    assert outcome.result.status is TaskStatus.WAITING_INPUT
    assert outcome.result.interaction.kind == "input"
    assert outcome.result.interaction.interaction_id != (
        card.interaction.interaction_id)
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "edit"
    # The old card's approval option is not the live input any more.
    assert env.snapshot()["result"]["interaction"]["interaction_id"] == (
        outcome.result.interaction.interaction_id)

    new_card = outcome.result
    current = env.resume({"selected_option_id": option_id(
        new_card, "改数量：鲜花礼盒")})
    assert "数量" in current.message
    current = env.resume({"text": "2"})
    assert "×2" in current.message and "398.00" in current.message
    current = env.resume({"selected_option_id": option_id(
        current, "就选这些，继续")})
    # The recomputed adoption page is a *new* interaction; nothing was frozen.
    assert current.status is TaskStatus.WAITING_INPUT
    assert "×2" in current.message and "398.00" in current.message
    assert "采用并开始办理" in " ".join(item.label
                                        for item in current.interaction.options)
    assert freezes(env) == []


# ------------------------------------------- quantity after a completed freeze


def test_quantity_edit_after_the_freeze_reaches_the_bank(env):
    freeze_card = start_to_freeze(env, budget="800元")
    flower_card = settle_confirmation(env, freeze_card)  # freeze completed
    assert flower_card.interaction.kind == "confirmation"
    original_actions = actions(env)
    original_key = next(key for key in original_actions
                        if key.startswith(ORDER_PREFIX))
    original = original_actions[original_key]
    original_operation = original["operation_id"]
    item_id = original["parameters"]["item_id"]

    outcome = begin_edit(env, flower_card)
    assert outcome.result.status is TaskStatus.WAITING_INPUT
    assert outcome.result.interaction.interaction_id != (
        flower_card.interaction.interaction_id)
    new_card = outcome.result
    current = env.resume({"selected_option_id": option_id(
        new_card, "改数量：鲜花礼盒")})
    current = env.resume({"text": "2"})
    current = env.resume({"selected_option_id": option_id(
        current, "按新方案继续")})
    assert current.interaction.kind == "confirmation"
    fields = confirmation_fields(env, current.interaction.record_ref)
    assert fields["quantity"] == "2 件"
    assert fields["unit_price"] == "199.00 元"
    assert fields["amount"] == "398.00 元"
    assert fields["account"] == "A1"
    assert fields["deliver_by"].startswith("2026-10-30")

    # The new confirmation is a new attempt for the same stable item.
    row_ids = {row["item_id"] for row in cross_state(env)["birthday"]["orders"]}
    live = actions(env)[original_key]
    assert live["parameters"]["item_id"] == item_id  # identity did not change
    assert live["parameters"]["request"]["quantity"] == 2
    assert live["parameters"]["request"]["expected_total_fen"] == 39800
    assert live["operation_id"] != original_operation
    # The replaced attempt is readable by its original operation number.
    retired = [entry for entry in attempts(env)
               if entry["operation_id"] == original_operation]
    assert len(retired) == 1
    assert retired[0]["parameters"]["request"]["quantity"] == 1
    assert item_id in row_ids and len(row_ids) == 2

    capture_card = settle_confirmation(env, current)  # order created qty 2
    bank_orders = orders(env)
    assert len(bank_orders) == 1
    assert bank_orders[0]["quantity"] == 2
    assert bank_orders[0]["total_fen"] == 39800

    cake_card = settle_confirmation(env, capture_card)  # paid 398
    assert cake_card.interaction.kind == "confirmation"
    paid = settle_confirmation(env, cake_card)  # cake order created
    done = settle_confirmation(env, paid)  # cake paid, remainder released
    assert done.status is TaskStatus.SUCCEEDED, done.message
    assert "鲜花礼盒 ×2" in done.message
    assert "释放 134.00 元" in done.message
    assert paid_amounts(env) == [39800, 26800]
    freeze = freezes(env)
    assert len(freeze) == 1
    assert freeze[0]["captured_total_fen"] == 66600
    assert freeze[0]["released_total_fen"] == 13400


# ------------------------------------------------- same-product replacement


def test_same_product_replacement_is_a_new_item_and_a_new_payment(env):
    freeze_card = start_to_freeze(env, budget="800元")
    flower_card = settle_confirmation(env, freeze_card)
    capture_card = settle_confirmation(env, flower_card)  # flower order created
    cake_card = settle_confirmation(env, capture_card)  # flower paid
    assert cake_card.interaction.kind == "confirmation"

    paid_row = cross_state(env)["birthday"]["orders"][0]
    paid_item = paid_row["item_id"]
    paid_order = {key: value for key, value in actions(env).items()
                  if key.startswith(ORDER_PREFIX)}[ORDER_PREFIX + paid_item]
    paid_operation = paid_order["operation_id"]

    new_card = begin_edit(env, cake_card).result
    current = env.resume({"selected_option_id": option_id(
        new_card, "替换：生日蛋糕")})
    current = env.resume({"selected_option_id": option_id(
        current, "鲜花礼盒")})
    current = env.resume({"selected_option_id": option_id(
        current, "按新方案继续")})
    assert current.interaction.kind == "confirmation"  # the new item's order

    capture_card = settle_confirmation(env, current)  # new flower ordered
    done = settle_confirmation(env, capture_card)  # new flower paid
    assert done.status is TaskStatus.SUCCEEDED, done.message
    assert "释放 402.00 元" in done.message
    bank_orders = orders(env)
    assert len(bank_orders) == 2
    assert {row["quantity"] for row in bank_orders} == {1}
    assert paid_amounts(env) == [19900, 19900]

    after = actions(env)
    assert after[ORDER_PREFIX + paid_item]["operation_id"] == paid_operation
    rows = cross_state(env)["birthday"]["orders"]
    assert len(rows) == 2
    item_ids = {row["item_id"] for row in rows}
    assert len(item_ids) == 2 and paid_item in item_ids
    new_row = next(row for row in rows if row["item_id"] != paid_item)
    assert new_row["product_id"] == "p_flower"  # same product, new item
    # No cake order was ever created: the replacement changed the plan item.
    assert all(order["product_id"] == "p_flower" for order in bank_orders)


# -------------------------------------------------- reported platform gap


def test_identical_refreeze_after_retirement_stops_without_a_second_freeze(env):
    """Known platform gap, reported in the hand-in (not patched from Cross).

    Ticket 03 retires the unsubmitted freeze attempt. The action binding reuses
    an attempt whose parameters are identical, so the security gate refuses it
    as retired; Cross must stop honestly instead of double freezing or
    pretending the edit succeeded. A new-attempt seam after a proven retirement
    belongs to the platform directory.
    """
    freeze_card = start_to_freeze(env, budget="500元")
    new_card = begin_edit(env, freeze_card).result
    current = env.resume({"selected_option_id": option_id(new_card, "就选这些")})
    current = env.resume(
        {"selected_option_id": option_id(current, "采用并开始办理")})
    assert current.status is TaskStatus.CANCELLED, current.message
    assert "没有冻结资金" in current.message
    assert freezes(env) == []
    assert orders(env) == []
    assert paid_amounts(env) == []
