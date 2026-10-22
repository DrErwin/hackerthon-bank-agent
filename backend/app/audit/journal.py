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
    AuthorizationSnapshot, EvidenceSnapshot,
)
from app.contracts.common import OperationLevel, Phase, SecurityDecisionCode
from app.storage.database import connect, transaction


REDACTION_VERSION = "v2"
SECRET_FIELD = re.compile(
    r"(?:password|passwd|secret|credential|cookie|api[_-]?key|otp|verification[_-]?code|demo[_-]?code|sms[_-]?code|验证码|密码|口令|(?:^|_)token$|authorization[_-]?header|^pin$)",
    re.I,
)
PERSON_NAME_FIELD = {"account_name", "recipient_name", "payee_name", "customer_name", "person_name"}
PHONE_FIELD = {"phone", "phone_number", "recipient_phone"}
ACCOUNT_FIELD = {"account_number", "card_number"}
ADDRESS_FIELD = {"address", "recipient_address"}
# Code labels are also used in safety explanations. Require an actual opaque
# code token after these two labels; password/other-secret labels remain broad.
_CODE_VALUE_AHEAD = r"(?=\s*(?:是|为|[:：=]|\s)\s*[\"'`*]*(?:[A-Za-z0-9]{4,}|\d{4,}|\[REDACTED\]))"
SECRET_LABEL = re.compile(
    rf"((?:(?:验证码|短信码){_CODE_VALUE_AHEAD}|密码|口令|登录凭据|credential|secret|cookie|api[_ -]?key|otp|token|authorization|bearer)\s*(?:是|为|[:：=]|\s)\s*)"
    r"([^\s,，;；]+)", re.I,
)
PHONE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
ACCOUNT = re.compile(r"(?<!\d)\d{12,19}(?!\d)")
OPAQUE_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I,
)
NAME = re.compile(r"((?:姓名|户名|收件人)\s*[:：]\s*)([\u4e00-\u9fff]{2,4})")
ADDRESS = re.compile(r"((?:地址|住址)\s*[:：]\s*)([^\s,，;；]+)")
# Opaque identifiers (evidence, argument, parameter and receipt references). The journal
# looks snapshots up by these exact strings, so masking a digit run inside one would
# break the evidence linkage — and a reference is not personal data.
REF_FIELD = re.compile(r"(?:^|_)refs?$")


def redact(value: object, known_secrets: Iterable[str] = (), *, free_text: bool = False,
           opaque: bool = False) -> object:
    """Remove known credentials and recognizable personal data before persistence."""
    if isinstance(value, BaseModel):
        return redact(value.model_dump(mode="json"), known_secrets, free_text=free_text)
    if isinstance(value, dict):
        display_value = None
        if "name" in value and "value_text" in value:
            name = re.sub(r"(?<!^)(?=[A-Z])", "_", str(value["name"])).lower()
            if SECRET_FIELD.search(name) or name == "code":
                display_value = "[REDACTED]"
            for fields in (PERSON_NAME_FIELD, PHONE_FIELD, ACCOUNT_FIELD, ADDRESS_FIELD):
                if name in fields:
                    display_value = redact({name: value["value_text"]}, known_secrets)[name]
        clean = {}
        for key, item in value.items():
            field = re.sub(r"(?<!^)(?=[A-Z])", "_", str(key)).lower()
            if field == "value_text" and display_value is not None:
                clean[key] = display_value
            elif REF_FIELD.search(field):
                clean[key] = redact(item, known_secrets, opaque=True)
            elif (field == "code" and isinstance(item, str)
                    and re.fullmatch(r"[A-Za-z0-9]{4,8}", item)) or SECRET_FIELD.search(field):
                clean[key] = "[REDACTED]"
            elif field in ADDRESS_FIELD:
                clean[key] = "[REDACTED]"
            elif field in PERSON_NAME_FIELD and isinstance(item, str) and item:
                clean[key] = item[0] + "*" * (len(item) - 1)
            elif field in PHONE_FIELD and isinstance(item, str):
                clean[key] = PHONE.sub(r"\1****\2", item)
            elif field in ACCOUNT_FIELD and isinstance(item, str):
                clean[key] = ACCOUNT.sub(lambda match: "****" + match.group()[-4:], item)
            else:
                clean[key] = redact(item, known_secrets, free_text=field in {"text", "message", "content"})
        return clean
    if isinstance(value, list):
        return [redact(item, known_secrets, free_text=free_text, opaque=opaque) for item in value]
    if not isinstance(value, str):
        return value
    result = value
    for secret in known_secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    result = SECRET_LABEL.sub(r"\1[REDACTED]", result)
    if opaque:
        # A reference stays byte-identical apart from known secrets: masking a digit run
        # inside it would break the audit evidence lookup performed by these strings.
        return result
    if free_text and re.fullmatch(r"\s*[A-Za-z0-9]{4,8}\s*", result) and re.search(r"\d", result):
        return "[REDACTED]"
    if OPAQUE_UUID.fullmatch(result):
        return result
    result = PHONE.sub(r"\1****\2", result)
    result = ACCOUNT.sub(lambda match: "****" + match.group()[-4:], result)
    result = NAME.sub(lambda match: match.group(1) + match.group(2)[0] + "*" * (len(match.group(2)) - 1), result)
    result = ADDRESS.sub(r"\1[REDACTED]", result)
    return result


def evidence_refs(event: AuditEvent) -> set[str]:
    """Snapshot IDs carried in the typed payload, separate from business record IDs."""
    payload = event.payload
    fields = {
        "chat.message": ("content_ref",),
        "model.started": ("request_ref",),
        "model.finished": ("response_ref",),
        "context.changed": ("before_ref", "after_ref", "source_refs"),
        "tool.started": ("arguments_ref",),
        "tool.finished": ("result_ref",),
        "confirmation.changed": ("display_ref",),
        "bank.observed": ("receipt_ref",),
        "admin.changed": ("before_ref", "after_ref"),
    }.get(event.event_type, ())
    refs = {event.evidence_ref} if event.evidence_ref else set()
    for field in fields:
        value = getattr(payload, field)
        refs.update(value if isinstance(value, list) else [value] if value else [])
    if event.event_type == "security.decided":
        decision = payload.decision
        refs.add(decision.parameters_ref)
        refs.update(decision.evidence_refs)
        if decision.authorization_snapshot_ref:
            refs.add(decision.authorization_snapshot_ref)
    return refs


def run_key(event: AuditEvent) -> str:
    return json.dumps([event.demo_round_id, "run" if event.run_id else "trace",
                       event.run_id or event.trace_id])


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
        snapshots: dict[str, object] | None = None, known_secrets: Iterable[str] = (),
    ) -> AuditEvent:
        with transaction(self.path) as connection:
            return self.append_in_transaction(
                connection, event, evidence=evidence, known_secrets=known_secrets,
                snapshots=snapshots,
            )

    def append_in_transaction(
        self, connection, event: AuditEvent, *, evidence: object | None = None,
        snapshots: dict[str, object] | None = None, known_secrets: Iterable[str] = (),
    ) -> AuditEvent:
        """Use the caller's application transaction for a tool result and its audit event."""
        secrets = tuple(known_secrets)
        clean = AuditEvent.model_validate(redact(event.model_dump(mode="json"), secrets))
        if clean.evidence_status == "available" and clean.evidence_ref is None:
            raise ValueError("available evidence requires evidence_ref")
        if clean.evidence_status != "available" and evidence is not None:
            raise ValueError("missing or restricted evidence cannot contain a readable snapshot")
        supplied = dict(snapshots or {})
        if evidence is not None:
            if clean.evidence_ref in supplied:
                raise ValueError("evidence supplied twice")
            supplied[clean.evidence_ref] = evidence
        if supplied.keys() - evidence_refs(clean):
            raise ValueError("snapshot is not referenced by the event")
        for evidence_id, value in supplied.items():
            content = redact(value, secrets, free_text=isinstance(value, str))
            encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            snapshot = EvidenceSnapshot(
                evidence_id=evidence_id, media_type="application/json",
                content_ref=f"audit:{evidence_id}", redaction_version=REDACTION_VERSION,
                content_hash=hashlib.sha256(encoded.encode()).hexdigest(), created_at=clean.timestamp,
            )
            connection.execute(
                "INSERT INTO audit_evidence VALUES (?, ?, ?, ?, ?)",
                (snapshot.evidence_id, clean.demo_round_id, clean.task_id,
                 snapshot.model_dump_json(), encoded),
            )
        if clean.evidence_status == "available" and self._stored_evidence(
            connection, clean, clean.evidence_ref,
        ) is None:
            raise ValueError("evidence is missing or outside the event scope")
        self._check_authorization(connection, clean)
        self._check_tool_decision(connection, clean)
        key = run_key(clean)
        highest = connection.execute(
            "SELECT MAX(sequence) FROM audit_events WHERE run_key = ?", (key,),
        ).fetchone()[0]
        if highest is not None and clean.sequence <= highest:
            raise ValueError("audit sequence must increase within the run or trace")
        connection.execute(
            "INSERT INTO audit_events(event_id, run_key, sequence, demo_round_id, task_id, trace_id, event_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (clean.event_id, key, clean.sequence, clean.demo_round_id,
             clean.task_id, clean.trace_id, clean.model_dump_json()),
        )
        return clean

    @staticmethod
    def _stored_evidence(connection, event: AuditEvent, evidence_id: str):
        return connection.execute(
            """SELECT content, snapshot_json FROM audit_evidence
               WHERE evidence_id = ? AND demo_round_id = ? AND task_id IS ?""",
            (evidence_id, event.demo_round_id, event.task_id),
        ).fetchone()

    def _check_authorization(self, connection, event: AuditEvent) -> None:
        if event.event_type != "security.decided":
            return
        decision = event.payload.decision
        if (decision.decision != SecurityDecisionCode.ALLOW or decision.phase != Phase.EXECUTION
                or decision.operation_level != OperationLevel.SENSITIVE):
            return
        ref = decision.authorization_snapshot_ref
        row = self._stored_evidence(connection, event, ref)
        if row is None:
            raise ValueError("sensitive allow requires a persisted authorization snapshot")
        if self._stored_evidence(connection, event, decision.parameters_ref) is None:
            raise ValueError("sensitive allow requires persisted action parameters")
        snapshot = AuthorizationSnapshot.model_validate_json(row["content"])
        if (snapshot.demo_round_id != event.demo_round_id or snapshot.task_id != event.task_id
                or snapshot.user_id != event.target_user_id
                or snapshot.operation_id != decision.operation_id
                or snapshot.action_revision != decision.action_revision
                or decision.task_id != event.task_id or decision.run_id != event.run_id):
            raise ValueError("authorization snapshot does not match the sensitive decision")
        if snapshot.confirmation is None or snapshot.confirmation.decision != "approved":
            raise ValueError("sensitive allow requires an approved confirmation in the snapshot")
        if event.actor_id == snapshot.user_id and event.session_id != snapshot.session_id:
            raise ValueError("authorization source session does not match the actor session")

    def _check_tool_decision(self, connection, event: AuditEvent) -> None:
        if event.event_type != "tool.started" or event.payload.operation_id is None:
            return
        if self._stored_evidence(connection, event, event.payload.arguments_ref) is None:
            raise ValueError("side-effect tool start requires persisted arguments")
        rows = connection.execute(
            """SELECT event_json FROM audit_events WHERE demo_round_id = ? AND task_id = ?
               AND run_key = ? ORDER BY row_id""",
            (event.demo_round_id, event.task_id, run_key(event)),
        ).fetchall()
        for row in rows:
            previous = AuditEvent.model_validate_json(row["event_json"])
            if previous.event_type != "security.decided":
                continue
            decision = previous.payload.decision
            if (decision.decision_id == event.payload.decision_id
                    and decision.decision == SecurityDecisionCode.ALLOW
                    and decision.operation_id == event.payload.operation_id
                    and decision.task_id == event.task_id and decision.run_id == event.run_id):
                return
        raise ValueError("side-effect tool start requires a persisted matching allow decision")

    def _events(self, demo_round_id: str, task_id: str | None = None) -> list[AuditEvent]:
        """One task's events, or every event of the round when no task narrows the scope."""
        connection = connect(self.path)
        try:
            if task_id is None:
                rows = connection.execute(
                    """SELECT event_json FROM audit_events WHERE demo_round_id = ?
                       ORDER BY row_id""",
                    (demo_round_id,),
                ).fetchall()
            else:
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

    def _evidence(self, event: AuditEvent, evidence_id: str | None = None) -> tuple[str | None, EvidenceSnapshot | None]:
        if evidence_id is None:
            if event.evidence_status != "available" or event.evidence_ref is None:
                return None, None
            evidence_id = event.evidence_ref
        if evidence_id is None:
            return None, None
        connection = connect(self.path)
        try:
            row = self._stored_evidence(connection, event, evidence_id)
            if row is None:
                return None, None
            snapshot = EvidenceSnapshot.model_validate_json(row["snapshot_json"])
            if hashlib.sha256(row["content"].encode()).hexdigest() != snapshot.content_hash:
                return None, None
            return row["content"], snapshot
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
                target_ref: str | None, export_id: str | None = None) -> None:
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
                export_id=export_id, permitted=permitted,
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
        absent = [ref for ref in evidence_refs(event)
                  if self._journal._evidence(event, ref)[0] is None]
        if absent and status == "available":
            status = "missing"
            reason = "content snapshot unavailable: " + ", ".join(sorted(absent))
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
                    task_id: str | None = None, *,
                    export_id: str | None = None) -> bytes:
        """A task's evidence package, or the whole round when no task narrows the scope."""
        self._access(viewer, "export", demo_round_id, task_id, export_id)
        events = self._journal._events(demo_round_id, task_id)
        details = [self._detail(event) for event in events]
        evidence = {}
        missing = []
        for event, detail in zip(events, details):
            for evidence_id in sorted(evidence_refs(event)):
                content, snapshot = self._journal._evidence(event, evidence_id)
                if content is not None and snapshot is not None:
                    evidence[evidence_id] = {
                        "snapshot": snapshot.model_dump(mode="json"),
                        "content": json.loads(content),
                    }
                else:
                    missing.append({
                        "event_id": event.event_id, "evidence_ref": evidence_id,
                        "reason": detail.missing_reason or "content snapshot unavailable",
                    })
            if detail.evidence_status != "available" and not evidence_refs(event):
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
                kind = event.event_type.split(".")[0]
                started.setdefault((run_key(event), kind, call_id), []).append(event.event_id)
            elif event.event_type in {"tool.finished", "model.finished"}:
                call_id = (event.payload.tool_call_id if event.event_type == "tool.finished"
                           else event.payload.model_call_id)
                kind = event.event_type.split(".")[0]
                key = (run_key(event), kind, call_id)
                if started.get(key):
                    started[key].pop()
        return [event_id for ids in started.values() for event_id in ids]
