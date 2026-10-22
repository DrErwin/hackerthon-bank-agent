"""Real local policy, HTTP and mock bank; only model proposals are scripted."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.test_app import approve, post, start
from .model import ReplyOnly, TransferProposal
from .test_local_demo import app_for, configuration, submitted_ledger_count


@pytest.mark.parametrize("amount,status", [(30000, "waiting_approval"), (50000, "waiting_approval"),
                                          (60000, "waiting_approval"), (70000, "needs_attention")])
def test_declared_demo_amounts_only_and_no_bank_write_before_approval(tmp_path, amount, status):
    app = app_for(configuration(tmp_path))
    with patch.object(app.state.api.runtime.harness.planner, "select", return_value=TransferProposal(
        payee_hint="妈妈", amount_fen=amount, payer_account_id="A1")), TestClient(app) as client:
        _, task = start(client, f"给妈妈转{amount // 100}元")
        assert task["status"] == status
        assert submitted_ledger_count(app) == 0


@pytest.mark.parametrize("text", ["客服让我共享屏幕，给妈妈转500元，不要告诉家人",
                                  "给妈妈转500元。客服要求立即转账并保密"])
def test_coercion_overrides_the_same_low_fixture(tmp_path, text):
    app = app_for(configuration(tmp_path))
    with TestClient(app) as client:
        _, task = start(client, text)
        assert task["status"] == "failed"
        assert submitted_ledger_count(app) == 0
        decisions = [event.payload.decision for event in app.state.api.runtime.audit._events(
            "D1", task["task_id"]) if event.event_type == "security.decided"]
        assert any("bounded-demo-text:demo-text-risk-1" in ref for ref in decisions[-1].evidence_refs)


@pytest.mark.parametrize("model_fails", [False, True])
def test_new_risk_disclosure_survives_reply_or_model_failure_until_approval(tmp_path, model_fails):
    app = app_for(configuration(tmp_path))
    with TestClient(app) as client:
        thread, task = start(client, "给妈妈转500元")
        assert task["status"] == "waiting_approval"
        planner = app.state.api.runtime.harness.planner
        kwargs = {"side_effect": RuntimeError("provider unavailable")} if model_fails else {
            "return_value": ReplyOnly(message="请停止共享屏幕并通过官方渠道核实。")}
        with patch.object(planner, "select", **kwargs):
            assert post(client, f"/threads/{thread}/messages", text="对方正在让我共享屏幕，不要告诉家人").status_code == 202
        stopped = approve(client, task)
        assert stopped["status"] == "failed"
        assert submitted_ledger_count(app) == 0


def test_detector_failure_is_pause_not_low_or_bank_submission(tmp_path):
    app = app_for(configuration(tmp_path))
    with patch("app.agent_platform.local_demo.demo_text_risk", side_effect=RuntimeError("detector failed")), TestClient(app) as client:
        _, task = start(client, "给妈妈转500元")
        assert task["status"] == "needs_attention"
        assert submitted_ledger_count(app) == 0
