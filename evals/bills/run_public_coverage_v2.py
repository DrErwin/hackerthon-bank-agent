"""Run ticket06 phase2 *public* business coverage against an exact Git source.

Usage:
  python evals/bills/run_public_coverage_v2.py --revision "$(git rev-parse HEAD)"

This is not the original 17-case L01 runner. It executes 40 additional
non-overlapping public scenarios: 14 L02 journeys, 14 L03 journeys, and four
sets of three bank-backed L02 rule contrasts. Only the registered Bills public
capability, real Harness/SQLite, real SecurityGate executor and real mock-bank
read boundary are assessed. Planning, demo admission and clock remain explicit
test doubles. Even all-green remains partial until full BF/HTTP/React/safety
evidence is accepted by the responsible owners.

The source tree is verified before and after execution, with CRLF normalized
for Git blob comparison. The report is append-only and sanitized on failures.
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
import sys
import time
from uuid import uuid4

import pytest
from run_business_evidence import verify_sources, runtime_imports
from run_evidence import REPOSITORY, utc_now

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "evals/bills"
TEST_PATH = "evals/bills/test_public_coverage_v2.py"
MANIFEST_PATH = "evals/bills/public-coverage-v2-cases.json"
REQUIRED_DISTRIBUTIONS = ("pytest", "pydantic", "fastapi", "langgraph", "deepagents")


class CoverageEvidence:
    def __init__(self, cases):
        self.cases = {item["id"]: item for item in cases}
        self.samples = {}
        self.errors = []
        self.collected = 0

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append(report.nodeid)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        case_id = item.callspec.id if hasattr(item, "callspec") else None
        self.samples[item.nodeid] = {
            "nodeid": item.nodeid, "case_id": case_id,
            "case": self.cases.get(case_id), "start_at": utc_now(), "phases": [],
        }
        started = time.monotonic()
        yield
        self.samples[item.nodeid].update(
            end_at=utc_now(), seconds=time.monotonic() - started)

    def pytest_runtest_logreport(self, report):
        record = self.samples[report.nodeid]
        record["phases"].append({
            "when": report.when, "outcome": report.outcome,
            "duration_seconds": report.duration,
        })
        for name, value in report.user_properties:
            if name in {"coverage_observations", "bank_integrity"}:
                record[name] = value
        if report.failed:
            # Tracebacks may contain full transactions, names or challenges.
            # Only save the crash *location*, not reprtraceback.
            site = getattr(report.longrepr, "reprcrash", None)
            record["failure"] = {
                "phase": report.when, "line": getattr(site, "lineno", None),
                "path": str(getattr(site, "path", "")),
            }

    def finalize(self):
        samples = list(self.samples.values())
        for sample in samples:
            phases = {p["when"]: p["outcome"] for p in sample["phases"]}
            result = "passed"
            if phases != {"setup": "passed", "call": "passed", "teardown": "passed"}:
                result = "skipped" if "skipped" in phases.values() else (
                    "failed" if phases.get("call") == "failed" else "error")
            evidence = sample.get("bank_integrity") or {}
            if result == "passed" and (
                not sample.get("case")
                or not sample.get("coverage_observations")
                or not evidence.get("bank_tables_unchanged")
                or not evidence.get("balances_unchanged")
                or evidence.get("funds_submit_calls") != 0
            ):
                result = "error"
                sample["evidence_error"] = "missing bank integrity or public path observations"
            sample["result"] = result
        summary = {key: sum(s["result"] == key for s in samples)
                   for key in ("passed", "failed", "skipped", "error")}
        summary["collection_errors"] = len(self.errors)
        return summary, samples


def read_manifest():
    data = json.loads((ROOT / MANIFEST_PATH).read_text(encoding="utf-8"))
    cases = data["cases"]
    ids = [x["id"] for x in cases]
    counts = Counter(x["tier"] for x in cases)
    if len(ids) != len(set(ids)) or len(ids) != 40:
        raise ValueError("40 unique new runtime cases required")
    if counts != {"l02_public": 14, "l03_public": 14, "l02_rule_public": 12}:
        raise ValueError(f"unexpected public case tiers: {counts}")
    for rule in range(1, 5):
        variants = ("HIT", "MISS", "NONELIGIBLE") if rule == 3 else ("HIT", "MISS", "INSUFFICIENT")
        required = {f"BILL-RULE-{rule}-{kind}" for kind in variants}
        if required - set(ids):
            raise ValueError(f"rule {rule} missing contrasts")
    if data["overall_status"] != "partial" or data["full_ticket_acceptance"]:
        raise ValueError("local public evaluation cannot self-certify full ticket acceptance")
    for case in cases:
        if not case.get("bf") or not case.get("expectation") or not case.get("kind"):
            raise ValueError(f"missing BF mapping / expectation in {case['id']}")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    options = parser.parse_args()
    manifest = read_manifest()
    tree, source_files = verify_sources(options.revision)
    needed = {TEST_PATH, MANIFEST_PATH, "evals/bills/run_public_coverage_v2.py"}
    if needed - set(source_files):
        raise ValueError("new coverage sources are not pinned in the published commit")

    plugin = CoverageEvidence(manifest["cases"])
    started = utc_now()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "backend"))
    command = ["-q", "--rootdir", ".", TEST_PATH]
    exit_code = int(pytest.main(command, plugins=[plugin]))
    summary, samples = plugin.finalize()
    if (plugin.collected != 40 or len(samples) != 40
            or {x["case_id"] for x in samples} != {x["id"] for x in manifest["cases"]}
            or any(summary[k] for k in ("failed", "skipped", "error", "collection_errors"))):
        exit_code = exit_code or 1
    if verify_sources(options.revision) != (tree, source_files):
        raise ValueError("Git source changed during run; refuse to archive as same revision")
    imports, errs = {}, []
    try:
        imports = runtime_imports(source_files)
    except ValueError as exc:
        errs.append(str(exc))
        exit_code = exit_code or 1

    report = {
        "schema_version": 1, "ticket_id": manifest["ticket_id"],
        "repository": REPOSITORY, "tested_revision": options.revision,
        "source_commit_url": f"https://github.com/{REPOSITORY}/commit/{options.revision}",
        "tested_tree": tree, "source_files": source_files, "runtime_imports": imports,
        "source_verification": "git_object_verified_complete_business_sources",
        "import_evidence_errors": errs, "run_id": str(uuid4()),
        "start_at": started, "end_at": utc_now(),
        "python_version": platform.python_version(),
        "pytest_version": pytest.__version__,
        "dependencies": {name: version(name) for name in REQUIRED_DISTRIBUTIONS},
        "environment": platform.system(), "command": command,
        "collected": plugin.collected, "summary": summary, "test_exit_code": exit_code,
        "expected_independent_cases": 40, "phase_result": "Passed" if not exit_code else "Failed",
        "overall_status": "partial", "full_ticket_acceptance": False,
        "real_components": manifest["real_components"],
        "test_doubles": manifest["test_doubles"],
        "exclusions": manifest["exclusions"],
        "tier_counts": dict(Counter(s["case"]["tier"] for s in samples if s["case"])),
        "samples": samples, "collection_errors": plugin.errors,
    }
    raw = (json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n").encode()
    dest_dir = DIRECTORY / "evidence" / datetime.now(
        timezone(timedelta(hours=8))).date().isoformat()
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = dest_dir / (
        f"{name}-python{platform.python_version()}-public-coverage-v2-"
        f"{options.revision[:12]}.json.gz")
    with path.open("xb") as stream:
        stream.write(gzip.compress(raw, mtime=0))
    print(json.dumps({
        "evidence": str(path), "tested_revision": options.revision,
        "sha256_uncompressed": hashlib.sha256(raw).hexdigest(),
        "summary": summary, "overall_status": "partial",
        "full_ticket_acceptance": False,
    }, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
