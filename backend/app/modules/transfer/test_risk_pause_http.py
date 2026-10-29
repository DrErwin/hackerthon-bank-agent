"""Public HTTP integration with real Harness/gate/bank; planner and risk are test substitutes."""

import pytest
from fastapi.testclient import TestClient

from app.api.test_app import approve, make_app, post, start
from app.contracts.common import RiskLevel
from app.security.gate import RiskFactsUnavailable


def install_coverage_substitute(runtime):
    def assess(context, action, declaration):
        if action.action_name != "bank.submit_transfer":
            return RiskLevel.LOW
        parameters = runtime.snapshots.resolve(context, action)
        if parameters["amount_fen"] == 60_000:
            raise RiskFactsUnavailable("test coverage missing", rule_id="risk-signal-coverage-required",
                                       policy_version="test-coverage-only")
        return RiskLevel.MEDIUM

    runtime.assess_risk = assess


@pytest.mark.parametrize("finish", ["cancel", "revise"])
def test_public_draft_recovery_preserves_gates_and_bank_before_effect(tmp_path, finish):
    app = make_app(tmp_path, prepare=install_coverage_substitute)
    with TestClient(app) as client:
        thread, original = start(client)
        task_id = original["task_id"]
        old_ref = original["interaction"]["record_ref"]
        old_confirmation = client.get(f"/api/v1/confirmations/{old_ref}").json()["data"]
        paused_response = post(client, f"/tasks/{task_id}/draft",
                               task_revision=original["task_revision"], amount_fen=60_000)
        assert paused_response.status_code == 200, paused_response.text
        paused = paused_response.json()["data"]
        assert paused["status"] == "waiting_input"
        assert not paused["recovery_required"]
        assert paused["allowed_actions"] == ["provide_input", "cancel"]
        assert paused["data"]["amount_fen"] == 60_000
        assert paused["data"]["payee"] == original["data"]["payee"]
        assert paused["data"]["operation_id"] != original["data"]["operation_id"]
        rechecked_response = post(client, f"/tasks/{task_id}/inputs",
                                  interaction_id=paused["interaction"]["interaction_id"],
                                  selected_option_id="resume")
        assert rechecked_response.status_code == 200, rechecked_response.text
        rechecked = rechecked_response.json()["data"]
        assert rechecked["status"] == "waiting_input"
        assert rechecked["data"]["operation_id"] == paused["data"]["operation_id"]
        stale = post(client, f"/confirmations/{old_ref}/answer",
                     confirmation_version=old_confirmation["confirmation_version"], choice="approve")
        assert stale.status_code == 409
        bank = app.state.api.runtime.bank
        assert bank.store.list_ledger("U1", "A1") == []
        if finish == "revise":
            revised_response = post(client, f"/tasks/{task_id}/draft",
                                    task_revision=rechecked["task_revision"], amount_fen=50_000)
            assert revised_response.status_code == 200, revised_response.text
            revised = revised_response.json()["data"]
            assert revised["task_id"] == task_id and revised["status"] == "waiting_approval"
            assert revised["data"]["amount_fen"] == 50_000
            assert revised["data"]["payee"] == original["data"]["payee"]
            assert revised["data"]["operation_id"] not in {
                original["data"]["operation_id"], paused["data"]["operation_id"],
            }
            verification = approve(client, revised)
            assert verification["interaction"]["kind"] == "verification"
            challenge = client.get("/api/v1/verifications/" + verification["interaction"]["record_ref"]).json()["data"]
            assert challenge["required_methods"] == ["code", "mock_face"]
            assert bank.store.list_ledger("U1", "A1") == []
        cancelled_response = post(client, f"/tasks/{task_id}/cancel")
        assert cancelled_response.status_code == 200, cancelled_response.text
        assert cancelled_response.json()["data"]["status"] == "cancelled"
        resumed = post(client, f"/tasks/{task_id}/resume")
        assert resumed.status_code == 200
        assert resumed.json()["data"]["status"] == "cancelled"
        assert bank.store.list_ledger("U1", "A1") == []
        tasks = client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"]
        assert len(tasks) == 1 and tasks[0]["task_id"] == task_id
