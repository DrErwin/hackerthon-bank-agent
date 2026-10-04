from contextlib import closing
"""Isolated real composition and observations, never the developer's demo stores."""

from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import gc
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.agent_platform.model import ReplyOnly, TransferProposal
from app.agent_platform.transfer_runtime import TransferRuntime
from app.api.app import ApiConfig, create_app
from app.audit.journal import AuditJournal, redact
from app.contracts.bank import BankError, SavedPayee
from app.memory.adapter import MemoryAdapter
from app.modules.transfer.tools import TransferSnapshots
from app.security.demo_policy import DemoRiskEvidence, DemoRiskSignal, DemoSecurityPolicy
from app.security.gate import RiskFactsUnavailable
from app.services.mock_bank.core import MockBankService, PAYEES
from app.storage.application import ApplicationStore
from app.storage.mock_bank.repository import MockBankStore

SECRET = b"transfer-evaluation-isolated-secret" * 2
ADMIN_KEY = "evaluation-admin-only"


class EvalClock:
    def __init__(self):
        self.at = datetime.now(timezone.utc)
        self.elapsed = 0.0

    def now(self): return self.at

    def advance(self, seconds):
        self.at += timedelta(seconds=seconds)
        self.elapsed += seconds


class RecordingPlanner:
    """Capture actual public proposal, safely; no fake live fallback."""

    def __init__(self, plan, delegate=None):
        self.plan, self.delegate = plan, delegate
        self.provider = delegate.provider if delegate else "offline-fixture"
        self.model_name = delegate.model_name if delegate else "fixed-proposal"
        self.config_version = delegate.config_version if delegate else "transfer-matrix-v1"
        self.records = []

    def select(self, intent_text, trusted, catalog, memory, thread_id):
        record = {"input": redact(intent_text), "provider": self.provider,
                  "model": self.model_name, "outcome": None}
        self.records.append(record)
        if self.plan.variant == "INP-17":
            record["error_type"] = "InjectedProviderTimeout"
            raise TimeoutError("injected provider outage")
        try:
            if self.delegate:
                outcome = self.delegate.select(intent_text, trusted, catalog, memory, thread_id)
            elif self.plan.variant in ("INP-16", "INP-18") or intent_text in ("嗯", "好", "行", "确认，直接转吧", "再转一次", "结果怎么样"):
                outcome = ReplyOnly(message="请使用当前任务的专用入口，资金尚未新增提交。")
            else:
                outcome = TransferProposal(payee_hint=self.plan.hint, amount_fen=self.plan.amount,
                                           payer_account_id=self.plan.payer)
            record["outcome"] = redact(outcome.model_dump(mode="json"))
            return outcome
        except Exception as exc:
            record["error_type"] = type(exc).__name__
            raise


class Environment:
    def __init__(self, directory: Path, case, plan, delegate=None):
        self.directory, self.case, self.plan = directory, case, plan
        directory.mkdir(parents=True, exist_ok=True)
        self.clock, self.stack = EvalClock(), ExitStack()
        self.planner = RecordingPlanner(plan, delegate)
        self.steps, self.assertions, self.submissions, self.bank_reads = [], [], [], []
        self.secrets = ["eval-secret-credential"]
        self.current_round = "D1"
        self.risk = plan.risk
        self.task, self.thread, self.session = None, None, None
        self.allowed = set()
        self.allow(plan.payer or "A5", plan.target, plan.amount or 50_000)
        if plan.target == "A9": self.allow(plan.payer or "A1", "A8", plan.amount or 50_000)
        for amount in (plan.setup.get("change_amount"), 6000 if plan.variant == "INP-13" else None,
                       60_000 if plan.variant == "VFY-20" else None):
            if amount: self.allow(plan.payer or "A1", plan.target, amount)
        if plan.setup.get("change_payee"): self.allow("A1", plan.setup["change_payee"], 50_000)
        if plan.setup.get("change_payer"): self.allow(plan.setup["change_payer"], plan.target, 50_000)
        self.stack.enter_context(patch("app.api.service.now", self.clock.now))
        clock = self.clock
        class WallTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return clock.at.astimezone(tz) if tz else clock.at.replace(tzinfo=None)
        for module in ("app.storage.application", "app.memory.adapter", "app.agent_platform.harness"):
            self.stack.enter_context(patch(module + ".datetime", WallTime))
        # Banking calendar remains fixed while wall-clock TTL and reconciliation
        # advance. History rows use this bank-recognized date/year.
        self.stack.enter_context(patch("app.services.mock_bank.core._now", lambda: self.bank_date))
        self.bank_date = self.clock.at.astimezone(timezone(timedelta(hours=8)))
        if plan.setup.get("family"):
            for ident in ("A8", "A9"):
                values = list(PAYEES[ident]); values[3] = "家人"
                self.stack.enter_context(patch.dict(PAYEES, {ident: tuple(values)}))
        self.bank = MockBankService(MockBankStore(directory / "bank.sqlite"), demo_secret=SECRET)
        self.bank.seed_demo(include_evaluation=True)
        self.prepare_accounts()
        self.build()
        self.baseline = self.bank_state()

    def allow(self, payer, target, amount):
        kind = "own" if target == "A5" else "saved"
        self.allowed.add((payer, kind, target, amount))
        # F36 manual matching is independently checked by the bank, then binds
        # immutable raw account details only in controlled snapshots.
        if target in PAYEES:
            self.allowed.add((payer, "manual", PAYEES[target][2], amount))

    def prepare_accounts(self):
        setup = self.plan.setup
        with closing(sqlite3.connect(self.bank.store.path)) as connection, connection:
            if setup.get("fund_a5"):
                connection.execute("UPDATE accounts SET book_balance_fen=100000 WHERE account_id='A5'")
            if setup.get("closed"):
                connection.execute("UPDATE accounts SET account_status='closed' WHERE account_id='A8_ACC'")
            if setup.get("account_type"):
                connection.execute("UPDATE accounts SET account_type=? WHERE account_id='A1'", (setup["account_type"],))
        if setup.get("day_history"):
            self.history(setup["day_history"], self.bank_date)
            self.check("fixture.day_remaining", self.bank.get_limits("U1", "A1").data.daily_remaining_fen == 50_000)
        if setup.get("annual_history"):
            self.history(setup["annual_history"], self.bank_date - timedelta(days=1))
            self.check("fixture.annual_remaining", self.bank.get_limits("U1", "A1").data.annual_remaining_fen == 40_000)

    def history(self, amount, date):
        # Bank-owned storage test seam loads actual historical outflow, so B05
        # itself computes consumed limits; no shadow limit rules in the runner.
        self.bank.store.commit_operation("U1", str(uuid4()), "evaluation.history",
            {"fixture": "historical-transfer", "amount": amount}, "succeeded", {}, date.isoformat(),
            [], [(str(uuid4()), "A1", amount, "outflow", "transfer", "transfer", date.isoformat())])

    def risk_facts(self, context, action, declaration):
        if declaration.side_effect:
            values = self.runtime.snapshots.resolve(context, action)
            payee = values.get("payee", {})
            binding = (values.get("payer_account_id"), payee.get("kind"),
                       payee.get("payee_id") or payee.get("account_id") or payee.get("account_number"),
                       values.get("amount_fen"))
            if binding not in self.allowed or self.risk == "missing":
                raise RiskFactsUnavailable("evaluation fixture absent", rule_id="eval-binding-required", policy_version="eval-v1")
        signals = frozenset(DemoRiskSignal(v) for v in (
            ["new_payee"] if declaration.side_effect and self.risk == "medium" else
            ["impersonation"] if declaration.side_effect and self.risk == "high" else
            ["familiar_payee", "familiar_device", "usual_amount_range", "clear_request"]))
        return DemoRiskEvidence("evaluation-fixture", "v1", self.case["id"].replace("[", "-").replace("]", ""),
                                signals, frozenset(DemoRiskSignal))

    def build(self):
        application = ApplicationStore(self.directory / "application.sqlite")
        self.policy = DemoSecurityPolicy(demo_user_id="U1", admin_actor_id="demo-admin",
            current_demo_round=lambda: self.current_round, risk_facts=self.risk_facts)
        self.runtime = TransferRuntime(application, MemoryAdapter(application, active_round=lambda: self.current_round),
            AuditJournal(application.path), self.bank, self.planner,
            authorize_capability=self.policy.authorize_capability, authorize_tool=self.policy.authorize_tool,
            assess_risk=self.policy.assess_risk, authorize_face=self.policy.authorize_face)
        self.runtime.confirmations._clock = self.clock.now
        self.bank.verification.clock = self.clock.now
        original_factory = self.runtime.harness.registry.get("transfer.start_transfer").factory
        # The runtime constructs a real transfer graph; use its existing clock
        # seam to test 10-second deadlines without sleeping for every sample.
        def factory(*args):
            flow = original_factory(*args)
            flow.monotonic = lambda: self.clock.elapsed
            flow.sleep = self.clock.advance
            flow.ports.tools.gate.clock = self.clock.now
            return flow
        registration = self.runtime.harness.registry.get("transfer.start_transfer")
        self.stack.enter_context(patch.dict(self.runtime.harness.registry._entries,
            {"transfer.start_transfer": replace(registration, factory=factory)}))
        self.api = create_app(self.runtime, ApiConfig(secret=SECRET, admin_key=ADMIN_KEY,
                                                     origins=("http://testserver",)))
        self.client = TestClient(self.api, raise_server_exceptions=False)
        self.client.__enter__()
        self.service = self.api.state.api
        if self.session:
            self.client.cookies.set("bank_session", self.session, domain="testserver.local", path="/api/v1")
        else:
            self.post("/session/enter")
            self.session = self.client.cookies.get("bank_session")
            self.thread = self.post("/threads").json()["data"]["thread_id"]
        self.original_submit = self.bank.submit_transfer
        self.bank.submit_transfer = self.observe_submit
        self.original_reads = {}
        for name in ("list_payees", "precheck_transfer", "get_operation"):
            original = getattr(self.bank, name)
            self.original_reads[name] = original
            def read(*args, _name=name, _call=original, **kwargs):
                result = _call(*args, **kwargs)
                self.bank_reads.append({"method": _name, "result": redact(result.model_dump(mode="json"))})
                return result
            setattr(self.bank, name, read)

    def observe_submit(self, *args, **kwargs):
        trusted, operation_id = args[:2]
        # At the actual bank boundary, audit must already contain an execution
        # ALLOW with trusted confirmation/verification snapshot.
        with closing(sqlite3.connect(self.runtime.application.path)) as connection, connection:
            rows = connection.execute("SELECT event_json FROM audit_events WHERE task_id=?", (trusted.task_id,)).fetchall()
            decisions = [json.loads(r[0])["payload"]["decision"] for r in rows if json.loads(r[0])["event_type"] == "security.decided"]
            decisions = [d for d in decisions if d["phase"] == "execution" and d["operation_id"] == str(operation_id) and d["decision"] == "allow"]
            snapshot = None
            if decisions and decisions[-1]["authorization_snapshot_ref"]:
                row = connection.execute("SELECT content FROM audit_evidence WHERE evidence_id=?",
                    (decisions[-1]["authorization_snapshot_ref"],)).fetchone()
                snapshot = json.loads(row[0]) if row else None
        authorized = (snapshot is not None and snapshot.get("confirmation", {}).get("decision") == "approved"
                      and bool(snapshot.get("verifications")) and snapshot.get("operation_id") == str(operation_id))
        self.submissions.append({"operation_id": str(operation_id), "task_id": trusted.task_id,
                                 "authorized": bool(authorized), "at": self.clock.at.isoformat()})
        return self.original_submit(*args, **kwargs)

    def post(self, path, *, client=None, **body):
        headers = {"Origin": "http://testserver"}
        admin_key = body.pop("admin_key", None)
        if admin_key: headers["X-Demo-Admin-Key"] = admin_key
        response = (client or self.client).post("/api/v1" + path, json={"request_id": str(uuid4()), **body},
                                               headers=headers)
        # Deliberately no raw request body, demo-code or exception text.
        self.steps.append({"entry": path, "http_status": response.status_code,
                           "response": redact(response.json()) if response.headers.get("content-type", "").startswith("application/json") else "controlled transport error",
                           "submit_calls": len(self.submissions), "ledger": self.bank_state()["outflow"]})
        return response

    def start(self, text=None, request_id=None):
        response = self.post(f"/threads/{self.thread}/messages", text=text or self.plan.text,
                             **({"request_id": request_id} if request_id else {}))
        self.message_response = response
        items = self.client.get("/api/v1/tasks", params={"thread_id": self.thread}).json()["data"]["items"]
        if items:
            self.task = items[-1]
        return self.task

    def get_task(self):
        if self.task:
            response = self.client.get(f"/api/v1/tasks/{self.task['task_id']}")
            if response.status_code == 200: self.task = response.json()["data"]
        return self.task

    def trusted(self):
        who = self.service.identity(self.session)
        return self.service.trusted(who, self.task["task_id"])

    def resume_fields(self, **fields):
        who = self.service.identity(self.session)
        self.service.continue_task(who, self.task["task_id"], {"fields": fields})
        self.get_task()
        self.snapshot("platform.provide_fields")

    def input(self, **body):
        r = self.post(f"/tasks/{self.task['task_id']}/inputs",
                      interaction_id=self.task["interaction"]["interaction_id"], **body)
        self.get_task()
        return r

    def confirmation(self):
        if self.task["interaction"]["kind"] == "confirmation":
            self.last_confirmation = self.client.get(f"/api/v1/confirmations/{self.task['interaction']['record_ref']}").json()["data"]
        return self.last_confirmation

    def approve(self):
        self.check("preconfirm.Z", len(self.submissions) == 0 and self.bank_state() == self.baseline)
        c = self.confirmation()
        r = self.post(f"/confirmations/{c['confirmation_id']}/answer",
                      confirmation_version=c["confirmation_version"], choice="approve")
        self.get_task()
        return r

    def challenge(self):
        return self.runtime.gateway.get_verification(self.trusted(), self.task["interaction"]["record_ref"])

    def code(self, wrong=False, submission_id=None):
        challenge = self.challenge()
        code = self.runtime.gateway.get_demo_code_for_api(self.trusted(), challenge.challenge_id)
        self.secrets.append(code)
        r = self.post(f"/verifications/{challenge.challenge_id}/code",
                      submission_id=submission_id or str(uuid4()), code="not-the-code" if wrong else code)
        self.get_task()
        return r

    def face(self, result="passed", admin=True):
        challenge = self.challenge()
        self.post(f"/verifications/{challenge.challenge_id}/face/start")
        other = TestClient(self.api, raise_server_exceptions=False)
        try:
            self.post("/session/enter", client=other, **({"admin_key": ADMIN_KEY} if admin else {}))
            r = self.post(f"/admin/verifications/{challenge.challenge_id}/face-result", client=other,
                          submission_id=str(uuid4()), demo_round_id="D1", result=result)
        finally:
            other.close()
        self.get_task()
        return r

    def complete(self):
        if self.task and self.task["status"] == "waiting_approval" and self.task["interaction"]["kind"] == "confirmation":
            self.approve()
        if self.task and self.task["status"] == "waiting_approval" and self.task["interaction"]["kind"] == "verification":
            self.check("preverification.Z", len(self.submissions) == 0 and self.bank_state() == self.baseline)
            self.code()
            if self.risk == "medium" and self.task["status"] == "waiting_approval": self.face()
        self.get_task()

    def code_without_continuation(self, face=False):
        """Real bank record + binding, stopping before the application resumes."""
        from app.services.mock_bank.verification import AdminContext
        challenge = self.challenge()
        code = self.runtime.gateway.get_demo_code_for_api(self.trusted(), challenge.challenge_id)
        self.secrets.append(code)
        outcome = self.runtime.gateway.verify_code(self.trusted(), challenge.challenge_id, uuid4(), code)
        if face:
            self.runtime.gateway.start_face(self.trusted(), challenge.challenge_id, uuid4())
            outcome = self.runtime.gateway.verify_face(AdminContext("demo-admin", True, "D1", "U1"),
                challenge.challenge_id, uuid4(), "passed")
        if outcome.verification_id:
            self.runtime.bind_verification(self.trusted(), outcome.verification_id)
        self.saved_verification = {"challenge_id": challenge.challenge_id, "verification_id": outcome.verification_id}
        self.snapshot("bank.verify_without_application_continuation")

    def restart(self, bank=True):
        self.client.__exit__(None, None, None)
        self.runtime.close()
        self.bank.submit_transfer = self.original_submit
        for name, original in self.original_reads.items(): setattr(self.bank, name, original)
        before = self.bank_state()
        if bank:
            self.bank = MockBankService(MockBankStore(self.directory / "bank.sqlite"), demo_secret=SECRET)
        self.build()
        self.check("restart.same_bank_balances", self.bank_state()["balances"] == before["balances"])
        self.get_task()
        self.snapshot("restart.same_application_and_bank_paths")

    def bank_state(self):
        with closing(sqlite3.connect(self.bank.store.path)) as c, c:
            balances = dict(c.execute("SELECT account_id, book_balance_fen FROM accounts"))
            outflow = c.execute("SELECT COUNT(*) FROM ledger_entries WHERE direction='outflow'").fetchone()[0]
        return {"balances": balances, "outflow": outflow}

    def ledger(self):
        with closing(sqlite3.connect(self.bank.store.path)) as c, c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute("SELECT * FROM ledger_entries WHERE direction='outflow'")]

    def snapshot(self, entry):
        self.steps.append({"entry": entry, "task": self.task, "submit_calls": len(self.submissions), "bank": self.bank_state()})

    def check(self, name, condition, actual=None):
        self.assertions.append({"name": name, "passed": bool(condition), "actual": redact(actual)})

    def state(self, expected):
        self.check("task.status", self.task is not None and self.task["status"] == expected,
                   self.task["status"] if self.task else "no_task")

    def zero(self):
        self.check("funds.Z", len(self.submissions) == 0 and self.bank_state() == self.baseline,
                   {"calls": len(self.submissions), "bank": self.bank_state()})

    def success(self, amount=None, target=None, payer=None):
        self.state("succeeded")
        if not self.task: return
        amount = amount if amount is not None else self.plan.amount or 50_000
        target, payer = target or self.plan.target, payer or self.plan.payer or "A5"
        operation = self.task["data"].get("operation")
        op_id = self.task["data"].get("operation_id")
        rows = [r for r in self.ledger() if r["operation_id"] == op_id]
        receipt = operation.get("receipt") if operation else None
        self.check("funds.S.calls", len(self.submissions) == 1 and all(s["authorized"] for s in self.submissions), self.submissions)
        self.check("funds.S.outflow", len(rows) == 1 and rows[0]["amount_fen"] == amount and rows[0]["account_id"] == payer, rows)
        self.check("funds.S.balance", self.bank_state()["balances"].get(payer) == self.baseline["balances"].get(payer, 0) - amount)
        self.check("funds.S.receipt", receipt is not None and receipt["amount_fen"] == amount
                   and receipt["payee"]["payee_id"] == target and receipt["fee_fen"] == 0
                   and len(rows) == 1 and str(receipt["transaction_id"]) == rows[0]["transaction_id"], receipt)
        bank_op = self.bank.store.get_operation("U1", op_id) if op_id else None
        self.check("funds.S.bank_truth", bank_op is not None and bank_op.status == "succeeded"
                   and bank_op.result.get("receipt") == receipt)
        for account, balance in self.baseline["balances"].items():
            if account != payer and account != target:
                self.check(f"funds.S.other.{account}", self.bank_state()["balances"][account] == balance)
        if target == "A5":
            self.check("funds.S.own_credit", self.bank_state()["balances"][target] == self.baseline["balances"][target] + amount)

    def original(self, task_id, operation_id, submit_count):
        self.check("funds.O.no_resubmit", len(self.submissions) == submit_count)
        self.check("funds.O.original_ids", self.task and self.task["task_id"] == task_id and self.task["data"]["operation_id"] == operation_id)
        self.check("funds.O.at_most_one", len([r for r in self.ledger() if r["operation_id"] == operation_id]) <= 1)

    def scan_secrets(self):
        # Controlled snapshots may store F36 account numbers. Ordinary messages,
        # audit, SSE and results must not. Verification codes may never persist.
        with closing(sqlite3.connect(self.runtime.application.path)) as c, c:
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'") if not r[0].startswith("sqlite_")]
            all_values, ordinary = [], []
            for table in tables:
                rows = c.execute('SELECT * FROM "' + table.replace('"', '""') + '"').fetchall()
                values = json.dumps(rows, ensure_ascii=False, default=lambda v: v.decode("utf-8", errors="ignore") if isinstance(v, bytes) else str(v))
                all_values.append(values)
                if table in ("api_messages", "api_events", "audit_events", "audit_evidence", "tasks", "api_requests", "checkpoints", "checkpoint_blobs", "checkpoint_writes"):
                    ordinary.append(values)
        persisted = "\n".join(all_values)
        with closing(sqlite3.connect(self.bank.store.path)) as c, c:
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'") if not r[0].startswith("sqlite_")]
            for table in tables:
                rows = c.execute('SELECT * FROM "' + table.replace('"', '""') + '"').fetchall()
                persisted += json.dumps(rows, ensure_ascii=False, default=str)
        public = "\n".join(ordinary) + json.dumps(self.planner.records, ensure_ascii=False)
        for secret in self.secrets:
            self.check("redaction.credential", secret not in persisted, {"secret": "[withheld]"})
        for target in ("A2", "A8", "A12"):
            for raw in (PAYEES[target][2], PAYEES[target][5]):
                if raw: self.check("redaction.private_number", raw not in public)

    def close(self):
        self.client.__exit__(None, None, None)
        self.runtime.close()
        self.stack.close()
        # SQLite context managers commit/rollback but don't close connections.
        # Backend test seams retain cyclic graph closures; collect after close
        # before Windows removes this sample's temporary directory.
        gc.collect()
