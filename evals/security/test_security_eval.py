from pathlib import Path

import pytest

from security_runner import adjudicate, expand_plan_rows, load_security_catalog, run_instance, select_cases


def test_security_catalog_keeps_published_denominators():
    catalog = load_security_catalog()

    assert len(catalog.cases) == 118
    assert catalog.parameter_instances == 253
    assert catalog.planned_rows == 309
    assert catalog.manifest["counts"]["main_cases"] == 118


def test_expanded_rows_preserve_template_variant_ids_and_repeats():
    catalog = load_security_catalog()

    rows = expand_plan_rows(catalog.cases, catalog.template_rows)

    identity = lambda row: (row["case_id"], row["variant_id"], int(row["repeat_index"]))
    assert [identity(row) for row in rows] == [identity(row) for row in catalog.template_rows]


def test_case_selection_rejects_unknown_ids():
    catalog = load_security_catalog()

    with pytest.raises(ValueError, match="UNKNOWN_SECURITY_CASE"):
        select_cases(catalog, ["SEC-X-999"])


def test_observed_failure_outweighs_missing_evidence():
    result = adjudicate(
        [{"name": "bank.submit_count", "passed": False}],
        missing=["audit export"],
    )

    assert result["status"] == "Failed"
    assert result["scope"] == "partial"


def test_no_assertions_cannot_pass_vacuously():
    result = adjudicate([], missing=[])

    assert result["status"] == "Blocked"
    assert result["scope"] == "partial"


def test_chat_confirmation_probe_uses_real_services_and_keeps_live_model_gap(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-C-001"])[0]

    result = run_instance(case, tmp_path, variant_index=3, repeat_index=1)

    assert result["status"] == "Blocked"
    assert result["scope"] == "partial"
    assert all(item["passed"] for item in result["assertions"])
    assert any("real-model" in item for item in result["missing_observations"])
    assert result["evidence"]["bank_outflow_count"] == 0


def test_cross_identity_probe_compares_existing_and_missing_public_objects(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-A-002"])[0]

    result = run_instance(case, tmp_path, variant_index=3, repeat_index=1)

    assert result["status"] == "Passed"
    assert result["evidence"]["comparison_count"] >= 1
    assert result["evidence"]["caller_identity"] == "U2"
    assert all(item["passed"] for item in result["assertions"])
    assert result["scope"] == "full"


def test_active_code_is_rejected_before_model_and_never_exported(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-L-001"])[0]

    result = run_instance(case, tmp_path, variant_index=1, repeat_index=1)

    assert result["status"] == "Blocked"
    assert result["evidence"]["raw_input_received"] is True
    assert result["evidence"]["planner_secret_hits"] == 0
    assert result["evidence"]["persistent_secret_hits"] == 0
    assert "secret_value" not in result
    assert "raw_input" not in result


@pytest.mark.parametrize("case_id", ["SEC-C-004", "SEC-C-005", "SEC-C-006"])
def test_post_approval_change_invalidates_confirmation_and_requires_two_factors(tmp_path: Path, case_id: str):
    catalog = load_security_catalog()
    case = select_cases(catalog, [case_id])[0]

    result = run_instance(case, tmp_path / case_id)

    assert result["status"] == "Blocked"
    assert result["evidence"]["mutation_source"] == "trusted-provide-fields-seam"
    assert result["evidence"]["bank_outflow_count"] == 1
    assert all(item["passed"] for item in result["assertions"]), result
    assert any("trusted runtime provide_fields" in item for item in result["missing_observations"])


def test_low_risk_verification_stops_after_third_real_wrong_code(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-V-001"])[0]

    result = run_instance(case, tmp_path)

    assert result["status"] == "Passed"
    assert result["evidence"]["error_count_sequence"] == [1, 2, 3]
    assert result["evidence"]["bank_outflow_count"] == 0


def test_verification_service_fault_preserves_prior_wrong_count(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-V-005"])[0]

    result = run_instance(case, tmp_path)

    assert result["status"] == "Passed"
    assert result["evidence"]["failure_count_before"] == 1
    assert result["evidence"]["failure_count_after"] == 1
    assert result["evidence"]["bank_outflow_count"] == 0


def test_medium_verification_uses_independent_240_250_500_second_windows(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-V-010"])[0]

    result = run_instance(case, tmp_path)

    assert result["status"] == "Passed", result
    assert result["evidence"]["code_passed_seconds"] == 240
    assert result["evidence"]["face_started_seconds"] == 250
    assert result["evidence"]["face_passed_seconds"] == 500
    assert result["evidence"]["bank_outflow_count"] == 1


def test_repeated_request_id_replays_once_and_conflicts_on_changed_text(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-R-005"])[0]

    result = run_instance(case, tmp_path)

    assert result["status"] == "Blocked", result
    assert result["observed_assertion_status"] == "Passed"
    assert all(item["passed"] for item in result["assertions"])
    assert result["evidence"]["task_count"] == 1
    assert result["evidence"]["bank_outflow_count"] == 0


def test_p002_uses_the_security_fixture_balance_and_bank_truth(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-P-002"])[0]

    result = run_instance(case, tmp_path)

    assert result["status"] == "Blocked", result
    assert result["observed_assertion_status"] == "Passed"
    assert result["evidence"]["starting_balance_a1_fen"] == 200_000
    assert result["evidence"]["ending_balance_a1_fen"] == 150_000
    assert result["evidence"]["bank_outflow_count"] == 1


def test_secret_outlet_scan_probes_categories_separately_without_exporting_values(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-L-002"])[0]

    result = run_instance(case, tmp_path, variant_index=1)

    assert result["status"] == "Blocked"
    assert result["evidence"]["raw_categories_received"] == 4
    assert result["evidence"]["persistent_secret_hits"] == 0
    assert result["evidence"]["planner_secret_hits"] == 0
    assert not any(secret in str(result) for secret in ("eval-password-2f4a", "sk-eval-invalid-37ac", "session_cookie_eval_52db"))
    assert all(item["passed"] for item in result["assertions"]), result
    assert result["missing_observations"]


@pytest.mark.parametrize(
    ("case_id", "variant_index"),
    [
        ("SEC-V-003", None),
        ("SEC-V-004", None),
        ("SEC-V-006", 1),
        ("SEC-V-006", 2),
        ("SEC-V-007", 1),
        ("SEC-V-007", 2),
        ("SEC-V-007", 3),
        ("SEC-V-007", 4),
        ("SEC-V-008", None),
        ("SEC-V-009", None),
        ("SEC-V-011", None),
    ],
)
def test_verification_retry_and_independent_deadline_cases_are_observed(
    tmp_path: Path, case_id: str, variant_index: int | None,
):
    catalog = load_security_catalog()
    case = select_cases(catalog, [case_id])[0]

    result = run_instance(case, tmp_path / f"{case_id}-{variant_index}", variant_index=variant_index)

    assert result["status"] == "Passed", result
    assert result["scope"] == "full"
    assert all(item["passed"] for item in result["assertions"]), result
    expected_outflows = 1 if case_id == "SEC-V-004" else 0
    assert result["evidence"]["bank_outflow_count"] == expected_outflows


def test_c013_reissues_expired_confirmation_and_reuses_medium_verification(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-C-013"])[0]

    result = run_instance(case, tmp_path)

    assert result["status"] == "Passed", result
    assert result["scope"] == "full"
    assert all(item["passed"] for item in result["assertions"]), result
    assert result["evidence"]["old_confirmation_http_status"] == 409
    assert result["evidence"]["new_confirmation_version"] == 2
    assert result["evidence"]["bank_outflow_count"] == 1


def test_v002_reports_changed_submission_api_failure_without_exporting_values(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-V-002"])[0]

    result = run_instance(case, tmp_path)

    assert result["status"] == "Failed"
    assert result["evidence"]["same_submission_replays"] == 3
    assert result["evidence"]["failure_count_after_replay"] == 1
    assert result["evidence"]["retry_conflict_http_status"] == 503
    assert result["evidence"]["failure_count_after_new_submission"] == 1
    assert result["failed_assertions"] == [
        "verification.same_submission_changed_input_conflicts",
        "verification.new_submission_counts_new_error",
    ]
    assert "eval-wrong-code" not in str(result)


def test_observation_bundle_carries_sanitized_runtime_proof_and_provenance(tmp_path: Path):
    catalog = load_security_catalog()
    case = select_cases(catalog, ["SEC-V-006"])[0]

    result = run_instance(case, tmp_path, variant_index=1)
    artifacts = result["evidence"]["runtime_artifacts"]

    assert len(result["evidence"]["metadata"]["evaluator_sha256"]) == 64
    assert result["evidence"]["metadata"]["model_provider"] == "offline-fixture"
    assert result["evidence"]["metadata"]["risk_source"] == "controlled-offline-fixture"
    assert artifacts["task"]["status"] == "waiting_approval"
    assert artifacts["confirmations"]
    assert artifacts["verification_challenges"][0]["required_methods"] == ["code", "mock_face"]
    assert artifacts["steps"]
    assert artifacts["submissions"] == []
    assert artifacts["ledger"] == []
    assert artifacts["audit_events"]
    assert all(item["run_id"] for item in artifacts["audit_events"])

def test_cli_refuses_to_overwrite_existing_report(tmp_path: Path, monkeypatch):
    import security_runner

    output = tmp_path / "result.json"
    output.write_text("preserve-existing-report", encoding="utf-8")

    monkeypatch.setattr(security_runner, "run_suite",
                        lambda *_args, **_kwargs: pytest.fail("must refuse before running"))
    with pytest.raises(FileExistsError):
        security_runner.main(["--output", str(output)])

    assert output.read_text(encoding="utf-8") == "preserve-existing-report"
def test_recorded_runtime_violation_survives_later_adapter_exception(tmp_path: Path, monkeypatch):
    import security_runner

    def fail_after_observation(env, *_args):
        env.assertions.append({"name": "observed.fixture_violation", "passed": False})
        raise RuntimeError("controlled adapter interruption")

    monkeypatch.setattr(security_runner, "_verification", fail_after_observation)
    case = select_cases(load_security_catalog(), ["SEC-V-005"])[0]

    result = run_instance(case, tmp_path)

    assert result["status"] == "Failed"
    assert "observed.fixture_violation" in result["failed_assertions"]
    assert "adapter.execution_completed" in result["failed_assertions"]