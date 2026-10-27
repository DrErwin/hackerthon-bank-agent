"""Platform21: real local composition and bank; external model is scripted only."""

import json
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
import pytest

from app.api.app import ApiConfig, create_app
from app.api.test_app import approve, enter, post, start
from app.contracts.common import Phase, RiskLevel
from app.contracts.platform import TrustedContext
from app.contracts.security import ActionDescriptor, ExecutionSecurityContext
from app.modules.transfer.manifest import PRIVATE_TOOLS
from app.security.gate import RiskFactsUnavailable
from app.storage.database import connect, transaction
from .local_demo import LocalDemoConfig, build_runtime, create_local_app, load_config
from .risk_conversation import RiskConversation
from .risk_inputs import TrustedRiskInputs
from .test_local_demo import ConnectorTestModel, app_for, configuration


PROFILE = "p01-marked-demo-v1"
REQUEST = (
    "这月养老金5000元到账了，帮我安排一下：留1500元生活费，"
    "2500元转自己的储蓄账户，1000元给家人，顺便看看没用的扣费。"
)


def write_config(tmp_path):
    content = configuration(tmp_path / "data").model_dump(mode="json")
    # Test-only credentials, never a copy of the operator's private config.
    content.update(api_key="scripted-model-test", api_secret="s" * 32,
                   bank_secret="b" * 32, admin_key="local-test-admin")
    path = tmp_path / "config.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def test_explicit_process_flag_enables_only_the_validated_profile_without_editing_file(tmp_path, monkeypatch):
    path = write_config(tmp_path)
    original = path.read_bytes()
    monkeypatch.setenv("BANK_PENSION_DEMO_PROFILE", PROFILE)
    loaded = load_config(path)
    assert loaded.pension_demo_profile == PROFILE
    assert path.read_bytes() == original


class PensionChatModel(ConnectorTestModel):
    """Fixed external-model output; actual planner/tool/schema and gates still run."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if any(isinstance(message, ToolMessage) for message in messages):
            reply = AIMessage(content="已记录联动候选。")
        else:
            reply = AIMessage(content="", tool_calls=[{
                "name": "propose_transfer", "args": {"capability_name": "cross.start_task"},
                "id": "pension-plan", "type": "tool_call",
            }])
        return ChatResult(generations=[ChatGeneration(message=reply)])


def pension_app(config):
    with patch("app.agent_platform.local_demo.ChatOpenAI", return_value=PensionChatModel()):
        runtime = build_runtime(config)
    return create_app(runtime, ApiConfig(
        secret=config.api_secret.get_secret_value().encode(), admin_key="local-test-admin",
        origins=("http://testserver",), demo_round_id=config.demo_round_id,
    ))


def seed_fresh_p01(app):
    """Only prepare this test's new bank; never touch an existing/shared round."""
    with transaction(app.state.api.runtime.bank.store.path) as connection:
        connection.execute("UPDATE accounts SET book_balance_fen=500000 WHERE account_id='A1'")


def choose(client, task, label):
    options = [item for item in task["interaction"]["options"] if label in item["label"]]
    assert len(options) == 1, [(item["label"]) for item in task["interaction"]["options"]]
    response = post(client, f"/tasks/{task['task_id']}/inputs",
                    interaction_id=task["interaction"]["interaction_id"],
                    selected_option_id=options[0]["id"])
    assert response.status_code == 200, response.text
    return response.json()["data"]


def text_input(client, task, text):
    response = post(client, f"/tasks/{task['task_id']}/inputs",
                    interaction_id=task["interaction"]["interaction_id"], text=text)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def plan_to_adoption(client, task, *, first_amount="2500元", first_destination="本人·储蓄账户"):
    for label in ("安排本月养老金", "主账户", "直接安排资金", "当前可用余额"):
        task = choose(client, task, label)
    task = text_input(client, task, "1500元")
    task = choose(client, task, "算进留存")
    task = choose(client, task, first_destination)
    task = text_input(client, task, first_amount)
    task = choose(client, task, "家庭")
    task = text_input(client, task, "1000元")
    task = choose(client, task, "去向已选好")
    return task


def transfer_children(client, parent_id):
    response = client.get(f"/api/v1/tasks/{parent_id}/children")
    assert response.status_code == 200, response.text
    return [item for item in response.json()["data"]
            if item["module"] == "transfer" and (item.get("data") or {}).get("operation_id")]


def bank_writes(app):
    with connect(app.state.api.runtime.bank.store.path) as connection:
        return [dict(row) for row in connection.execute(
            "SELECT operation_id,action_name,status FROM bank_operations ORDER BY rowid")]


def test_real_new_parent_and_child_reach_medium_confirmation_only_when_opted_in(tmp_path):
    config = configuration(tmp_path).model_copy(update={"pension_demo_profile": PROFILE})
    app = pension_app(config)
    seed_fresh_p01(app)
    try:
        with TestClient(app) as client:
            _, menu = start(client, REQUEST)
            ready = plan_to_adoption(client, menu)
            choose(client, ready, "采用并开始办理")
            children = transfer_children(client, menu["task_id"])
            assert len(children) == 1
            assert children[0]["status"] == "waiting_approval", children[0]
            assert children[0]["interaction"]["kind"] == "confirmation"
            source, context, action, declaration = resolved_inputs(app, menu["task_id"], children[0])
            assert source.request_source_task_id == menu["task_id"]
            assert source.request_capture_version == RiskConversation.CAPTURE_VERSION
            assert source.request_text == REQUEST + "\n1500元\n2500元\n1000元"
            assert app.state.api.runtime.assess_risk(context, action, declaration).risk_level == RiskLevel.MEDIUM
            assert bank_writes(app) == []
    finally:
        app.state.api.runtime.close()


def test_unidentified_ordinary_text_invalidates_capture_without_losing_history_or_task_progress(tmp_path):
    config = configuration(tmp_path).model_copy(update={"pension_demo_profile": PROFILE})
    app = pension_app(config)
    seed_fresh_p01(app)
    runtime = app.state.api.runtime
    try:
        with TestClient(app) as client:
            _, menu = start(client, REQUEST)
            menu = text_input(client, menu, "1500元")
            current = runtime.application.get_task("U1", "D1", menu["task_id"])
            assert current.snapshot["risk_capture_version"] == RiskConversation.CAPTURE_VERSION
            assert runtime.harness.risk_conversation.texts(current) == ["1500元"]
            who = TrustedContext(
                user_id=current.user_id, session_id=current.session_id,
                demo_round_id=current.demo_round_id, task_id=current.task_id,
                run_id=current.run_id, parent_task_id=None,
            )
            result = runtime.harness.resume(who, {"text": "请再列一下可退订项目"})
            after = runtime.application.get_task("U1", "D1", current.task_id)
            assert after.snapshot.get("risk_capture_version") is None
            assert after.revision > current.revision
            assert result.status.value == "waiting_input"
            assert runtime.harness.risk_conversation.texts(after) == ["1500元"]
            ready = plan_to_adoption(client, result.model_dump(mode="json"))
            choose(client, ready, "采用并开始办理")
            children = transfer_children(client, current.task_id)
            assert len(children) == 1 and children[0]["status"] == "needs_attention"
            assert bank_writes(app) == []
    finally:
        runtime.close()


def resolved_inputs(app, parent_id, child):
    runtime = app.state.api.runtime
    task = runtime.application.get_task("U1", "D1", child["task_id"])
    context = ExecutionSecurityContext(
        user_id=task.user_id, session_id=task.session_id, demo_round_id=task.demo_round_id,
        task_id=task.task_id, run_id=task.run_id, source_task_id=parent_id,
        operation_id=UUID(child["data"]["operation_id"]), action_revision=1,
        confirmation_id=None, confirmation_version=None, verification_ids=[],
        release_authorization_id=None,
    )
    confirmation = runtime.confirmations.get(context, child["interaction"]["record_ref"])
    context = context.model_copy(update={"action_revision": confirmation.action_revision})
    action = ActionDescriptor(action_name=confirmation.action_name,
                              parameters_ref=confirmation.parameters_ref,
                              resource_refs=[], phase=Phase.ADMISSION)
    declaration = next(item for item in PRIVATE_TOOLS if item.name == "bank.submit_transfer")
    source = TrustedRiskInputs(runtime.application, runtime.snapshots, runtime.gateway).resolve(
        context, action, declaration)
    return source, context, action, declaration


@pytest.mark.parametrize("flag", ["", "false", "p01-marked-demo-v2", "p01-marked-demo-v1 secret-value"])
def test_bad_process_profile_uses_existing_sanitized_config_error(tmp_path, monkeypatch, flag):
    path = write_config(tmp_path)
    original = path.read_bytes()
    monkeypatch.setenv("BANK_PENSION_DEMO_PROFILE", flag)
    with pytest.raises(ValueError) as caught:
        load_config(path)
    assert str(caught.value) == "LOCAL_DEMO_CONFIG_INVALID"
    assert "secret-value" not in str(caught.value)
    assert path.read_bytes() == original


def test_old_config_defaults_none_and_explicit_file_literal_is_validated(tmp_path, monkeypatch):
    monkeypatch.delenv("BANK_PENSION_DEMO_PROFILE", raising=False)
    path = write_config(tmp_path)
    content = json.loads(path.read_text(encoding="utf-8"))
    content.pop("pension_demo_profile")
    path.write_text(json.dumps(content), encoding="utf-8")
    assert load_config(path).pension_demo_profile is None
    content["pension_demo_profile"] = PROFILE
    path.write_text(json.dumps(content), encoding="utf-8")
    assert load_config(path).pension_demo_profile == PROFILE
    content["pension_demo_profile"] = "unapproved"
    path.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(ValueError, match="^LOCAL_DEMO_CONFIG_INVALID$"):
        load_config(path)


def test_create_local_app_consumes_the_same_process_flag_and_sanitizes_bad_values(tmp_path, monkeypatch):
    path = write_config(tmp_path)
    monkeypatch.setenv("BANK_LOCAL_CONFIG", str(path))
    monkeypatch.setenv("BANK_PENSION_DEMO_PROFILE", "invalid-secret-value")
    with pytest.raises(ValueError, match="^LOCAL_DEMO_CONFIG_INVALID$"):
        create_local_app()
    monkeypatch.setenv("BANK_PENSION_DEMO_PROFILE", PROFILE)
    with patch("app.agent_platform.local_demo.ChatOpenAI", return_value=PensionChatModel()):
        app = create_local_app()
    try:
        assert app.state.api.runtime.harness is not None
        assert load_config(path).pension_demo_profile == PROFILE
    finally:
        app.state.api.runtime.close()


def edit_capture_for_test(runtime, task_id, value):
    """Explicit legacy/corrupt metadata fixture in this test's isolated application."""
    task = runtime.application.get_task("U1", "D1", task_id)
    snapshot = dict(task.snapshot)
    if value is None:
        snapshot.pop("risk_capture_version", None)
    else:
        snapshot["risk_capture_version"] = value
    return runtime.application.update_task("U1", "D1", task_id, task.revision,
                                         task.run_id, task.status, task.checkpoint_id, snapshot)


@pytest.mark.parametrize("source", ["parent", "child"])
@pytest.mark.parametrize("value", [None, "future-capture-version"])
def test_missing_or_other_parent_or_child_capture_keeps_actual_gate_unknown(tmp_path, source, value):
    app = pension_app(configuration(tmp_path).model_copy(update={"pension_demo_profile": PROFILE}))
    seed_fresh_p01(app)
    try:
        with TestClient(app) as client:
            _, menu = start(client, REQUEST)
            ready = plan_to_adoption(client, menu)
            choose(client, ready, "采用并开始办理")
            child = transfer_children(client, menu["task_id"])[0]
            before, context, action, declaration = resolved_inputs(app, menu["task_id"], child)
            runtime = app.state.api.runtime
            edit_capture_for_test(runtime, menu["task_id"] if source == "parent" else child["task_id"], value)
            after, _, _, _ = resolved_inputs(app, menu["task_id"], child)
            assert after.request_capture_version is None
            assert after.request_source_task_id == before.request_source_task_id
            assert after.request_text == before.request_text
            assert after.evidence_ref != before.evidence_ref
            with pytest.raises(RiskFactsUnavailable) as caught:
                runtime.assess_risk(context, action, declaration)
            assert caught.value.rule_id == "risk-signal-coverage-required"
            assert approve(client, child)["status"] == "needs_attention"
            assert bank_writes(app) == []
    finally:
        app.state.api.runtime.close()


def test_default_remains_unknown_and_legacy_parent_does_not_gain_coverage_after_opt_in_restart(tmp_path):
    config = configuration(tmp_path)
    app = pension_app(config)
    seed_fresh_p01(app)
    try:
        with TestClient(app) as client:
            _, menu = start(client, REQUEST)
            ready = plan_to_adoption(client, menu)
            choose(client, ready, "采用并开始办理")
            child = transfer_children(client, menu["task_id"])[0]
            assert child["status"] == "needs_attention"
            edit_capture_for_test(app.state.api.runtime, menu["task_id"], None)
            cookie = client.cookies.get("bank_session")
            version = app.state.api.runtime.harness.planner.config_version
            original_operation = child["data"]["operation_id"]
            assert bank_writes(app) == []
    finally:
        app.state.api.runtime.close()
    restarted = pension_app(config.model_copy(update={"pension_demo_profile": PROFILE}))
    try:
        assert restarted.state.api.runtime.harness.planner.config_version == version
        with TestClient(restarted) as client:
            client.cookies.set("bank_session", cookie)
            response = post(client, f"/tasks/{child['task_id']}/resume")
            assert response.status_code == 200, response.text
            task = response.json()["data"]
            assert task["status"] == "needs_attention"
            assert task["data"]["operation_id"] == original_operation
            source = restarted.state.api.runtime.application.get_task("U1", "D1", menu["task_id"])
            assert "risk_capture_version" not in source.snapshot
            assert bank_writes(restarted) == []
    finally:
        restarted.state.api.runtime.close()


@pytest.mark.parametrize("extra,first_destination,expected", [
    ("我还要听别人安排", "本人·储蓄账户", "needs_attention"),
    ("不要告诉家人", "本人·储蓄账户", "failed"),
    ("", "妈妈", "needs_attention"),
])
def test_actual_unknown_danger_or_other_payee_never_submits(tmp_path, extra, first_destination, expected):
    app = pension_app(configuration(tmp_path).model_copy(update={"pension_demo_profile": PROFILE}))
    seed_fresh_p01(app)
    try:
        with TestClient(app) as client:
            _, menu = start(client, REQUEST)
            ready = plan_to_adoption(client, menu, first_destination=first_destination)
            if extra:
                ready = text_input(client, ready, extra)
            choose(client, ready, "采用并开始办理")
            child = transfer_children(client, menu["task_id"])[0]
            assert child["status"] == expected
            assert bank_writes(app) == []
    finally:
        app.state.api.runtime.close()


def enter_admin(admin):
    response = admin.post("/api/v1/session/enter", json={"request_id": str(uuid4())},
                          headers={"Origin": "http://testserver", "X-Demo-Admin-Key": "local-test-admin"})
    assert response.status_code == 200 and response.json()["data"]["role"] == "admin"


def verify_medium(client, admin, app, child, before):
    assert child["interaction"]["kind"] == "confirmation"
    assert len(bank_writes(app)) == before
    waiting = approve(client, child)
    assert waiting["status"] == "waiting_approval"
    assert waiting["interaction"]["kind"] == "verification"
    ref = waiting["interaction"]["record_ref"]
    view = client.get(f"/api/v1/verifications/{ref}").json()["data"]
    assert set(view["required_methods"]) == {"code", "mock_face"}
    assert view["summary"]["operation_id"] == child["data"]["operation_id"]
    assert view["summary"]["amount_fen"] == child["data"]["amount_fen"]
    code = client.get(f"/api/v1/verifications/{ref}/demo-code").json()["data"]["code"]
    coded = post(client, f"/verifications/{ref}/code", submission_id=str(uuid4()), code=code)
    assert coded.status_code == 200, coded.text
    assert coded.json()["data"]["task"]["status"] == "waiting_approval"
    assert len(bank_writes(app)) == before
    assert post(client, f"/verifications/{ref}/face/start").status_code == 200
    body = {"request_id": str(uuid4()), "submission_id": str(uuid4()),
            "demo_round_id": "D1", "result": "passed"}
    forbidden = post(client, f"/admin/verifications/{ref}/face-result", **body)
    assert forbidden.status_code == 403
    done = post(admin, f"/admin/verifications/{ref}/face-result", **body)
    assert done.status_code == 200, done.text
    repeated = post(admin, f"/admin/verifications/{ref}/face-result", **body)
    assert repeated.json() == done.json()
    task = done.json()["data"]["task"]
    assert task["status"] == "succeeded"
    assert task["data"]["operation_id"] == child["data"]["operation_id"]
    assert len(bank_writes(app)) == before + 1
    return task, ref


def test_p01_two_medium_transfers_confirm_verify_and_restart_without_duplicate_money(tmp_path):
    config = configuration(tmp_path).model_copy(update={"pension_demo_profile": PROFILE})
    app = pension_app(config)
    seed_fresh_p01(app)
    try:
        with TestClient(app) as client, TestClient(app) as admin:
            _, menu = start(client, REQUEST)
            ready = plan_to_adoption(client, menu)
            choose(client, ready, "采用并开始办理")
            first = transfer_children(client, menu["task_id"])[0]
            assert first["data"]["amount_fen"] == 250_000
            enter_admin(admin)
            done_first, first_challenge = verify_medium(client, admin, app, first, 0)
            cookie = client.cookies.get("bank_session")
            original_op = done_first["data"]["operation_id"]
            captured = app.state.api.runtime.application.get_task("U1", "D1", menu["task_id"])
            assert captured.snapshot["risk_capture_version"] == RiskConversation.CAPTURE_VERSION
    finally:
        app.state.api.runtime.close()

    restarted = pension_app(config)
    try:
        with TestClient(restarted) as client, TestClient(restarted) as admin:
            client.cookies.set("bank_session", cookie)
            saved = client.get(f"/api/v1/tasks/{first['task_id']}").json()["data"]
            assert saved["data"]["operation_id"] == original_op
            assert saved["data"]["operation"]["receipt"] == done_first["data"]["operation"]["receipt"]
            queried = post(client, f"/tasks/{first['task_id']}/query-result")
            assert queried.status_code == 200, queried.text
            assert queried.json()["data"]["data"]["operation_id"] == original_op
            assert len(bank_writes(restarted)) == 1
            resumed = post(client, f"/tasks/{menu['task_id']}/resume")
            assert resumed.status_code == 200, resumed.text
            children = transfer_children(client, menu["task_id"])
            assert len(children) == 2
            second = next(item for item in children if item["task_id"] != first["task_id"])
            assert second["data"]["amount_fen"] == 100_000
            source, context, action, declaration = resolved_inputs(restarted, menu["task_id"], second)
            assert source.request_capture_version == RiskConversation.CAPTURE_VERSION
            assert restarted.state.api.runtime.assess_risk(context, action, declaration).risk_level == RiskLevel.MEDIUM
            enter_admin(admin)
            _, second_challenge = verify_medium(client, admin, restarted, second, 1)
            assert second_challenge != first_challenge
            final = post(client, f"/tasks/{menu['task_id']}/resume")
            assert final.status_code == 200, final.text
            receipt = final.json()["data"]
            assert receipt["status"] == "succeeded"
            assert "5000.00" in receipt["message"] and "1500.00" in receipt["message"]
            assert "3500.00" in receipt["message"]
            operations = bank_writes(restarted)
            assert len(operations) == 2
            assert len({row["operation_id"] for row in operations}) == 2
            assert all(row["action_name"] == "bank.submit_transfer" and row["status"] == "succeeded"
                       for row in operations)
            bank = restarted.state.api.runtime.bank
            assert bank.store.get_account("U1", "A1").book_balance_fen == 150_000
            assert bank.store.get_account("U1", "A5").book_balance_fen == 250_000
            assert restarted.state.api.runtime.application.get_active_arrangement("U1", "D1", "A1") is None
    finally:
        restarted.state.api.runtime.close()


def test_existing_a2_fixture_still_precedes_the_new_profile(tmp_path):
    config = configuration(tmp_path).model_copy(update={"pension_demo_profile": PROFILE})
    app = app_for(config)
    try:
        with TestClient(app) as client:
            _, task = start(client, "从A1给妈妈转500元")
            assert task["interaction"]["kind"] == "confirmation"
            waiting = approve(client, task)
            ref = waiting["interaction"]["record_ref"]
            view = client.get(f"/api/v1/verifications/{ref}").json()["data"]
            assert view["required_methods"] == ["code"]
            assert bank_writes(app) == []
    finally:
        app.state.api.runtime.close()
