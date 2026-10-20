"""Reuse existing component tests as explicitly partial scenario observations."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_ref(module, function):
    return "backend/app/" + module + ".py::test_" + function


GATE = "security/test_gate"
API = "api/test_app"
MEMORY = "memory/test_memory"
AUDIT = "audit/test_journal"
TRANSFER = "agent_platform/test_transfer_runtime"
BINDINGS = {
    "SEC-D-001": [test_ref(GATE, "gate_uses_real_confirmation_and_verification_record_refs")],
    "SEC-D-005": [test_ref(GATE, "high_risk_termination_is_durable")],
    "SEC-D-006": [test_ref(GATE, "audit_failure_pauses_before_handler")],
    "SEC-D-008": [test_ref(GATE, "risk_verification_rules_and_dependency_fail_closed")],
    "SEC-D-009": [test_ref("modules/bills/test_public_integration", "security_refusal_happens_before_bank_read")],
    "SEC-A-001": [test_ref(API, "cookie_origin_ownership_and_expired_session_checks")],
    "SEC-A-004": [test_ref(TRANSFER, "new_session_recovery_requires_new_confirmation_and_verification")],
    "SEC-A-006": [test_ref(GATE, "foreign_verification_blocks_and_invalid_challenge_pauses")],
    "SEC-A-007": [test_ref(GATE, "high_risk_termination_is_durable")],
    "SEC-A-009": [test_ref(API, "private_payee_form_does_not_copy_account_number_to_chat")],
    "SEC-C-002": [test_ref(GATE, "stale_cancelled_cross_user_and_changed_parameters_never_allow")],
    "SEC-C-003": [test_ref(TRANSFER, "confirmation_and_verification_show_bank_quote_and_backend_risk")],
    "SEC-E-001": [test_ref("services/test_bank", "transfer_is_denied_without_server_authorization")],
    "SEC-E-002": [test_ref(GATE, "stale_cancelled_cross_user_and_changed_parameters_never_allow")],
    "SEC-E-003": [test_ref(GATE, "executor_requires_execution_phase_and_rechecks_termination_before_claim")],
    "SEC-E-004": [test_ref(GATE, "registry_rejects_missing_or_unsafe_tool_declarations")],
    "SEC-E-005": [test_ref("services/test_bank", "bank_rejects_scope_balance_limit_payee_and_risk")],
    "SEC-E-009": [test_ref("security/test_bills_read_policy", "module_mutation_cannot_mutate_the_security_allowlist")],
    "SEC-R-001": [test_ref(API, "timeout_queries_original_operation_without_resubmitting")],
    "SEC-R-002": [test_ref(GATE, "abandoned_claim_not_found_never_redelivers_handler")],
    "SEC-R-003": [test_ref(API, "timeout_queries_original_operation_without_resubmitting")],
    "SEC-R-004": [test_ref(API, "new_session_queries_processing_operation_without_resubmitting")],
    "SEC-R-006": [test_ref(TRANSFER, "two_processes_cannot_submit_same_approved_operation_twice")],
    "SEC-R-007": [test_ref(API, "cancel_in_flight_only_queries_original_bank_operation")],
    "SEC-R-009": [test_ref(TRANSFER, "audit_start_failure_prevents_bank_submission")],
    "SEC-R-010": [test_ref("agent_platform/test_fault_snapshot", "completed_result_is_saved_before_completion_audit_fails")],
    "SEC-R-011": [test_ref(API, "live_sse_reconnect_replays_events_without_new_task")],
    "SEC-M-001": [test_ref(API, "medium_risk_face_is_admin_only_and_audit_read_does_not_run_model")],
    "SEC-M-002": [test_ref("security/test_demo_policy", "admin_face_authorization_uses_a_separate_configured_admin_identity")],
    "SEC-L-003": [test_ref(AUDIT, "redacted_evidence_survives_restart_and_is_scoped")],
    "SEC-L-005": [test_ref(AUDIT, "damaged_evidence_is_marked_missing_instead_of_exported")],
    "SEC-L-006": [test_ref(AUDIT, "redacted_evidence_survives_restart_and_is_scoped")],
    "SEC-L-007": [test_ref(AUDIT, "export_marks_missing_results_without_running_tools")],
    "SEC-L-008": [test_ref(API, "read_dependency_errors_use_controlled_envelope_without_exception_text")],
    "SEC-L-009": [test_ref(AUDIT, "sensitive_allow_requires_matching_persisted_authorization")],
    "SEC-N-001": [test_ref("agent_platform/test_payee_references", "reference_denies_other_scope")],
    "SEC-N-002": [test_ref(MEMORY, "agent_file_writes_reject_prohibited_memory")],
    "SEC-N-003": [test_ref(MEMORY, "scope_and_reset_reject_old_session_and_restore_seeds")],
    "SEC-N-004": [test_ref(MEMORY, "agent_file_writes_reject_prohibited_memory")],
    "SEC-N-005": [test_ref(MEMORY, "agent_file_writes_reject_prohibited_memory")],
    "SEC-N-006": [test_ref(MEMORY, "scope_and_reset_reject_old_session_and_restore_seeds")],
    "SEC-N-007": [test_ref(MEMORY, "delete_is_atomic_versioned_idempotent_and_refreshes_context")],
    "SEC-N-008": [test_ref(GATE, "confirmation_is_durable_button_only_versioned_and_one_hour")],
    "SEC-P-001": [test_ref("modules/bills/test_public_integration", "real_bank_harness_and_security_complete_l01")],
    "SEC-P-008": [test_ref("modules/bills/test_public_integration", "real_details_returns_bank_metadata_not_invented_values")],
    "SEC-P-009": [test_ref(TRANSFER, "medium_risk_requires_bound_code_and_face_record")],
    "SEC-P-011": [test_ref("modules/bills/test_public_integration", "bank_failure_is_a_failed_trace_and_retryable_original_task")],
    "SEC-X-005": [test_ref("modules/bills/test_report_service", "share_request_does_not_share_or_grant_download")],
    "SEC-T-001": [test_ref(GATE, "high_risk_termination_is_durable")],
    "SEC-T-002": [test_ref(TRANSFER, "medium_risk_requires_bound_code_and_face_record")],
    "SEC-T-015": [test_ref(MEMORY, "agent_file_writes_reject_prohibited_memory")],
    "SEC-V-012": [test_ref("agent_platform/test_session_verification_reuse", "session_verification_survives_restart_and_new_task_confirms_once")],
    "SEC-V-013": [test_ref("security/test_verification_terminal", "bank_terminal_fact_is_durable_and_cannot_resume")],
    "SEC-V-014": [test_ref(API, "no_secrets_in_chat_validation_errors_or_persisted_receipts")],
    "SEC-V-015": [test_ref("api/test_verification_fault", "verification_fault_updates_task_and_replays_original_submission")],
    "SEC-V-016": [test_ref(API, "resending_code_replaces_current_challenge_without_resetting_failures")],
    "SEC-V-017": [test_ref(GATE, "mismatched_medium_risk_summary_cannot_authorize")],
}


class SafeCollector:
    def __init__(self):
        self.results = {}
        self.collection_errors = 0

    def pytest_collectreport(self, report):
        self.collection_errors += int(report.failed)

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or report.failed or report.skipped:
            # Parameterized test node IDs can contain synthetic credentials.
            key = hashlib.sha256(report.nodeid.encode()).hexdigest()
            status = "Failed" if report.failed else "Blocked" if report.skipped else "Passed"
            rank = {"Passed": 0, "Blocked": 1, "Failed": 2}
            if rank[status] >= rank.get(self.results.get(key), -1):
                self.results[key] = status


def worker(input_path, output_path):
    import pytest
    sys.path.insert(0, str(ROOT / "backend"))
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    targets, hashes = [], {}
    for target in data["targets"]:
        path, function = target.split("::", 1)
        resolved = (ROOT / path).resolve()
        if not resolved.is_relative_to(ROOT) or not function.startswith("test_"):
            raise ValueError("invalid registered component target")
        targets.append(str(resolved) + "::" + function)
        hashes[path] = hashlib.sha256(resolved.read_bytes()).hexdigest()
    collector = SafeCollector()
    code = pytest.main([*targets, "-q", "--tb=no", "--basetemp", str(Path(output_path).parent / "pytest")],
                       plugins=[collector])
    report = {"pytest_exit_code": int(code), "collection_errors": collector.collection_errors,
              "results": collector.results, "source_sha256": hashes}
    with Path(output_path).open("x", encoding="utf-8") as stream:
        json.dump(report, stream)
    return int(code)


def run_component(case, directory, variant, repeat, execution_id):
    from security_runner import _result
    # A nearby component test is not an implementation of another parameter.
    selected_variant = {"SEC-P-001": 2, "SEC-E-003": 2}.get(case["id"], 1)
    if variant not in (None, selected_variant):
        return _result(case, variant, repeat, [],
            ["No registered component observation for this exact parameter; no substitute was run."],
            {"real_model_calls": 0, "original_stimulus_delivered": False}, execution_id)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    source, output = directory / "targets.json", directory / "result.json"
    with source.open("x", encoding="utf-8") as stream:
        json.dump({"targets": BINDINGS[case["id"]]}, stream)
    try:
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve()),
            "--worker-input", str(source), "--worker-output", str(output)],
            capture_output=True, timeout=120, check=False)
    except subprocess.TimeoutExpired:
        return _result(case, variant, repeat,
            [{"name": "component_worker_completed", "passed": False}],
            ["Component worker exceeded its observation deadline; suite continues with a failed adapter."],
            {"error_type": "TimeoutExpired", "real_model_calls": 0}, execution_id)
    if not output.exists():
        return _result(case, variant, repeat, [{"name": "component_worker_completed", "passed": False}],
            ["Component worker produced no safe result."], {"returncode": completed.returncode}, execution_id)
    report = json.loads(output.read_text(encoding="utf-8"))
    assertions = [{"name": "component:" + ref, "passed": status == "Passed"}
                  for ref, status in report["results"].items() if status != "Blocked"]
    if report["collection_errors"]:
        assertions.append({"name": "component_collection_completed", "passed": False})
    if report["pytest_exit_code"] not in {0, 1, 5}:
        assertions.append({"name": "component_worker_completed", "passed": False})
    return _result(case, variant, repeat, assertions,
        ["Component assertions only; the exact published scenario/variant and presentation are not fully exercised.",
         "A component pass is not evidence that the original attack payload reached a model."],
        {"adapter": "component-observations-v1", "targets": BINDINGS[case["id"]],
         "component_results": report, "real_model_calls": 0,
         "original_stimulus_delivered": False}, execution_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-input", type=Path, required=True)
    parser.add_argument("--worker-output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(worker(args.worker_input, args.worker_output))
