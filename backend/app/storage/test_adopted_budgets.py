"""v05-adopted-budget-storage/01: real SQLite adoption, replay and version seams."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.contracts import AdoptedBudget, BudgetRef
from app.storage import ApplicationStore
from app.storage.application import SCHEMA_VERSION
from app.storage.database import connect
from app.storage.test_cross_records import commitment, prepared_store


NOW = "2026-10-25T10:00:00+08:00"
SCOPE = {
    "account_ids": ["own_daily"],
    "start_at": "2026-10-01T00:00:00+08:00",
    "end_at": "2026-11-01T00:00:00+08:00",
}


def budget(**changes):
    return AdoptedBudget.model_validate({
        "budget_id": "B1", "user_id": "U1", "demo_round_id": "D1",
        "source_task_id": "TASK_A", "version": 1, "scope": SCOPE,
        "purpose": "本月购物", "personal_limit_fen": 100000,
        "adopted_at": NOW, "adoption_interaction_id": "I1", "status": "active",
    } | changes)


def ref(version=1, budget_id="B1"):
    return BudgetRef(budget_id=budget_id, version=version)


def test_adoption_reads_original_facts_and_survives_restart(tmp_path):
    path = tmp_path / "app.sqlite"
    store = prepared_store(path)
    record = budget()
    assert store.get_adopted_budget("U1", "D1", ref()) is None
    assert store.list_adopted_budgets("U1", "D1") == []
    assert store.adopt_budget("U1", "D1", record, expected_task_revision=0) == record
    reopened = ApplicationStore(path)
    assert reopened.get_adopted_budget("U1", "D1", ref()) == record
    assert reopened.list_adopted_budgets("U1", "D1") == [record]
    assert reopened.get_adopted_budget("U1", "D1", ref(99)) is None


def test_revision_preserves_history_and_old_occupations(tmp_path):
    path = tmp_path / "app.sqlite"
    store = prepared_store(path)
    first = budget()
    store.adopt_budget("U1", "D1", first, expected_task_revision=0)
    occupied = commitment("C1", "TASK_B", 30000)
    store.register_budget_commitment("U1", "D1", occupied)
    store.update_task("U1", "D1", "TASK_A", 0, "R2", "waiting_input", None, {})
    second = budget(version=2, adoption_interaction_id="I2", purpose="礼物",
                    scope=SCOPE | {"account_ids": ["own_savings"]}, personal_limit_fen=80000)
    store.adopt_budget("U1", "D1", second, expected_task_revision=1, previous_version=1)
    reopened = ApplicationStore(path)
    assert reopened.get_adopted_budget("U1", "D1", ref()).status == "superseded"
    assert reopened.get_adopted_budget("U1", "D1", ref(2)) == second
    assert reopened.list_adopted_budgets("U1", "D1") == [second]
    history = reopened.list_adopted_budgets("U1", "D1", include_superseded=True)
    assert [(r.version, r.status, r.source_task_id) for r in history] == [
        (1, "superseded", "TASK_A"), (2, "active", "TASK_A"),
    ]
    assert history[0].scope == first.scope
    assert history[0].personal_limit_fen == first.personal_limit_fen
    assert reopened.list_budget_commitments("U1", "D1", "B1") == [occupied]
    # Old request after supersession returns history and cannot resurrect version 1.
    replay = reopened.adopt_budget("U1", "D1", first, expected_task_revision=0)
    assert replay.status == "superseded"
    assert reopened.list_adopted_budgets("U1", "D1") == [second]


@pytest.mark.parametrize("changes", [
    {"personal_limit_fen": 90000}, {"purpose": "别的用途"},
    {"scope": SCOPE | {"account_ids": ["own_savings"]}},
    {"budget_id": "B2"}, {"adopted_at": "2026-10-25T11:00:00+08:00"},
])
def test_interaction_replay_rejects_changed_snapshot(tmp_path, changes):
    store = prepared_store(tmp_path / "app.sqlite")
    original = budget()
    store.adopt_budget("U1", "D1", original, expected_task_revision=0)
    assert store.adopt_budget("U1", "D1", original, expected_task_revision=0) == original
    with pytest.raises(ValueError, match="interaction conflicts"):
        store.adopt_budget("U1", "D1", budget(**changes), expected_task_revision=0)
    assert store.list_adopted_budgets("U1", "D1", include_superseded=True) == [original]


def test_interaction_cannot_adopt_another_version_or_task_revision(tmp_path):
    store = prepared_store(tmp_path / "app.sqlite")
    store.adopt_budget("U1", "D1", budget(), expected_task_revision=0)
    with pytest.raises(ValueError, match="interaction conflicts"):
        store.adopt_budget("U1", "D1", budget(version=2),
                           expected_task_revision=0, previous_version=1)
    with pytest.raises(ValueError, match="interaction conflicts"):
        store.adopt_budget("U1", "D1", budget(), expected_task_revision=1)
    assert store.get_adopted_budget("U1", "D1", ref()).status == "active"


@pytest.mark.parametrize("version,previous", [(2, None), (3, 1), (1, 1), (3, 2), (1, 0)])
def test_rejects_skipped_or_stale_versions_without_superseding(tmp_path, version, previous):
    store = prepared_store(tmp_path / "app.sqlite")
    store.adopt_budget("U1", "D1", budget(), expected_task_revision=0)
    with pytest.raises(ValueError):
        store.adopt_budget("U1", "D1", budget(version=version, adoption_interaction_id="I2"),
                           expected_task_revision=0, previous_version=previous)
    assert store.list_adopted_budgets("U1", "D1", include_superseded=True) == [budget()]


def test_source_revision_guard_and_missing_source_task(tmp_path):
    store = prepared_store(tmp_path / "app.sqlite")
    store.update_task("U1", "D1", "TASK_A", 0, "R2", "waiting_input", None, {})
    with pytest.raises(ValueError, match="source task changed"):
        store.adopt_budget("U1", "D1", budget(), expected_task_revision=0)
    with pytest.raises(ValueError, match="task is not in scope"):
        store.adopt_budget("U1", "D1", budget(source_task_id="missing"), expected_task_revision=0)
    with pytest.raises(ValueError, match="only an active"):
        store.adopt_budget("U1", "D1", budget(status="superseded"), expected_task_revision=1)
    assert store.list_adopted_budgets("U1", "D1", include_superseded=True) == []


def test_real_actor_round_and_source_task_isolation(tmp_path):
    path = tmp_path / "app.sqlite"
    store = prepared_store(path)
    for session, user, round_id, task in [("S2", "U2", "D1", "OTHER_USER"),
                                           ("S3", "U1", "D2", "OTHER_ROUND")]:
        store.create_session(session, user, round_id, NOW, "2026-10-26T00:00:00+08:00")
        store.create_task(task, user, session, round_id, "RUN", "waiting_input", {})
    store.adopt_budget("U1", "D1", budget(), expected_task_revision=0)
    for user, round_id, task in [("U2", "D1", "OTHER_USER"), ("U1", "D2", "OTHER_ROUND")]:
        with pytest.raises(ValueError, match="budget is not in scope"):
            store.adopt_budget(user, round_id, budget(), expected_task_revision=0)
        # Forging model actor fields still cannot claim a task owned by somebody else.
        with pytest.raises(ValueError, match="task is not in scope"):
            store.adopt_budget(user, round_id, budget(user_id=user, demo_round_id=round_id),
                               expected_task_revision=0)
        assert store.get_adopted_budget(user, round_id, ref()) is None
        assert store.list_adopted_budgets(user, round_id, include_superseded=True) == []
        # A genuinely scoped adoption is independent, even with the same budget id.
        own = budget(user_id=user, demo_round_id=round_id, source_task_id=task)
        store.adopt_budget(user, round_id, own, expected_task_revision=0)
        assert ApplicationStore(path).get_adopted_budget(user, round_id, ref()) == own
    assert store.get_adopted_budget("U1", "D1", ref()) == budget()


@pytest.mark.parametrize("is_revision", [False, True])
def test_competing_connections_produce_one_active_version(tmp_path, is_revision):
    path = tmp_path / "app.sqlite"
    store = prepared_store(path)
    if is_revision:
        store.adopt_budget("U1", "D1", budget(), expected_task_revision=0)
    stores = [ApplicationStore(path), ApplicationStore(path)]

    def adopt(index):
        record = budget(version=2 if is_revision else 1,
                        adoption_interaction_id=f"race-{index}",
                        source_task_id="TASK_A" if index == 0 else "TASK_B",
                        personal_limit_fen=50000 + index)
        try:
            stores[index].adopt_budget("U1", "D1", record, expected_task_revision=0,
                                      previous_version=1 if is_revision else None)
            return "adopted"
        except ValueError as exc:
            assert "active version changed" in str(exc)
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(adopt, [0, 1])) == ["adopted", "conflict"]
    reopened = ApplicationStore(path)
    active = reopened.list_adopted_budgets("U1", "D1")
    assert len(active) == 1
    assert active[0].version == (2 if is_revision else 1)
    history = reopened.list_adopted_budgets("U1", "D1", include_superseded=True)
    assert len(history) == (2 if is_revision else 1)
    if is_revision:
        assert history[0].status == "superseded"


def test_simultaneous_exact_replay_returns_one_record(tmp_path):
    path = tmp_path / "app.sqlite"
    prepared_store(path)
    stores = [ApplicationStore(path), ApplicationStore(path)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda s: s.adopt_budget("U1", "D1", budget(), expected_task_revision=0), stores,
        ))
    assert results == [budget(), budget()]
    assert stores[0].list_adopted_budgets("U1", "D1", include_superseded=True) == [budget()]


def test_v5_upgrade_retains_existing_tasks_and_occupations(tmp_path):
    path = tmp_path / "app.sqlite"
    store = prepared_store(path)
    occupied = commitment("C1", "TASK_B", 30000)
    store.register_budget_commitment("U1", "D1", occupied)
    with connect(path) as connection:
        connection.execute("DROP TABLE adopted_budgets")
        connection.execute("PRAGMA user_version = 5")
    upgraded = ApplicationStore(path)
    assert upgraded.get_task("U1", "D1", "TASK_A") is not None
    assert upgraded.list_budget_commitments("U1", "D1", "B1") == [occupied]
    upgraded.adopt_budget("U1", "D1", budget(), expected_task_revision=0)
    reopened = ApplicationStore(path)
    assert reopened.get_adopted_budget("U1", "D1", ref()) == budget()
    assert reopened.list_adopted_budgets("U1", "D2") == []
    with connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
