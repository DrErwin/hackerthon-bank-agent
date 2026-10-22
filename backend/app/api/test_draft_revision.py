"""HTTP regression for editing an unsubmitted transfer, with real safety and bank."""

from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.agent_platform.model import TransferProposal
from .test_app import approve, make_app, post, start


def test_edit_preserves_task_and_replaces_confirmation_without_cancelling(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        thread, task = start(client)
        ref = task["interaction"]["record_ref"]
        old = client.get(f"/api/v1/confirmations/{ref}").json()["data"]
        body = dict(request_id=str(uuid4()), task_revision=task["task_revision"],
                    amount_fen=60000)
        endpoint = f"/tasks/{task['task_id']}/draft"
        first = post(client, endpoint, **body)
        assert first.status_code == 200, first.text
        changed = first.json()["data"]
        assert changed["task_id"] == task["task_id"]
        assert changed["status"] == "waiting_approval"
        assert changed["data"]["amount_fen"] == 60000
        assert changed["data"]["payer_account_id"] == task["data"]["payer_account_id"]
        assert changed["data"]["payee"] == task["data"]["payee"]
        assert changed["data"]["operation_id"] != task["data"]["operation_id"]
        assert post(client, endpoint, **body).json() == first.json()
        stale = post(client, f"/confirmations/{ref}/answer",
                     confirmation_version=old["confirmation_version"], choice="approve")
        assert stale.status_code == 409
        conflict = post(client, endpoint, task_revision=task["task_revision"], amount_fen=70000)
        assert conflict.status_code == 409
        waiting = approve(client, changed)
        assert waiting["interaction"]["kind"] == "verification"
        # A verification-in-progress is outside the editable draft boundary.
        assert post(client, endpoint, task_revision=waiting["task_revision"],
                    amount_fen=70000).status_code == 409
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        result = post(client, f"/verifications/{challenge}/code",
                      submission_id=str(uuid4()), code=code)
        completed = result.json()["data"]["task"]
        assert completed["status"] == "succeeded"
        assert completed["data"]["operation"]["receipt"]["amount_fen"] == 60000
        assert post(client, endpoint, task_revision=completed["task_revision"],
                    amount_fen=70000).status_code == 409
        tasks = client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"]
        assert len(tasks) == 1
        assert len(app.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1")) == 1


@pytest.mark.parametrize("fields", [
    {}, {"amount_fen": 0}, {"amount_fen": -100}, {"amount_fen": True},
    {"amount_fen": 60000.5}, {"payer_account_id": " "}, {"payee_hint": "验证码123456"},
    {"user_id": "U2"}, {"approve": True},
])
def test_invalid_draft_is_rejected_without_changing_task(tmp_path, fields):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        response = post(client, f"/tasks/{task['task_id']}/draft",
                        task_revision=task["task_revision"], **fields)
        assert response.status_code == 400, response.text
        actual = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert actual["task_revision"] == task["task_revision"]
        assert actual["data"] == task["data"]


def test_input_can_supply_account_text_and_cannot_answer_stale_step(tmp_path):
    app = make_app(tmp_path, proposal=TransferProposal(payee_hint="妈妈", amount_fen=None))
    with TestClient(app) as client:
        _, task = start(client, "给妈妈转账")
        amount_step = task["interaction"]["interaction_id"]
        response = post(client, f"/tasks/{task['task_id']}/inputs",
                        interaction_id=amount_step, text="500元")
        assert response.status_code == 200
        account_step = response.json()["data"]["interaction"]["interaction_id"]
        response = post(client, f"/tasks/{task['task_id']}/inputs",
                        interaction_id=account_step, text="A1")
        assert response.status_code == 200, response.text
        assert response.json()["data"]["interaction"]["kind"] == "confirmation"
        assert post(client, f"/tasks/{task['task_id']}/inputs",
                    interaction_id=amount_step, text="600").status_code == 409


def test_draft_rejects_other_owner_and_changed_session(tmp_path):
    from datetime import datetime, timedelta, timezone
    from .test_app import enter

    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        endpoint = f"/tasks/{task['task_id']}/draft"
        api = app.state.api
        original_user = api.config.demo_user_id
        # An independently signed-in user cannot address this task.
        other = make_app(tmp_path, user="U2")
        with TestClient(other) as outsider:
            enter(outsider)
            assert post(outsider, endpoint, task_revision=task["task_revision"],
                        amount_fen=60000).status_code == 404
        assert original_user == "U1"
        api.store.write("UPDATE sessions SET expires_at=?",
                        ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),))
        enter(client)
        assert post(client, endpoint, task_revision=task["task_revision"],
                    amount_fen=60000).status_code == 409


def test_draft_does_not_claim_to_edit_a_payee_selection(tmp_path):
    app = make_app(tmp_path, proposal=TransferProposal(payee_hint="张伟", amount_fen=50000, payer_account_id="A1"))
    with TestClient(app) as client:
        _, task = start(client, "给张伟转500元")
        assert task["status"] == "waiting_input"
        assert len(task["interaction"]["options"]) > 1
        response = post(client, f"/tasks/{task['task_id']}/draft",
                        task_revision=task["task_revision"], amount_fen=60000)
        assert response.status_code == 409
        actual = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert actual["task_revision"] == task["task_revision"]
