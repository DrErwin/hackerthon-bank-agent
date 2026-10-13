"""Frozen-contract examples and invalid inputs for the first transfer path."""

from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts.audit import (
    BankObservedPayload, SecurityDecidedPayload, ToolFinishedPayload, ToolStartedPayload,
)
from app.contracts.bills import (
    AccountSourceAsOf, BillReport, BillScope, SpendingSummary,
)
from app.contracts import (
    AccountList, AuditEvent, CapabilityDefinition, ConfirmationRecord,
    DetailsResponse, ExportView, OperationResult, PayeeList, PayeeVerification, QueryResult,
    SecurityDecision, StartTransferInput, StreamEvent, SubmitDetailsRequest,
    TaskRecordsView, TaskView, TransferReceipt, TransferTaskView, VerificationChallenge,
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


def bill_report():
    """A second-module (L03) result: the platform hands it back as the task's own payload."""

    as_of = "2026-09-30T08:00:00+08:00"
    summary = SpendingSummary(
        scope=BillScope(account_ids=["A1"], start_at="2026-09-01T00:00:00+08:00",
                        end_at="2026-09-30T00:00:00+08:00"),
        as_of=as_of,
        source_as_of=[AccountSourceAsOf(account_id="A1", as_of=as_of)],
        transaction_count=0, consumption_gross_fen=0, consumption_refund_fen=0,
        consumption_net_fen=0, transfer_out_fen=0, transfer_in_fen=0,
        categories=[], comparison=None,
    )
    return BillReport(
        report_id="RP1", scope=summary.scope, summary=summary,
        spoken_summary="本期没有消费。", monthly_average_fen=None, statistical_days=0,
        average_basis="无可统计天数", generated_at=as_of,
    )


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
    adapter = TypeAdapter(QueryResult[AccountList])
    failure = adapter.validate_python({
        "kind": "error", "error": {"code": "DEPENDENCY_UNAVAILABLE", "details": {}},
    })
    assert failure.kind == "error"
    assert adapter.validate_json(adapter.dump_json(failure)).kind == "error"
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "ok", "data": None})
    assert adapter.validate_python({"kind": "ok", "data": {"accounts": []}}).data.accounts == []
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "ok", "data": []})


def test_payee_queries_keep_named_results_and_match_consistent():
    payees = TypeAdapter(QueryResult[PayeeList]).validate_python({
        "kind": "ok", "data": {"payees": [payee() | {"last_transfer_at": None}]},
    })
    assert payees.data.payees[0].bank_name == "模拟银行"
    assert PayeeVerification.model_validate({"matched": False, "payee": None}).payee is None
    assert PayeeVerification.model_validate({"matched": True, "payee": payee()}).matched
    for inconsistent in ({"matched": True, "payee": None}, {"matched": False, "payee": payee()}):
        with pytest.raises(ValidationError):
            PayeeVerification.model_validate(inconsistent)


def test_controlled_details_form_has_kind_specific_fields_and_response():
    request_id = str(uuid4())
    search = SubmitDetailsRequest.model_validate({
        "request_id": request_id, "interaction_id": "I1", "kind": "payee_search",
        "fields": {"kind": "phone", "value": "13800000000"},
    })
    assert search.fields.value == "13800000000"
    assert "13800000000" not in repr(search)
    manual = SubmitDetailsRequest.model_validate({
        "request_id": request_id, "interaction_id": "I1", "kind": "payee",
        "fields": {"account_number": "62220001", "account_name": "王明"},
    })
    assert "62220001" not in repr(manual)
    with pytest.raises(ValidationError):
        SubmitDetailsRequest.model_validate({
            "request_id": request_id, "interaction_id": "I1", "kind": "payee",
            "fields": {"kind": "phone", "value": "13800000000"},
        })
    response = DetailsResponse[TransferTaskView].model_validate({
        "detail_ref": "DETAIL1", "display_fields": [
            {"name": "payee", "label": "收款人", "value_text": "王*"},
        ],
        "candidates": None, "task": task(),
    })
    assert DetailsResponse[TransferTaskView].model_validate_json(response.model_dump_json()) == response


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


def test_release_audit_payloads_can_carry_both_controlled_references():
    operation_id = str(uuid4())
    release_refs = {"release_authorization_id": "REL1", "freeze_id": "FR1"}
    cases = (
        (SecurityDecidedPayload, {"decision": {
            "decision_id": "DEC1", "task_id": "T1", "run_id": "R1",
            "action_name": "bank.release_frozen", "parameters_ref": "PARAM1",
            "operation_id": operation_id, "action_revision": 1, "phase": "execution",
            "operation_level": "sensitive", "risk_level": "medium", "decision": "allow",
            "reason_codes": [], "rule_ids": ["RELEASE"], "policy_version": "v1",
            "authorization_snapshot_ref": "AUTH1", "evidence_refs": [],
            "interaction": None, "checked_at": NOW, "message": "可以收尾",
        }}),
        (ToolStartedPayload, {
            "tool_call_id": "TC1", "tool_name": "bank.release_frozen",
            "tool_version": "v1", "arguments_ref": "ARG1",
            "decision_id": "DEC1", "operation_id": operation_id,
        }),
        (ToolFinishedPayload, {
            "tool_call_id": "TC1", "operation_id": operation_id,
            "result_ref": "EV1", "duration_ms": 12, "error": None,
        }),
        (BankObservedPayload, {
            "operation_id": operation_id, "lookup": "found", "operation_status": "succeeded",
            "transaction_id": None, "receipt_ref": "EV1", "error": None,
        }),
    )
    for payload_type, fields in cases:
        payload = payload_type.model_validate(fields | release_refs)
        assert payload_type.model_validate_json(payload.model_dump_json()) == payload


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


def test_task_records_view_carries_history_without_secrets():
    records = TaskRecordsView.model_validate({
        "task_id": "T1",
        "confirmations": [{
            "confirmation_id": "C1", "task_id": "T1", "confirmation_version": 1,
            "display_fields": [
                {"name": "amount", "label": "金额", "value_text": "500.00 元"},
                {"name": "payee", "label": "收款人", "value_text": "王*"},
            ],
            "created_at": NOW, "expires_at": "2026-09-28T11:00:00+08:00",
            "decision": "approved",
        }],
        "verifications": [{
            "challenge_id": "V1", "task_id": "T1", "created_at": NOW,
            "summary": None, "required_methods": ["code"],
            "code_expires_at": "2026-09-28T10:05:00+08:00",
            "face_started_at": None, "face_expires_at": None,
            "code_result": "passed", "face_result": "not_required",
            "challenge_status": "passed", "consecutive_code_failures": 0,
        }],
    })
    restored = TaskRecordsView.model_validate_json(records.model_dump_json())
    assert restored == records
    assert restored.confirmations[0].decision == "approved"
    assert restored.verifications[0].created_at is not None
    # Replay views never carry a code value, only its result and expiry.
    assert "code" not in restored.verifications[0].model_dump()
    for missing in (
        {"task_id": ""},
        {"confirmations": [{"confirmation_id": "C1"}]},
        {"verifications": [{k: v for k, v in records.verifications[0].model_dump().items()
                            if k != "created_at"}]},
    ):
        with pytest.raises(ValidationError):
            TaskRecordsView.model_validate(records.model_dump() | missing)


def test_task_view_names_the_business_module_and_keeps_old_producers_valid():
    """F08—F15 views tell the frontend which business slot to render (§6.5)."""

    unnamed = TaskView[TransferTaskView].model_validate(task())
    assert unnamed.module is None
    named = TaskView[TransferTaskView].model_validate(task() | {"module": "transfer"})
    assert named.module == "transfer"
    assert TaskView[TransferTaskView].model_validate_json(named.model_dump_json()).module == "transfer"
    event = StreamEvent.model_validate({
        "event_id": "E1", "thread_id": "TH1", "session_id": "S1",
        "task_id": "T1", "run_id": "R1", "module": "bills",
        "event_type": "task_updated", "occurred_at": NOW, "payload": task() | {"module": "bills"},
    })
    assert event.payload.module == "bills"
    for broken in ({"module": "schedule"}, {"module": ""}, {"module": "transfer-agent"}):
        with pytest.raises(ValidationError):
            TaskView[TransferTaskView].model_validate(task() | broken)


def test_task_updated_event_carries_the_second_module_payload():
    """§6.5/§6.6: data is the owning module's displayable result, not the transfer view (Issue #122)."""

    report = bill_report()
    payload = task() | {"module": "bills", "data": report.model_dump(mode="json")}
    body = {
        "event_id": "E1", "thread_id": "TH1", "session_id": "S1",
        "task_id": "T1", "run_id": "R1", "module": "bills",
        "event_type": "task_updated", "occurred_at": NOW, "payload": payload,
    }
    event = StreamEvent.model_validate(body)
    assert event.payload.module == "bills"
    # The whole second-module payload survives parsing and a JSON round trip.
    assert event.payload.data == report.model_dump(mode="json")
    assert StreamEvent.model_validate_json(event.model_dump_json()).payload.data \
        == report.model_dump(mode="json")
    for broken in ("schedule", ""):
        with pytest.raises(ValidationError):
            StreamEvent.model_validate(body | {"payload": payload | {"module": broken}})


def test_export_view_reports_one_state_with_a_controlled_download_path():
    waiting = ExportView.model_validate({
        "export_id": "X1", "kind": "details", "status": "waiting_verification",
        "task_id": "T1", "file_name": None, "media_type": None,
        "download_path": None, "error": None,
    })
    assert waiting.download_path is None and waiting.task_id == "T1"
    ready = ExportView.model_validate({
        "export_id": "X1", "kind": "card", "status": "ready", "task_id": None,
        "file_name": "report.html", "media_type": "text/html",
        "download_path": "/api/v1/exports/X1/download", "error": None,
    })
    assert ExportView.model_validate_json(ready.model_dump_json()) == ready
    failed = ExportView.model_validate({
        "export_id": "X2", "kind": "audit", "status": "failed", "task_id": None,
        "file_name": None, "media_type": None, "download_path": None,
        "error": {"code": "DEPENDENCY_UNAVAILABLE", "source": "platform", "field": None,
                  "reason": "导出资源暂不可用", "upstream_code": None},
    })
    assert failed.error.code == "DEPENDENCY_UNAVAILABLE"
    for broken in (
        {"kind": "report"},
        {"status": "pending"},
        {"export_id": ""},
        {"file_name": 1},
        {"download_path": "C:\\tmp\\report.html"},
        {"download_path": "https://example.test/report.html"},
        {"download_path": "//example.test/report.html"},
        {"download_path": "exports/X1/download"},
    ):
        with pytest.raises(ValidationError):
            ExportView.model_validate(ready.model_dump() | broken)
    # A sensitive details export always belongs to the task that verified it (§6.7).
    with pytest.raises(ValidationError):
        ExportView.model_validate({
            "export_id": "X3", "kind": "details", "status": "preparing", "task_id": None,
            "file_name": None, "media_type": None, "download_path": None, "error": None,
        })
