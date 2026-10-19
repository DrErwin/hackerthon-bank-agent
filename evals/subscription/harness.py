"""Platform-runtime harness for the scenario-05 goldens (no HTTP layer, no bank double).

One assembly per evaluation: the real mock bank (B29/B30 and seeded facts), the real
``SecurityGate``/``DeterministicExecutor``, the real demo policy, the real audit journal
and stores, and the module's own checkpointed state machine. Only the model entry is a
scripted stand-in, because these cases pin deterministic routing, not model quality.
"""

from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from app.agent_platform.model import TransferProposal
from app.agent_platform.subscription_runtime import (
    CANCEL_TOOL, register_subscription, subscription_risk_evidence,
)
from app.agent_platform.transfer_runtime import TransferRuntime
from app.audit.journal import AuditJournal
from app.contracts.bank import BankError, QueryFailure
from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.security import ConfirmationAnswer
from app.memory.adapter import MemoryAdapter
from app.security.demo_policy import DemoRiskEvidence, DemoRiskSignal, DemoSecurityPolicy
from app.security.gate import RiskFactsUnavailable
from app.services.mock_bank import subscriptions as bank_subscriptions
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore
from app.storage.database import connect, transaction
from app.storage.mock_bank.repository import MockBankStore


# The bank clock of the demo day: 2026-10-19 12:00 Beijing, so every seeded offset and
# the 30-day reminder window are deterministic.
NOW = datetime(2026, 10, 19, 4, 0, tzinfo=timezone.utc)
DEMO_SECRET = b"subscription-eval-secret-is-at-least-32-bytes"
LIST_CAPABILITY = "subscription.list_subscriptions"
CANCEL_CAPABILITY = "subscription.cancel_subscription"
READ_SIGNALS = frozenset({
    DemoRiskSignal.FAMILIAR_PAYEE, DemoRiskSignal.FAMILIAR_DEVICE,
    DemoRiskSignal.USUAL_AMOUNT_RANGE, DemoRiskSignal.CLEAR_REQUEST,
})
ALL_SIGNALS = frozenset(DemoRiskSignal)
# Promises the bank cannot keep; they must never appear in any subscription output.
# The list is semantic, not a blacklist: a merchant-side entitlement the bank cannot
# guarantee is forbidden even when worded differently from the frozen phrase.
FORBIDDEN_PROMISES = (
    "会员可用至", "还能用到", "先退订再重新订阅", "先解约再重签",
    "继续享受", "会员有效", "到期日", "可以用到", "会员可以继续", "权益可用",
)
# The one promise the confirmation card and the receipt are allowed to make.
CANCEL_PROMISE = "从下一期（{date}）起不再自动扣费，之前已经扣掉的钱不退"


def billing_date(offset_days: int) -> str:
    """The bank's own next-debit date for a seeded offset (billing hour 09:00)."""

    at = (NOW + timedelta(days=offset_days)).replace(hour=9, minute=0, second=0, microsecond=0)
    return at.date().isoformat()


def trusted(task="T1", run="R1", session="S1", *, user="U1", round_id="D1"):
    return TrustedContext(user_id=user, session_id=session, task_id=task, run_id=run,
                          parent_task_id=None, demo_round_id=round_id)


def open_session(application, session_id="S1", *, user="U1", round_id="D1"):
    at = datetime.now(timezone.utc)
    application.create_session(session_id, user, round_id, at.isoformat(),
                               (at + timedelta(days=1)).isoformat())


class RoutedPlanner:
    """Scripted model entry: the platform route under test is the capability name."""

    provider = "scripted"
    model_name = "subscription-eval"
    config_version = "eval-v1"

    def __init__(self, capability=LIST_CAPABILITY):
        self.capability = capability
        self.calls = 0
        self.catalogs = []

    def select(self, intent_text, trusted, catalog, memory, thread_id, context_summary=None):
        self.calls += 1
        self.catalogs.append([item["name"] for item in catalog])
        return TransferProposal(capability_name=self.capability)


@dataclass
class Composition:
    """One assembled runtime plus the handles a case needs to inspect bank state."""

    application: ApplicationStore
    bank: MockBankService
    planner: RoutedPlanner
    runtime: TransferRuntime
    policy: DemoSecurityPolicy
    # The owner this assembly was built for; multi-user cases drive another user.
    user: str = "U1"
    round_id: str = "D1"

    def close(self) -> None:
        self.runtime.close()


def _write_seed_override(tmp_path, rows) -> Path:
    """A full mandate seed file = the shipped seeds plus the case's own rows."""

    seeds = json.loads(
        (bank_subscriptions.SEEDS_DIR / bank_subscriptions.MANDATE_SEED_FILE)
        .read_text(encoding="utf-8"))
    seeds.extend(rows)
    target = Path(tmp_path) / "seed-override"
    target.mkdir(parents=True, exist_ok=True)
    (target / bank_subscriptions.MANDATE_SEED_FILE).write_text(
        json.dumps(seeds, ensure_ascii=False), encoding="utf-8")
    return target


def composition(tmp_path, *, seed_flows=True, clock=NOW, user="U1", round_id="D1",
                session_id="S1", extra_mandates=None, extra_flows=None) -> Composition:
    """Real services end to end.

    ``seed_flows=False`` keeps the ledger empty (SF07); ``extra_mandates`` / ``extra_flows``
    append case-owned facts without touching the shipped demo seeds.
    """

    tmp_path = Path(tmp_path)
    suffix = "" if (user, round_id) == ("U1", "D1") else f"-{user}-{round_id}"
    path = tmp_path / f"application{suffix}.sqlite"
    application = ApplicationStore(path)
    memory = MemoryAdapter(application, active_round=lambda: round_id)
    seed_dir = _write_seed_override(tmp_path, extra_mandates) if extra_mandates else None
    with patch.object(bank_subscriptions, "SEEDS_DIR", seed_dir) if seed_dir else _noop():
        bank = MockBankService(MockBankStore(tmp_path / f"bank{suffix}.sqlite"),
                               demo_secret=DEMO_SECRET, clock=lambda: clock)
    if seed_flows:
        bank.seed_flow_history()
    if extra_flows:
        bank.store.seed_ledger_rows(extra_flows)
    wiring: dict = {}
    read_evidence = DemoRiskEvidence(
        source="server-eval-fixture", source_version="facts-v1", evidence_ref="read",
        signals=READ_SIGNALS, checked_signals=ALL_SIGNALS,
    )

    def risk_facts(context, action, declaration):
        if not declaration.side_effect:
            return read_evidence
        if declaration.name == CANCEL_TOOL:
            subscription = wiring.get("subscription")
            payload = (subscription.binding(context.task_id, action.parameters_ref)
                       if subscription is not None else None)
            return subscription_risk_evidence(
                payload, source_version="facts-v1", checked_signals=ALL_SIGNALS,
            )
        raise RiskFactsUnavailable("no server-owned fixture covers this write",
                                   rule_id="eval-fixture-required",
                                   policy_version=DemoSecurityPolicy.policy_version)

    policy = DemoSecurityPolicy(
        demo_user_id=user, admin_actor_id="demo-admin", current_demo_round=lambda: round_id,
        risk_facts=risk_facts,
    )
    planner = RoutedPlanner()
    runtime = TransferRuntime(
        application, memory, AuditJournal(path), bank, planner,
        authorize_capability=policy.authorize_capability,
        authorize_tool=policy.authorize_tool, assess_risk=policy.assess_risk,
        authorize_face=policy.authorize_face,
    )
    wiring["subscription"] = register_subscription(runtime, clock=bank.clock)
    open_session(application, session_id, user=user, round_id=round_id)
    return Composition(application, bank, planner, runtime, policy,
                       user=user, round_id=round_id)


class _noop:
    def __enter__(self):
        return None

    def __exit__(self, *exc_info):
        return False


# --------------------------------------------------------------------------- driving


def owner(comp: Composition, task="T1", run="R1", session=None):
    """The trusted context this assembly accepts (its own user and demo round)."""

    return trusted(task, run, session or "S1", user=comp.user, round_id=comp.round_id)


def start(comp: Composition, text, *, task="T1", run="R1", capability=CANCEL_CAPABILITY):
    comp.planner.capability = capability
    return comp.runtime.harness.start(owner(comp, task, run), uuid4(), text)


def resume(comp: Composition, task="T1", run="R2", *, session=None, **response):
    return comp.runtime.harness.resume(owner(comp, task, run, session), response)


def recover_to_new_session(comp: Composition, task="T1", *, run="R9", session="S2"):
    """A fresh login session takes over the owned task; the old one keeps nothing."""

    open_session(comp.application, session, user=comp.user, round_id=comp.round_id)
    return comp.runtime.harness.recover_session(owner(comp, task, run, session))


def pending_binding(comp: Composition, task_id):
    connection = connect(comp.application.path)
    try:
        row = connection.execute(
            "SELECT operation_id, action_revision FROM agent_transfer_confirmations WHERE task_id = ?",
            (task_id,),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None, "no pending confirmation binding for this task"
    return UUID(row["operation_id"]), row["action_revision"]


def confirmation_for(comp: Composition, trusted_owner, pending=None):
    operation_id, revision = pending_binding(comp, trusted_owner.task_id)
    context = comp.runtime._context(trusted_owner, operation_id, revision)
    assert context.confirmation_id is not None
    record = comp.runtime.confirmations.get(context, context.confirmation_id)
    if pending is not None:
        assert pending.interaction.record_ref == record.confirmation_id
    return record


def approve(comp: Composition, trusted_owner, pending):
    record = confirmation_for(comp, trusted_owner, pending)
    assert record.decision == "pending"
    comp.runtime.answer_confirmation(trusted_owner, ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version, choice="approve",
    ))
    return record


def verify_by_code(comp: Composition, trusted_owner, challenge_id):
    code = comp.runtime.gateway.get_demo_code_for_api(trusted_owner, challenge_id)
    return comp.runtime.gateway.verify_code(trusted_owner, challenge_id, uuid4(), code)


def cancel_to_success(comp: Composition, text, *, task="T1", runs=("R1", "R2", "R3")):
    """Confirm, verify with a fresh code, bind, and execute one cancellation."""

    started = start(comp, text, task=task, run=runs[0])
    assert started.status == TaskStatus.WAITING_APPROVAL, started.error
    approve(comp, owner(comp, task, runs[0]), started)
    verification = comp.runtime.harness.resume(owner(comp, task, runs[1]), {"choice": "approve"})
    assert verification.interaction is not None and verification.interaction.kind == "verification"
    verified = verify_by_code(comp, owner(comp, task, runs[1]),
                              verification.interaction.record_ref)
    assert verified.verification_id is not None
    comp.runtime.bind_verification(owner(comp, task, runs[1]), verified.verification_id)
    return comp.runtime.harness.resume(owner(comp, task, runs[2]), {})


def begin_cancel(comp: Composition, text, *, task="T1", run="R1"):
    """Start a cancellation and stop on the confirmation card (nothing submitted)."""

    started = start(comp, text, task=task, run=run)
    assert started.status == TaskStatus.WAITING_APPROVAL, started.error
    assert started.interaction is not None and started.interaction.kind == "confirmation"
    return started


def confirm_and_verify(comp: Composition, text, *, task="T1", runs=("R1", "R2", "R3")):
    """Drive through the button and a fresh session code; stays before the bank call."""

    started = begin_cancel(comp, text, task=task, run=runs[0])
    record = approve(comp, owner(comp, task, runs[0]), started)
    verification = comp.runtime.harness.resume(owner(comp, task, runs[1]),
                                               {"choice": "approve"})
    assert verification.interaction is not None and verification.interaction.kind == "verification"
    verified = verify_by_code(comp, owner(comp, task, runs[1]),
                              verification.interaction.record_ref)
    assert verified.verification_id is not None
    comp.runtime.bind_verification(owner(comp, task, runs[1]), verified.verification_id)
    return started, record, verification, verified


# ------------------------------------------------------------------ failure injection


def arm_cancel_timeout(comp: Composition, *, sleep_seconds=0.4, gateway_timeout=0.05,
                       settle=True):
    """Make the single B30 write outlast the gateway budget.

    ``settle=True`` lets the bank really cancel afterwards (the platform just never saw
    it); ``settle=False`` models a debit the bank never processed.
    """

    original = comp.bank.cancel_subscription
    comp.runtime.gateway._transfer_timeout_seconds = gateway_timeout

    def slow(context, operation_id, mandate_id):
        time_sleep(sleep_seconds)
        if not settle:
            return QueryFailure(kind="error", error=BankError(code="CALL_TIMEOUT", details={}))
        return original(context, operation_id, mandate_id)

    comp.bank.cancel_subscription = slow
    return original


def time_sleep(seconds: float) -> None:
    import time
    time.sleep(seconds)


def fail_mandates_query(comp: Composition, code="BANK_UNAVAILABLE"):
    """Make B29 fail (the module must say "cannot read", never degrade to flows)."""

    comp.bank.list_subscriptions = lambda *args, **kwargs: QueryFailure(
        kind="error", error=BankError(code=code, details={}))


def fail_cancel_with(comp: Composition, code="BANK_UNAVAILABLE"):
    """Make the single B30 write answer with a business error (no timeout, no change)."""

    comp.bank.cancel_subscription = lambda *args, **kwargs: QueryFailure(
        kind="error", error=BankError(code=code, details={}))


def fake_failed_operation(comp: Composition, failure_code="BANK_UNAVAILABLE"):
    """B14 later reports the original operation as a bank-side failure."""

    from app.contracts.bank import OperationFound, OperationResult

    def lookup(context, operation_id):
        return OperationFound(lookup="found", operation=OperationResult(
            operation_id=operation_id, operation_type="bank.cancel_subscription",
            operation_status="failed", recorded_at=NOW, updated_at=NOW,
            receipt=None, failure=BankError(code=failure_code, details={})))

    comp.bank.get_operation = lookup


def freeze_account(bank: MockBankService, account_id="A1", status="frozen") -> None:
    with transaction(bank.store.path) as connection:
        connection.execute("UPDATE accounts SET account_status = ? WHERE account_id = ?",
                           (status, account_id))


def update_mandate(bank: MockBankService, mandate_id, **columns) -> None:
    assignments = ", ".join(f"{name} = ?" for name in columns)
    with transaction(bank.store.path) as connection:
        connection.execute(f"UPDATE bank_subscriptions SET {assignments} WHERE mandate_id = ?",
                           (*columns.values(), mandate_id))


def insert_mandate(bank: MockBankService, *, mandate_id, user_id="U1", account_id="A1",
                   account_masked="****0001", merchant_id="M_EVAL", merchant_name,
                   service_name="评测样本", amount_fen, cycle="monthly",
                   next_billing_at=None, last_billed_at=None, status="active",
                   signed_at="2026-01-01T09:00:00+00:00", cancelled_at=None,
                   cancel_operation_id=None) -> None:
    with transaction(bank.store.path) as connection:
        connection.execute(
            """INSERT INTO bank_subscriptions (
               mandate_id, user_id, account_id, account_masked, merchant_id, merchant_name,
               service_name, amount_fen, cycle, next_billing_at, last_billed_at, status,
               signed_at, cancelled_at, cancel_operation_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mandate_id, user_id, account_id, account_masked, merchant_id, merchant_name,
             service_name, amount_fen, cycle, next_billing_at, last_billed_at, status,
             signed_at, cancelled_at, cancel_operation_id))


def ledger_rows(account_id, user_id, rows, *, month_offsets=(1, 2, 3, 4)):
    """Irregular single purchases that never form a rule-4 periodic series."""

    facts = []
    for index, (offset, amount, merchant) in enumerate(
            zip(month_offsets, rows, [f"M_ODD_{position}" for position in range(len(rows))]), 1):
        # One day back from the bank clock: a row at the exact window edge is not read.
        at = NOW - timedelta(days=30 * offset + 1)
        facts.append({
            "transaction_id": f"FIX-{account_id}-{index}", "account_id": account_id,
            "user_id": user_id, "amount_fen": amount, "direction": "outflow",
            "nature": "consumption", "category": "other", "occurred_at": at.isoformat(),
            "counterparty_id": merchant, "counterparty_name": f"杂项{index}",
            "counterparty_account_masked": None, "channel": "快捷支付",
            "summary": "单笔消费", "original_transaction_id": None,
            "original_occurred_at": None,
        })
    return facts


def mandate(bank: MockBankService, mandate_id, *, user="U1"):
    response = bank.list_subscriptions(user)
    assert response.kind == "ok"
    return next(item for item in response.data.mandates if item.mandate_id == mandate_id)


def mandate_status(bank: MockBankService, mandate_id, *, user="U1") -> str:
    return mandate(bank, mandate_id, user=user).status


def bank_operations(bank: MockBankService) -> int:
    connection = connect(bank.store.path)
    try:
        return connection.execute("SELECT COUNT(*) FROM bank_operations").fetchone()[0]
    finally:
        connection.close()


def cancel_operations(bank: MockBankService) -> int:
    """Committed B30 rows: the one number that must never grow past one per task."""

    connection = connect(bank.store.path)
    try:
        return connection.execute(
            "SELECT COUNT(*) FROM bank_operations WHERE action_name = 'bank.cancel_subscription'",
        ).fetchone()[0]
    finally:
        connection.close()


def security_confirmations(comp: Composition, task_id) -> int:
    connection = connect(comp.application.path)
    try:
        return connection.execute(
            "SELECT COUNT(*) FROM security_confirmations WHERE task_id = ?", (task_id,),
        ).fetchone()[0]
    finally:
        connection.close()


def events(comp: Composition, task_id="T1"):
    return comp.runtime.audit._events(comp.round_id, task_id)


def texts(*values) -> list[str]:
    """Every user-visible string a case produced, for the wording red line."""

    collected: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            collected.append(value)
        elif isinstance(value, (list, tuple)):
            collected.extend(texts(*value))
        elif isinstance(value, dict):
            collected.extend(texts(*value.values()))
        else:
            message = getattr(value, "message", None)
            interaction = getattr(value, "interaction", None)
            collected.extend(texts(message, interaction))
            collected.extend(texts(getattr(value, "prompt", None)))
            collected.extend(texts([option.label for option in
                                    getattr(value, "options", []) or []]))
            collected.extend(texts([field.value_text for field in
                                    getattr(value, "display_fields", []) or []]))
    return [item for item in collected if item]


# --------------------------------------------------------------------- case recording


@dataclass
class CheckLog:
    """One golden case's structured result: the evidence is collected while asserting."""

    case_id: str
    scenario: str
    dimension: str
    nodeid: str = ""
    items: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def ok(self, name: str, condition, actual=None) -> bool:
        passed = bool(condition)
        self.items.append({"name": name, "passed": passed, "actual": actual})
        assert passed, f"{self.case_id} failed: {name} -> {actual!r}"
        return True

    def eq(self, name: str, actual, expected) -> bool:
        return self.ok(name, actual == expected, {"actual": actual, "expected": expected})

    def contains(self, name: str, text, needle: str) -> bool:
        return self.ok(name, needle in (text or ""), {"needle": needle, "text": text})

    def excludes(self, name: str, text, needle: str) -> bool:
        return self.ok(name, needle not in (text or ""), {"needle": needle, "text": text})

    def note(self, text: str) -> None:
        self.notes.append(text)

    def report(self, *, outcome: str | None = None, extras: dict | None = None) -> dict:
        failed = [item["name"] for item in self.items if not item["passed"]]
        status = outcome or ("Failed" if failed else "Passed")
        return {
            "case_id": self.case_id,
            "scenario": self.scenario,
            "dimension": self.dimension,
            "nodeid": self.nodeid,
            "status": status,
            "assertions_total": len(self.items),
            "assertions_passed": len([item for item in self.items if item["passed"]]),
            "failed_assertions": failed,
            "assertions": self.items,
            "notes": self.notes,
            **(extras or {}),
        }


def load_cases() -> dict:
    """Every case's machine-readable expectation, keyed by case id (never duplicated)."""

    payload = json.loads((Path(__file__).resolve().parent / "golden_cases.json")
                         .read_text(encoding="utf-8"))
    return {case["case_id"]: case for case in payload["cases"]}


def begin(store, request, case_id, cases) -> tuple[dict, CheckLog]:
    case = cases[case_id]
    log = CheckLog(case["case_id"], case["scenario"], case["dimension"],
                   nodeid=request.node.nodeid)
    store["reports"].append(log)
    return case, log


def step_label(result) -> str:
    """The state the case's expected sequence talks about: status[:interaction]."""

    if result.status in {TaskStatus.WAITING_APPROVAL, TaskStatus.WAITING_INPUT} \
            and result.interaction is not None:
        return f"{result.status.value}:{result.interaction.kind}"
    return result.status.value


def confirmation_texts(record) -> list[str]:
    return [f"{field.label}：{field.value_text}" for field in record.display_fields]


def assert_envelope(log, case, comp, result, *, task="T1", produced) -> None:
    """Every case's cross-cutting contract: route, state, bank truth and wording."""

    expected = case["expected"]
    record = comp.application.get_task(comp.user, comp.round_id, task)
    log.eq("route.capability", record.snapshot.get("capability_name"), expected["capability"])
    log.eq("final.status", result.status.value, expected["final_status"])
    kind = result.interaction.kind if result.interaction is not None else None
    log.eq("final.interaction", kind, expected["interaction"])
    log.eq("bank.operations", bank_operations(comp.bank), expected["bank_operations"])
    for mandate_id, status in expected["mandates"].items():
        log.eq(f"mandate.{mandate_id}.status",
               mandate_status(comp.bank, mandate_id, user=comp.user), status)
    confirmations = security_confirmations(comp, task)
    if expected.get("requires_confirmation") is None:
        log.note("cross-flow case: confirmation use is asserted in the case body")
    elif expected["requires_confirmation"]:
        log.ok("gate.confirmation_used", confirmations >= 1, confirmations)
    else:
        log.eq("gate.no_confirmation", confirmations, 0)
    joined = " | ".join(produced)
    for needle in expected["required_text"]:
        log.ok(f"text.required[{needle}]", needle in joined, {"needle": needle})
    for needle in expected["forbidden_text"]:
        log.ok(f"text.forbidden[{needle}]", needle not in joined, {"needle": needle})


def write_evidence(directory: Path, reports: list[CheckLog], outcomes: dict[str, str],
                   *, commands: list[list[str]], extra: dict | None = None) -> dict:
    """Archive the raw report, then index it in manifest.json + manifest.md (§六)."""

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    label = f"subscription-platform-{stamp}"
    entries = [report.report(outcome=outcomes.get(report.nodeid)) for report in reports]
    payload = {
        "module": "subscription",
        "layer": "platform-runtime",
        "label": label,
        "generated_at": stamp,
        "python": sys.version.split()[0],
        "app_file": _app_file(),
        "commands": commands,
        **({"extra": extra} if extra else {}),
        "summary": {
            "cases_run": len(entries),
            "counts": _counts(entries),
            "assertions_total": sum(item["assertions_total"] for item in entries),
            "assertions_passed": sum(item["assertions_passed"] for item in entries),
            "failed_cases": [item["case_id"] for item in entries if item["status"] != "Passed"],
        },
        "cases": entries,
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False).encode("utf-8")
    report_path = directory / f"{label}.json.gz"
    if report_path.exists():
        raise FileExistsError(f"evidence report already exists: {report_path}")
    with gzip.open(report_path, "wb") as handle:
        handle.write(encoded)

    entry = {
        "label": label,
        "layer": "platform-runtime",
        "generated_at": stamp,
        "revision": _git(["rev-parse", "HEAD"]),
        # Only source dirt matters: the evidence archive itself is written after this
        # snapshot, so listing its own files would make every clean run look dirty.
        "dirty_paths": [line for line in _git(["status", "--porcelain"]).splitlines()
                        if line and "evals/subscription/evidence/" not in line],
        "app_file": _app_file(),
        "python": payload["python"],
        "commands": commands,
        "cases_run": payload["summary"]["cases_run"],
        "counts": payload["summary"]["counts"],
        "assertions_total": payload["summary"]["assertions_total"],
        "assertions_passed": payload["summary"]["assertions_passed"],
        "failed_cases": payload["summary"]["failed_cases"],
        "evidence_file": report_path.name,
        "decompressed_sha256": sha256(encoded).hexdigest(),
        "extra": extra or {},
    }
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    manifest.append(entry)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# 场景 05 订阅代扣评测运行报告", ""]
    for item in manifest:
        lines.extend(_manifest_markdown(item, entries if item["label"] == label else None))
    # CI rejects a new blank line at EOF, so keep exactly one terminating newline even
    # when a generated section already ends with an empty line.
    while lines and not lines[-1].strip():
        lines.pop()
    (directory / "manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return entry


def _manifest_markdown(item: dict, entries: list[dict] | None) -> list[str]:
    lines = [
        f"## {item['label']}（{item['layer']}）", "",
        f"- 运行时间：`{item['generated_at']}`；提交：`{item['revision']}`；"
        f"脏文件：{len(item['dirty_paths'])} 个",
        f"- 解释器：`python {item['python']}`；被测包：`{item['app_file']}`",
        f"- 命令：{'; '.join(' '.join(command) for command in item['commands'])}",
        f"- 用例：{item['cases_run']}；状态分布：{json.dumps(item['counts'], ensure_ascii=False)}；"
        f"断言：{item['assertions_passed']}/{item['assertions_total']}",
        f"- 原始报告：`{item['evidence_file']}`（解压后 sha256 `{item['decompressed_sha256']}`）",
    ]
    if item.get("extra"):
        lines.append(f"- 附加观测：`{json.dumps(item['extra'], ensure_ascii=False)}`")
    if entries:
        lines.extend(["", "| 用例 | 场景 | 维度 | 状态 | 断言 | 失败断言 |",
                      "|---|---|---|---|---|---|"])
        for case in entries:
            lines.append(
                f"| {case['case_id']} | {case['scenario']} | {case['dimension']} | "
                f"{case['status']} | {case['assertions_passed']}/{case['assertions_total']} | "
                f"{', '.join(case['failed_assertions']) or '—'} |")
    lines.append("")
    return lines


def _counts(entries: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for item in entries:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return counts


def _app_file() -> str:
    import app
    return str(app.__file__)


def app_file() -> str:
    """Public alias: tools quote this so a sample always names the tree it measured."""

    return _app_file()


def _git(args: list[str]) -> str:
    repo = Path(__file__).resolve().parents[2]
    try:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                              check=False).stdout.strip()
    except OSError:
        return ""


def evidence_directory() -> Path | None:
    configured = os.environ.get("SUB_EVAL_EVIDENCE")
    return Path(configured) if configured else None
