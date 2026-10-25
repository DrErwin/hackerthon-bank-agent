"""Declared inputs through public factories and real child dispatch, no live model."""
from datetime import timedelta
from uuid import uuid4

import pytest

from app.agent_platform.registry import CapabilityRegistry
from app.contracts.bills import (AnomalyResult, BillDetails, BillReport, BillScope,
    BillSummarizeInput, DetectAnomaliesInput, GenerateReportInput, SpendingSummary,
    TransactionCandidates, TransactionClues)
from app.modules.bills.anomaly_entry import register_bills_anomalies
from app.modules.bills.entry import register_bills, register_bills_report
from app.modules.bills.test_public import CTX, END, NOW, START, Reads, Saver, transaction
from app.modules.bills.test_public_integration import Environment, BANK_NOW, trusted
from app.services.bank_gateway.gateway import BankGateway


def registry(reads_factory, clock):
    result = CapabilityRegistry()
    for register in (register_bills, register_bills_report, register_bills_anomalies):
        register(result, reads_factory, clock)
    return result


def requests(scope, transaction_id="p"):
    previous = scope.model_copy(update={"start_at": scope.start_at - timedelta(days=31),
                                        "end_at": scope.start_at})
    return [
        ("bills.summarize", BillSummarizeInput(scope=scope, comparison_scope=previous), SpendingSummary),
        ("bills.summarize", BillSummarizeInput(scope=scope, mode="details", category="shopping"), BillDetails),
        ("bills.detect_anomalies", DetectAnomaliesInput(mode="locate", scope=scope,
            clues=TransactionClues(category="shopping")), TransactionCandidates),
        ("bills.detect_anomalies", DetectAnomaliesInput(mode="single", account_id=scope.account_ids[0],
            transaction_id=transaction_id), AnomalyResult),
        ("bills.detect_anomalies", DetectAnomaliesInput(mode="scan", scope=scope), AnomalyResult),
        ("bills.generate_report", GenerateReportInput(scope=scope, purpose="share_request",
            comparison_scope=previous), BillReport),
    ]


@pytest.mark.parametrize("case", range(6))
def test_factory_preserves_input_replay_and_conflict(case):
    reads, saver = Reads([transaction(), transaction("p2")]), Saver()
    reg = registry(lambda *_: reads, lambda: NOW)
    scope = BillScope(account_ids=["a1"], start_at=START, end_at=END)
    capability, request, model = requests(scope)[case]
    factory = reg.get(capability).factory
    first = factory(CTX, saver, None).start(CTX, request)
    assert first.status == "succeeded", first
    assert isinstance(first.data, model)
    if case == 0:
        assert first.data.scope == scope and first.data.comparison.scope == request.comparison_scope
        assert first.data.consumption_net_fen == 100000
    elif case == 1:
        assert first.data.scope == scope and first.data.category == "shopping"
        assert [r.transaction_id for r in first.data.transactions] == ["p", "p2"]
    elif case == 2:
        assert len(first.data.candidates) == 2  # caller selects, never default first
    elif case == 3:
        assert first.data.transaction.transaction_id == "p"
    elif case == 5:
        assert first.data.summary.comparison.scope == request.comparison_scope
    calls, writes = len(reads.calls), saver.writes
    replay = factory(CTX, saver, None).start(CTX.model_copy(update={"run_id": "r2"}), request)
    assert isinstance(replay.data, model) and replay.data == first.data
    assert replay.run_id == "r2" and len(reads.calls) == calls and saver.writes == writes
    changed = (request.model_copy(update={"transaction_id": "other"}) if case == 3 else
               request.model_copy(update={"scope": scope.model_copy(update={"account_ids": ["a2"]})}))
    with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
        factory(CTX, saver, None).start(CTX, changed)
    for field in ("session_id", "user_id", "demo_round_id"):
        with pytest.raises(PermissionError, match="ACCESS_DENIED"):
            factory(CTX, saver, None).start(CTX.model_copy(update={field: "other"}), request)


@pytest.mark.parametrize("case", [0, 4, 5])
def test_retry_and_session_recovery_keep_exact_scope(case):
    reads, saver = Reads([transaction()]), Saver()
    reads.failure = lambda *_: True
    reg = registry(lambda *_: reads, lambda: NOW)
    capability, request, _ = requests(BillScope(account_ids=["a1"], start_at=START, end_at=END))[case]
    factory = reg.get(capability).factory
    pending = factory(CTX, saver, None).start(CTX, request)
    assert pending.status == "waiting_input" and pending.data is None
    context = CTX.model_copy(update={"session_id": "s2", "run_id": "r2"})
    recovered = factory(context, saver, None).recover_session(context, source_session_id=CTX.session_id)
    reads.failure = None
    result = factory(context, saver, None).resume(context, {
        "selected_option_id": recovered.interaction.options[0].id,
        "interaction_id": recovered.interaction.interaction_id})
    assert result.status == "succeeded", result
    state = next(iter(saver.saved.checkpoint["channel_values"].values()))
    assert state["typed_request"] == request.model_dump(mode="json")


@pytest.mark.parametrize("case", range(6))
def test_real_dispatch_bank_evidence_and_permissions(tmp_path, case):
    env = Environment(tmp_path)
    try:
        register_bills_report(env.registry, env.reads_factory, lambda: BANK_NOW)
        register_bills_anomalies(env.registry, env.reads_factory, lambda: BANK_NOW)
        parent = trusted("PARENT")
        env.application.create_task(parent.task_id, parent.user_id, parent.session_id,
            parent.demo_round_id, parent.run_id, "running", {})
        account = BankGateway.list_accounts(env.gateway, parent).data.accounts[0].account_id
        rows = BankGateway.list_transactions(env.gateway, parent, account, START, END).data.transactions
        assert rows
        capability, request, model = requests(BillScope(account_ids=[account], start_at=START, end_at=END),
                                              rows[0].transaction_id)[case]
        balances = env.balances()
        child = env.harness.dispatch_child(parent, capability, uuid4(), request,
                                           step_id="bill_evidence", plan_revision=1)
        assert child.status == "succeeded", child
        assert isinstance(child.data, model)
        if case == 1:
            assert child.data.transactions == [r for r in rows if r.category == "shopping"]
        if case == 3:
            assert child.data.transaction == rows[0]
        assert env.decisions and env.gateway.reads
        assert env.balances() == balances and env.gateway.bank_writes == 0
        env.permission = False
        env.gateway.reads.clear()
        denied = env.harness.dispatch_child(parent, capability, uuid4(), request,
                                            step_id="denied", plan_revision=1)
        assert denied.status == "failed" and denied.error.source == "security"
        assert env.gateway.reads == [] and env.gateway.bank_writes == 0
    finally:
        env.close()


@pytest.mark.parametrize("capability", ["bills.summarize", "bills.generate_report", "bills.detect_anomalies"])
def test_wrong_input_rejected_before_read(capability):
    reads = Reads()
    reg = registry(lambda *_: reads, lambda: NOW)
    scope = BillScope(account_ids=["a1"], start_at=START, end_at=END)
    wrong = (GenerateReportInput(scope=scope, purpose="self_view") if capability != "bills.generate_report"
             else BillSummarizeInput(scope=scope))
    for request in (wrong, {"scope": scope.model_dump(mode="json")}):
        result = reg.get(capability).factory(CTX, Saver(), None).start(CTX, request)
        assert result.status == "failed" and result.error.code == "INVALID_ARGUMENT"
    assert reads.calls == []
