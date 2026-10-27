"""F30—F32 HTTP checks use new isolated stores, never the shared demo bank."""

from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.agent_platform.transfer_runtime import TransferRuntime
from app.agent_platform.demo_clock import DemoClock
from app.audit.journal import AuditJournal
from app.contracts.bank import SavedPayee
from app.contracts.common import RiskLevel
from app.contracts.platform import TrustedContext
from app.memory.adapter import MemoryAdapter, MemoryContext
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore
from app.storage.mock_bank.repository import MockBankStore

from .app import ApiConfig, create_app
from .test_app import Planner, enter, make_app, post, start


def reset_app(path):
    """Real stores, gateway drain and shared business clock; planner is scripted."""
    application = ApplicationStore(path / "application.sqlite")
    clock = DemoClock()
    clock.set(datetime(2026, 10, 27, 9, tzinfo=timezone.utc))
    bank = MockBankService(MockBankStore(path / "bank.sqlite"), demo_secret=b"s" * 32,
                           clock=clock)
    memory = MemoryAdapter(application, active_round=lambda: bank.current_demo_round_id or "D1")
    if bank.current_demo_round_id is None:
        memory.seed_demo("U1", "D1", "2026-10")
    runtime = TransferRuntime(application, memory, AuditJournal(application.path), bank,
        Planner(), authorize_capability=lambda *_: True, authorize_tool=lambda *_: True,
        assess_risk=lambda *_: RiskLevel.LOW, authorize_face=lambda admin, *_: admin.authorized,
        demo_clock=clock)
    return create_app(runtime, ApiConfig(secret=b"s" * 32, admin_key="test-admin-key",
                                        origins=("http://testserver",)))


def prepare_reset(client):
    client.cookies.clear()
    admin_enter(client)
    preview = post(client, "/admin/demo/reset-preview", demo_round_id="D1")
    assert preview.status_code == 200, preview.text
    return {"request_id": str(uuid4()),
            "reset_confirmation_id": preview.json()["data"]["reset_confirmation_id"]}


def submit_reset(client, body):
    response = client.post("/api/v1/admin/demo/reset", json=body,
                           headers={"Origin": "http://testserver"})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def admin_enter(client):
    response = client.post("/api/v1/session/enter", json={"request_id": str(uuid4())},
        headers={"Origin": "http://testserver", "X-Demo-Admin-Key": "test-admin-key"})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_reset_preview_requires_admin_and_does_not_reset_the_bank(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        enter(client)
        response = post(client, "/admin/demo/reset-preview", demo_round_id="D1")
        assert response.status_code == 403, response.text
        client.cookies.clear()
        admin_enter(client)
        request_id = str(uuid4())
        body = {"request_id": request_id, "demo_round_id": "D1"}
        first = client.post("/api/v1/admin/demo/reset-preview", json=body,
                            headers={"Origin": "http://testserver"})
        assert first.status_code == 200, first.text
        assert first.json()["data"]["demo_round_id"] == "D1"
        assert first.json()["data"]["effects"]
        assert client.post("/api/v1/admin/demo/reset-preview", json=body,
            headers={"Origin": "http://testserver"}).json() == first.json()
        assert post(client, "/admin/demo/reset-preview", demo_round_id="wrong").status_code == 409


def test_reset_invalidates_old_authority_and_restores_memory_while_preserving_history(tmp_path):
    app = reset_app(tmp_path)
    runtime = app.state.api.runtime
    with TestClient(app) as client:
        _thread, task = start(client)
        assert task["status"] == "waiting_approval"
        old_cookie = client.cookies.get("bank_session")
        old_identity = app.state.api.identity(old_cookie)
        old_context = TrustedContext(user_id="U1", session_id=old_identity.session_id,
            demo_round_id="D1", task_id=task["task_id"], run_id=task["run_id"], parent_task_id=None)
        audit_before = app.state.api.store.rows("SELECT event_id FROM audit_events ORDER BY row_id")
        assert audit_before
        body = prepare_reset(client)
        result = submit_reset(client, body)
        assert result["status"] == "succeeded", result
        target = result["resulting_round_id"]
        assert target != "D1"
        assert runtime.bank.current_demo_round_id == target
        assert app.state.api.demo.current_round_id == target
        audit_after = app.state.api.store.rows("SELECT event_id FROM audit_events ORDER BY row_id")
        assert all(event in audit_after for event in audit_before)
        assert runtime.application.get_task("U1", "D1", task["task_id"]) is not None
        assert runtime.bank.submit_transfer(old_context, uuid4(), "A1",
            SavedPayee(kind="saved", payee_id="A2"), 10000).error.code == "ACCESS_DENIED"
        with pytest.raises(ValueError, match="STALE_ROUND"):
            runtime.memory.backend(MemoryContext("U1", old_identity.session_id, "D1"))
        old_response = client.get(f"/api/v1/tasks/{task['task_id']}",
                                 headers={"Cookie": "bank_session=" + old_cookie})
        assert old_response.status_code == 401
        # Management original-id reads remain possible with the original admin grant.
        assert client.get("/api/v1/admin/operations/" + result["management_operation_id"]).json()["data"] == result
        client.cookies.clear()
        new_session = enter(client)
        assert new_session["demo_round_id"] == target
        assert client.get(f"/api/v1/tasks/{task['task_id']}").status_code == 404
        memories = runtime.memory.list(MemoryContext("U1", new_session["session_id"], target))
        assert len(memories) == 6
        assert client.get("/api/v1/admin/audit/events", params={"task_id": task["task_id"],
            "demo_round_id": "D1"}).status_code == 403
        client.cookies.clear()
        admin_enter(client)
        historical = client.get("/api/v1/admin/audit/events", params={"task_id": task["task_id"],
            "demo_round_id": "D1"})
        assert historical.status_code == 200, historical.text
        old_event_id = audit_before[0]["event_id"]
        assert client.get("/api/v1/admin/audit/events/" + old_event_id).status_code == 200
        assert client.get("/api/v1/admin/audit/events", params={"task_id": task["task_id"],
            "demo_round_id": "unrelated-round"}).status_code == 403
        # A real, separately granted administrator has no ownership of this reset.
        at = datetime.now(timezone.utc)
        other_session = str(uuid4())
        runtime.application.create_session(other_session, "other-admin", target, at.isoformat(),
                                           (at + timedelta(hours=2)).isoformat())
        app.state.api.store.write("INSERT INTO api_sessions VALUES (?, 'admin')", (other_session,))
        other_cookie = "bank_session=" + app.state.api.cookie(other_session)
        assert client.get("/api/v1/admin/audit/events", params={"task_id": task["task_id"],
            "demo_round_id": "D1"}, headers={"Cookie": other_cookie}).status_code == 403
        assert client.get("/api/v1/admin/audit/events/" + old_event_id,
                          headers={"Cookie": other_cookie}).status_code == 403


def test_waiting_reset_stops_new_business_and_only_the_same_request_can_continue(tmp_path, monkeypatch):
    app = reset_app(tmp_path)
    service = app.state.api
    drained = [False]
    monkeypatch.setattr(service.runtime.gateway, "wait_for_inflight", lambda timeout: drained[0])
    with TestClient(app) as client:
        enter(client)
        old_cookie = client.cookies.get("bank_session")
        body = prepare_reset(client)
        result = submit_reset(client, body)
        assert (result["status"], result["phase"]) == ("running", "waiting_inflight")
        assert service.runtime.bank.current_demo_round_id is None
        blocked = client.post("/api/v1/threads", json={"request_id": str(uuid4())},
            headers={"Origin": "http://testserver", "Cookie": "bank_session=" + old_cookie})
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "DEMO_RESET_IN_PROGRESS"
        assert post(client, "/admin/demo/reset-preview", demo_round_id="D1").status_code == 409
        # GET never starts or advances a bank write.
        assert client.get("/api/v1/admin/operations/" + result["management_operation_id"]).json()["data"] == result
        assert service.runtime.bank.current_demo_round_id is None
        drained[0] = True
        completed = submit_reset(client, body)
        assert completed["status"] == "succeeded"
        assert completed["management_operation_id"] == result["management_operation_id"]


def test_management_request_conflicts_cannot_consume_another_confirmation(tmp_path):
    app = reset_app(tmp_path)
    with TestClient(app) as client:
        first = prepare_reset(client)
        other = post(client, "/admin/demo/reset-preview", demo_round_id="D1").json()["data"]
        completed = submit_reset(client, first)
        assert completed["status"] == "succeeded"
        changed = {**first, "reset_confirmation_id": other["reset_confirmation_id"]}
        response = client.post("/api/v1/admin/demo/reset", json=changed,
                               headers={"Origin": "http://testserver"})
        assert response.status_code == 409
        reused = {**first, "request_id": str(uuid4())}
        response = client.post("/api/v1/admin/demo/reset", json=reused,
                               headers={"Origin": "http://testserver"})
        assert response.status_code == 409


def test_bank_response_loss_recovers_original_receipt_without_clearing_again(tmp_path, monkeypatch):
    app = reset_app(tmp_path)
    bank = app.state.api.runtime.bank
    original = bank.reset_demo
    calls = []

    def lose_response(*args):
        calls.append(args)
        original(*args)
        raise TimeoutError("lost reset response")

    monkeypatch.setattr(bank, "reset_demo", lose_response)
    with TestClient(app) as client:
        body = prepare_reset(client)
        failed = submit_reset(client, body)
        assert (failed["status"], failed["phase"]) == ("failed", "resetting_bank")
        assert app.state.api.demo.current_round_id == "D1"
        target = bank.current_demo_round_id
        assert target != "D1"
        new_context = TrustedContext(user_id="U1", session_id="test-new-session", demo_round_id=target,
            task_id="test-new-task", run_id="test-new-run", parent_task_id=None)
        bank.submit_transfer(new_context, uuid4(), "A1", SavedPayee(kind="saved", payee_id="A2"), 10000)
        before = bank.store.get_account("U1", "A1").book_balance_fen
        recovered = submit_reset(client, body)
        assert recovered["status"] == "succeeded", recovered
        assert recovered["management_operation_id"] == failed["management_operation_id"]
        assert len(calls) == 1
        assert bank.store.get_account("U1", "A1").book_balance_fen == before
        assert submit_reset(client, body) == recovered


def test_partial_memory_failure_stays_closed_and_management_relogin_can_continue(tmp_path, monkeypatch):
    app = reset_app(tmp_path)
    memory = app.state.api.runtime.memory
    original = memory.reset_user
    calls = []

    def unavailable(*args):
        calls.append(args)
        raise OSError("memory unavailable")

    monkeypatch.setattr(memory, "reset_user", unavailable)
    with TestClient(app) as client:
        body = prepare_reset(client)
        failed = submit_reset(client, body)
        assert (failed["status"], failed["phase"]) == ("failed", "resetting_memory")
        assert app.state.api.demo.current_round_id == "D1"
        client.cookies.clear()
        admin_enter(client)
        result = client.get("/api/v1/admin/operations/" + failed["management_operation_id"])
        assert result.status_code == 200
        assert result.json()["data"] == failed
        assert len(calls) == 1
        # Ordinary login remains blocked even though the bank already has its new round.
        client.cookies.clear()
        assert post(client, "/session/enter").status_code == 409
        admin_enter(client)
        monkeypatch.setattr(memory, "reset_user", original)
        recovered = submit_reset(client, body)
        assert recovered["status"] == "succeeded", recovered


def test_reset_result_round_and_clock_survive_a_restart_with_the_old_config(tmp_path):
    first = reset_app(tmp_path)
    with TestClient(first) as client:
        body = prepare_reset(client)
        result = submit_reset(client, body)
        assert result["status"] == "succeeded", result
        initial = first.state.api.demo.state()["initial_logical_at"]
    second = reset_app(tmp_path)
    with TestClient(second) as client:
        admin_enter(client)
        response = client.get("/api/v1/admin/operations/" + result["management_operation_id"])
        assert response.json()["data"] == result
        assert second.state.api.demo.current_round_id == result["resulting_round_id"]
        assert second.state.api.demo.state()["initial_logical_at"] == initial
        assert second.state.api.runtime.bank.clock() == datetime.fromisoformat(initial)
        client.cookies.clear()
        assert enter(client)["demo_round_id"] == result["resulting_round_id"]


def test_http_reset_waits_for_a_real_timed_out_gateway_future(tmp_path, monkeypatch):
    app = reset_app(tmp_path)
    runtime = app.state.api.runtime
    runtime.gateway.close()
    # This seam isolates reset coordination from execution authorization. The
    # future, delayed bank call, account mutation and reset are all real.
    runtime.gateway = BankGateway(runtime.bank, transfer_timeout_seconds=0.01,
                                  authorize_transfer=lambda *_: True)
    started, release = Event(), Event()
    original = runtime.bank.submit_transfer

    def delayed(*args):
        started.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(runtime.bank, "submit_transfer", delayed)
    try:
        with TestClient(app) as client:
            who = TrustedContext(user_id="U1", session_id="test-session", demo_round_id="D1",
                task_id="test-transfer", run_id="test-run", parent_task_id=None)
            operation_id = uuid4()
            pending = runtime.gateway.submit_transfer(who, operation_id, "A1",
                SavedPayee(kind="saved", payee_id="A2"), 50000)
            assert pending.error.code == "CALL_TIMEOUT"
            assert started.wait(2)
            assert runtime.gateway.get_operation(who, operation_id).lookup == "not_found"
            body = prepare_reset(client)
            waiting = submit_reset(client, body)
            assert waiting["status"] == "running"
            assert waiting["phase"] == "waiting_inflight"
            assert runtime.bank.current_demo_round_id is None
            release.set()
            assert runtime.gateway.wait_for_inflight(3.0)
            assert runtime.gateway.get_operation(who, operation_id).operation.operation_status == "succeeded"
            completed = submit_reset(client, body)
            assert completed["status"] == "succeeded", completed
            assert completed["management_operation_id"] == waiting["management_operation_id"]
            assert runtime.bank.store.get_account("U1", "A1").book_balance_fen == 6000000
    finally:
        release.set()
        runtime.gateway.close()


def test_partial_reset_can_restart_then_resume_its_original_management_request(tmp_path, monkeypatch):
    first = reset_app(tmp_path)
    memory = first.state.api.runtime.memory
    monkeypatch.setattr(memory, "reset_user", lambda *_: (_ for _ in ()).throw(OSError("unavailable")))
    with TestClient(first) as client:
        body = prepare_reset(client)
        failed = submit_reset(client, body)
        assert failed["phase"] == "resetting_memory"
        target = first.state.api.runtime.bank.current_demo_round_id
        assert first.state.api.demo.current_round_id == "D1"
    second = reset_app(tmp_path)
    with TestClient(second) as client:
        admin_enter(client)
        original = client.get("/api/v1/admin/operations/" + failed["management_operation_id"])
        assert original.status_code == 200
        assert original.json()["data"] == failed
        assert second.state.api.demo.current_round_id == "D1"
        assert second.state.api.runtime.bank.current_demo_round_id == target
        completed = submit_reset(client, body)
        assert completed["status"] == "succeeded", completed
        assert completed["resulting_round_id"] == target
        assert completed["management_operation_id"] == failed["management_operation_id"]


def test_missing_required_admin_audit_stops_before_the_bank_reset(tmp_path, monkeypatch):
    app = reset_app(tmp_path)
    runtime = app.state.api.runtime
    append = runtime.audit.append

    def unavailable(*_args, **_kwargs):
        raise OSError("audit unavailable")

    with TestClient(app) as client:
        body = prepare_reset(client)
        monkeypatch.setattr(runtime.audit, "append", unavailable)
        failed = submit_reset(client, body)
        assert (failed["status"], failed["phase"]) == ("failed", "resetting_bank")
        assert runtime.bank.current_demo_round_id is None
        assert runtime.bank.store.get_account("U1", "A1").book_balance_fen == 6000000
        monkeypatch.setattr(runtime.audit, "append", append)
        completed = submit_reset(client, body)
        assert completed["status"] == "succeeded", completed
        assert completed["management_operation_id"] == failed["management_operation_id"]


def test_reset_persists_admission_stop_without_waiting_on_the_api_worker_lock(tmp_path):
    app = reset_app(tmp_path)
    service = app.state.api
    acquired, release = Event(), Event()

    def worker():
        with service.mutation_lock:
            acquired.set()
            assert release.wait(5)

    with TestClient(app) as client:
        body = prepare_reset(client)
        thread = Thread(target=worker)
        thread.start()
        try:
            assert acquired.wait(2)
            waiting = submit_reset(client, body)
            assert (waiting["status"], waiting["phase"]) == ("running", "waiting_inflight")
            assert service.demo.state()["reset_state"] == "waiting_inflight"
            assert service.runtime.bank.current_demo_round_id is None
        finally:
            release.set()
            thread.join(3)
        completed = submit_reset(client, body)
        assert completed["status"] == "succeeded", completed
