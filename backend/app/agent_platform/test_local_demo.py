"""HTTP proof of local composition with controlled model responses, never real GLM."""

import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.api.app import ApiConfig, create_app
from app.api.test_app import approve, enter, post, start

from .local_demo import LocalDemoConfig, build_runtime, create_local_app, load_config
from .test_harness import ScriptedChatModel


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


def ledger_count(app):
    return len(app.state.api.runtime.gateway._bank.store.list_ledger("U1", "A1"))


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
            assert len(messages) == (2 if mode == "reply" else 1)
            assert ledger_count(app) == 0
            if mode == "none":
                assert app.state.api.store.rows("SELECT status FROM api_message_jobs ORDER BY created_at DESC LIMIT 1")[0]["status"] == "error_completed"


def test_confirm_verify_repeat_and_rebuild_use_one_original_operation(tmp_path):
    config = configuration(tmp_path)
    app = app_for(config)
    with TestClient(app) as client:
        _, task = start(client)
        assert task["interaction"]["kind"] == "confirmation"
        assert ledger_count(app) == 0
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
        assert ledger_count(app) == 1
        original_cookie = client.cookies.get("bank_session")
    restarted = app_for(config)
    with TestClient(restarted) as client:
        client.cookies.set("bank_session", original_cookie)
        recovered = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert recovered["data"]["operation_id"] == done["data"]["operation_id"]
        assert recovered["data"]["operation"]["receipt"] == done["data"]["operation"]["receipt"]
        assert ledger_count(restarted) == 1


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
            assert ledger_count(app) == 0
            if amount == 50100:
                waiting = approve(client, task)
                challenge = waiting["interaction"]["record_ref"]
                view = client.get(f"/api/v1/verifications/{challenge}").json()["data"]
                assert set(view["required_methods"]) == {"code", "mock_face"}
                assert ledger_count(app) == 0
                code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
                coded = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
                assert coded.json()["data"]["task"]["status"] == "waiting_approval"
                assert ledger_count(app) == 0
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
                    assert ledger_count(app) == 1
