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

from copy import deepcopy
from uuid import UUID, uuid4

import pytest

from app.agent_platform.birthday_edit import EDIT_OPTION_LABEL
from app.agent_platform.test_birthday_runtime_wiring import (
    DELIVER_DATE, DELIVERY_REF, answer_verification, approve_confirmation, composition, option_id,
    trusted,
)
from app.contracts.common import TaskStatus
from app.contracts.platform import StartTransferInput
from app.storage.database import connect

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
    current = env.resume({"text": DELIVER_DATE})
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


def bank_orders(runtime) -> list[dict]:
    with connect(runtime.gateway._bank.store.path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM orders")]


def orders(env) -> list[dict]:
    return bank_orders(env.runtime)


def freezes(env) -> list[dict]:
    with connect(env.runtime.gateway._bank.store.path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM freezes")]


def confirmation_fields_for(runtime, who, record_ref):
    record = runtime.confirmations.get(
        runtime._context(who, None, None), record_ref)
    return {field.name: field.value_text for field in record.display_fields}


def confirmation_fields(env, record_ref):
    return confirmation_fields_for(env.runtime, env.who, record_ref)


# ------------------------------------------------- composition-level mounting


def test_real_composition_mounts_the_cross_handoff(env):
    """Ticket 08's implementation is mounted by ``register_cross`` itself.

    No test here assigns ``birthday.handoff.cross``: the real composition must
    find the Cross candidate preparation, so the platform edit entry never
    refuses with ``CROSS_HANDOFF_UNAVAILABLE``.
    """
    handoff = env.runtime.birthday.handoff
    assert handoff.cross is not None
    assert callable(handoff.cross.prepare)
    # Behavioural proof through the real entry: the edit option published on the
    # real card reaches Cross and a new input card is published.
    card = start_to_freeze(env, budget="800元")
    outcome = begin_edit(env, card)
    assert outcome.result.status is TaskStatus.WAITING_INPUT
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "edit"


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
    assert fields["account"] == "主账户（尾号 0001）"
    assert fields["deliver_by"].startswith(f"{int(DELIVER_DATE[:4])}年{int(DELIVER_DATE[5:7])}月{int(DELIVER_DATE[8:])}日")

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
    assert "没花完的 134.00 元已退回原卡" in done.message
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
    assert "没花完的 402.00 元已退回原卡" in done.message
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


# ------------------------------------ same-parameter continuation after edit
#
# Ticket 03 retires the unsubmitted attempt. Before platform 09's continuation
# seam Cross must fail closed (keep the task/facts, release nothing); after 09
# the same parameters build a *new* attempt/operation and reach a fresh
# confirmation. These tests run against whichever platform is present in the
# tree, so they stay green before and after 09; the new-attempt branch is
# verified against 09's birthday_runtime change in the hand-in.


def freeze_released_fen(env) -> int:
    rows = freezes(env)
    return int(rows[0]["released_total_fen"] or 0) if rows else 0


def platform_retries_same_parameter_attempt(runtime) -> bool:
    """True when platform ticket 09's sealed-retirement new-attempt seam exists."""
    return hasattr(runtime.birthday.ports_factory(None), "_sealed_retirement")


def sealed_retirement(env, action: dict) -> bool:
    """The old attempt's security retirement is permanently sealed (02)."""
    operation_id = UUID(str(action["operation_id"]))
    revision = int(action["action_revision"])
    context = env.runtime._context(env.who, operation_id, revision)
    record = env.runtime.confirmations.state.get_retirement(
        context, env.who.task_id, operation_id, revision)
    return record is not None and record.state == "sealed"


def assert_new_attempt(env, before: dict, key: str) -> dict:
    """Ticket 09: same facts, new operation, previous attempt preserved/sealed."""
    live = actions(env)[key]
    assert live["operation_id"] != before["operation_id"]
    assert live["parameters"] == before["parameters"]
    assert int(live["action_revision"]) > int(before["action_revision"])
    assert sealed_retirement(env, before)
    assert any(attempt["operation_id"] == before["operation_id"]
               for attempt in attempts(env))
    return live


def test_freeze_wait_edit_continue_keeps_the_task_open_without_release(env):
    card = start_to_freeze(env, budget="800元")
    old_action = deepcopy(actions(env)["freeze"])
    new_card = begin_edit(env, card).result
    current = env.resume({"selected_option_id": option_id(new_card, "就选这些")})
    current = env.resume(
        {"selected_option_id": option_id(current, "采用并开始办理")})
    if platform_retries_same_parameter_attempt(env.runtime):
        # Platform 09: identical freeze parameters become a new attempt and a
        # fresh confirmation; no freeze exists yet and nothing was released.
        assert current.status is TaskStatus.WAITING_APPROVAL, current.message
        assert current.interaction.kind == "confirmation"
        assert_new_attempt(env, old_action, "freeze")
        assert env.task().status is TaskStatus.WAITING_APPROVAL
    else:
        assert current.status is TaskStatus.WAITING_INPUT, current.message
        assert "已由平台安全撤离" in current.message
        assert "未释放" in current.message
        assert env.task().status is TaskStatus.WAITING_INPUT
    assert freezes(env) == []
    assert orders(env) == [] and paid_amounts(env) == []


def test_order_wait_edit_continue_keeps_the_task_open_and_the_freeze(env):
    freeze_card = start_to_freeze(env, budget="800元")
    flower_card = settle_confirmation(env, freeze_card)
    original_key = next(key for key in actions(env)
                        if key.startswith(ORDER_PREFIX))
    old_action = deepcopy(actions(env)[original_key])
    new_card = begin_edit(env, flower_card).result
    current = env.resume({"selected_option_id": option_id(
        new_card, "按新方案继续")})
    if platform_retries_same_parameter_attempt(env.runtime):
        assert current.status is TaskStatus.WAITING_APPROVAL, current.message
        assert current.interaction.kind == "confirmation"
        assert_new_attempt(env, old_action, original_key)
    else:
        assert current.status is TaskStatus.WAITING_INPUT, current.message
        assert "已由平台安全撤离" in current.message
        assert actions(env)[original_key]["operation_id"] == (
            old_action["operation_id"])
        # A retry while the seam is missing stays recoverable and never turns
        # into a stop/release.
        current = env.resume({"selected_option_id": option_id(
            current, "稍后再试")})
        assert current.status is TaskStatus.WAITING_INPUT, current.message
    assert env.task().status is not TaskStatus.CANCELLED
    assert freeze_released_fen(env) == 0
    assert orders(env) == [] and paid_amounts(env) == []


def test_capture_wait_edit_continue_keeps_paid_facts_and_the_freeze(env):
    freeze_card = start_to_freeze(env, budget="800元")
    flower_card = settle_confirmation(env, freeze_card)
    capture_card = settle_confirmation(env, flower_card)
    cake_order_card = settle_confirmation(env, capture_card)  # flower paid
    cake_capture_card = settle_confirmation(env, cake_order_card)
    assert cake_capture_card.interaction.kind == "confirmation"
    before_orders = orders(env)
    before_paid = paid_amounts(env)
    cake_item = cross_state(env)["birthday"]["orders"][1]["item_id"]
    capture_key = f"capture:item/{cake_item}"
    old_action = deepcopy(actions(env)[capture_key])
    new_card = begin_edit(env, cake_capture_card).result
    current = env.resume({"selected_option_id": option_id(
        new_card, "按新方案继续")})
    if platform_retries_same_parameter_attempt(env.runtime):
        assert current.status is TaskStatus.WAITING_APPROVAL, current.message
        assert current.interaction.kind == "confirmation"
        assert_new_attempt(env, old_action, capture_key)
    else:
        assert current.status is TaskStatus.WAITING_INPUT, current.message
        assert "已由平台安全撤离" in current.message
    assert env.task().status is not TaskStatus.CANCELLED
    assert paid_amounts(env) == before_paid == [19900]
    assert orders(env) == before_orders
    assert freeze_released_fen(env) == 0


# --------------------------- price change re-adoption (spec §7, real chain)


def drive_entry_to_freeze(entry, who):
    """Direct entry drive on the real composition (no G3 harness publication)."""
    started = entry.start(who, StartTransferInput(
        request_id=uuid4(), intent_text=INTENT))
    assert started.status is TaskStatus.WAITING_INPUT, started.message
    current = entry.resume(who, {"text": "500元"})
    current = entry.resume(who, {"text": DELIVER_DATE})
    current = entry.resume(who, {"text": DELIVERY_REF})
    current = entry.resume(who, {"selected_option_id": option_id(current, "鲜花")})
    current = entry.resume(who, {"selected_option_id": option_id(current, "蛋糕")})
    current = entry.resume(who, {"selected_option_id": option_id(current, "就选这些")})
    return entry.resume(
        who, {"selected_option_id": option_id(current, "采用并开始办理")})


def test_changed_quote_re_adopts_and_reconfirms_on_the_real_platform(tmp_path):
    """A changed price is a new plan version and a new attempt (spec §7).

    The real gate, bank and platform ports are used. The task's adopted quote is
    made stale (189.00) before the freeze executes; when the order step re-reads
    the real 199.00 price, the row must be recomputed and a *new* order check /
    confirmation must be produced. Nothing is written straight to the bank and
    no approval on the price card can execute the new amount.
    """
    runtime, entry = composition(tmp_path)
    who = trusted(runtime)
    try:
        freeze_card = drive_entry_to_freeze(entry, who)
        assert freeze_card.interaction.kind == "confirmation"
        _saved, state = entry._load(who, None)
        stale = state["birthday"]["orders"][0]
        stale["unit_price_fen"] = 18900
        stale["amount_fen"] = 18900
        entry._save(who, None, state)

        approve_confirmation(runtime, who, freeze_card.interaction.record_ref)
        waiting = entry.resume(who, {"choice": "approve"})
        assert waiting.interaction.kind == "verification"
        answer_verification(runtime, who, "R1", waiting.interaction.record_ref)
        price_card = entry.resume(who, {"choice": "resume"})
        # The real freeze completed; the changed price is surfaced before any
        # order is checked or written.
        assert price_card.status is TaskStatus.WAITING_INPUT, price_card.message
        assert "价格已从 189.00 元变为 199.00 元" in price_card.message
        assert "重新采用方案并确认" in price_card.message
        assert bank_orders(runtime) == []
        revision_before = entry._load(who, None)[1]["plan_revision"]

        # An approval on the price card never executes the new amount.
        with pytest.raises(ValueError, match="INVALID_OPTION"):
            entry.resume(who, {"choice": "approve"})
        assert bank_orders(runtime) == []

        confirmation = entry.resume(
            who, {"selected_option_id": option_id(price_card, "按新价")})
        # New plan revision + new order_check attempt, then the user confirms.
        assert confirmation.interaction.kind == "confirmation"
        assert entry._load(who, None)[1]["plan_revision"] > revision_before
        fields = confirmation_fields_for(
            runtime, who, confirmation.interaction.record_ref)
        assert fields["amount"] == "199.00 元"
        assert fields["unit_price"] == "199.00 元"
        assert bank_orders(runtime) == []  # only after the new approval
        item_id = entry._load(who, None)[1]["birthday"]["orders"][0]["item_id"]
        live = (runtime.application.get_task("U1", "D1", "BIRTHDAY")
                .snapshot.get("birthday_actions") or {})[ORDER_PREFIX + item_id]
        assert live["parameters"]["amount_fen"] == 19900
        assert live["parameters"]["request"]["expected_total_fen"] == 19900

        approve_confirmation(runtime, who, confirmation.interaction.record_ref)
        waiting = entry.resume(who, {"choice": "approve"})
        assert waiting.interaction.kind == "verification"
        answer_verification(runtime, who, "R1", waiting.interaction.record_ref)
        entry.resume(who, {"choice": "resume"})
        created = bank_orders(runtime)
        assert len(created) == 1
        assert created[0]["quantity"] == 1
        assert created[0]["total_fen"] == 19900
    finally:
        runtime.gateway.close()
