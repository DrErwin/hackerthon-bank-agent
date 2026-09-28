"""Frozen-contract examples and invalid inputs for the first transfer path."""

from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts import (
    AccountSummary, AuditEvent, CapabilityDefinition, ConfirmationRecord,
    OperationResult, QueryResult, SecurityDecision, StartTransferInput,
    StreamEvent, TaskView, TransferReceipt, TransferTaskView, VerificationChallenge,
    VerificationCodeRequest,
)


NOW = "2026-09-28T10:00:00+08:00"


def payee():
    return {
        "payee_id": "P1", "name_masked": "王*", "account_masked": "****1234",
        "remark": None, "bank_name": "模拟银行",
    }


def receipt():
    return {
        "transaction_id": "TX1", "payer_account_id": "A1", "payee": payee(),
        "amount_fen": 50000, "fee_fen": 0, "arrival_mode": "instant",
        "completed_at": NOW,
        "balance": {
            "account_id": "A1", "book_balance_fen": 50000,
            "frozen_balance_fen": 0, "available_balance_fen": 50000, "as_of": NOW,
        },
    }


def operation():
    return {
        "operation_id": str(uuid4()), "operation_type": "bank.submit_transfer",
        "operation_status": "succeeded", "recorded_at": NOW, "updated_at": NOW,
        "receipt": receipt(), "failure": None,
    }


def task():
    op = operation()
    return {
        "task_id": "T1", "run_id": "R1", "status": "succeeded",
        "data": {
            "operation_id": op["operation_id"], "payer_account_id": "A1",
            "payee": payee(), "amount_fen": 50000, "operation": op,
        },
        "message": "转账成功", "interaction": None, "error": None,
        "allowed_actions": [], "recovery_required": False, "recovery_reason": None,
        "thread_id": "TH1", "demo_round_id": "D1", "snapshot_at": NOW,
        "task_revision": 3, "cancel_requested": False,
    }


def test_transfer_task_and_bank_result_round_trip():
    model = TaskView[TransferTaskView].model_validate(task())
    restored = TaskView[TransferTaskView].model_validate_json(model.model_dump_json())
    assert restored == model
    assert restored.data.operation.receipt.transaction_id == "TX1"
    assert restored.data.operation.operation_id == restored.data.operation_id


def test_task_update_event_carries_the_same_snapshot_revision():
    event = StreamEvent.model_validate({
        "event_id": "E1", "thread_id": "TH1", "session_id": "S1",
        "task_id": "T1", "run_id": "R1", "module": "transfer",
        "event_type": "task_updated", "occurred_at": NOW, "payload": task(),
    })
    restored = StreamEvent.model_validate_json(event.model_dump_json())
    assert restored.payload.task_revision == 3
    with pytest.raises(ValidationError):
        StreamEvent.model_validate(event.model_dump() | {"event_type": "message_completed"})


def test_query_error_is_not_an_empty_success():
    adapter = TypeAdapter(QueryResult[list[AccountSummary]])
    failure = adapter.validate_python({
        "kind": "error", "error": {"code": "DEPENDENCY_UNAVAILABLE", "details": {}},
    })
    assert failure.kind == "error"
    assert adapter.validate_json(adapter.dump_json(failure)).kind == "error"
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "ok", "data": None})


@pytest.mark.parametrize("status,receipt_value,failure", [
    ("succeeded", None, None),
    ("failed", receipt(), None),
    ("processing", receipt(), None),
])
def test_bank_result_rejects_false_outcomes(status, receipt_value, failure):
    bad = operation() | {"operation_status": status, "receipt": receipt_value, "failure": failure}
    with pytest.raises(ValidationError):
        OperationResult[TransferReceipt].model_validate(bad)


def test_invalid_task_state_missing_id_and_wrong_types_are_rejected():
    original = task()
    for change in (
        {"status": "approved"}, {"task_id": ""}, {"task_id": None},
        {"task_revision": "3"}, {"snapshot_at": "2026-09-28T10:00:00"},
        {"snapshot_at": 1_000_000},
    ):
        with pytest.raises(ValidationError):
            TaskView[TransferTaskView].model_validate(original | change)


def test_waiting_approval_requires_controlled_record_reference():
    waiting = task() | {
        "status": "waiting_approval", "data": None,
        "interaction": {
            "interaction_id": "I1", "kind": "confirmation", "prompt": "确认办理？",
            "required_fields": [], "options": [], "record_ref": None,
        },
    }
    with pytest.raises(ValidationError):
        TaskView[TransferTaskView].model_validate(waiting)
    waiting["interaction"]["record_ref"] = "C1"
    assert TaskView[TransferTaskView].model_validate(waiting).status == "waiting_approval"


def test_confirmation_verification_and_security_bind_the_same_action():
    operation_id = str(uuid4())
    confirmation = ConfirmationRecord.model_validate({
        "confirmation_id": "C1", "confirmation_version": 1,
        "user_id": "U1", "session_id": "S1", "demo_round_id": "D1", "task_id": "T1",
        "operation_id": operation_id, "action_name": "bank.submit_transfer",
        "action_revision": 1, "parameters_ref": "PARAM1", "display_fields": [
            {"name": "amount", "label": "金额", "value_text": "500.00 元"},
        ],
        "created_at": NOW, "expires_at": "2026-09-28T11:00:00+08:00",
        "decision": "approved", "decided_at": NOW,
    })
    summary = {
        "operation_id": operation_id, "action_revision": 1,
        "source_confirmation_id": confirmation.confirmation_id,
        "source_confirmation_version": confirmation.confirmation_version,
        "action_name": "bank.submit_transfer", "amount_fen": 50000,
        "payee": payee(), "display_fields": confirmation.model_dump(mode="json")["display_fields"],
    }
    challenge_data = {
        "challenge_id": "V1", "user_id": "U1", "session_id": "S1",
        "demo_round_id": "D1", "task_id": "T1", "purpose": "action_step_up",
        "operation_id": operation_id, "action_revision": 1, "summary": summary,
        "required_methods": ["code", "mock_face"], "created_at": NOW,
        "code_created_at": NOW, "code_expires_at": "2026-09-28T10:05:00+08:00",
        "face_started_at": None, "face_expires_at": None, "challenge_status": "pending",
        "code_result": "pending", "face_result": "pending",
        "consecutive_code_failures": 0,
    }
    challenge = VerificationChallenge.model_validate(challenge_data)
    assert VerificationChallenge.model_validate_json(challenge.model_dump_json()) == challenge
    with pytest.raises(ValidationError):
        VerificationChallenge.model_validate(challenge_data | {"action_revision": 2})

    decision = SecurityDecision.model_validate({
        "decision_id": "DEC1", "task_id": "T1", "run_id": "R1",
        "action_name": "bank.submit_transfer", "parameters_ref": "PARAM1",
        "operation_id": operation_id, "action_revision": 1, "phase": "execution",
        "operation_level": "sensitive", "risk_level": "medium", "decision": "allow",
        "reason_codes": [], "rule_ids": ["RISK1"], "policy_version": "v1",
        "authorization_snapshot_ref": "AUTH1", "evidence_refs": [],
        "interaction": None, "checked_at": NOW, "message": "可以继续",
    })
    assert decision.operation_id == challenge.operation_id == confirmation.operation_id
    with pytest.raises(ValidationError):
        SecurityDecision.model_validate(decision.model_dump() | {"authorization_snapshot_ref": None})


def test_tool_declaration_disallows_write_auto_retry():
    declaration = {
        "name": "bank.submit_transfer", "input_schema_ref": "TransferInput",
        "output_schema_ref": "TransferReceipt", "required_permissions": ["transfer"],
        "operation_level": "sensitive", "side_effect": True,
        "confirmation_policy": "per_action", "timeout_ms": 4000,
        "retry_policy": "read_only", "handler_ref": "bank.submit_transfer",
    }
    with pytest.raises(ValidationError):
        CapabilityDefinition.model_validate(declaration)


def test_audit_event_checks_payload_and_never_invents_bank_failure():
    operation_id = str(uuid4())
    event = {
        "event_id": "E1", "trace_id": "TR1", "span_id": "SP1", "sequence": 1,
        "parent_span_id": None, "demo_round_id": "D1", "actor_id": "U1",
        "session_id": "S1", "target_session_id": None, "target_user_id": "U1",
        "thread_id": "TH1", "task_id": "T1", "run_id": "R1", "module": "bank",
        "event_type": "bank.observed", "timestamp": NOW, "logical_at": NOW,
        "outcome": "unknown", "evidence_ref": "EV1", "evidence_status": "available",
        "missing_reason": None,
        "payload": {
            "operation_id": operation_id, "lookup": "not_found",
            "operation_status": None, "transaction_id": None,
            "receipt_ref": None, "error": None,
        },
    }
    model = AuditEvent.model_validate(event)
    assert AuditEvent.model_validate_json(model.model_dump_json()) == model
    with pytest.raises(ValidationError):
        AuditEvent.model_validate(event | {"payload": event["payload"] | {"operation_status": "failed"}})
    with pytest.raises(ValidationError):
        AuditEvent.model_validate(event | {"event_type": "tool.started"})


def test_model_rejects_unexpected_authorization_fields_and_non_uuid4_operation():
    with pytest.raises(ValidationError):
        StartTransferInput.model_validate({
            "request_id": str(uuid4()), "intent_text": "给妈妈转 500 元", "approved": True,
        })
    assert StartTransferInput.model_validate({
        "request_id": "00000000-0000-1000-8000-000000000000",
        "intent_text": "给妈妈转 500 元",
    }).intent_text
    with pytest.raises(ValidationError):
        OperationResult[TransferReceipt].model_validate(
            operation() | {"operation_id": "00000000-0000-1000-8000-000000000000"}
        )
    for amount in (0, "50000"):
        with pytest.raises(ValidationError):
            StartTransferInput.model_validate({
                "request_id": str(uuid4()), "intent_text": "给妈妈转 500 元",
                "amount_fen": amount,
            })


def test_code_request_masks_secret_when_serialized_or_logged():
    request = VerificationCodeRequest.model_validate({
        "request_id": str(uuid4()), "submission_id": str(uuid4()), "code": "123456",
    })
    assert "123456" not in repr(request)
    assert "123456" not in request.model_dump_json()
    assert request.code.get_secret_value() == "123456"
