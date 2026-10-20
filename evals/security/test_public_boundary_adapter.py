from pathlib import Path

import pytest

from public_boundary_adapter import SUPPORTED, run_public_boundary
from security_runner import load_security_catalog, run_instance


@pytest.mark.parametrize("case_id,variant", [
    *((case_id, 1) for case_id in sorted(SUPPORTED - {"SEC-X-008"})),
    ("SEC-X-003", 2), ("SEC-X-003", 3),
    *(("SEC-X-006", variant) for variant in range(2, 7)),
])
def test_actual_boundaries_keep_whole_case_gaps(tmp_path, case_id, variant):
    case = next(case for case in load_security_catalog().cases if case["id"] == case_id)
    variant = variant if case["parameter_sets"] else None
    row = run_public_boundary(case, tmp_path / "probe", variant, 1, "test-execution")
    assert row["assertions"]
    assert all(item["passed"] for item in row["assertions"]), row
    assert row["status"] == "Blocked"
    assert row["observed_assertion_status"] == "Passed"
    assert row["missing_observations"]


def test_catalog_dispatches_a_supported_public_probe(tmp_path):
    case = next(case for case in load_security_catalog().cases if case["id"] == "SEC-X-009")
    row = run_instance(case, tmp_path / "dispatch")
    assert row["evidence"].get("adapter") == "public-boundary-v1"
    assert row["observed_assertion_status"] == "Passed"


def test_used_probe_directory_is_rejected(tmp_path):
    case = next(case for case in load_security_catalog().cases if case["id"] == "SEC-X-009")
    with pytest.raises(FileExistsError):
        run_public_boundary(case, tmp_path, None, 1, "repeat")


@pytest.mark.parametrize("variant", [1, 2])
def test_generation_failure_is_observed_as_fail_not_hidden_by_missing_evidence(tmp_path, variant):
    case = next(case for case in load_security_catalog().cases if case["id"] == "SEC-X-008")
    row = run_public_boundary(case, tmp_path / "generation", variant, 1, "test-generation")
    # The observer stays valid after the provider fixes the product.
    assert row["status"] == ("Failed" if row["failed_assertions"] else "Blocked")
    assert any(item["name"] == "bank_funds_unchanged" and item["passed"] for item in row["assertions"])
