"""Message acceptance binds a same-chat bill source before model work."""
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.agent_platform.model import ReplyOnly, TransferProposal
from app.agent_platform.test_local_demo import app_for, configuration
from .test_app import post, start


def test_parent_is_persisted_and_never_taken_from_another_chat(tmp_path):
    app = app_for(configuration(tmp_path))
    harness = app.state.api.runtime.harness
    with TestClient(app) as client, patch.object(harness.planner, "select", return_value=TransferProposal(
            capability_name="bills.summarize")):
        thread, bill = start(client, "2026年9月所有账户账单")
        assert bill["status"] == "succeeded"
        with patch.object(harness.planner, "select", return_value=TransferProposal(
                capability_name="transfer.list_accounts")):
            post(client, f"/threads/{thread}/messages", text="查询我的账户")
        seen = []
        def reply(text, trusted, *args, **kwargs):
            seen.append(trusted.parent_task_id)
            return ReplyOnly(message="请查看账单。")
        with patch.object(harness.planner, "select", side_effect=reply):
            request_id = str(uuid4())
            assert post(client, f"/threads/{thread}/messages", text="看看餐饮明细", request_id=request_id).status_code == 202
            assert seen == [bill["task_id"]]
            job = app.state.api.store.rows("SELECT * FROM api_message_jobs WHERE request_id=?", (request_id,))[0]
            assert job["parent_task_id"] == bill["task_id"]
            other = post(client, "/threads").json()["data"]["thread_id"]
            post(client, f"/threads/{other}/messages", text="看看餐饮明细")
            assert seen[-1] is None
            post(client, f"/threads/{thread}/messages", text="看看餐饮明细", request_id=request_id)
            assert len(seen) == 2


def test_old_session_or_changed_owner_cannot_supply_parent(tmp_path):
    app = app_for(configuration(tmp_path))
    harness = app.state.api.runtime.harness
    with TestClient(app) as client, patch.object(harness.planner, "select", return_value=TransferProposal(
            capability_name="bills.summarize")):
        thread, bill = start(client, "2026年9月所有账户账单")
        seen = []
        def reply(text, trusted, *args, **kwargs):
            seen.append(trusted.parent_task_id)
            return ReplyOnly(message="请选择范围。")
        with patch.object(harness.planner, "select", side_effect=reply):
            app.state.api.store.write("UPDATE api_tasks SET session_id='old' WHERE task_id=?", (bill["task_id"],))
            post(client, f"/threads/{thread}/messages", text="看看餐饮明细")
            assert seen[-1] is None
            app.state.api.store.write("UPDATE api_tasks SET user_id='OTHER' WHERE task_id=?", (bill["task_id"],))
            post(client, f"/threads/{thread}/messages", text="看看餐饮明细")
            assert seen[-1] is None
