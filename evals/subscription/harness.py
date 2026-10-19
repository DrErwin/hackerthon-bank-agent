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
from uuid import UUID, uuid4

from app.agent_platform.model import TransferProposal
from app.agent_platform.subscription_runtime import (
    CANCEL_TOOL, register_subscription, subscription_risk_evidence,
)
from app.agent_platform.transfer_runtime import TransferRuntime
from app.audit.journal import AuditJournal
from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.security import ConfirmationAnswer
from app.memory.adapter import MemoryAdapter
from app.security.demo_policy import DemoRiskEvidence, DemoRiskSignal, DemoSecurityPolicy
from app.security.gate import RiskFactsUnavailable
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore
from app.storage.database import connect
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
FORBIDDEN_PROMISES = ("会员可用至", "还能用到", "先退订再重新订阅", "先解约再重签")
# The one promise the confirmation card and the receipt are allowed to make.
CANCEL_PROMISE = "从下一期（{date}）起不再自动扣费，之前已经扣掉的钱不退"


def billing_date(offset_days: int) -> str:
    """The bank's own next-debit date for a seeded offset (billing hour 09:00)."""

    at = (NOW + timedelta(days=offset_days)).replace(hour=9, minute=0, second=0, microsecond=0)
    return at.date().isoformat()


def trusted(task="T1", run="R1", session="S1"):
    return TrustedContext(user_id="U1", session_id=session, task_id=task, run_id=run,
                          parent_task_id=None, demo_round_id="D1")


def open_session(application, session_id="S1"):
    at = datetime.now(timezone.utc)
    application.create_session(session_id, "U1", "D1", at.isoformat(),
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

    def close(self) -> None:
        self.runtime.close()


def composition(tmp_path, *, seed_flows=True, clock=NOW) -> Composition:
    """Real services end to end; ``seed_flows=False`` keeps the ledger empty (SF07)."""

    path = Path(tmp_path) / "application.sqlite"
    application = ApplicationStore(path)
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    bank = MockBankService(MockBankStore(Path(tmp_path) / "bank.sqlite"),
                           demo_secret=DEMO_SECRET, clock=lambda: clock)
    if seed_flows:
        bank.seed_flow_history()
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
        demo_user_id="U1", admin_actor_id="demo-admin", current_demo_round=lambda: "D1",
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
    open_session(application)
    return Composition(application, bank, planner, runtime, policy)


# --------------------------------------------------------------------------- driving


def start(comp: Composition, text, *, task="T1", run="R1", capability=CANCEL_CAPABILITY):
    comp.planner.capability = capability
    return comp.runtime.harness.start(trusted(task, run), uuid4(), text)


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


def confirmation_for(comp: Composition, owner, pending=None):
    operation_id, revision = pending_binding(comp, owner.task_id)
    context = comp.runtime._context(owner, operation_id, revision)
    assert context.confirmation_id is not None
    record = comp.runtime.confirmations.get(context, context.confirmation_id)
    if pending is not None:
        assert pending.interaction.record_ref == record.confirmation_id
    return record


def approve(comp: Composition, owner, pending):
    record = confirmation_for(comp, owner, pending)
    assert record.decision == "pending"
    comp.runtime.answer_confirmation(owner, ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version, choice="approve",
    ))
    return record


def verify_by_code(comp: Composition, owner, challenge_id):
    code = comp.runtime.gateway.get_demo_code_for_api(owner, challenge_id)
    return comp.runtime.gateway.verify_code(owner, challenge_id, uuid4(), code)


def cancel_to_success(comp: Composition, text, *, task="T1", runs=("R1", "R2", "R3")):
    """Confirm, verify with a fresh code, bind, and execute one cancellation."""

    started = start(comp, text, task=task, run=runs[0])
    assert started.status == TaskStatus.WAITING_APPROVAL, started.error
    approve(comp, trusted(task, runs[0]), started)
    verification = comp.runtime.harness.resume(trusted(task, runs[1]), {"choice": "approve"})
    assert verification.interaction is not None and verification.interaction.kind == "verification"
    verified = verify_by_code(comp, trusted(task, runs[1]), verification.interaction.record_ref)
    assert verified.verification_id is not None
    comp.runtime.bind_verification(trusted(task, runs[1]), verified.verification_id)
    return comp.runtime.harness.resume(trusted(task, runs[2]), {})


# ------------------------------------------------------------------------ bank facts


def mandate(bank: MockBankService, mandate_id):
    response = bank.list_subscriptions("U1")
    assert response.kind == "ok"
    return next(item for item in response.data.mandates if item.mandate_id == mandate_id)


def mandate_status(bank: MockBankService, mandate_id) -> str:
    return mandate(bank, mandate_id).status


def bank_operations(bank: MockBankService) -> int:
    connection = connect(bank.store.path)
    try:
        return connection.execute("SELECT COUNT(*) FROM bank_operations").fetchone()[0]
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
    return comp.runtime.audit._events("D1", task_id)


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
        "dirty_paths": [line for line in _git(["status", "--porcelain"]).splitlines() if line],
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
