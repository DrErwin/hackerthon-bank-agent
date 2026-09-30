"""Exercise HTTP boundaries with the real bank, security gate and transfer graph."""

from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.agent_platform.model import TransferProposal
from app.agent_platform.transfer_runtime import TransferRuntime
from app.audit.journal import AuditJournal
from app.contracts.common import RiskLevel
from app.memory.adapter import MemoryAdapter
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore
from app.storage.mock_bank.repository import MockBankStore

from .app import ApiConfig, create_app


class Planner:
    provider = "scripted"
    model_name = "http-test"
    config_version = "test-v1"

    def __init__(self, proposal=None):
        self.calls = 0
        self.proposal = proposal or TransferProposal(
            payee_hint="妈妈", amount_fen=50_000, payer_account_id="A1",
        )

    def select(self, *args):
        self.calls += 1
        return self.proposal


def make_app(path, *, proposal=None, risk=RiskLevel.LOW, user="U1"):
    application = ApplicationStore(path / "application.sqlite")
    runtime = TransferRuntime(
        application, MemoryAdapter(application, active_round=lambda: "D1"),
        AuditJournal(application.path),
        MockBankService(MockBankStore(path / "bank.sqlite"), demo_secret=b"s" * 32),
        Planner(proposal), authorize_capability=lambda *_: True,
        authorize_tool=lambda *_: True, assess_risk=lambda *_: risk,
        authorize_face=lambda admin, *_: admin.authorized,
    )
    return create_app(runtime, ApiConfig(
        demo_user_id=user, demo_round_id="D1", secret=b"s" * 32,
        admin_key="test-admin-key", origins=("http://testserver",),
    ))


def post(client, path, **body):
    return client.post("/api/v1" + path, json={"request_id": str(uuid4()), **body},
                       headers={"Origin": "http://testserver"})


def enter(client):
    response = post(client, "/session/enter")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def start(client, text="给妈妈转 500 元"):
    enter(client)
    thread = post(client, "/threads").json()["data"]["thread_id"]
    accepted = post(client, f"/threads/{thread}/messages", text=text)
    assert accepted.status_code == 202, accepted.text
    task_id = accepted.json()["data"]["task_id"]
    task = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
    return thread, task


def approve(client, task):
    ref = task["interaction"]["record_ref"]
    confirmation = client.get(f"/api/v1/confirmations/{ref}").json()["data"]
    response = post(client, f"/confirmations/{ref}/answer",
                    confirmation_version=confirmation["confirmation_version"], choice="approve")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_http_transfer_requires_confirmation_and_verification(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        thread, task = start(client)
        assert task["status"] == "waiting_approval"
        assert task["interaction"]["kind"] == "confirmation"
        original_operation = task["data"]["operation_id"]
        waiting = approve(client, task)
        assert waiting["interaction"]["kind"] == "verification"
        challenge = waiting["interaction"]["record_ref"]
        code_response = client.get(f"/api/v1/verifications/{challenge}/demo-code")
        assert code_response.headers["cache-control"] == "no-store"
        code = code_response.json()["data"]["code"]
        result = post(client, f"/verifications/{challenge}/code",
                      submission_id=str(uuid4()), code=code)
        assert result.status_code == 200, result.text
        completed = result.json()["data"]["task"]
        assert completed["status"] == "succeeded"
        assert completed["data"]["operation_id"] == original_operation
        assert completed["data"]["operation"]["receipt"]["amount_fen"] == 50_000
        assert completed["task_revision"] > task["task_revision"]
        history = client.get(f"/api/v1/threads/{thread}/messages").text
        assert code not in history
        assert client.get("/api/v1/admin/audit/events", params={"task_id": task["task_id"]}).status_code == 403


def test_message_retries_and_plain_chat_assent_never_duplicate_business(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        enter(client)
        thread = post(client, "/threads").json()["data"]["thread_id"]
        body = {"request_id": str(uuid4()), "text": "给妈妈转 500 元"}
        first = client.post(f"/api/v1/threads/{thread}/messages", json=body, headers={"Origin": "http://testserver"})
        second = client.post(f"/api/v1/threads/{thread}/messages", json=body, headers={"Origin": "http://testserver"})
        assert first.status_code == second.status_code == 202
        assert first.json() == second.json()
        conflict = client.post(f"/api/v1/threads/{thread}/messages", json={**body, "text": "不同请求"}, headers={"Origin": "http://testserver"})
        assert conflict.status_code == 409
        assert app.state.api.runtime.harness.planner.calls == 1
        assent = post(client, f"/threads/{thread}/messages", text="确认")
        assert assent.json()["data"]["task_id"] != first.json()["data"]["task_id"]
        tasks = client.get("/api/v1/tasks").json()["data"]["items"]
        original = next(task for task in tasks if task["task_id"] == first.json()["data"]["task_id"])
        assert original["interaction"]["kind"] == "confirmation"
        assert original["data"]["operation"] is None


def test_confirmation_version_retries_and_expiry_return_conflicts(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        ref = task["interaction"]["record_ref"]
        assert post(client, f"/confirmations/{ref}/answer", confirmation_version=2, choice="approve").status_code == 409
        body = {"request_id": str(uuid4()), "confirmation_version": 1, "choice": "approve"}
        first = client.post(f"/api/v1/confirmations/{ref}/answer", json=body, headers={"Origin": "http://testserver"})
        retry = client.post(f"/api/v1/confirmations/{ref}/answer", json=body, headers={"Origin": "http://testserver"})
        assert first.json() == retry.json()
        assert post(client, f"/confirmations/{ref}/answer", confirmation_version=1, choice="approve").status_code == 409
        assert post(client, f"/tasks/{task['task_id']}/resume").json()["data"]["status"] == "waiting_approval"
    with TestClient(make_app(tmp_path)) as client:
        _, task = start(client)
        from datetime import timedelta
        from .service import now
        app_service = client.app.state.api
        app_service.runtime.confirmations._clock = lambda: now() + timedelta(hours=2)
        assert post(client, f"/confirmations/{task['interaction']['record_ref']}/answer", confirmation_version=1, choice="approve").status_code == 409


def test_input_candidates_and_cancel_continue_the_original_task(tmp_path, monkeypatch):
    proposal = TransferProposal(payee_hint="妈妈", payer_account_id="A1")
    app = make_app(tmp_path, proposal=proposal)
    with TestClient(app) as client:
        _, task = start(client)
        interaction = task["interaction"]["interaction_id"]
        assert post(client, f"/tasks/{task['task_id']}/inputs", interaction_id="old", text="500 元").status_code == 409
        response = post(client, f"/tasks/{task['task_id']}/inputs", interaction_id=interaction, text="500 元")
        assert response.status_code == 200, response.text
        updated = response.json()["data"]
        assert updated["task_id"] == task["task_id"]
        assert updated["interaction"]["kind"] == "confirmation"
        assert post(client, f"/tasks/{task['task_id']}/inputs", interaction_id=interaction, text="500 元").status_code == 409
        cancelled = post(client, f"/tasks/{task['task_id']}/cancel").json()["data"]
        assert cancelled["status"] == "cancelled"
        assert cancelled["cancel_requested"]

    from app.services.mock_bank.core import PAYEES
    owner, name, number, remark, bank_name, phone = PAYEES["A3"]
    monkeypatch.setitem(PAYEES, "A3", (owner, name, number, "妈妈备用", bank_name, phone))
    app = make_app(tmp_path / "candidates", proposal=TransferProposal(payee_hint="妈妈", payer_account_id="A1", amount_fen=50_000))
    # Bank search still provides the candidates, never the API's own account list.
    with TestClient(app) as client:
        _, task = start(client)
        interaction = task["interaction"]
        assert {item["id"] for item in interaction["options"]} == {"A2", "A3"}
        bad = post(client, f"/tasks/{task['task_id']}/inputs", interaction_id=interaction["interaction_id"], selected_option_id="forged")
        assert bad.status_code == 400
        good = post(client, f"/tasks/{task['task_id']}/inputs", interaction_id=interaction["interaction_id"], selected_option_id="A2")
        assert good.status_code == 200, good.text
        assert good.json()["data"]["interaction"]["kind"] == "confirmation"


def test_private_payee_form_does_not_copy_account_number_to_chat(tmp_path):
    app = make_app(tmp_path, proposal=TransferProposal(amount_fen=50_000, payer_account_id="A1"))
    with TestClient(app) as client:
        thread, task = start(client)
        response = post(client, f"/tasks/{task['task_id']}/details",
                        interaction_id=task["interaction"]["interaction_id"], kind="payee",
                        fields={"account_number": "6222000000000002", "account_name": "王阿姨"})
        assert response.status_code == 200, response.text
        assert response.json()["data"]["detail_ref"]
        assert response.json()["data"]["task"]["interaction"]["kind"] == "confirmation"
        assert "6222000000000002" not in response.text
        assert "6222000000000002" not in client.get(f"/api/v1/threads/{thread}/messages").text
        assert post(client, f"/tasks/{task['task_id']}/details", interaction_id=task["interaction"]["interaction_id"],
                    kind="payee", fields={"account_number": "6222000000000002", "account_name": "王阿姨"}).status_code == 409


def test_payee_search_uses_exact_requested_bank_filter_and_requires_selection(tmp_path):
    app = make_app(tmp_path, proposal=TransferProposal(amount_fen=50_000, payer_account_id="A1"))
    with TestClient(app) as client:
        _, task = start(client)
        interaction_id = task["interaction"]["interaction_id"]
        empty = post(client, f"/tasks/{task['task_id']}/details", interaction_id=interaction_id,
                     kind="payee_search", fields={"kind": "name", "value": "妈妈"})
        assert empty.status_code == 200, empty.text
        assert empty.json()["data"]["candidates"] == []
        assert empty.json()["data"]["task"]["status"] == "waiting_input"
        match = post(client, f"/tasks/{task['task_id']}/details", interaction_id=interaction_id,
                     kind="payee_search", fields={"kind": "remark", "value": "妈妈"})
        assert match.status_code == 200, match.text
        assert [c["payee_id"] for c in match.json()["data"]["candidates"]] == ["A2"]
        assert match.json()["data"]["task"]["status"] == "waiting_input"
        assert post(client, f"/tasks/{task['task_id']}/inputs", interaction_id=interaction_id, selected_option_id="A3").status_code == 400
        selected = post(client, f"/tasks/{task['task_id']}/inputs", interaction_id=interaction_id, selected_option_id="A2")
        assert selected.status_code == 200, selected.text
        assert selected.json()["data"]["interaction"]["kind"] == "confirmation"


def test_no_secrets_in_chat_validation_errors_or_persisted_receipts(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        thread, task = start(client)
        for text in ("验证码是 123456", "123456", "password: hunter2"):
            rejected = post(client, f"/threads/{thread}/messages", text=text)
            assert rejected.status_code == 400
            assert text not in rejected.text
        waiting = approve(client, task)
        challenge = waiting["interaction"]["record_ref"]
        rejected = post(client, f"/verifications/{challenge}/code", submission_id="bad", code="secret123")
        assert rejected.status_code == 400
        assert "secret123" not in rejected.text
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        body = {"request_id": str(uuid4()), "submission_id": str(uuid4()), "code": code}
        first = client.post(f"/api/v1/verifications/{challenge}/code", json=body, headers={"Origin": "http://testserver"})
        retry = client.post(f"/api/v1/verifications/{challenge}/code", json=body, headers={"Origin": "http://testserver"})
        assert first.status_code == retry.status_code == 200
        assert first.json() == retry.json()
        changed = client.post(f"/api/v1/verifications/{challenge}/code", json={**body, "code": "different"}, headers={"Origin": "http://testserver"})
        assert changed.status_code == 409
        from app.storage.database import connect
        with connect(tmp_path / "application.sqlite") as connection:
            for table, column in (("api_requests", "response_json"), ("api_events", "event_json"), ("api_messages", "view_json"), ("tasks", "snapshot_json")):
                assert all(code not in (row[0] or "") for row in connection.execute(f"SELECT {column} FROM {table}"))


def test_cookie_origin_ownership_and_expired_session_checks(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/v1/session").status_code == 401
        assert client.post("/api/v1/session/enter", json={"request_id": str(uuid4())}, headers={"Origin": "https://evil.example"}).status_code == 403
        first = enter(client)
        assert enter(client) == first
        assert first["role"] == "user"
        cookie = client.cookies.get("bank_session")
        _, task = start(client)
        confirmation = task["interaction"]["record_ref"]
        other = make_app(tmp_path, user="U2")
        with TestClient(other) as second:
            enter(second)
            assert second.get(f"/api/v1/tasks/{task['task_id']}").status_code == 404
            assert post(second, f"/tasks/{task['task_id']}/resume").status_code == 404
            assert second.get(f"/api/v1/confirmations/{confirmation}").status_code == 404
            assert post(second, f"/confirmations/{confirmation}/answer", confirmation_version=1, choice="approve").status_code == 404
        from datetime import timedelta
        from .service import now
        app.state.api.store.write("UPDATE sessions SET expires_at=? WHERE session_id=?",
                                 ((now() - timedelta(seconds=1)).isoformat(), first["session_id"]))
        assert post(client, f"/tasks/{task['task_id']}/resume").status_code == 401
        assert client.get(f"/api/v1/confirmations/{confirmation}").status_code == 401
        new_session = enter(client)
        assert new_session["session_id"] != first["session_id"]
        assert client.get(f"/api/v1/tasks/{task['task_id']}").status_code == 200
        # Safe and explicit public-platform gap; never reuse old authorization.
        blocked = post(client, f"/tasks/{task['task_id']}/resume")
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "SESSION_RECONFIRMATION_REQUIRED"


def test_restart_keeps_task_and_receipts_without_repeating_model(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        cookie = client.cookies.get("bank_session")
        operation = task["data"]["operation_id"]
    restarted = make_app(tmp_path)
    with TestClient(restarted) as client:
        client.cookies.set("bank_session", cookie)
        snapshot = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert snapshot["task_id"] == task["task_id"]
        body = {"request_id": str(uuid4())}
        first = client.post(f"/api/v1/tasks/{task['task_id']}/resume", json=body, headers={"Origin": "http://testserver"})
        duplicate = client.post(f"/api/v1/tasks/{task['task_id']}/resume", json=body, headers={"Origin": "http://testserver"})
        assert first.json() == duplicate.json()
        snapshot = first.json()["data"]
        assert snapshot["data"]["operation_id"] == operation
        assert snapshot["run_id"] != task["run_id"]
        assert snapshot["interaction"]["kind"] == "confirmation"
        assert restarted.state.api.runtime.harness.planner.calls == 0
        assert client.get("/api/v1/tasks", params={"recovery_required": True}).json()["data"]["items"] == []


def test_medium_risk_face_is_admin_only_and_audit_read_does_not_run_model(tmp_path):
    app = make_app(tmp_path, risk=RiskLevel.MEDIUM)
    with TestClient(app) as user, TestClient(make_app(tmp_path, risk=RiskLevel.MEDIUM)) as admin:
        _, task = start(user)
        waiting = approve(user, task)
        challenge = waiting["interaction"]["record_ref"]
        assert post(user, f"/admin/verifications/{challenge}/face-result", submission_id=str(uuid4()), demo_round_id="D1", result="passed").status_code == 403
        started = post(user, f"/verifications/{challenge}/face/start").json()["data"]
        again = post(user, f"/verifications/{challenge}/face/start").json()["data"]
        assert again["face_expires_at"] == started["face_expires_at"]
        code = user.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        code_result = post(user, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
        assert code_result.json()["data"]["task"]["status"] == "waiting_approval"
        admin_login = admin.post("/api/v1/session/enter", json={"request_id": str(uuid4())}, headers={"Origin": "http://testserver", "X-Demo-Admin-Key": "test-admin-key"})
        assert admin_login.json()["data"]["role"] == "admin"
        wrong_round = post(admin, f"/admin/verifications/{challenge}/face-result", submission_id=str(uuid4()), demo_round_id="old", result="passed")
        assert wrong_round.status_code == 403
        face = post(admin, f"/admin/verifications/{challenge}/face-result", submission_id=str(uuid4()), demo_round_id="D1", result="passed")
        assert face.status_code == 200, face.text
        assert face.json()["data"]["task"]["status"] == "succeeded"
        timeline = admin.get("/api/v1/admin/audit/events", params={"task_id": task["task_id"], "limit": 100})
        assert timeline.status_code == 200, timeline.text
        events = timeline.json()["data"]["items"]
        assert {event["event_type"] for event in events} >= {"model.started", "security.decided", "bank.observed"}
        assert any(event["event_type"] == "verification.changed" and event["module"] == "api"
                   and event["actor_id"] == "demo-admin" and event["target_user_id"] == "U1" for event in events)
        evidence_ref = next(event["event_id"] for event in events if event["event_type"] == "model.finished")
        evidence = admin.get(f"/api/v1/admin/audit/events/{evidence_ref}")
        assert evidence.status_code == 200, evidence.text
        assert code not in evidence.text
        assert app.state.api.runtime.harness.planner.calls == 1


def test_resending_code_replaces_current_challenge_without_resetting_failures(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        waiting = approve(client, task)
        old = waiting["interaction"]["record_ref"]
        wrong = post(client, f"/verifications/{old}/code", submission_id=str(uuid4()), code="wrong")
        assert wrong.json()["data"]["verification"]["consecutive_code_failures"] == 1
        response = post(client, f"/verifications/{old}/resend-code")
        assert response.status_code == 200, response.text
        new = response.json()["data"]["challenge_id"]
        assert new != old
        assert response.json()["data"]["consecutive_code_failures"] == 1
        current = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert current["interaction"]["record_ref"] == new
        assert client.get(f"/api/v1/verifications/{old}/demo-code").status_code == 409


def test_pages_bind_cursor_to_user_and_filter(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        enter(client)
        created = [post(client, "/threads").json()["data"]["thread_id"] for _ in range(3)]
        first = client.get("/api/v1/threads", params={"limit": 2}).json()["data"]
        second = client.get("/api/v1/threads", params={"limit": 2, "cursor": first["next_cursor"]}).json()["data"]
        assert {item["thread_id"] for item in first["items"] + second["items"]} == set(created)
        assert second["next_cursor"] is None
        invalid = client.get("/api/v1/tasks", params={"cursor": first["next_cursor"]})
        assert invalid.status_code == 400
        assert client.get("/api/v1/threads", params={"limit": 101}).status_code == 400


def test_accepted_message_can_resume_after_crash_before_worker_starts(tmp_path, monkeypatch):
    from fastapi import BackgroundTasks
    app = make_app(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(BackgroundTasks, "add_task", lambda *_args, **_kwargs: None)
        with TestClient(app) as client:
            enter(client)
            thread = post(client, "/threads").json()["data"]["thread_id"]
            accepted = post(client, f"/threads/{thread}/messages", text="给妈妈转 500 元")
            assert accepted.status_code == 202
            task_id = accepted.json()["data"]["task_id"]
            cookie = client.cookies.get("bank_session")
            assert app.state.api.runtime.harness.planner.calls == 0
    restarted = make_app(tmp_path)
    with TestClient(restarted) as client:
        client.cookies.set("bank_session", cookie)
        recoverable = client.get("/api/v1/tasks", params={"recovery_required": True}).json()["data"]["items"]
        assert [t["task_id"] for t in recoverable] == [task_id]
        resumed = post(client, f"/tasks/{task_id}/resume")
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["data"]["interaction"]["kind"] == "confirmation"
        assert restarted.state.api.runtime.harness.planner.calls == 1


def test_timeout_queries_original_operation_without_resubmitting(tmp_path):
    import time
    app = make_app(tmp_path)
    # The public mock-bank fault control simulates its response arriving late.
    app.state.api.runtime.gateway._bank.slow_seconds = 0.2
    app.state.api.runtime.gateway._transfer_timeout_seconds = 0.01
    app.state.api.runtime.gateway._bank.arm_slow_once("U1")
    with TestClient(app) as client:
        _, task = start(client)
        waiting = approve(client, task)
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        result = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
        assert result.status_code == 200, result.text
        task = result.json()["data"]["task"]
        # The graph normally polls until the original result settles. Either
        # final success or a pending query is valid, but a second debit is not.
        if task["status"] == "needs_attention":
            time.sleep(0.3)
            queried = post(client, f"/tasks/{task['task_id']}/query-result")
            assert queried.status_code == 200, queried.text
            current = queried.json()["data"]
        else:
            current = task
        assert current["status"] == "succeeded"
        assert current["data"]["operation_id"] == task["data"]["operation_id"]
        assert post(client, f"/tasks/{task['task_id']}/cancel").status_code == 409
        assert len(app.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1")) == 1


def test_live_sse_reconnect_replays_events_without_new_task(tmp_path):
    import json
    import socket
    import threading
    import time
    import httpx
    import uvicorn

    app = make_app(tmp_path)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    worker = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    worker.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
            enter(client)
            thread = post(client, "/threads").json()["data"]["thread_id"]
            accepted = post(client, f"/threads/{thread}/messages", text="给妈妈转 500 元")
            task_id = accepted.json()["data"]["task_id"]
            with client.stream("GET", f"/api/v1/threads/{thread}/events") as stream:
                assert stream.status_code == 200
                assert stream.headers["content-type"].startswith("text/event-stream")
                for line in stream.iter_lines():
                    if line.startswith("data: "):
                        event = json.loads(line[6:])
                        if event["event_type"] == "task_updated":
                            break
            cursor = event["event_id"]
            original_revision = event["payload"]["task_revision"]
            with client.stream("GET", f"/api/v1/threads/{thread}/events", headers={"Last-Event-ID": cursor}) as stream:
                for line in stream.iter_lines():
                    if line.startswith("data: "):
                        next_event = json.loads(line[6:])
                        break
            assert next_event["event_id"] != cursor
            assert next_event["task_id"] == task_id
            snapshot = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
            assert snapshot["task_revision"] >= original_revision
            assert app.state.api.runtime.harness.planner.calls == 1
            assert len(client.get("/api/v1/tasks").json()["data"]["items"]) == 1
            assert client.get(f"/api/v1/threads/{thread}/events", headers={"Last-Event-ID": "foreign"}).status_code == 409
    finally:
        server.should_exit = True
        worker.join(timeout=5)
        sock.close()
        assert not worker.is_alive()


def test_restart_after_bank_verification_before_api_binding_uses_saved_submission(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        waiting = approve(client, task)
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        body = {"request_id": str(uuid4()), "submission_id": str(uuid4()), "code": code}
        cookie = client.cookies.get("bank_session")
        service = app.state.api
        who = service.identity(cookie)
        trusted, _ = service.verification(who, challenge)
        service.store.receipt(who, f"/api/v1/verifications/{challenge}/code", body["request_id"], body)
        from uuid import UUID
        saved = service.runtime.gateway.verify_code(trusted, challenge, UUID(body["submission_id"]), code)
        assert saved.verification_id
    restarted = make_app(tmp_path)
    with TestClient(restarted) as client:
        client.cookies.set("bank_session", cookie)
        recovered = client.post(f"/api/v1/verifications/{challenge}/code", json=body, headers={"Origin": "http://testserver"})
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["data"]["task"]["status"] == "succeeded"
        assert restarted.state.api.runtime.harness.planner.calls == 0
        assert len(restarted.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1")) == 1


def test_deployment_entrypoint_loads_only_server_configured_runtime(tmp_path, monkeypatch):
    import sys
    import types
    injected = make_app(tmp_path)
    configured_runtime = injected.state.api.runtime
    factory = types.ModuleType("api_test_bootstrap")
    factory.build_runtime = lambda: configured_runtime
    monkeypatch.setitem(sys.modules, factory.__name__, factory)
    monkeypatch.setenv("BANK_RUNTIME_FACTORY", "api_test_bootstrap:build_runtime")
    monkeypatch.setenv("BANK_API_SECRET", "s" * 32)
    monkeypatch.setenv("BANK_API_ORIGINS", "http://testserver")
    with TestClient(create_app()) as client:
        enter(client)
        assert client.get("/api/v1/session").status_code == 200
        assert post(client, "/threads").status_code == 200


def test_deployment_without_runtime_factory_fails_before_accepting_requests(monkeypatch):
    monkeypatch.delenv("BANK_RUNTIME_FACTORY", raising=False)
    with pytest.raises(RuntimeError, match="BANK_RUNTIME_FACTORY"):
        with TestClient(create_app()):
            pass


@pytest.mark.parametrize("operation", ["code", "resend-code", "face/start", "face-result"])
def test_audit_failure_prevents_verification_writes(tmp_path, monkeypatch, operation):
    from contextlib import ExitStack
    app = make_app(tmp_path, risk=RiskLevel.MEDIUM)
    with TestClient(app) as user, ExitStack() as resources:
        _, task = start(user)
        waiting = approve(user, task)
        challenge = waiting["interaction"]["record_ref"]
        client = user
        body = {}
        path = f"/verifications/{challenge}/{operation}"
        if operation == "code":
            code = user.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
            body = {"submission_id": str(uuid4()), "code": code}
        elif operation == "face-result":
            assert post(user, f"/verifications/{challenge}/face/start").status_code == 200
            client = resources.enter_context(TestClient(make_app(tmp_path, risk=RiskLevel.MEDIUM)))
            login = client.post("/api/v1/session/enter", json={"request_id": str(uuid4())},
                                headers={"Origin": "http://testserver", "X-Demo-Admin-Key": "test-admin-key"})
            assert login.status_code == 200
            path = f"/admin/verifications/{challenge}/face-result"
            body = {"submission_id": str(uuid4()), "demo_round_id": "D1", "result": "passed"}
        before = user.get(f"/api/v1/verifications/{challenge}").json()["data"]
        def unavailable(*args, **kwargs):
            raise RuntimeError("audit offline")
        monkeypatch.setattr(client.app.state.api.runtime.audit, "append", unavailable)
        rejected = post(client, path, **body)
        assert rejected.status_code == 503, rejected.text
        after = user.get(f"/api/v1/verifications/{challenge}").json()["data"]
        assert before == after
        assert user.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]["interaction"]["record_ref"] == challenge


def test_read_dependency_errors_use_controlled_envelope_without_exception_text(tmp_path, monkeypatch):
    import sqlite3
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        waiting = approve(client, task)
        challenge = waiting["interaction"]["record_ref"]
        with monkeypatch.context() as patch:
            def bank_unavailable(*args, **kwargs):
                raise RuntimeError("sensitive-provider-diagnostics")
            patch.setattr(app.state.api.runtime.gateway, "get_verification", bank_unavailable)
            result = client.get(f"/api/v1/verifications/{challenge}")
            assert result.status_code == 503
            assert result.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
            assert "sensitive-provider-diagnostics" not in result.text
        def database_unavailable(*args, **kwargs):
            raise sqlite3.OperationalError("sensitive-database-diagnostics")
        monkeypatch.setattr(app.state.api.store, "rows", database_unavailable)
        result = client.get(f"/api/v1/tasks/{task['task_id']}")
        assert result.status_code == 503
        assert "sensitive-database-diagnostics" not in result.text


def test_accepted_unstarted_task_can_cancel_without_calling_model(tmp_path, monkeypatch):
    from fastapi import BackgroundTasks
    app = make_app(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(BackgroundTasks, "add_task", lambda *_args, **_kwargs: None)
        with TestClient(app) as client:
            enter(client)
            thread = post(client, "/threads").json()["data"]["thread_id"]
            accepted = post(client, f"/threads/{thread}/messages", text="给妈妈转 500 元")
            task_id = accepted.json()["data"]["task_id"]
            cookie = client.cookies.get("bank_session")
    restarted = make_app(tmp_path)
    with TestClient(restarted) as client:
        client.cookies.set("bank_session", cookie)
        before = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
        assert "cancel" in before["allowed_actions"]
        cancelled = post(client, f"/tasks/{task_id}/cancel")
        assert cancelled.status_code == 200, cancelled.text
        after = cancelled.json()["data"]
        assert after["status"] == "cancelled"
        assert after["task_revision"] > before["task_revision"]
        assert post(client, f"/tasks/{task_id}/resume").json()["data"]["status"] == "cancelled"
        assert restarted.state.api.runtime.harness.planner.calls == 0


def test_restart_after_final_face_before_binding_recovers_original_submission(tmp_path):
    app = make_app(tmp_path, risk=RiskLevel.MEDIUM)
    with TestClient(app) as user, TestClient(make_app(tmp_path, risk=RiskLevel.MEDIUM)) as admin:
        _, task = start(user)
        waiting = approve(user, task)
        challenge = waiting["interaction"]["record_ref"]
        assert post(user, f"/verifications/{challenge}/face/start").status_code == 200
        code = user.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        assert post(user, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code).status_code == 200
        login = admin.post("/api/v1/session/enter", json={"request_id": str(uuid4())},
                           headers={"Origin": "http://testserver", "X-Demo-Admin-Key": "test-admin-key"})
        assert login.status_code == 200
        body = {"request_id": str(uuid4()), "submission_id": str(uuid4()), "demo_round_id": "D1", "result": "passed"}
        admin_cookie = admin.cookies.get("bank_session")
        user_cookie = user.cookies.get("bank_session")
        who = admin.app.state.api.identity(admin_cookie)
        endpoint = f"/api/v1/admin/verifications/{challenge}/face-result"
        admin.app.state.api.store.receipt(who, endpoint, body["request_id"], body)
        from app.services.mock_bank.verification import AdminContext
        from uuid import UUID
        saved = admin.app.state.api.runtime.gateway.verify_face(AdminContext(who.user_id, True, "D1", "U1"),
            challenge, UUID(body["submission_id"]), "passed")
        assert saved.verification_id
    restarted = make_app(tmp_path, risk=RiskLevel.MEDIUM)
    with TestClient(restarted) as admin:
        admin.cookies.set("bank_session", admin_cookie)
        recovered = admin.post(endpoint, json=body, headers={"Origin": "http://testserver"})
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["data"]["task"]["status"] == "succeeded"
        repeated = admin.post(endpoint, json=body, headers={"Origin": "http://testserver"})
        assert repeated.json() == recovered.json()
        assert restarted.state.api.runtime.harness.planner.calls == 0
        assert len(restarted.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1")) == 1


def test_cancel_in_flight_only_queries_original_bank_operation(tmp_path):
    app = make_app(tmp_path)
    bank = app.state.api.runtime.gateway._bank
    bank.slow_seconds = 12.0
    app.state.api.runtime.gateway._transfer_timeout_seconds = 0.01
    bank.arm_slow_once("U1")
    with TestClient(app) as client:
        _, task = start(client)
        waiting = approve(client, task)
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        response = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
        assert response.status_code == 200, response.text
        pending = response.json()["data"]["task"]
        assert pending["status"] == "needs_attention"
        assert "query" in pending["allowed_actions"]
        assert "cancel" in pending["allowed_actions"]
        original = pending["data"]["operation_id"]
        stopped = post(client, f"/tasks/{task['task_id']}/cancel")
        assert stopped.status_code == 200, stopped.text
        assert stopped.json()["data"]["cancel_requested"]
        assert stopped.json()["data"]["data"]["operation_id"] == original
        # Wait for the original bank worker to finish, without another submission.
        app.state.api.runtime.gateway.close()
        settled = post(client, f"/tasks/{task['task_id']}/query-result")
        assert settled.status_code == 200, settled.text
        final = settled.json()["data"]
        assert final["status"] == "succeeded", final
        assert final["data"]["operation_id"] == original
        assert final["cancel_requested"]
        assert len(bank.store.list_ledger("U1", "A1")) == 1
