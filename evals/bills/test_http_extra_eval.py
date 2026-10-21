"""Ticket07 phase2: additional in-process HTTP bills public capability journeys.

The actual ASGI ApiService, authenticated task API, registered BillsEntry,
scoped SQLite, tool SecurityGate, BankGateway and seeded MockBank are used.
Only planning/LOW-risk/admission inputs are scripted test policy. A test-owned
CSV formula row is inserted into the *mock bank* before starting the report.
This is not a live GLM/browser/security-professional acceptance suite.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.agent_platform.local_demo import _bills_reads_factory
from app.agent_platform.model import TransferProposal
from app.contracts.bills import AnomalyResult, BillDetails, BillReport, SpendingSummary, TransactionCandidates
from app.modules.bills.anomaly_entry import register_bills_anomalies
from app.modules.bills.anomaly_manifest import ANOMALY_MANIFEST
from app.storage.mock_bank.repository import MockBankStore

from test_report_http_eval import (
    HttpEnvironment, bank_funds, observe_gateway,
)


CASES = json.loads(Path(__file__).with_name("http-extra-cases.json").read_text(encoding="utf-8"))["cases"]


class SelectedPlanner:
    provider = "scripted"
    model_name = "ticket07-bills-http-extra"
    config_version = "routing-only-v1"

    def __init__(self, cap):
        self.capability = cap

    def select(self, text, trusted, catalog, memory, thread_id, context_summary=None):
        assert self.capability in {entry["name"] for entry in catalog}
        return TransferProposal(capability_name=self.capability)


def _formula_row():
    # No real-person data or URL fetch; hostile strings live only in test-bank data.
    return {
        "transaction_id": "EVAL-CSV-FORMULA-ONLY", "account_id": "A1", "user_id": "U1",
        "amount_fen": 3750, "direction": "outflow", "nature": "consumption",
        "category": "dining", "occurred_at": "2026-09-28T12:01:00+08:00",
        "counterparty_id": "EVAL-FORMULA-TEST",
        "counterparty_name": '=HYPERLINK("https://invalid.example","click")',
        "counterparty_account_masked": None, "channel": "模拟测试",
        "summary": "@SUM(1,1)",
    }


@pytest.fixture
def extra_env(tmp_path, request, monkeypatch):
    env = HttpEnvironment(tmp_path)
    kind = request.node.callspec.params["case"]["kind"]
    if kind == "csv_formula":
        assert MockBankStore(env.bank_path).seed_ledger_rows([_formula_row()]) == 1
    before = bank_funds(env.bank_path)
    integrity = {}
    for name in ("list_accounts", "list_transactions", "create_verification", "verify_code",
                 "submit_transfer", "cancel_subscription"):
        observe_gateway(env, monkeypatch, name)
    request.node.user_properties.extend([
        ("http_observations", env.observations),
        ("bank_integrity", integrity), ("bank_calls", env.bank_calls),
    ])
    try:
        yield env
    finally:
        after = bank_funds(env.bank_path)
        integrity.update(
            before_funds_sha256=before, after_funds_sha256=after,
            accounts_ledger_unchanged=before == after,
            verification_challenge_count=env.verification_count(),
            funds_submit_calls=sum(
                row["method"] in {"submit_transfer", "cancel_subscription"}
                for row in env.bank_calls
            ),
        )
        assert before == after, "bank balances/ledger changed after read/export path"
        assert integrity["funds_submit_calls"] == 0, "a bills query must not write funds"
        assert env.observations and (env.bank_calls or kind == "l02_cancel")


def _route(env, cap):
    if cap == "bills.detect_anomalies":
        register_bills_anomalies(
            env.runtime.harness.registry, _bills_reads_factory(env.runtime),
            env.bank_clock,
        )
        expected = ANOMALY_MANIFEST.capabilities[0]
        original = env.runtime.harness.authorize_capability

        def admit(trusted, declaration):
            if declaration.name == expected.name:
                return (trusted.user_id == "U1"
                        and trusted.demo_round_id == "D1"
                        and declaration == expected)
            return original(trusted, declaration)

        # This is a declared test admission callback, never production-policy approval.
        env.runtime.harness.authorize_capability = admit
    env.runtime.harness.planner = SelectedPlanner(cap)


def _new_task(env, client, text):
    env.enter(client)
    thread_id = env.request(client, "POST", "/threads", expected=200).json()["data"]["thread_id"]
    env.ids["thread_id"] = thread_id
    env.request(client, "POST", f"/threads/{thread_id}/messages", expected=202, text=text)
    items = env.request(client, "GET", f"/tasks?thread_id={thread_id}", expected=200).json()["data"]["items"]
    assert len(items) == 1, items
    task = items[0]
    env.ids.update(task_id=task["task_id"], run_id=task["run_id"])
    assert task["module"] == "bills"
    return task


def _answer(env, client, task, *, label=None, index=None):
    options = task["interaction"]["options"]
    if label is not None:
        matches = [item for item in options if item["label"] == label]
        assert len(matches) == 1, (label, options)
        picked = matches[0]
    else:
        assert index is not None and 0 <= index < len(options)
        picked = options[index]
    return env.request(
        client, "POST", f"/tasks/{task['task_id']}/inputs", expected=200,
        interaction_id=task["interaction"]["interaction_id"],
        selected_option_id=picked["id"],
    ).json()["data"]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_extra_bills_http_scenario(case, extra_env):
    env = extra_env
    kind = case["kind"]
    cap = ("bills.detect_anomalies" if kind.startswith("l02_")
           else "bills.summarize" if kind.startswith("l01_")
           else "bills.generate_report")
    _route(env, cap)
    with TestClient(env.app) as client:
        task = _new_task(env, client, case["input"])
        assert env.runtime.harness.registry.get(cap).manifest is not None

        if kind == "l01_summary":
            assert task["status"] == "succeeded"
            data = SpendingSummary.model_validate(task["data"])
            assert data.transaction_count == 18
            assert data.consumption_gross_fen == 586400
            assert data.consumption_net_fen == 581900
            assert env.bank_calls

        elif kind == "l01_details":
            assert task["status"] == "succeeded"
            data = BillDetails.model_validate(task["data"])
            assert data.category == "dining"
            assert len(data.transactions) == 3
            assert data.scope.start_at.year == 2026
            assert data.scope.start_at.month == 9

        elif kind == "l01_clarification":
            assert task["status"] == "waiting_input"
            assert not any(x["method"] == "list_transactions" for x in env.bank_calls)
            first_id = task["task_id"]
            task = _answer(env, client, task, label="上月")
            assert task["status"] == "waiting_input" and task["task_id"] == first_id
            task = _answer(env, client, task, label="所有本人账户")
            assert task["status"] == "succeeded" and task["task_id"] == first_id
            summary = SpendingSummary.model_validate(task["data"])
            assert summary.consumption_gross_fen == 586400

        elif kind == "l02_candidate":
            assert task["status"] == "waiting_input"
            candidates = TransactionCandidates.model_validate(task["data"]).candidates
            assert len(candidates) > 1
            first_id = task["task_id"]
            after = _answer(env, client, task, index=0)
            assert after["task_id"] == first_id and after["status"] == "succeeded"
            result = AnomalyResult.model_validate(after["data"])
            assert result.transaction == candidates[0]
            assert [x.rule_id for x in result.checks] == [1, 2, 3, 4]

        elif kind == "l02_scan":
            assert task["status"] == "succeeded"
            data = AnomalyResult.model_validate(task["data"])
            assert data.transaction is None
            assert [c.rule_id for c in data.checks] == [4]
            assert all(f.rule_id == 4 for f in data.findings)

        elif kind == "l02_no_match":
            assert task["status"] == "waiting_input"
            candidates = TransactionCandidates.model_validate(task["data"]).candidates
            assert len(candidates) == 0
            assert "没有符合线索" in task["message"]
            assert task["interaction"]["kind"] == "input"

        elif kind == "l02_cancel":
            assert task["status"] == "waiting_input"
            stopped = env.request(
                client, "POST", f"/tasks/{task['task_id']}/cancel", expected=200,
            ).json()["data"]
            assert stopped["task_id"] == task["task_id"]
            assert stopped["status"] == "cancelled"
            assert not any(x["method"] == "list_transactions" for x in env.bank_calls)

        elif kind == "csv_formula":
            assert task["status"] == "succeeded"
            report = BillReport.model_validate(task["data"])
            assert report.summary.transaction_count == 19
            assert report.summary.consumption_gross_fen == 586400 + 3750
            export = env.export(client, report, "details")
            assert export["status"] == "waiting_verification"
            challenge = env.challenge(client, export)
            verified = env.submit_code(client, challenge, env.code(client, challenge))
            assert verified["kind"] == "verified"
            downloaded = env.downloaded(client, export, 200)
            assert downloaded.headers["cache-control"] == "no-store"
            assert downloaded.headers["content-type"].startswith("text/csv")
            records = list(csv.DictReader(io.StringIO(downloaded.text)))
            matched = [r for r in records if r["transaction_id"] == "EVAL-CSV-FORMULA-ONLY"]
            assert len(matched) == 1
            # Prefixes prevent formula execution without altering original bank facts.
            assert matched[0]["counterparty_name"].startswith("'=HYPERLINK(")
            assert matched[0]["summary"] == "'@SUM(1,1)"
            assert len(records) == 19

        else:
            pytest.fail("scenario not implemented: " + kind)

        if kind == "l02_cancel":
            assert env.bank_calls == []
            env.observations.append({"action": "zero_bank_read_asserted",
                                     "task_id": task["task_id"], "actual_reads": 0})
        else:
            assert env.bank_calls
        assert all(row["user_id"] == "U1" and row["demo_round_id"] == "D1"
                   for row in env.bank_calls)
