"""Ticket v05-cross-platform/05: the real local composition mounts the cross module.

Natural life-goal routing, honest refusals for goals whose business module is not
delivered, traceable father-child links, zero bank writes on the read phase, and
the original single-business entry staying usable — all on build_runtime's real
factories, policy and stores.
"""

from datetime import datetime, timedelta, timezone
from contextlib import closing
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.app import ApiConfig, create_app
from app.contracts.common import TaskStatus
from app.contracts.bank import QueryOk, TransactionList
from app.contracts.bills import BillScope, SpendingSummary
from app.contracts.platform import TrustedContext
from app.storage.database import connect

from .local_demo import LocalDemoConfig, build_runtime
from .test_local_demo import ConnectorTestModel, configuration, month_start


class RoutingModel(ConnectorTestModel):
    """One scripted planner: cross for the first goal, a transfer afterwards."""

    model_name: str = "glm-4.7"
    calls: int = 0
    # Tests that only need the ordinary transfer path start after the cross one.
    start_at: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        step = self.start_at + self.calls
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        if step == 1:
            args = {"capability_name": "cross.start_task"}
        else:
            args = {"payee_hint": "妈妈", "amount_fen": 50_000, "payer_account_id": "A1"}
        reply = AIMessage(content="", tool_calls=[
            {"name": "propose_transfer", "args": args, "id": f"call-{step}", "type": "tool_call"},
        ])
        return ChatResult(generations=[ChatGeneration(message=reply)])


def wired_app(tmp_path, start_at=0):
    config = configuration(tmp_path)
    with patch("app.agent_platform.local_demo.ChatOpenAI",
               return_value=RoutingModel(response_mode="transfer", start_at=start_at)):
        runtime = build_runtime(config)
    app = create_app(runtime, ApiConfig(
        secret=config.api_secret.get_secret_value().encode(), admin_key="local-test-admin",
        origins=("http://testserver",), demo_round_id=config.demo_round_id,
    ))
    return app, runtime


def enter(client):
    from .test_local_demo import enter as demo_enter

    return demo_enter(client)


def trusted(runtime, task_id, run_id="R1"):
    return TrustedContext(user_id="U1", session_id="S1", task_id=task_id, run_id=run_id,
                          parent_task_id=None, demo_round_id="D1")


def submitted_ledger_count(runtime):
    rows = runtime.gateway._bank.store.list_ledger("U1", "A1")
    return len([row for row in rows if not row["operation_id"].startswith("seed:")])


def test_real_composition_mounts_cross_and_traces_children(tmp_path):
    app, runtime = wired_app(tmp_path)
    client = TestClient(app)
    enter(client)
    now = datetime.now(timezone.utc)
    runtime.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    with closing(connect(runtime.gateway._bank.store.path)) as connection:
        operations_before = connection.execute("SELECT COUNT(*) FROM bank_operations").fetchone()[0]
    bank_reads = []
    read_transactions = runtime.gateway.list_transactions

    def observe_bank_read(context, account_id, start_at, end_at):
        response = read_transactions(context, account_id, start_at, end_at)
        assert isinstance(response, QueryOk)
        bank_reads.append((context, account_id, start_at, end_at,
                           TransactionList.model_validate(response.data)))
        return response

    # A natural expense-reduction goal reaches the registered cross capability;
    # the harness creates the task itself with the request's own snapshot.
    with patch.object(runtime.gateway, "list_transactions", side_effect=observe_bank_read):
        result = runtime.harness.handle_message(
            trusted(runtime, "GOAL"), uuid4(), "最近钱花得快，帮我处理不用的自动扣费",
        )
    assert result.task_id == "GOAL"
    task = runtime.application.get_task("U1", "D1", "GOAL")
    assert task.snapshot["capability_name"] == "cross.start_task"

    # Read children ran through the real registered factories and are traceable.
    relations = runtime.application.list_child_tasks("U1", "D1", "GOAL")
    by_step = {relation.step_id: relation for relation in relations}
    assert set(by_step) >= {"accounts", "subscriptions", "bills_compare"}
    for relation in relations:
        child = runtime.application.get_task("U1", "D1", relation.child_task_id)
        assert child.snapshot["capability_name"] == {
            "accounts": "transfer.list_accounts",
            "subscriptions": "subscription.list_subscriptions",
            "bills_compare": "bills.summarize",
        }[relation.step_id]
    # The real subscription inventory and typed bill comparison both arrived.
    subscriptions = runtime.application.get_task("U1", "D1", by_step["subscriptions"].child_task_id)
    inventory = subscriptions.snapshot["result"]["data"]["list_result"]["items"]
    assert any(item["service_name"].startswith("优酷") for item in inventory)
    bills = runtime.application.get_task("U1", "D1", by_step["bills_compare"].child_task_id)
    assert bills.snapshot["result"]["status"] == "succeeded"
    assert bills.snapshot["result"]["error"] is None
    summary = SpendingSummary.model_validate(bills.snapshot["result"]["data"])
    accounts = runtime.application.get_task("U1", "D1", by_step["accounts"].child_task_id)
    account_ids = [item["account_id"] for item in accounts.snapshot["result"]["data"]["accounts"]]
    bank_now = runtime.gateway._bank.clock()
    assert summary.scope == BillScope(account_ids=account_ids,
        start_at=month_start(bank_now, 1), end_at=month_start(bank_now))
    assert summary.comparison is not None
    assert summary.comparison.scope == BillScope(account_ids=account_ids,
        start_at=month_start(bank_now, 2), end_at=month_start(bank_now, 1))

    # Observe the actual B08 responses instead of asking the bills service to
    # compute its own expected answer. Provenance includes the real child scope.
    bills_reads = [read for read in bank_reads if read[0].task_id == bills.task_id]
    assert bills_reads
    for context, *_ in bills_reads:
        assert (context.user_id, context.session_id, context.demo_round_id,
                context.task_id, context.parent_task_id) == (
                    "U1", "S1", "D1", bills.task_id, "GOAL")
    current_batches = {account: batch for _, account, start, end, batch in bills_reads
                       if (start, end) == (summary.scope.start_at, summary.scope.end_at)}
    reference_batches = {account: batch for _, account, start, end, batch in bills_reads
                         if (start, end) == (summary.comparison.scope.start_at,
                                             summary.comparison.scope.end_at)}
    assert set(current_batches) == set(reference_batches) == set(account_ids)
    assert {source.account_id: source.as_of for source in summary.source_as_of} == {
        account: batch.as_of for account, batch in current_batches.items()}
    assert summary.as_of == min(batch.as_of for batch in current_batches.values())
    assert summary.comparison.as_of == min(batch.as_of for batch in reference_batches.values())
    rows = [row for batch in current_batches.values() for row in batch.transactions]
    reference_rows = [row for batch in reference_batches.values() for row in batch.transactions]
    assert summary.transaction_count == len(rows) > 0
    assert summary.consumption_gross_fen == sum(row.amount_fen for row in rows if row.nature == "consumption")
    assert summary.consumption_refund_fen == sum(row.amount_fen for row in rows if row.nature == "refund")
    assert summary.consumption_net_fen == summary.consumption_gross_fen - summary.consumption_refund_fen
    for direction, actual in (("outflow", summary.transfer_out_fen), ("inflow", summary.transfer_in_fen)):
        assert actual == sum(row.amount_fen for row in rows if row.nature == "transfer" and row.direction == direction)
    reference_net = sum(row.amount_fen for row in reference_rows if row.nature == "consumption") - sum(
        row.amount_fen for row in reference_rows if row.nature == "refund")
    assert summary.comparison.consumption_net_fen == reference_net
    assert summary.comparison.delta_fen == summary.consumption_net_fen - reference_net

    events = runtime.audit._events("D1", bills.task_id)
    reads_started = {event.payload.tool_call_id for event in events
                     if event.event_type == "tool.started"
                     and event.payload.tool_name == "bills.bank.list_transactions"}
    reads_finished = {event.payload.tool_call_id for event in events
                      if event.event_type == "tool.finished" and event.outcome == "succeeded"}
    assert len(reads_started) == len(bills_reads)
    assert reads_started <= reads_finished

    # The parent's own menu view carries the plan and current step facts.
    view = result.model_dump(mode="json")
    assert view["status"] in {"running", "waiting_input"}
    # The whole goal phase is reads: no bank ledger movement at all.
    assert submitted_ledger_count(runtime) == 0
    for account_id in account_ids:
        assert all(row["operation_id"].startswith("seed:") for row in
                   runtime.gateway._bank.store.list_ledger("U1", account_id))
    with closing(connect(runtime.gateway._bank.store.path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM bank_operations").fetchone()[0] == operations_before
    app.state.api.runtime.close()


def test_pension_and_birthday_goals_reach_their_real_flows(tmp_path):
    """All three life goals now reach their real modules (business 02/03 +
    platform 09 wiring); none is refused or faked."""
    app, runtime = wired_app(tmp_path)
    now = datetime.now(timezone.utc)
    runtime.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    from app.contracts.platform import StartTransferInput
    from app.memory.adapter import MemoryContext
    from app.modules.cross.entry import CrossEntry

    for task_id, goal, first_question in (
        ("PENSION", "养老金到了，帮我安排本月的钱", "账户"),
        ("BIRTHDAY", "帮我安排家人生日", "预算"),
    ):
        runtime.application.create_task(task_id, "U1", "S1", "D1", "R1", "running", {})
        saver = runtime.memory.checkpointer(MemoryContext("U1", "S1", "D1"), task_id)
        entry = CrossEntry(runtime.harness, saver, None, runtime.gateway._bank.clock,
                           birthday_ports_factory=runtime.birthday.ports_factory)
        started = entry.start(trusted(runtime, task_id),
                              StartTransferInput(request_id=uuid4(), intent_text=goal))
        assert started.status is TaskStatus.WAITING_INPUT, started.message
        assert first_question in started.message
        children = runtime.application.list_child_tasks("U1", "D1", task_id)
        # Reads ran through the real factories; nothing was written.
        assert all(relation.step_id in {"accounts", "subscriptions", "bills_details",
                                        "bills_compare"}
                   for relation in children)
    assert submitted_ledger_count(runtime) == 0
    app.state.api.runtime.close()


def test_original_transfer_entry_still_runs_in_the_same_composition(tmp_path):
    app, runtime = wired_app(tmp_path, start_at=1)
    now = datetime.now(timezone.utc)
    runtime.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    # The second scripted proposal is an ordinary transfer; the entry still
    # reaches its confirmation under the unchanged security gates.
    pending = runtime.harness.handle_message(trusted(runtime, "PLAIN"), uuid4(), "给妈妈转 500 元")
    assert pending.status is TaskStatus.WAITING_APPROVAL
    assert pending.interaction.kind == "confirmation"
    task = runtime.application.get_task("U1", "D1", "PLAIN")
    assert task.snapshot["capability_name"] == "transfer.start_transfer"
    assert runtime.application.list_child_tasks("U1", "D1", "PLAIN") == []
    app.state.api.runtime.close()
