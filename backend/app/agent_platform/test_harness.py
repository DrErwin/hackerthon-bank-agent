"""Public dispatch, durable recovery, model boundary and trace for ticket 09."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.audit.journal import AuditJournal
from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from app.memory.adapter import MemoryAdapter
from app.modules.transfer.manifest import MANIFEST
from app.modules.transfer.test_workflow import Ports
from app.modules.transfer.workflow import TransferWorkflow
from app.storage.application import ApplicationStore

from .harness import AgentHarness
from .model import DeepAgentPlanner, ModelSettings, TransferProposal
from .registry import CapabilityRegistry


class ProposalModel:
    provider = "scripted"
    model_name = "transfer-test"
    config_version = "test-v1"

    def __init__(self):
        self.calls = 0

    def select(self, intent_text, trusted, catalog, memory, thread_id):
        self.calls += 1
        assert [item["name"] for item in catalog] == ["transfer.start_transfer"]
        assert intent_text == "给妈妈转 500 元"
        return TransferProposal(payee_hint="妈妈", amount_fen=50_000,
                                payer_account_id="A1")


class ScriptedChatModel(BaseChatModel):
    model_name: str = "transfer-scripted"
    offered_tools: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "scripted"

    def _get_ls_params(self, **kwargs):
        return {"ls_provider": "scripted", "ls_model_name": self.model_name}

    def bind_tools(self, tools, **kwargs):
        self.offered_tools = [item.name for item in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if any(isinstance(item, ToolMessage) for item in messages):
            reply = AIMessage(content="已记录转账候选。")
        else:
            reply = AIMessage(content="", tool_calls=[{
                "name": "propose_transfer",
                "args": {"payee_hint": "妈妈", "amount_fen": 50_000,
                         "payer_account_id": "A1"},
                "id": "call-1", "type": "tool_call",
            }])
        return ChatResult(generations=[ChatGeneration(message=reply)])


def trusted(user="U1", run="R1"):
    return TrustedContext(user_id=user, session_id="S1", task_id="T1", run_id=run,
                          parent_task_id=None, demo_round_id="D1")


def runtime(path, ports, planner, authorize=lambda _trusted, _definition: True):
    application = ApplicationStore(path)
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    audit = AuditJournal(path)
    registry = CapabilityRegistry()
    registry.register_transfer(MANIFEST, lambda _trusted, saver: TransferWorkflow(ports, saver))
    return AgentHarness(application, memory, audit, registry, planner, authorize)


def test_public_transfer_survives_new_harness_and_deduplicates(tmp_path):
    path = tmp_path / "app.sqlite"
    ports = Ports()
    planner = ProposalModel()
    harness = runtime(path, ports, planner)
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    request_id = uuid4()
    pending = harness.start(trusted(), request_id, "给妈妈转 500 元")
    assert pending.status == TaskStatus.WAITING_APPROVAL
    assert pending.task_id == "T1"
    assert pending.data.operation_id is not None
    assert ports.submissions == 0
    assert harness.start(trusted(), request_id, "给妈妈转 500 元") == pending
    assert planner.calls == 1

    ports.approved = True
    restarted = runtime(path, ports, planner)
    assert restarted.get(trusted()) == pending
    done = restarted.resume(trusted(run="R2"), {"choice": "approve"})
    assert done.status == TaskStatus.SUCCEEDED
    assert done.run_id == "R2"
    assert done.data.operation_id == pending.data.operation_id
    assert ports.submissions == 1
    assert restarted.resume(trusted(run="R2"), {"choice": "approve"}) == done
    assert ports.submissions == 1

    events = restarted.audit._events("D1", "T1")
    assert [event.event_type for event in events] == [
        "model.started", "model.finished", "task.transition",
        "recovery.checked", "task.transition",
    ]
    assert {event.trace_id for event in events} == {events[0].trace_id}
    assert [(event.run_id, event.sequence) for event in events] == [
        ("R1", 0), ("R1", 1), ("R1", 2), ("R2", 0), ("R2", 1),
    ]


def test_task_owner_and_request_are_bound(tmp_path):
    path = tmp_path / "app.sqlite"
    harness = runtime(path, Ports(), ProposalModel())
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    request_id = uuid4()
    harness.start(trusted(), request_id, "给妈妈转 500 元")
    with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
        harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    with pytest.raises(PermissionError):
        harness.resume(trusted(user="U2"), {"choice": "approve"})


def test_deep_agent_only_receives_proposal_tool(tmp_path):
    path = tmp_path / "app.sqlite"
    application = ApplicationStore(path)
    now = datetime.now(timezone.utc)
    application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    task = application.create_task("T1", "U1", "S1", "D1", "R1", TaskStatus.RUNNING, {})
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    model = ScriptedChatModel()
    planner = DeepAgentPlanner(ModelSettings(
        model=model, provider="scripted", model_name="transfer-scripted",
        config_version="scripted-v1",
    ))
    proposal = planner.select(
        "给妈妈转 500 元", trusted(),
        [{"name": "transfer.start_transfer", "description": "普通转账",
          "input_schema_ref": "StartTransferInput"}],
        memory, task.checkpoint_thread_id,
    )
    assert proposal == TransferProposal(payee_hint="妈妈", amount_fen=50_000,
                                        payer_account_id="A1")
    assert model.offered_tools == ["propose_transfer"]


def test_public_capability_denial_never_enters_transfer(tmp_path):
    path = tmp_path / "app.sqlite"
    ports = Ports()
    planner = ProposalModel()
    harness = runtime(path, ports, planner,
                      authorize=lambda _trusted, _definition: False)
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    with pytest.raises(PermissionError, match="ACCESS_DENIED"):
        harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    assert ports.read_calls == []
    assert ports.submissions == 0
    assert planner.calls == 0


def test_invalid_model_amount_does_not_start_a_bank_task(tmp_path):
    class InvalidAmount(ProposalModel):
        def select(self, intent_text, trusted, catalog, memory, thread_id):
            return TransferProposal(payee_hint="妈妈", amount_fen=-1,
                                    payer_account_id="A1")

    path = tmp_path / "app.sqlite"
    ports = Ports()
    harness = runtime(path, ports, InvalidAmount())
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    failed = harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    assert failed.status == TaskStatus.FAILED
    assert failed.error.code == "MODEL_PROPOSAL_FAILED"
    assert ports.read_calls == []
    assert ports.submissions == 0
    assert [event.event_type for event in harness.audit._events("D1", "T1")] == [
        "model.started", "model.finished", "task.transition",
    ]


def test_deep_agent_and_transfer_share_task_storage_without_crossing_checkpoints(tmp_path):
    path = tmp_path / "app.sqlite"
    model = ScriptedChatModel()
    planner = DeepAgentPlanner(ModelSettings(
        model=model, provider="scripted", model_name="transfer-scripted",
        config_version="scripted-v1",
    ))
    ports = Ports()
    harness = runtime(path, ports, planner)
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    pending = harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    assert pending.status == TaskStatus.WAITING_APPROVAL
    assert ports.submissions == 0
    assert model.offered_tools == ["propose_transfer"]
    ports.approved = True
    assert runtime(path, ports, planner).resume(trusted(), {"choice": "approve"}).status == TaskStatus.SUCCEEDED
    assert ports.submissions == 1
