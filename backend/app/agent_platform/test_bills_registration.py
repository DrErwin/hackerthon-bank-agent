"""Second-module registration and routing: the bills stub proves the platform seam (v04-platform/03)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.audit.journal import AuditJournal
from app.contracts.common import TaskStatus
from app.contracts.platform import ModuleManifest, TrustedContext
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
