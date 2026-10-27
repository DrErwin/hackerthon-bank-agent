"""API22: existing real demo policy retains the persisted parent during HTTP actions."""

from unittest.mock import patch
from uuid import uuid4
from dataclasses import replace

from fastapi.testclient import TestClient
import pytest

from app.agent_platform.model import TransferProposal
from app.agent_platform.test_local_demo import app_for, configuration
from app.contracts.bank import SavedPayee
from app.contracts.platform import StartTransferInput
from app.storage.database import connect

from .test_app import approve, post, start
from .service import ApiProblem


def test_child_confirmation_and_code_keep_parent_and_one_original_bank_effect(tmp_path):
    app = app_for(configuration(tmp_path))
    with TestClient(app) as client:
        api = app.state.api
        runtime = api.runtime
        with patch.object(runtime.harness.planner, "select", return_value=TransferProposal(
                capability_name="cross.start_task")):
            _, parent = start(client, "给妈妈转500元")
        identity = api.identity(client.cookies.get("bank_session"))
        parent_context = api.trusted(identity, parent["task_id"])
        request_id = uuid4()
        child = runtime.harness.dispatch_child(parent_context, "transfer.start_transfer", request_id,
            StartTransferInput(request_id=request_id, intent_text="内部计划转账步骤",
                payer_account_id="A1", payee=SavedPayee(kind="saved", payee_id="A2"), amount_fen=50000),
            step_id="transfer:1", plan_revision=1)
        published = client.get(f"/api/v1/tasks/{parent['task_id']}/children")
        assert published.status_code == 200, published.text
        task = next(item for item in published.json()["data"] if item["task_id"] == child.task_id)
        operation = task["data"]["operation_id"]
        waiting = approve(client, task)
        assert waiting["status"] == "waiting_approval", waiting
        assert waiting["interaction"]["kind"] == "verification"
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        result = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
        assert result.status_code == 200, result.text
        completed = result.json()["data"]["task"]
        assert completed["status"] == "succeeded", completed
        assert completed["data"]["operation_id"] == operation
        assert api.trusted(identity, child.task_id).parent_task_id == parent["task_id"]
        assert api.trusted(identity, parent["task_id"]).parent_task_id is None
        with patch.object(runtime.application, "parent_of_task", wraps=runtime.application.parent_of_task) as lookup:
            for change, expected in [({"user_id": "U2"}, "NOT_FOUND"),
                    ({"demo_round_id": "D2"}, "NOT_FOUND"),
                    ({"session_id": "FOREIGN"}, "SESSION_RECONFIRMATION_REQUIRED")]:
                with pytest.raises(ApiProblem) as error:
                    api.trusted(replace(identity, **change), child.task_id)
                assert error.value.code == expected
            assert lookup.call_count == 0  # Scope/session checks precede source lookup.
        repeated = client.get(f"/api/v1/tasks/{child.task_id}")
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["data"]["data"]["operation_id"] == operation
        with connect(runtime.bank.store.path) as connection:
            rows = connection.execute("SELECT operation_id FROM bank_operations WHERE action_name='bank.submit_transfer'").fetchall()
        assert [row[0] for row in rows] == [operation]
