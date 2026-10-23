"""HTTP proof of local composition with controlled model responses, never real GLM."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.api.app import ApiConfig, create_app
from app.api.test_app import approve, enter, post, start
from app.contracts.platform import TrustedContext
from app.modules.bills.anomaly_manifest import ANOMALY_MANIFEST
from app.modules.bills.manifest import REPORT_MANIFEST

from .local_demo import LocalDemoConfig, build_runtime, create_local_app, load_config
from .test_harness import ScriptedChatModel
from .model import TransferProposal


class ConnectorTestModel(ScriptedChatModel):
    model_name: str = "glm-4.7"

    def _get_ls_params(self, **kwargs):
        return {"ls_provider": "openai", "ls_model_name": self.model_name}


def configuration(tmp_path):
    content = json.loads(Path(__file__).with_name("local_demo.example.json").read_text())
    content.update(api_key="local-test-model-key", api_secret="s" * 32,
                   bank_secret="b" * 32, admin_key="local-test-admin",
                   data_directory=str(tmp_path.resolve()), origins=["http://testserver"])
    # Production allows local browser origins; TestClient keeps that same host.
    content["origins"] = ["http://localhost:5173"]
    return LocalDemoConfig.model_validate(content)


def app_for(config, response_mode="transfer"):
    with patch("app.agent_platform.local_demo.ChatOpenAI", return_value=ConnectorTestModel(response_mode=response_mode)):
        runtime = build_runtime(config)
    return create_app(runtime, ApiConfig(
        secret=config.api_secret.get_secret_value().encode(), admin_key="local-test-admin",
        origins=("http://testserver",), demo_round_id=config.demo_round_id,
    ))


SEEDED_OPERATION_PREFIX = "seed:"


def month_start(at, months_back=0):
    """First instant of the month that many months before ``at``."""
    month_index = at.month - 1 - months_back
    year = at.year + month_index // 12
    month = month_index % 12 + 1
    return at.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def submitted_ledger_count(app):
    """Ledger rows this demo run produced; seeded history rows use the storage marker."""
    rows = app.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1")
    return len([row for row in rows if not row["operation_id"].startswith(SEEDED_OPERATION_PREFIX)])


def test_missing_or_invalid_config_never_echoes_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("BANK_LOCAL_CONFIG", raising=False)
    with pytest.raises(ValueError, match="BANK_LOCAL_CONFIG_REQUIRED"):
        create_local_app()
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "do-not-echo-this", "unknown": "secret"}))
    with pytest.raises(ValueError) as error:
        load_config(path)
    assert str(error.value) == "LOCAL_DEMO_CONFIG_INVALID"
    assert "do-not-echo-this" not in str(error.value)


@pytest.mark.parametrize("endpoint", ["https://api.openai.com/v1/", "https://open.bigmodel.cn/api/anthropic", "http://open.bigmodel.cn/api/paas/v4/"])
def test_wrong_provider_or_protocol_is_not_a_runtime_fallback(tmp_path, endpoint):
    config = configuration(tmp_path).model_dump()
    config["base_url"] = endpoint
    with pytest.raises(ValueError):
        LocalDemoConfig.model_validate(config)


def test_explicit_coding_endpoint_is_passed_to_connector(tmp_path):
    content = configuration(tmp_path).model_dump()
    content.update(base_url="https://open.bigmodel.cn/api/coding/paas/v4/", model_name="glm-5.3")
    config = LocalDemoConfig.model_validate(content)
    with patch("app.agent_platform.local_demo.ChatOpenAI",
               return_value=ConnectorTestModel(model_name="glm-5.3")) as connector:
        build_runtime(config)
    assert connector.call_args.kwargs["base_url"] == config.base_url
    assert connector.call_args.kwargs["model"] == "glm-5.3"
    assert connector.call_args.kwargs["max_retries"] == 0


def test_reply_only_and_invalid_model_create_no_task_or_bank_submission(tmp_path):
    config = configuration(tmp_path)
    for mode in ("reply", "none"):
        app = app_for(config, mode)
        with TestClient(app) as client:
            enter(client)
            thread = post(client, "/threads").json()["data"]["thread_id"]
            accepted = post(client, f"/threads/{thread}/messages", text="你好")
            assert accepted.status_code == 202
            assert accepted.json()["data"]["task_id"] is None
            assert client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"] == []
            messages = client.get(f"/api/v1/threads/{thread}/messages").json()["data"]["items"]
            # 失败也要留可读消息（票 28）：模型无输出时，除用户消息外还有一条面向用户的失败说明。
            assert len(messages) == 2
            assert [item["role"] for item in messages] == ["user", "assistant"]
            assert messages[-1]["text"].strip()
            assert all(marker not in messages[-1]["text"] for marker in ("MODEL_PROPOSAL_FAILED", "Traceback", "Error"))
            assert submitted_ledger_count(app) == 0
            if mode == "none":
                assert app.state.api.store.rows("SELECT status FROM api_message_jobs ORDER BY created_at DESC LIMIT 1")[0]["status"] == "error_completed"


@pytest.mark.parametrize("amount", [0, -100])
def test_nonpositive_proposal_publishes_durable_amount_refusal(tmp_path, amount):
    app = app_for(configuration(tmp_path))
    api = app.state.api
    request = str(uuid4())
    with patch.object(api.runtime.harness.planner, "select", return_value=TransferProposal(
        payee_hint="妈妈", amount_fen=amount, payer_account_id="A1")) as planner, \
            patch.object(api.runtime.gateway._bank, "submit_transfer", wraps=api.runtime.gateway._bank.submit_transfer) as submit:
        with TestClient(app) as client:
            enter(client)
            thread = post(client, "/threads").json()["data"]["thread_id"]
            for _ in range(2):
                response = post(client, f"/threads/{thread}/messages", request_id=request,
                                text="从A1给妈妈转0元" if amount == 0 else "从A1给妈妈转-1元")
                assert response.status_code == 202
                assert response.json()["data"]["task_id"] is None
            messages = client.get(f"/api/v1/threads/{thread}/messages").json()["data"]["items"]
            replies = [m for m in messages if m["role"] == "assistant"]
            assert len(replies) == 1
            assert "金额" in replies[0]["text"] and "大于零" in replies[0]["text"]
            assert replies[0]["task_ids"] == []
            events = api.store.events(thread, None)
            assert not any(event["event_type"] == "stream_error" for event in events)
            assert any(event["event_type"] == "message_completed"
                       and event["payload"]["message_id"] == replies[0]["message_id"] for event in events)
            assert client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"] == []
            assert api.store.rows("SELECT status FROM api_message_jobs WHERE request_id=?", (request,))[0]["status"] == "reply_completed"
            assert planner.call_count == 1
            assert submit.call_count == 0
            assert submitted_ledger_count(app) == 0


def test_demo_runtime_seeds_shared_flow_history_for_bills(tmp_path):
    config = configuration(tmp_path)
    app = app_for(config)
    gateway = app.state.api.runtime.gateway
    bank = gateway._bank
    for account_id in ("A1", "A5"):
        rows = bank.store.list_ledger("U1", account_id)
        assert rows and all(row["operation_id"].startswith(SEEDED_OPERATION_PREFIX) for row in rows)
    at = datetime.now(timezone(timedelta(hours=8)))
    user = TrustedContext(
        user_id="U1", session_id="S1", task_id="T1", run_id="R1",
        parent_task_id=None, demo_round_id=config.demo_round_id,
    )
    for account_id in ("A1", "A5"):
        last_month = gateway.list_transactions(user, account_id, month_start(at, 1), month_start(at, 0))
        assert last_month.kind == "ok" and last_month.data.transactions
        assert all(row.counterparty_name and row.summary for row in last_month.data.transactions)
        assert gateway.list_transactions(user, account_id, month_start(at, 0), at).kind == "ok"
    current_month = gateway.list_transactions(user, "A1", month_start(at, 0), at)
    if at.day >= 6:
        assert current_month.data.transactions, "a past-day sample exists from the 6th on"
    restarted = app_for(config)
    assert len(restarted.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1")) == len(
        bank.store.list_ledger("U1", "A1"))


def test_confirm_verify_repeat_and_rebuild_use_one_original_operation(tmp_path):
    config = configuration(tmp_path)
    app = app_for(config)
    with TestClient(app) as client:
        _, task = start(client)
        assert task["interaction"]["kind"] == "confirmation"
        assert submitted_ledger_count(app) == 0
        waiting = approve(client, task)
        assert waiting["interaction"]["kind"] == "verification"
        challenge = waiting["interaction"]["record_ref"]
        code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
        body = {"request_id": str(uuid4()), "submission_id": str(uuid4()), "code": code}
        first = client.post(f"/api/v1/verifications/{challenge}/code", json=body, headers={"Origin": "http://testserver"})
        second = client.post(f"/api/v1/verifications/{challenge}/code", json=body, headers={"Origin": "http://testserver"})
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        done = first.json()["data"]["task"]
        assert done["status"] == "succeeded"
        assert submitted_ledger_count(app) == 1
        original_cookie = client.cookies.get("bank_session")
    restarted = app_for(config)
    with TestClient(restarted) as client:
        client.cookies.set("bank_session", original_cookie)
        recovered = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert recovered["data"]["operation_id"] == done["data"]["operation_id"]
        assert recovered["data"]["operation"]["receipt"] == done["data"]["operation"]["receipt"]
        assert submitted_ledger_count(restarted) == 1


@pytest.mark.parametrize("amount,payee,expected", [(50100, "妈妈", "waiting_approval"), (50200, "妈妈", "failed"), (60100, "妈妈", "needs_attention")])
def test_bound_medium_high_and_missing_facts_never_submit(tmp_path, amount, payee, expected):
    model = ConnectorTestModel()
    original = model._generate

    def generate(self, *args, **kwargs):
        result = original(*args, **kwargs)
        for call in result.generations[0].message.tool_calls:
            if call["name"] == "propose_transfer":
                call["args"].update(amount_fen=amount, payee_hint=payee)
        return result

    with patch.object(ConnectorTestModel, "_generate", generate):
        app = app_for(configuration(tmp_path))
        with TestClient(app) as client:
            _, task = start(client)
            assert task["status"] == expected
            assert submitted_ledger_count(app) == 0
            if amount == 50100:
                waiting = approve(client, task)
                challenge = waiting["interaction"]["record_ref"]
                view = client.get(f"/api/v1/verifications/{challenge}").json()["data"]
                assert set(view["required_methods"]) == {"code", "mock_face"}
                assert submitted_ledger_count(app) == 0
                code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
                coded = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
                assert coded.json()["data"]["task"]["status"] == "waiting_approval"
                assert submitted_ledger_count(app) == 0
                assert post(client, f"/verifications/{challenge}/face/start").status_code == 200
                denied = post(client, f"/admin/verifications/{challenge}/face-result",
                              submission_id=str(uuid4()), demo_round_id="D1", result="passed")
                assert denied.status_code == 403
                with TestClient(app) as admin:
                    entered = admin.post("/api/v1/session/enter", json={"request_id": str(uuid4())},
                                         headers={"Origin": "http://testserver", "X-Demo-Admin-Key": "local-test-admin"})
                    assert entered.json()["data"]["role"] == "admin"
                    answered = post(admin, f"/admin/verifications/{challenge}/face-result",
                                    submission_id=str(uuid4()), demo_round_id="D1", result="passed")
                    assert answered.status_code == 200
                    assert answered.json()["data"]["task"]["status"] == "succeeded"
                    assert submitted_ledger_count(app) == 1


def test_real_bills_module_registered_and_serves_consecutive_stage_one_tasks(tmp_path):
    """v04-platform/05 stage one: the real bills module is registered by the
    deployment factory, the contract stub steps aside, and two consecutive
    tasks get per-task read gates without registration collisions."""
    app = app_for(configuration(tmp_path))
    api = app.state.api
    catalog = [item["name"] for item in api.runtime.harness.registry.public_catalog()]
    assert "transfer.start_transfer" in catalog
    # Issue #190: L01, L02 and L03 are all real capabilities now.
    assert {"bills.summarize", "bills.detect_anomalies",
            "bills.generate_report"} <= set(catalog)
    # The real L02/L03 manifests own their capabilities, i.e. the contract-shaped
    # stub (app.agent_platform.bills_stub.BILLS_MANIFEST) did not provide them.
    assert api.runtime.harness.registry.get("bills.detect_anomalies").manifest is ANOMALY_MANIFEST
    assert api.runtime.harness.registry.get("bills.generate_report").manifest is REPORT_MANIFEST

    with patch.object(api.runtime.harness.planner, "select",
                      return_value=TransferProposal(capability_name="bills.summarize")):
        with TestClient(app) as client:
            enter(client)
            thread = post(client, "/threads").json()["data"]["thread_id"]
            for text in ("查2026年9月所有账户的账单", "再查2026年8月所有账户的账单"):
                accepted = post(client, f"/threads/{thread}/messages", text=text)
                assert accepted.status_code == 202, accepted.text
            task_ids = [item["task_id"] for item in
                        client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"]]
            assert len(task_ids) == 2 and task_ids[0] != task_ids[1]
            for task_id in task_ids:
                task = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
                assert task["module"] == "bills", task
                assert task["status"] == "succeeded", task
                assert task["data"]["scope"]["account_ids"]
                assert task["data"]["transaction_count"] > 0
                assert "契约形状桩" not in task["message"]
    assert submitted_ledger_count(app) == 0


def test_bills_stage_one_waits_for_choices_and_resumes_to_success(tmp_path):
    app = app_for(configuration(tmp_path))
    api = app.state.api
    with patch.object(api.runtime.harness.planner, "select",
                      return_value=TransferProposal(capability_name="bills.summarize")):
        with TestClient(app) as client:
            enter(client)
            thread = post(client, "/threads").json()["data"]["thread_id"]
            accepted = post(client, f"/threads/{thread}/messages", text="查一下账单")
            assert accepted.status_code == 202, accepted.text
            items = client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"]
            assert len(items) == 1
            task_id = items[0]["task_id"]
            task = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
            assert task["module"] == "bills" and task["status"] == "waiting_input"
            interaction = task["interaction"]
            month = next(o for o in interaction["options"] if o["label"] == "上月")
            chosen = post(client, f"/tasks/{task_id}/inputs",
                          interaction_id=interaction["interaction_id"], selected_option_id=month["id"])
            assert chosen.status_code == 200, chosen.text
            task = chosen.json()["data"]
            interaction = task["interaction"]
            accounts = next(o for o in interaction["options"] if o["label"] == "所有本人账户")
            final = post(client, f"/tasks/{task_id}/inputs",
                         interaction_id=interaction["interaction_id"], selected_option_id=accounts["id"])
            task = final.json()["data"]
            assert task["status"] == "succeeded", task
            assert task["data"]["transaction_count"] > 0
    assert submitted_ledger_count(app) == 0
