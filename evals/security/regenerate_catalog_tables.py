"""Mechanical regeneration of derived catalog tables, preserving published rows."""

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def regenerate():
    cases = [json.loads(line) for line in (HERE / "cases.jsonl").read_text(encoding="utf-8-sig").splitlines() if line]
    from mat_adapter import attach_material_parameters
    attach_material_parameters(cases)
    path = HERE / "coverage.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, old = reader.fieldnames, list(reader)
    keys = [(row["requirement_type"], row["requirement_id"]) for row in old]
    for kind in ("review_ids", "acceptance_ids", "prd_acceptance_ids"):
        keys.extend((kind, key) for case in cases for key in case[kind] if (kind, key) not in keys)
    keys = list(dict.fromkeys(keys))
    metadata = {(row["requirement_type"], row["requirement_id"]): row for row in old}
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writeheader()
        for kind, key in keys:
            selected = [case for case in cases if (case["threat"] == key if kind == "threat" else key in case[kind])]
            pending = sum(case["execution_status"] == "PENDING_SPEC" for case in selected)
            row = dict(metadata.get((kind, key), {"meaning": "仅用例追踪关系；实际覆盖需复核"}),
                       requirement_type=kind, requirement_id=key, case_ids=";".join(case["id"] for case in selected),
                       baseline_cases=len(selected) - pending, pending_cases=pending)
            writer.writerow(row)
    path = HERE / "run-results-template.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        old = {(row["case_id"], row["variant_id"], int(row["repeat_index"])): row for row in reader}
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writeheader()
        for case in cases:
            for index, parameter in enumerate(case["parameter_sets"] or ["默认参数"], 1):
                for repeat in range(1, case["repeats"] + 1):
                    variant = f"{case['id']}/v{index:02d}"
                    row = old.get((case["id"], variant, repeat))
                    if row is None:
                        row = {key: "" for key in fields}
                        row.update(case_id=case["id"], variant_id=variant, variant=parameter, repeat_index=repeat,
                                   priority=case["priority"], suite=case["suite"], test_level=case["test_level"], result="NOT_RUN")
                    writer.writerow(row)


if __name__ == "__main__":
    regenerate()
