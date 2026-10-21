"""Archive ticket 07 HTTP evidence against an exact, published source commit.

python evals/bills/run_http_evidence.py --revision <40-character-source-SHA>
The full backend, real initializers, seeds and this evaluation must match that
commit before and after execution. Evidence files are append-only and excluded
from the source check. No source-slice, module-stub or live-model fallback.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "evals/bills"
REPOSITORY = "DrErwin/hackerthon-bank-agent"
COMPOSITION_REVISION = "0d829d5a458d553ad0d975709b88f1f4b8a0529f"
BACKEND_TREE = "aa85d882c8c355242950f42c721d7cc512998068"
TEST_PATH = "evals/bills/test_report_http_eval.py"
MANIFEST_PATH = "evals/bills/report-http-cases.json"
EXTRA_TEST_PATH = "evals/bills/test_http_extra_eval.py"
EXTRA_MANIFEST_PATH = "evals/bills/http-extra-cases.json"
REQUIRED_FILES = {
    "backend/app/__init__.py", "backend/app/contracts/__init__.py",
    "backend/app/api/__init__.py", "backend/app/api/app.py", "backend/app/api/service.py",
    "backend/app/api/store.py", "backend/app/contracts/bills.py",
    "backend/app/contracts/security.py", "backend/app/contracts/api.py",
    "backend/app/agent_platform/harness.py", "backend/app/agent_platform/local_demo.py",
    "backend/app/agent_platform/transfer_runtime.py", "backend/app/agent_platform/registry.py",
    "backend/app/modules/bills/entry.py", "backend/app/modules/bills/manifest.py",
    "backend/app/modules/bills/report_service.py", "backend/app/modules/bills/_report.py",
    "backend/app/modules/bills/service.py", "backend/app/modules/bills/reads.py",
    "backend/app/security/gate.py", "backend/app/security/__init__.py",
    "backend/app/audit/journal.py", "backend/app/memory/adapter.py",
    "backend/app/storage/application.py", "backend/app/storage/mock_bank/repository.py",
    "backend/app/services/bank_gateway/gateway.py", "backend/app/services/mock_bank/core.py",
    "backend/app/services/mock_bank/verification.py", "backend/app/services/mock_bank/flow_seeds.py",
    "backend/app/services/mock_bank/seeds/accounts.json",
    "backend/app/services/mock_bank/seeds/flow_history.json",
    "backend/app/services/mock_bank/seeds/subscription_flows.json", "backend/pyproject.toml",
    "evals/bills/conftest.py", "evals/bills/run_http_evidence.py", TEST_PATH, MANIFEST_PATH,
    "evals/bills/report-http-cases.md", EXTRA_TEST_PATH, EXTRA_MANIFEST_PATH,
    ".scratch/v04-ethan-bills-backend/issues/07-integration-evidence.md",
    "docs/contracts/公共契约-2026-09-23.md",
}
REQUIRED_IMPORTS = {
    "app", "app.contracts", "app.api", "app.api.app", "app.api.service", "app.api.store",
    "app.modules.bills.entry", "app.modules.bills.report_service", "app.modules.bills.reads",
    "app.agent_platform.harness", "app.agent_platform.local_demo", "app.agent_platform.transfer_runtime",
    "app.security.gate", "app.security", "app.memory.adapter",
    "app.services.bank_gateway.gateway", "app.services.mock_bank.core",
    "app.services.mock_bank.verification", "app.storage.application", "app.audit.journal",
    "app.modules.bills.anomaly_entry", "app.modules.bills.anomaly_service",
    "app.modules.bills.anomaly_manifest",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def is_source(path):
    return (path in REQUIRED_FILES or Path(path).suffix in {".py", ".json", ".sql", ".toml"}
            and (path.startswith("backend/")
                 or path.startswith("evals/bills/") and "/evidence/" not in path))


def verify_sources(revision):
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("an exact published 40-character source commit is required")
    if git("rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip() != revision:
        raise ValueError("source revision did not resolve to itself")
    if git("rev-parse", f"{revision}:backend").decode().strip() != BACKEND_TREE:
        raise ValueError("this evidence stage requires the declared composed backend tree")
    expected = {}
    for item in git("ls-tree", "-rz", "--full-tree", revision).split(b"\0"):
        if not item:
            continue
        fields, raw_path = item.split(b"\t", 1)
        path = raw_path.decode("utf-8")
        if is_source(path):
            mode, kind, blob = fields.decode().split()
            if kind != "blob" or mode not in {"100644", "100755"}:
                raise ValueError(f"source is not a regular Git file: {path}")
            expected[path] = blob
    missing = REQUIRED_FILES - set(expected)
    if missing:
        raise ValueError(f"full source and evidence definitions are required: {sorted(missing)}")
    extra = [path for path in git("ls-files", "--others", "--exclude-standard").decode().splitlines()
             if is_source(path)]
    if extra:
        raise ValueError(f"uncommitted source could change execution: {extra}")
    sources = {}
    for path, blob in sorted(expected.items()):
        file = ROOT / path
        if file.is_symlink():
            raise ValueError(f"symlink source is not permitted: {path}")
        raw = file.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if actual != blob:
            raise ValueError(f"working source differs from the tested commit: {path}")
        sources[path] = {"git_blob_sha": blob, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return git("rev-parse", f"{revision}^{{tree}}").decode().strip(), sources


def runtime_imports(sources):
    missing = REQUIRED_IMPORTS - set(sys.modules)
    if missing:
        raise ValueError(f"expected real components were not imported: {sorted(missing)}")
    result = {}
    for name, module in tuple(sys.modules.items()):
        if name != "app" and not name.startswith("app."):
            continue
        filename = getattr(module, "__file__", None)
        if filename is None:
            continue  # legitimate namespace packages have no initializer file
        path = Path(filename).resolve().relative_to(ROOT).as_posix()
        if path not in sources:
            raise ValueError(f"runtime module outside verified source: {name} -> {path}")
        result[name] = path
    return result


class HttpEvidence:
    def __init__(self, cases):
        self.cases = {case["id"]: case for case in cases}
        self.samples, self.collection_errors, self.collected = {}, [], 0

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(report.nodeid)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        case_id = item.callspec.id if hasattr(item, "callspec") else None
        tier = ("in_process_http_real_l03" if case_id and case_id.startswith("BILL-HTTP-0")
                else "in_process_http_real_bills_phase2")
        record = {"nodeid": item.nodeid, "sample_id": case_id, "tier": tier,
                  "requirement_mapping": self.cases.get(case_id), "started_at": utc_now(), "phases": []}
        self.samples[item.nodeid] = record
        started = time.perf_counter()
        yield
        record.update(finished_at=utc_now(), duration_seconds=time.perf_counter() - started)

    def pytest_runtest_logreport(self, report):
        record = self.samples[report.nodeid]
        record["phases"].append({"phase": report.when, "outcome": report.outcome,
                                  "duration_seconds": report.duration})
        for key, value in report.user_properties:
            if key in {"http_observations", "bank_integrity", "bank_calls"}:
                record[key] = value
        if report.failed:
            # Assertion payloads can contain a CSV or a dedicated demo code.
            # Store the exact failing source location, never that raw traceback.
            crash = getattr(report.longrepr, "reprcrash", None)
            record["failure"] = {"phase": report.when, "path": getattr(crash, "path", None),
                                  "line": getattr(crash, "lineno", None)}

    def results(self):
        samples = list(self.samples.values())
        for record in samples:
            phases = {phase["phase"]: phase["outcome"] for phase in record["phases"]}
            if any(value == "failed" for key, value in phases.items() if key != "call"):
                result = "error"
            elif phases.get("call") == "failed":
                result = "failed"
            elif "skipped" in phases.values():
                result = "skipped"
            elif phases == {"setup": "passed", "call": "passed", "teardown": "passed"}:
                result = "passed"
            else:
                result = "error"
            integrity = record.get("bank_integrity", {})
            if result == "passed" and (not record.get("requirement_mapping")
                    or not record.get("http_observations")
                    or (not record.get("bank_calls") and not (
                        (record.get("requirement_mapping") or {}).get("kind") == "l02_cancel"
                        and any(item.get("action") == "zero_bank_read_asserted"
                                for item in record.get("http_observations", []))))
                    or not integrity.get("accounts_ledger_unchanged") or integrity.get("funds_submit_calls") != 0):
                result = "error"
                record["evidence_error"] = "missing HTTP/real-bank observations or unchanged-funds proof"
            record["result"] = result
            record["http_request_count"] = sum("method" in item for item in record.get("http_observations", []))
        counts = {key: sum(record["result"] == key for record in samples)
                  for key in ("passed", "failed", "skipped", "error")}
        counts["collection_errors"] = len(self.collection_errors)
        return counts, samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    tree, sources = verify_sources(args.revision)
    manifest = json.loads((ROOT / MANIFEST_PATH).read_text(encoding="utf-8"))
    extra = json.loads((ROOT / EXTRA_MANIFEST_PATH).read_text(encoding="utf-8"))
    first_ids = {f"BILL-HTTP-{number:02}" for number in range(1, 8)}
    extra_ids = {f"BILL-HTTP-X{number:02}" for number in range(1, 9)}
    if len(manifest["cases"]) != 7 or {c["id"] for c in manifest["cases"]} != first_ids:
        raise ValueError("original seven distinct HTTP cases must be preserved")
    if len(extra["cases"]) != 8 or {c["id"] for c in extra["cases"]} != extra_ids:
        raise ValueError("eight new L01/L02/F10/CSV HTTP cases must be present")
    expected = first_ids | extra_ids
    cases = manifest["cases"] + extra["cases"]
    if manifest["overall_status"] != "partial" or not manifest["remaining_dependencies"]:
        raise ValueError("HTTP-only evidence cannot claim full ticket acceptance")
    plugin = HttpEvidence(cases)
    started = utc_now()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "backend"))
    command = ["-q", "--rootdir", str(ROOT), TEST_PATH, EXTRA_TEST_PATH]
    exit_code = int(pytest.main(command, plugins=[plugin]))
    summary, samples = plugin.results()
    observed = [sample["sample_id"] for sample in samples]
    if (plugin.collected != len(expected) or len(observed) != len(expected)
            or set(observed) != expected or any(summary[key] for key in ("failed", "skipped", "error", "collection_errors"))):
        exit_code = exit_code or 1
    if verify_sources(args.revision) != (tree, sources):
        raise ValueError("source changed during evaluation; do not archive a moving target")
    imports, evidence_errors = {}, []
    try:
        imports = runtime_imports(sources)
    except ValueError as error:
        evidence_errors.append(str(error))
        exit_code = exit_code or 1
    report = {"schema_version": 1, "repository": REPOSITORY,
        "ticket_id": manifest["ticket_id"], "stage": manifest["stage"],
        "overall_status": "partial", "full_ticket_acceptance": False,
        "phase_result": "Passed" if exit_code == 0 else "Failed",
        "run_id": str(uuid4()), "tested_revision": args.revision, "tested_tree": tree,
        "source_commit_url": f"https://github.com/{REPOSITORY}/commit/{args.revision}",
        "composition_revision": COMPOSITION_REVISION, "backend_tree": BACKEND_TREE,
        "composition_is_production_admission": False,
        "source_verification": "git_object_verified_full_backend_and_eval_sources",
        "source_policy": "all backend and bills-eval Python/JSON/SQL/TOML plus named contracts/case definitions; byte-exact Git files before/after; evidence excluded",
        "source_files": sources, "runtime_imports": imports,
        "runtime_sources_verified": not evidence_errors, "evidence_errors": evidence_errors,
        "started_at": started, "finished_at": utc_now(), "python_version": platform.python_version(),
        "dependencies": {name: version(name) for name in ("pytest", "pydantic", "fastapi", "starlette", "httpx", "langgraph", "deepagents")},
        "system": platform.system(), "pytest_args": command, "exit_code": exit_code,
        "business_clock": "2026-10-14T13:00:00+08:00", "test_data": "fresh synthetic SQLite bank per scenario",
        "real_components": manifest["real_components"] + [
            "Real L01/L02 registered public capabilities, API F10/cancel, bank-backed CSV formula path"],
        "test_doubles": manifest["test_doubles"],
        "additional_case_manifest": EXTRA_MANIFEST_PATH, "extra_scenarios": len(extra["cases"]),
        "collected": plugin.collected, "summary": summary,
        "tier_counts": dict(Counter(sample["tier"] for sample in samples)),
        "http_request_count": sum(sample["http_request_count"] for sample in samples),
        "collection_errors": plugin.collection_errors, "samples": samples,
        "remaining_dependencies": manifest["remaining_dependencies"],
        "extra_remaining": extra["remaining"],
        "coverage_limitations": manifest["coverage_limitations"],
        "counting_rule": "one sample per declared scenario; expected refusals can pass; HTTP request count is not case count; no live-model/page/security signoff or full BF acceptance"}
    raw = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    out = DIRECTORY / "evidence" / datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = out / f"{stamp}-python{platform.python_version()}-http-l03-exports-{args.revision[:12]}.json.gz"
    with dest.open("xb") as stream:
        stream.write(gzip.compress(raw, mtime=0))
    print(json.dumps({"report": str(dest), "uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
        "summary": summary, "http_request_count": report["http_request_count"],
        "overall_status": "partial", "tested_revision": args.revision}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
