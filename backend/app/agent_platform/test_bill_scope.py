"""Actual harness, bill module, policy and bank; planner is a test double."""
from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.test_app import start
from app.contracts.platform import TrustedContext
from .model import TransferProposal
from .test_local_demo import app_for, configuration, submitted_ledger_count


def child_context(task):
    return TrustedContext(user_id=task.user_id, session_id=task.session_id,
        demo_round_id=task.demo_round_id, task_id=str(uuid4()), run_id=str(uuid4()), parent_task_id=task.task_id)


def test_completed_bill_followups_keep_scope_and_original_result(tmp_path):
    app = app_for(configuration(tmp_path))
    harness = app.state.api.runtime.harness
    with TestClient(app) as client, patch.object(harness.planner, "select",
            return_value=TransferProposal(capability_name="bills.summarize")):
        _, original = start(client, "2026年9月所有账户账单")
        source = harness.application.get_task("U1", "D1", original["task_id"])
        details = harness.handle_message(child_context(source), uuid4(), "看看餐饮明细")
        data = details.model_dump(mode="json")["data"]
        assert details.status == "succeeded", details.error
        assert data["scope"] == original["data"]["scope"] and data["category"] == "dining"
        assert harness.application.get_task("U1", "D1", source.task_id).snapshot == source.snapshot
        assert submitted_ledger_count(app) == 0
        details_task = harness.application.get_task("U1", "D1", details.task_id)
        with patch.object(harness.planner, "select", return_value=TransferProposal(capability_name="bills.detect_anomalies")):
            unknown = harness.handle_message(child_context(details_task), uuid4(), "核对陌生扣款")
            assert unknown.status in {"succeeded", "waiting_input"}
            if unknown.interaction:
                assert "月份" not in unknown.interaction.prompt
                assert unknown.model_dump(mode="json")["data"]["scope"] == data["scope"]


@pytest.mark.parametrize("changed", ["session", "missing", "data"])
def test_invalid_source_never_supplies_scope(tmp_path, changed):
    app = app_for(configuration(tmp_path))
    harness = app.state.api.runtime.harness
    with TestClient(app) as client, patch.object(harness.planner, "select", return_value=TransferProposal(
            capability_name="bills.summarize")):
        _, original = start(client, "2026年9月所有账户账单")
        source = harness.application.get_task("U1", "D1", original["task_id"])
        context = child_context(source)
        invalid = (replace(source, session_id="OTHER") if changed == "session" else None if changed == "missing"
            else replace(source, snapshot={**source.snapshot, "result": {"data": {"scope": original["data"]["scope"]}}}))
        get_task = harness.application.get_task
        def lookup(user, round_id, task_id):
            return invalid if task_id == source.task_id else get_task(user, round_id, task_id)
        with patch.object(harness.application, "get_task", side_effect=lookup):
            result = harness.handle_message(context, uuid4(), "看看餐饮明细")
        assert result.status == "waiting_input"
        assert "月份" in result.interaction.prompt
