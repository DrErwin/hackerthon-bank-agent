"""D01-D05: the output seam observes assistant replies, export files and memory view.

The fixtures are the real HTTP application from ``test_app.py`` (real store, mock bank,
audit journal and memory adapter). Where no production endpoint can produce a shape (a
task result message carrying unmasked personal data, an export file carrying a secret),
the test injects that producer-side value and then reads it back over HTTP — the same
seam the deployed code uses.

Credential replies are asserted layering-agnostically (ticket 09): the Harness reply gate
and the API output probe are both valid blockers, so D01 only requires that nothing
delivered shows the value, while D01b keeps the probe's own evidence through the task
result message path (which never passes the planner reply gate).
"""

from contextlib import closing
from datetime import datetime, timezone
import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.agent_platform.model import ReplyOnly
from app.api.service import OUTPUT_BLOCKED_MEMORY, OUTPUT_BLOCKED_REPLY
from app.api.test_app import (
    _bill_report, admin_login, enter, make_app, post, start,
)
from app.contracts.tasks import ModuleResult, TransferTaskView
from app.storage.database import connect

ORIGIN = {"Origin": "http://testserver"}
RAW_CODE = "246813"
RAW_REPLY_CODE = "123456"
RAW_ACCOUNT = "6222000000000022"
RAW_PHONE = "13900000003"


def messages(client, thread):
    return client.get(f"/api/v1/threads/{thread}/messages").json()["data"]["items"]


def server_events(app, thread):
    return app.state.api.store.events(thread, None)


def audit_events(app):
    return app.state.api.runtime.audit._events("D1")


def probe_evidence(app):
    """Evidence snapshots written by the output probe (reason code + findings only)."""

    with closing(connect(app.state.api.runtime.application.path)) as connection:
        rows = [json.loads(row["content"]) for row in connection.execute(
            "SELECT content FROM audit_evidence")]
    return [row for row in rows if isinstance(row, dict)
            and str(row.get("reason_code", "")).startswith("OUTPUT_PROBE")]


def probe_events(app):
    """chat.message audit events written by the output probe (module=api)."""

    return [event for event in audit_events(app)
            if event.event_type == "chat.message" and event.module == "api"]


def send(client, thread, text):
    return post(client, f"/threads/{thread}/messages", text=text)


def new_thread(client):
    enter(client)
    return post(client, "/threads").json()["data"]["thread_id"]


def delivered_message_store(app):
    """The delivered conversation tables a user can read back over HTTP."""

    with closing(connect(app.state.api.runtime.application.path)) as connection:
        return json.dumps(
            [[list(row) for row in connection.execute(f'SELECT * FROM "{table}"')]
             for table in ("api_messages", "api_events", "api_message_jobs")],
            ensure_ascii=False, default=str)


def test_d01_credential_reply_never_reaches_a_delivered_surface(tmp_path):
    """I01: layering-agnostic — either the Harness reply gate or the API output probe may
    block the reply; either way no delivered message / SSE / message store shows the code.
    """

    reply = f"您的本次登录 code {RAW_REPLY_CODE} 已发送，请勿泄露给他人。"
    app = make_app(tmp_path, proposal=ReplyOnly(message=reply))
    with TestClient(app) as client:
        thread = new_thread(client)
        accepted = send(client, thread, "帮我看看这条消息")
        assert accepted.status_code == 202, accepted.text

        history = client.get(f"/api/v1/threads/{thread}/messages")
        assert RAW_REPLY_CODE not in history.text
        # The blocking layer differs by design: Harness fail-closed publishes no assistant
        # message, the API probe publishes the fixed safe text. Both are accepted here.
        assert [row["role"] for row in history.json()["data"]["items"]] in (
            ["user"], ["user", "assistant"])
        assert RAW_REPLY_CODE not in delivered_message_store(app)

        events = server_events(app, thread)
        assert events and RAW_REPLY_CODE not in json.dumps(events, ensure_ascii=False)
        assert client.get("/api/v1/tasks",
                          params={"thread_id": thread}).json()["data"]["items"] == []


def test_d01b_task_result_message_with_a_credential_is_blocked_and_audited(tmp_path):
    """I02: independent probe evidence — a task result message never passes the planner
    reply gate, so the output seam itself must block it whole and leave a denied record.
    """

    app = make_app(tmp_path)
    with TestClient(app) as client:
        thread, task = start(client)
        service = app.state.api
        identity = service.identity(client.cookies.get("bank_session"))
        record = service.runtime.application.get_task("U1", "D1", task["task_id"])
        result = ModuleResult[TransferTaskView].model_validate(record.snapshot["result"])
        result = result.model_copy(update={
            "message": f"请注意：验证码是 {RAW_CODE}，不要告诉任何人。"})
        service.runtime.application.update_task(
            "U1", "D1", record.task_id, record.revision, record.run_id, record.status,
            record.checkpoint_id, {**record.snapshot, "result": result.model_dump(mode="json")})
        service.publish_task(identity, task["task_id"])

        history = client.get(f"/api/v1/threads/{thread}/messages")
        assert RAW_CODE not in history.text
        delivered = messages(client, thread)[-1]
        assert delivered["role"] == "assistant"
        assert delivered["text"] == OUTPUT_BLOCKED_REPLY
        completed = [event for event in server_events(app, thread)
                     if event["event_type"] == "message_completed"]
        assert completed[-1]["payload"]["text"] == OUTPUT_BLOCKED_REPLY

        denied = probe_events(app)
        assert len(denied) == 1 and denied[0].outcome == "denied"
        evidence = next(row for row in probe_evidence(app) if row["action"] == "blocked")
        assert evidence["findings"] == ["credential"]
        assert evidence["reason_code"] == "OUTPUT_PROBE_BLOCKED"
        assert RAW_CODE not in json.dumps(evidence, ensure_ascii=False)


def test_d02_personal_data_in_a_task_message_is_redacted_in_place(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        thread, task = start(client)
        service = app.state.api
        identity = service.identity(client.cookies.get("bank_session"))
        runtime = service.runtime

        # Producer-side stand-in: the module result message now carries unmasked personal
        # data. Publishing it is the same `publish_task` path real results use.
        record = runtime.application.get_task("U1", "D1", task["task_id"])
        result = ModuleResult[TransferTaskView].model_validate(record.snapshot["result"])
        dirty = (f"已向账户 {RAW_ACCOUNT} 转账 500.00 元，"
                 f"联系手机 {RAW_PHONE}，交易号 3f9a1c7e-5b2d-4e8a-9c1f-7a2b4d6e8f0a。")
        result = result.model_copy(update={"message": dirty})
        runtime.application.update_task(
            "U1", "D1", record.task_id, record.revision, record.run_id, record.status,
            record.checkpoint_id, {**record.snapshot, "result": result.model_dump(mode="json")})
        service.publish_task(identity, task["task_id"])

        text = messages(client, thread)[-1]["text"]
        assert "****0022" in text and "139****0003" in text
        assert "500.00" in text and "3f9a1c7e-5b2d-4e8a-9c1f-7a2b4d6e8f0a" in text
        for raw in (RAW_ACCOUNT, RAW_PHONE):
            assert raw not in client.get(f"/api/v1/threads/{thread}/messages").text
        # The assistant message SSE reuses the stored (already guarded) message view. The
        # task_updated payload keeps the module's own task message by contract (§6.5), so
        # only the delivered message events are scanned here.
        completed = [event for event in server_events(app, thread)
                     if event["event_type"] == "message_completed"]
        assert completed[-1]["payload"]["text"] == text
        assert RAW_ACCOUNT not in json.dumps(completed, ensure_ascii=False)

        redacted = probe_events(app)
        assert len(redacted) == 1 and redacted[0].outcome == "denied"
        assert set(redacted[0].payload.related_task_ids) == {task["task_id"]}
        evidence = next(row for row in probe_evidence(app) if row["action"] == "redacted")
        assert set(evidence["findings"]) == {"full_account", "personal_phone"}
        assert evidence["reason_code"] == "OUTPUT_PROBE_REDACTED"
        assert RAW_ACCOUNT not in json.dumps(evidence, ensure_ascii=False)


def test_d03_clean_reply_is_not_touched(tmp_path):
    reply = ("已向妈妈转账 500.00 元，交易号 3f9a1c7e-5b2d-4e8a-9c1f-7a2b4d6e8f0a，"
             "收款账户 ****0002。")
    app = make_app(tmp_path, proposal=ReplyOnly(message=reply))
    with TestClient(app) as client:
        thread = new_thread(client)
        accepted = send(client, thread, "给妈妈转 500 元")
        assert accepted.status_code == 202, accepted.text
        rows = messages(client, thread)
        assert rows[-1]["text"] == reply
        assert not probe_events(app)
        assert not probe_evidence(app)


def test_d04_export_with_an_authentication_secret_is_refused(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        service = app.state.api
        owner = service.identity(client.cookies.get("bank_session"))
        report = service.capture_report(owner, task["task_id"], _bill_report())

        created = post(client, f"/reports/{report.report_id}/exports", kind="card")
        assert created.status_code == 200, created.text
        export_id = created.json()["data"]["export_id"]
        row = service.store.export_row(export_id, owner.user_id, owner.demo_round_id)
        # Producer-side stand-in: the generated file carries an authentication secret.
        service.store.finish_export(export_id, "ready", file_name=row["file_name"],
                                    media_type=row["media_type"],
                                    content=f"<html>验证码是 {RAW_CODE}</html>")

        blocked = client.get(f"/api/v1/exports/{export_id}/download")
        assert blocked.status_code == 503, blocked.text
        assert blocked.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
        assert "content-disposition" not in blocked.headers
        assert RAW_CODE not in blocked.text
        denied = [event for event in audit_events(app)
                  if event.event_type == "audit.accessed"
                  and event.payload.export_id == export_id
                  and event.payload.action == "download"]
        assert len(denied) == 1
        assert (denied[0].outcome, denied[0].payload.permitted,
                denied[0].payload.reason_code) == ("denied", False, "OUTPUT_PROBE_BLOCKED")

        # A clean export still downloads byte-for-byte (personal bill data is the content).
        clean = post(client, f"/reports/{report.report_id}/exports", kind="card")
        clean_id = clean.json()["data"]["export_id"]
        clean_row = service.store.export_row(clean_id, owner.user_id, owner.demo_round_id)
        normal = client.get(f"/api/v1/exports/{clean_id}/download")
        assert normal.status_code == 200, normal.text
        assert normal.text == clean_row["content"]
        assert "九月吃饭净消费 7 元" in normal.text


def test_d04_audit_export_with_a_secret_is_refused(tmp_path):
    user_app, admin_app = make_app(tmp_path), make_app(tmp_path)
    with TestClient(user_app) as user, TestClient(admin_app) as admin:
        _, task = start(user)
        service = admin_app.state.api
        service.capture_report(service.identity(user.cookies.get("bank_session")), task["task_id"],
                               _bill_report())
        admin_login(admin)
        created = post(admin, "/admin/audit/exports", demo_round_id="D1")
        assert created.status_code == 200, created.text
        export_id = created.json()["data"]["export_id"]
        row = service.store.export_row(export_id, "demo-admin", "D1")
        service.store.finish_export(export_id, "ready", file_name=row["file_name"],
                                    media_type=row["media_type"],
                                    content=json.dumps({"leak": f"验证码是 {RAW_CODE}"},
                                                       ensure_ascii=False))
        blocked = admin.get(f"/api/v1/exports/{export_id}/download")
        assert blocked.status_code == 503, blocked.text
        assert RAW_CODE not in blocked.text
        denied = [event for event in audit_events(admin_app)
                  if event.event_type == "audit.accessed"
                  and event.payload.export_id == export_id
                  and event.payload.action == "download"]
        assert denied and denied[-1].payload.permitted is False
        assert denied[-1].payload.reason_code == "OUTPUT_PROBE_BLOCKED"


def test_d05_memory_view_redacts_without_losing_fields(tmp_path):
    app = make_app(tmp_path)
    app.state.api.runtime.memory.seed_demo("U1", "D1", "2026-09")
    with TestClient(app) as client:
        enter(client)
        service = app.state.api
        owner = service.identity(client.cookies.get("bank_session"))
        # Defence-in-depth stand-in: a row that bypassed the memory vocabulary and holds
        # an unmasked personal name. The view must mask it without dropping fields.
        namespace = json.dumps(["memory", "D1", "U1"], separators=(",", ":"))
        now = datetime.now(timezone.utc).isoformat()
        with closing(connect(service.runtime.application.path)) as connection:
            connection.executemany(
                "INSERT INTO memory_files VALUES (?, ?, ?, 1, ?, ?)",
                [(namespace, "/memories/contact.md",
                  json.dumps({"content": "联系人姓名：王五（演示）", "encoding": "utf-8"},
                             ensure_ascii=False), now, now),
                 (namespace, "/memories/preference.md",
                  json.dumps({"content": "用户偏好：喜欢简短说明。", "encoding": "utf-8"},
                             ensure_ascii=False), now, now)])
            connection.commit()

        listed = client.get("/api/v1/memories")
        assert listed.status_code == 200, listed.text
        items = {item["memory_id"]: item for item in listed.json()["data"]["items"]}
        assert all(set(item) == {"memory_id", "version", "content", "updated_at"}
                   for item in items.values())
        assert "妈妈 → 银行种子 A2" in items["alias-mother"]["content"]
        assert "生日配送演示资料" in items["birthday-delivery"]["content"]
        assert items["contact"]["version"] == 1 and items["contact"]["updated_at"] == now
        assert items["contact"]["content"] == "联系人姓名：王*（演示）"
        assert items["preference"]["content"] == "用户偏好：喜欢简短说明。"
        assert "王五" not in listed.text

        # Deletion and its tombstone behave exactly as before the probe was introduced.
        deleted = client.post("/api/v1/memories/delete", headers=ORIGIN, json={
            "request_id": str(uuid4()), "memory_ids": ["preference"],
            "expected_versions": {"preference": items["preference"]["version"]}})
        assert deleted.status_code == 200, deleted.text
        remaining = {item["memory_id"] for item in
                     client.get("/api/v1/memories").json()["data"]["items"]}
        assert "preference" not in remaining and "alias-mother" in remaining
        backend = service.runtime.memory.backend(service.memory_context(owner))
        try:
            backend.write("/memories/preference-again.md", "用户偏好：喜欢简短说明。")
        except ValueError as exc:
            assert "deleted memory" in str(exc)
        else:  # pragma: no cover - the tombstone must always refuse the restore
            raise AssertionError("deleted memory content must not be restored")
