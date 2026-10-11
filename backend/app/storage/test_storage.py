"""Persistent boundaries required by the v0.3 transfer path."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3
from typing import TypedDict
from uuid import uuid4

import pytest
from langgraph.graph import StateGraph
from langgraph.types import Command, interrupt

from app.storage import ApplicationStore, StoragePaths
from app.storage.mock_bank.repository import BankAccount, MockBankStore


NOW = "2026-09-28T10:00:00+08:00"


def prepared_task(path):
    store = ApplicationStore(path)
    store.create_session("S1", "U1", "D1", NOW, "2026-09-28T12:00:00+08:00")
    task = store.create_task("T1", "U1", "S1", "D1", "R1", "waiting_approval", {"step": "confirm"})
    return store, task


def active_session_window():
    created_at = datetime.now(timezone.utc)
    return created_at.isoformat(), (created_at + timedelta(days=1)).isoformat()


def test_application_scope_and_operation_identity_survive_restart(tmp_path):
    paths = StoragePaths(tmp_path)
    store, task = prepared_task(paths.application)
    assert task.checkpoint_thread_id
    store.bind_ref("U1", "D1", "T1", "confirmation", "C1")
    store.bind_ref("U1", "D1", "T1", "verification", "V1")
    store.bind_ref("U1", "D1", "T1", "memory", "M1")
    store.create_task("T2", "U1", "S1", "D1", "R2", "running", {})
    store.bind_ref("U1", "D1", "T2", "verification", "V1")
    store.bind_ref("U1", "D1", "T2", "memory", "M1")
    with pytest.raises(ValueError):
        store.bind_ref("U1", "D1", "T2", "confirmation", "C1")
    store.create_session("S3", "U1", "D1", NOW, "2026-09-28T12:00:00+08:00")
    store.create_task("T4", "U1", "S3", "D1", "R4", "running", {})
    store.bind_ref("U1", "D1", "T4", "memory", "M1")
    with pytest.raises(ValueError):
        store.bind_ref("U1", "D1", "T4", "verification", "V1")
    store.create_session("S2", "U2", "D1", NOW, "2026-09-28T12:00:00+08:00")
    store.create_task("T3", "U2", "S2", "D1", "R3", "running", {})
    with pytest.raises(ValueError):
        store.bind_ref("U2", "D1", "T3", "verification", "V1")
    with pytest.raises(ValueError):
        store.bind_ref("U2", "D1", "T3", "memory", "M1")
    operation_id = str(uuid4())
    first = store.reserve_operation("U1", "D1", "T1", operation_id, "bank.submit_transfer", {"amount_fen": 50000})
    assert first.state == "reserved"
    assert store.reserve_operation("U1", "D1", "T1", operation_id, "bank.submit_transfer", {"amount_fen": 50000}) == first
    with pytest.raises(ValueError):
        store.reserve_operation("U1", "D1", "T1", operation_id, "bank.submit_transfer", {"amount_fen": 60000})
    assert store.record_operation_result("U1", "D1", operation_id, "unknown", None).state == "unknown"
    assert store.record_operation_result("U1", "D1", operation_id, "succeeded", "RECEIPT1").state == "succeeded"
    with pytest.raises(ValueError):
        store.record_operation_result("U1", "D1", operation_id, "failed", "ERROR1")
    store = ApplicationStore(paths.application)
    assert store.get_session("U1", "D1", "S1").session_id == "S1"
    assert store.get_session("U2", "D1", "S1") is None
    assert store.get_task("U1", "D1", "T1").checkpoint_thread_id == task.checkpoint_thread_id
    assert store.get_operation("U1", "D1", operation_id).result_ref == "RECEIPT1"
    assert store.get_operation("U2", "D1", operation_id) is None
    assert store.get_task("U2", "D1", "T1") is None
    assert store.get_task("U1", "D2", "T1") is None
    for kind, record_id in (("confirmation", "C1"), ("verification", "V1"), ("memory", "M1")):
        assert store.has_ref("U1", "D1", "T1", kind, record_id)
        assert not store.has_ref("U2", "D1", "T1", kind, record_id)
        assert not store.has_ref("U1", "D2", "T1", kind, record_id)
    assert store.has_ref("U1", "D1", "T2", "verification", "V1")
    assert store.has_ref("U1", "D1", "T2", "memory", "M1")
    with pytest.raises(ValueError):
        store.checkpoint_saver("U2", "D1", "T1")
    with pytest.raises(ValueError):
        store.bind_ref("U2", "D1", "T1", "confirmation", "C2")


def test_task_operation_list_is_scoped_and_keeps_reserved_operations(tmp_path):
    store, _ = prepared_task(StoragePaths(tmp_path).application)
    first = store.reserve_operation(
        "U1", "D1", "T1", "OP1", "bank.submit_transfer", {"amount_fen": 50000},
    )
    second = store.reserve_operation(
        "U1", "D1", "T1", "OP2", "bank.submit_transfer", {"amount_fen": 25000},
    )
    store.create_session("S2", "U2", "D1", NOW, "2026-09-28T12:00:00+08:00")
    store.create_task("T2", "U2", "S2", "D1", "R2", "running", {})

    assert store.list_task_operations("U1", "D1", "T1") == [first, second]
    assert not hasattr(first, "created_sequence")
    assert not hasattr(store.list_task_operations("U1", "D1", "T1")[0], "created_sequence")
    with sqlite3.connect(store.path) as connection:
        connection.execute("""UPDATE tool_operations SET rowid = CASE operation_id
            WHEN 'OP1' THEN 100 WHEN 'OP2' THEN 1 END""")
    assert store.list_task_operations("U1", "D1", "T1") == [first, second]
    assert store.list_task_operations("U2", "D1", "T2") == []
    with pytest.raises(ValueError, match="task is not in scope"):
        store.list_task_operations("U2", "D1", "T1")


def test_application_v3_operation_order_migrates_to_explicit_sequence(tmp_path):
    store, _ = prepared_task(StoragePaths(tmp_path).application)
    first = store.reserve_operation(
        "U1", "D1", "T1", "OP1", "bank.submit_transfer", {"amount_fen": 50000},
    )
    second = store.reserve_operation(
        "U1", "D1", "T1", "OP2", "bank.submit_transfer", {"amount_fen": 25000},
    )
    with sqlite3.connect(store.path) as connection:
        connection.executescript("""
            ALTER TABLE tool_operations RENAME TO tool_operations_v4;
            CREATE TABLE tool_operations (
                operation_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES tasks(task_id),
                user_id TEXT NOT NULL,
                demo_round_id TEXT NOT NULL,
                action_name TEXT NOT NULL,
                parameters_digest TEXT NOT NULL,
                state TEXT NOT NULL,
                result_ref TEXT
            );
            INSERT INTO tool_operations
                SELECT operation_id, task_id, user_id, demo_round_id, action_name,
                       parameters_digest, state, result_ref
                FROM tool_operations_v4 ORDER BY created_sequence;
            DROP TABLE tool_operations_v4;
            PRAGMA user_version = 3;
        """)

    migrated = ApplicationStore(store.path)
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
    assert migrated.list_task_operations("U1", "D1", "T1") == [first, second]


def test_langgraph_interrupt_resumes_from_original_task_after_reopen(tmp_path):
    paths = StoragePaths(tmp_path)
    store, task = prepared_task(paths.application)

    class GraphState(TypedDict):
        amount: int

    def after_confirmation(state: GraphState):
        approved = interrupt("confirm transfer")
        return {"amount": state["amount"] if approved else 0}

    builder = StateGraph(GraphState)
    builder.add_node("confirm", after_confirmation)
    builder.set_entry_point("confirm")
    builder.set_finish_point("confirm")
    config = {"configurable": {"thread_id": task.checkpoint_thread_id}}
    graph = builder.compile(checkpointer=store.checkpoint_saver("U1", "D1", "T1"))
    paused = asyncio.run(graph.ainvoke({"amount": 50000}, config))
    assert paused["__interrupt__"]
    checkpoint = graph.get_state(config)
    assert checkpoint.next == ("confirm",)
    store.update_task("U1", "D1", "T1", 0, "R1", "waiting_approval",
                      checkpoint.config["configurable"]["checkpoint_id"], {"step": "confirm"})

    reopened = ApplicationStore(paths.application)
    original = reopened.get_task("U1", "D1", "T1")
    assert original.checkpoint_id
    resumed_graph = builder.compile(checkpointer=reopened.checkpoint_saver("U1", "D1", "T1"))
    assert resumed_graph.invoke(Command(resume=True), config)["amount"] == 50000
    with pytest.raises(ValueError):
        reopened.checkpoint_saver("U1", "D1", "T1").get_tuple(
            {"configurable": {"thread_id": "another-task"}},
        )


def test_bank_ledger_and_operation_are_one_transaction(tmp_path):
    paths = StoragePaths(tmp_path)
    bank = MockBankStore(paths.bank)
    bank.seed_account(BankAccount("A1", "U1", "class_i", "active", 100000, 0, 0))
    parameters = {"payer_account_id": "A1", "amount_fen": 50000}
    operation_id = str(uuid4())
    result = {"operation_status": "succeeded", "transaction_id": "TX1"}
    changes = [("A1", 0, 50000, 0)]
    ledger = [("TX1", "A1", 50000, "outflow", "transfer", "transfer", NOW)]
    first = bank.commit_operation(
        "U1", operation_id, "bank.submit_transfer", parameters, "succeeded",
        result, NOW, changes, ledger,
    )
    assert bank.commit_operation(
        "U1", operation_id, "bank.submit_transfer", parameters, "succeeded",
        {"ignored": True}, NOW, changes, ledger,
    ) == first
    bank = MockBankStore(paths.bank)
    assert bank.get_account("U1", "A1").book_balance_fen == 50000
    assert len(bank.list_ledger("U1", "A1")) == 1
    assert bank.get_operation("U1", operation_id) == first
    assert bank.get_operation("U2", operation_id) is None
    assert bank.get_account("U2", "A1") is None
    with pytest.raises(ValueError):
        bank.list_ledger("U2", "A1")
    with pytest.raises(ValueError):
        bank.commit_operation(
            "U1", operation_id, "bank.submit_transfer", {"amount_fen": 60000},
            "succeeded", result, NOW, [], [],
        )
    with pytest.raises(sqlite3.IntegrityError):
        bank.commit_operation(
            "U1", str(uuid4()), "bank.submit_transfer", parameters, "succeeded",
            result, NOW, [("A1", 1, 0, 0)], [("TX1", "A1", 50000, "outflow", "transfer", "transfer", NOW)],
        )
    assert bank.get_account("U1", "A1").book_balance_fen == 50000
    assert len(bank.list_ledger("U1", "A1")) == 1


def test_processing_bank_operation_settles_once_and_survives_reopen(tmp_path):
    path = StoragePaths(tmp_path).bank
    bank = MockBankStore(path)
    bank.seed_account(BankAccount("A1", "U1", "class_i", "active", 100000, 0, 0))
    operation_id = str(uuid4())
    parameters = {"payer_account_id": "A1", "amount_fen": 50000}
    processing = bank.commit_operation(
        "U1", operation_id, "bank.submit_transfer", parameters, "processing",
        {"operation_status": "processing"}, NOW, [], [],
    )
    assert processing.status == "processing"
    assert bank.get_account("U1", "A1").book_balance_fen == 100000
    with pytest.raises(ValueError):
        bank.commit_operation(
            "U1", str(uuid4()), "bank.submit_transfer", parameters, "processing",
            {}, NOW, [("A1", 0, 50000, 0)], [],
        )

    bank = MockBankStore(path)
    changes = [("A1", 0, 50000, 0)]
    ledger = [("TX1", "A1", 50000, "outflow", "transfer", "transfer", NOW)]
    with pytest.raises(sqlite3.IntegrityError):
        bank.finalize_operation(
            "U1", operation_id, "bank.submit_transfer", parameters, "succeeded",
            {"operation_status": "succeeded"}, NOW, changes, ledger + ledger,
        )
    assert bank.get_operation("U1", operation_id).status == "processing"
    assert bank.get_account("U1", "A1").book_balance_fen == 100000
    final = bank.finalize_operation(
        "U1", operation_id, "bank.submit_transfer", parameters, "succeeded",
        {"operation_status": "succeeded", "transaction_id": "TX1"}, NOW,
        changes, ledger,
    )
    assert final.status == "succeeded"
    assert bank.finalize_operation(
        "U1", operation_id, "bank.submit_transfer", parameters, "succeeded",
        {"ignored": True}, NOW, changes, ledger,
    ) == final
    assert bank.commit_operation(
        "U1", operation_id, "bank.submit_transfer", parameters, "succeeded",
        {"ignored": True}, NOW, changes, ledger,
    ) == final
    with pytest.raises(ValueError):
        bank.finalize_operation(
            "U1", operation_id, "bank.submit_transfer", {"amount_fen": 60000},
            "succeeded", {}, NOW, [], [],
        )
    with pytest.raises(ValueError):
        bank.finalize_operation(
            "U1", operation_id, "bank.submit_transfer", parameters,
            "failed", {}, NOW, [], [],
        )
    reopened = MockBankStore(path)
    assert reopened.get_operation("U1", operation_id) == final
    assert reopened.get_account("U1", "A1").book_balance_fen == 50000
    assert len(reopened.list_ledger("U1", "A1")) == 1


def test_bank_v1_migration_preserves_operation_result(tmp_path):
    path = StoragePaths(tmp_path).bank
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE bank_operations (
            operation_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, action_name TEXT NOT NULL,
            parameters_digest TEXT NOT NULL, status TEXT NOT NULL,
            result_json TEXT NOT NULL, recorded_at TEXT NOT NULL
        )""")
        connection.execute(
            "INSERT INTO bank_operations VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("old", "U1", "bank.submit_transfer", "digest", "processing", "{}", NOW),
        )
        connection.execute("PRAGMA user_version = 1")
    bank = MockBankStore(path)
    assert bank.get_operation("U1", "old").updated_at == NOW
    assert MockBankStore(path).get_operation("U1", "old").status == "processing"


def test_storage_files_and_migrations_remain_separate(tmp_path):
    paths = StoragePaths(tmp_path)
    app = ApplicationStore(paths.application)
    bank = MockBankStore(paths.bank)
    ApplicationStore(paths.application)
    MockBankStore(paths.bank)
    assert paths.application != paths.bank
    assert not hasattr(app, "get_account")
    assert not hasattr(app, "list_ledger")
    assert bank.get_operation("U1", str(uuid4())) is None


def test_task_session_transition_preserves_task_and_invalidates_old_authorizations(tmp_path):
    path = StoragePaths(tmp_path).application
    store, original = prepared_task(path)
    created_at, expires_at = active_session_window()
    store.create_session("S2", "U1", "D1", created_at, expires_at)
    store.bind_ref("U1", "D1", "T1", "confirmation", "C1")
    store.bind_ref("U1", "D1", "T1", "verification", "V1")
    store.bind_ref("U1", "D1", "T1", "memory", "M1")
    operation = store.reserve_operation(
        "U1", "D1", "T1", "OP1", "bank.submit_transfer", {"amount_fen": 50000},
    )

    transitioned = store.transition_task_session(
        "U1", "D1", "T1", "S1", "S2", 0,
    )

    assert transitioned.session_id == "S2"
    assert transitioned.task_id == original.task_id
    assert transitioned.checkpoint_thread_id == original.checkpoint_thread_id
    assert transitioned.revision == 1
    assert transitioned.snapshot == original.snapshot
    assert store.get_operation("U1", "D1", "OP1") == operation
    assert not store.has_ref("U1", "D1", "T1", "confirmation", "C1")
    assert not store.has_ref("U1", "D1", "T1", "verification", "V1")
    assert store.has_ref("U1", "D1", "T1", "memory", "M1")

    # The security service may issue a newer version of this confirmation ID
    # for the new session. The storage binding follows that versioned record;
    # the security service still rejects answers carrying the old version.
    store.bind_ref("U1", "D1", "T1", "confirmation", "C1")
    assert store.has_ref("U1", "D1", "T1", "confirmation", "C1")
    assert not store.has_ref("U1", "D1", "T1", "verification", "V1")

    retried = store.transition_task_session(
        "U1", "D1", "T1", "S1", "S2", 0,
    )
    assert retried == transitioned
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM task_session_transitions").fetchone()[0] == 1


def test_task_session_transition_rejects_invalid_scope_expiry_and_stale_revision(tmp_path):
    path = StoragePaths(tmp_path).application
    store, _ = prepared_task(path)
    created_at, expires_at = active_session_window()
    store.create_session("OTHER_USER", "U2", "D1", created_at, expires_at)
    store.create_session("OTHER_ROUND", "U1", "D2", created_at, expires_at)
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=2)
    store.create_session(
        "EXPIRED", "U1", "D1", (expired_at - timedelta(days=1)).isoformat(), expired_at.isoformat(),
    )
    store.create_session("S2", "U1", "D1", created_at, expires_at)

    for target in ("OTHER_USER", "OTHER_ROUND", "EXPIRED"):
        with pytest.raises(ValueError):
            store.transition_task_session("U1", "D1", "T1", "S1", target, 0)
    with pytest.raises(ValueError):
        store.transition_task_session("U1", "D1", "T1", "OTHER_USER", "S2", 0)
    with pytest.raises(ValueError):
        store.transition_task_session("U1", "D1", "T1", "S1", "S2", 1)

    assert store.get_task("U1", "D1", "T1").session_id == "S1"
    assert store.get_task("U1", "D1", "T1").revision == 0


def test_session_transition_retry_must_match_a_recorded_transition(tmp_path):
    path = StoragePaths(tmp_path).application
    store, _ = prepared_task(path)
    created_at, expires_at = active_session_window()
    store.create_session("S2", "U1", "D1", created_at, expires_at)
    store.create_task("T2", "U1", "S2", "D1", "R2", "waiting_approval", {})
    store.update_task("U1", "D1", "T2", 0, "R2", "waiting_approval", None, {})

    with pytest.raises(ValueError):
        store.transition_task_session("U1", "D1", "T2", "S1", "S2", 0)

    assert store.get_task("U1", "D1", "T2").session_id == "S2"
    assert store.get_task("U1", "D1", "T2").revision == 1


def test_concurrent_task_session_transitions_allow_one_target_only(tmp_path):
    path = StoragePaths(tmp_path).application
    store, _ = prepared_task(path)
    created_at, expires_at = active_session_window()
    store.create_session("S2", "U1", "D1", created_at, expires_at)
    store.create_session("S3", "U1", "D1", created_at, expires_at)

    def transition(target):
        return store.transition_task_session("U1", "D1", "T1", "S1", target, 0)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(transition, target) for target in ("S2", "S3")]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except ValueError as error:
                outcomes.append(error)

    assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, ValueError) for outcome in outcomes) == 1
    assert store.get_task("U1", "D1", "T1").revision == 1


def test_task_reference_session_scope_migrates_from_application_v1(tmp_path):
    path = StoragePaths(tmp_path).application
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, demo_round_id TEXT NOT NULL,
                created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                UNIQUE(session_id, user_id, demo_round_id)
            );
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, session_id TEXT NOT NULL,
                demo_round_id TEXT NOT NULL, run_id TEXT NOT NULL, status TEXT NOT NULL,
                revision INTEGER NOT NULL, checkpoint_thread_id TEXT NOT NULL UNIQUE,
                checkpoint_id TEXT, snapshot_json TEXT NOT NULL
            );
            CREATE TABLE task_refs (
                task_id TEXT NOT NULL, user_id TEXT NOT NULL, demo_round_id TEXT NOT NULL,
                kind TEXT NOT NULL, record_id TEXT NOT NULL,
                PRIMARY KEY(task_id, kind, record_id)
            );
            INSERT INTO sessions VALUES ('S1', 'U1', 'D1', '2026-09-28T10:00:00+08:00',
                '2026-09-28T12:00:00+08:00');
            INSERT INTO tasks VALUES ('T1', 'U1', 'S1', 'D1', 'R1', 'waiting_approval', 0,
                'thread-1', NULL, '{}');
            INSERT INTO task_refs VALUES ('T1', 'U1', 'D1', 'confirmation', 'C1');
            PRAGMA user_version = 1;
        """)

    store = ApplicationStore(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
    assert store.has_ref("U1", "D1", "T1", "confirmation", "C1")

    created_at, expires_at = active_session_window()
    store.create_session("S2", "U1", "D1", created_at, expires_at)
    store.transition_task_session("U1", "D1", "T1", "S1", "S2", 0)
    assert not store.has_ref("U1", "D1", "T1", "confirmation", "C1")


def test_list_session_tasks_orders_active_first_and_scopes_by_session(tmp_path):
    paths = StoragePaths(tmp_path)
    store = ApplicationStore(paths.application)
    store.create_session("S1", "U1", "D1", NOW, "2026-09-28T12:00:00+08:00")
    store.create_task("T1", "U1", "S1", "D1", "R1", "waiting_approval", {"step": 1})
    store.create_task("T2", "U1", "S1", "D1", "R2", "succeeded", {"step": 2})
    store.create_task("T3", "U1", "S1", "D1", "R3", "running", {"step": 3})
    store.create_session("S2", "U1", "D1", NOW, "2026-09-28T12:00:00+08:00")
    store.create_task("T4", "U1", "S2", "D1", "R4", "running", {"step": 4})
    assert [task.task_id for task in store.list_session_tasks("U1", "D1", "S1")] == [
        "T3", "T1", "T2",
    ]
    assert [task.task_id for task in store.list_session_tasks("U1", "D1", "S2")] == ["T4"]


def test_list_session_tasks_follows_session_transition(tmp_path):
    # A recovered task belongs to its new session: planning context there must
    # see it instead of denying the user's business exists.
    store, _ = prepared_task(StoragePaths(tmp_path).application)
    created_at, expires_at = active_session_window()
    store.create_session("S9", "U1", "D1", created_at, expires_at)
    store.transition_task_session("U1", "D1", "T1", "S1", "S9", 0)
    assert [task.task_id for task in store.list_session_tasks("U1", "D1", "S9")] == ["T1"]
    assert store.list_session_tasks("U1", "D1", "S1") == []
