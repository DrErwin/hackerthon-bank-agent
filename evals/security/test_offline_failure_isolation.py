import json
import pytest

from security_runner import load_security_catalog, run_instance, run_suite


@pytest.mark.parametrize("case_id,module", [("SEC-L-010", "bills_audit_probe"), ("SEC-T-003", "detector_regression")])
def test_probe_exception_returns_safe_failed_result(tmp_path, monkeypatch, case_id, module):
    import importlib
    target = importlib.import_module(module)
    def interrupted(*args, **kwargs):
        raise RuntimeError("synthetic-sensitive-upstream-value")
    monkeypatch.setattr(target, "probe", interrupted)
    case = next(case for case in load_security_catalog().cases if case["id"] == case_id)
    row = run_instance(case, tmp_path / "instance", 1 if case["parameter_sets"] else None)
    assert row["status"] == "Failed" and row["evidence"]["adapter_error_type"] == "RuntimeError"
    assert "synthetic-sensitive" not in json.dumps(row)


def test_suite_preserves_each_failed_probe_and_unselected_rows(tmp_path, monkeypatch):
    import bills_audit_probe
    def interrupted(*_):
        raise RuntimeError("synthetic-sensitive-upstream-value")
    monkeypatch.setattr(bills_audit_probe, "probe", interrupted)
    report = run_suite(load_security_catalog(), tmp_path / "suite", ["SEC-L-010"])
    assert len(report["rows"]) == 357
    assert report["status_counts"]["Failed"] == 1
    assert report["status_counts"]["NotRun"] == 356
    assert "synthetic-sensitive" not in json.dumps(report)
