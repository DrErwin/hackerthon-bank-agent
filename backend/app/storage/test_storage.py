"""Persistent boundaries required by the v0.3 transfer path."""

from __future__ import annotations

import asyncio
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
