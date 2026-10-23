"""Ticket v05-cross-platform/02: durable task relations, D1 arrangements, budget seams.

The storage layer owns persistence and serialized check-and-register seams only;
business amounts, adoption truth and bank rules stay with their callers.
"""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from app.contracts import AdoptedArrangement, BudgetCommitment
from app.storage import ApplicationStore
from app.storage.application import ArrangementConflictError, BudgetOccupationExceededError


NOW = "2026-10-24T18:00:00+08:00"
DEBIT_SCOPE = {
    "account_ids": ["own_daily"],
    "start_at": "2026-10-01T00:00:00+08:00",
    "end_at": "2026-11-01T00:00:00+08:00",
}


def prepared_store(path, tasks=("PARENT", "TASK_A", "TASK_B")):
    store = ApplicationStore(path)
    store.create_session("S1", "U1", "D1", NOW, "2026-10-24T23:59:59+08:00")
    for index, task_id in enumerate(tasks):
        store.create_task(task_id, "U1", "S1", "D1", f"R{index}", "running", {})
    return store


def arrangement(task_id: str, arrangement_id: str, plan_revision: int = 1,
                payer: str = "own_daily") -> AdoptedArrangement:
    return AdoptedArrangement.model_validate({
        "arrangement_id": arrangement_id, "user_id": "U1", "demo_round_id": "D1",
        "source_task_id": task_id, "plan_revision": plan_revision,
        "payer_account_id": payer, "funds_basis": "selected_income",
        "income_transaction_ids": ["tx_pension_01"], "base_fen": 500000,
        "living_reserve_fen": 150000, "reserve_includes_known_debits": True,
        "upcoming_debit_scope": DEBIT_SCOPE, "known_debits_fen": 3900,
        "adopted_at": NOW, "adoption_interaction_id": "I1", "status": "active",
    })


def commitment(commitment_id: str, task_id: str, unconsumed_fen: int, *,
               budget_id: str = "B1", version: int = 1,
               state: str = "pending") -> BudgetCommitment:
    # Deterministic per commitment so an idempotent replay compares equal.
    suffix = int.from_bytes(commitment_id.encode(), "big") % (1 << 48)
    return BudgetCommitment.model_validate({
        "budget_ref": {"budget_id": budget_id, "version": version}, "task_id": task_id,
        "commitment_id": commitment_id, "committed_fen": unconsumed_fen,
        "unconsumed_fen": unconsumed_fen, "freeze_id": None,
        "operation_ids": [f"00000000-0000-4000-8000-{suffix:012x}"],
        "settled_transaction_ids": [],
        "state": state, "updated_at": NOW,
    })


def test_task_relations_survive_restart_and_reject_reparenting(tmp_path):
    path = tmp_path / "application.sqlite3"
    store = prepared_store(path)
    store.create_task("CHILD", "U1", "S1", "D1", "R9", "running", {})
    store.link_child_task("U1", "D1", "PARENT", "CHILD", "step_pay", 2)
    # Repeated linking never creates a second relation or task.
    store.link_child_task("U1", "D1", "PARENT", "CHILD", "step_pay", 2)
    relations = store.list_child_tasks("U1", "D1", "PARENT")
    assert [(r.child_task_id, r.step_id, r.plan_revision) for r in relations] == [("CHILD", "step_pay", 2)]
    assert store.parent_of_task("U1", "D1", "CHILD") == "PARENT"
    assert store.parent_of_task("U1", "D1", "PARENT") is None
    with pytest.raises(ValueError):
        store.link_child_task("U1", "D1", "TASK_A", "CHILD", "step_x", 1)
    with pytest.raises(ValueError):
        store.link_child_task("U1", "D1", "PARENT", "PARENT", "step_x", 1)
    with pytest.raises(ValueError):
        store.link_child_task("U2", "D1", "PARENT", "CHILD", "step_pay", 2)
    with pytest.raises(ValueError):
        store.link_child_task("U1", "D2", "PARENT", "CHILD", "step_pay", 2)
    with pytest.raises(ValueError):
        store.link_child_task("U1", "D1", "PARENT", "MISSING", "step_pay", 2)

    # A grandchild keeps a bounded lineage for D1 holder checks (ticket 03).
    store.link_child_task("U1", "D1", "CHILD", "TASK_A", "leaf", 1)
    assert store.task_lineage("U1", "D1", "TASK_A") == ["TASK_A", "CHILD", "PARENT"]

    reopened = ApplicationStore(path)
    assert reopened.parent_of_task("U1", "D1", "CHILD") == "PARENT"
    assert reopened.task_lineage("U1", "D1", "TASK_A") == ["TASK_A", "CHILD", "PARENT"]


def test_arrangement_acquire_is_exclusive_per_account_and_survives_restart(tmp_path):
    path = tmp_path / "application.sqlite3"
    store = prepared_store(path)
    first = store.acquire_arrangement(arrangement("TASK_A", "arr_01"))
    assert first.status == "active"
    assert store.get_active_arrangement("U1", "D1", "own_daily").record.arrangement_id == "arr_01"

    # Same id, same facts: idempotent retry; same id, different facts: rejected.
    store.acquire_arrangement(arrangement("TASK_A", "arr_01"))
    with pytest.raises(ValueError):
        store.acquire_arrangement(arrangement("TASK_A", "arr_01", plan_revision=2))

    # A different task cannot take the same account (D1).
    with pytest.raises(ArrangementConflictError) as conflict:
        store.acquire_arrangement(arrangement("TASK_B", "arr_02"))
    assert conflict.value.holder_task_id == "TASK_A"
    assert store.get_active_arrangement("U1", "D1", "own_daily").record.arrangement_id == "arr_01"

    # The same parent revising its plan supersedes its own record, not the account.
    store.acquire_arrangement(arrangement("TASK_A", "arr_03", plan_revision=2))
    assert store.get_arrangement("U1", "D1", "arr_01").status == "superseded"
    assert store.get_active_arrangement("U1", "D1", "own_daily").record.arrangement_id == "arr_03"

    # Another account is unaffected; wrong scope sees nothing.
    store.acquire_arrangement(arrangement("TASK_B", "arr_04", payer="own_savings"))
    assert store.get_active_arrangement("U2", "D1", "own_daily") is None
    assert store.get_active_arrangement("U1", "D2", "own_daily") is None

    store.close_arrangement("U1", "D1", "arr_03")
    assert store.get_active_arrangement("U1", "D1", "own_daily") is None
    assert store.get_arrangement("U1", "D1", "arr_03").status == "closed"
    with pytest.raises(ValueError):
        store.close_arrangement("U1", "D1", "arr_03")

    reopened = ApplicationStore(path)
    assert reopened.get_arrangement("U1", "D1", "arr_01").status == "superseded"
    assert reopened.get_active_arrangement("U1", "D1", "own_savings").record.source_task_id == "TASK_B"


def test_competing_arrangement_acquires_admit_exactly_one_holder(tmp_path):
    path = tmp_path / "application.sqlite3"
    prepared_store(path)
    stores = [ApplicationStore(path), ApplicationStore(path)]
    outcomes = []

    def acquire(store: ApplicationStore, task_id: str):
        try:
            return ("acquired", store.acquire_arrangement(arrangement(task_id, f"arr_{task_id}")))
        except ArrangementConflictError as exc:
            return ("conflict", exc.holder_task_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda pair: acquire(*pair), zip(stores, ("TASK_A", "TASK_B"))))

    assert sorted(outcome[0] for outcome in outcomes) == ["acquired", "conflict"]
    active = ApplicationStore(path).get_active_arrangement("U1", "D1", "own_daily")
    assert active.record.source_task_id in {"TASK_A", "TASK_B"}
    holder = active.record.source_task_id
    loser = next(outcome for outcome in outcomes if outcome[0] == "conflict")
    assert loser[1] == holder


def test_budget_commitment_seam_blocks_interleaved_overcommitment(tmp_path):
    path = tmp_path / "application.sqlite3"
    store = prepared_store(path)
    first = store.register_budget_commitment(
        "U1", "D1", commitment("C1", "TASK_A", 40000), max_in_flight_fen=50000,
    )
    assert first.unconsumed_fen == 40000
    # Idempotent retry and a mutated replay of the same id.
    store.register_budget_commitment("U1", "D1", commitment("C1", "TASK_A", 40000))
    with pytest.raises(ValueError):
        store.register_budget_commitment("U1", "D1", commitment("C1", "TASK_A", 30000))
    # The second task cannot spend the same remaining budget (M17 seam).
    with pytest.raises(BudgetOccupationExceededError) as exceeded:
        store.register_budget_commitment(
            "U1", "D1", commitment("C2", "TASK_B", 20000), max_in_flight_fen=50000,
        )
    assert exceeded.value.in_flight_fen == 60000
    # Unknown occupations stay listed and keep consuming the cap; closed ones do not.
    store.update_budget_commitment(
        "U1", "D1", "C1", commitment("C1", "TASK_A", 40000, state="unknown"),
    )
    with pytest.raises(BudgetOccupationExceededError):
        store.register_budget_commitment(
            "U1", "D1", commitment("C3", "TASK_A", 15000), max_in_flight_fen=50000,
        )
    store.update_budget_commitment(
        "U1", "D1", "C1", commitment("C1", "TASK_A", 0, state="closed"),
    )
    store.register_budget_commitment(
        "U1", "D1", commitment("C3", "TASK_A", 15000), max_in_flight_fen=50000,
    )
    listed = store.list_budget_commitments("U1", "D1", "B1")
    assert {item.commitment_id for item in listed} == {"C3"}
    # A new budget version still shares one budget_id occupation list (§5.4).
    store.register_budget_commitment(
        "U1", "D1", commitment("C4", "TASK_B", 10000, version=2), max_in_flight_fen=50000,
    )
    with pytest.raises(ValueError):
        store.update_budget_commitment(
            "U1", "D1", "C4", commitment("C4", "TASK_A", 10000, version=2),
        )
    with pytest.raises(ValueError):
        store.update_budget_commitment(
            "U2", "D1", "C4", commitment("C4", "TASK_B", 0, version=2, state="closed"),
        )
    with pytest.raises(ValueError):
        store.update_budget_commitment(
            "U1", "D2", "C4", commitment("C4", "TASK_B", 0, version=2, state="closed"),
        )
    assert [item for item in store.list_budget_commitments("U1", "D1", "B1")
            if item.commitment_id == "C4"][0].state == "pending"
    with pytest.raises(ValueError):
        store.register_budget_commitment("U1", "D1", commitment("C5", "MISSING", 1000))
    reopened = ApplicationStore(path)
    assert len(reopened.list_budget_commitments("U1", "D1", "B1", include_closed=True)) == 3


def test_controlled_details_stay_scoped_to_owner_round_and_task(tmp_path):
    path = tmp_path / "application.sqlite3"
    store = prepared_store(path)
    payload = {"recipient_name": "张三", "phone": "13800000000", "address": "某市某区 1 号"}
    store.store_controlled_detail("dref_1", "U1", "D1", "TASK_A", "delivery", payload, NOW)
    stored = store.get_controlled_detail("U1", "D1", "dref_1")
    assert stored.payload == payload and stored.task_id == "TASK_A"
    # Idempotent same facts; a mutated replay or scope change is rejected.
    store.store_controlled_detail("dref_1", "U1", "D1", "TASK_A", "delivery", payload, NOW)
    with pytest.raises(ValueError):
        store.store_controlled_detail(
            "dref_1", "U1", "D1", "TASK_A", "delivery", payload | {"phone": "13900000000"}, NOW,
        )
    with pytest.raises(ValueError):
        store.store_controlled_detail("dref_1", "U1", "D1", "TASK_A", "payee", payload, NOW)
    with pytest.raises(ValueError):
        store.store_controlled_detail("dref_2", "U1", "D1", "MISSING", "delivery", payload, NOW)
    # Wrong owner, round or task filter sees nothing, not an error.
    assert store.get_controlled_detail("U2", "D1", "dref_1") is None
    assert store.get_controlled_detail("U1", "D2", "dref_1") is None
    assert store.get_controlled_detail("U1", "D1", "dref_1", task_id="TASK_B") is None
    reopened = ApplicationStore(path)
    assert reopened.get_controlled_detail("U1", "D1", "dref_1").payload == payload


def test_v4_database_upgrades_to_v5_without_losing_existing_rows(tmp_path):
    path = tmp_path / "application.sqlite3"
    store = prepared_store(path)
    store.acquire_arrangement(arrangement("TASK_A", "arr_old"))
    # Rewind to the v4 shape the way an old on-disk database would look.
    from app.storage.database import connect
    with connect(path) as connection:
        connection.execute("DROP TABLE task_relations")
        connection.execute("DROP INDEX IF EXISTS arrangements_one_active_per_account")
        connection.execute("DROP TABLE arrangements")
        connection.execute("DROP TABLE budget_commitments")
        connection.execute("DROP TABLE controlled_details")
        connection.execute("PRAGMA user_version = 4")
        connection.commit()
    upgraded = ApplicationStore(path)
    assert upgraded.get_task("U1", "D1", "TASK_A") is not None
    assert upgraded.get_active_arrangement("U1", "D1", "own_daily") is None
    upgraded.link_child_task("U1", "D1", "PARENT", "TASK_B", "step_1", 1)
    assert upgraded.parent_of_task("U1", "D1", "TASK_B") == "PARENT"
