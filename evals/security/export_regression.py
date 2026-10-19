"""Run existing public export checks plus ticket04 additions; never call a model."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.api import test_app, test_export_secrets


EXISTING = (
    "test_f21_returns_the_report_card_to_its_owner_only",
    "test_report_capture_is_bound_to_an_owned_task",
    "test_f22_card_export_downloads_without_reverification",
    "test_f22_details_export_requires_fresh_verification",
    "test_details_export_expires_with_its_challenge",
    "test_details_export_cancels_along_the_same_platform_task",
    "test_details_export_survives_code_resend",
    "test_details_export_fails_after_three_wrong_codes",
    "test_exports_stay_invisible_to_other_users",
)


class SafeResults:
    """Store outcomes only; exclude response bodies, local paths and tracebacks."""

    def __init__(self):
        self.rows = []
        self.collection_errors = 0

    def pytest_collectreport(self, report):
        self.collection_errors += int(report.failed)

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or report.failed or getattr(report, "skipped", False):
            status = "Failed" if report.failed else "Passed" if report.passed else "Blocked"
            test_id = report.nodeid.split("::", 1)[-1]
            previous = next((row for row in self.rows if row["test_id"] == test_id), None)
            if previous is not None:
                rank = {"Passed": 0, "Blocked": 1, "Failed": 2}
                if rank[status] > rank[previous["status"]]:
                    previous.update(phase=report.when, status=status)
            else:
                self.rows.append({"test_id": test_id, "phase": report.when, "status": status})


def run(output):
    output = output.resolve()
    workspace = Path(__file__).resolve().parents[2]
    if output.exists():
        raise FileExistsError("report already exists")
    if output.is_relative_to(workspace):
        raise ValueError("report must be outside the evaluation workspace")
    targets = [f"{test_app.__file__}::{name}" for name in EXISTING]
    targets += [f"{test_export_secrets.__file__}::test_details_export_never_stores_or_returns_the_verification_code",
                str(Path(__file__).with_name("test_export_boundary.py"))]
    results = SafeResults()
    exit_code = pytest.main([*targets, "-q", "--tb=no"], plugins=[results])
    files = [Path(__file__), Path(__file__).with_name("test_export_boundary.py"),
             Path(test_app.__file__), Path(test_export_secrets.__file__),
             Path(test_app.__file__).with_name("service.py")]
    report = {
        "schema_version": "security-export-regression-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "execution_layer": "real-http-api-with-controlled-platform-test-fixtures",
        "model_mode": "fixed offline planner; allow-all authorization and fixed risk callbacks",
        "real_model_calls": 0,
        "report_source": "controlled contract-valid L03 card, not real bills L01-L03",
        "scope": "F21-F24 platform export boundaries; no full-catalog denominator claim",
        "source_sha256": {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in files},
        "pytest_exit_code": int(exit_code),
        "collection_errors": results.collection_errors,
        "status_counts": dict(Counter(row["status"] for row in results.rows)),
        "rows": results.rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(output), "status_counts": report["status_counts"]}))
    return int(exit_code)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
