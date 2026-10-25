"""Ticket v05-birthday-platform-dependencies/01: real quantity and stable items.

The platform ports are exercised the way the orchestrator calls them today,
plus the captured-original keyword Cross08 will pass once its own ticket lands,
over the real security gate and the real isolated mock bank. Stand-in plan rows
stand for the server snapshot Cross08 will send; they are not a public
protocol. The legacy single-item shape (no ``item_id``) must keep behaving
exactly as before, including its stored parameter shape.
"""

from uuid import UUID, uuid4

from app.contracts.common import OperationStatus, SecurityDecisionCode, TaskStatus
from app.modules.cross.birthday_ports import BirthdayPlan
from app.storage.database import connect

from .test_birthday_runtime_wiring import (
    DELIVERY_REF, answer_verification, approve_confirmation, composition, trusted,
)

DELIVER_BY = "2026-11-30"  # a bare date: end of that Beijing day
NORMALIZED_DELIVER_BY = "2026-11-30T23:59:59+08:00"

FLOWER = {"product_id": "p_flower", "name": "鲜花礼盒", "merchant_id": "m_flower",
          "merchant_name": "邻里花店", "category": "shopping",
          "unit_price_fen": 19900}


def plan(*items, payer="A1", deliver_by=DELIVER_BY) -> BirthdayPlan:
    return BirthdayPlan(
        payer_account_id=payer, budget_id=None, budget_version=None,
        budget_limit_fen=50000, freeze_amount_fen=50000,
        deliver_by=deliver_by, delivery_ref=DELIVERY_REF, items=tuple(items))


def row(*, item_id=None, quantity=1, unit_price_fen=19900, **overrides) -> dict:
    item = {**FLOWER, "quantity": quantity, "amount_fen": unit_price_fen * quantity}
    if item_id is not None:
        item["item_id"] = item_id
    item.update(overrides)
    return item


def bank_orders(runtime) -> list[dict]:
    with connect(runtime.gateway._bank.store.path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM orders")]


def confirmation(runtime, who, ref):
    return runtime.confirmations.get(runtime._context(who, None, None), ref)


def actions(runtime) -> dict:
    return runtime.application.get_task(
        "U1", "D1", "BIRTHDAY").snapshot.get("birthday_actions") or {}


def attempts(runtime) -> list:
    return runtime.application.get_task(
        "U1", "D1", "BIRTHDAY").snapshot.get("birthday_attempts") or []


def order_to_bank(runtime, ports, who, plan_data, item):
    """Walk one order from check through the real confirmation and step-up."""
    answer = ports.order_check(who, plan_data, item)
    assert answer.decision is SecurityDecisionCode.REQUIRE_CONFIRMATION
    approve_confirmation(runtime, who, answer.interaction.record_ref)
    waiting = ports.order_execute(who, plan_data, item)
    assert waiting.state == "verify_wait"
    answer_verification(runtime, who, "R1", waiting.verify.record_ref)
    outcome = ports.order_execute(who, plan_data, item)
    assert outcome.state == "completed", outcome
    return answer, outcome


def test_quantity_flows_to_confirmation_and_the_real_bank(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    ports = runtime.birthday.ports_factory(who)
    item = row(item_id="item-flower-1", quantity=2)
    plan_data = plan(item)
    try:
        answer, outcome = order_to_bank(runtime, ports, who, plan_data, item)

        stored = actions(runtime)["order:item/item-flower-1"]
        assert stored["parameters"]["item_id"] == "item-flower-1"
        # Only the stable item id joins the binding; the request itself freezes
        # quantity and total, and delivery stays on the plan.
        assert "quantity" not in stored["parameters"]
        assert "account_id" not in stored["parameters"]
        assert "deliver_by" not in stored["parameters"]
        request = stored["parameters"]["request"]
        assert request["quantity"] == 2
        assert request["expected_total_fen"] == 39800
        assert request["delivery"]["deliver_by"] == NORMALIZED_DELIVER_BY
        facts = stored["facts"]
        assert facts["quantity"] == 2
        assert facts["unit_price_fen"] == 19900
        assert facts["deliver_by"] == NORMALIZED_DELIVER_BY
        assert facts["account_id"] == "A1"

        record = confirmation(runtime, who, answer.interaction.record_ref)
        fields = {field.name: field.value_text for field in record.display_fields}
        # The §3.5 clause only belongs to a freeze.
        assert "release_clause" not in fields
        assert fields["quantity"] == "2 件"
        assert fields["unit_price"] == "199.00 元"
        assert fields["amount"] == "398.00 元"
        assert fields["deliver_by"] == NORMALIZED_DELIVER_BY
        assert fields["account"] == "A1"
        assert "邻里花店" in fields["item"]

        orders = bank_orders(runtime)
        assert len(orders) == 1
        assert orders[0]["quantity"] == 2
        assert orders[0]["total_fen"] == 39800
        lookup = runtime.gateway.get_operation(who, UUID(outcome.operation_id))
        assert lookup.operation.operation_status is OperationStatus.SUCCEEDED
        assert lookup.operation.receipt.order.quantity == 2
        assert lookup.operation.receipt.order.total_fen == 39800
    finally:
        runtime.gateway.close()


def test_legacy_single_item_call_keeps_its_original_shape(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    ports = runtime.birthday.ports_factory(who)
    item = row()  # no item_id: the old callers' explicit quantity=1
    plan_data = plan(item)
    try:
        answer, _outcome = order_to_bank(runtime, ports, who, plan_data, item)

        stored = actions(runtime)["order:p_flower"]
        # A new field here would have made every in-flight old task look like a
        # different attempt; the legacy binding keeps exactly its old keys.
        assert set(stored["parameters"]) == {
            "__action__", "product_id", "amount_fen", "merchant_id",
            "merchant_name", "purpose", "category", "request",
        }
        assert stored["parameters"]["request"]["quantity"] == 1
        assert stored["parameters"]["request"]["expected_total_fen"] == 19900
        assert bank_orders(runtime)[0]["quantity"] == 1

        fields = {field.name: field.value_text
                  for field in confirmation(runtime, who, answer.interaction.record_ref).display_fields}
        assert fields["quantity"] == "1 件"
        assert fields["unit_price"] == "199.00 元"
        assert fields["amount"] == "199.00 元"
    finally:
        runtime.gateway.close()


def test_preexisting_legacy_attempt_is_reused_without_new_facts(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    ports = runtime.birthday.ports_factory(who)
    item = row()
    plan_data = plan(item)
    try:
        ports.order_check(who, plan_data, item)
        stored = actions(runtime)["order:p_flower"]
        # An attempt written before this change carries no display facts; the
        # same call must recover it by its original operation id, not replace it.
        task = runtime.application.get_task("U1", "D1", "BIRTHDAY")
        old = {key: value for key, value in stored.items() if key != "facts"}
        runtime.application.update_task(
            "U1", "D1", "BIRTHDAY", task.revision, task.run_id, task.status,
            task.checkpoint_id,
            {**task.snapshot, "birthday_actions": {"order:p_flower": old}},
        )
        again = ports.order_check(who, plan_data, item)
        assert again.operation_id == stored["operation_id"]
        assert actions(runtime)["order:p_flower"] == old
        assert attempts(runtime) == []
    finally:
        runtime.gateway.close()


def test_ambiguous_or_inconsistent_items_never_reach_the_bank(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    ports = runtime.birthday.ports_factory(who)
    try:
        # quantity > 1 without a stable item id: the old product key cannot
        # carry that attempt, so the platform refuses instead of downgrading.
        no_identity = plan(row(quantity=2))
        answer = ports.order_check(who, no_identity, no_identity.items[0])
        assert answer.decision is SecurityDecisionCode.BLOCK
        assert answer.reason_code == "ITEM_IDENTITY_AMBIGUOUS"
        failed = ports.order_execute(who, no_identity, no_identity.items[0])
        assert failed.executed is False and failed.state == "failed"

        # The same product twice without item ids is just as ambiguous.
        twice = plan(row(), row())
        for item in twice.items:
            answer = ports.order_check(who, twice, item)
            assert answer.reason_code == "ITEM_IDENTITY_AMBIGUOUS"

        # A row whose subtotal disagrees with unit price x quantity is refused.
        mismatched = row(item_id="item-flower-1", quantity=2,
                         amount_fen=19900)
        answer = ports.order_check(who, plan(mismatched), mismatched)
        assert answer.reason_code == "ITEM_AMOUNT_MISMATCH"

        # A non-positive quantity is refused before any bank input is built.
        zero = row(item_id="item-flower-1", quantity=0)
        answer = ports.order_check(who, plan(zero), zero)
        assert answer.reason_code == "ITEM_QUANTITY_INVALID"

        assert bank_orders(runtime) == []
        assert actions(runtime) == {}
    finally:
        runtime.gateway.close()


def test_same_product_replacement_keeps_two_distinct_items(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    ports = runtime.birthday.ports_factory(who)
    first = row(item_id="item-flower-1")
    second = row(item_id="item-flower-2")  # the same product, a new execution item
    plan_data = plan(first, second)
    try:
        _answer_a, outcome_a = order_to_bank(runtime, ports, who, plan_data, first)
        _answer_b, outcome_b = order_to_bank(runtime, ports, who, plan_data, second)
        assert outcome_a.operation_id != outcome_b.operation_id

        stored = actions(runtime)
        assert set(stored) == {"order:item/item-flower-1", "order:item/item-flower-2"}
        assert (stored["order:item/item-flower-1"]["operation_id"]
                != stored["order:item/item-flower-2"]["operation_id"])

        orders = bank_orders(runtime)
        assert len(orders) == 2
        assert len({order["order_id"] for order in orders}) == 2
        assert [order["quantity"] for order in orders] == [1, 1]

        # Capture attempts stay bound to their own order and item.
        capture_a = ports.capture_check(who, plan_data, first, orders[0]["order_id"])
        capture_b = ports.capture_check(who, plan_data, second, orders[1]["order_id"])
        assert capture_a.decision is SecurityDecisionCode.REQUIRE_CONFIRMATION
        assert capture_b.decision is SecurityDecisionCode.REQUIRE_CONFIRMATION
        assert capture_a.operation_id != capture_b.operation_id
        stored = actions(runtime)
        assert stored["capture:item/item-flower-1"]["parameters"]["order_id"] == orders[0]["order_id"]
        assert stored["capture:item/item-flower-2"]["parameters"]["order_id"] == orders[1]["order_id"]
    finally:
        runtime.gateway.close()


def test_changed_parameters_keep_the_replaced_attempt_readable(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    ports = runtime.birthday.ports_factory(who)
    try:
        one = row(item_id="item-flower-1", quantity=1)
        ports.order_check(who, plan(one), one)
        original = actions(runtime)["order:item/item-flower-1"]
        assert original["parameters"]["request"]["quantity"] == 1

        # The same item now wants two: a new attempt and operation, while the
        # old attempt stays readable by its saved id with its original params.
        two = row(item_id="item-flower-1", quantity=2)
        ports.order_check(who, plan(two), two)
        stored = actions(runtime)["order:item/item-flower-1"]
        assert stored["operation_id"] != original["operation_id"]
        assert stored["parameters"]["request"]["quantity"] == 2
        assert stored["facts"]["quantity"] == 2
        assert stored["action_revision"] > original["action_revision"]
        assert attempts(runtime) == [original]
        assert ports._action_for(who, original["operation_id"]) == original
    finally:
        runtime.gateway.close()


def test_execute_only_submits_the_captured_original_attempt(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    ports = runtime.birthday.ports_factory(who)
    item = row(item_id="item-flower-1")
    plan_data = plan(item)
    try:
        answer = ports.order_check(who, plan_data, item)
        approve_confirmation(runtime, who, answer.interaction.record_ref)
        waiting = ports.order_execute(who, plan_data, item,
                                      operation_id=answer.operation_id)
        assert waiting.state == "verify_wait"
        answer_verification(runtime, who, "R1", waiting.verify.record_ref)

        # A captured id that is not this item's attempt is never submitted.
        refused = ports.order_execute(who, plan_data, item,
                                      operation_id=str(uuid4()))
        assert refused.executed is False and refused.state == "failed"
        assert bank_orders(runtime) == []

        outcome = ports.order_execute(who, plan_data, item,
                                      operation_id=answer.operation_id)
        assert outcome.state == "completed"
        assert outcome.operation_id == answer.operation_id
        assert len(bank_orders(runtime)) == 1
    finally:
        runtime.gateway.close()


def test_capture_refuses_quantity_without_item_identity(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    ports = runtime.birthday.ports_factory(who)
    try:
        legacy = row()
        # Without a create-order source for that order id the gate blocks, not
        # asks: an unverified order reference is never a payable target.
        assert ports.capture_check(who, plan(legacy), legacy, "order-1").decision is (
            SecurityDecisionCode.BLOCK)
        ambiguous = row(quantity=2)
        answer = ports.capture_check(who, plan(ambiguous), ambiguous, "order-1")
        assert answer.decision is SecurityDecisionCode.BLOCK
        assert answer.reason_code == "ITEM_IDENTITY_AMBIGUOUS"
        assert not [key for key in actions(runtime) if key.startswith("capture:item/")]
    finally:
        runtime.gateway.close()


def test_legacy_call_never_downgrades_an_item_binding(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    ports = runtime.birthday.ports_factory(who)
    try:
        # A stored item attempt for this product exists: a later id-less call
        # must not open a second, product-keyed attempt beside it.
        item = row(item_id="item-flower-1")
        ports.order_check(who, plan(item), item)
        plain = row()
        answer = ports.order_check(who, plan(plain), plain)
        assert answer.decision is SecurityDecisionCode.BLOCK
        assert answer.reason_code == "ITEM_IDENTITY_AMBIGUOUS"
        assert "order:p_flower" not in actions(runtime)

        # The plan itself already carries the stable id for this product.
        hybrid = row(item_id="item-flower-2")
        answer = ports.order_check(
            who, plan(hybrid), {**plain, "product_id": "p_flower"})
        assert answer.reason_code == "ITEM_IDENTITY_AMBIGUOUS"

        # A row with the field present but empty is the new shape without an
        # identity, not the old callers' omission.
        blank = {**row(), "item_id": ""}
        answer = ports.order_check(who, plan(blank), blank)
        assert answer.reason_code == "ITEM_IDENTITY_AMBIGUOUS"
    finally:
        runtime.gateway.close()


def test_capture_reads_the_orders_own_creation_parameters(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    ports = runtime.birthday.ports_factory(who)
    item = row(item_id="item-flower-1")
    try:
        _answer, outcome = order_to_bank(runtime, ports, who, plan(item), item)
        order_id = runtime.gateway.get_operation(
            who, UUID(outcome.operation_id)).operation.receipt.order.order_id

        # A fresh quote for the same item must not rewrite the created order.
        requoted = {**item, "amount_fen": 29900, "unit_price_fen": 29900}
        capture = ports.capture_check(who, plan(requoted), requoted, order_id)
        assert capture.decision is SecurityDecisionCode.REQUIRE_CONFIRMATION
        stored = actions(runtime)["capture:item/item-flower-1"]
        assert stored["parameters"]["amount_fen"] == 19900
        assert stored["facts"]["unit_price_fen"] == 19900
        record = confirmation(runtime, who, capture.interaction.record_ref)
        fields = {field.name: field.value_text for field in record.display_fields}
        assert fields["amount"] == "199.00 元"
        assert fields["unit_price"] == "199.00 元"
    finally:
        runtime.gateway.close()


def test_display_label_stays_stable_for_an_older_attempt():
    from .birthday_runtime import _display_fields

    parameters = {"amount_fen": 19900, "product_id": "p_flower",
                  "merchant_name": "邻里花店", "purpose": "鲜花礼盒"}
    legacy = {field.name: field.label for field in
              _display_fields("bank.create_order", parameters)}
    assert legacy["amount"] == "金额"  # a pre-change confirmation still matches
    assert "quantity" not in legacy
    new = {field.name: field.label for field in
           _display_fields("bank.create_order", parameters,
                           {"quantity": 1, "unit_price_fen": 19900})}
    assert new["amount"] == "金额（小计）"
    assert new["quantity"] == "数量"
