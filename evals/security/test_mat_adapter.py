"""MAT is a parameter source, not authorization or a fake detector."""

import hashlib

import pytest

from mat_adapter import PARAMETERS, attach_material_parameters
from security_runner import expand_plan_rows, load_security_catalog, run_instance


def test_five_mandatory_parameters_keep_original_and_recompute_denominators():
    catalog = load_security_catalog()
    cases = [case for case in catalog.cases if case.get("material_parameters")]
    assert len(cases) == 5
    materials = [case["material_parameters"][2] for case in cases]
    assert {item["material_id"] for item in materials} == {
        "MAT-VFY16-01", "MAT-VFY16-02", "MAT-VFY16-03", "MAT-VFY16-04", "MAT-FRAUD-01"}
    assert (len(catalog.cases), catalog.parameter_instances, catalog.planned_rows) == (138, 295, 357)
    plan = expand_plan_rows(catalog.cases, catalog.template_rows)
    assert sum(row["variant_id"].endswith("/v02") and row["case_id"] in {case["id"] for case in cases}
               for row in plan) == 11
    for case in cases:
        assert case["parameter_sets"][0] == "默认参数"
        material = case["material_parameters"][2]
        assert material["legal_control"] and material["source_ids"] and material["execution_status"] == "NOT_RUN"


def test_chat_material_is_observed_without_claiming_model_or_detector_pass(tmp_path):
    case = next(case for case in load_security_catalog().cases if case["id"] == "SEC-T-010")
    result = run_instance(case, tmp_path, 2)
    assert result["status"] == "Blocked"
    assert result["observed_assertion_status"] == "Passed"
    assert result["evidence"]["payload_delivered"]
    assert result["evidence"]["legal_control"]["text_received"]
    assert all(item["passed"] for item in result["assertions"])
    assert result["evidence"]["payload_sha256"] == hashlib.sha256(case["material_parameters"][2]["payload"].encode()).hexdigest()


@pytest.mark.parametrize(("case_id", "entry"), [
    ("SEC-T-012", "tool-return"),
    ("SEC-T-008", "untrusted-material"),
    ("SEC-T-015", "memory-summary"),
])
def test_new_entry_observers_deliver_the_stimulus_and_stay_blocked(tmp_path, case_id, entry):
    case = next(case for case in load_security_catalog().cases if case["id"] == case_id)
    result = run_instance(case, tmp_path, 2)
    assert result["status"] == "Blocked"
    assert result["observed_assertion_status"] == "Passed"
    assert result["assertions"] and all(item["passed"] for item in result["assertions"])
    evidence = result["evidence"]
    assert evidence["entry"] == entry
    assert evidence["payload_delivered"] is True
    assert evidence["original_stimulus_delivered"] is True
    assert evidence["real_model_calls"] == 0
    # No new evidence adapter name; the default readiness mapping stays valid.
    assert "adapter" not in evidence
    assert result["missing_observations"]
    assert any("model" in item for item in result["missing_observations"])


def test_unknown_material_entry_is_blocked_without_pretending_delivery(tmp_path):
    import copy

    case = copy.deepcopy(next(case for case in load_security_catalog().cases if case["id"] == "SEC-T-012"))
    case["material_parameters"][2]["entry"] = "future-unimplemented-entry"
    result = run_instance(case, tmp_path, 2)
    assert result["status"] == "Blocked"
    assert result["evidence"]["payload_delivered"] is False
    assert result["assertions"] == []
    assert result["missing_observations"]


def test_material_binding_drift_requires_review():
    catalog = load_security_catalog()
    with pytest.raises(ValueError, match="CHANGED_REVIEW_REQUIRED"):
        attach_material_parameters(catalog.cases)


def test_live_material_cannot_silently_use_fixed_reply(tmp_path):
    case = next(case for case in load_security_catalog().cases if case["id"] == "SEC-T-010")
    with pytest.raises(ValueError, match="MAT_LIVE_ADAPTER_NOT_IMPLEMENTED"):
        run_instance(case, tmp_path, 2, planner_factory=lambda: object())


def test_cli_refuses_prior_work_directory_even_if_report_was_not_saved(tmp_path):
    from mat_adapter import main

    output = tmp_path / "interrupted.json"
    work = tmp_path / "interrupted-work"
    work.mkdir()
    marker = work / "prior-state.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        main(["--output", str(output)])
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not output.exists()
