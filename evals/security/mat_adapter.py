"""MAT parameter expansion and honest offline probes, never a model fallback."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


PARAMETERS = Path(__file__).with_name("mat-parameters.jsonl")


def attach_material_parameters(cases):
    """Append v02 while preserving each published original as v01."""
    by_id = {case["id"]: case for case in cases}
    materials = [json.loads(line) for line in PARAMETERS.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
    ids = [item["material_id"] for item in materials]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_MAT_ID")
    for item in materials:
        case = by_id.get(item["case_id"])
        if case is None:
            raise ValueError("UNKNOWN_MAT_CASE")
        if not all(item.get(key) for key in ("payload", "legal_control", "source_ids",
                                              "preconditions", "expected", "must_not", "missing")):
            raise ValueError("INCOMPLETE_MAT_PARAMETER")
        if case["parameter_sets"]:
            raise ValueError("MAT_BASE_PARAMETER_CHANGED_REVIEW_REQUIRED")
        case["parameter_sets"] = ["默认参数", item["material_id"]]
        case["material_parameters"] = {2: item}
    return materials


def run_material_instance(case, directory, variant_index, repeat_index, execution_id):
    from security_runner import _environment, _observation, _result

    material = case["material_parameters"][variant_index]
    assertions = []
    evidence = {"material_id": material["material_id"], "entry": material["entry"],
                "source_ids": material["source_ids"], "real_model_calls": 0,
                "payload_sha256": hashlib.sha256(material["payload"].encode()).hexdigest(),
                "payload_delivered": False,
                "risk_source": "controlled-offline-fixture; real detection not evaluated",
                "model_mode": "fixed offline planner; no attack interpretation claim"}
    missing = list(material["missing"])
    if material["entry"] not in {"chat-direct", "chat-fraud"}:
        from interaction_adapter import ENTRIES as OBSERVED_ENTRIES, observe_entry
        if material["entry"] not in OBSERVED_ENTRIES:
            # A future entry without a real observation path stays honestly blocked.
            return _result(case, variant_index, repeat_index, assertions, missing, evidence, execution_id)
        assertions, missing, observed = observe_entry(case, material, directory)
        evidence.update(observed)
        return _result(case, variant_index, repeat_index, assertions, missing, evidence, execution_id)

    try:
        for name, text in (("attack", material["payload"]), ("legal_control", material["legal_control"])):
            env = _environment(Path(directory) / name, case)
            try:
                received = []
                original = env.planner.select

                def observe(intent_text, *args, **kwargs):
                    received.append(intent_text == text)
                    return original(intent_text, *args, **kwargs)

                env.planner.select = observe
                if material["entry"] == "chat-direct" or name == "legal_control":
                    env.start()
                    previous = env.confirmation()
                    previous_task = env.task["task_id"]
                    # A fixed ReplyOnly checks transport/state, not attack resistance.
                    env.planner.plan.variant = "INP-18"
                    env.start(text=text)
                    env.get_task()
                    current = env.confirmation()
                    _observation(assertions, name + ".pending_binding_preserved",
                                 env.task["task_id"] == previous_task
                                 and current["confirmation_id"] == previous["confirmation_id"]
                                 and current["display_fields"] == previous["display_fields"]
                                 and current["decision"] == "pending")
                else:
                    # Fraud text reaches the real HTTP entry, but risk is explicitly
                    # fixture-low: no detector conclusion is inferred from this probe.
                    env.start(text=text)
                _observation(assertions, name + ".text_reached_planner", any(received))
                _observation(assertions, name + ".no_bank_write",
                             not env.submissions and env.bank_state() == env.baseline)
                evidence[name] = {"text_received": any(received),
                                  "bank_submit_count": len(env.submissions),
                                  "bank_state_unchanged": env.bank_state() == env.baseline,
                                  "task_status": env.task["status"] if env.task else None}
                if name == "attack":
                    evidence["payload_delivered"] = any(received)
            finally:
                env.close()
    except Exception as exc:
        _observation(assertions, "material.adapter_completed", False)
        evidence["adapter_error_type"] = type(exc).__name__
        missing.append("The isolated material probe did not complete.")
    return _result(case, variant_index, repeat_index, assertions, missing, evidence, execution_id)


def main(argv=None):
    from security_runner import _git_head_revision, _output_inside_repository, load_security_catalog, run_instance

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError("report already exists")
    if _output_inside_repository(args.output):
        raise ValueError("report must be outside repository")
    work_root = args.output.parent / (args.output.stem + "-work")
    # Exclusive creation also protects interrupted runs whose JSON was not saved.
    work_root.mkdir(parents=True, exist_ok=False)
    catalog = load_security_catalog()
    rows = []
    for case in catalog.cases:
        for variant_index in case.get("material_parameters", {}):
            for repeat_index in range(1, case["repeats"] + 1):
                rows.append(run_instance(case, work_root / case["id"] / str(repeat_index),
                                         variant_index, repeat_index))
    report = {"schema_version": "security-mat-offline-v1", "real_model_calls": 0,
              "code_revision": _git_head_revision(),
              "material_sha256": hashlib.sha256(PARAMETERS.read_bytes()).hexdigest(),
              "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "execution_layer": "partial real HTTP transport; missing entries gated",
              "denominators": {"main_cases": len(catalog.cases),
                               "parameter_instances": catalog.parameter_instances,
                               "planned_result_rows": catalog.planned_rows},
              "selected_material_instances": sum(len(case.get("material_parameters", {})) for case in catalog.cases),
              "selected_rounds": len(rows),
              "status_counts": dict(Counter(row["status"] for row in rows)), "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status_counts": report["status_counts"], "denominators": report["denominators"]}))
    return int(any(row["status"] == "Failed" for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
