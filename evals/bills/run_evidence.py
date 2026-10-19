"""Pinned, append-only private-arithmetic evidence (not whole-business acceptance).

Clean checkout: python evals/bills/run_evidence.py --revision <full commit SHA>
Network-isolated slice: add --source-manifest <connector-verified manifest>.
The latter never claims package initialization, bank/API/UI or full-repo coverage.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "DrErwin/hackerthon-bank-agent"
SOURCE_PATHS = (
    "backend/app/contracts/common.py",
    "backend/app/modules/bills/_statistics.py",
    "backend/app/modules/bills/manifest.py",
    "backend/app/modules/bills/test_statistics.py",
    "backend/app/modules/bills/test_statistics_contract.py",
    "evals/bills/conftest.py",
    "evals/bills/test_statistics_eval.py",
    "evals/bills/fixtures/arithmetic-cases.json",
    "evals/bills/fixture_map.json",
    "evals/bills/run_evidence.py",
    "evals/bills/test_evidence_integrity.py",
    "evals/bills/representative-cases.md",
    "evals/bills/expanded-cases.md",
    "evals/bills/coverage-matrix.md",
)
TEST_PATHS = (
    "backend/app/modules/bills/test_statistics.py",
    "backend/app/modules/bills/test_statistics_contract.py",
    "evals/bills/test_statistics_eval.py",
    "evals/bills/test_evidence_integrity.py",
)
CASE_RE = re.compile(r"BILL-(?:[A-Z0-9]+-)?\d+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_bytes(raw: bytes) -> bytes:
    # Decode to fail on corruption; do NOT strip whitespace or normalize Unicode.
    raw.decode("utf-8")
    return raw.replace(b"\r\n", b"\n")


def fingerprints(raw: bytes) -> dict[str, str]:
    data = canonical_bytes(raw)
    return {"sha256": hashlib.sha256(data).hexdigest(),
            "git_blob_sha": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}


def verify_sources(revision: str, manifest_path: Path | None, *, root: Path = ROOT) -> tuple[str, dict]:
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("use an exact 40-character tested commit")
    if manifest_path is not None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (manifest["tested_revision"] != revision or manifest["repository"] != REPOSITORY
                or set(manifest["files"]) != set(SOURCE_PATHS)):
            raise ValueError("manifest repository, revision or file set mismatch")
        expected = manifest["files"]
        mode = "connector_verified_file_slice"
    else:
        resolved = subprocess.run(["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
                                  cwd=root, check=True, capture_output=True, text=True).stdout.strip()
        if resolved != revision:
            raise ValueError("revision is not the exact commit")
        expected = {}
        for path in SOURCE_PATHS:
            raw = subprocess.run(["git", "show", f"{revision}:{path}"], cwd=root,
                                 check=True, capture_output=True).stdout
            expected[path] = fingerprints(raw)
        mode = "git_object_verified_source_files"
    actual = {path: fingerprints((root / path).read_bytes()) for path in SOURCE_PATHS}
    if actual != expected:
        changed = [path for path in SOURCE_PATHS if actual[path] != expected[path]]
        raise ValueError(f"working sources differ from pinned revision: {changed}")
    records = {}
    for path in SOURCE_PATHS:
        raw = (root / path).read_bytes()
        records[path] = {**actual[path], "worktree_sha256": hashlib.sha256(raw).hexdigest(),
                         "worktree_bytes": len(raw), "crlf_normalized": b"\r\n" in raw}
    return mode, records


def case_definitions(text: str) -> dict[str, str]:
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and CASE_RE.fullmatch(cells[0]):
            if cells[0] in rows:
                raise ValueError(f"duplicate definition: {cells[0]}")
            if len(cells) != 8:
                raise ValueError(f"expected eight fields: {cells[0]}")
            rows[cells[0]] = line
    return rows


def validate_case_links(cases: list[dict], mapping: dict[str, list[str]],
                        core: str, expanded: str, matrix: str) -> dict[str, int]:
    core_rows, expanded_rows = case_definitions(core), case_definitions(expanded)
    definitions = set(core_rows) | set(expanded_rows)
    ids = [c["id"] for c in cases]
    if len(set(ids)) != len(ids) or any(re.fullmatch(r"ARITH-\d{2}", c) is None for c in ids):
        raise ValueError("duplicate or invalid fixture ID")
    if mapping != {c["id"]: c["case_ids"] for c in cases}:
        raise ValueError("fixture and mapping differ")
    for sample, linked in mapping.items():
        if not linked or len(set(linked)) != len(linked):
            raise ValueError(f"empty or duplicate mapping: {sample}")
        for case_id in linked:
            if case_id not in definitions:
                raise ValueError(f"undefined business case: {case_id}")
            if case_id in expanded_rows and sample not in expanded_rows[case_id]:
                raise ValueError(f"missing reverse link: {case_id} -> {sample}")
    unknown = set(CASE_RE.findall(matrix)) - definitions
    if unknown:
        raise ValueError(f"matrix references undefined cases: {sorted(unknown)}")
    inverse = {}
    for line in matrix.splitlines():
        match = re.match(r"^\|\s*(ARITH-\d{2})\s*\|([^|]+)\|", line)
        if match:
            if match[1] in inverse:
                raise ValueError(f"duplicate matrix sample: {match[1]}")
            inverse[match[1]] = CASE_RE.findall(match[2])
    if inverse != mapping:
        raise ValueError("human matrix and machine mapping differ")
    return {"core_designs": len(core_rows), "expanded_designs": len(expanded_rows),
            "overlap_designs": len(set(core_rows) & set(expanded_rows)),
            "unique_designs": len(definitions), "golden_fixtures": len(cases),
            "partially_linked_designs": len({c for linked in mapping.values() for c in linked})}


class EvidencePlugin:
    def __init__(self, mapping: dict[str, list[str]]):
        self.mapping = mapping
        self.samples: dict[str, dict] = {}
        self.collected = 0
        self.collection_errors: list[str] = []

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(str(report.longrepr))

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        sample = item.callspec.id if hasattr(item, "callspec") else None
        fixture = sample if sample in self.mapping else None
        tier = "evidence_tooling" if Path(str(item.path)).name == "test_evidence_integrity.py" else "private_arithmetic"
        self.samples[item.nodeid] = {"nodeid": item.nodeid, "fixture_id": fixture,
            "business_case_ids": self.mapping[fixture] if fixture else [],
            "tier": tier, "started_at": utc_now(), "phases": []}
        start = time.perf_counter()
        yield
        record = self.samples[item.nodeid]
        record["finished_at"] = utc_now()
        record["duration_seconds"] = time.perf_counter() - start

    def pytest_runtest_logreport(self, report):
        record = self.samples[report.nodeid]
        record["phases"].append({"phase": report.when, "outcome": report.outcome,
                                  "duration_seconds": report.duration})
        if report.failed:
            record["failure"] = str(report.longrepr)

    def results(self) -> tuple[dict, list[dict]]:
        counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
        records = list(self.samples.values())
        for record in records:
            phases = record["phases"]
            if any(p["outcome"] == "failed" and p["phase"] != "call" for p in phases):
                result = "error"
            elif any(p["outcome"] == "failed" for p in phases):
                result = "failed"
            elif any(p["outcome"] == "skipped" for p in phases):
                result = "skipped"
            elif any(p["phase"] == "call" and p["outcome"] == "passed" for p in phases):
                result = "passed"
            else:
                result = "error"
            record["result"] = result
            counts[result] += 1
        counts["collection_errors"] = len(self.collection_errors)
        return counts, records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    mode, sources = verify_sources(args.revision, args.source_manifest)
    directory = ROOT / "evals/bills"
    cases = json.loads((directory / "fixtures/arithmetic-cases.json").read_text(encoding="utf-8"))["cases"]
    mapping = json.loads((directory / "fixture_map.json").read_text(encoding="utf-8"))
    coverage = validate_case_links(cases, mapping,
        (directory / "representative-cases.md").read_text(encoding="utf-8"),
        (directory / "expanded-cases.md").read_text(encoding="utf-8"),
        (directory / "coverage-matrix.md").read_text(encoding="utf-8"))
    plugin = EvidencePlugin(mapping)
    started = utc_now()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "backend"))
    command = ["-q", *TEST_PATHS]
    exit_code = int(pytest.main(command, plugins=[plugin]))
    summary, samples = plugin.results()
    if (plugin.collected == 0 or plugin.collected != len(samples)) and exit_code == 0:
        exit_code = 5
    report = {
        "schema_version": 3, "repository": REPOSITORY, "tested_revision": args.revision,
        "source_verification": mode, "canonicalization": "UTF-8; CRLF to LF only",
        "source_files": sources, "started_at": started, "finished_at": utc_now(),
        "python_version": platform.python_version(), "pytest_version": pytest.__version__,
        "system": platform.system(), "pytest_args": command,
        "collected": plugin.collected, "exit_code": exit_code, "summary": summary,
        "tier_counts": dict(Counter(s["tier"] for s in samples)),
        "design_coverage_counts": coverage, "collection_errors": plugin.collection_errors,
        "samples": samples,
        "package_initializers_present": {p: (ROOT / p).exists() for p in
            ("backend/app/__init__.py", "backend/app/contracts/__init__.py")},
        "scope": "private arithmetic plus evidence tooling; no complete bills business acceptance",
        "not_verified": ["L01/L02/L03 public flows", "B08 authorization/data fetching", "task recovery",
                         "live model", "HTTP", "React", "professional security review", "full-repository regression"],
    }
    raw = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
    out = args.output_dir or directory / "evidence" / datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = out / f"{stamp}-python{platform.python_version()}-private-arithmetic-{args.revision[:12]}.json.gz"
    with dest.open("xb") as stream:
        stream.write(gzip.compress(raw, mtime=0))
    print(json.dumps({"report": str(dest), "uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
                      "summary": summary, "tested_revision": args.revision}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
