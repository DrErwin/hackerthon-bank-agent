import pytest

from coverage_readiness import audit


def test_function_quantities_are_independent_ids_and_not_group_rename():
    result = audit()
    assert result["design_quantity_gate"] and result["six_direction_design_gate"]
    assert len(result["functions"]) == 12
    memory = next(row for row in result["functions"] if row["id"] == "memory")
    assert "SEC-N-008" not in memory["case_ids"]
    assert "SEC-T-015" in memory["case_ids"]
    readonly = next(row for row in result["functions"] if row["id"] == "read")
    assert readonly["directions"]["failure_recovery"] == ["SEC-P-011"]
    assert all(not row["runtime_complete"] for row in result["functions"])
    assert len(result["inventory"]) == 138
    assert not result["acceptance_item_quantity_gate"]
    assert len(result["acceptance_items_under_10"]) == 29
    for issue in ("#174", "#145"):
        state = next(row["state"] for row in result["known_external_dependencies"] if issue in row["scope"])
        assert "historical Failed" in state and "merged" in state
        assert "pending merge" not in state


def test_readiness_rejects_other_batch_denominators():
    with pytest.raises(ValueError, match="DENOMINATOR_MISMATCH"):
        audit({"denominators": {"main_cases": 137}, "rows": []})


def test_failed_whole_case_and_partial_observations_remain_separate():
    initial = audit()
    result = audit({"denominators": initial["denominators"], "rows": [{
        "case_id": "SEC-X-008", "variant_id": "SEC-X-008/v01", "repeat_index": 1,
        "status": "Failed", "assertions": [{"name": "example", "passed": False}],
        "missing_observations": ["human presentation"], "evidence": {"adapter": "public-boundary-v1"}}]})
    row = next(row for row in result["inventory"] if row["case_id"] == "SEC-X-008")
    assert row["whole_case_status_counts"] == {"Failed": 1}
    assert row["observed_rows"] == 1
    assert row["remaining"] == ["human presentation"]
    assert row["actual_observation_mapping"][0]["code_entry"] == "public_boundary_adapter.run_public_boundary"
