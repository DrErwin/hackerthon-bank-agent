"""Second-module registration, routing and resume through one platform entry (v04-platform/03 and 08)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.audit.journal import AuditJournal
from app.contracts.bills import AccountSourceAsOf, BillScope, SpendingSummary
from app.contracts.common import TaskStatus
from app.contracts.platform import ModuleManifest, TrustedContext
from app.contracts.tasks import InteractionRequest, ModuleResult
from app.memory.adapter import MemoryAdapter
from app.modules.transfer.manifest import MANIFEST
from app.storage.application import ApplicationStore

from .bills_stub import BILLS_MANIFEST, register_bills_stub
from .harness import AgentHarness
from .model import TransferProposal
from .registry import CapabilityRegistry


def trusted(task="T1"):
    return TrustedContext(user_id="U1", session_id="S1", task_id=task, run_id="R1",
                          parent_task_id=None, demo_round_id="D1")


class BillsPlanner:
    provider = "scripted"
    model_name = "bills-test"
    config_version = "test-v1"

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = 0
        self.catalogs = []

    def select(self, intent_text, trusted, catalog, memory, thread_id, context_summary=None):
        self.calls += 1
        self.catalogs.append(catalog)
        return self.outcome


def harness_with_bills(path, outcome, *, authorize=lambda *_: True):
    application = ApplicationStore(path)
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    audit = AuditJournal(application.path)
    registry = CapabilityRegistry()
    # The transfer factory is never reached when the planner routes to bills.
    registry.register_transfer(MANIFEST, lambda _trusted, _saver, _trace: None)
    register_bills_stub(registry)
    planner = BillsPlanner(outcome)
    return AgentHarness(application, memory, audit, registry, planner, authorize), planner


def test_bills_capabilities_register_alongside_transfer(tmp_path):
    harness, planner = harness_with_bills(tmp_path / "app.sqlite",
                                          TransferProposal(capability_name="bills.summarize"))
    catalog = harness.registry.public_catalog()
    names = [item["name"] for item in catalog]
    assert set(names) == {"transfer.start_transfer", "bills.summarize",
                          "bills.detect_anomalies", "bills.generate_report"}
    transfer_entry = next(item for item in catalog
                          if item["name"] == "transfer.start_transfer")
    assert transfer_entry["input_schema_ref"] == "StartTransferInput"


def test_bill_intent_routes_to_the_registered_bills_stub(tmp_path):
    harness, planner = harness_with_bills(tmp_path / "app.sqlite",
                                          TransferProposal(capability_name="bills.summarize"))
    at = datetime.now(timezone.utc)
    harness.application.create_session("S1", "U1", "D1", at.isoformat(),
                                       (at + timedelta(days=1)).isoformat())
    result = harness.start(trusted(), uuid4(), "这个月钱花哪了")
    assert result.status == TaskStatus.SUCCEEDED
    assert "契约形状桩" in result.message
    task = harness.application.get_task("U1", "D1", "T1")
    assert task.snapshot["capability_name"] == "bills.summarize"
    assert task.snapshot["intent_text"] == "这个月钱花哪了"
    assert task.snapshot["result"]["status"] == "succeeded"


def test_register_module_rejects_foreign_and_duplicate_capabilities(tmp_path):
    registry = CapabilityRegistry()
    register_bills_stub(registry)
    with pytest.raises(ValueError, match="DUPLICATE_CAPABILITY"):
        register_bills_stub(registry)

    foreign = ModuleManifest(
        module_name="bills", version="test", owner="test", description="",
        implementation_kind="workflow", dependencies=[],
        capabilities=[BILLS_MANIFEST.capabilities[0].model_copy(
            update={"name": "cross.locate"})],
    )
    with pytest.raises(ValueError, match="CAPABILITY_NOT_IN_MODULE"):
        registry.register_module(foreign, lambda *_: None)

    empty = ModuleManifest(module_name="bills", version="test", owner="test",
                           description="", implementation_kind="workflow",
                           dependencies=[], capabilities=[])
    with pytest.raises(ValueError, match="NO_PUBLIC_CAPABILITY"):
        registry.register_module(empty, lambda *_: None)

    duplicated = ModuleManifest(
        module_name="bills", version="test", owner="test", description="",
        implementation_kind="workflow", dependencies=[],
        capabilities=[BILLS_MANIFEST.capabilities[0], BILLS_MANIFEST.capabilities[0]],
    )
    with pytest.raises(ValueError, match="DUPLICATE_CAPABILITY"):
        registry.register_module(duplicated, lambda *_: None)


def bills_summary():
    """A second-module payload small enough to read, still a contract model (§5.3)."""

    as_of = "2026-09-30T08:00:00+00:00"
    return SpendingSummary(
        scope=BillScope(account_ids=["A1"], start_at="2026-09-01T00:00:00+00:00",
                        end_at="2026-09-30T00:00:00+00:00"),
        as_of=as_of,
        source_as_of=[AccountSourceAsOf(account_id="A1", as_of=as_of)],
        transaction_count=0, consumption_gross_fen=0, consumption_refund_fen=0,
        consumption_net_fen=0, transfer_out_fen=0, transfer_in_fen=0,
        categories=[], comparison=None,
    )


class WaitingBillsEntry:
    """A second-module capability that pauses for the user, then finishes on the same task."""

    def __init__(self, summary):
        self._summary = summary

    def start(self, trusted, request, *, thread_id=None):
        return self._result(trusted, TaskStatus.WAITING_INPUT, "请选择要查看的月份。")

    def resume(self, trusted, response, *, thread_id=None):
        return self._result(trusted, TaskStatus.SUCCEEDED, "已按所选月份汇总。")

    def recover_session(self, trusted, *, source_session_id, thread_id=None):
        return self._result(trusted, TaskStatus.SUCCEEDED, "已按所选月份汇总。")

    def checkpoint_context(self, trusted, *, thread_id=None):
        return None

    def _result(self, trusted, status, message):
        waiting = status == TaskStatus.WAITING_INPUT
        return ModuleResult(
            task_id=trusted.task_id, run_id=trusted.run_id, status=status, data=self._summary,
            message=message,
            interaction=InteractionRequest(
                interaction_id="I1", kind="input", prompt="要看哪个月？", required_fields=["text"],
                options=[], record_ref=None,
            ) if waiting else None,
            error=None, allowed_actions=["provide_input", "cancel"] if waiting else [],
            recovery_required=False, recovery_reason=None,
        )


def waiting_bills_harness(path, summary):
    """The one platform entry with a registered second module that pauses for input."""

    application = ApplicationStore(path)
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    registry = CapabilityRegistry()
    registry.register_transfer(MANIFEST, lambda _trusted, _saver, _trace: None)
    registry.register_module(BILLS_MANIFEST,
                             lambda _trusted, _saver, _trace: WaitingBillsEntry(summary))
    planner = BillsPlanner(TransferProposal(capability_name="bills.summarize"))
    return AgentHarness(application, memory, AuditJournal(application.path), registry, planner,
                        lambda *_: True)


def open_session(application, session_id):
    at = datetime.now(timezone.utc)
    application.create_session(session_id, "U1", "D1", at.isoformat(),
                               (at + timedelta(days=1)).isoformat())


def test_waiting_second_module_task_resumes_along_its_own_payload(tmp_path):
    """Issue #122 第 2 项：等待类账单任务沿原任务 resume，不被转账视图定型挡住。"""

    summary = bills_summary()
    harness = waiting_bills_harness(tmp_path / "app.sqlite", summary)
    open_session(harness.application, "S1")

    started = harness.start(trusted(), uuid4(), "帮我看这个月的账单")
    assert started.status == TaskStatus.WAITING_INPUT
    assert started.data == summary
    # 平台按快照原样交回第二模块载荷（不再定型为转账视图），按模块自己的契约模型可解析。
    fetched = harness.get(trusted())
    assert fetched.data == summary.model_dump(mode="json")
    assert SpendingSummary.model_validate(fetched.data) == summary

    resumed = harness.resume(TrustedContext(user_id="U1", session_id="S1", task_id="T1",
                                            run_id="R2", parent_task_id=None,
                                            demo_round_id="D1"), {})
    assert resumed.status == TaskStatus.SUCCEEDED
    assert resumed.data == summary


def test_waiting_second_module_task_recovers_into_a_new_session(tmp_path):
    """同一接缝的跨会话恢复：审计取值不得按转账字段硬取（Issue #122 第 2 项）。"""

    summary = bills_summary()
    harness = waiting_bills_harness(tmp_path / "app.sqlite", summary)
    open_session(harness.application, "S1")
    open_session(harness.application, "S2")
    started = harness.start(trusted(), uuid4(), "帮我看这个月的账单")
    assert started.status == TaskStatus.WAITING_INPUT

    recovered = harness.recover_session(TrustedContext(
        user_id="U1", session_id="S2", task_id="T1", run_id="R2",
        parent_task_id=None, demo_round_id="D1"))

    assert recovered.status == TaskStatus.WAITING_INPUT
    assert SpendingSummary.model_validate(recovered.data) == summary
    assert harness.application.get_task("U1", "D1", "T1").session_id == "S2"
    events = [event for event in harness.audit._events("D1", "T1")
              if event.event_type == "recovery.checked"]
    assert [event.outcome for event in events] == ["started", "succeeded"]
    # 第二模块结果没有 operation 引用；不得从转账字段硬取（否则恢复在落库前中断）。
    assert all(event.payload.operation_ids == [] for event in events)
