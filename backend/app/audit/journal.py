"""Append-only audit storage and a separately authorized read path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Callable, Iterable
from uuid import uuid4

from pydantic import BaseModel

from app.contracts.audit import (
    AuditAccessedPayload, AuditEvent, AuditEventDetail, AuditEventSummary,
    EvidenceSnapshot,
)
from app.storage.database import connect, transaction


REDACTION_VERSION = "v1"
SECRET_FIELD = re.compile(
    r"^(?:password|passwd|secret|token|access_token|api[_-]?key|otp|verification_code|demo_code|sms_code|验证码|密码)$",
    re.I,
)
PERSON_NAME_FIELD = {"account_name", "recipient_name", "payee_name", "customer_name", "person_name"}
PHONE_FIELD = {"phone", "phone_number", "recipient_phone"}
ACCOUNT_FIELD = {"account_number", "card_number"}
ADDRESS_FIELD = {"address", "recipient_address"}
SECRET_LABEL = re.compile(
    r"((?:验证码|短信码|密码|口令|api[_ -]?key|token|authorization|bearer)\s*[:：= ]\s*)"
    r"([^\s,，;；]+)", re.I,
)
PHONE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
ACCOUNT = re.compile(r"(?<!\d)\d{12,19}(?!\d)")
NAME = re.compile(r"((?:姓名|户名|收件人)\s*[:：]\s*)([\u4e00-\u9fff]{2,4})")
ADDRESS = re.compile(r"((?:地址|住址)\s*[:：]\s*)([^\s,，;；]+)")


def redact(value: object, known_secrets: Iterable[str] = ()) -> object:
    """Remove known credentials and recognizable personal data before persistence."""
    if isinstance(value, BaseModel):
        return redact(value.model_dump(mode="json"), known_secrets)
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            field = str(key).lower()
            if field == "code" and isinstance(item, str) and re.fullmatch(r"\d{4,8}", item):
                clean[key] = "[REDACTED]"
            elif SECRET_FIELD.search(field) or field in ADDRESS_FIELD:
                clean[key] = "[REDACTED]"
            elif field in PERSON_NAME_FIELD and isinstance(item, str) and item:
                clean[key] = item[0] + "*" * (len(item) - 1)
            elif field in PHONE_FIELD and isinstance(item, str):
                clean[key] = PHONE.sub(r"\1****\2", item)
            elif field in ACCOUNT_FIELD and isinstance(item, str):
                clean[key] = ACCOUNT.sub(lambda match: "****" + match.group()[-4:], item)
            else:
                clean[key] = redact(item, known_secrets)
        return clean
    if isinstance(value, list):
        return [redact(item, known_secrets) for item in value]
    if not isinstance(value, str):
        return value
    result = value
    for secret in known_secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    result = SECRET_LABEL.sub(r"\1[REDACTED]", result)
    result = PHONE.sub(r"\1****\2", result)
    result = ACCOUNT.sub(lambda match: "****" + match.group()[-4:], result)
    result = NAME.sub(lambda match: match.group(1) + match.group(2)[0] + "*" * (len(match.group(2)) - 1), result)
    result = ADDRESS.sub(r"\1[REDACTED]", result)
    return result


class AuditJournal:
    def __init__(self, application_path: Path):
        self.path = application_path
        with transaction(self.path) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS audit_evidence (
                evidence_id TEXT PRIMARY KEY,
                demo_round_id TEXT NOT NULL,
                task_id TEXT,
                snapshot_json TEXT NOT NULL,
                content TEXT NOT NULL
            )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS audit_events (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                run_key TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                demo_round_id TEXT NOT NULL,
                task_id TEXT,
                trace_id TEXT NOT NULL,
                event_json TEXT NOT NULL,
                UNIQUE(run_key, sequence)
            )""")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS audit_task_idx ON audit_events(demo_round_id, task_id, row_id)",
            )

    def append(
        self, event: AuditEvent, *, evidence: object | None = None,
        known_secrets: Iterable[str] = (),
    ) -> AuditEvent:
        with transaction(self.path) as connection:
            return self.append_in_transaction(
                connection, event, evidence=evidence, known_secrets=known_secrets,
            )

    def append_in_transaction(
        self, connection, event: AuditEvent, *, evidence: object | None = None,
        known_secrets: Iterable[str] = (),
    ) -> AuditEvent:
        """Use the caller's application transaction for a tool result and its audit event."""
        secrets = tuple(known_secrets)
        clean = AuditEvent.model_validate(redact(event.model_dump(mode="json"), secrets))
        if clean.evidence_status == "available":
            if clean.evidence_ref is None:
                raise ValueError("available evidence requires evidence_ref")
            if evidence is not None:
                content = redact(evidence, secrets)
                encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                snapshot = EvidenceSnapshot(
                    evidence_id=clean.evidence_ref, media_type="application/json",
                    content_ref=f"audit:{clean.evidence_ref}", redaction_version=REDACTION_VERSION,
                    content_hash=hashlib.sha256(encoded.encode()).hexdigest(), created_at=clean.timestamp,
                )
                connection.execute(
                    "INSERT INTO audit_evidence VALUES (?, ?, ?, ?, ?)",
                    (snapshot.evidence_id, clean.demo_round_id, clean.task_id,
                     snapshot.model_dump_json(), encoded),
                )
            owned = connection.execute(
                """SELECT 1 FROM audit_evidence WHERE evidence_id = ? AND demo_round_id = ?
                   AND task_id IS ?""",
                (clean.evidence_ref, clean.demo_round_id, clean.task_id),
            ).fetchone()
            if owned is None:
                raise ValueError("evidence is missing or outside the event scope")
        elif evidence is not None:
            raise ValueError("missing or restricted evidence cannot contain a readable snapshot")
        run_key = f"run:{clean.run_id}" if clean.run_id is not None else f"trace:{clean.trace_id}"
        highest = connection.execute(
            "SELECT MAX(sequence) FROM audit_events WHERE run_key = ?", (run_key,),
        ).fetchone()[0]
        if highest is not None and clean.sequence <= highest:
            raise ValueError("audit sequence must increase within the run or trace")
        connection.execute(
            "INSERT INTO audit_events(event_id, run_key, sequence, demo_round_id, task_id, trace_id, event_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (clean.event_id, run_key, clean.sequence, clean.demo_round_id,
             clean.task_id, clean.trace_id, clean.model_dump_json()),
        )
        return clean

    def _events(self, demo_round_id: str, task_id: str) -> list[AuditEvent]:
        connection = connect(self.path)
        try:
            rows = connection.execute(
                """SELECT event_json FROM audit_events WHERE demo_round_id = ? AND task_id = ?
                   ORDER BY row_id""",
                (demo_round_id, task_id),
            ).fetchall()
            return [AuditEvent.model_validate_json(row["event_json"]) for row in rows]
        finally:
            connection.close()

    def _event(self, demo_round_id: str, event_id: str) -> AuditEvent | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                "SELECT event_json FROM audit_events WHERE demo_round_id = ? AND event_id = ?",
                (demo_round_id, event_id),
            ).fetchone()
            return AuditEvent.model_validate_json(row["event_json"]) if row else None
        finally:
            connection.close()

    def _evidence(self, event: AuditEvent) -> tuple[str | None, EvidenceSnapshot | None]:
        if event.evidence_status != "available" or event.evidence_ref is None:
            return None, None
        connection = connect(self.path)
        try:
            row = connection.execute(
                """SELECT content, snapshot_json FROM audit_evidence
                   WHERE evidence_id = ? AND demo_round_id = ? AND task_id IS ?""",
                (event.evidence_ref, event.demo_round_id, event.task_id),
            ).fetchone()
            if row is None:
                return None, None
            return row["content"], EvidenceSnapshot.model_validate_json(row["snapshot_json"])
        finally:
            connection.close()


@dataclass(frozen=True)
class AuditViewer:
    actor_id: str
    session_id: str
    demo_round_id: str


class AuditReader:
    def __init__(
        self, journal: AuditJournal,
        authorize: Callable[[AuditViewer, str, str, str | None], bool] | None = None,
    ):
        self._journal = journal
        self._authorize = authorize

    def _access(self, viewer: AuditViewer, action: str, target_round: str,
                target_ref: str | None) -> None:
        try:
            permitted = self._authorize is not None and self._authorize(
                viewer, action, target_round, target_ref,
            )
        except Exception:
            permitted = False
        now = datetime.now(timezone.utc)
        event = AuditEvent(
            event_id=str(uuid4()), trace_id=str(uuid4()), span_id=str(uuid4()),
            sequence=0, parent_span_id=None, demo_round_id=viewer.demo_round_id,
            actor_id=viewer.actor_id, session_id=viewer.session_id,
            target_session_id=None, target_user_id=None, thread_id=None,
            task_id=None, run_id=None, module="audit", event_type="audit.accessed",
            timestamp=now, logical_at=None,
            outcome="succeeded" if permitted else "denied", evidence_ref=None,
            evidence_status="missing", missing_reason="access event has no content snapshot",
            payload=AuditAccessedPayload(
                action=action, filter_ref=target_round,
                target_refs=[] if target_ref is None else [target_ref],
                export_id=None, permitted=permitted,
                reason_code="ALLOWED" if permitted else "ACCESS_DENIED",
            ),
        )
        self._journal.append(event)
        if not permitted:
            raise PermissionError("ACCESS_DENIED")

    def _detail(self, event: AuditEvent) -> AuditEventDetail:
        content, _ = self._journal._evidence(event)
        status = event.evidence_status
        reason = event.missing_reason
        if status == "available" and content is None:
            status, reason = "missing", "content snapshot unavailable"
        return AuditEventDetail.model_validate({
            **event.model_dump(include=set(AuditEventSummary.model_fields)),
            "payload": event.payload, "evidence": content,
            "evidence_status": status, "missing_reason": reason,
        })

    def timeline(self, viewer: AuditViewer, demo_round_id: str,
                 task_id: str) -> list[AuditEventDetail]:
        self._access(viewer, "list", demo_round_id, task_id)
        return [self._detail(event) for event in self._journal._events(demo_round_id, task_id)]

    def detail(self, viewer: AuditViewer, demo_round_id: str,
               event_id: str) -> AuditEventDetail:
        self._access(viewer, "read", demo_round_id, event_id)
        event = self._journal._event(demo_round_id, event_id)
        if event is None:
            raise KeyError("event not found")
        return self._detail(event)

    def export_json(self, viewer: AuditViewer, demo_round_id: str,
                    task_id: str) -> bytes:
        self._access(viewer, "export", demo_round_id, task_id)
        events = self._journal._events(demo_round_id, task_id)
        details = [self._detail(event) for event in events]
        evidence = {}
        missing = []
        for event, detail in zip(events, details):
            content, snapshot = self._journal._evidence(event)
            if content is not None and snapshot is not None:
                evidence[snapshot.evidence_id] = {
                    "snapshot": snapshot.model_dump(mode="json"),
                    "content": json.loads(content),
                }
            elif detail.evidence_status != "available":
                missing.append({"event_id": event.event_id, "reason": detail.missing_reason})
        package = {
            "demo_round_id": demo_round_id, "task_id": task_id,
            "summary": {
                "event_count": len(events),
                "first_at": min((event.timestamp.isoformat() for event in events), default=None),
                "last_at": max((event.timestamp.isoformat() for event in events), default=None),
                "modules": sorted({event.module for event in events}),
                "versions": sorted({
                    event.payload.config_version if event.event_type == "model.started"
                    else event.payload.tool_version
                    for event in events if event.event_type in {"model.started", "tool.started"}
                }),
            },
            "events": [detail.model_dump(mode="json") for detail in details],
            "evidence": evidence, "missing": missing,
            "manifest": {
                "algorithm": "sha256",
                "content_format": "UTF-8 canonical JSON with sorted keys and compact separators",
                "content_hashes": {
                    evidence_id: item["snapshot"]["content_hash"]
                    for evidence_id, item in evidence.items()
                },
            },
            "unpaired_starts": self._unpaired(events),
        }
        return json.dumps(package, ensure_ascii=False, sort_keys=True).encode("utf-8")

    @staticmethod
    def _unpaired(events: list[AuditEvent]) -> list[str]:
        started = {}
        for event in events:
            if event.event_type in {"tool.started", "model.started"}:
                call_id = (event.payload.tool_call_id if event.event_type == "tool.started"
                           else event.payload.model_call_id)
                started[call_id] = event.event_id
            elif event.event_type in {"tool.finished", "model.finished"}:
                call_id = (event.payload.tool_call_id if event.event_type == "tool.finished"
                           else event.payload.model_call_id)
                started.pop(call_id, None)
        return list(started.values())
