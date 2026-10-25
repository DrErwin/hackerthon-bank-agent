"""Run the bounded offline/backend plan and emit secret-free, layered evidence.

No model configuration is loaded. The selected tests use temporary databases,
controlled planners or direct workflow entry; HTTP fixtures own ephemeral ports.
"""

import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[3]
PLAN = Path(__file__).with_name("plan.json")


class Results:
    def __init__(self):
        self.tests = {}
        self.collection_errors = []

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(report.nodeid)

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or report.failed or report.skipped:
            prior = self.tests.get(report.nodeid)
            # A teardown error may turn success into failure, never the reverse.
            if prior is None or prior["outcome"] != "failed":
                self.tests[report.nodeid] = {
                    "nodeid": report.nodeid, "outcome": report.outcome,
                    "phase": report.when,
                    "bank_observations": {k: json.loads(v) for k, v in report.user_properties
                                          if k in {"bank_facts", "bank_before", "bank_after"}},
                }


def matches(node, actual):
    return node == actual or actual.startswith(node + "[")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or ROOT == output or ROOT in output.parents:
        parser.error("output must be a new path outside the repository")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    nodes = list(dict.fromkeys(n for case in plan["cases"] for n in case["nodes"]))
    sys.path.insert(0, str(ROOT / "backend"))
    import pytest

    recorder = Results()
    # Do not persist pytest tracebacks: failures can contain synthetic raw
    # delivery/code fixtures. Report node IDs and facts; rerun locally for detail.
    started = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="cross-security-02-") as temporary:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = int(pytest.main([
                "-q", "--tb=no", "-p", "no:cacheprovider",
                "--rootdir", str(ROOT), "--basetemp", str(Path(temporary) / "pytest"),
                *[str(ROOT / n.split("::")[0]) + "::" + n.split("::", 1)[1]
                  for n in nodes],
            ], plugins=[recorder]))
    tests = list(recorder.tests.values())
    cases = []
    for case in plan["cases"]:
        selected = [r for r in tests if any(matches(n, r["nodeid"]) for n in case["nodes"])]
        all_present = all(any(matches(n, r["nodeid"]) for r in selected) for n in case["nodes"])
        status = "FAILED" if any(r["outcome"] == "failed" for r in selected) else (
            "PASSED" if all_present and all(r["outcome"] == "passed" for r in selected)
            else "BLOCKED")
        cases.append({**case, "status": status, "tests": selected})
    hashed = sorted(set(ROOT.glob("backend/app/**/*.py")) | {
        PLAN, Path(__file__).resolve(), Path(__file__).with_name("test_runtime.py"),
        ROOT / "backend/pyproject.toml",
    })
    fingerprint = hashlib.sha256()
    for path in hashed:
        fingerprint.update(path.relative_to(ROOT).as_posix().encode())
        fingerprint.update(hashlib.sha256(path.read_bytes()).digest())
    report = {
        "ticket": plan["ticket"], "started_at_utc": started,
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_fingerprint_sha256": fingerprint.hexdigest(),
        "environment": {
            "python": sys.version.split()[0],
            "packages": {name: version(name) for name in (
                "pytest", "fastapi", "pydantic", "deepagents", "langgraph",
                "langchain-openai", "uvicorn",
            )},
            "databases": "isolated pytest temporary directories",
            "http_ports": "127.0.0.1 ephemeral, owned by each HTTP fixture",
        },
        "pytest_exit_code": code, "test_totals": dict(Counter(r["outcome"] for r in tests)),
        "collection_errors": recorder.collection_errors,
        "overall": "FAILED" if code or any(c["status"] == "FAILED" for c in cases) else "BLOCKED",
        "real_model": "NOT_RUN", "browser": "BLOCKED", "human_security_acceptance": "UNVERIFIED",
        "scope": "Local components and real birthday composition; never full three-goal/model/browser acceptance.",
        "limitations": [
            "No provider calls or model comparison. Scripted planners/fixed risk fixtures are labelled per layer.",
            "HTTP component fixtures are not birthday page E2E. Runtime probes enter the workflow directly.",
            "Only new runtime probes export numeric bank observations; legacy node results rely on their source assertions.",
        ],
        "cases": cases, "pending": plan["pending"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"report": str(output), "overall": report["overall"],
                      "pytest_exit_code": code, "test_totals": report["test_totals"]}))
    return 1 if code or any(c["status"] != "PASSED" for c in cases) else 0


if __name__ == "__main__":
    raise SystemExit(main())
