"""Trace design coverage and actual observations without inferring acceptance."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from security_runner import ROOT, load_security_catalog

HERE = Path(__file__).resolve().parent
DIRECTIONS = {"normal", "negative", "boundary", "information_change", "failure_recovery", "risk_cross"}


def audit(report=None):
    catalog = load_security_catalog()
    definitions = json.loads((HERE / "function-coverage.json").read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in catalog.cases}
    functions = []
    for definition in definitions["functions"]:
        ids = set(definition.get("case_ids", [])) | set(definition.get("extra", []))
        ids |= {case["id"] for case in catalog.cases if case["group"] in definition.get("groups", [])}
        if not ids <= by_id.keys() or set(definition["directions"]) != DIRECTIONS:
            raise ValueError("INVALID_FUNCTION_COVERAGE_REGISTRY")
        if any(not set(values) <= ids for values in definition["directions"].values()):
            raise ValueError("DIRECTION_OUTSIDE_FUNCTION")
        functions.append({"id": definition["id"], "name": definition["name"], "source": definition["source"],
                          "case_ids": sorted(ids), "independent_case_count": len(ids),
                          "quantity_at_least_10": len(ids) >= 10,
                          "directions": definition["directions"],
                          "six_directions_have_design": all(definition["directions"].values()),
                          "runtime_complete": False})
    threats = {name: sum(case["threat"] == name for case in catalog.cases)
               for name in ("coercion", "exfiltration", "authorization", "prompt_injection")}
    # Cases that serve business-module scenarios rather than a public security family stay visible.
    function_ids = set().union(*(set(item["case_ids"]) for item in functions))
    outside_functions = sorted(set(by_id) - function_ids)
    # Record each exact cited clause instead of treating group counts as proof.
    clauses = sorted({ref for case in catalog.cases for ref in case["source_refs"]})
    clause_rows = [{"source_ref": ref, "case_ids": sorted(case["id"] for case in catalog.cases if ref in case["source_refs"])}
                   for ref in clauses]
    acceptance_rows = []
    for kind in ("acceptance_ids", "prd_acceptance_ids"):
        for key in sorted({key for case in catalog.cases for key in case[kind]}):
            ids = sorted(case["id"] for case in catalog.cases if key in case[kind])
            acceptance_rows.append({"type": kind, "id": key, "case_ids": ids, "main_case_count": len(ids),
                                    "deficit_to_10": max(0, 10 - len(ids))})
    under_10 = [row for row in acceptance_rows if row["main_case_count"] < 10]
    if report is not None and report["denominators"] != {
            "main_cases": len(catalog.cases), "parameter_instances": catalog.parameter_instances,
            "planned_result_rows": catalog.planned_rows}:
        raise ValueError("READINESS_REPORT_DENOMINATOR_MISMATCH")
    inventory = []
    for case in catalog.cases:
        rows = [row for row in (report or {}).get("rows", []) if row["case_id"] == case["id"]]
        observed = [row for row in rows if row.get("assertions")]
        targets = sorted({target for row in rows for target in row.get("evidence", {}).get("targets", [])})
        mapping = []
        for row in observed:
            evidence = row.get("evidence", {})
            entry = {"public-boundary-v1": "public_boundary_adapter.run_public_boundary",
                     "component-observations-v1": "component_adapter.run_component"}.get(evidence.get("adapter"))
            if entry is None:
                entry = ("bills_audit_probe.probe" if case["id"] == "SEC-L-010" else
                         "detector_regression.probe" if case["id"] in {"SEC-T-003", "SEC-T-004", "SEC-T-005"} else
                         "mat_adapter.run_material_instance" if evidence.get("material_id") else "security_runner.run_instance")
            mapping.append({"variant_id": row["variant_id"], "repeat_index": row["repeat_index"],
                            "code_entry": entry, "actual_status": row["status"],
                            "assertion_count": len(row["assertions"]),
                            "original_stimulus_delivered": evidence.get("original_stimulus_delivered", "not attested by this map")})
        inventory.append({"case_id": case["id"], "title": case["title"], "source_refs": case["source_refs"],
                          "designed_instances": max(1, len(case["parameter_sets"])),
                          "planned_rows": max(1, len(case["parameter_sets"])) * case["repeats"],
                          "observed_rows": len(observed),
                          "whole_case_status_counts": dict(Counter(row["status"] for row in rows)),
                          "component_targets": targets,
                          "actual_observation_mapping": mapping,
                          "remaining": sorted({gap for row in rows for gap in row.get("missing_observations", [])}),
                          "source_design_status": case["execution_status"]})
    return {"schema_version": "security-function-readiness-v1",
            "scope": definitions["scope"], "design_review_is_not_runtime_approval": True,
            "denominators": {"main_cases": len(catalog.cases), "parameter_instances": catalog.parameter_instances,
                             "planned_result_rows": catalog.planned_rows},
            "functions": functions, "threat_counts": threats,
            "design_quantity_gate": all(item["quantity_at_least_10"] for item in functions) and min(threats.values()) >= 3,
            "quantity_gate_scope": "12 security function families only; does not close the acceptance-item gate",
            "acceptance_item_quantity_gate": not under_10,
            "acceptance_items_under_10": under_10,
            "cases_outside_function_matrix": outside_functions,
            "six_direction_design_gate": all(item["six_directions_have_design"] for item in functions),
            "rule_trace": clause_rows, "inventory": inventory,
            "known_external_dependencies": [
                {"scope": "F26-F31 management/reset/one-shot faults, F35/F24 audit export, F37/F38 memory API", "owner": "Erwin", "state": "missing public assembly or endpoints"},
                {"scope": "Production L03 assembly and cross-module workflows", "owner": "Erwin and business module owners", "state": "not inferred from test harness"},
                {"scope": "Untrusted tool/file/memory attack transport, proposed calls and final output observers", "owner": "Erwin/platform with Ringo adapters", "state": "missing trusted observation seam"},
                {"scope": "Risk terminal wording", "owner": "梁爽", "state": "historical and current source still require issue #173; actual observations in inventory"},
                {"scope": "Export generation failures, issue #174", "owner": "Erwin", "state": "40a61c3 historical Failed; fix #180 merged in 8329dbec basis; current probe assertions in inventory"},
                {"scope": "Bills audit minimum evidence, issue #145", "owner": "周恩宇", "state": "40a61c3 historical Failed, b3a00b0 candidate Passed; fix #171 merged in 8329dbec basis; current assertions in inventory"},
                {"scope": "Real model rerun and page interaction", "owner": "Ringo with budget confirmation / frontend", "state": "not run this offline delivery"}],
            "limitations": definitions["limitations"],
            "input_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in
                             (HERE / "cases.jsonl", HERE / "function-coverage.json", HERE / "source-manifest.json")}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(ROOT):
        raise ValueError("audit output requires a fresh path outside the repository")
    report = json.loads(args.run_report.read_text(encoding="utf-8")) if args.run_report else None
    result = audit(report)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("denominators", "design_quantity_gate", "six_direction_design_gate", "acceptance_item_quantity_gate")}))
    return int(not result["design_quantity_gate"] or not result["six_direction_design_gate"] or not result["acceptance_item_quantity_gate"])


if __name__ == "__main__":
    raise SystemExit(main())
