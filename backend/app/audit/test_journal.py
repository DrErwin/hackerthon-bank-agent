"""Audit write reliability and read-only replay boundaries."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import uuid4

import pytest

from app.audit.journal import AuditJournal, AuditReader, AuditViewer
from app.contracts.audit import AuditEvent, ChatMessagePayload, ToolStartedPayload
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
