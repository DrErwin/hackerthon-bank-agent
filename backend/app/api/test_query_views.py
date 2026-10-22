"""The server-owned capability selects its payload type, not a client hint."""

import pytest
from fastapi.testclient import TestClient

from .test_app import make_app, start


@pytest.mark.parametrize("name,data", [("list_accounts", {"accounts": []}), ("list_payees", {"payees": []})])
def test_query_view_reads_stored_capability_and_preserves_owner_check(tmp_path, name, data):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, view = start(client)
        store = app.state.api.runtime.application
        task = store.get_task("U1", "D1", view["task_id"])
        snapshot = task.snapshot
        snapshot["capability_name"] = "transfer." + name
        snapshot["result"]["data"] = data
        store.update_task("U1", "D1", task.task_id, task.revision, task.run_id, task.status, task.checkpoint_id, snapshot)
        for _ in range(2):
            result = client.get(f"/api/v1/tasks/{task.task_id}")
            assert result.status_code == 200
            assert result.json()["data"]["data"] == data
        app.state.api.store.write("UPDATE api_tasks SET user_id='OTHER' WHERE task_id=?", (task.task_id,))
        assert client.get(f"/api/v1/tasks/{task.task_id}").status_code == 404


def test_default_transfer_type_is_not_loosened():
    from .service import task_view_model
    from app.contracts.tasks import TransferTaskView
    assert task_view_model("transfer") is TransferTaskView
    assert task_view_model("transfer", "transfer.unknown") is TransferTaskView
