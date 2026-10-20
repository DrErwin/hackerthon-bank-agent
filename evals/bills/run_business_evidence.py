"""Append-only ticket 06 phase-1 public L01 evidence from an exact source commit.

python evals/bills/run_business_evidence.py --revision <published 40-character SHA>
Requires the complete source checkout, including real package initializers,
bank seeds, contracts, Harness, security and the declared test-wiring helper.
There is no file-slice or dependency-stub fallback for this business tier.
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
from uuid import uuid4

import pytest

from run_evidence import EvidencePlugin, REPOSITORY, case_definitions, utc_now

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "evals/bills"
TEST_PATH = "evals/bills/test_public_business_eval.py"
MANIFEST_PATH = "evals/bills/public-business-cases.json"
SUFFIXES = {".py", ".json", ".sql", ".toml"}
REQUIRED_SOURCES = {
    "backend/app/__init__.py", "backend/app/contracts/__init__.py",
    "backend/app/contracts/bank.py", "backend/app/contracts/bills.py",
    "backend/app/modules/bills/entry.py", "backend/app/modules/bills/service.py",
    "backend/app/modules/bills/reads.py", "backend/app/modules/bills/manifest.py",
    "backend/app/modules/bills/_statistics.py",
    "backend/app/modules/bills/test_public_integration.py",
    "backend/app/agent_platform/harness.py", "backend/app/agent_platform/registry.py",
    "backend/app/security/gate.py", "backend/app/audit/journal.py",
    "backend/app/storage/application.py", "backend/app/storage/mock_bank/repository.py",
    "backend/app/services/bank_gateway/gateway.py",
    "backend/app/services/mock_bank/core.py", "backend/app/services/mock_bank/flow_seeds.py",
    "backend/app/services/mock_bank/seeds/accounts.json",
    "backend/app/services/mock_bank/seeds/flow_history.json",
    "backend/app/services/mock_bank/seeds/subscription_flows.json",
    "backend/pyproject.toml", TEST_PATH, MANIFEST_PATH,
    "evals/bills/conftest.py", "evals/bills/run_business_evidence.py",
    "evals/bills/run_evidence.py",
}
REQUIRED_IMPORTS = {
    "app", "app.contracts", "app.contracts.bank", "app.contracts.bills",
    "app.modules.bills.entry", "app.modules.bills.service", "app.modules.bills.reads",
    "app.modules.bills.test_public_integration", "app.agent_platform.harness",
    "app.security.gate", "app.services.bank_gateway.gateway",
    "app.services.mock_bank.core", "app.storage.application",
    "app.storage.mock_bank.repository", "app.audit.journal",
}


def git(*args, root=ROOT):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout


def is_source(path):
    return (Path(path).suffix in SUFFIXES
            and (path.startswith("backend/")
                 or path.startswith("evals/bills/") and "/evidence/" not in path))


def verify_sources(revision, *, root=ROOT):
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("use an exact published 40-character source commit")
    if git("rev-parse", "--verify", f"{revision}^{{commit}}", root=root).decode().strip() != revision:
        raise ValueError("the tested revision must resolve to itself")
    expected = {}
    for item in git("ls-tree", "-rz", "--full-tree", revision, root=root).split(b"\0"):
        if not item:
            continue
        fields, raw_path = item.split(b"\t", 1)
        path = raw_path.decode("utf-8")
        if is_source(path):
            mode, kind, blob = fields.decode().split()
            if kind != "blob" or mode not in {"100644", "100755"}:
                raise ValueError(f"business sources must be regular Git files: {path}")
            expected[path] = blob
    missing = REQUIRED_SOURCES - set(expected)
    if missing:
        raise ValueError(f"complete business sources are required: {sorted(missing)}")
    untracked = [path for path in git("ls-files", "--others", "--exclude-standard", root=root).decode().splitlines()
                 if is_source(path)]
    if untracked:
        raise ValueError(f"uncommitted source files could alter imports: {untracked}")
    sources = {}
    for path, blob in sorted(expected.items()):
        file = root / path
        if file.is_symlink():
            raise ValueError(f"source cannot be replaced with a symlink: {path}")
        raw = file.read_bytes()
        actual_blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if actual_blob != blob:
            raise ValueError(f"working source differs from tested Git blob: {path}")
        sources[path] = {"git_blob_sha": blob, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return git("rev-parse", f"{revision}^{{tree}}", root=root).decode().strip(), sources


def validate_manifest():
    manifest = json.loads((ROOT / MANIFEST_PATH).read_text(encoding="utf-8"))
    cases = manifest["cases"]
    expected_ids = {f"BILL-PUBLIC-{number:02}" for number in range(1, 18)}
    if len(cases) != 17 or {case["id"] for case in cases} != expected_ids:
        raise ValueError("phase 1 requires all 17 independent runtime scenarios exactly once")
    definitions = {}
    for name in ("representative-cases.md", "expanded-cases.md"):
        definitions.update(case_definitions((DIRECTORY / name).read_text(encoding="utf-8")))
    for case in cases:
        if not case["bf"] or not case["spec"] or not case["assertions"]:
            raise ValueError(f"missing requirement/behavior mapping: {case['id']}")
        if set(case["design_links"]) - set(definitions):
            raise ValueError(f"unknown historical design link: {case['id']}")
    paths = [item["path"] for item in manifest["blocked_paths"]]
    if len(paths) != len(set(paths)) or not paths:
        raise ValueError("blocked dependencies require separate unique paths")
    if any(item["status"] != "Blocked" or not item["owner"] or not item["reason"]
           for item in manifest["blocked_paths"]):
        raise ValueError("a blocked dependency cannot be counted as passed or skipped")
    if manifest["overall_status"] != "partial" or not manifest["remaining_coverage"]:
        raise ValueError("first-phase samples cannot claim full ticket acceptance")
    return manifest


class BusinessEvidencePlugin(EvidencePlugin):
    def __init__(self, cases):
        super().__init__({case["id"]: case["design_links"] for case in cases})
        self.cases = {case["id"]: case for case in cases}

    def pytest_runtest_logreport(self, report):
        super().pytest_runtest_logreport(report)
        record = self.samples[report.nodeid]
        for key, value in report.user_properties:
            if key in {"business_observations", "bank_integrity"}:
                record[key] = value

    def results(self):
        _, records = super().results()
        for record in records:
            case_id = record["fixture_id"]
            if case_id not in self.cases:
                record["result"] = "error"
                record["evidence_error"] = "collected sample is not in the phase-1 manifest"
                continue
            record.update(sample_id=case_id, tier="public_l01_business",
                          requirement_mapping=self.cases[case_id])
            if record["result"] == "passed":
                integrity = record.get("bank_integrity", {})
                if (not record.get("business_observations") or not integrity.get("bank_tables_unchanged")
                        or not integrity.get("balances_unchanged") or integrity.get("funds_submit_calls") != 0):
                    record["result"] = "error"
                    record["evidence_error"] = "passed test lacks real public observations or bank integrity proof"
        counts = {key: sum(record["result"] == key for record in records)
                  for key in ("passed", "failed", "skipped", "error")}
        counts["collection_errors"] = len(self.collection_errors)
        return counts, records


def runtime_imports(sources):
    missing = REQUIRED_IMPORTS - set(sys.modules)
    if missing:
        raise ValueError(f"real business components were not imported: {sorted(missing)}")
    loaded = {}
    for name, module in tuple(sys.modules.items()):
        if name != "app" and not name.startswith("app."):
            continue
        filename = getattr(module, "__file__", None)
        if filename is None:  # legitimate namespace packages are not source substitutes
            continue
        path = Path(filename).resolve().relative_to(ROOT).as_posix()
        if path not in sources:
            raise ValueError(f"runtime app module is outside verified Git sources: {name} -> {path}")
        loaded[name] = path
    return loaded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    tree, sources = verify_sources(args.revision)
    manifest = validate_manifest()
    plugin = BusinessEvidencePlugin(manifest["cases"])
    started = utc_now()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "backend"))
    command = ["-q", "--rootdir", str(ROOT), TEST_PATH]
    exit_code = int(pytest.main(command, plugins=[plugin]))
    summary, samples = plugin.results()
    expected = {case["id"] for case in manifest["cases"]}
    observed = [sample.get("sample_id") for sample in samples]
    complete = (len(observed) == len(expected) and set(observed) == expected
                and plugin.collected == len(expected))
    if not complete or any(summary[key] for key in ("failed", "skipped", "error", "collection_errors")):
        exit_code = exit_code or 1
    # Verification is repeated after execution, including all imported backend
    # sources and package initialization. A moving source tree cannot be archived.
    if verify_sources(args.revision) != (tree, sources):
        raise ValueError("sources changed while tests were executing")
    evidence_errors = []
    try:
        imports = runtime_imports(sources)
    except ValueError as error:
        imports = {}
        evidence_errors.append(str(error))
        exit_code = exit_code or 1
    report = {
        "schema_version": 1, "repository": REPOSITORY,
        "ticket_id": manifest["ticket_id"], "stage": manifest["stage"],
        "overall_status": "partial", "full_ticket_acceptance": False,
        "phase_result": "Passed" if exit_code == 0 else "Failed",
        "run_id": str(uuid4()), "tested_revision": args.revision, "tested_tree": tree,
        "source_commit_url": f"https://github.com/{REPOSITORY}/commit/{args.revision}",
        "source_verification": "git_object_verified_complete_business_sources",
        "source_policy": "all tracked backend and evals/bills Python/JSON/SQL/TOML; byte-exact Git blobs; evidence files excluded",
        "source_files": sources, "runtime_imports": imports,
        "runtime_sources_verified": not evidence_errors, "evidence_errors": evidence_errors,
        "package_initializers_verified": {path: sources[path] for path in (
            "backend/app/__init__.py", "backend/app/contracts/__init__.py")},
        "started_at": started, "finished_at": utc_now(),
        "python_version": platform.python_version(), "pytest_version": pytest.__version__,
        "dependencies": {name: version(name) for name in ("pydantic", "langgraph", "fastapi", "deepagents")},
        "system": platform.system(), "pytest_args": command,
        "business_clock": "2026-10-14T13:00:00+08:00", "test_data": "fresh synthetic seeded SQLite bank per scenario",
        "real_components": manifest["real_components"], "test_doubles": manifest["test_doubles"],
        "collected": plugin.collected, "expected_runtime_scenarios": len(expected),
        "exit_code": exit_code, "summary": summary,
        "tier_counts": dict(Counter(sample.get("tier") for sample in samples)),
        "collection_errors": plugin.collection_errors, "samples": samples,
        "blocked_paths": manifest["blocked_paths"], "blocked_path_count": len(manifest["blocked_paths"]),
        "remaining_coverage": manifest["remaining_coverage"],
        "counting_rule": "sample pass means the asserted outcome (including refusal) matched; Blocked paths are not pytest skips or passed samples; historical arithmetic counts are separate",
    }
    raw = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    out = DIRECTORY / "evidence" / datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = out / f"{stamp}-python{platform.python_version()}-public-l01-phase1-{args.revision[:12]}.json.gz"
    with dest.open("xb") as stream:
        stream.write(gzip.compress(raw, mtime=0))
    print(json.dumps({"report": str(dest), "uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
                      "summary": summary, "blocked_paths": len(manifest["blocked_paths"]),
                      "overall_status": "partial", "tested_revision": args.revision}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
