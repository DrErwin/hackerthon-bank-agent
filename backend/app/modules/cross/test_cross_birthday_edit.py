"""Ticket v05-cross-business/08: quantities, stable items and the controlled edit.

Failure modes this file pins down first (the code is written to these):

1. A quantity is only a positive integer the server recomputes; "0", "两束",
   "-1" and an empty basket must never freeze, order or pay.
2. Every plan row carries a server-side stable ``item_id`` separate from
   ``product_id``: an edit keeps the identity of an unchanged item across plan
   revisions, a same-product replacement gets a new item id, and order/capture
   attempts are keyed by that item, never by ``product_id`` or ``plan_revision``.
3. Editing at a confirmation/verification wait publishes a *new* input
   interaction; the old card's interaction/option ids cannot execute the new
   plan, and paid / created-unpaid / failed / unknown facts are never rewritten.
4. A new plan is recomputed from unit price x quantity, re-adopted (before the
   freeze) or re-confirmed (after it), and an over-cap result writes nothing.
5. The second basis: only an explicit bank failure that the original operation
   query re-verifies as "failed, no order, nothing in flight" offers a new
   ordinary input replacement (new item, new attempts); an unverifiable outcome
   stays skip/stop, never a replacement.
6. ``CrossBirthdayHandoff.prepare`` only returns content for the reserved
   candidate ref: it reads the exact source state, never writes the saver, and
   refuses a foreign actor or a non-edit request.
"""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest

from app.agent_platform.birthday_edit import (
    BirthdayEditError, CandidateRequest, CrossCandidate,
)
from app.contracts.bank import Product
from app.contracts.common import TaskStatus
from app.contracts.cross import CrossStartInput
from app.contracts.platform import TrustedContext
from app.modules.cross.birthday import BirthdayFlow
from app.modules.cross.birthday_handoff import BirthdayHandoffAdapter
from app.storage.checkpoints import CheckpointRef

from .test_cross_birthday import (
    CAKE, FLOWER, ScriptedBirthdayPorts, birthday_composition, option_id,
    run_to_freeze, store_delivery,
)
from .test_cross_expense import NOW, parent_trusted

GIFT = Product(product_id="P_GIFT", merchant_id="M_GIFT", merchant_name="礼物铺",
               product_name="保温杯", unit_price_fen=9900, category="other",
               earliest_delivery_at=NOW)

HANDOFF = BirthdayHandoffAdapter(lambda: NOW)


class EditPorts(ScriptedBirthdayPorts):
    """Scripted ports that also record the item dicts Cross really sent."""

    def __init__(self, *, verify_failures=False, **kwargs):
        super().__init__(**kwargs)
        self.order_items: list[dict] = []
        self.capture_items: list[dict] = []
        self.order_checks: list[dict] = []
        self.failed_orders: list[str] = []
        self.failed_requeries: dict[str, object] = {}
        self.verify_failures = verify_failures

    def order_check(self, context, plan, item):
        from app.contracts.common import SecurityDecisionCode
        from app.modules.cross.birthday_ports import GateAnswer
        from .test_cross_birthday import gate_confirmation
        self.order_checks.append(deepcopy(item))
        return GateAnswer(
            decision=SecurityDecisionCode.REQUIRE_CONFIRMATION,
            operation_id=str(uuid4()),
            interaction=gate_confirmation(
                "order", f"下单 {item['name']} ×{item['quantity']}，"
                         f"金额 {item['amount_fen'] / 100:.2f} 元"))

    def capture_check(self, context, plan, item, order_id):
        from app.contracts.common import SecurityDecisionCode
        from app.modules.cross.birthday_ports import GateAnswer
        from .test_cross_birthday import gate_confirmation
        return GateAnswer(
            decision=SecurityDecisionCode.REQUIRE_CONFIRMATION,
            operation_id=str(uuid4()),
            interaction=gate_confirmation(
                "capture", f"按订单付款 {item['name']} ×{item['quantity']}，"
                           f"金额 {item['amount_fen'] / 100:.2f} 元"))

    def order_execute(self, context, plan, item):
        from app.modules.cross.birthday_ports import WriteOutcome
        self.order_items.append(deepcopy(item))
        state = self.orders_script.pop(0) if self.orders_script else "completed"
        if state == "failed":
            operation_id = str(uuid4())
            self.failed_orders.append(operation_id)
            if self.verify_failures is True:
                self.failed_requeries[operation_id] = WriteOutcome(
                    executed=True, state="failed",
                    result=self._failed_operation_result(operation_id),
                    operation_id=operation_id)
            elif self.verify_failures == "weak":
                # The port says failed but the original OperationResult is not
                # readable: that is not enough to prove "no order".
                self.failed_requeries[operation_id] = WriteOutcome(
                    executed=True, state="failed", result=None,
                    operation_id=operation_id)
            return type(self)._write_failure(operation_id)
        if state == "unknown":
            unknown = WriteOutcome(executed=True, state="unknown", result=None,
                                   operation_id=str(uuid4()))
            self.last_order_op = unknown.operation_id
            return unknown
        from .test_cross_birthday import completed_order
        return completed_order(item["product_id"])

    @staticmethod
    def _failed_operation_result(operation_id):
        from app.contracts.bank import BankError, OperationResult
        from app.contracts.common import OperationStatus
        return OperationResult(
            operation_id=UUID(operation_id), operation_type="bank.create_order",
            operation_status=OperationStatus.FAILED,
            recorded_at=NOW, updated_at=NOW, receipt=None,
            failure=BankError(code="PRODUCT_UNAVAILABLE", details={}))

    @staticmethod
    def _write_failure(operation_id):
        from app.modules.cross.birthday_ports import WriteOutcome
        return WriteOutcome(executed=True, state="failed", result=None,
                            operation_id=operation_id)

    def capture_execute(self, context, plan, item, order_id):
        from app.modules.cross.birthday_ports import WriteOutcome
        from .test_cross_birthday import completed_capture
        self.capture_items.append({**deepcopy(item), "order_id": order_id})
        state = self.captures_script.pop(0) if self.captures_script else "completed"
        if state == "unknown":
            unknown = WriteOutcome(executed=True, state="unknown", result=None,
                                   operation_id=str(uuid4()))
            self.last_capture_op = unknown.operation_id
            return unknown
        if state == "failed":
            return WriteOutcome(executed=True, state="failed", result=None,
                                operation_id=str(uuid4()))
        return completed_capture(item["product_id"])

    def requery(self, context, plan, target, operation_id):
        result = super().requery(context, plan, target, operation_id)
        if result is None:
            return self.failed_requeries.get(operation_id)
        return result


def start_to_pick(entry, *, budget="500元"):
    started = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="给妈妈过生日，安排花和蛋糕"))
    assert started.status is TaskStatus.WAITING_INPUT, started.message
    current = entry.resume(parent_trusted(), {"text": budget})
    assert current.status is TaskStatus.WAITING_INPUT
    current = entry.resume(parent_trusted(), {"text": "2026-10-30"})
    return entry.resume(parent_trusted(), {"text": "deliver-ref-0001"})


def pick(entry, current, needle):
    return entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(current, needle)})


def select(entry, current, needle):
    return entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(current, needle)})


def to_order_card(entry, *, budget="500元", picks=("康乃馨", "蛋糕")):
    """Pick the products, adopt and settle the freeze, stop at the first
    order confirmation (the real write path)."""
    current = start_to_pick(entry, budget=budget)
    for needle in picks:
        current = pick(entry, current, needle)
    current = select(entry, current, "就选这些")
    current = select(entry, current, "采用并开始办理")
    assert current.interaction.kind == "confirmation"
    return entry.resume(parent_trusted(), {"choice": "approve"})


def to_freeze_card(entry, *, budget="500元", picks=("康乃馨", "蛋糕")):
    current = start_to_pick(entry, budget=budget)
    for needle in picks:
        current = pick(entry, current, needle)
    current = select(entry, current, "就选这些")
    return select(entry, current, "采用并开始办理")


def enter_edit(entry, card, *, action_name, item):
    """Simulate the ticket-03 edit entry publication for the Cross unit tests.

    The real platform reads the exact sealed source, reserves the candidate and
    seals/publishes the returned content; here the reservation is the same
    CandidateRequest shape and the sealed write is the test saver.
    """
    who = parent_trusted()
    saved, _state = entry._load(who, None)
    assert saved is not None
    config = saved.config["configurable"]
    source = CheckpointRef(config["thread_id"],
                           config.get("checkpoint_ns") or "",
                           config["checkpoint_id"])
    candidate = CheckpointRef(config["thread_id"], "birthday/edit/test",
                              str(uuid4()))
    request = CandidateRequest(
        kind="edit", candidate=candidate, conversion_digest="d" * 64,
        accepted_version=1, source=source, source_checkpoint=saved.checkpoint,
        edit_ref="edit-test-1",
        edit={"interaction_id": card.interaction.interaction_id,
              "action_name": action_name, "item": item,
              "kind": card.interaction.kind},
    )
    result = HANDOFF.prepare(who, request)
    entry.saver.put(saved.config, result.checkpoint, result.metadata,
                    result.new_versions)
    return result


def start_edit(entry, card, *, action_name, item):
    result = enter_edit(entry, card, action_name=action_name, item=item)
    assert result.result.status is TaskStatus.WAITING_INPUT
    assert result.result.interaction.kind == "input"
    return result.result


def edit_quantity(entry, current, needle, quantity):
    current = select(entry, current, f"改数量：{needle}")
    assert current.status is TaskStatus.WAITING_INPUT
    assert "数量" in current.message
    return entry.resume(parent_trusted(), {"text": str(quantity)})


def action_records(application):
    return application.get_task("U1", "D1", "PARENT").snapshot.get(
        "birthday_actions") or {}


def birthday_state(entry):
    return entry._load(parent_trusted(), None)[1]["birthday"]


def revision(entry):
    return entry._load(parent_trusted(), None)[1]["plan_revision"]


def fact(birthday, kind, item):
    """The stored display facts for one stable execution item."""
    return birthday["write_facts"][f"{kind}:{item['item_id'] or item['product_id']}"]


def page(result) -> str:
    return result.message


# --------------------------------------------------------------------- Q01


def test_q01_two_flowers_are_398_on_one_stable_item(tmp_path):
    ports = EditPorts(released_amount_fen=10200)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    current = start_to_pick(entry)
    current = pick(entry, current, "康乃馨")
    current = entry.resume(parent_trusted(), {"text": "2"})
    assert "×2" in page(current) and "398.00" in page(current)

    current = select(entry, current, "就选这些")
    # The adoption page shows every service fact the user must see.
    assert "康乃馨花束" in page(current) and "×2" in page(current)
    assert "单价 199.00 元" in page(current)
    assert "小计 398.00 元" in page(current)
    assert "合计 398.00 元" in page(current)
    assert "2026-10-30" in page(current)
    assert "A1" in page(current)

    freeze_card = select(entry, current, "采用并开始办理")
    assert freeze_card.interaction.kind == "confirmation"
    entry.resume(parent_trusted(), {"choice": "approve"})  # freeze → order card
    entry.resume(parent_trusted(), {"choice": "approve"})  # order → capture card
    # One execution item, one order and one payment, for two units.
    assert len({item["item_id"] for item in ports.order_items}) == 1
    flower = ports.order_items[0]
    assert flower["quantity"] == 2
    assert flower["unit_price_fen"] == 19900
    assert flower["amount_fen"] == 39800

    done = entry.resume(parent_trusted(), {"choice": "approve"})
    assert done.status is TaskStatus.SUCCEEDED, done.message
    assert "康乃馨花束 ×2" in done.message and "398.00 元" in done.message
    assert "释放 102.00 元" in done.message
    assert len({item["item_id"] for item in ports.capture_items}) == 1
    stored = birthday_state(entry)
    item_id = flower["item_id"]
    assert item_id
    assert fact(stored, "order", flower)["status"] == "completed"
    assert fact(stored, "capture", flower)["status"] == "completed"


def test_q01_invalid_quantity_and_empty_basket_write_nothing(tmp_path):
    ports = EditPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    current = start_to_pick(entry)
    current = pick(entry, current, "康乃馨")
    for bad in ("0", "-1", "两束", "1.5"):
        current = entry.resume(parent_trusted(), {"text": bad})
        assert current.status is TaskStatus.WAITING_INPUT
        assert "正整数" in current.message
        assert "×1" in page(current), page(current)
    # Removing the only item must leave an empty basket with nothing to adopt.
    current = select(entry, current, "移除：康乃馨")
    assert "都不选" in " ".join(item.label for item in current.interaction.options)
    assert not [item for item in current.interaction.options
                if "就选这些" in item.label]
    stopped = select(entry, current, "停止")
    assert stopped.status is TaskStatus.CANCELLED
    assert ports.freeze_executes == 0
    assert ports.order_executes == [] and ports.capture_executes == []
    assert action_records(application) == {}


# --------------------------------------------------------------------- Q02


def test_q02_adoption_page_can_change_the_basket_before_any_write(tmp_path):
    ports = EditPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    current = start_to_pick(entry)
    current = pick(entry, current, "康乃馨")
    current = pick(entry, current, "蛋糕")
    current = select(entry, current, "就选这些")
    assert "467.00" in page(current)
    before_revision = revision(entry)
    current = select(entry, current, "调整数量或移除商品")
    assert current.status is TaskStatus.WAITING_INPUT
    current = select(entry, current, "移除：六寸")
    current = select(entry, current, "就选这些")
    assert "199.00" in page(current)
    assert "蛋糕" not in page(current)
    assert revision(entry) > before_revision
    assert ports.freeze_executes == 0  # nothing was written by editing

    freeze_card = select(entry, current, "采用并开始办理")
    assert freeze_card.interaction.kind == "confirmation"


def test_q02_quantity_over_cap_is_refused_before_any_write(tmp_path):
    ports = EditPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    current = start_to_pick(entry, budget="300元")
    current = pick(entry, current, "康乃馨")
    current = entry.resume(parent_trusted(), {"text": "2"})
    current = select(entry, current, "就选这些")
    assert "超过预算上限 300.00 元" in page(current)
    assert "去掉些商品" in " ".join(item.label for item in current.interaction.options)
    stopped = select(entry, current, "停止")
    assert stopped.status is TaskStatus.CANCELLED
    assert ports.freeze_executes == 0 and ports.order_executes == []
    assert action_records(application) == {}


# --------------------------------------------------------------------- Q03


def test_edit_from_order_confirmation_recomputes_and_reconfirms(tmp_path):
    ports = EditPorts(released_amount_fen=13400)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    card = to_order_card(entry, budget="800元")
    assert card.status is TaskStatus.WAITING_APPROVAL
    before = birthday_state(entry)
    original_row = deepcopy(before["orders"][0])
    original_item = original_row["item_id"]
    before_revision = revision(entry)

    edit = start_edit(entry, card, action_name="bank.create_order",
                      item=f"order:item/{original_item}")
    assert edit.interaction.interaction_id != card.interaction.interaction_id
    # The edit is a new plan revision; item identity is not rebuilt with it.
    assert revision(entry) > before_revision
    assert birthday_state(entry)["orders"][0]["item_id"] == original_item

    current = edit_quantity(entry, edit, "康乃馨", 2)
    assert "×2" in page(current) and "398.00" in page(current)
    current = select(entry, current, "按新方案继续")
    assert current.status is TaskStatus.WAITING_APPROVAL
    assert current.interaction.kind == "confirmation"
    assert "398.00" in page(current)

    # The new confirmation is the live one; it executes the recomputed order.
    entry.resume(parent_trusted(), {"choice": "approve"})  # order executes
    flower = ports.order_items[-1]
    assert flower["item_id"] == original_item  # unchanged item keeps identity
    assert flower["quantity"] == 2 and flower["amount_fen"] == 39800

    current = entry.resume(parent_trusted(), {"choice": "approve"})  # capture
    assert current.interaction.kind == "confirmation"
    entry.resume(parent_trusted(), {"choice": "approve"})  # pays → cake order
    entry.resume(parent_trusted(), {"choice": "approve"})  # cake order
    entry.resume(parent_trusted(), {"choice": "approve"})  # cake capture
    done = entry.resume(parent_trusted(), {"choice": "approve"})  # finalize
    assert done.status is TaskStatus.SUCCEEDED, done.message
    assert "康乃馨花束 ×2" in done.message and "398.00 元" in done.message
    assert "释放 134.00 元" in done.message

    # The edited row keeps its stable item id and the recomputed amount.
    after = birthday_state(entry)
    assert after["orders"][0]["item_id"] == original_item
    assert after["orders"][0]["quantity"] == 2
    assert after["orders"][0]["amount_fen"] == 39800
    assert fact(after, "order", original_row)["status"] == "completed"
    assert fact(after, "capture", original_row)["status"] == "completed"


def test_edit_from_capture_wait_keeps_the_created_order(tmp_path):
    ports = EditPorts(products=(FLOWER, CAKE, GIFT), released_amount_fen=13500)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    current = start_to_pick(entry, budget="800元")
    for needle in ("康乃馨", "蛋糕", "保温杯"):
        current = pick(entry, current, needle)
    current = select(entry, current, "就选这些")
    current = select(entry, current, "采用并开始办理")
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # freeze
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # flower order
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # flower capture
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # cake order
    assert current.interaction.kind == "confirmation"  # cake capture card
    before = birthday_state(entry)
    cake_row = deepcopy(before["orders"][1])
    cake_order = fact(before, "order", cake_row)

    edit = start_edit(entry, current, action_name="bank.capture_frozen",
                      item=f"capture:item/{cake_row['item_id']}")
    current = edit_quantity(entry, edit, "保温杯", 2)
    current = select(entry, current, "按新方案继续")
    # The created unpaid cake order is re-confirmed, then paid once.
    assert current.interaction.kind == "confirmation"
    entry.resume(parent_trusted(), {"choice": "approve"})
    cake_capture_after = ports.capture_items[-1]
    assert cake_capture_after["item_id"] == cake_row["item_id"]
    assert cake_capture_after["order_id"]
    assert cake_capture_after["quantity"] == 1

    current = entry.resume(parent_trusted(), {"choice": "approve"})  # gift order
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # gift capture
    done = entry.resume(parent_trusted(), {"choice": "approve"})
    assert done.status is TaskStatus.SUCCEEDED, done.message
    assert "保温杯 ×2" in done.message
    assert "释放 135.00 元" in done.message
    after = birthday_state(entry)
    assert after["orders"][1]["item_id"] == cake_row["item_id"]
    assert after["orders"][1]["quantity"] == 1
    assert fact(after, "order", cake_row)["operation_id"] == cake_order["operation_id"]
    assert fact(after, "capture", cake_row)["status"] == "completed"


def test_capture_wait_edit_without_changes_reconfirms_the_same_order(tmp_path):
    ports = EditPorts(products=(FLOWER, CAKE, GIFT), released_amount_fen=13500)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    current = start_to_pick(entry, budget="800元")
    for needle in ("康乃馨", "蛋糕", "保温杯"):
        current = pick(entry, current, needle)
    current = select(entry, current, "就选这些")
    current = select(entry, current, "采用并开始办理")
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # freeze
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # flower order
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # flower capture
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # cake order
    assert current.interaction.kind == "confirmation"  # cake capture card
    cake_row = birthday_state(entry)["orders"][1]

    edit = start_edit(entry, current, action_name="bank.capture_frozen",
                      item=f"capture:item/{cake_row['item_id']}")
    labels = " ".join(item.label for item in edit.interaction.options)
    assert "改数量：六寸蛋糕" not in labels
    current = select(entry, edit, "按新方案继续")
    # The same created order is re-confirmed with its original order number.
    assert current.interaction.kind == "confirmation"
    capture_card = current
    entry.resume(parent_trusted(), {"choice": "approve"})
    executed = [item for item in ports.capture_items
                if item["item_id"] == cake_row["item_id"]]
    assert len(executed) == 1
    assert executed[0]["order_id"] == cake_row["order_id"]
    assert executed[0]["amount_fen"] == cake_row["amount_fen"]
    assert capture_card.interaction.record_ref  # a real confirmation record


# --------------------------------------------------------------------- Q05


def test_paid_and_created_unpaid_items_are_preserved_by_an_edit(tmp_path):
    ports = EditPorts(products=(FLOWER, CAKE, GIFT), captures=(
        "completed", "failed", "completed"), released_amount_fen=40300)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    current = start_to_pick(entry, budget="800元")
    for needle in ("康乃馨", "蛋糕", "保温杯"):
        current = pick(entry, current, needle)
    current = select(entry, current, "就选这些")
    current = select(entry, current, "采用并开始办理")
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # freeze
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # flower order
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # flower capture
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # cake order
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # cake capture fails
    assert current.interaction.kind == "confirmation"  # gift order card

    before = birthday_state(entry)
    flower_row, cake_row, gift_row = deepcopy(before["orders"])
    cake_order = deepcopy(fact(before, "order", cake_row))
    cake_capture = deepcopy(fact(before, "capture", cake_row))
    paid_capture = deepcopy(fact(before, "capture", flower_row))

    edit = start_edit(entry, current, action_name="bank.create_order",
                      item=f"order:item/{gift_row['item_id']}")
    # Only unattempted rows are listed as editable; the paid and created orders
    # are shown as facts, never as rewrite targets.
    labels = " ".join(item.label for item in edit.interaction.options)
    assert "改数量：保温杯" in labels
    assert "改数量：六寸" not in labels
    assert "改数量：康乃馨花束" not in labels
    assert "再加一件商品" not in labels  # ticket scope: change/remove/replace only
    assert "付款没有办成，订单未付款" in page(edit)
    assert "已付款" in page(edit)

    current = edit_quantity(entry, edit, "保温杯", 2)
    current = select(entry, current, "按新方案继续")
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # gift order
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # gift capture
    done = entry.resume(parent_trusted(), {"choice": "approve"})
    assert done.status is TaskStatus.SUCCEEDED, done.message
    assert "六寸蛋糕：订单已创建，未付款" in done.message
    assert "释放 403.00 元" in done.message

    after = birthday_state(entry)
    assert fact(after, "order", cake_row) == cake_order
    assert fact(after, "capture", cake_row) == cake_capture
    assert fact(after, "capture", flower_row) == paid_capture  # settled flower untouched
    assert after["orders"][1]["item_id"] == cake_row["item_id"]  # created order row
    assert after["orders"][1]["order_id"] == cake_row["order_id"]


# --------------------------------------------------------------------- Q04


def test_edited_quantity_uses_the_fresh_unit_price_not_the_old_line_total(tmp_path):
    ports = EditPorts(fresh_prices={"P_FLOWER": 25000},
                      released_amount_fen=10000)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    card = to_order_card(entry, budget="800元")
    item_id = birthday_state(entry)["orders"][0]["item_id"]
    edit = start_edit(entry, card, action_name="bank.create_order",
                      item=f"order:item/{item_id}")
    current = edit_quantity(entry, edit, "康乃馨", 2)
    revision_before = revision(entry)
    current = select(entry, current, "按新方案继续")
    # A changed service price is re-quoted BEFORE the order; the line subtotal is
    # rebuilt as the new unit price x the edited quantity (2), not the old total.
    assert "价格已从 199.00 元变为 250.00 元" in page(current)
    assert "重新采用方案并确认" in page(current)
    assert "按新价 500.00 元继续" in " ".join(
        item.label for item in current.interaction.options)
    # An approval on the price card itself must not execute the new amount.
    with pytest.raises(ValueError, match="INVALID_OPTION"):
        entry.resume(parent_trusted(), {"choice": "approve"})
    assert ports.order_items == []
    assert ports.order_checks == []  # only the price card exists so far

    current = select(entry, current, "按新价")
    # The new price is a new plan version and a new order attempt: the user
    # receives a fresh confirmation instead of a direct write of the row.
    assert current.interaction.kind == "confirmation"
    assert revision(entry) > revision_before
    assert ports.order_checks[-1]["quantity"] == 2
    assert ports.order_checks[-1]["unit_price_fen"] == 25000
    assert ports.order_checks[-1]["amount_fen"] == 50000
    assert ports.order_items == []  # nothing submitted before the new approval
    entry.resume(parent_trusted(), {"choice": "approve"})
    assert ports.order_items[-1]["quantity"] == 2
    assert ports.order_items[-1]["unit_price_fen"] == 25000
    assert ports.order_items[-1]["amount_fen"] == 50000


def test_edited_plan_over_the_original_cap_writes_nothing(tmp_path):
    ports = EditPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    card = to_order_card(entry, budget="500元")
    item_id = birthday_state(entry)["orders"][0]["item_id"]
    edit = start_edit(entry, card, action_name="bank.create_order",
                      item=f"order:item/{item_id}")
    current = edit_quantity(entry, edit, "康乃馨", 2)
    current = select(entry, current, "按新方案继续")
    assert "超过原上限 500.00 元" in page(current)
    assert "不能自动追加预算" in page(current)
    assert ports.order_executes == []  # no extra money was committed
    # Lowering the quantity again continues on the original cap, no reset.
    current = edit_quantity(entry, current, "康乃馨", 1)
    current = select(entry, current, "按新方案继续")
    assert current.interaction.kind == "confirmation"
    assert "199.00" in page(current)


def test_old_price_change_option_without_item_key_still_works(tmp_path):
    """An old checkpoint's price-change choice carries only product_id/total."""
    ports = EditPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    to_order_card(entry)  # reach the ordered phase through the real flow
    who = parent_trusted()
    _saved, state = entry._load(who, None)
    b = state["birthday"]
    # Rewrite the plan to the pre-08 legacy shape: no item ids, rows keyed by
    # product and the old price-choice option value.
    b["chosen"] = ["P_FLOWER", "P_CAKE"]
    b["orders"] = [
        {"product_id": product_id, "name": name, "amount_fen": amount,
         "quantity": 1, "order": None, "capture": None,
         "order_id": None, "transaction_id": None}
        for product_id, name, amount in (
            ("P_FLOWER", "康乃馨花束", 18900), ("P_CAKE", "六寸蛋糕", 26800))]
    b["phase"] = "orders"
    b["pending"] = None
    b["holding"] = None
    flow = BirthdayFlow(entry, state, ports)
    ask = flow._ask(who, "价格变化，请重新选择。",
                    [("按新价 199.00 元继续", {"kind": "b_price_ok",
                                              "product_id": "P_FLOWER",
                                              "amount_fen": 19900}),
                     ("停止剩余办理", {"kind": "b_stop"})])
    entry._save(who, None, state)

    # Restoring that old card never raises: the option still resolves the
    # product-keyed row, then re-quotes and asks for a new confirmation at the
    # legacy price (the row is not submitted directly).
    result = entry.resume(who, {"selected_option_id": option_id(ask, "按新价")})
    assert result.status is TaskStatus.WAITING_APPROVAL
    assert ports.order_checks[-1]["amount_fen"] == 19900
    assert ports.order_items == []
    entry.resume(who, {"choice": "approve"})
    assert ports.order_items[-1]["amount_fen"] == 19900
    assert "item_id" not in ports.order_items[-1]


# --------------------------------------------------------------------- Q09


def test_same_product_replacement_gets_a_new_item_and_new_payment(tmp_path):
    ports = EditPorts(released_amount_fen=40200)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    card = to_order_card(entry, budget="800元")
    card = entry.resume(parent_trusted(), {"choice": "approve"})  # order executes
    card = entry.resume(parent_trusted(), {"choice": "approve"})  # pays, cake card
    before = birthday_state(entry)
    paid_row = deepcopy(before["orders"][0])
    paid_capture = deepcopy(fact(before, "capture", paid_row))
    original_item = paid_row["item_id"]
    assert ports.capture_items  # the flower was paid

    edit = start_edit(entry, card, action_name="bank.create_order",
                      item=f"order:item/{before['orders'][1]['item_id']}")
    current = select(entry, edit, "替换：六寸")
    current = select(entry, current, "康乃馨")  # same product, new execution item
    current = select(entry, current, "按新方案继续")
    assert current.interaction.kind == "confirmation"
    entry.resume(parent_trusted(), {"choice": "approve"})  # new flower order
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # capture
    done = entry.resume(parent_trusted(), {"choice": "approve"})
    assert done.status is TaskStatus.SUCCEEDED, done.message
    assert "释放 402.00 元" in done.message

    after = birthday_state(entry)
    order_facts = {key: value for key, value in after["write_facts"].items()
                   if key.startswith("order:")}
    capture_facts = {key: value for key, value in after["write_facts"].items()
                     if key.startswith("capture:")}
    assert len(order_facts) == 2 and len(capture_facts) == 2
    assert all(value["status"] == "completed" for value in order_facts.values())
    row_ids = {row["item_id"] for row in after["orders"]}
    replaced = after["orders"][1]
    assert row_ids == {original_item, replaced["item_id"]}
    assert replaced["item_id"] != original_item
    assert replaced["product_id"] == "P_FLOWER"  # same product, new item
    new_capture = next(value for key, value in capture_facts.items()
                       if key != f"capture:{original_item}")
    assert new_capture["operation_id"] != paid_capture["operation_id"]
    # The original paid item keeps its own attempts and payment facts.
    assert fact(after, "capture", paid_row) == paid_capture
    assert all(row["product_id"] != "P_CAKE" for row in after["orders"])


# --------------------------------------------------------------------- Q10


def test_verified_order_failure_offers_an_ordinary_replacement(tmp_path):
    ports = EditPorts(verify_failures=True, orders=("completed", "failed"),
                      released_amount_fen=3300)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    card = to_order_card(entry, budget="500元")
    # Freeze, flower order and payment, then the cake order fails at the bank.
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # flower order
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # capture
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # cake order
    assert current.status is TaskStatus.WAITING_INPUT
    assert "银行已明确失败" in page(current)
    assert "没有生成订单" in page(current)
    assert "换一件继续" in " ".join(item.label for item in current.interaction.options)
    assert ports.requery_ids[-1] == ports.failed_orders[0]

    before = birthday_state(entry)
    failed_row = next(row for row in before["orders"] if row["order"] == "failed")
    failed_fact = deepcopy(fact(before, "order", failed_row))
    old_item_id = failed_row["item_id"]

    current = select(entry, current, "换一件继续")
    current = select(entry, current, "蛋糕")
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # new order
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # capture
    done = entry.resume(parent_trusted(), {"choice": "approve"})
    assert done.status is TaskStatus.SUCCEEDED, done.message
    assert "六寸蛋糕：订单已创建并已付款 268.00 元" in done.message
    assert "释放 33.00 元" in done.message

    after = birthday_state(entry)
    assert fact(after, "order", failed_row) == failed_fact  # failure never rewritten
    evidence = after["verified_failures"][ports.failed_orders[0]]
    # The second basis cites the original OperationResult, not just a status.
    assert evidence["operation_status"] == "failed"
    assert evidence["bank_error_code"] == "PRODUCT_UNAVAILABLE"
    assert evidence["receipt"] is None and evidence["order_id"] is None
    assert evidence["in_flight"] is False
    new_items = {row["item_id"] for row in after["orders"]}
    assert old_item_id in new_items and len(new_items) == 3


def test_second_basis_requires_the_original_operation_result(tmp_path):
    """A failed port status without the original OperationResult proves nothing."""
    ports = EditPorts(verify_failures="weak", orders=("completed", "failed"),
                      released_amount_fen=30100)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    to_order_card(entry, budget="500元")
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # flower order
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # flower capture
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # cake fails
    # No replacement is offered and no second-basis fact is recorded: the flow
    # keeps the original "failed row stays unsubmitted, continue" behaviour.
    assert current.status is TaskStatus.SUCCEEDED, current.message
    assert "下单未办成" in current.message
    assert "已核实" not in current.message
    assert birthday_state(entry)["verified_failures"] == {}
    assert len(ports.order_items) == 2  # no replacement attempt
    assert ports.requery_ids[-1] == ports.failed_orders[0]


def test_unverified_failure_never_builds_a_replacement(tmp_path):
    ports = EditPorts(verify_failures=False, orders=("completed", "failed"),
                      released_amount_fen=30100)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    to_order_card(entry, budget="500元")
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # flower order
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # flower capture
    current = entry.resume(parent_trusted(), {"choice": "approve"})  # cake fails
    # Without the "no order / nothing in flight" proof the flow keeps the old
    # behaviour: the failed row stays unsubmitted, no replacement is invented.
    assert current.status is TaskStatus.SUCCEEDED, current.message
    assert "下单未办成" in current.message
    assert "释放 301.00 元" in current.message
    assert ports.requery_ids[-1] == ports.failed_orders[0]
    assert len(ports.order_items) == 2  # the replacement was never attempted
    assert [item for item in ports.order_items
            if item["product_id"] == "P_CAKE"]  # the one failed attempt


# ------------------------------------------------- edit identity / refusals


def test_old_card_ids_and_approve_cannot_execute_the_edited_plan(tmp_path):
    ports = EditPorts(released_amount_fen=13400)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    card = to_order_card(entry, budget="800元")
    writes_before = len(ports.order_executes) + len(ports.capture_executes)
    item_id = birthday_state(entry)["orders"][0]["item_id"]
    edit = start_edit(entry, card, action_name="bank.create_order",
                      item=f"order:item/{item_id}")
    with pytest.raises(ValueError, match="INTERACTION_STALE"):
        entry.resume(parent_trusted(), {"interaction_id":
                                       card.interaction.interaction_id})
    with pytest.raises(ValueError, match="INVALID_OPTION"):
        entry.resume(parent_trusted(), {"selected_option_id": "approve"})
    with pytest.raises(ValueError, match="INVALID_OPTION"):
        entry.resume(parent_trusted(), {"choice": "approve"})
    assert len(ports.order_executes) + len(ports.capture_executes) == writes_before

    # The current edit interaction still works and keeps every item identity.
    current = edit_quantity(entry, edit, "康乃馨", 2)
    current = select(entry, current, "按新方案继续")
    assert current.interaction.kind == "confirmation"


def test_prepare_is_a_pure_candidate_read_and_refuses_foreign_actors(tmp_path):
    ports = EditPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    card = to_order_card(entry)

    saved, state = entry._load(parent_trusted(), None)
    config = saved.config["configurable"]
    source = CheckpointRef(config["thread_id"], config.get("checkpoint_ns") or "",
                           config["checkpoint_id"])
    candidate_ref = CheckpointRef(config["thread_id"], "birthday/edit/test",
                                  str(uuid4()))

    def request(**overrides):
        values = dict(kind="edit", candidate=candidate_ref,
                      conversion_digest="d" * 64, accepted_version=1,
                      source=source, source_checkpoint=saved.checkpoint,
                      edit_ref="edit-test-1",
                      edit={"interaction_id": card.interaction.interaction_id,
                            "action_name": "bank.create_order"})
        values.update(overrides)
        return CandidateRequest(**values)

    stranger = TrustedContext(user_id="U2", session_id="S2", task_id="PARENT",
                              run_id="R2", parent_task_id=None,
                              demo_round_id="D1")
    with pytest.raises(BirthdayEditError) as foreign:
        HANDOFF.prepare(stranger, request())
    assert foreign.value.code == "ACCESS_DENIED"

    # A foreign session never answers the same task (越权/旧交互拒绝).
    other_session = TrustedContext(user_id="U1", session_id="S2",
                                   task_id="PARENT", run_id="R2",
                                   parent_task_id=None, demo_round_id="D1")
    with pytest.raises(PermissionError):
        entry.resume(other_session, {"text": "2"})

    with pytest.raises(BirthdayEditError) as wrong_kind:
        HANDOFF.prepare(parent_trusted(), request(kind="root"))
    assert wrong_kind.value.code == "CANDIDATE_INVALID"

    with pytest.raises(BirthdayEditError) as no_source:
        HANDOFF.prepare(parent_trusted(), request(source_checkpoint=None))
    assert no_source.value.code == "CANDIDATE_INVALID"

    # Nothing was written: the source state is still the live one.
    _saved, still = entry._load(parent_trusted(), None)
    assert still["birthday"]["phase"] == state["birthday"]["phase"]
    assert still["interaction_id"] == state["interaction_id"]

    result = HANDOFF.prepare(parent_trusted(), request())
    assert isinstance(result, CrossCandidate)
    assert result.checkpoint["id"] == candidate_ref.checkpoint_id
    assert result.result.status is TaskStatus.WAITING_INPUT
    assert result.result.interaction.interaction_id != card.interaction.interaction_id


def test_edit_removing_everything_before_the_freeze_writes_nothing(tmp_path):
    ports = EditPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    card = to_freeze_card(entry)
    edit = start_edit(entry, card, action_name="bank.freeze_funds", item="freeze")
    current = select(entry, edit, "移除：康乃馨")
    current = select(entry, current, "移除：六寸")
    labels = " ".join(item.label for item in current.interaction.options)
    assert "就选这些" not in labels
    stopped = select(entry, current, "停止")
    assert stopped.status is TaskStatus.CANCELLED
    assert ports.freeze_executes == 0
    assert birthday_state(entry)["orders"] == []
    assert birthday_state(entry)["write_facts"] == {}


def test_repeated_edits_keep_item_ids_and_recompute_amounts(tmp_path):
    ports = EditPorts(released_amount_fen=13500)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)

    card = to_order_card(entry, budget="1000元")
    item_id = birthday_state(entry)["orders"][0]["item_id"]

    edit = start_edit(entry, card, action_name="bank.create_order",
                      item=f"order:item/{item_id}")
    current = edit_quantity(entry, edit, "康乃馨", 2)
    revision_two = revision(entry)
    current = select(entry, current, "按新方案继续")
    assert current.interaction.kind == "confirmation"

    edit = start_edit(entry, current, action_name="bank.create_order",
                      item=f"order:item/{item_id}")
    current = edit_quantity(entry, edit, "康乃馨", 3)
    revision_three = revision(entry)
    assert revision_three > revision_two
    assert "×3" in page(current) and "597.00" in page(current)
    current = select(entry, current, "按新方案继续")
    assert "597.00" in page(current)  # the order confirmation pages the new amount
    entry.resume(parent_trusted(), {"choice": "approve"})
    assert ports.order_items[-1]["item_id"] == item_id
    assert ports.order_items[-1]["quantity"] == 3
    assert ports.order_items[-1]["amount_fen"] == 59700
