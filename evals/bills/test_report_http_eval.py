"""Ticket 07: real L03 -> HTTP report resources and two export paths.

FastAPI/TestClient, TransferRuntime/Harness, scoped SQLite, the existing bills
read factory, SecurityGate/executor and the seeded bank are real. Only planner
routing, narrow authorization/LOW-risk inputs and bank clocks are scripted.
This does not exercise a live model, browser or production policy approval.
"""
from __future__ import annotations

import csv
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from pydantic import SecretStr

from app.agent_platform.local_demo import _bills_reads_factory
from app.agent_platform.model import TransferProposal
from app.agent_platform.transfer_runtime import TransferRuntime
from app.api.app import ApiConfig, create_app
from app.audit.journal import AuditJournal
from app.contracts.bills import BillReport
from app.contracts.common import RiskLevel
from app.memory.adapter import MemoryAdapter
from app.modules.bills.entry import register_bills, register_bills_report
from app.modules.bills.manifest import MANIFEST, REPORT_MANIFEST
from app.modules.bills.reads import PRIVATE_TOOLS
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore
from app.storage.mock_bank.repository import MockBankStore

BANK_NOW = datetime.fromisoformat("2026-10-14T13:00:00+08:00")
CASES = json.loads(Path(__file__).with_name("report-http-cases.json").read_text(encoding="utf-8"))["cases"]
ORIGIN = "http://testserver"


class Clock:
    def __init__(self, at):
        self.at = at

    def __call__(self):
        return self.at


class ReportPlanner:
    provider = "scripted"
    model_name = "ticket07-http-L03"
    config_version = "test-routing-only-v1"

    def __init__(self):
        self.calls = 0

    def select(self, text, trusted, catalog, memory, thread_id, context_summary=None):
        assert "bills.generate_report" in {item["name"] for item in catalog}
        self.calls += 1
        return TransferProposal(capability_name="bills.generate_report")


def bank_funds(path):
    """Authentication records may change; actual accounts and ledger may not."""
    with sqlite3.connect(path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        # Include all bank tables except the verification service's own records.
        tables = sorted(name for name in tables if not name.startswith("bank_verification"))
        facts = {name: connection.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall()
                 for name in tables}
    raw = json.dumps(facts, sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


class HttpEnvironment:
    def __init__(self, directory):
        self.bank_path = directory / "bank.sqlite"
        self.bank_clock, self.verification_clock = Clock(BANK_NOW), Clock(datetime.now(timezone.utc))
        self.bank = MockBankService(MockBankStore(self.bank_path), demo_secret=b"h" * 32,
                                    clock=self.bank_clock)
        self.bank.seed_flow_history()
        # Drive the real bank's expiry calculation; never fabricate a passed/expired record.
        self.bank.verification.clock = self.verification_clock
        self.application = ApplicationStore(directory / "application.sqlite")
        self.planner, self.observations = ReportPlanner(), []
        self.bank_calls, self.authorization = [], []
        allowed = {item.name: item for item in (*MANIFEST.capabilities, *REPORT_MANIFEST.capabilities)}
        private = {item.name: item for item in PRIVATE_TOOLS}

        def capability(context, declaration):
            return (context.user_id == "U1" and context.demo_round_id == "D1"
                    and allowed.get(declaration.name) == declaration)

        def tool(context, action, declaration):
            result = (context.user_id == "U1" and context.demo_round_id == "D1"
                      and private.get(declaration.name) == declaration
                      and action.action_name == declaration.name)
            self.authorization.append({"tool": declaration.name, "allowed": result,
                                       "task_id": context.task_id, "run_id": context.run_id})
            return result

        self.runtime = TransferRuntime(self.application,
            MemoryAdapter(self.application, active_round=lambda: "D1"),
            AuditJournal(self.application.path), self.bank, self.planner,
            authorize_capability=capability, authorize_tool=tool,
            assess_risk=lambda *_: RiskLevel.LOW)
        # The same real task-scoped factory used by local_demo, with explicit test policy.
        reads = _bills_reads_factory(self.runtime)
        register_bills(self.runtime.harness.registry, reads, self.bank_clock)
        register_bills_report(self.runtime.harness.registry, reads, self.bank_clock)
        self.app = create_app(runtime=self.runtime, config=ApiConfig(
            demo_user_id="U1", demo_round_id="D1", secret=b"h" * 32,
            admin_key="ticket07-synthetic-admin", origins=(ORIGIN,)))
        self.owner_session = None
        self.ids = {}

    def request(self, client, method, path, *, expected, **body):
        request_id = str(uuid4()) if method == "POST" else None
        arguments = {"headers": {"Origin": ORIGIN}}
        if method == "POST":
            arguments["json"] = {"request_id": request_id, **{
                key: value.get_secret_value() if isinstance(value, SecretStr) else value
                for key, value in body.items()}}
        started = datetime.now(timezone.utc).isoformat()
        response = client.request(method, "/api/v1" + path, **arguments)
        record = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
            "method": method, "path": path, "request_id": request_id,
            "submission_id": body.get("submission_id"),
            "status_code": response.status_code, "expected_status": expected,
            "content_type": response.headers.get("content-type"),
            "cache_control": response.headers.get("cache-control"),
            "session_id": (client.cookies.get("bank_session") or "").split(".")[0] or None,
            "configured_user_id": client.app.state.api.config.demo_user_id,
            "demo_round_id": client.app.state.api.config.demo_round_id,
            "correlation": dict(self.ids)}
        # No request text, verification code, raw bank rows, cookies or download body is archived.
        if "/demo-code" not in path:
            record["response_sha256"] = hashlib.sha256(response.content).hexdigest()
            record["response_bytes"] = len(response.content)
        if response.headers.get("content-type", "").startswith("application/json"):
            payload = response.json()
            data = payload.get("data") or {}
            record["error_code"] = (payload.get("error") or data.get("error") or {}).get("code")
            record["business_status"] = data.get("status")
            record["verification_outcome"] = data.get("kind") if "/code" in path else None
        self.observations.append(record)
        assert response.status_code == expected, (method, path, response.status_code, response.text)
        return response

    def enter(self, client):
        return self.request(client, "POST", "/session/enter", expected=200).json()["data"]

    def report(self, client):
        self.owner_session = self.enter(client)["session_id"]
        thread = self.request(client, "POST", "/threads", expected=200).json()["data"]["thread_id"]
        self.ids["thread_id"] = thread
        self.request(client, "POST", f"/threads/{thread}/messages", expected=202,
                     text="2026年9月所有账户账单报告")
        listing = self.request(client, "GET", f"/tasks?thread_id={thread}", expected=200).json()["data"]["items"]
        assert len(listing) == 1
        task = listing[0]
        self.ids.update(task_id=task["task_id"], run_id=task["run_id"])
        assert task["status"] == "succeeded" and task["module"] == "bills", task
        report = BillReport.model_validate(task["data"])
        self.ids["report_id"] = report.report_id
        stored = self.application.get_task("U1", "D1", task["task_id"])
        assert stored.snapshot["capability_name"] == "bills.generate_report" and stored.checkpoint_id
        self.ids["checkpoint_id"] = stored.checkpoint_id
        context = self.app.state.api.trusted(self.app.state.api.identity(client.cookies.get("bank_session")), task["task_id"])
        rows = []
        for account_id in report.scope.account_ids:
            result = self.runtime.gateway.list_transactions(context, account_id, report.scope.start_at, report.scope.end_at)
            assert result.kind == "ok" and result.data.as_of == BANK_NOW
            rows.extend(result.data.transactions)
        rows.sort(key=lambda row: (row.occurred_at, row.account_id, row.transaction_id))
        gross = sum(row.amount_fen for row in rows if row.direction == "outflow" and row.nature == "consumption")
        refund = sum(row.amount_fen for row in rows if row.direction == "inflow" and row.nature == "refund")
        assert (report.summary.transaction_count, report.summary.consumption_gross_fen,
                report.summary.consumption_refund_fen, report.summary.consumption_net_fen) == (
                    len(rows), gross, refund, gross - refund)
        assert (len(rows), gross, refund) == (18, 586400, 4500)
        assert report.statistical_days == 30 and report.generated_at == BANK_NOW
        assert self.authorization and all(item["allowed"] for item in self.authorization)
        card = self.request(client, "GET", f"/reports/{report.report_id}", expected=200)
        assert BillReport.model_validate(card.json()["data"]) == report
        assert "transactions" not in card.text
        self.observations.append({"action": "real_report_assertions", **self.ids,
            "scope": report.scope.model_dump(mode="json"), "transaction_count": len(rows),
            "gross_fen": gross, "refund_fen": refund, "net_fen": gross - refund,
            "source_as_of": [item.model_dump(mode="json") for item in report.summary.source_as_of],
            "planner_calls": self.planner.calls, "gate_authorizations": list(self.authorization)})
        return report, rows

    def export(self, client, report, kind):
        export = self.request(client, "POST", f"/reports/{report.report_id}/exports",
                              expected=200, kind=kind).json()["data"]
        self.ids.update(export_id=export["export_id"], export_task_id=export["task_id"])
        return export

    def challenge(self, client, export):
        task = self.request(client, "GET", f"/tasks/{export['task_id']}", expected=200).json()["data"]
        assert task["module"] == "bills" and task["status"] == "waiting_approval"
        assert task["interaction"]["kind"] == "verification"
        challenge = task["interaction"]["record_ref"]
        self.ids["challenge_id"] = challenge
        return challenge

    def code(self, client, challenge):
        response = self.request(client, "GET", f"/verifications/{challenge}/demo-code", expected=200)
        assert response.headers["cache-control"] == "no-store"
        return SecretStr(response.json()["data"]["code"])

    def submit_code(self, client, challenge, code):
        return self.request(client, "POST", f"/verifications/{challenge}/code", expected=200,
                            submission_id=str(uuid4()), code=code).json()["data"]

    def downloaded(self, client, export, expected):
        return self.request(client, "GET", f"/exports/{export['export_id']}/download", expected=expected)

    def verification_count(self):
        with sqlite3.connect(self.bank_path) as connection:
            return connection.execute("SELECT COUNT(*) FROM bank_verification_challenges").fetchone()[0]


def observe_gateway(env, monkeypatch, name):
    """A forwarding observer: every response still comes from the real gateway."""
    original = getattr(env.runtime.gateway, name)

    def call(context, *args, **kwargs):
        event = {"method": name, "at": datetime.now(timezone.utc).isoformat(),
            "user_id": context.user_id, "session_id": context.session_id,
            "demo_round_id": context.demo_round_id, "task_id": context.task_id,
            "run_id": context.run_id}
        if name == "list_transactions":
            event.update(account_id=args[0], start_at=args[1].isoformat(), end_at=args[2].isoformat())
        env.bank_calls.append(event)
        try:
            result = original(context, *args, **kwargs)
        except Exception as error:
            event.update(outcome="raised", exception_type=type(error).__name__)
            raise
        event["outcome"] = getattr(result, "kind", None)
        if name in {"list_accounts", "list_transactions"} and result.kind == "ok":
            field = "accounts" if name == "list_accounts" else "transactions"
            event["row_count"] = len(getattr(result.data, field))
        return result

    monkeypatch.setattr(env.runtime.gateway, name, call)


@contextmanager
def peer_client(app):
    """Share the already initialized runtime without running its lifespan twice."""
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def http_env(tmp_path, request, monkeypatch):
    env = HttpEnvironment(tmp_path)
    before, integrity = bank_funds(env.bank_path), {}
    for name in ("list_accounts", "list_transactions", "create_verification", "verify_code",
                 "submit_transfer", "cancel_subscription"):
        observe_gateway(env, monkeypatch, name)
    request.node.user_properties.extend([("http_observations", env.observations),
                                        ("bank_integrity", integrity), ("bank_calls", env.bank_calls)])
    try:
        yield env
    finally:
        after = bank_funds(env.bank_path)
        integrity.update(before_funds_sha256=before, after_funds_sha256=after,
                         accounts_ledger_unchanged=before == after,
                         verification_challenge_count=env.verification_count(),
                         funds_submit_calls=sum(item["method"] in {"submit_transfer", "cancel_subscription"}
                                                for item in env.bank_calls))
        assert after == before
        assert integrity["funds_submit_calls"] == 0


def export_reads(env, export):
    return [item for item in env.bank_calls
            if item["method"] == "list_transactions" and item["task_id"] == export["task_id"]]


def assert_csv(response, rows):
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "no-store"
    parsed = list(csv.DictReader(io.StringIO(response.text)))
    expected = [{"occurred_at": row.occurred_at.isoformat(), "account_id": row.account_id,
        "direction": row.direction, "nature": row.nature, "category": row.category,
        "amount_fen": str(row.amount_fen), "counterparty_name": row.counterparty_name,
        "counterparty_account_masked": row.counterparty_account_masked or "",
        "channel": row.channel or "", "summary": row.summary, "transaction_id": row.transaction_id}
        for row in rows]
    assert parsed == expected


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_report_http_case(case, http_env):
    env, number = http_env, case["id"].rsplit("-", 1)[1]
    with TestClient(env.app) as client:
        report, rows = env.report(client)
        if number == "01":
            messages = env.request(client, "GET", f"/threads/{env.ids['thread_id']}/messages", expected=200).json()["data"]["items"]
            assistant = [item for item in messages if item["role"] == "assistant"][-1]
            assert assistant["text"] == report.spoken_summary and assistant["report_ids"] == [report.report_id]
            assert env.verification_count() == 0
            assert env.planner.calls == 1

        elif number == "02":
            export = env.export(client, report, "card")
            assert export["status"] == "ready" and export["task_id"] is None
            assert env.verification_count() == 0
            status = env.request(client, "GET", f"/exports/{export['export_id']}", expected=200).json()["data"]
            assert status["status"] == "ready"
            download = env.downloaded(client, export, 200)
            assert download.headers["content-type"].startswith("text/html")
            assert download.headers["cache-control"] == "no-store"
            assert report.spoken_summary in download.text
            assert all(row.transaction_id not in download.text for row in rows)

        elif number in {"03", "04", "05", "07"}:
            export = env.export(client, report, "details")
            assert export["status"] == "waiting_verification" and export["download_path"] is None
            denied = env.downloaded(client, export, 409)
            assert denied.json()["error"]["code"] == "EXPORT_NOT_READY"
            assert not export_reads(env, export)
            challenge = env.challenge(client, export)
            code = env.code(client, challenge)
            if number == "04":
                wrong = SecretStr("000000" if code.get_secret_value() != "000000" else "111111")
                for _ in range(3):
                    rejected = env.submit_code(client, challenge, wrong)
                    assert rejected["kind"] == "rejected"
                    env.downloaded(client, export, 409)
                status = env.request(client, "GET", f"/exports/{export['export_id']}", expected=200).json()["data"]
                assert status["status"] == "failed" and status["error"]["code"] == "VERIFICATION_REJECTED"
                assert rejected["task"]["status"] == "failed"
                assert not export_reads(env, export)
            elif number == "05":
                view = env.request(client, "GET", f"/verifications/{challenge}", expected=200).json()["data"]
                expiry = datetime.fromisoformat(view["code_expires_at"])
                env.verification_clock.at = expiry
                env.observations.append({"action": "advance_verification_clock_to_bank_expiry",
                                         "at": expiry.isoformat(), **env.ids})
                rejected = env.request(client, "POST", f"/verifications/{challenge}/code", expected=409,
                                       submission_id=str(uuid4()), code=code)
                assert rejected.json()["error"]["code"] == "TASK_TERMINATED"
                status = env.request(client, "GET", f"/exports/{export['export_id']}", expected=200).json()["data"]
                assert status["status"] == "failed" and status["error"]["code"] == "VERIFICATION_EXPIRED"
                task = env.request(client, "GET", f"/tasks/{export['task_id']}", expected=200).json()["data"]
                assert task["status"] == "failed"
                env.downloaded(client, export, 409)
                assert not export_reads(env, export)
            else:
                verified = env.submit_code(client, challenge, code)
                assert verified["kind"] == "verified"
                assert verified["task"]["task_id"] == export["task_id"]
                assert verified["task"]["status"] == "succeeded" and verified["task"]["module"] == "bills"
                status = env.request(client, "GET", f"/exports/{export['export_id']}", expected=200).json()["data"]
                assert status["status"] == "ready"
                assert_csv(env.downloaded(client, export, 200), rows)
                reads = export_reads(env, export)
                assert len(reads) == len(report.scope.account_ids)
                assert {item["account_id"] for item in reads} == set(report.scope.account_ids)
                assert sum(item["row_count"] for item in reads) == len(rows)
                assert all(datetime.fromisoformat(item["start_at"]) == report.scope.start_at
                           and datetime.fromisoformat(item["end_at"]) == report.scope.end_at for item in reads)
                if number == "07":
                    with peer_client(env.app) as fresh:
                        assert env.enter(fresh)["session_id"] != env.owner_session
                        env.request(fresh, "GET", f"/reports/{report.report_id}", expected=200)
                        denied = env.downloaded(fresh, export, 409)
                        assert denied.json()["error"]["code"] == "SESSION_RECONFIRMATION_REQUIRED"

        elif number == "06":
            card, details = env.export(client, report, "card"), env.export(client, report, "details")
            challenge = env.challenge(client, details)
            other = create_app(runtime=env.runtime, config=ApiConfig(demo_user_id="U2", demo_round_id="D1",
                secret=b"h" * 32, origins=(ORIGIN,)))
            before = len(env.bank_calls)
            with peer_client(other) as stranger:
                env.enter(stranger)
                env.request(stranger, "GET", f"/reports/{report.report_id}", expected=404)
                env.request(stranger, "POST", f"/reports/{report.report_id}/exports", expected=404, kind="details")
                for export in (card, details):
                    env.request(stranger, "GET", f"/exports/{export['export_id']}", expected=404)
                    env.downloaded(stranger, export, 404)
                env.request(stranger, "GET", f"/verifications/{challenge}/demo-code", expected=404)
            assert len(env.bank_calls) == before

        else:
            pytest.fail(f"unimplemented HTTP scenario: {case['id']}")
