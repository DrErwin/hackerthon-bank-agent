"""User-visible discovery/editing paths with real bank, safety and HTTP."""
from fastapi.testclient import TestClient
import pytest

from app.agent_platform.model import TransferProposal
from app.agent_platform.own_bank_queries import register_own_bank_queries
from .test_app import approve, enter, make_app, post, start
from unittest.mock import patch
from uuid import uuid4
from app.agent_platform.test_local_demo import app_for, configuration


def test_choices_are_owned_masked_audited_and_do_not_change_draft(tmp_path):
    app = make_app(tmp_path, proposal=TransferProposal(amount_fen=60000, payer_account_id="A1"))
    with TestClient(app) as client:
        _, task = start(client, "我要转600元")
        url = f"/api/v1/tasks/{task['task_id']}"
        accounts = client.get(url + "/transfer-choices?kind=accounts")
        payees = client.get(url + "/transfer-choices?kind=payees")
        assert accounts.status_code == payees.status_code == 200
        assert accounts.json()["data"]["accounts"][0]["available_balance_fen"] >= 0
        assert payees.json()["data"]["payees"]
        assert all("*" in p["account_masked"] for p in payees.json()["data"]["payees"])
        current = client.get(url).json()["data"]
        assert current["task_revision"] == task["task_revision"]
        assert current["data"] == task["data"]
        assert app.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1") == []
        assert any(e.event_type == "tool.finished" for e in app.state.api.runtime.audit._events("D1", task["task_id"]))
        app.state.api.store.write("UPDATE api_tasks SET user_id='OTHER' WHERE task_id=?", (task["task_id"],))
        assert client.get(url + "/transfer-choices?kind=payees").status_code == 404


def test_choose_payee_and_change_amount_without_losing_payer(tmp_path):
    app = make_app(tmp_path, proposal=TransferProposal(amount_fen=60000, payer_account_id="A1"))
    with TestClient(app) as client:
        _, task = start(client)
        path = f"/tasks/{task['task_id']}"
        contacts = client.get("/api/v1" + path + "/transfer-choices?kind=payees").json()["data"]["payees"]
        payee = next(p for p in contacts if p.get("remark") == "妈妈")
        response = post(client, path + "/draft", task_revision=task["task_revision"],
                        payee_id=payee["payee_id"])
        assert response.status_code == 200, response.text
        selected = response.json()["data"]
        assert selected["status"] == "waiting_approval"
        assert selected["data"]["payer_account_id"] == "A1"
        assert selected["data"]["amount_fen"] == 60000
        assert selected["data"]["payee"]["account_masked"] == payee["account_masked"]
        old = client.get("/api/v1/confirmations/" + selected["interaction"]["record_ref"]).json()["data"]
        revised = post(client, path + "/draft", task_revision=selected["task_revision"], amount_fen=30000).json()["data"]
        assert revised["task_id"] == task["task_id"]
        assert revised["data"]["amount_fen"] == 30000
        assert post(client, "/confirmations/" + old["confirmation_id"] + "/answer",
                    confirmation_version=old["confirmation_version"], choice="approve").status_code == 409
        verifying = approve(client, revised)
        assert post(client, path + "/draft", task_revision=verifying["task_revision"], amount_fen=50000).status_code == 409
        assert app.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1") == []


def test_edit_during_ambiguous_payee_selection_preserves_amount(tmp_path):
    app = make_app(tmp_path, proposal=TransferProposal(payee_hint="张伟", amount_fen=50000, payer_account_id="A1"))
    with TestClient(app) as client:
        _, task = start(client)
        assert len(task["interaction"]["options"]) > 1
        response = post(client, f"/tasks/{task['task_id']}/draft",
                        task_revision=task["task_revision"], payee_id=task["interaction"]["options"][0]["id"])
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "waiting_approval"
        assert response.json()["data"]["data"]["amount_fen"] == 50000


def test_question_reads_contacts_without_consuming_pending_payee(tmp_path):
    app = make_app(tmp_path, proposal=TransferProposal(amount_fen=60000, payer_account_id="A1"),
                   prepare=register_own_bank_queries)
    with TestClient(app) as client:
        thread, task = start(client)
        app.state.api.runtime.harness.planner.proposal = TransferProposal(capability_name="transfer.list_payees")
        assert post(client, f"/threads/{thread}/messages", text="我有哪些收款人啊").status_code == 202
        current = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert current["task_revision"] == task["task_revision"]
        assert current["interaction"] == task["interaction"]
        tasks = client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"]
        query = next(t for t in tasks if t["task_id"] != task["task_id"])
        assert query["data"]["payees"]
        response = post(client, f"/tasks/{query['task_id']}/actions",
                        source_revision=query["task_revision"], action="refresh_query")
        assert response.status_code == 200, response.text
        assert response.json()["data"]["data"]["payees"]
        assert app.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1") == []


def test_expired_session_cannot_read_transfer_choices(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        app.state.api.store.write("UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00'")
        enter(client)
        assert client.get(f"/api/v1/tasks/{task['task_id']}/transfer-choices?kind=accounts").status_code == 409


def test_bill_month_and_row_actions_preserve_scope_and_reject_forged_rows(tmp_path):
    app = app_for(configuration(tmp_path))
    with TestClient(app) as client, patch.object(app.state.api.runtime.harness.planner, "select",
            return_value=TransferProposal(capability_name="bills.summarize")):
        _, source = start(client, "2026年9月所有账户账单")
        path = f"/tasks/{source['task_id']}/actions"
        changed = post(client, path, source_revision=source["task_revision"],
                       action="bill_range", month="2026-08")
        assert changed.status_code == 200, changed.text
        result = changed.json()["data"]
        assert result["data"]["scope"]["start_at"].startswith("2026-08-01")
        assert result["data"]["scope"]["account_ids"] == source["data"]["scope"]["account_ids"]
        details = post(client, path, source_revision=source["task_revision"],
                       action="bill_details").json()["data"]
        row = details["data"]["transactions"][0]
        detail_path = f"/tasks/{details['task_id']}/actions"
        selected = dict(source_revision=details["task_revision"], action="bill_check",
                        transaction_id=row["transaction_id"], account_id=row["account_id"])
        assert post(client, detail_path, **{**selected, "transaction_id": "forged"}).status_code == 400
        checked = post(client, detail_path, **selected)
        assert checked.status_code == 200, checked.text
        assert checked.json()["data"]["status"] in {"succeeded", "waiting_input"}
        assert post(client, path, source_revision=source["task_revision"], action="bill_range",
                    month="2026-13").status_code == 400


def test_refresh_subscription_reads_current_bank_state(tmp_path):
    from .test_card_actions import bank_operations
    app = app_for(configuration(tmp_path))
    with TestClient(app) as client, patch.object(app.state.api.runtime.harness.planner, "select",
            return_value=TransferProposal(capability_name="subscription.list_subscriptions")):
        _, source = start(client, "查看我的订阅")
        row = next(item for item in source["data"]["list_result"]["items"] if item["can_cancel_in_bank"])
        path = f"/tasks/{source['task_id']}/actions"
        waiting = post(client, path, source_revision=source["task_revision"],
                       action="subscription_cancel", subscription_id=row["subscription_id"]).json()["data"]
        verifying = approve(client, waiting)
        challenge = verifying["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        assert post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code).status_code == 200
        before = bank_operations(app.state.api.runtime.gateway._bank)
        refreshed = post(client, path, source_revision=source["task_revision"], action="refresh_query")
        assert refreshed.status_code == 200, refreshed.text
        current = next(item for item in refreshed.json()["data"]["data"]["list_result"]["items"] if item["subscription_id"] == row["subscription_id"])
        assert current["status"] == "cancelled"
        assert bank_operations(app.state.api.runtime.gateway._bank) == before


def test_stale_saved_payee_can_be_corrected_without_losing_other_fields(tmp_path):
    app = make_app(tmp_path, proposal=TransferProposal(amount_fen=50000, payer_account_id="A1"))
    with TestClient(app) as client:
        _, task = start(client)
        path = f"/tasks/{task['task_id']}/draft"
        rejected = post(client, path, task_revision=task["task_revision"], payee_id="missing").json()["data"]
        assert rejected["status"] == "waiting_input"
        assert rejected["error"]["code"] == "PAYEE_MISMATCH"
        assert rejected["data"]["amount_fen"] == 50000
        assert rejected["data"]["payer_account_id"] == "A1"
        contacts = client.get(f"/api/v1/tasks/{task['task_id']}/transfer-choices?kind=payees").json()["data"]["payees"]
        payee = next(item for item in contacts if item["remark"] == "妈妈")
        corrected = post(client, path, task_revision=rejected["task_revision"], payee_id=payee["payee_id"]).json()["data"]
        assert corrected["status"] == "waiting_approval" and corrected["error"] is None
        assert app.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1") == []


def test_manual_payee_mismatch_explains_the_fields_to_correct():
    from .app import problem
    from .service import ApiProblem
    status, payload = problem(ApiProblem(400, "PAYEE_MISMATCH"))
    assert status == 400
    assert "姓名与银行卡号" in payload["error"]["reason"]
