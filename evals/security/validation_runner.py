"""Safe offline pytest report: no captured output, test parameters or tracebacks."""

import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import time

from component_adapter import ROOT, SafeCollector


def run(suite, output):
    import pytest
    if output.exists() or output.resolve().is_relative_to(ROOT):
        raise ValueError("validation output requires a fresh path outside the repository")
    work = output.parent / (output.stem + "-work")
    work.mkdir(parents=True, exist_ok=False)
    for path in (ROOT / "backend", ROOT / "evals" / "transfer", ROOT / "evals" / "security"):
        sys.path.insert(0, str(path))
    targets = {"backend": [ROOT / "backend" / "app"], "security": [ROOT / "evals" / "security"],
               "security-core": [ROOT / "backend" / "app" / "security"],
               "l03": [ROOT / "backend" / "app" / path for path in (
                   "security/test_bills_report_policy.py", "security/test_bills_read_policy.py", "agent_platform/test_local_demo.py")],
               "declarations": [ROOT / "backend" / "app" / "security" / name for name in (
                   "test_module_declaration_boundary.py", "test_bills_read_policy.py", "test_bills_report_policy.py")]}
    collector = SafeCollector()
    started = time.monotonic()
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        code = pytest.main([*[str(path) for path in targets[suite]], "-q", "--tb=no", "--basetemp", str(work / "pytest")], plugins=[collector])
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    result = {"schema_version": "security-validation-summary-v1", "suite": suite,
              "code_revision": revision, "pytest_exit_code": int(code),
              "counts": dict(Counter(collector.results.values())), "tests": collector.results,
              "collection_errors": collector.collection_errors,
              "elapsed_seconds": round(time.monotonic() - started, 3), "real_model_calls": 0,
              "note": "Test node IDs hashed. No raw parameters, captured output or tracebacks exported. Unit green does not imply catalog acceptance."}
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("suite", "pytest_exit_code", "counts", "collection_errors")}))
    return int(code)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("backend", "security", "l03", "declarations", "security-core"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.suite, args.output))
