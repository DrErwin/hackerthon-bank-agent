"""Unknown verification outcomes stay visible and recover by original submission."""
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from app.api.test_app import make_app, start, approve, post
from app.storage.database import connect
from app.storage.mock_bank.repository import MockBankStore


@pytest.mark.parametrize("bank_saved", [False, True])
def test_verification_fault_updates_task_and_replays_original_submission(tmp_path, bank_saved):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, initial = start(client)
        waiting = approve(client, initial)
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        body = {"request_id": str(uuid4()), "submission_id": str(uuid4()), "code": code}
        path = f"/api/v1/verifications/{challenge}/code"
        gateway = app.state.api.runtime.gateway
        original = gateway.verify_code
        calls = []
        def fault(*args):
            calls.append(args[2])
            if bank_saved:
                original(*args)
            raise RuntimeError("private verification input: " + code)
        with patch.object(gateway, "verify_code", side_effect=fault):
            failed = client.post(path, json=body, headers={"Origin": "http://testserver"})
        assert failed.status_code == 503
        assert code not in failed.text
        current = client.get(f"/api/v1/tasks/{initial['task_id']}").json()["data"]
        assert current["status"] == "needs_attention"
        assert "待核实" in failed.text
        assert current["recovery_reason"] == "VERIFICATION_OUTCOME_UNKNOWN"
        assert current["data"]["operation_id"] == initial["data"]["operation_id"]
        trusted = app.state.api.trusted(app.state.api.identity(client.cookies.get("bank_session")), initial["task_id"])
        fact = gateway.get_verification(trusted, challenge)
        assert fact.consecutive_code_failures == 0
        assert len(MockBankStore(tmp_path / "bank.sqlite").list_ledger("U1", "A1")) == 0
        assert post(client, f"/tasks/{initial['task_id']}/resume").status_code == 409
        changed = client.post(path, json={**body, "request_id": str(uuid4()), "submission_id": str(uuid4())},
                              headers={"Origin": "http://testserver"})
        assert changed.status_code == 409
        recovered = client.post(path, json=body, headers={"Origin": "http://testserver"})
        assert recovered.status_code == 200, recovered.text
        result = recovered.json()["data"]["task"]
        assert result["status"] == "succeeded"
        assert result["data"]["operation"]["receipt"]["amount_fen"] == 50000
        assert len(MockBankStore(tmp_path / "bank.sqlite").list_ledger("U1", "A1")) == 1
        assert len(calls) == 1
        connection = connect(app.state.api.runtime.application.path)
        for table in ("api_requests", "api_events", "tasks", "audit_events", "checkpoint_writes", "checkpoint_blobs"):
            assert all(code not in str(tuple(row)) for row in connection.execute(f"SELECT * FROM {table}")), table
        connection.close()
