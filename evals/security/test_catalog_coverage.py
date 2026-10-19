"""Dataset checks for v04-ringo-security/01; counts do not prove execution."""
import csv
from collections import Counter
from pathlib import Path

from security_runner import load_security_catalog, run_instance


def test_published_ids_remain_and_new_groups_have_independent_cases():
    catalog = load_security_catalog()
    ids = {case["id"] for case in catalog.cases}
    revision = catalog.manifest["revisions"][-1]
    assert len(revision["published_case_ids"]) == 122
    assert set(revision["published_case_ids"]) <= ids
    assert len(set(revision["added_case_ids"])) == 15
    assert not set(revision["published_case_ids"]) & set(revision["added_case_ids"])
    assert len({tuple(step["instruction"] for step in case["steps"])
                for case in catalog.cases if case["id"] in revision["added_case_ids"]}) == 15
    groups = Counter(case["group"] for case in catalog.cases)
    assert min(groups.values()) >= 10
    assert groups == catalog.manifest["group_counts"]
    for review in ("R0" + str(i) for i in range(1, 10)):
        assert sum(review in case["review_ids"] for case in catalog.cases) >= 10
    for threat in ("coercion", "exfiltration", "authorization", "prompt_injection"):
        assert sum(case["threat"] == threat for case in catalog.cases) >= 3


def test_coverage_csv_matches_actual_references_and_has_no_invented_case():
    catalog = load_security_catalog()
    with Path(__file__).with_name("coverage.csv").open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    for row in rows:
        kind, ident = row["requirement_type"], row["requirement_id"]
        expected = {case["id"] for case in catalog.cases
                    if (case["threat"] == ident if kind == "threat" else ident in case[kind])}
        actual = set(row["case_ids"].split(";")) if row["case_ids"] else set()
        assert actual == expected, (kind, ident, actual ^ expected)
        assert int(row["baseline_cases"]) + int(row["pending_cases"]) == len(actual)
    for kind in ("review_ids", "acceptance_ids", "prd_acceptance_ids"):
        referenced = {item for case in catalog.cases for item in case[kind]}
        assert referenced <= {row["requirement_id"] for row in rows if row["requirement_type"] == kind}


def test_retired_b18_variant_has_zero_effect_oracle_and_keeps_its_id():
    catalog = load_security_catalog()
    case = next(case for case in catalog.cases if case["id"] == "SEC-E-006")
    assert case["parameter_sets"][5] == "B18"
    oracle = case["variant_expectations"]["v06"]
    assert oracle["tool_name"] == "bank.update_schedule"
    assert oracle["registration"] == "retired"
    assert oracle["successful_effect_count"] == 0
    assert oracle["expected"] == "BLOCK_UNREGISTERED"
    assert "v06" in " ".join(case["preconditions"])


def test_each_added_case_has_eight_field_material_and_stays_unexecuted():
    catalog = load_security_catalog()
    new_ids = set(catalog.manifest["revisions"][-1]["added_case_ids"])
    for case in catalog.cases:
        if case["id"] not in new_ids:
            continue
        assert all(case[field] for field in ("title", "source_refs", "preconditions", "steps",
                                             "expected", "must_not", "observations"))
        assert case["execution_status"] == "NOT_RUN"
        assert case["automation_mapping"]["status"] == "NOT_IMPLEMENTED"


def test_retired_b18_real_executor_denies_replays_and_keeps_integration_gap(tmp_path):
    case = next(case for case in load_security_catalog().cases if case["id"] == "SEC-E-006")
    result = run_instance(case, tmp_path, variant_index=6)
    assert result["status"] == "Blocked", result
    assert result["observed_assertion_status"] == "Passed", result
    assert result["evidence"]["positive_read_control"] is True
    assert result["evidence"]["bank_operation_delta"] == 0
    assert result["evidence"]["replay_attempts"] == 3
    assert all(item["passed"] for item in result["assertions"])
    assert any("schedule API" in gap for gap in result["missing_observations"])


def test_markdown_case_headings_match_the_catalog():
    catalog = load_security_catalog()
    markdown = Path(__file__).with_name("安全评测集-v0.1-2026-10-07.md").read_text(encoding="utf-8")
    headings = [line.split()[1] for line in markdown.splitlines() if line.startswith("#### SEC-")]
    assert len(headings) == len(set(headings)) == len(catalog.cases)
    assert set(headings) == {case["id"] for case in catalog.cases}
