"""Cross06 integration: real Harness/F10 provenance, checkpoints and storage.

Bills returns contract-validated controlled facts; birthday money ports are
scripted. This is module/interface validation, not a bank/model/page E2E run.
Every database is under pytest's explicitly isolated absolute basetemp.
"""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from unittest.mock import patch

from app.contracts.bank import Transaction
from app.contracts.bills import AccountSourceAsOf, BillDetails, BillScope, SpendingSummary
from app.contracts.common import TaskStatus
from app.contracts.cross import BudgetCommitment, BudgetRef, CrossStartInput, CrossTaskView
from app.contracts.tasks import ModuleResult
from app.modules.bills.manifest import MANIFEST
from .test_cross_birthday import (NOW, ScriptedBirthdayPorts, birthday_composition,
    option_id, parent_trusted, store_delivery)


SCOPE = BillScope(account_ids=["A1"], start_at="2026-10-01T00:00:00+08:00",
                  end_at="2026-11-01T00:00:00+08:00")


@pytest.fixture
def env(tmp_path):
    assert tmp_path.is_absolute()
    ports = ScriptedBirthdayPorts()
    harness, entry, store = birthday_composition(tmp_path, ports)
    data = SimpleNamespace(ports=ports, harness=harness, entry=entry, store=store,
                           used=260000, changed=False, calls=0, rows=None, on_read=None)

    class Bills:
        def start(self, trusted, request, *, thread_id=None):
            data.calls += 1
            if data.on_read:
                data.on_read(request, data.calls)
            at = NOW + timedelta(microseconds=data.calls)
            sources = [AccountSourceAsOf(account_id=a, as_of=at) for a in request.scope.account_ids]
            rows = data.rows if data.rows is not None else ([Transaction(transaction_id="spent",
                account_id="A1", occurred_at=NOW, amount_fen=data.used, nature="consumption",
                category="shopping", direction="outflow", counterparty_id=None, counterparty_name="商户",
                counterparty_account_masked=None, channel="bank", summary="真实口径受控案例",
                original_transaction_id=None, original_occurred_at=None)] if data.used else [])
            rows = [r for r in rows if r.account_id in request.scope.account_ids
                    and request.scope.start_at <= r.occurred_at < request.scope.end_at]
            if request.mode == "details":
                result = BillDetails(scope=request.scope, category=None,
                                     transactions=sorted(rows, key=lambda t: (t.occurred_at, t.account_id, t.transaction_id)),
                                     source_as_of=sources, as_of=at)
            else:
                used = data.used + (1 if data.changed and data.calls % 3 == 0 else 0)
                result = SpendingSummary(scope=request.scope, as_of=at, source_as_of=sources,
                    transaction_count=len(rows), consumption_gross_fen=used, consumption_refund_fen=0,
                    consumption_net_fen=used, transfer_out_fen=0, transfer_in_fen=0,
                    categories=[], comparison=None)
            return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id, status="succeeded",
                data=result, message="受控L01事实", interaction=None, error=None, allowed_actions=[],
                recovery_required=False, recovery_reason=None)

        def checkpoint_context(self, trusted, *, thread_id=None):
            return None

    harness.registry.register_module(MANIFEST, lambda *_: Bills())
    store_delivery(store)
    data.who = parent_trusted()

    def begin(constraints=None, *, request=None):
        result = entry.start(data.who, CrossStartInput(request_id=request or uuid4(), goal="生日安排",
            scenario="birthday", constraints=constraints))
        task = store.get_task("U1", "D1", "PARENT")
        store.update_task("U1", "D1", "PARENT", task.revision, data.who.run_id, result.status,
            task.checkpoint_id, {**task.snapshot, "capability_name": "cross.start_task",
            "config_version": harness.planner.config_version, "trace_id": str(uuid4()),
            "result": result.model_dump(mode="json")})
        return result

    data.begin = begin
    data.answer = lambda result, label: harness.resume(data.who, {"choice": option_id(result, label)})
    data.submit = lambda result, label, request=None: harness.resume_budget_input(data.who,
        input_request_id=request or uuid4(), interaction_id=result.interaction.interaction_id,
        selected_option_id=option_id(result, label))

    def begin_other(task_id, given):
        from app.memory.adapter import MemoryContext
        from .entry import CrossEntry
        who = data.who.model_copy(update={"task_id": task_id})
        store.create_task(task_id, "U1", "S1", "D1", who.run_id, "running", {})
        other = CrossEntry(harness, harness.memory.checkpointer(MemoryContext("U1", "S1", "D1"), task_id),
                           None, lambda: NOW, lambda _: ports)
        result = other.start(who, CrossStartInput(request_id=uuid4(), goal="生日安排", scenario="birthday", constraints=given))
        task = store.get_task("U1", "D1", task_id)
        store.update_task("U1", "D1", task_id, task.revision, who.run_id, result.status, task.checkpoint_id,
            {"capability_name": "cross.start_task", "config_version": harness.planner.config_version,
             "trace_id": str(uuid4()), "result": result.model_dump(mode="json")})
        return who, result

    data.begin_other = begin_other
    return data


def constraints(**overrides):
    return {"personal_limit_fen": 300000, "scope": SCOPE.model_dump(mode="json"),
        "purpose": "生日安排", "budget_fen": 50000, "payer_account_id": "A1",
        "deliver_by": "2026-10-30T18:00:00+08:00", "delivery_ref": "deliver-ref-0001", **overrides}


def adopt(env):
    candidate = env.begin(constraints())
    completion = env.submit(candidate, "采用个人预算")
    return candidate, completion


def basket(env, adopted):
    current = env.answer(adopted, "继续生日")
    for label in ("康乃馨", "蛋糕", "就选这些", "采用并开始"):
        current = env.answer(current, label)
    return current


def test_bg01_complete_constraints_in_request_identity(env):
    request = uuid4()
    env.begin(constraints(), request=request)
    env.entry.start(env.who, CrossStartInput(request_id=request, goal="生日安排", scenario="birthday", constraints=constraints()))
    for field, value in [("budget_fen", 40000), ("purpose", "全部消费"),
                         ("deliver_by", "2026-10-30T19:00:00+08:00"),
                         ("budget_ref", {"budget_id": "other", "version": 1})]:
        with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
            env.entry.start(env.who, CrossStartInput(request_id=request, goal="生日安排", scenario="birthday",
                constraints=constraints(**{field: value})))


def test_bg03_true_f10_is_one_exact_adoption_not_execution(env):
    candidate = env.begin(constraints())
    assert CrossTaskView.model_validate(candidate.data).budget.adopted is False
    request = uuid4()
    completion = env.submit(candidate, "采用个人预算", request)
    records = env.store.list_adopted_budgets("U1", "D1")
    assert len(records) == 1 and records[0].version == 1
    assert records[0].adoption_interaction_id == candidate.interaction.interaction_id
    assert records[0].scope == SCOPE and records[0].source_task_id == "PARENT"
    assert env.submit(candidate, "采用个人预算", request) == completion
    assert env.ports.freeze_executes == 0
    assert CrossTaskView.model_validate(completion.result.data).budget.remaining_fen == 40000
    assert env.harness.budget_input_origin(env.who) is None


def test_bg04_model_with_the_real_option_cannot_adopt(env):
    candidate = env.begin(constraints())
    rejected = env.answer(candidate, "采用个人预算")
    assert "专用" in rejected.message
    assert env.store.list_adopted_budgets("U1", "D1") == []
    assert env.ports.freeze_executes == 0


def test_bg06_modify_rotates_snapshot_and_old_interaction_is_rejected(env):
    candidate = env.begin(constraints())
    amount = env.submit(candidate, "修改个人限额").result
    fresh = env.harness.resume(env.who, {"text": "3500元"})
    assert fresh.interaction.interaction_id != candidate.interaction.interaction_id
    assert CrossTaskView.model_validate(fresh.data).budget.personal_limit_fen == 350000
    with pytest.raises(ValueError):
        env.submit(candidate, "采用个人预算")
    env.submit(fresh, "采用个人预算")
    assert env.store.list_adopted_budgets("U1", "D1")[0].personal_limit_fen == 350000


def test_bg06_decline_creates_no_adoption_and_stops_unresolved_constraint(env):
    candidate = env.begin(constraints())
    result = env.submit(candidate, "不采用").result
    assert result.status == TaskStatus.CANCELLED
    assert env.store.list_adopted_budgets("U1", "D1") == []
    assert env.ports.freeze_executes == 0


def test_bg10_insufficient_room_stops_before_freeze(env):
    _, adopted = adopt(env)
    result = env.answer(adopted.result, "继续生日")
    for label in ("康乃馨", "蛋糕", "就选这些"):
        result = env.answer(result, label)
    assert "个人预算" in result.message and "暂停" in result.message
    assert env.ports.freeze_executes == 0
    assert env.store.list_budget_commitments("U1", "D1", env.store.list_adopted_budgets("U1", "D1")[0].budget_id) == []


def test_bg18_pending_is_durable_before_the_write_and_unknown_keeps_it(env):
    env.used = 0
    env.ports.freeze_script = "unknown"
    _, adopted = adopt(env)
    result = basket(env, adopted.result)
    ref = env.store.list_adopted_budgets("U1", "D1")[0]
    original = env.ports.freeze_execute

    def observe(context, plan):
        rows = env.store.list_budget_commitments("U1", "D1", ref.budget_id)
        assert len(rows) == 1 and rows[0].state == "pending" and rows[0].unconsumed_fen == 50000
        assert rows[0].operation_ids
        return original(context, plan)

    env.ports.freeze_execute = observe
    unknown = env.harness.resume(env.who, {"choice": "approve"})
    hold = env.store.list_budget_commitments("U1", "D1", ref.budget_id)[0]
    assert hold.state == "unknown" and hold.unconsumed_fen == 50000
    stopped = env.harness.resume(env.who, {"cancel": True})
    assert "核实" in stopped.message and env.ports.freeze_executes == 1
    assert env.store.list_budget_commitments("U1", "D1", ref.budget_id)[0].unconsumed_fen == 50000


def test_bg16_changing_window_is_not_zero_spending(env):
    env.changed = True
    result = env.begin(constraints())
    assert "变化" in result.message and env.store.list_adopted_budgets("U1", "D1") == []
    assert env.ports.freeze_executes == 0


def test_bg02_supplied_zero_and_foreign_delivery_never_write(env):
    result = env.begin({"budget_fen": 0, "payer_account_id": "A1"})
    assert "上限为0" in result.message and env.ports.freeze_executes == 0


def test_bg08_invalid_reference_does_not_fall_back_to_no_budget(env):
    result = env.begin({"budget_ref": {"budget_id": "other-user", "version": 1}})
    assert "原预算" in result.message and env.ports.freeze_executes == 0


@pytest.mark.parametrize("cancel_before_recovery", [False, True])
def test_bg07_adoption_commit_before_result_checkpoint_recovers_read_only(env, cancel_before_recovery):
    candidate = env.begin(constraints())
    request = uuid4()
    original = env.store.adopt_budget
    calls = []

    def crash(*args, **kwargs):
        calls.append(kwargs)
        original(*args, **kwargs)
        raise RuntimeError("after durable adoption before result checkpoint")

    with patch.object(env.store, "adopt_budget", side_effect=crash):
        with pytest.raises(RuntimeError):
            env.submit(candidate, "采用个人预算", request)
    record = env.store.list_adopted_budgets("U1", "D1")[0]
    if cancel_before_recovery:
        env.harness.resume(env.who, {"cancel": True})
    recovered = env.submit(candidate, "采用个人预算", request)
    assert recovered.result.status == TaskStatus.NEEDS_ATTENTION
    assert "已采用" in recovered.result.message
    assert len(calls) == 1
    assert env.store.list_adopted_budgets("U1", "D1") == [record]
    assert env.ports.freeze_executes == 0 and env.harness.budget_input_origin(env.who) is None
    if cancel_before_recovery:
        assert env.store.get_task("U1", "D1", "PARENT").status == TaskStatus.CANCELLED
    else:
        resumed = env.harness.resume(env.who, {})
        assert "已核实原个人预算" in resumed.message
        assert CrossTaskView.model_validate(resumed.data).budget.adopted
        assert env.submit(candidate, "采用个人预算", request) == recovered
        continued = env.answer(resumed, "继续生日")
        assert "康乃馨" in str(continued.interaction)
        assert env.store.list_adopted_budgets("U1", "D1") == [record]
        assert env.ports.freeze_executes == 0


@pytest.mark.parametrize("status", ["needs_attention", "blocked"])
def test_bg19_release_not_verified_keeps_real_adopted_occupation(env, status):
    from .birthday_ports import ReleaseOutcome
    env.used = 0
    env.ports.release_status = status
    env.ports.finalize = lambda *_: ReleaseOutcome(status=status)
    _, adopted = adopt(env)
    basket(env, adopted.result)
    env.harness.resume(env.who, {"choice": "approve"})
    result = env.harness.resume(env.who, {"cancel": True})
    budget = env.store.list_adopted_budgets("U1", "D1")[0]
    holds = env.store.list_budget_commitments("U1", "D1", budget.budget_id)
    assert len(holds) == 1 and holds[0].unconsumed_fen == 50000 and holds[0].state == "active"
    assert env.ports.order_executes == [] and result.status not in {TaskStatus.CANCELLED, TaskStatus.SUCCEEDED}


def test_bg11_receipt_consumption_and_ledger_are_counted_once(env):
    from .birthday_ports import WriteOutcome
    env.used = 0
    env.rows = []
    def capture(context, plan, item, order_id):
        env.used += item["amount_fen"]
        tid = f"settled-{item['product_id']}"
        env.rows.append(Transaction(transaction_id=tid, account_id="A1", occurred_at=NOW,
            amount_fen=item["amount_fen"], direction="outflow", nature="consumption", category="shopping",
            counterparty_id=None, counterparty_name="商户", counterparty_account_masked=None,
            channel="bank", summary="脚本化核销事实", original_transaction_id=None, original_occurred_at=None))
        return WriteOutcome(executed=True, state="completed", operation_id=str(uuid4()),
            result=SimpleNamespace(receipt=SimpleNamespace(transaction_id=tid,
                captured_amount_fen=item["amount_fen"], remaining_fen=50000-env.used)))
    env.ports.capture_execute = capture
    _, adopted = adopt(env)
    current = basket(env, adopted.result)
    for _ in range(8):
        if current.status != TaskStatus.WAITING_APPROVAL:
            break
        current = env.harness.resume(env.who, {"choice": "approve"})
    assert current.status == TaskStatus.SUCCEEDED
    budget = env.store.list_adopted_budgets("U1", "D1")[0]
    hold = env.store.list_budget_commitments("U1", "D1", budget.budget_id, include_closed=True)[0]
    assert hold.state == "closed" and hold.committed_fen == 46700 and hold.unconsumed_fen == 0
    assert len(hold.settled_transaction_ids) == 2
    view = CrossTaskView.model_validate(current.data).budget
    assert view.used_fen == 46700 and view.remaining_fen == 253300


def choose(env, who, result, label):
    return env.harness.resume(who, {"choice": option_id(result, label)})


def basket_for(env, who, result):
    for label in ("康乃馨", "蛋糕", "就选这些", "采用并开始"):
        result = choose(env, who, result, label)
    return result


def test_bg13_two_initial_candidates_cannot_silently_replace_each_other(env):
    a = env.begin(constraints())
    who_b, b = env.begin_other("SECOND", constraints())
    barrier = Barrier(2)
    def submit(who, candidate):
        barrier.wait()
        return env.harness.resume_budget_input(who, input_request_id=uuid4(),
            interaction_id=candidate.interaction.interaction_id,
            selected_option_id=option_id(candidate, "采用个人预算")).result
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit, env.who, a), pool.submit(submit, who_b, b)]
        results = [f.result() for f in futures]
    records = env.store.list_adopted_budgets("U1", "D1", include_superseded=True)
    assert len(records) == 1 and records[0].version == 1
    assert sum("已采用" in r.message for r in results) == 1
    assert any("发生变化" in r.message for r in results)
    assert env.ports.freeze_executes == 0


def test_bg12_two_tasks_real_connections_only_one_reservation_wins(env):
    env.used = 0
    env.ports.freeze_script = "unknown"
    candidate = env.begin(constraints(personal_limit_fen=60000))
    adopted = env.submit(candidate, "采用个人预算").result
    gate_a = basket(env, adopted)
    who_b, picked = env.begin_other("SECOND", {"budget_fen": 50000, "payer_account_id": "A1",
        "deliver_by": "2026-10-30T18:00:00+08:00"})
    # A task-owned controlled detail is required; no cross-task reference reuse.
    env.store.store_controlled_detail("second-ref", "U1", "D1", "SECOND", "delivery",
        {"recipient_name": "测试", "phone": "13800000000", "address": "隔离测试地址"},
        NOW.isoformat())
    picked = env.harness.resume(who_b, {"text": "second-ref"})
    gate_b = basket_for(env, who_b, picked)
    assert gate_a.status == gate_b.status == TaskStatus.WAITING_APPROVAL
    barrier = Barrier(2)
    def approve(who):
        barrier.wait()
        return env.harness.resume(who, {"choice": "approve"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result() for f in [pool.submit(approve, env.who), pool.submit(approve, who_b)]]
    record = env.store.list_adopted_budgets("U1", "D1")[0]
    holds = env.store.list_budget_commitments("U1", "D1", record.budget_id)
    assert len(holds) == 1 and holds[0].unconsumed_fen == 50000
    assert env.ports.freeze_executes == 1
    assert any("可新增额度" in r.message for r in results)


def test_bg17_version_change_keeps_old_unknown_hold_and_allows_only_original_close(env):
    env.used = 0
    env.ports.freeze_script = "unknown"
    env.ports.released_amount_fen = 50000
    _, adopted = adopt(env)
    basket(env, adopted.result)
    unknown = env.harness.resume(env.who, {"choice": "approve"})
    v1 = env.store.list_adopted_budgets("U1", "D1")[0]
    who_b, candidate = env.begin_other("SECOND", constraints(personal_limit_fen=40000, delivery_ref=None))
    v2_result = env.harness.resume_budget_input(who_b, input_request_id=uuid4(),
        interaction_id=candidate.interaction.interaction_id,
        selected_option_id=option_id(candidate, "采用个人预算"))
    history = env.store.list_adopted_budgets("U1", "D1", include_superseded=True)
    assert [(r.version, r.status) for r in history] == [(1, "superseded"), (2, "active")]
    assert history[0].budget_id == history[1].budget_id == v1.budget_id
    assert env.store.list_budget_commitments("U1", "D1", v1.budget_id)[0].budget_ref.version == 1
    stopped = env.harness.resume(env.who, {"cancel": True})
    closed = choose(env, env.who, stopped, "核实原操作")
    assert closed.status == TaskStatus.CANCELLED and env.ports.freeze_executes == 1
    assert env.store.list_budget_commitments("U1", "D1", v1.budget_id) == []
    assert env.ports.order_executes == []


@pytest.mark.parametrize("missing", ["receipt", "transaction"])
def test_bg24_missing_cross_task_settlement_facts_never_become_zero(env, missing):
    env.used = 0
    _, adopted = adopt(env)
    record = env.store.list_adopted_budgets("U1", "D1")[0]
    op = uuid4()
    env.store.create_task("HISTORY", "U1", "S1", "D1", "RH", "succeeded", {"result": {"data": {
        "steps": [] if missing == "receipt" else [{"action": "bank.capture_frozen", "status": "succeeded",
        "operation_id": str(op), "result_ref": "not-yet-in-ledger", "amount_fen": 19900}]}}})
    env.store.register_budget_commitment("U1", "D1", BudgetCommitment(
        budget_ref=BudgetRef(budget_id=record.budget_id, version=1), task_id="HISTORY", commitment_id="history",
        committed_fen=19900, unconsumed_fen=0, freeze_id="old-freeze", operation_ids=[op],
        settled_transaction_ids=["not-yet-in-ledger"], state="closed", updated_at=NOW))
    paused = env.answer(adopted.result, "继续生日")
    for label in ("康乃馨", "蛋糕", "就选这些"):
        paused = env.answer(paused, label)
    assert "暂停" in paused.message
    assert env.ports.freeze_executes == 0


def test_real_l01_and_dedicated_origin_adopt_without_any_bank_write(tmp_path):
    """Read/adoption integration only: real L01 + bank reads, no money chain."""
    from app.agent_platform.test_birthday_runtime_wiring import composition, trusted
    from app.agent_platform.test_cross_runtime_wiring import submitted_ledger_count
    from app.contracts.bills import BillSummarizeInput
    runtime, entry = composition(tmp_path)
    who = trusted(runtime)
    try:
        from .plan import month_range
        start, end = month_range(runtime.gateway._bank.clock(), 0)
        scope = BillScope(account_ids=["A1"], start_at=start, end_at=end)
        expected = runtime.harness.dispatch_child(who, "bills.summarize", uuid4(),
            BillSummarizeInput(scope=scope), step_id="budget-oracle", plan_revision=1)
        assert expected.status == TaskStatus.SUCCEEDED
        used = SpendingSummary.model_validate(expected.data).consumption_net_fen
        candidate = entry.start(who, CrossStartInput(request_id=uuid4(), goal="生日安排", scenario="birthday",
            constraints={"personal_limit_fen": 300000, "scope": scope, "purpose": "生日安排"}))
        assert CrossTaskView.model_validate(candidate.data).budget.used_fen == used
        task = runtime.application.get_task("U1", "D1", who.task_id)
        runtime.application.update_task("U1", "D1", who.task_id, task.revision, who.run_id,
            candidate.status, task.checkpoint_id, {**task.snapshot, "config_version": runtime.harness.planner.config_version,
            "result": candidate.model_dump(mode="json")})
        completion = runtime.harness.resume_budget_input(who, input_request_id=uuid4(),
            interaction_id=candidate.interaction.interaction_id, selected_option_id=option_id(candidate, "采用个人预算"))
        record = runtime.application.list_adopted_budgets("U1", "D1")[0]
        assert record.scope == scope and CrossTaskView.model_validate(completion.result.data).budget.adopted
        assert submitted_ledger_count(runtime) == 0
        assert runtime.gateway._bank.birthday.store.path.resolve().is_relative_to(tmp_path.resolve())
    finally:
        runtime.gateway.close()


def test_bg15_closed_settlement_ledger_lag_is_not_extra_room(env):
    env.used = 0
    env.rows = []
    candidate = env.begin(constraints(personal_limit_fen=40000, budget_fen=30000))
    adopted = env.submit(candidate, "采用个人预算").result
    record = env.store.list_adopted_budgets("U1", "D1")[0]
    op = uuid4()
    tid = "late-ledger"
    env.store.create_task("HISTORY", "U1", "S1", "D1", "RH", "succeeded", {"result": {"data": {"steps": [
        {"action": "bank.capture_frozen", "status": "succeeded", "operation_id": str(op),
         "result_ref": tid, "amount_fen": 19900}]}}})
    env.store.register_budget_commitment("U1", "D1", BudgetCommitment(
        budget_ref=BudgetRef(budget_id=record.budget_id, version=1), task_id="HISTORY", commitment_id="history",
        committed_fen=19900, unconsumed_fen=0, freeze_id="fz-history", operation_ids=[op],
        settled_transaction_ids=[tid], state="closed", updated_at=NOW))
    def arrive(request, call):
        if call == 4:  # after the stable current window, before the original-scope lookup
            env.used = 19900
            env.rows.append(Transaction(transaction_id=tid, account_id="A1", occurred_at=NOW,
                amount_fen=19900, nature="consumption", category="shopping", direction="outflow",
                counterparty_id=None, counterparty_name="商户", counterparty_account_masked=None, channel="bank",
                summary="延后可见的受控案例", original_transaction_id=None, original_occurred_at=None))
    result = env.answer(adopted, "继续生日")
    env.calls = 0
    env.on_read = arrive
    result = env.answer(result, "康乃馨")
    result = env.answer(result, "就选这些")
    assert "201.00" in result.message and "199.00" in result.message
    assert env.ports.freeze_executes == 0


def test_bg23_new_budget_after_freeze_requires_explicit_binding_and_real_remainder(env):
    from .birthday_ports import WriteOutcome
    env.used = 0
    env.ports.freeze_execute = lambda *_: WriteOutcome(executed=True, state="completed",
        operation_id=str(uuid4()), result=SimpleNamespace(receipt=SimpleNamespace(
            freeze_id="prior-freeze", frozen_amount_fen=50000, remaining_fen=50000)))
    picked = env.begin({k: v for k, v in constraints().items()
                        if k not in {"personal_limit_fen", "scope", "purpose"}})
    current = basket_for(env, env.who, picked)
    current = env.harness.resume(env.who, {"choice": "approve"})
    assert env.store.list_adopted_budgets("U1", "D1") == []
    who_b, candidate = env.begin_other("SECOND", constraints(delivery_ref=None))
    env.harness.resume_budget_input(who_b, input_request_id=uuid4(),
        interaction_id=candidate.interaction.interaction_id,
        selected_option_id=option_id(candidate, "采用个人预算"))
    paused = env.harness.resume(env.who, {"choice": "approve"})
    assert "冻结后" in paused.message and env.ports.order_executes == []
    candidate = env.answer(paused, "查看当前个人预算候选")
    newly_adopted = env.submit(candidate, "采用个人预算").result
    current = env.answer(newly_adopted, "继续生日")
    record = env.store.list_adopted_budgets("U1", "D1")[0]
    hold = env.store.list_budget_commitments("U1", "D1", record.budget_id)[0]
    assert hold.unconsumed_fen == 50000 and hold.freeze_id == "prior-freeze"
    assert current.status == TaskStatus.WAITING_APPROVAL and env.ports.order_executes == []


def test_bg14_old_quote_cannot_use_consumption_occupation_gap(env):
    """B got a gate before A's freeze; A settles before B can submit."""
    from .birthday_ports import WriteOutcome
    env.used = 0
    env.rows = []
    candidate = env.begin(constraints(personal_limit_fen=60000))
    adopted = env.submit(candidate, "采用个人预算").result
    gate_a = basket(env, adopted)
    who_b, delivery = env.begin_other("SECOND", {"budget_fen": 20000, "payer_account_id": "A1",
                                               "deliver_by": "2026-10-30T18:00:00+08:00"})
    env.store.store_controlled_detail("second-ref", "U1", "D1", "SECOND", "delivery",
        {"recipient_name": "测试", "phone": "13800000000", "address": "隔离案例"}, NOW.isoformat())
    current = env.harness.resume(who_b, {"text": "second-ref"})
    for label in ("康乃馨", "就选这些", "采用并开始"):
        current = choose(env, who_b, current, label)
    assert current.status == gate_a.status == TaskStatus.WAITING_APPROVAL
    env.harness.resume(env.who, {"choice": "approve"})  # A freeze
    env.harness.resume(env.who, {"choice": "approve"})  # A order
    def paid(*_):
        env.used = 19900
        env.rows.append(Transaction(transaction_id="a-paid", account_id="A1", occurred_at=NOW,
            amount_fen=19900, nature="consumption", category="shopping", direction="outflow",
            counterparty_id=None, counterparty_name="商户", counterparty_account_masked=None, channel="bank",
            summary="受控已核销", original_transaction_id=None, original_occurred_at=None))
        return WriteOutcome(executed=True, state="completed", operation_id=str(uuid4()),
            result=SimpleNamespace(receipt=SimpleNamespace(transaction_id="a-paid", captured_amount_fen=19900,
                                                          remaining_fen=30100)))
    env.ports.capture_execute = paid
    env.harness.resume(env.who, {"choice": "approve"})
    rejected = env.harness.resume(who_b, {"choice": "approve"})
    budget = env.store.list_adopted_budgets("U1", "D1")[0]
    holds = env.store.list_budget_commitments("U1", "D1", budget.budget_id)
    assert len(holds) == 1 and holds[0].unconsumed_fen == 30100
    assert env.used == 19900 and env.ports.freeze_executes == 1
    assert "暂停" in rejected.message


@pytest.mark.parametrize("old_state", ["closed", "unknown"])
def test_bg15_old_scope_consumption_excluded_but_old_inflight_counts(env, old_state):
    env.used = 0
    september = BillScope(account_ids=["A1"], start_at="2026-09-01T00:00:00+08:00",
                          end_at="2026-10-01T00:00:00+08:00")
    candidate = env.begin(constraints(scope=september.model_dump(mode="json")))
    env.submit(candidate, "采用个人预算")
    old = env.store.list_adopted_budgets("U1", "D1")[0]
    env.store.create_task("OLD", "U1", "S1", "D1", "RO", "needs_attention", {})
    env.store.register_budget_commitment("U1", "D1", BudgetCommitment(
        budget_ref=BudgetRef(budget_id=old.budget_id, version=1), task_id="OLD", commitment_id="old-scope",
        committed_fen=50000 if old_state == "unknown" else 19900,
        unconsumed_fen=50000 if old_state == "unknown" else 0, freeze_id="old-freeze", operation_ids=[uuid4()],
        settled_transaction_ids=[] if old_state == "unknown" else ["september-paid"], state=old_state, updated_at=NOW))
    who_b, candidate = env.begin_other("SECOND", constraints(personal_limit_fen=60000, delivery_ref=None,
        budget_ref={"budget_id": old.budget_id, "version": 1}))
    adopted = env.harness.resume_budget_input(who_b, input_request_id=uuid4(),
        interaction_id=candidate.interaction.interaction_id,
        selected_option_id=option_id(candidate, "采用个人预算")).result
    current = choose(env, who_b, adopted, "继续生日")
    env.store.store_controlled_detail("second-ref", "U1", "D1", "SECOND", "delivery",
        {"recipient_name": "测试", "phone": "13800000000", "address": "隔离案例"}, NOW.isoformat())
    current = env.harness.resume(who_b, {"text": "second-ref"})
    for label in ("康乃馨", "蛋糕", "就选这些"):
        current = choose(env, who_b, current, label)
    assert ("暂停" in current.message) is (old_state == "unknown")
    assert env.ports.freeze_executes == 0
    assert env.store.list_budget_commitments("U1", "D1", old.budget_id, include_closed=True)[0].state == old_state


def test_bg04_plain_amount_cannot_skip_unadopted_personal_candidate(env):
    candidate = env.begin(constraints())
    result = env.harness.resume(env.who, {"text": "500元"})
    assert result.interaction.interaction_id == candidate.interaction.interaction_id
    assert CrossTaskView.model_validate(result.data).budget.adopted is False
    assert env.store.list_adopted_budgets("U1", "D1") == []
    assert env.ports.freeze_executes == 0


def test_bg16_text_after_failed_candidate_read_cannot_skip_required_budget(env):
    env.changed = True
    paused = env.begin(constraints())
    result = env.harness.resume(env.who, {"text": "500元"})
    assert "暂停" in result.message and env.store.list_adopted_budgets("U1", "D1") == []
    env.changed = False
    candidate = env.answer(result, "重新核对预算")
    assert CrossTaskView.model_validate(candidate.data).budget.adopted is False
    assert env.ports.freeze_executes == 0


def test_bg16_modified_candidate_retry_reads_facts_again(env):
    candidate = env.begin(constraints())
    env.submit(candidate, "修改个人限额")
    env.changed = True
    paused = env.harness.resume(env.who, {"text": "3500元"})
    calls = env.calls
    env.changed = False
    retried = env.answer(paused, "重新核对预算")
    assert env.calls > calls
    assert CrossTaskView.model_validate(retried.data).budget.personal_limit_fen == 350000
    env.submit(retried, "采用个人预算")
    assert env.store.list_adopted_budgets("U1", "D1")[0].personal_limit_fen == 350000


def test_bg12_verify_pause_cannot_resize_or_replace_original_reservation(env):
    from app.contracts.tasks import InteractionRequest
    env.used = 0
    candidate = env.begin(constraints(personal_limit_fen=100000))
    adopted = env.submit(candidate, "采用个人预算").result
    basket(env, adopted)
    env.ports.freeze_script = "verify_once"
    env.ports.verify_challenge = InteractionRequest(interaction_id="verify-1", kind="verification",
        prompt="请输入验证码", required_fields=["code"], options=[], record_ref="challenge-1")
    waiting = env.harness.resume(env.who, {"choice": "approve"})
    record = env.store.list_adopted_budgets("U1", "D1")[0]
    original = env.store.list_budget_commitments("U1", "D1", record.budget_id)[0]
    env.changed = True
    paused = env.harness.resume(env.who, {"choice": "resume"})
    labels = [option.label for option in paused.interaction.options]
    assert not any("调整本次" in label or "个人预算候选" in label for label in labels)
    amount = env.harness.resume(env.who, {"text": "800元"})
    assert amount.interaction == paused.interaction
    assert env.store.list_budget_commitments("U1", "D1", record.budget_id)[0] == original
    env.changed = False
    retry = env.answer(amount, "重新核对预算")
    assert retry.interaction == waiting.interaction
    sent = []
    execute = env.ports.freeze_execute
    def observe(context, plan):
        sent.append(plan.freeze_amount_fen)
        return execute(context, plan)
    env.ports.freeze_execute = observe
    env.harness.resume(env.who, {"choice": "resume"})
    assert sent == [50000]
    current = env.store.list_budget_commitments("U1", "D1", record.budget_id)[0]
    assert current.committed_fen == current.unconsumed_fen == 50000
    assert original.operation_ids[0] in current.operation_ids


def test_bg07_interruption_before_adoption_requires_a_new_input(env):
    candidate = env.begin(constraints())
    request = uuid4()
    with patch.object(env.store, "adopt_budget", side_effect=RuntimeError("before adoption")):
        with pytest.raises(RuntimeError):
            env.submit(candidate, "采用个人预算", request)
    assert env.store.list_adopted_budgets("U1", "D1") == []
    fresh = env.harness.resume(env.who, {})
    assert fresh.interaction.interaction_id != candidate.interaction.interaction_id
    with pytest.raises(ValueError):
        env.submit(candidate, "采用个人预算", request)
    env.submit(fresh, "采用个人预算")
    assert len(env.store.list_adopted_budgets("U1", "D1")) == 1
    assert env.ports.freeze_executes == 0


def test_bg18_interrupted_submit_restores_original_pending_without_new_reservation(env):
    env.used = 0
    _, adopted = adopt(env)
    gate = basket(env, adopted.result)
    record = env.store.list_adopted_budgets("U1", "D1")[0]
    with patch.object(env.ports, "freeze_execute", side_effect=RuntimeError("before port submission")):
        with pytest.raises(RuntimeError):
            env.harness.resume(env.who, {"choice": "approve"})
    original = env.store.list_budget_commitments("U1", "D1", record.budget_id)[0]
    restored = env.harness.resume(env.who, {})
    assert restored.interaction == gate.interaction
    env.harness.resume(env.who, {"choice": "approve"})
    rows = env.store.list_budget_commitments("U1", "D1", record.budget_id)
    assert len(rows) == 1 and rows[0].committed_fen == 50000
    assert original.operation_ids[0] in rows[0].operation_ids
    assert env.ports.freeze_executes == 1
