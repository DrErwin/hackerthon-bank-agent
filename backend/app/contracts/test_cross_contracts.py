"""Ticket v05-cross-platform/01 model checks: cross inputs, arrangements, plans, birthday bank.

Covers the model layer of the CT list (CT01—CT09, CT13, CT15) in the field detail
doc; runtime, storage and E2E layers stay with their own tickets.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.contracts import (
    AdoptedArrangement, AdoptedBudget, Allocation, ArrangementView, BudgetCommitment, BudgetRef,
    BudgetView, CaptureFrozenInput, CreateOrderInput, CrossConstraints, CrossScenario,
    CrossStartInput, CrossStep, CrossTaskView, DeliveryInput, FreezeFundsInput, FreezeReceipt,
    FreezeView, GetFreezeInput, OrderView, ProductList, ReleaseFrozenInput, ReleaseReceipt,
    SubmitDetailsRequest, TaskView,
)

NOW = "2026-10-24T18:00:00+08:00"
SCOPE = {
    "account_ids": ["own_daily"],
    "start_at": "2026-10-01T00:00:00+08:00",
    "end_at": "2026-11-01T00:00:00+08:00",
}


def balance() -> dict:
    return {
        "account_id": "own_daily", "book_balance_fen": 50000,
        "frozen_balance_fen": 0, "available_balance_fen": 50000, "as_of": NOW,
    }


def step(step_id: str, **overrides) -> dict:
    payload = {
        "step_id": step_id, "action": "transfer", "child_task_id": None, "operation_id": None,
        "status": None, "amount_fen": None, "order_id": None, "payment_status": None,
        "result_ref": None, "error": None, "depends_on": [],
    }
    return payload | overrides


def arrangement(**overrides) -> dict:
    payload = {
        "arrangement_id": "arr_01", "plan_revision": 1, "payer_account_id": "own_daily",
        "funds_basis": "selected_income", "income_transaction_ids": ["tx_pension_01"],
        "base_fen": 500000, "living_reserve_fen": 150000, "reserve_includes_known_debits": True,
        "upcoming_debit_scope": SCOPE, "known_debits_fen": 3900,
        "protected_fen": 150000, "distributable_fen": 350000, "facts_as_of": NOW, "adopted": False,
    }
    return payload | overrides


# --- CT01/CT03: start input accepts what it can and rejects bad shapes ---


def test_ex01_goal_only_input_parses_for_runtime_clarification():
    model = CrossStartInput.model_validate({
        "request_id": "c591c8a2-ef32-4b2c-8b10-24bd637a4201",
        "goal": "养老金到了，帮我安排本月的钱",
        "scenario": "monthly_arrangement",
    })
    assert model.scenario is CrossScenario.MONTHLY_ARRANGEMENT
    assert model.constraints is None


def test_ct02_missing_or_blank_goal_and_request_id_are_rejected():
    with pytest.raises(ValidationError):
        CrossStartInput.model_validate({"request_id": str(uuid4()), "goal": ""})
    with pytest.raises(ValidationError):
        CrossStartInput.model_validate({"request_id": str(uuid4()), "goal": "   "})
    with pytest.raises(ValidationError):
        CrossStartInput.model_validate({"goal": "省一点"})
    with pytest.raises(ValidationError):
        CrossStartInput.model_validate({"request_id": "not-a-uuid", "goal": "省一点"})


def test_ct03_unknown_scenario_and_bad_amounts_are_rejected():
    with pytest.raises(ValidationError):
        CrossStartInput.model_validate({
            "request_id": str(uuid4()), "goal": "生日", "scenario": "anything",
        })
    for bad in (-1, "500000", 1.5, True):
        with pytest.raises(ValidationError):
            CrossConstraints.model_validate({"budget_fen": bad})
        with pytest.raises(ValidationError):
            CrossConstraints.model_validate({"arrangement_amount_fen": bad})
    with pytest.raises(ValidationError):
        Allocation.model_validate({"destination": "transfer", "target_account_id": "a", "ratio_bps": 0})
    with pytest.raises(ValidationError):
        Allocation.model_validate({"destination": "transfer", "target_account_id": "a", "ratio_bps": 10001})
    assert Allocation.model_validate(
        {"destination": "transfer", "target_account_id": "a", "ratio_bps": 5000},
    ).ratio_bps == 5000


# --- CT04: allocation shape ---


def test_ct04_allocation_requires_exactly_one_amount_and_one_transfer_target():
    ok = Allocation.model_validate({
        "destination": "transfer", "target_account_id": "own_savings", "amount_fen": 250000,
    })
    assert ok.amount_fen == 250000
    cases = [
        {"destination": "transfer", "target_account_id": "a", "amount_fen": 1, "ratio_bps": 1},
        {"destination": "transfer", "target_account_id": "a"},
        {"destination": "transfer", "amount_fen": 1},
        {"destination": "transfer", "target_account_id": "a", "payee": {"kind": "own", "account_id": "b"}, "amount_fen": 1},
        {"destination": "transfer", "target_account_id": "a", "amount_fen": 0},
        {"destination": "retain", "payee": {"kind": "own", "account_id": "b"}, "amount_fen": 1},
        {"destination": "retain", "target_account_id": "own_savings", "amount_fen": 1},
    ]
    for payload in cases:
        with pytest.raises(ValidationError):
            Allocation.model_validate(payload)
    assert Allocation.model_validate({"destination": "retain", "amount_fen": 0}).amount_fen == 0


# --- CT05: old calls and old payloads keep working ---


def test_ct05_old_income_distribution_input_and_old_view_payload_stay_readable():
    old_input = CrossStartInput.model_validate({
        "request_id": "c591c8a2-ef32-4b2c-8b10-24bd637a4202",
        "goal": "把这笔收入分配到另一张卡",
        "scenario": "income_distribution",
        "constraints": {"income_transaction_ids": ["tx_pension_01"]},
    })
    assert old_input.scenario is CrossScenario.INCOME_DISTRIBUTION

    old_view = CrossTaskView.model_validate({
        "scenario": "income_distribution", "plan_revision": 1,
        "steps": [step("alloc_01", status="succeeded")],
        "budget": None, "summary": "分配完成",
    })
    assert old_view.plan_step_ids is None
    assert old_view.steps[0].depends_on == []
    restored = CrossTaskView.model_validate_json(old_view.model_dump_json())
    assert restored == old_view


def test_ex04_new_view_fields_parse_and_route_to_the_child_task():
    view = CrossTaskView.model_validate({
        "scenario": "birthday", "plan_revision": 2,
        "steps": [step("cancel_01"), step("transfer_01")],
        "budget": None, "summary": "等确认",
        "plan_step_ids": ["cancel_01", "transfer_01"], "active_step_id": "transfer_01",
        "interaction_task_id": "child_transfer_01", "stop_reason": None,
    })
    assert view.interaction_task_id == "child_transfer_01"


# --- CT06/CT07: plan structure ---


def test_ct06_null_facts_stay_expressible_and_payment_links_stay_consistent():
    view = CrossTaskView.model_validate({
        "scenario": "birthday", "plan_revision": 1,
        "steps": [step("pay_01", status=None, payment_status=None)],
        "budget": None, "summary": "付款结果未知",
    })
    assert view.steps[0].payment_status is None
    paid_order = {"order_id": "O1", "product_id": "P1", "quantity": 1, "merchant_id": "M1",
                  "merchant_name": "花店", "total_fen": 19900, "created_at": NOW, "deliver_by": NOW,
                  "recipient_name_masked": "张*", "phone_masked": "****1234",
                  "address_masked": "某市****", "payment_status": "paid",
                  "payment_transaction_id": "TX1"}
    assert OrderView.model_validate(paid_order).payment_transaction_id == "TX1"
    with pytest.raises(ValidationError):
        OrderView.model_validate(paid_order | {"payment_transaction_id": None})
    with pytest.raises(ValidationError):
        OrderView.model_validate(paid_order | {"payment_status": "unpaid"})


def test_ct07_duplicate_dangling_self_and_cyclic_dependencies_are_rejected():
    base = {"scenario": "birthday", "plan_revision": 1, "budget": None, "summary": "s"}
    with pytest.raises(ValidationError):
        CrossTaskView.model_validate(base | {"steps": [step("a"), step("a")]})
    with pytest.raises(ValidationError):
        CrossTaskView.model_validate(base | {"steps": [step("a", depends_on=["ghost"])]})
    with pytest.raises(ValidationError):
        CrossTaskView.model_validate(base | {"steps": [step("a", depends_on=["a"])]})
    with pytest.raises(ValidationError):
        CrossTaskView.model_validate(base | {"steps": [
            step("a", depends_on=["b"]), step("b", depends_on=["a"]),
        ]})
    with pytest.raises(ValidationError):
        CrossTaskView.model_validate(base | {"steps": [step("a")], "plan_step_ids": ["ghost"]})
    with pytest.raises(ValidationError):
        CrossTaskView.model_validate(base | {"steps": [step("a")], "active_step_id": "ghost"})
    chained = CrossTaskView.model_validate(base | {
        "steps": [step("query"), step("pay", depends_on=["query"])],
        "plan_step_ids": ["query", "pay"], "active_step_id": "pay",
    })
    assert chained.steps[1].depends_on == ["query"]


# --- CT08: the shared envelope still routes waiting states ---


def test_ct08_waiting_rules_of_the_shared_envelope_still_hold():
    interaction = {
        "interaction_id": "I1", "kind": "input", "prompt": "留多少生活费？",
        "required_fields": [], "options": [], "record_ref": None,
    }
    with pytest.raises(ValidationError):
        TaskView[CrossTaskView].model_validate({
            "task_id": "T1", "run_id": "R1", "status": "waiting_approval",
            "data": {"scenario": None, "plan_revision": 1, "steps": [], "budget": None, "summary": "s"},
            "message": "m", "interaction": interaction, "error": None,
            "allowed_actions": ["provide_input"], "recovery_required": False, "recovery_reason": None,
            "module": "cross", "thread_id": "TH1", "demo_round_id": "D1",
            "snapshot_at": NOW, "task_revision": 1, "cancel_requested": False,
        })


# --- CT09: arrangement and budget equations ---


def test_ct09_arrangement_equations_cover_both_reserve_calibers():
    includes = ArrangementView.model_validate(arrangement())
    assert includes.protected_fen == 150000 and includes.distributable_fen == 350000
    excludes = ArrangementView.model_validate(arrangement(
        reserve_includes_known_debits=False, protected_fen=153900, distributable_fen=346100,
    ))
    assert excludes.distributable_fen == 346100
    negative = ArrangementView.model_validate(arrangement(
        base_fen=100000, living_reserve_fen=150000, protected_fen=150000, distributable_fen=-50000,
    ))
    assert negative.distributable_fen < 0
    for payload in (
        arrangement(protected_fen=153900),
        arrangement(distributable_fen=340000),
        arrangement(funds_basis="available_balance"),
        arrangement(income_transaction_ids=["tx1", "tx1"]),
    ):
        with pytest.raises(ValidationError):
            ArrangementView.model_validate(payload)
    available = ArrangementView.model_validate(arrangement(
        funds_basis="available_balance", income_transaction_ids=[],
    ))
    assert available.income_transaction_ids == []


def test_ct09_budget_view_equations_and_adoption_link():
    view = BudgetView.model_validate({
        "budget_ref": {"budget_id": "B1", "version": 1}, "purpose": "日常",
        "scope": SCOPE, "personal_limit_fen": 300000, "used_fen": 260000,
        "remaining_fen": 40000, "facts_as_of": NOW, "adopted": True,
    })
    assert view.remaining_fen == 40000
    with pytest.raises(ValidationError):
        BudgetView.model_validate({**view.model_dump(), "remaining_fen": 39999})
    with pytest.raises(ValidationError):
        BudgetView.model_validate(view.model_dump() | {"adopted": True, "budget_ref": None})
    with pytest.raises(ValidationError):
        BudgetView.model_validate(view.model_dump() | {"adopted": False})


def test_ct09_adoption_and_commitment_records_keep_their_shapes():
    adopted = AdoptedArrangement.model_validate({
        "arrangement_id": "arr_01", "user_id": "U1", "demo_round_id": "D1",
        "source_task_id": "T1", "plan_revision": 1, "funds_basis": "selected_income",
        "payer_account_id": "own_daily", "income_transaction_ids": ["tx_pension_01"],
        "base_fen": 500000,
        "living_reserve_fen": 150000, "reserve_includes_known_debits": True,
        "upcoming_debit_scope": SCOPE, "known_debits_fen": 3900,
        "adopted_at": NOW, "adoption_interaction_id": "I1", "status": "active",
    })
    assert adopted.status == "active"
    with pytest.raises(ValidationError):
        AdoptedArrangement.model_validate({**adopted.model_dump(), "status": "paused"})
    AdoptedBudget.model_validate({
        "budget_id": "B1", "user_id": "U1", "demo_round_id": "D1", "source_task_id": "T1",
        "version": 1, "scope": SCOPE, "purpose": "日常", "personal_limit_fen": 300000,
        "adopted_at": NOW, "adoption_interaction_id": "I1", "status": "active",
    })
    commitment = BudgetCommitment.model_validate({
        "budget_ref": {"budget_id": "B1", "version": 1}, "task_id": "T1",
        "commitment_id": "C1", "committed_fen": 50000, "unconsumed_fen": 50000,
        "freeze_id": None, "operation_ids": [uuid4()], "settled_transaction_ids": [],
        "state": "pending", "updated_at": NOW,
    })
    assert commitment.state == "pending"
    with pytest.raises(ValidationError):
        BudgetCommitment.model_validate({**commitment.model_dump(), "unconsumed_fen": 50001})
    with pytest.raises(ValidationError):
        duplicated = commitment.model_dump()
        BudgetCommitment.model_validate(
            duplicated | {"operation_ids": [duplicated["operation_ids"][0], duplicated["operation_ids"][0]]},
        )


# --- CT constraints: contradiction and duplicates ---


def test_funds_basis_contradiction_is_rejected_but_clarification_is_allowed():
    ex02 = CrossConstraints.model_validate({
        "funds_basis": "selected_income", "arrangement_amount_fen": 500000,
        "living_reserve_fen": 150000, "reserve_includes_known_debits": True,
        "income_transaction_ids": ["tx_pension_01"],
        "allocations": [
            {"destination": "transfer", "target_account_id": "own_savings", "amount_fen": 250000},
            {"destination": "transfer", "payee": {"kind": "saved", "payee_id": "family_01"}, "amount_fen": 100000},
            {"destination": "retain", "amount_fen": 150000},
        ],
    })
    assert len(ex02.allocations) == 3
    with pytest.raises(ValidationError):
        CrossConstraints.model_validate({
            "funds_basis": "available_balance", "income_transaction_ids": ["tx_pension_01"],
        })
    missing_ids_ok = CrossConstraints.model_validate({"funds_basis": "selected_income"})
    assert missing_ids_ok.income_transaction_ids is None
    with pytest.raises(ValidationError):
        CrossConstraints.model_validate({"income_transaction_ids": ["tx1", "tx1"]})
    with pytest.raises(ValidationError):
        CrossConstraints.model_validate({"selected_subscription_ids": ["s1", "s1"]})


# --- CT13: delivery details keep the controlled F36 shape ---


def test_ct13_delivery_details_match_their_kind():
    request = SubmitDetailsRequest.model_validate({
        "request_id": str(uuid4()), "interaction_id": "I1", "kind": "delivery",
        "fields": {"recipient_name": "张三", "phone": "13800000000", "address": "某市某区 1 号"},
    })
    assert request.kind == "delivery"
    with pytest.raises(ValidationError):
        SubmitDetailsRequest.model_validate({
            "request_id": str(uuid4()), "interaction_id": "I1", "kind": "delivery",
            "fields": {"account_number": "6200000000000001", "account_name": "张三"},
        })


# --- CT15: birthday bank inputs, receipts and views ---


def test_ct15_freeze_inputs_reject_non_positive_amounts_and_keep_the_view_equation():
    FreezeFundsInput.model_validate({"account_id": "own_daily", "amount_fen": 50000, "reason": "生日"})
    for bad_input in (0, -1):
        with pytest.raises(ValidationError):
            FreezeFundsInput.model_validate({"account_id": "a", "amount_fen": bad_input, "reason": "r"})
        with pytest.raises(ValidationError):
            CaptureFrozenInput.model_validate({
                "freeze_id": "f", "amount_fen": bad_input, "merchant_id": "m",
                "merchant_name": "商户", "purpose": "p", "category": "shopping",
            })
        with pytest.raises(ValidationError):
            ReleaseFrozenInput.model_validate({"freeze_id": "f", "amount_fen": bad_input})
    FreezeView.model_validate({
        "freeze_id": "freeze_01", "account_id": "own_daily", "original_amount_fen": 50000,
        "captured_total_fen": 46700, "released_total_fen": 3300, "remaining_fen": 0, "as_of": NOW,
    })
    with pytest.raises(ValidationError):
        FreezeView.model_validate({
            "freeze_id": "freeze_01", "account_id": "own_daily", "original_amount_fen": 50000,
            "captured_total_fen": 46700, "released_total_fen": 3300, "remaining_fen": 1, "as_of": NOW,
        })
    GetFreezeInput.model_validate({"freeze_id": "freeze_01"})


def test_ct15_receipts_round_trip_and_delivery_repr_hides_raw_text():
    freeze = FreezeReceipt.model_validate({
        "freeze_id": "f1", "frozen_amount_fen": 50000, "remaining_fen": 0, "balance": balance(),
    })
    assert freeze.remaining_fen == 0
    release = ReleaseReceipt.model_validate({
        "freeze_id": "f1", "released_amount_fen": 30100, "remaining_fen": 0, "balance": balance(),
    })
    assert release.released_amount_fen == 30100
    order = CreateOrderInput.model_validate({
        "product_id": "p_flower", "quantity": 1, "expected_total_fen": 19900,
        "delivery": {
            "recipient_name": "张三", "phone": "13800000000",
            "address": "某市某区 1 号", "deliver_by": NOW,
        },
    })
    assert "张三" not in repr(order) and "13800000000" not in repr(order)
    ProductList.model_validate({"products": []})
