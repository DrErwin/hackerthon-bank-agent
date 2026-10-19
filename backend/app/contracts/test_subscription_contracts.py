"""Public-contract tests for scenario 05 subscription / auto-debit models (§5.5, §7A)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts import (
    ModuleError, SubscriptionCancelInput, SubscriptionCancelReceipt, SubscriptionItem,
    SubscriptionListInput, SubscriptionListResult, SubscriptionMandate, SubscriptionMandateList,
    SubscriptionTaskView, TaskView, TransferTaskView,
)

NOW = "2026-10-19T09:00:00+08:00"
LATER = "2026-10-25T09:00:00+08:00"


def mandate(**overrides) -> dict:
    payload = {
        "mandate_id": "sub_001", "account_id": "A1", "account_masked": "****0001",
        "merchant_id": "M_UYUN", "merchant_name": "优酷视频", "service_name": "优酷 VIP 连续包月",
        "amount_fen": 2500, "cycle": "monthly", "next_billing_at": LATER, "last_billed_at": NOW,
        "status": "active", "signed_at": NOW, "cancelled_at": None, "cancel_operation_id": None,
    }
    return payload | overrides


def item(**overrides) -> dict:
    payload = {
        "subscription_id": "sub_001", "source_type": "mandate", "mandate_id": "sub_001",
        "merchant_id": "M_UYUN", "merchant_name": "优酷视频", "service_name": "优酷 VIP 连续包月",
        "amount_fen": 2500, "cycle": "monthly", "account_id": "A1", "account_masked": "****0001",
        "last_billed_at": NOW, "next_billing_at": LATER, "status": "active",
        "can_cancel_in_bank": True, "days_until_renewal": 6, "is_upcoming_renewal": True,
        "external_cancel_guide": None, "billed_count": 6, "billed_total_fen": 15000,
    }
    return payload | overrides


def list_result(**overrides) -> dict:
    row = item()
    payload = {
        "items": [row], "upcoming_renewals": [row], "active_count": 1,
        "upcoming_total_fen": 2500, "as_of": NOW,
    }
    return payload | overrides


def task_view(**overrides) -> dict:
    payload = {"action": "list", "list_result": list_result()}
    return payload | overrides


def task() -> dict:
    return {
        "task_id": "T1", "run_id": "R1", "status": "succeeded", "data": task_view(),
        "message": "已列出自动扣费。", "interaction": None, "error": None,
        "allowed_actions": [], "recovery_required": False, "recovery_reason": None,
        "thread_id": "TH1", "demo_round_id": "D1", "snapshot_at": NOW,
        "task_revision": 1, "cancel_requested": False,
    }


def test_subscription_models_round_trip():
    mandate_row = SubscriptionMandate.model_validate(mandate())
    assert mandate_row.cycle == "monthly" and mandate_row.status == "active"
    assert SubscriptionMandateList(mandates=[mandate_row], as_of=NOW).mandates[0].amount_fen == 2500
    view = SubscriptionTaskView.model_validate(task_view())
    assert view.list_result.upcoming_total_fen == 2500
    payload = task() | {"module": "subscription"}
    named = TaskView[SubscriptionTaskView].model_validate(payload)
    assert named.module == "subscription"
    assert TaskView[SubscriptionTaskView].model_validate_json(named.model_dump_json()).data.action == "list"


def test_subscription_models_forbid_extra_fields():
    with pytest.raises(ValidationError):
        SubscriptionItem.model_validate(item() | {"amount_cents": 2500})
    with pytest.raises(ValidationError):
        SubscriptionListInput.model_validate(
            {"request_id": "8f14e45f-ea0e-4a1e-9f2b-1c2d3e4f5a6b", "intent_text": "查", "scope": {}})


def test_amounts_and_counts_reject_bad_numbers():
    for broken in ({"amount_fen": -1}, {"amount_fen": 12.5}, {"amount_fen": True}):
        with pytest.raises(ValidationError):
            SubscriptionItem.model_validate(item() | broken)
    with pytest.raises(ValidationError):
        SubscriptionItem.model_validate(item() | {"billed_count": -1})
    with pytest.raises(ValidationError):
        SubscriptionItem.model_validate(item() | {"billed_count": 0})


def test_reminder_days_stay_inside_the_contract_window():
    request = {"request_id": "8f14e45f-ea0e-4a1e-9f2b-1c2d3e4f5a6b", "intent_text": "查自动扣费"}
    assert SubscriptionListInput.model_validate(request).reminder_days == 30
    assert SubscriptionListInput.model_validate(request | {"reminder_days": 90}).reminder_days == 90
    for broken in (0, 91, "30", 30.0):
        with pytest.raises(ValidationError):
            SubscriptionListInput.model_validate(request | {"reminder_days": broken})
    with pytest.raises(ValidationError):
        SubscriptionListInput.model_validate(request | {"account_ids": []})
    with pytest.raises(ValidationError):
        SubscriptionListInput.model_validate(request | {"account_ids": ["A1", "A1"]})


def test_item_source_and_status_rules():
    with pytest.raises(ValidationError):
        SubscriptionItem.model_validate(item() | {"mandate_id": None})
    with pytest.raises(ValidationError):
        SubscriptionItem.model_validate(item() | {
            "source_type": "suspected_ledger", "status": "suspected", "can_cancel_in_bank": False})
    with pytest.raises(ValidationError):
        SubscriptionItem.model_validate(item() | {
            "source_type": "suspected_ledger", "status": "suspected", "can_cancel_in_bank": True})
    with pytest.raises(ValidationError):
        SubscriptionItem.model_validate(item() | {
            "status": "cancelled", "can_cancel_in_bank": False,
            "next_billing_at": None, "is_upcoming_renewal": True})
    suspected = SubscriptionItem.model_validate(item() | {
        "subscription_id": "sus_oasis_01", "source_type": "suspected_ledger", "mandate_id": None,
        "status": "suspected", "can_cancel_in_bank": False, "is_upcoming_renewal": False,
        "days_until_renewal": None, "next_billing_at": None, "channel": "快捷支付"})
    assert suspected.mandate_id is None and suspected.channel == "快捷支付"


def test_list_result_stays_consistent_with_its_rows():
    with pytest.raises(ValidationError):
        SubscriptionListResult.model_validate(list_result() | {"upcoming_renewals": []})
    with pytest.raises(ValidationError):
        SubscriptionListResult.model_validate(list_result() | {"upcoming_total_fen": 0})
    with pytest.raises(ValidationError):
        SubscriptionListResult.model_validate(list_result() | {"active_count": 0})
    with pytest.raises(ValidationError):
        SubscriptionListResult.model_validate(list_result() | {"items": [item(), item()]})
    with pytest.raises(ValidationError):
        SubscriptionListResult.model_validate(list_result() | {"suspected_scan_status": "insufficient_data"})
    scanned = SubscriptionListResult.model_validate(list_result() | {
        "suspected_scan_status": "insufficient_data", "suspected_scan_reason": "流水不足 3 个月"})
    assert scanned.suspected_scan_reason == "流水不足 3 个月"


def test_task_view_matches_action_to_payload():
    with pytest.raises(ValidationError):
        SubscriptionTaskView.model_validate({"action": "list"})
    with pytest.raises(ValidationError):
        SubscriptionTaskView.model_validate({"action": "cancel", "list_result": list_result()})
    with pytest.raises(ValidationError):
        SubscriptionTaskView.model_validate({"action": "list", "list_result": list_result(), "operation_id": "x"})
    receipt = SubscriptionCancelReceipt.model_validate({
        "mandate_id": "sub_001", "account_id": "A1", "account_masked": "****0001",
        "merchant_id": "M_UYUN", "merchant_name": "优酷视频", "service_name": "优酷 VIP 连续包月",
        "amount_fen": 2500, "cycle": "monthly", "previous_next_billing_at": LATER,
        "effective_stop_at": LATER, "cancelled_at": NOW,
    })
    operation = {"operation_id": "b3f1c2d4-5e6a-4b7c-8d9e-0f1a2b3c4d5e",
                 "operation_type": "bank.cancel_subscription", "operation_status": "succeeded",
                 "recorded_at": NOW, "updated_at": NOW, "receipt": receipt.model_dump(mode="json"),
                 "failure": None}
    cancel = SubscriptionTaskView.model_validate({
        "action": "cancel", "selected_item": item(), "operation_id": operation["operation_id"],
        "operation": operation,
    })
    assert cancel.operation.receipt.status == "cancelled"
    with pytest.raises(ValidationError):
        SubscriptionTaskView.model_validate({
            "action": "cancel", "selected_item": item(),
            "operation_id": "11111111-2222-4333-8444-555555555555", "operation": operation})


def test_cancel_receipt_stops_from_the_previous_next_billing():
    payload = {
        "mandate_id": "sub_001", "account_id": "A1", "account_masked": "****0001",
        "merchant_id": "M_UYUN", "merchant_name": "优酷视频", "service_name": "优酷 VIP 连续包月",
        "amount_fen": 2500, "cycle": "monthly", "previous_next_billing_at": LATER,
        "effective_stop_at": "2026-11-25T09:00:00+08:00", "cancelled_at": NOW,
    }
    with pytest.raises(ValidationError):
        SubscriptionCancelReceipt.model_validate(payload)
    with pytest.raises(ValidationError):
        SubscriptionCancelReceipt.model_validate(payload | {"effective_stop_at": LATER, "status": "active"})


def test_cancelled_mandate_keeps_its_cancellation_facts():
    cancelled = mandate(status="cancelled", next_billing_at=None, cancelled_at=NOW,
                        cancel_operation_id="b3f1c2d4-5e6a-4b7c-8d9e-0f1a2b3c4d5e")
    assert SubscriptionMandate.model_validate(cancelled).cancelled_at is not None
    for broken in (
        {"status": "cancelled", "next_billing_at": None, "cancelled_at": None, "cancel_operation_id": None},
        {"status": "cancelled", "next_billing_at": LATER, "cancelled_at": NOW,
         "cancel_operation_id": "b3f1c2d4-5e6a-4b7c-8d9e-0f1a2b3c4d5e"},
        {"status": "active", "cancelled_at": NOW, "cancel_operation_id": None},
    ):
        with pytest.raises(ValidationError):
            SubscriptionMandate.model_validate(mandate() | broken)


def test_module_error_and_cancel_input_accept_the_subscription_vocabulary():
    error = ModuleError(code="STATE_CONFLICT", source="subscription", field=None,
                        reason="该代扣协议已退订。", upstream_code="STATE_CONFLICT")
    assert error.source == "subscription"
    with pytest.raises(ValidationError):
        ModuleError(code="X", source="subscribe", field=None, reason="r", upstream_code=None)
    request = SubscriptionCancelInput.model_validate({
        "request_id": "8f14e45f-ea0e-4a1e-9f2b-1c2d3e4f5a6b",
        "intent_text": "把优酷视频的自动扣费退了"})
    assert request.subscription_id is None and request.merchant_hint is None
    for broken in ({"merchant_hint": "   "}, {"subscription_id": ""}):
        with pytest.raises(ValidationError):
            SubscriptionCancelInput.model_validate({
                "request_id": "8f14e45f-ea0e-4a1e-9f2b-1c2d3e4f5a6b",
                "intent_text": "退订"} | broken)


def test_task_view_still_accepts_the_existing_modules():
    for module in ("transfer", "bills", "cross", None):
        payload = task() | {"data": {"operation_id": None, "payer_account_id": None, "payee": None,
                                     "amount_fen": None, "operation": None}, "module": module}
        assert TaskView[TransferTaskView].model_validate(payload).module == module
