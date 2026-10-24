"""Ticket v05-cross-platform/05: the real local composition mounts the cross module.

Natural life-goal routing, honest refusals for goals whose business module is not
delivered, traceable father-child links, zero bank writes on the read phase, and
the original single-business entry staying usable — all on build_runtime's real
factories, policy and stores.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.app import ApiConfig, create_app
from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext

from .local_demo import LocalDemoConfig, build_runtime
from .test_local_demo import ConnectorTestModel, configuration


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

    # A natural expense-reduction goal reaches the registered cross capability;
    # the harness creates the task itself with the request's own snapshot.
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
    # The real subscription inventory arrived; the typed-input gap in the real
    # bills entry fails honestly instead of faking a comparison.
    subscriptions = runtime.application.get_task("U1", "D1", by_step["subscriptions"].child_task_id)
    inventory = subscriptions.snapshot["result"]["data"]["list_result"]["items"]
    assert any(item["service_name"].startswith("优酷") for item in inventory)
    bills = runtime.application.get_task("U1", "D1", by_step["bills_compare"].child_task_id)
    assert bills.snapshot["result"]["status"] == "failed"

    # The parent's own menu view carries the plan and current step facts.
    view = result.model_dump(mode="json")
    assert view["status"] in {"running", "waiting_input"}
    # The whole goal phase is reads: no bank ledger movement at all.
    assert submitted_ledger_count(runtime) == 0
    app.state.api.runtime.close()


def test_undelivered_goals_are_refused_without_faking_success(tmp_path):
    """Pension arrived with v05-cross-business/02; only birthday is still an
    honestly-refused goal in this composition."""
    app, runtime = wired_app(tmp_path)
    now = datetime.now(timezone.utc)
    runtime.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    for task_id, goal, fragment in (
        ("BIRTHDAY", "帮我安排家人生日", "暂时不能办理"),
    ):
        runtime.application.create_task(task_id, "U1", "S1", "D1", "R1", "running", {})
        from app.contracts.platform import StartTransferInput
        from app.memory.adapter import MemoryContext
        from app.modules.cross.entry import CrossEntry
        saver = runtime.memory.checkpointer(MemoryContext("U1", "S1", "D1"), task_id)
        entry = CrossEntry(runtime.harness, saver, None, runtime.gateway._bank.clock)
        menu = entry.start(trusted(runtime, task_id),
                           StartTransferInput(request_id=uuid4(), intent_text=goal))
        assert menu.status is TaskStatus.WAITING_INPUT
        assert fragment in menu.message
        options = {option.label for option in menu.interaction.options}
        assert any("减" in label for label in options)
        # No children were dispatched for an undelivered goal.
        assert runtime.application.list_child_tasks("U1", "D1", task_id) == []
    # A pension goal now reaches the real registered cross module too (its
    # business module landed in v05-cross-business/02).
    runtime.application.create_task("PENSION", "U1", "S1", "D1", "R1", "running", {})
    from app.contracts.platform import StartTransferInput
    from app.memory.adapter import MemoryContext
    from app.modules.cross.entry import CrossEntry
    saver = runtime.memory.checkpointer(MemoryContext("U1", "S1", "D1"), "PENSION")
    entry = CrossEntry(runtime.harness, saver, None, runtime.gateway._bank.clock)
    pension = entry.start(trusted(runtime, "PENSION"),
                          StartTransferInput(request_id=uuid4(),
                                             intent_text="养老金到了，帮我安排本月的钱"))
    # The pension module asks its funds-basis question first (v05-cross-business/02);
    # reaching the registered module without faking an outcome is this ticket's bar.
    assert pension.status is TaskStatus.WAITING_INPUT
    assert pension.interaction is not None
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
