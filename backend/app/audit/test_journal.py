"""Audit write reliability and read-only replay boundaries."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import UUID, uuid4

import pytest

from app.audit.journal import AuditJournal, AuditReader, AuditViewer, redact
from app.contracts.audit import (
    AuditEvent, AuthorizationSnapshot, ChatMessagePayload, ModelStartedPayload,
    SecurityDecidedPayload, ToolStartedPayload,
)
from app.storage import StoragePaths
from app.storage.database import connect, transaction


def event(event_type="chat.message", *, sequence=0, evidence_ref="E1",
          evidence_status="available", run_id="R1"):
    payload = (
        ChatMessagePayload(message_id="M1", role="user", content_ref="E1", related_task_ids=["T1"])
        if event_type == "chat.message" else
        ToolStartedPayload(
            tool_call_id="C1", tool_name="bank.get_account", tool_version="v1",
            arguments_ref="E1", decision_id="DEC1", operation_id=None,
        )
    )
    return AuditEvent(
        event_id=str(uuid4()), trace_id="TRACE1", span_id=f"SPAN{sequence}",
        sequence=sequence, parent_span_id=None, demo_round_id="D1", actor_id="U1",
        session_id="S1", target_session_id=None, target_user_id="U1",
        thread_id="TH1", task_id="T1", run_id=run_id, module="transfer",
        event_type=event_type, timestamp=datetime.now(timezone.utc), logical_at=None,
        outcome="started" if event_type == "tool.started" else "succeeded",
        evidence_ref=evidence_ref, evidence_status=evidence_status,
        missing_reason=None if evidence_status == "available" else "result was not recorded",
        payload=payload,
    )


def test_redacted_evidence_survives_restart_and_is_scoped(tmp_path):
    path = StoragePaths(tmp_path).application
    journal = AuditJournal(path)
    source = {
        "text": "姓名：李华 手机 13900000002 卡号 6222000000000002 验证码: 123456 地址：演示市示例路1号",
        "password": "do-not-store", "extra": "private-marker",
        "code": "123456",
        "recipient_name": "王阿姨", "recipient_address": "演示市演示区示例路1号",
    }
    journal.append(event(), evidence=source, known_secrets=["private-marker"])
    persisted = path.read_bytes()
    for secret in (b"do-not-store", b"private-marker", b"123456", b"13900000002", b"6222000000000002"):
        assert secret not in persisted
    reader = AuditReader(AuditJournal(path), authorize=lambda viewer, action, round_id, ref: (
        viewer.actor_id == "admin" and round_id == "D1"
    ))
    admin = AuditViewer("admin", "ADMIN_SESSION", "D2")
    detail = reader.timeline(admin, "D1", "T1")[0]
    assert detail.evidence_status == "available"
    assert "139****0002" in detail.evidence
    assert "****0002" in detail.evidence
    assert "李*" in detail.evidence
    assert '"recipient_name":"王**"' in detail.evidence
    assert "[REDACTED]" in detail.evidence
    with pytest.raises(PermissionError):
        reader.timeline(AuditViewer("U1", "S1", "D1"), "D1", "T1")
    with pytest.raises(PermissionError):
        reader.timeline(admin, "D9", "T1")
    with connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    assert count == 4  # original event, allowed read, two denied reads


def test_uuid_operation_survives_redaction_without_exposing_accounts(tmp_path):
    operation_id = UUID("c39aad1a-9bb9-4497-a57a-210489574284")
    base = event(evidence_ref=None, evidence_status="missing")
    decision = {
        "decision_id": "DEC1", "task_id": "T1", "run_id": "R1",
        "action_name": "bank.submit_transfer", "parameters_ref": "PARAM1",
        "operation_id": str(operation_id), "action_revision": 1,
        "phase": "admission", "operation_level": "sensitive",
        "risk_level": "high", "decision": "block",
        "reason_codes": ["HIGH_RISK"], "rule_ids": ["RULE1"],
        "policy_version": "v1", "authorization_snapshot_ref": None,
        "evidence_refs": [], "interaction": None,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "message": "安全规则已阻止交易",
    }
    blocked = AuditEvent.model_validate({
        **base.model_dump(mode="json"), "event_type": "security.decided",
        "payload": SecurityDecidedPayload.model_validate({"decision": decision}).model_dump(mode="json"),
    })
    journal = AuditJournal(StoragePaths(tmp_path).application)
    journal.append(blocked)
    assert journal._events("D1", "T1")[0].payload.decision.operation_id == operation_id
    masked = redact({"text": "手机 13900000002 卡号 6222000000000002"})["text"]
    assert "13900000002" not in masked
    assert "6222000000000002" not in masked


def test_opaque_references_survive_redaction_so_evidence_still_links(tmp_path):
    """A digit run inside a reference is not a card number (subscription ticket 08)."""

    reference = "sub-ref-2b5a4d19634889502aae10d4"
    started = AuditEvent.model_validate({
        **event("tool.started", evidence_ref=None, evidence_status="missing").model_dump(mode="json"),
        "payload": ToolStartedPayload(
            tool_call_id="C1", tool_name="subscription.bank.cancel_subscription", tool_version="0.4.0",
            arguments_ref=reference, decision_id="DEC1", operation_id=None,
        ).model_dump(mode="json"),
    })
    journal = AuditJournal(StoragePaths(tmp_path).application)
    journal.append(started, snapshots={reference: {"mandate_id": "sub_001", "amount_fen": 2500}})
    stored = journal._events("D1", "T1")[0]
    assert stored.payload.arguments_ref == reference
    assert journal._stored_evidence(connect(journal.path), stored, reference) is not None

    clean = redact({"parameters_ref": reference, "source_refs": [reference],
                    "card_number": "6222000000000002"})
    assert clean["parameters_ref"] == reference
    assert clean["source_refs"] == [reference]
    assert "6222000000000002" not in clean["card_number"]
    assert "****0002" in clean["card_number"]
    # A known secret inside a reference is still removed (secret protection wins).
    assert redact({"evidence_ref": "E1-secret-77"}, ("secret",))["evidence_ref"] == "E1-[REDACTED]-77"


def test_export_marks_missing_results_without_running_tools(tmp_path):
    journal = AuditJournal(StoragePaths(tmp_path).application)
    journal.append(event("tool.started", evidence_ref="E1", evidence_status="missing"))
    reader = AuditReader(journal, authorize=lambda *_: True)
    package = json.loads(reader.export_json(AuditViewer("admin", "AS1", "D1"), "D1", "T1"))
    assert len(package["events"]) == 1
    assert package["unpaired_starts"] == [package["events"][0]["event_id"]]
    assert package["missing"][0]["reason"] == "result was not recorded"
    assert package["evidence"] == {}


def test_timeline_keeps_parent_call_and_run_order(tmp_path):
    journal = AuditJournal(StoragePaths(tmp_path).application)
    parent = event(sequence=0)
    child = event("tool.started", sequence=1, evidence_ref=None, evidence_status="missing")
    child.parent_span_id = parent.span_id
    journal.append(parent, evidence={"text": "safe"})
    journal.append(child)
    reader = AuditReader(journal, authorize=lambda *_: True)
    timeline = reader.timeline(AuditViewer("admin", "AS1", "D1"), "D1", "T1")
    assert [item.sequence for item in timeline] == [0, 1]
    assert timeline[1].parent_span_id == timeline[0].span_id


def test_event_and_application_update_share_rollback(tmp_path):
    path = StoragePaths(tmp_path).application
    journal = AuditJournal(path)
    with transaction(path) as connection:
        connection.execute("CREATE TABLE demo_tool_results (value TEXT NOT NULL)")
        connection.execute("INSERT INTO demo_tool_results VALUES ('original')")
    first = event()
    journal.append(first, evidence={"text": "safe"})
    duplicate_sequence = event(sequence=0, evidence_ref=None, evidence_status="missing")
    with pytest.raises(ValueError, match="audit sequence"):
        with transaction(path) as connection:
            connection.execute("UPDATE demo_tool_results SET value = 'new'")
            journal.append_in_transaction(connection, duplicate_sequence)
    with connect(path) as connection:
        value = connection.execute("SELECT value FROM demo_tool_results").fetchone()[0]
        count = connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    assert value == "original"
    assert count == 1


def test_secret_variants_never_reach_persistent_evidence(tmp_path):
    path = StoragePaths(tmp_path).application
    journal = AuditJournal(path)
    journal.append(event(), evidence={
        "cookie": "session=secret123", "credential": "abc123", "refreshToken": "refresh123",
        "text": "验证码是123456；我的口令为abc123", "message": "AB12CD",
        "note": "OTP 739284",
        "code": "AB12CD", "display_fields": [
            {"name": "recipient_address", "value_text": "演示市演示区1号",
             "credential": "nested-secret"},
        ],
    })
    persisted = path.read_bytes()
    for secret in (b"secret123", b"abc123", b"refresh123", b"123456", b"739284", b"AB12CD",
                   b"nested-secret"):
        assert secret not in persisted
    assert "演示市演示区1号" not in path.read_text(errors="ignore")


def test_multiple_payload_snapshots_are_exported_and_missing_refs_marked(tmp_path):
    journal = AuditJournal(StoragePaths(tmp_path).application)
    started = event(sequence=0)
    started = AuditEvent.model_validate({
        **started.model_dump(mode="json"), "event_type": "model.started",
        "payload": ModelStartedPayload(
            model_call_id="CALL1", provider="provider", model="model",
            config_version="v1", request_ref="REQ1",
        ).model_dump(mode="json"),
    })
    journal.append(started, evidence={"text": "response"}, snapshots={"REQ1": {"text": "prompt"}})
    missing = event(sequence=1, evidence_ref=None, evidence_status="missing")
    missing.payload.content_ref = "MISSING1"
    journal.append(missing)
    reader = AuditReader(journal, authorize=lambda *_: True)
    package = json.loads(reader.export_json(AuditViewer("admin", "AS1", "D1"), "D1", "T1"))
    assert set(package["evidence"]) == {"E1", "REQ1"}
    assert package["evidence"]["REQ1"]["content"] == {"text": "prompt"}
    assert any(item.get("evidence_ref") == "MISSING1" for item in package["missing"])


def test_damaged_evidence_is_marked_missing_instead_of_exported(tmp_path):
    path = StoragePaths(tmp_path).application
    journal = AuditJournal(path)
    journal.append(event(), evidence={"text": "safe"})
    with transaction(path) as connection:
        connection.execute("UPDATE audit_evidence SET content = 'damaged' WHERE evidence_id = 'E1'")
    reader = AuditReader(journal, authorize=lambda *_: True)
    package = json.loads(reader.export_json(AuditViewer("admin", "AS1", "D1"), "D1", "T1"))
    assert package["evidence"] == {}
    assert package["missing"][0]["evidence_ref"] == "E1"
    assert package["events"][0]["evidence_status"] == "missing"


def test_sensitive_allow_requires_matching_persisted_authorization(tmp_path):
    journal = AuditJournal(StoragePaths(tmp_path).application)
    operation_id = str(uuid4())
    base = event(sequence=0, evidence_ref=None, evidence_status="missing")
    decision = {
        "decision_id": "DEC1", "task_id": "T1", "run_id": "R1",
        "action_name": "bank.submit_transfer", "parameters_ref": "PARAM1",
        "operation_id": operation_id, "action_revision": 1, "phase": "execution",
        "operation_level": "sensitive", "risk_level": "medium", "decision": "allow",
        "reason_codes": [], "rule_ids": ["RULE1"], "policy_version": "v1",
        "authorization_snapshot_ref": "AUTH1", "evidence_refs": [],
        "interaction": None, "checked_at": datetime.now(timezone.utc).isoformat(),
        "message": "allowed",
    }
    allow = AuditEvent.model_validate({
        **base.model_dump(mode="json"), "event_type": "security.decided",
        "payload": SecurityDecidedPayload.model_validate({"decision": decision}).model_dump(mode="json"),
    })
    with pytest.raises(ValueError, match="authorization snapshot"):
        journal.append(allow, snapshots={"PARAM1": {"amount_fen": 50000}})
    wrong = {
        "user_id": "OTHER", "session_id": "S1", "demo_round_id": "D1", "task_id": "T1",
        "operation_id": operation_id, "action_revision": 1,
        "confirmation": {
            "confirmation_id": "CONF1", "version": 1, "decision": "approved",
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "display_fields": [{"name": "amount", "label": "金额", "value_text": "500元"}],
        },
        "verifications": [], "release_authorization_id": None,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    with pytest.raises(ValueError, match="does not match"):
        journal.append(allow, snapshots={"PARAM1": {"amount_fen": 50000}, "AUTH1": wrong})
    with connect(journal.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM audit_evidence").fetchone()[0] == 0
    snapshot = AuthorizationSnapshot.model_validate(wrong | {"user_id": "U1"})
    journal.append(allow, snapshots={"PARAM1": {"amount_fen": 50000}, "AUTH1": snapshot})
    tool = event("tool.started", sequence=1, evidence_ref=None, evidence_status="missing")
    tool.payload.operation_id = operation_id
    tool.payload.arguments_ref = "ARG1"
    with pytest.raises(ValueError, match="persisted arguments"):
        journal.append(tool)
    journal.append(tool, snapshots={"ARG1": {"amount_fen": 50000}})
    reader = AuditReader(journal, authorize=lambda *_: True)
    package = json.loads(reader.export_json(AuditViewer("admin", "AS1", "D1"), "D1", "T1"))
    assert package["evidence"]["AUTH1"]["content"]["user_id"] == "U1"
    assert package["evidence"]["ARG1"]["content"]["amount_fen"] == 50000


def test_sequence_and_unpaired_calls_are_isolated_by_round_run_and_type(tmp_path):
    journal = AuditJournal(StoragePaths(tmp_path).application)
    first = event("tool.started", evidence_ref=None, evidence_status="missing")
    journal.append(first)
    later_round = event(sequence=0, evidence_ref=None, evidence_status="missing")
    later_round.demo_round_id = "D2"
    journal.append(later_round)
    other_run = event("tool.started", sequence=0, evidence_ref=None,
                      evidence_status="missing", run_id="R2")
    journal.append(other_run)
    reader = AuditReader(journal, authorize=lambda *_: True)
    package = json.loads(reader.export_json(AuditViewer("admin", "AS1", "D1"), "D1", "T1"))
    assert set(package["unpaired_starts"]) == {first.event_id, other_run.event_id}
