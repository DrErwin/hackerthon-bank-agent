"""Ticket 06 phase 1: actual L01 public paths with a seeded, local Mock Bank.

Only Environment wiring is reused from the backend integration suite. Each case
starts/resumes the registered capability through the real Harness and asserts
its own business outcome. The planner and authorization/LOW-risk policy are
scripted test doubles; named error cases inject gateway failures explicitly.
These are neither live-model/HTTP tests nor professional-security acceptance.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest

from app.contracts.bank import BankError, QueryFailure
from app.contracts.bills import BillDetails
from app.modules.bills.test_public_integration import (
    BANK_NOW, END, START, Environment, payload, trusted,
)
from app.services.bank_gateway.gateway import BankGateway

CASES = json.loads(Path(__file__).with_name("public-business-cases.json").read_text(encoding="utf-8"))["cases"]


def bank_digest(env):
    """Check actual bank tables, not just a mocked write-call counter."""
    with sqlite3.connect(env.directory / "bank.sqlite") as connection:
        raw = "\n".join(connection.iterdump()).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def business_env(tmp_path, request):
    env = Environment(tmp_path)
    before_balances, before_digest = env.balances(), bank_digest(env)
    observations = []
    integrity = {"before_bank_sha256": before_digest}
    request.node.user_properties.extend([
        ("business_observations", observations), ("bank_integrity", integrity),
    ])
    env.business_observations = observations
    try:
        yield env
    finally:
        try:
            after_balances, after_digest = env.balances(), bank_digest(env)
            integrity.update(after_bank_sha256=after_digest,
                             balances_unchanged=after_balances == before_balances,
                             bank_tables_unchanged=after_digest == before_digest,
                             funds_submit_calls=env.gateway.bank_writes)
            assert after_balances == before_balances
            assert after_digest == before_digest
            assert env.gateway.bank_writes == 0
        finally:
            env.close()


def observe(env, context, result, action, request_id=None, **facts):
    """Archive result facts and correlation IDs; no raw merchant/account rows."""
    raw = result.model_dump(mode="json")
    data = raw.get("data") or {}
    record = {
        "at": datetime.now(timezone.utc).isoformat(), "action": action,
        "user_id": context.user_id, "demo_round_id": context.demo_round_id,
        "session_id": context.session_id, "task_id": result.task_id,
        "requested_run_id": context.run_id, "result_run_id": result.run_id,
        "request_id": str(request_id) if request_id else None,
        "business_status": raw["status"], "data_present": raw["data"] is not None,
        "error_code": raw["error"]["code"] if raw["error"] else None,
        "upstream_code": raw["error"]["upstream_code"] if raw["error"] else None,
        "interaction_kind": raw["interaction"]["kind"] if raw["interaction"] else None,
        "scope": data.get("scope"), "as_of": data.get("as_of"),
        "amounts_fen": {key: data[key] for key in (
            "consumption_gross_fen", "consumption_refund_fen", "consumption_net_fen",
            "transfer_out_fen", "transfer_in_fen") if key in data},
        "transaction_count": data.get("transaction_count", len(data["transactions"])
                                      if "transactions" in data else None),
        # Injected failures bypass ObservedGateway; this is deliberately not
        # labeled as the number of all attempted bank calls.
        "observed_gateway_read_calls": len(env.gateway.reads),
        "funds_submit_calls": env.gateway.bank_writes,
        **facts,
    }
    task = env.application.get_task(context.user_id, context.demo_round_id, context.task_id)
    assert task is not None and task.snapshot["capability_name"] == "bills.summarize"
    assert task.checkpoint_id is not None
    record["checkpoint_id"] = task.checkpoint_id
    env.business_observations.append(record)
    return result


def start(env, text, *, task="T1", request_id=None):
    context, request_id = trusted(task=task), request_id or uuid4()
    return observe(env, context, env.harness.start(context, request_id, text), "start", request_id)


def choose(env, result, label, *, run, session="S1"):
    matches = [option for option in result.interaction.options if option.label == label]
    assert len(matches) == 1
    context = trusted(task=result.task_id, run=run, session=session)
    return observe(env, context,
        env.harness.resume(context, {"choice": matches[0].id}), "resume_option")


def oracle_accounts(env):
    response = BankGateway.list_accounts(env.gateway, trusted())
    assert response.kind == "ok"
    return response.data.accounts


def oracle_rows(env, scope):
    rows = []
    for account_id in scope.account_ids:
        response = BankGateway.list_transactions(
            env.gateway, trusted(), account_id, scope.start_at, scope.end_at)
        assert response.kind == "ok" and response.data.as_of == BANK_NOW
        rows.extend(response.data.transactions)
    return sorted(rows, key=lambda row: (row.occurred_at, row.account_id, row.transaction_id))


def assert_summary(env, result, *, expected_ids=None, start_at=START, end_at=END):
    assert result.status == "succeeded", result
    summary = payload(result)
    assert (summary.scope.start_at, summary.scope.end_at) == (start_at, end_at)
    expected_ids = expected_ids or [account.account_id for account in oracle_accounts(env)]
    assert sorted(summary.scope.account_ids) == sorted(expected_ids)
    rows = oracle_rows(env, summary.scope)
    # Independent formulas over actual public B08 rows; no bills calculator.
    gross = sum(row.amount_fen for row in rows if row.nature == "consumption" and row.direction == "outflow")
    refund = sum(row.amount_fen for row in rows if row.nature == "refund" and row.direction == "inflow")
    outgoing = sum(row.amount_fen for row in rows if row.nature == "transfer" and row.direction == "outflow")
    incoming = sum(row.amount_fen for row in rows if row.nature == "transfer" and row.direction == "inflow")
    assert (summary.transaction_count, summary.consumption_gross_fen,
            summary.consumption_refund_fen, summary.consumption_net_fen,
            summary.transfer_out_fen, summary.transfer_in_fen) == (
                len(rows), gross, refund, gross - refund, outgoing, incoming)
    assert {item.account_id for item in summary.source_as_of} == set(expected_ids)
    assert summary.as_of == BANK_NOW and all(item.as_of == BANK_NOW for item in summary.source_as_of)
    assert {item.category for item in summary.categories} == {
        "dining", "transport", "medical", "shopping", "housing", "transfer", "other"}
    assert next(item for item in summary.categories if item.category == "transfer").share_bps is None
    return summary, rows


def failure():
    return QueryFailure(kind="error", error=BankError(code="CALL_TIMEOUT", details={}))


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_public_business_case(case, business_env, monkeypatch):
    env, number = business_env, case["id"].rsplit("-", 1)[1]

    if number == "01":
        result = start(env, case["input"])
        summary, rows = assert_summary(env, result)
        assert (summary.transaction_count, summary.consumption_gross_fen,
                summary.consumption_refund_fen, summary.consumption_net_fen) == (18, 586400, 4500, 581900)
        assert len(summary.scope.account_ids) > 1 and rows
        assert env.decisions and all(item.decision == "allow" for item in env.decisions)

    elif number == "02":
        result = start(env, case["input"])
        assert result.status == "waiting_input" and not any(call[0] == "transactions" for call in env.gateway.reads)
        account = oracle_accounts(env)[0]
        result = choose(env, result, account.display_name + " · " + account.account_masked, run="R2")
        assert_summary(env, result, expected_ids=[account.account_id])
        assert {call[2] for call in env.gateway.reads if call[0] == "transactions"} == {account.account_id}

    elif number == "03":
        result = start(env, case["input"])
        assert result.status == "waiting_input" and env.gateway.reads == []
        result = choose(env, result, "上月", run="R2")
        assert result.status == "waiting_input"
        result = choose(env, result, "所有本人账户", run="R3")
        assert result.task_id == "T1" and result.run_id == "R3"
        assert_summary(env, result)

    elif number == "04":
        result = start(env, case["input"])
        assert result.status == "succeeded", result
        details = payload(result, BillDetails)
        assert details.category == "dining"
        assert (details.scope.start_at, details.scope.end_at) == (START, END)
        assert set(details.scope.account_ids) == {account.account_id for account in oracle_accounts(env)}
        rows = oracle_rows(env, details.scope)
        expected = []
        for row in rows:
            category = row.category
            if row.nature == "refund":
                original = BankGateway.list_transactions(env.gateway, trusted(), row.account_id,
                    row.original_occurred_at, row.original_occurred_at + timedelta(microseconds=1))
                assert original.kind == "ok"
                matched = [item for item in original.data.transactions if item.transaction_id == row.original_transaction_id]
                assert len(matched) == 1
                category = matched[0].category
            if category == "dining":
                expected.append(row.model_copy(update={"category": category}))
        assert details.transactions == expected and len(expected) == 3
        assert any(row.channel is None for row in expected)  # unknown stays unknown
        assert any(row.nature == "refund" and row.original_occurred_at < START for row in expected)
        assert all(item.as_of == BANK_NOW for item in details.source_as_of)

    elif number == "05":
        result = start(env, case["input"])
        summary, rows = assert_summary(env, result)
        assert summary.consumption_refund_fen > 0 and summary.transfer_in_fen > 0
        assert any(row.nature == "interest" for row in rows)
        assert "转账支出" not in result.message
        # September has no outgoing transfer. July has a real 500-yuan seed,
        # so the exclusion assertion also exercises a nonzero transfer-out.
        july = start(env, "2026年7月所有账户不含转账消费统计", task="T2")
        july_summary, _ = assert_summary(env, july,
            start_at=datetime.fromisoformat("2026-07-01T00:00:00+08:00"),
            end_at=datetime.fromisoformat("2026-08-01T00:00:00+08:00"))
        assert july_summary.transfer_out_fen == 50000
        assert "转账支出" not in july.message

    elif number == "06":
        result = start(env, case["input"])
        summary, rows = assert_summary(env, result,
            start_at=datetime.fromisoformat("2024-11-01T00:00:00+08:00"),
            end_at=datetime.fromisoformat("2024-12-01T00:00:00+08:00"))
        assert rows == [] and summary.transaction_count == 0
        assert "记录" in result.message and "没有" in result.message
        assert all(item.share_bps is None for item in summary.categories)
        assert any(call[0] == "transactions" for call in env.gateway.reads)

    elif number == "07":
        result = start(env, case["input"])
        assert result.status == "failed" and result.data is None
        assert result.error.code == result.error.upstream_code == "RANGE_UNSUPPORTED"
        calls = [call for call in env.gateway.reads if call[0] == "transactions"]
        assert calls and all(call[3].year == 2020 for call in calls)

    elif number == "08":
        env.permission = False
        result = start(env, case["input"])
        assert result.status == "failed" and result.data is None and result.error.source == "security"
        assert env.gateway.reads == [] and any(item.decision == "block" for item in env.decisions)

    elif number in {"09", "10"}:
        method = "list_accounts" if number == "09" else "list_transactions"
        original, attempts = getattr(env.gateway, method), []

        def unavailable(*args):
            attempts.append(method)
            return failure()

        monkeypatch.setattr(env.gateway, method, unavailable)
        result = start(env, case["input"])
        assert result.status == "waiting_input" and result.data is None and attempts
        env.business_observations[-1]["injected_failure"] = {"method": method, "code": "CALL_TIMEOUT", "attempts": len(attempts)}
        if number == "09":
            assert not any(call[0] == "transactions" for call in env.gateway.reads)
        monkeypatch.setattr(env.gateway, method, original)
        result = choose(env, result, "重新查询原范围", run="R2")
        assert result.task_id == "T1" and result.run_id == "R2"
        assert_summary(env, result)

    elif number == "11":
        accounts = oracle_accounts(env)
        assert len(accounts) == 2
        failed_account = accounts[1].account_id
        original, attempts = env.gateway.list_transactions, []

        def partial(context, account_id, start_at, end_at):
            attempts.append({"account_id": account_id, "outcome": "injected_failure" if account_id == failed_account else "real_bank"})
            return failure() if account_id == failed_account else original(context, account_id, start_at, end_at)

        monkeypatch.setattr(env.gateway, "list_transactions", partial)
        result = start(env, case["input"])
        assert result.status == "waiting_input" and result.data is None
        assert {item["outcome"] for item in attempts} == {"real_bank", "injected_failure"}
        assert attempts[0]["outcome"] == "real_bank"
        env.business_observations[-1]["account_attempts"] = attempts
        env.business_observations[-1]["injected_failure"] = {"method": "list_transactions", "code": "CALL_TIMEOUT", "account_id": failed_account}

    elif number == "12":
        request_id = uuid4()
        first = start(env, case["input"], request_id=request_id)
        assert_summary(env, first)
        count = len(env.gateway.reads)
        second = start(env, case["input"], request_id=request_id)
        assert first.model_dump(mode="json") == second.model_dump(mode="json")
        assert len(env.gateway.reads) == count
        env.business_observations[-1]["dedup_layer"] = "Harness; module guard separately covered by ticket 09"

    elif number == "13":
        first = start(env, case["input"])
        assert first.status == "waiting_input"
        option = first.interaction.options[0].id
        context = trusted(run="R2")
        stopped = observe(env, context, env.harness.resume(context, {"cancel": True}), "cancel")
        assert stopped.status == "cancelled"
        context = trusted(run="R3")
        replay = observe(env, context, env.harness.resume(context, {"choice": option}), "resume_old_option")
        assert replay.status == "cancelled" and replay.data is None and env.gateway.reads == []

    elif number == "14":
        first = start(env, case["input"])
        old_options = {item.id for item in first.interaction.options}
        env.session("S2")
        context = trusted(session="S2", run="R2")
        moved = observe(env, context, env.harness.recover_session(context), "recover_session")
        assert moved.status == "waiting_input" and moved.task_id == "T1"
        assert not old_options & {item.id for item in moved.interaction.options}
        assert env.gateway.reads == []
        assert len(moved.interaction.options) == 1
        result = choose(env, moved, moved.interaction.options[0].label, session="S2", run="R3")
        result = choose(env, result, "上月", session="S2", run="R4")
        result = choose(env, result, "所有本人账户", session="S2", run="R5")
        assert result.task_id == "T1" and result.run_id == "R5"
        assert_summary(env, result)
        assert env.application.get_task("U1", "D1", "T1").session_id == "S2"

    elif number == "15":
        accounts = oracle_accounts(env)
        refunds = [row for account in accounts for row in
            BankGateway.list_transactions(env.gateway, trusted(), account.account_id, START, END).data.transactions
            if row.nature == "refund" and row.original_occurred_at < START]
        assert len(refunds) == 1
        refund = refunds[0]
        missing_range = (refund.account_id, refund.original_occurred_at,
                         refund.original_occurred_at + timedelta(microseconds=1))
        original = env.gateway.list_transactions
        completed_current_accounts, failed_lookups = set(), []

        def missing_original(context, account_id, start_at, end_at):
            if (account_id, start_at, end_at) == missing_range:
                failed_lookups.append((account_id, start_at, end_at))
                return failure()
            response = original(context, account_id, start_at, end_at)
            if (start_at, end_at) == (START, END):
                assert response.kind == "ok"
                completed_current_accounts.add(account_id)
            return response

        monkeypatch.setattr(env.gateway, "list_transactions", missing_original)
        result = start(env, case["input"])
        assert completed_current_accounts == {account.account_id for account in accounts}
        assert failed_lookups and result.status == "waiting_input" and result.data is None
        env.business_observations[-1].update(
            completed_current_account_ids=sorted(completed_current_accounts),
            injected_failure={"method": "list_transactions", "stage": "refund_original",
                "code": "CALL_TIMEOUT", "attempts": len(failed_lookups),
                "account_id": refund.account_id, "start_at": missing_range[1].isoformat(),
                "end_at": missing_range[2].isoformat()})
        monkeypatch.setattr(env.gateway, "list_transactions", original)
        result = choose(env, result, "重新查询原范围", run="R2")
        assert result.task_id == "T1" and result.run_id == "R2"
        summary, rows = assert_summary(env, result)
        assert (summary.transaction_count, summary.consumption_gross_fen,
                summary.consumption_refund_fen, summary.consumption_net_fen) == (18, 586400, 4500, 581900)
        assert refund.original_transaction_id not in {row.transaction_id for row in rows}

    elif number == "16":
        result = start(env, case["input"])
        assert result.status == "waiting_input"
        assert not any(call[0] == "transactions" for call in env.gateway.reads)
        accounts = [account for account in oracle_accounts(env) if account.account_id == "A5"]
        assert len(accounts) == 1
        account = accounts[0]
        result = choose(env, result, account.display_name + " · " + account.account_masked, run="R2")
        assert result.status == "succeeded", result
        details = payload(result, BillDetails)
        assert details.scope.account_ids == [account.account_id] and details.category == "dining"
        assert (details.scope.start_at, details.scope.end_at) == (START, END)
        rows = oracle_rows(env, details.scope)
        assert rows and any(row.nature == "consumption" for row in rows)
        assert all(row.category != "dining" for row in rows)
        assert details.transactions == [] and "没有匹配记录" in result.message
        assert details.as_of == BANK_NOW
        assert [(item.account_id, item.as_of) for item in details.source_as_of] == [(account.account_id, BANK_NOW)]
        assert {call[2] for call in env.gateway.reads if call[0] == "transactions"} == {account.account_id}
        env.business_observations[-1].update(unfiltered_bank_row_count=len(rows), selected_category="dining")

    elif number == "17":
        result = start(env, case["input"])
        assert result.status == "waiting_input" and result.data is None and env.gateway.reads == []
        assert "不支持" in result.message
        assert [option.label for option in result.interaction.options] == ["查看全部类别"]
        result = choose(env, result, "查看全部类别", run="R2")
        assert result.task_id == "T1" and result.run_id == "R2"
        summary, _ = assert_summary(env, result)
        assert next(item for item in summary.categories if item.category == "dining").outflow_fen > 0
        assert (summary.transaction_count, summary.consumption_net_fen) == (18, 581900)

    else:
        pytest.fail(f"case has no implementation: {case['id']}")
