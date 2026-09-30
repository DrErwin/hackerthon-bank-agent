"""Public dispatch, durable recovery, model boundary and trace for ticket 09."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.audit.journal import AuditJournal
from app.contracts.common import TaskStatus
from app.contracts.audit import TaskTransitionPayload
from app.contracts.platform import TrustedContext
from app.memory.adapter import MemoryAdapter
from app.modules.transfer.manifest import MANIFEST
from app.modules.transfer.test_workflow import Ports
from app.modules.transfer.workflow import TransferWorkflow
from app.storage.application import ApplicationStore

from .harness import AgentHarness, RunTrace
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


def runtime(path, ports, planner, authorize=lambda _trusted, _definition: True,
            factory=None):
    application = ApplicationStore(path)
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    audit = AuditJournal(path)
    registry = CapabilityRegistry()
    registry.register_transfer(
        MANIFEST, factory or (lambda _trusted, saver, _trace: TransferWorkflow(ports, saver)),
    )
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


def test_recover_session_transitions_storage_and_records_both_sessions(tmp_path):
    path = tmp_path / "app.sqlite"
    ports = Ports()
    harness = runtime(path, ports, ProposalModel())
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    pending = harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    harness.application.create_session(
        "S2", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    current = trusted(run="R2").model_copy(update={"session_id": "S2"})

    recovered = harness.recover_session(current)

    assert recovered.task_id == "T1"
    assert recovered.run_id == "R2"
    assert recovered.status == TaskStatus.WAITING_APPROVAL
    assert recovered.data.operation_id == pending.data.operation_id
    assert ports.submissions == 0
    task = harness.application.get_task("U1", "D1", "T1")
    assert task.session_id == "S2"
    events = [event for event in harness.audit._events("D1", "T1")
              if event.event_type == "recovery.checked"]
    assert [event.outcome for event in events] == ["started", "succeeded"]
    assert all(event.session_id == "S2" and event.target_session_id == "S1" for event in events)
    assert all(event.payload.previous_run_id == "R1" for event in events)
    assert all(event.payload.current_run_id == "R2" for event in events)
    assert all(event.payload.operation_ids == [pending.data.operation_id] for event in events)

    # An ordinary chat reply does not skip the new session's confirmation.
    resumed = harness.resume(current, {"choice": "approve"})
    assert resumed.status == TaskStatus.WAITING_APPROVAL
    assert ports.submissions == 0


def test_recovery_audit_failure_prevents_task_or_checkpoint_conversion(tmp_path):
    path = tmp_path / "app.sqlite"
    ports = Ports()
    harness = runtime(path, ports, ProposalModel())
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    before = harness.application.get_task("U1", "D1", "T1")
    harness.application.create_session(
        "S2", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    current = trusted(run="R2").model_copy(update={"session_id": "S2"})
    append = harness.audit.append_in_transaction

    def unavailable(connection, event, **kwargs):
        if event.event_type == "recovery.checked":
            raise RuntimeError("audit unavailable")
        return append(connection, event, **kwargs)

    with patch.object(harness.audit, "append_in_transaction", side_effect=unavailable):
        with pytest.raises(RuntimeError, match="audit unavailable"):
            harness.recover_session(current)

    after = harness.application.get_task("U1", "D1", "T1")
    assert after.session_id == "S1"
    assert after.revision == before.revision
    assert "session_recovery" not in after.snapshot
    assert ports.submissions == 0


def test_session_recovery_retries_after_storage_transition_and_is_idempotent(tmp_path):
    ports = Ports()
    calls = []

    class FailsOnce(TransferWorkflow):
        def recover_session(self, trusted, *, source_session_id, thread_id=None):
            if not calls:
                calls.append("interrupted")
                raise RuntimeError("simulated interruption after storage transition")
            calls.append("recovered")
            return super().recover_session(
                trusted, source_session_id=source_session_id, thread_id=thread_id,
            )

    harness = runtime(
        tmp_path / "app.sqlite", ports, ProposalModel(),
        factory=lambda _trusted, saver, _trace: FailsOnce(ports, saver),
    )
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    pending = harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    harness.application.create_session(
        "S2", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    first_identity = trusted(run="R2").model_copy(update={"session_id": "S2"})

    with pytest.raises(RuntimeError, match="simulated interruption"):
        harness.recover_session(first_identity)

    interrupted = harness.application.get_task("U1", "D1", "T1")
    assert interrupted.session_id == "S2"
    assert interrupted.snapshot["session_recovery"]["phase"] == "transitioned"
    assert ports.submissions == 0

    restarted = runtime(
        tmp_path / "app.sqlite", ports, ProposalModel(),
        factory=lambda _trusted, saver, _trace: FailsOnce(ports, saver),
    )
    retry_identity = first_identity.model_copy(update={"run_id": "R3"})
    recovered = restarted.recover_session(retry_identity)
    assert recovered.status == TaskStatus.WAITING_APPROVAL
    assert recovered.data.operation_id == pending.data.operation_id
    assert ports.submissions == 0
    assert calls == ["interrupted", "recovered"]

    audit_count = len([event for event in restarted.audit._events("D1", "T1")
                       if event.event_type == "recovery.checked"])
    assert restarted.recover_session(retry_identity) == recovered
    assert len([event for event in restarted.audit._events("D1", "T1")
                if event.event_type == "recovery.checked"]) == audit_count


def test_recover_session_rejects_foreign_user_before_audit_or_transition(tmp_path):
    path = tmp_path / "app.sqlite"
    harness = runtime(path, Ports(), ProposalModel())
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    harness.application.create_session(
        "S2", "U2", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    current = trusted(user="U2", run="R2").model_copy(update={"session_id": "S2"})

    with pytest.raises(PermissionError, match="ACCESS_DENIED"):
        harness.recover_session(current)

    assert harness.application.get_task("U1", "D1", "T1").session_id == "S1"
    assert not any(event.event_type == "recovery.checked"
                   for event in harness.audit._events("D1", "T1"))


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


def test_public_capability_cannot_return_another_task_result(tmp_path):
    class MisboundWorkflow(TransferWorkflow):
        def start(self, trusted, request, *, thread_id=None):
            result = super().start(trusted, request, thread_id=thread_id)
            return result.model_copy(update={"task_id": "T2"})

        def resume(self, trusted, response, *, thread_id=None):
            result = super().resume(trusted, response, thread_id=thread_id)
            return result.model_copy(update={"task_id": "T2"})

    path = tmp_path / "app.sqlite"
    ports = Ports()
    planner = ProposalModel()
    bad_factory = lambda _trusted, saver, _trace: MisboundWorkflow(ports, saver)
    now = datetime.now(timezone.utc)
    harness = runtime(path, ports, planner, factory=bad_factory)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    request_id = uuid4()
    with pytest.raises(ValueError, match="CAPABILITY_CONTEXT_MISMATCH"):
        harness.start(trusted(), request_id, "给妈妈转 500 元")
    assert "result" not in harness.application.get_task("U1", "D1", "T1").snapshot

    pending = runtime(path, ports, planner).start(trusted(), request_id, "给妈妈转 500 元")
    assert pending.task_id == "T1"
    with pytest.raises(ValueError, match="CAPABILITY_CONTEXT_MISMATCH"):
        runtime(path, ports, planner, factory=bad_factory).resume(trusted(run="R2"), {})
    assert runtime(path, ports, planner).get(trusted()) == pending


def test_resume_rejects_silent_model_configuration_change(tmp_path):
    path = tmp_path / "app.sqlite"
    ports = Ports()
    harness = runtime(path, ports, ProposalModel())
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    changed_planner = ProposalModel()
    changed_planner.config_version = "test-v2"
    with pytest.raises(ValueError, match="MODEL_CONFIG_CHANGED"):
        runtime(path, ports, changed_planner).resume(trusted(run="R2"), {"choice": "approve"})
    assert ports.submissions == 0


def test_recovery_event_reports_still_waiting_without_approval(tmp_path):
    path = tmp_path / "app.sqlite"
    ports = Ports()
    harness = runtime(path, ports, ProposalModel())
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    waiting = harness.resume(trusted(), {"choice": "approve"})
    assert waiting.status == TaskStatus.WAITING_APPROVAL
    assert ports.submissions == 0
    recovery = [event for event in harness.audit._events("D1", "T1")
                if event.event_type == "recovery.checked"]
    assert recovery[-1].payload.result == "wait"


def test_resume_after_crash_before_first_model_result(tmp_path):
    path = tmp_path / "app.sqlite"
    planner = ProposalModel()
    harness = runtime(path, Ports(), planner)
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    request_id = uuid4()
    harness.application.create_task(
        "T1", "U1", "S1", "D1", "R1", TaskStatus.RUNNING,
        {"request_id": str(request_id), "intent_text": "给妈妈转 500 元",
         "config_version": planner.config_version, "trace_id": str(uuid4())},
    )
    waiting = harness.resume(trusted(run="R2"), {})
    assert waiting.status == TaskStatus.WAITING_APPROVAL
    assert waiting.run_id == "R2"
    assert planner.calls == 1
    recovery = [event for event in harness.audit._events("D1", "T1")
                if event.event_type == "recovery.checked"]
    assert recovery[-1].payload.result == "wait"


def test_resume_after_graph_checkpoint_but_before_task_summary(tmp_path):
    path = tmp_path / "app.sqlite"
    planner = ProposalModel()
    ports = Ports()
    harness = runtime(path, ports, planner)
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    task = harness.application.get_task("U1", "D1", "T1")
    harness.application.update_task(
        "U1", "D1", "T1", task.revision, "R1", TaskStatus.RUNNING,
        task.checkpoint_id, {key: value for key, value in task.snapshot.items() if key != "result"},
    )
    waiting = runtime(path, ports, planner).resume(trusted(run="R2"), {})
    assert waiting.status == TaskStatus.WAITING_APPROVAL
    assert waiting.run_id == "R2"
    assert planner.calls == 1
    assert ports.submissions == 0


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
    events = harness.audit._events("D1", "T1")
    assert [event.event_type for event in events] == [
        "model.started", "model.finished", "task.transition",
    ]
    assert events[1].parent_span_id == events[0].span_id


@pytest.mark.parametrize("intent", [
    "给妈妈转 500 元，验证码123456",
    "给妈妈转 500 元，短信码是 123456",
    "给妈妈转500元，短信发来的 123456 是验证码",
    "转 500 元，password 在后面",
])
def test_credentials_never_enter_model_task_or_audit(tmp_path, intent):
    path = tmp_path / "app.sqlite"
    planner = ProposalModel()
    harness = runtime(path, Ports(), planner)
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    with pytest.raises(ValueError, match="CREDENTIAL_IN_REQUEST"):
        harness.start(trusted(), uuid4(), intent)
    assert planner.calls == 0
    assert harness.application.get_task("U1", "D1", "T1") is None
    assert harness.audit._events("D1", "T1") == []


def test_parallel_audit_events_get_unique_order(tmp_path):
    path = tmp_path / "app.sqlite"
    harness = runtime(path, Ports(), ProposalModel())
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    task = harness.application.get_task("U1", "D1", "T1")

    def record(_index):
        return RunTrace(harness.audit, trusted(), task.checkpoint_thread_id,
                        task.snapshot["trace_id"]).record(
            "task.transition", TaskTransitionPayload(
                previous_status=TaskStatus.RUNNING, status=TaskStatus.RUNNING,
                plan_revision=None, step_id=None, reason_code="AUDIT_ORDER_TEST",
                checkpoint_ref=None,
            ), "succeeded",
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        added = list(pool.map(record, range(12)))
    assert sorted(event.sequence for event in added) == list(range(3, 15))


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
