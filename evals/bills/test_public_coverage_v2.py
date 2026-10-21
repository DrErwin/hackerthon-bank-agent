"""Ticket 06 phase 2: bank-backed public L02/L03 and independent rule contrasts.

Every case builds a fresh SQLite MockBank, registers the *real* BillsEntry for
the requested capability with a real Harness/SecurityGate/executor, and starts a
public task.  Only capability selection and LOW-risk/permission facts are
scripted.  Test-owned additional ledger facts are inserted with the bank's
documented seed_ledger_rows API *before* read-only proofs begin.

This suite does not exercise a live LLM, HTTP, React, or professional security
approval. No skipped cases and no default-allow production path.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest

from app.agent_platform.harness import AgentHarness
from app.agent_platform.model import TransferProposal
from app.contracts.bank import BankError, QueryFailure
from app.contracts.bills import AnomalyResult, BillReport, TransactionCandidates
from app.modules.bills.anomaly_entry import register_bills_anomalies
from app.modules.bills.entry import register_bills_report
from app.modules.bills.test_anomaly_integration import f10
from app.modules.bills.test_public_integration import (
    BANK_NOW, START, END, Environment, trusted,
)
from app.services.bank_gateway.gateway import BankGateway
from app.storage.mock_bank.repository import MockBankStore


CASES = json.loads(Path(__file__).with_name("public-coverage-v2-cases.json").read_text(encoding="utf-8"))["cases"]
L02 = [case for case in CASES if case["tier"] == "l02_public"]
L03 = [case for case in CASES if case["tier"] == "l03_public"]
RULES = [case for case in CASES if case["tier"] == "l02_rule_public"]


def _bank_digest(env):
    with sqlite3.connect(env.directory / "bank.sqlite") as connection:
        data = "\n".join(connection.iterdump()).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class RoutedPlanner:
    provider = "scripted"
    model_name = "bills-public-coverage-v2"
    config_version = "test-only-routed-v1"

    def __init__(self, capability):
        self.capability = capability

    def select(self, intent_text, context, catalog, memory, thread_id, context_summary=None):
        assert self.capability in {item["name"] for item in catalog}
        return TransferProposal(capability_name=self.capability)


@pytest.fixture
def bank_env(tmp_path, request):
    env = Environment(tmp_path)
    observations = []
    integrity = {}
    request.node.user_properties.extend([
        ("coverage_observations", observations), ("bank_integrity", integrity),
    ])
    env.coverage_observations = observations
    env.coverage_integrity = integrity
    try:
        yield env
    finally:
        try:
            assert integrity.get("before_bank_sha256"), "each public case must arm bank proof"
            after = _bank_digest(env)
            integrity.update(
                after_bank_sha256=after,
                bank_tables_unchanged=after == integrity["before_bank_sha256"],
                balances_unchanged=env.balances() == integrity["before_balances"],
                funds_submit_calls=env.gateway.bank_writes,
            )
            assert integrity["bank_tables_unchanged"], "read-only case changed real bank facts"
            assert integrity["balances_unchanged"]
            assert integrity["funds_submit_calls"] == 0
            assert observations, "the case must leave a public result observation"
        finally:
            env.close()


def _arm(env):
    env.coverage_integrity["before_bank_sha256"] = _bank_digest(env)
    env.coverage_integrity["before_balances"] = env.balances()


def _activate(env, name):
    if name == "L02":
        tick = [BANK_NOW]

        def bank_clock():
            tick[0] += timedelta(microseconds=1)
            return tick[0]

        env.gateway._bank.clock = bank_clock
        register_bills_anomalies(env.registry, env.reads_factory, bank_clock)
        capability = "bills.detect_anomalies"
    else:
        register_bills_report(env.registry, env.reads_factory, lambda: BANK_NOW)
        capability = "bills.generate_report"
    env.harness = AgentHarness(
        env.application, env.memory, env.audit, env.registry,
        RoutedPlanner(capability),
        lambda context, declaration: env.valid_session(context),
    )
    assert capability in {item["name"] for item in env.registry.public_catalog()}
    return capability


def _observe(env, action, result):
    data = result.data
    env.coverage_observations.append({
        "action": action, "task_id": result.task_id, "run_id": result.run_id,
        "status": result.status, "data_type": type(data).__name__ if data is not None else None,
        "error_code": result.error.code if result.error is not None else None,
        "gateway_read_count": len(env.gateway.reads),
        "bank_funds_submit_calls": env.gateway.bank_writes,
    })
    return result


def _start(env, text, request_id=None):
    return _observe(env, "start", env.harness.start(trusted(), request_id or uuid4(), text))


def _choose(env, result, index, run="R2", session="S1"):
    context = trusted(session=session, run=run)
    response = f10(result, index)
    return _observe(env, "resume", env.harness.resume(context, response))


def _select_by_label(env, result, label, run="R2", session="S1"):
    positions = [index for index, option in enumerate(result.interaction.options)
                 if option.label == label]
    assert len(positions) == 1, (label, [o.label for o in result.interaction.options])
    return _choose(env, result, positions[0], run=run, session=session)


def _real_report(env, result, *, year=None, month=None):
    assert result.status == "succeeded", result
    report = BillReport.model_validate(
        result.data.model_dump() if hasattr(result.data, "model_dump") else result.data
    )
    assert report.report_id and report.scope.account_ids
    if year is not None:
        assert report.scope.start_at.year == year
    if month is not None:
        assert report.scope.start_at.month == month
    rows = []
    for account_id in report.scope.account_ids:
        response = BankGateway.list_transactions(
            env.gateway, trusted(), account_id, report.scope.start_at, report.scope.end_at
        )
        assert response.kind == "ok"
        rows.extend(response.data.transactions)
    gross = sum(x.amount_fen for x in rows
                if x.direction == "outflow" and x.nature == "consumption")
    refunds = sum(x.amount_fen for x in rows
                  if x.direction == "inflow" and x.nature == "refund")
    assert (report.summary.transaction_count, report.summary.consumption_gross_fen,
            report.summary.consumption_refund_fen, report.summary.consumption_net_fen) == (
                len(rows), gross, refunds, gross - refunds)
    assert report.allowed_actions == [] if hasattr(report, "allowed_actions") else True
    return report


@pytest.mark.parametrize("case", L02, ids=[x["id"] for x in L02])
def test_public_l02_scenario(case, bank_env):
    env = bank_env
    _activate(env, "L02")
    _arm(env)
    mode = case["kind"]
    request_id = uuid4()
    result = _start(env, case["input"], request_id)
    assert env.gateway.bank_writes == 0

    if mode == "multiple_candidates":
        assert result.status == "waiting_input"
        data = TransactionCandidates.model_validate(result.data)
        assert len(data.candidates) > 1
        assert len(result.interaction.options) == len(data.candidates)

    elif mode in {"select_first", "select_last"}:
        assert result.status == "waiting_input"
        data = TransactionCandidates.model_validate(result.data)
        index = 0 if mode == "select_first" else len(data.candidates) - 1
        selected = data.candidates[index]
        answer = _choose(env, result, index)
        assert answer.task_id == result.task_id and answer.status == "succeeded"
        single = AnomalyResult.model_validate(answer.data)
        assert single.transaction == selected
        assert [check.rule_id for check in single.checks] == [1, 2, 3, 4]
        assert all("盗刷已确认" not in finding.evidence for finding in single.findings)

    elif mode == "scan":
        assert result.status == "succeeded", result
        data = AnomalyResult.model_validate(result.data)
        assert data.transaction is None
        assert [check.rule_id for check in data.checks] == [4]
        assert all(x.rule_id == 4 for x in data.findings)

    elif mode == "missing_month":
        assert result.status == "waiting_input" and not env.gateway.reads
        assert any(o.label == "上月" for o in result.interaction.options)

    elif mode == "choose_account":
        assert result.status == "waiting_input"
        assert any(read[0] == "accounts" for read in env.gateway.reads)
        assert not any(read[0] == "transactions" for read in env.gateway.reads)
        assert any("所有本人账户" == o.label for o in result.interaction.options)

    elif mode == "ambiguous_amount":
        assert result.status == "waiting_input" and not env.gateway.reads
        assert any(o.label == "列出原范围流水" for o in result.interaction.options)

    elif mode == "no_matching_amount":
        assert result.status == "waiting_input"
        data = TransactionCandidates.model_validate(result.data)
        assert len(data.candidates) == 0 and "没有符合线索" in result.message
        assert any(x[0] == "transactions" for x in env.gateway.reads)

    elif mode == "partial_month":
        assert result.status == "waiting_input" and not env.gateway.reads

    elif mode == "cancel":
        assert result.status == "waiting_input"
        stopped = _observe(env, "cancel", env.harness.resume(trusted(run="R2"), {"cancel": True}))
        assert stopped.status == "cancelled" and stopped.data is None
        assert not env.gateway.reads

    elif mode in {"request_replay", "scan_replay"}:
        reads = list(env.gateway.reads)
        replay = _start(env, case["input"], request_id)
        assert replay.model_dump(mode="json") == result.model_dump(mode="json")
        assert env.gateway.reads == reads

    elif mode == "permission_revoked":
        assert result.status == "waiting_input"
        reads = list(env.gateway.reads)
        env.permission = False
        refused = _choose(env, result, 0)
        assert refused.status == "failed" and refused.error.source == "security"
        assert refused.data is None and env.gateway.reads == reads

    elif mode == "session_recovery":
        assert result.status == "waiting_input"
        old_options = {o.id for o in result.interaction.options}
        env.session("S2")
        moved = _observe(env, "recover_session",
            env.harness.recover_session(trusted(session="S2", run="R2")))
        assert moved.status == "waiting_input" and moved.task_id == result.task_id
        assert old_options.isdisjoint({o.id for o in moved.interaction.options})
        assert env.gateway.bank_writes == 0

    else:
        raise AssertionError("unhandled public L02 case " + mode)
    task = env.application.get_task("U1", "D1", "T1")
    assert task is not None and task.snapshot["capability_name"] == "bills.detect_anomalies"
    assert task.checkpoint_id


@pytest.mark.parametrize("case", L03, ids=[x["id"] for x in L03])
def test_public_l03_scenario(case, bank_env, monkeypatch):
    env = bank_env
    _activate(env, "L03")
    _arm(env)
    mode = case["kind"]
    request_id = uuid4()
    if mode == "permission_revoked":
        env.permission = False
    if mode == "retry_B08":
        original = env.gateway.list_transactions
        attempts = []

        def unavailable(*args):
            attempts.append("CALL_TIMEOUT")
            return QueryFailure(kind="error",
                                error=BankError(code="CALL_TIMEOUT", details={}))
        monkeypatch.setattr(env.gateway, "list_transactions", unavailable)

    result = _start(env, case["input"], request_id)
    if mode == "september":
        report = _real_report(env, result, year=2026, month=9)
        assert report.summary.transaction_count == 18
        assert report.summary.consumption_gross_fen == 586400

    elif mode == "august":
        _real_report(env, result, year=2026, month=8)

    elif mode == "this_year":
        report = _real_report(env, result, year=2026, month=1)
        assert report.scope.end_at == BANK_NOW

    elif mode == "choose_accounts":
        assert result.status == "waiting_input"
        assert not any(x[0] == "transactions" for x in env.gateway.reads)
        selected = _select_by_label(env, result, "所有本人账户")
        _real_report(env, selected, year=2026, month=9)

    elif mode in {"missing_period", "comparison_clarification", "future_period", "unsupported_day"}:
        assert result.status == "waiting_input" and result.data is None
        assert not env.gateway.reads

    elif mode == "category_clarification":
        assert result.status == "waiting_input" and not env.gateway.reads
        after = _select_by_label(env, result, "查看全部类别报告")
        _real_report(env, after, year=2026, month=9)

    elif mode == "permission_revoked":
        assert result.status == "failed" and result.data is None
        assert result.error.source == "security"
        assert not any(x[0] == "transactions" for x in env.gateway.reads)

    elif mode == "request_replay":
        report = _real_report(env, result, year=2026, month=9)
        reads = list(env.gateway.reads)
        replay = _start(env, case["input"], request_id)
        again = BillReport.model_validate(replay.data)
        assert again.report_id == report.report_id
        assert env.gateway.reads == reads

    elif mode == "retry_B08":
        assert result.status == "waiting_input" and attempts
        assert result.data is None
        monkeypatch.setattr(env.gateway, "list_transactions", original)
        retried = _select_by_label(env, result, "重新查询原范围")
        _real_report(env, retried, year=2026, month=9)

    elif mode in {"printed_report", "share_request"}:
        report = _real_report(env, result, year=2026, month=9)
        assert result.allowed_actions == []
        assert not hasattr(report, "download_url")

    else:
        raise AssertionError("unhandled public L03 case " + mode)
    task = env.application.get_task("U1", "D1", "T1")
    assert task is not None and task.snapshot["capability_name"] == "bills.generate_report"
    assert task.checkpoint_id


def _seeded_row(name, when, amount, *, merchant="EVAL-MERCHANT", nature="consumption",
                direction="outflow"):
    return {
        "transaction_id": name, "user_id": "U1", "account_id": "A1",
        "amount_fen": amount, "direction": direction, "nature": nature,
        "category": "transfer" if nature == "transfer" else
                    "other" if nature == "interest" else "shopping",
        "occurred_at": when, "counterparty_id": merchant,
        "counterparty_name": "模拟评测商户", "summary": "评测账单流水",
        "channel": "测试银行流水", "counterparty_account_masked": None,
    }


def _rule_rows(case):
    rule, variant = case["rule"], case["variant"]
    prefix = "EVAL-" + str(rule) + "-" + variant
    when = "2026-09-15T12:10:00+08:00"
    amount, nature, direction, merchant = 1000, "consumption", "outflow", prefix
    if rule == 1:
        amount = 250000 if variant in {"hit", "insufficient"} else 100
        if variant == "insufficient":
            nature = "transfer"
    elif rule == 2:
        nature, amount = "transfer", 43000
        merchant = "EMPLOYER" if variant == "miss" else None if variant == "insufficient" else prefix
    elif rule == 3:
        when = "2026-09-15T23:10:00+08:00" if variant != "miss" else when
        if variant == "insufficient":
            # Non-spending late-night bank interest is explicitly not suspicious;
            # unlike rules 1/2/4, rule 3 has no insufficient state for a
            # timezone-aware, authenticated transaction. This variant checks
            # the negative non-eligible path and must not be mislabeled missing.
            nature, direction = "interest", "inflow"
    elif rule == 4:
        amount = 5556 if variant == "miss" else 5555
        if variant == "insufficient":
            merchant = None
    target = _seeded_row(prefix + "-TARGET", when, amount,
                         merchant=merchant, nature=nature, direction=direction)
    rows = [target]
    if rule == 4 and variant != "insufficient":
        for month in (7, 8):
            rows.append(_seeded_row(
                prefix + "-M" + str(month), f"2026-{month:02}-15T12:10:00+08:00",
                5555, merchant=merchant,
            ))
    return target["transaction_id"], rows


@pytest.mark.parametrize("case", RULES, ids=[x["id"] for x in RULES])
def test_public_bank_rule_contrast(case, bank_env):
    env = bank_env
    target_id, rows = _rule_rows(case)
    store = MockBankStore(env.directory / "bank.sqlite")
    assert store.seed_ledger_rows(rows) == len(rows)
    _activate(env, "L02")
    _arm(env)
    first = _start(env, "核对交易，2026年9月所有账户")
    assert first.status == "waiting_input", first
    candidates = TransactionCandidates.model_validate(first.data).candidates
    positions = [i for i, row in enumerate(candidates) if row.transaction_id == target_id]
    assert len(positions) == 1, "target must be read from the real seeded bank"
    selected = _choose(env, first, positions[0])
    assert selected.status == "succeeded", selected
    data = AnomalyResult.model_validate(selected.data)
    assert data.transaction.transaction_id == target_id
    checks = {check.rule_id: check for check in data.checks}
    assert sorted(checks) == [1, 2, 3, 4]

    rule, variant = case["rule"], case["variant"]
    check = checks[rule]
    # Rule 3 has no "insufficient" classification for valid bank timestamps:
    # its third contrast proves noneligible nighttime bank income stays clear.
    expected = {
        "hit": ("evaluated", True),
        "miss": ("evaluated", False),
        "insufficient": ("insufficient_data", None) if rule != 3 else ("evaluated", False),
    }[variant]
    assert (check.status, check.matched) == expected, (case["id"], check)
    if variant == "hit":
        assert any(item.rule_id == rule and target_id in item.transaction_ids
                   for item in data.findings)
    else:
        assert not any(item.rule_id == rule and target_id in item.transaction_ids
                       for item in data.findings)
    assert env.gateway.bank_writes == 0
