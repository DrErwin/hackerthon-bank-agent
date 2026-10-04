"""Planning stops at its result, retains conflicts, and never invents an account."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from typing import Any
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.memory.adapter import MemoryAdapter
from app.storage.application import ApplicationStore
from fastapi.testclient import TestClient
from app.api.test_app import start
from .model import DeepAgentPlanner, ModelSettings, TransferProposal
from .test_harness import ScriptedChatModel, trusted
from .test_local_demo import ConnectorTestModel, app_for, configuration, ledger_count


class PlanningSequenceModel(ScriptedChatModel):
    calls: int = 0
    account: str | None = "A1"
    payee: str | None = "妈妈"
    amount: int | None = None
    tail_reply: bool = False
    simultaneous: bool = False

    def _generate(self, messages, **kwargs):
        self.calls += 1
        if any(isinstance(m, ToolMessage) for m in messages):
            calls = [{"name": "reply_only", "args": {"message": "请补充金额。"},
                      "id": "tail", "type": "tool_call"}] if self.tail_reply and self.calls == 2 else []
        else:
            calls = [{"name": "propose_transfer", "args": {
                "payee_hint": self.payee, "amount_fen": self.amount,
                "payer_account_id": self.account}, "id": "first", "type": "tool_call"}]
            if self.simultaneous:
                calls.append({"name": "reply_only", "args": {"message": "请补充金额。"},
                              "id": "conflict", "type": "tool_call"})
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=calls))])


def select(tmp_path, model):
    application = ApplicationStore(tmp_path / "app.sqlite")
    now = datetime.now(timezone.utc)
    application.create_session("S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat())
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    planner = DeepAgentPlanner(ModelSettings(model, "scripted", model.model_name, "ticket10-test"))
    return planner.select("给妈妈转钱", trusted(), [{"name": "transfer.start_transfer"}], memory, "thread")


def test_result_ends_planning_before_followup_reply(tmp_path):
    model = PlanningSequenceModel(tail_reply=True)
    proposal = select(tmp_path, model)
    assert proposal.amount_fen is None
    assert model.calls == 1


def test_simultaneous_conflict_is_rejected_with_safe_diagnostics(tmp_path):
    with pytest.raises(ValueError, match="MODEL_PROPOSAL_AMBIGUOUS") as caught:
        select(tmp_path, PlanningSequenceModel(simultaneous=True))
    assert caught.value.stage == "result_count"
    assert caught.value.outcome_count == 2
    assert set(caught.value.tool_names) == {"propose_transfer", "reply_only"}


@pytest.mark.parametrize("account", [None, "null"])
def test_absent_account_remains_absent(tmp_path, account):
    proposal = select(tmp_path, PlanningSequenceModel(account=account, amount=1600))
    assert proposal.payer_account_id is None
    assert proposal.amount_fen == 1600


def test_explicit_account_is_preserved(tmp_path):
    assert select(tmp_path, PlanningSequenceModel(account="OTHER")).payer_account_id == "OTHER"


def test_absent_recipient_uses_same_null_semantics(tmp_path):
    assert select(tmp_path, PlanningSequenceModel(payee="null")).payee_hint is None


def test_no_result_has_safe_zero_count(tmp_path):
    with pytest.raises(ValueError, match="MODEL_PROPOSAL_AMBIGUOUS") as caught:
        select(tmp_path, ScriptedChatModel(response_mode="none"))
    assert caught.value.stage == "result_count"
    assert caught.value.outcome_count == 0
    assert caught.value.tool_names == ()


class MalformedFieldsModel(PlanningSequenceModel):
    invalid_amount: Any = ["provider-private-text"]

    def _generate(self, messages, **kwargs):
        result = super()._generate(messages, **kwargs)
        for call in result.generations[0].message.tool_calls:
            if call["name"] == "propose_transfer":
                call["args"]["amount_fen"] = self.invalid_amount
        return result


def test_malformed_fields_are_distinct_from_no_result(tmp_path):
    with pytest.raises(ValueError, match="MODEL_PROPOSAL_INVALID") as caught:
        select(tmp_path, MalformedFieldsModel())
    assert caught.value.stage == "field_parse"
    assert caught.value.outcome_count == 0
    assert "provider-private-text" not in str(caught.value)


@pytest.mark.parametrize("amount", [True, "1600", 1600.0, 1600.5])
def test_amount_type_is_not_coerced_before_validation(tmp_path, amount):
    with pytest.raises(ValueError, match="MODEL_PROPOSAL_INVALID"):
        select(tmp_path, MalformedFieldsModel(invalid_amount=amount))


def test_invocation_failure_exposes_no_provider_exception(tmp_path):
    with patch("langgraph.graph.state.CompiledStateGraph.invoke",
               side_effect=RuntimeError("provider-private-text")):
        with pytest.raises(ValueError, match="MODEL_PLANNING_FAILED") as caught:
            select(tmp_path, PlanningSequenceModel())
    assert caught.value.stage == "model_call"
    assert caught.value.outcome_count == 0
    assert "provider-private-text" not in str(caught.value)


@pytest.mark.parametrize("amount,account,missing", [
    (None, "A1", "amount_fen"), (1600, "null", "payer_account_id"),
])
def test_missing_fields_reach_http_task_without_bank_submission(tmp_path, amount, account, missing):
    original = ConnectorTestModel._generate

    def generate(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        for call in result.generations[0].message.tool_calls:
            if call["name"] == "propose_transfer":
                call["args"].update(amount_fen=amount, payer_account_id=account)
        return result

    with patch.object(ConnectorTestModel, "_generate", generate):
        app = app_for(configuration(tmp_path))
        with TestClient(app) as client:
            _, task = start(client, text="给妈妈转钱")
            assert task["status"] == "waiting_input"
            assert missing in task["interaction"]["required_fields"]
            assert ledger_count(app) == 0
