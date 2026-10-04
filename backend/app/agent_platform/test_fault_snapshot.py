"""Persist mid-flight faults while keeping bank authority and operation identity."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.api.test_app import make_app, start, approve, post, enter
from app.contracts.bank import BankError, OperationNotFound, QueryFailure


def test_session_expires_inside_original_query_and_rebuild_queries_only_original(tmp_path):
    app = make_app(tmp_path)
    service = app.state.api
    bank = service.runtime.gateway._bank
    reads, submits = [], []
    with TestClient(app) as client:
        _, task = start(client)
        task_id, operation_id = task["task_id"], task["data"]["operation_id"]
        waiting = approve(client, task)
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        old_session = service.identity(client.cookies.get("bank_session"))

        def unknown(*args, **kwargs):
            submits.append(str(args[1]))
            return QueryFailure(kind="error", error=BankError(code="CALL_TIMEOUT", details={}))

        def expire_inside_read(*args):
            reads.append(str(args[1]))
            service.store.write("UPDATE sessions SET expires_at=? WHERE session_id=?",
                ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), old_session.session_id))
            return OperationNotFound(lookup="not_found", operation=None)

        with patch.object(bank, "submit_transfer", side_effect=unknown), \
             patch.object(bank, "get_operation", side_effect=expire_inside_read):
            response = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
        assert response.status_code == 401, response.text
        assert reads == [operation_id]
        assert submits == [operation_id]
        saved = service.runtime.application.get_task("U1", "D1", task_id)
        assert saved.status.value == "needs_attention"
        assert saved.snapshot["result"]["data"]["operation_id"] == operation_id
        assert saved.snapshot["result"]["interaction"] is None
        assert client.get(f"/api/v1/tasks/{task_id}").status_code == 401
        cookies = dict(client.cookies)
    service.runtime.close()

    restarted = make_app(tmp_path)
    with TestClient(restarted) as client:
        client.cookies.update(cookies)
        assert client.get(f"/api/v1/tasks/{task_id}").status_code == 401
        client.cookies.clear()
        enter(client)
        read = client.get(f"/api/v1/tasks/{task_id}")
        assert read.status_code == 200, read.text
        pending = read.json()["data"]
        assert pending["status"] == "needs_attention"
        assert pending["data"]["operation_id"] == operation_id
        with patch.object(restarted.state.api.runtime.gateway._bank, "submit_transfer", side_effect=AssertionError("must not resubmit")):
            recovered = post(client, f"/tasks/{task_id}/resume")
        assert recovered.status_code == 200, recovered.text
        current = recovered.json()["data"]
        assert current["task_id"] == task_id
        assert current["data"]["operation_id"] == operation_id
        assert current["status"] == "needs_attention"
        assert current["data"]["operation"] is None
        assert restarted.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1") == []
    restarted.state.api.runtime.close()


@pytest.mark.parametrize("fault_step", ["collect", "precheck", "security"])
def test_amount_change_fault_snapshot_matches_committed_checkpoint_and_restart(tmp_path, fault_step):
    app = make_app(tmp_path)
    service = app.state.api
    with TestClient(app) as client:
        _, task = start(client)
        task_id = task["task_id"]
        original_operation = task["data"]["operation_id"]
        who = service.identity(client.cookies.get("bank_session"))
        append = service.runtime.audit.append_in_transaction

        def unavailable(connection, event, **kwargs):
            if event.event_type == "task.transition" and event.payload.step_id == fault_step and event.payload.reason_code == "NODE_STARTED":
                raise RuntimeError("injected next-node audit outage")
            return append(connection, event, **kwargs)

        with patch.object(service.runtime.audit, "append_in_transaction", side_effect=unavailable), \
             patch.object(service.runtime.gateway._bank, "submit_transfer", wraps=service.runtime.gateway._bank.submit_transfer) as submits:
            with pytest.raises(RuntimeError, match="next-node audit outage"):
                service.continue_task(who, task_id, {"fields": {"amount_fen": 60000}})
        assert submits.call_count == 0
        trusted = service.trusted(who, task_id)
        stored = service.runtime.application.get_task("U1", "D1", task_id)
        saver = service.runtime.memory.checkpointer(service.runtime.harness._scope(trusted), task_id)
        flow = service.runtime._transfer_factory(trusted, saver, service.runtime.harness._trace(trusted, stored))
        checkpoint = flow.graph.get_state({"configurable": {"thread_id": stored.checkpoint_thread_id}})
        assert checkpoint.values["amount_fen"] == 60000
        assert checkpoint.values["operation_id"] != original_operation
        assert stored.checkpoint_id == checkpoint.config["configurable"]["checkpoint_id"]
        visible = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
        assert visible["status"] == "needs_attention"
        assert visible["data"]["amount_fen"] == checkpoint.values["amount_fen"]
        assert visible["data"]["operation_id"] == checkpoint.values["operation_id"]
        cookies = dict(client.cookies)
    service.runtime.close()
    restarted = make_app(tmp_path)
    with TestClient(restarted) as client:
        client.cookies.update(cookies)
        before = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
        assert before["data"] == visible["data"]
        recovered = post(client, f"/tasks/{task_id}/resume")
        assert recovered.status_code == 200, recovered.text
        current = recovered.json()["data"]
        assert current["data"]["amount_fen"] == 60000
        if visible["data"]["operation_id"] is not None:
            assert current["data"]["operation_id"] == visible["data"]["operation_id"]
        else:
            assert current["data"]["operation_id"] != original_operation
        assert current["interaction"]["kind"] == "confirmation"
        stale = post(client, f"/confirmations/{task['interaction']['record_ref']}/answer", confirmation_version=1, choice="approve")
        assert stale.status_code == 409
        assert restarted.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1") == []
    restarted.state.api.runtime.close()


def test_completed_result_is_saved_before_completion_audit_fails(tmp_path):
    app = make_app(tmp_path)
    service = app.state.api
    with TestClient(app) as client:
        _, task = start(client)
        waiting = approve(client, task)
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        append = service.runtime.audit.append_in_transaction

        def unavailable(connection, event, **kwargs):
            if event.event_type == "recovery.checked" and event.payload.reason_code == "PUBLIC_CAPABILITY_RESUMED":
                raise RuntimeError("injected completion-audit outage")
            return append(connection, event, **kwargs)

        with patch.object(service.runtime.audit, "append_in_transaction", side_effect=unavailable):
            response = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
        assert response.status_code == 503
        current = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert current["status"] == "succeeded"
        assert current["data"]["operation_id"] == task["data"]["operation_id"]
        assert current["data"]["operation"]["receipt"]["amount_fen"] == 50000
        assert len(service.runtime.gateway._bank.store.list_ledger("U1", "A1")) == 1
        cookies = dict(client.cookies)
    service.runtime.close()
    restarted = make_app(tmp_path)
    with TestClient(restarted) as client:
        client.cookies.update(cookies)
        resumed = post(client, f"/tasks/{task['task_id']}/resume")
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["data"]["status"] == "succeeded"
        assert len(restarted.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1")) == 1
    restarted.state.api.runtime.close()
