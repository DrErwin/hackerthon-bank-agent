"""L01 integration: real Harness, scoped SQLite, SecurityGate and seeded Mock Bank.

The planner and the LOW-risk test policy are explicit test doubles. This does
not claim real-model, HTTP, frontend or professional-security acceptance.
"""
from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import uuid4

import pytest

from app.audit.journal import AuditJournal
from app.agent_platform.harness import AgentHarness
from app.agent_platform.model import TransferProposal
from app.agent_platform.registry import CapabilityRegistry
from app.contracts.bank import BankError, QueryFailure
from app.contracts.bills import BillDetails, SpendingSummary
from app.contracts.common import RiskLevel, TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.security import ExecutionSecurityContext
from app.memory.adapter import MemoryAdapter
from app.security import ConfirmationService, SecurityGate, ToolRegistry
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore
from app.storage.mock_bank.repository import MockBankStore

from app.modules.bills.entry import register_bills
from app.modules.bills.reads import GatewayBillsReads

BANK_NOW = datetime.fromisoformat("2026-10-14T13:00:00+08:00")
START = datetime.fromisoformat("2026-09-01T00:00:00+08:00")
END = datetime.fromisoformat("2026-10-01T00:00:00+08:00")


def trusted(task="T1", *, session="S1", run="R1"):
    return TrustedContext(user_id="U1", session_id=session, task_id=task, run_id=run,
                          parent_task_id=None, demo_round_id="D1")


class Planner:
    provider = "scripted"
    model_name = "test-bills-L01"
    config_version = "test-l01-v1"

    def select(self, intent_text, context, catalog, memory, thread_id, context_summary=None):
        assert "bills.summarize" in {item["name"] for item in catalog}
        return TransferProposal(capability_name="bills.summarize")


class ObservedGateway(BankGateway):
    def __init__(self, bank):
        super().__init__(bank)
        self.reads = []
        self.bank_writes = 0

    def list_accounts(self, context):
        self.reads.append(("accounts", context.user_id))
        return super().list_accounts(context)

    def list_transactions(self, context, account_id, start_at, end_at):
        self.reads.append(("transactions", context.user_id, account_id, start_at, end_at))
        return super().list_transactions(context, account_id, start_at, end_at)

    def submit_transfer(self, *args, **kwargs):
        self.bank_writes += 1
        raise AssertionError("a bill query must never call a funds operation")


class Environment:
    def __init__(self, directory):
        self.directory = directory
        self.application = ApplicationStore(directory / "application.sqlite")
        self.memory = MemoryAdapter(self.application, active_round=lambda: "D1")
        self.audit = AuditJournal(self.application.path)
        bank = MockBankService(MockBankStore(directory / "bank.sqlite"),
                               demo_secret=b"l01-test-only-not-production-secret", clock=lambda: BANK_NOW)
        bank.seed_flow_history()
        self.gateway = ObservedGateway(bank)
        self.decisions = []
        self.permission = True
        self.session()
        self.registry = CapabilityRegistry()
        register_bills(self.registry, self.reads_factory, lambda: BANK_NOW)
        self.harness = AgentHarness(self.application, self.memory, self.audit, self.registry, Planner(),
                                    lambda context, definition: self.valid_session(context))

    def session(self, session_id="S1"):
        at = datetime.now(timezone.utc)
        self.application.create_session(session_id, "U1", "D1", at.isoformat(),
                                         (at + timedelta(days=1)).isoformat())

    def valid_session(self, context):
        session = self.application.get_session(context.user_id, context.demo_round_id, context.session_id)
        return (context.user_id == "U1" and context.demo_round_id == "D1" and session is not None
                and datetime.fromisoformat(session.expires_at) > datetime.now(timezone.utc))

    @staticmethod
    def security_context(context):
        return ExecutionSecurityContext(user_id=context.user_id, session_id=context.session_id,
            demo_round_id=context.demo_round_id, task_id=context.task_id, run_id=context.run_id,
            source_task_id=context.parent_task_id, operation_id=None, action_revision=None,
            confirmation_id=None, confirmation_version=None, verification_ids=[],
            release_authorization_id=None)

    def reads_factory(self, context, trace):
        def no_sensitive_flow(*args):
            raise AssertionError("read-only L01 must not create a confirmation or verification")

        def authorize(current, action, declaration):
            return (self.permission and self.valid_session(current)
                    and declaration.required_permissions == ["bills.read"]
                    and action.action_name in {"bills.bank.list_accounts", "bills.bank.list_transactions"})

        def terminated(current):
            task = self.application.get_task(current.user_id, current.demo_round_id, current.task_id)
            if task is None or task.session_id != current.session_id:
                raise PermissionError("ACCESS_DENIED")
            return task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}

        gate = SecurityGate(ToolRegistry(), ConfirmationService(self.directory / "security.sqlite"),
            scope_authorizer=authorize, task_state_resolver=terminated,
            risk_assessor=lambda *_: RiskLevel.LOW, confirmation_preparer=no_sensitive_flow,
            verification_preparer=no_sensitive_flow, verification_resolver=no_sensitive_flow,
            challenge_resolver=no_sensitive_flow, decision_sink=self.decisions.append,
            snapshot_writer=no_sensitive_flow, summary_validator=lambda *_: False)
        return GatewayBillsReads(self.gateway, gate, self.security_context, trace)

    def balances(self):
        return {a.account_id: a.available_balance_fen
                for a in BankGateway.list_accounts(self.gateway, trusted()).data.accounts}

    def close(self):
        self.gateway.close()


@pytest.fixture
def env(tmp_path):
    result = Environment(tmp_path)
    yield result
    result.close()


def payload(result, model=SpendingSummary):
    return model.model_validate(result.data.model_dump() if hasattr(result.data, "model_dump") else result.data)


def test_real_bank_harness_and_security_complete_l01(env):
    balances = env.balances()
    result = env.harness.start(trusted(), uuid4(), "2026年9月所有账户账单")
    assert result.status == TaskStatus.SUCCEEDED, result
    summary = payload(result)
    account_ids = summary.scope.account_ids
    rows = [row for account in account_ids for row in
            BankGateway.list_transactions(env.gateway, trusted(), account, START, END).data.transactions]
    gross = sum(r.amount_fen for r in rows if r.nature == "consumption" and r.direction == "outflow")
    refund = sum(r.amount_fen for r in rows if r.nature == "refund" and r.direction == "inflow")
    assert summary.transaction_count == len(rows) > 0
    assert (summary.consumption_gross_fen, summary.consumption_refund_fen,
            summary.consumption_net_fen) == (gross, refund, gross - refund)
    assert summary.as_of == BANK_NOW
    assert env.gateway.bank_writes == 0 and env.balances() == balances
    assert env.decisions and all(d.decision == "allow" for d in env.decisions)
    task = env.application.get_task("U1", "D1", "T1")
    assert task.snapshot["capability_name"] == "bills.summarize"
    assert task.checkpoint_id is not None
    assert "契约形状桩" not in result.message


def test_real_entry_resumes_month_and_account_choices_after_recreation(env):
    result = env.harness.start(trusted(), uuid4(), "查账单")
    assert result.status == TaskStatus.WAITING_INPUT and env.gateway.reads == []
    month = next(o for o in result.interaction.options if o.label == "上月")
    result = env.harness.resume(trusted(run="R2"), {"choice": month.id})
    assert result.status == TaskStatus.WAITING_INPUT
    option = next(o for o in result.interaction.options if o.label == "所有本人账户")
    # A fresh Entry object is made on every resume; state comes from the real scoped saver.
    result = env.harness.resume(trusted(run="R3"), {"choice": option.id})
    assert result.task_id == "T1" and result.run_id == "R3"
    assert result.status == TaskStatus.SUCCEEDED
    assert payload(result).scope.start_at == START
    assert env.gateway.bank_writes == 0


def test_security_refusal_happens_before_bank_read(env):
    env.permission = False
    result = env.harness.start(trusted(), uuid4(), "2026年9月所有账户账单")
    assert result.status == TaskStatus.FAILED
    assert result.error.source == "security"
    assert env.gateway.reads == [] and env.gateway.bank_writes == 0
    assert any(d.decision == "block" for d in env.decisions)


def test_no_duplicate_reads_when_original_start_is_replayed(env):
    request_id = uuid4()
    first = env.harness.start(trusted(), request_id, "2026年9月所有账户账单")
    count = len(env.gateway.reads)
    second = env.harness.start(trusted(), request_id, "2026年9月所有账户账单")
    assert len(env.gateway.reads) == count
    assert payload(first) == payload(second)
    assert first.task_id == second.task_id


def test_cancellation_does_not_query_bank_or_revive_task(env):
    result = env.harness.start(trusted(), uuid4(), "查账单")
    option = result.interaction.options[0].id
    stopped = env.harness.resume(trusted(run="R2"), {"cancel": True})
    assert stopped.status == TaskStatus.CANCELLED
    try:
        retried = env.harness.resume(trusted(run="R3"), {"choice": option})
        assert retried.status == TaskStatus.CANCELLED
    except (ValueError, PermissionError):
        pass  # platform may reject a terminated task before invoking its module
    assert env.gateway.reads == []


def test_cross_session_recovery_keeps_original_task_and_rechecks_reads(env):
    result = env.harness.start(trusted(), uuid4(), "查账单")
    old_choice = result.interaction.options[0].id
    env.session("S2")
    moved = env.harness.recover_session(trusted(session="S2", run="R2"))
    assert moved.task_id == "T1" and moved.status == TaskStatus.WAITING_INPUT
    assert old_choice not in {o.id for o in moved.interaction.options}
    assert env.gateway.reads == []
    result = env.harness.resume(trusted(session="S2", run="R3"), {"choice": moved.interaction.options[0].id})
    assert result.status == TaskStatus.WAITING_INPUT
    month = next(o for o in result.interaction.options if o.label == "上月")
    result = env.harness.resume(trusted(session="S2", run="R4"), {"choice": month.id})
    accounts = next(o for o in result.interaction.options if o.label == "所有本人账户")
    result = env.harness.resume(trusted(session="S2", run="R5"), {"choice": accounts.id})
    assert result.status == TaskStatus.SUCCEEDED and result.task_id == "T1"
    assert env.gateway.bank_writes == 0


def test_real_details_returns_bank_metadata_not_invented_values(env):
    result = env.harness.start(trusted(), uuid4(), "2026年9月所有账户餐饮明细")
    assert result.status == TaskStatus.SUCCEEDED, result
    details = payload(result, BillDetails)
    assert details.category == "dining"
    assert all(t.category == "dining" for t in details.transactions)
    assert env.gateway.bank_writes == 0


def test_bank_failure_is_a_failed_trace_and_retryable_original_task(env, monkeypatch):
    raw_secret = "untrusted-upstream-secret-should-never-be-persisted"
    original = env.gateway.list_transactions
    monkeypatch.setattr(env.gateway, "list_transactions", lambda *_: QueryFailure(kind="error",
        error=BankError(code="CALL_TIMEOUT", details={"secret": raw_secret})))
    result = env.harness.start(trusted(), uuid4(), "2026年9月所有账户账单")
    assert result.status == TaskStatus.WAITING_INPUT and result.data is None
    with sqlite3.connect(env.application.path) as connection:
        stored = "\n".join(connection.iterdump())
    assert raw_secret not in stored
    assert "BILLS_BANK_QUERY_FAILED" in stored
    monkeypatch.setattr(env.gateway, "list_transactions", original)
    result = env.harness.resume(trusted(run="R2"), {"choice": result.interaction.options[0].id})
    assert result.status == TaskStatus.SUCCEEDED and result.task_id == "T1"
    assert env.gateway.bank_writes == 0
