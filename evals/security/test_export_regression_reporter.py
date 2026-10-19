"""The report must not hide failures or overwrite source/evidence files."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from export_regression import SafeResults, run


def event(when, *, failed=False, passed=False):
    return SimpleNamespace(when=when, failed=failed, passed=passed,
                           nodeid="test_export_boundary.py::test_synthetic_marker")


def test_teardown_failure_replaces_call_pass_and_keeps_one_result():
    collector = SafeResults()
    collector.pytest_runtest_logreport(event("call", passed=True))
    collector.pytest_runtest_logreport(event("teardown", failed=True))
    assert collector.rows == [{"test_id": "test_synthetic_marker", "phase": "teardown",
                               "status": "Failed"}]


def test_setup_failure_and_collection_failure_remain_visible():
    collector = SafeResults()
    collector.pytest_runtest_logreport(event("setup", failed=True))
    collector.pytest_collectreport(SimpleNamespace(failed=True))
    assert collector.rows[0]["status"] == "Failed"
    assert collector.collection_errors == 1


def test_report_refuses_existing_file(tmp_path):
    existing = tmp_path / "existing.json"
    existing.touch()
    with pytest.raises(FileExistsError):
        run(existing)
    assert existing.read_bytes() == b""


def test_setup_skip_is_recorded_as_blocked_instead_of_disappearing():
    collector = SafeResults()
    skipped = event("setup")
    skipped.skipped = True
    collector.pytest_runtest_logreport(skipped)
    assert collector.rows == [{"test_id": "test_synthetic_marker", "phase": "setup",
                               "status": "Blocked"}]


def test_report_refuses_source_workspace():
    with pytest.raises(ValueError, match="outside"):
        run(Path(__file__).with_name("unused-export-report.json"))
