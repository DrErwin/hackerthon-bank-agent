"""Observe Issue145 without exporting bank values or mutating business code."""

import argparse
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4


def minimal_read_evidence(event_type, value):
    if not isinstance(value, dict) or not value:
        return False
    if event_type == "tool.started":
        digest = value.get("parameters_sha256")
        # The shared redactor can mask a digit run within a hex digest. This
        # check proves restricted scalar content, not exact digest fidelity.
        return (set(value) == {"parameters_sha256"} and isinstance(digest, str)
                and re.fullmatch(r"[0-9a-f*]{32,64}", digest) is not None)
    required = {"result_ref", "status", "row_count"}
    reference, count = value.get("result_ref"), value.get("row_count")
    return (required <= set(value) <= required | {"code"}
            and isinstance(reference, str)
            and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", reference) is not None
            and value["status"] in ("succeeded", "failed")
            and (count is None or type(count) is int and count >= 0)
            and ("code" not in value or isinstance(value["code"], str)
                 and re.fullmatch(r"[A-Z_]{4,64}", value["code"]) is not None))


def probe(directory):
    from app.audit.journal import AuditReader, AuditViewer
    from app.modules.bills import reads as source
    from app.modules.bills.test_public_integration import Environment, trusted
    from public_boundary_adapter import funds_snapshot

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    env = Environment(directory)
    try:
        before = funds_snapshot(directory)
        result = env.harness.start(trusted(), uuid4(), "2026年9月所有账户账单")
        reader = AuditReader(env.audit, authorize=lambda viewer, *_: viewer.actor_id == "test-admin")
        rows = reader.timeline(AuditViewer("test-admin", "ADMIN-S", "D1"), "D1", "T1")
        observations = []
        for event in rows:
            if event.module != "bills" or event.event_type not in {"tool.started", "tool.finished"}:
                continue
            if event.event_type == "tool.started" and not event.payload.tool_name.startswith("bills.bank."):
                continue
            value = json.loads(event.evidence) if event.evidence else None
            observations.append({"event_type": event.event_type,
                "minimum_only": minimal_read_evidence(event.event_type, value),
                "has_evidence": value is not None})
        checks = {"query_still_succeeds": result.status == "succeeded",
                  "bank_unchanged": funds_snapshot(directory) == before,
                  "actual_read_events_observed": bool(observations),
                  "bank_facts_not_in_audit": bool(observations) and all(
                      item["minimum_only"] for item in observations)}
        return {"schema_version": "bills-audit-boundary-v1", "issue": 145,
                "status": "Passed" if all(checks.values()) else "Failed",
                "checks": checks, "read_events": observations, "real_model_calls": 0,
                "source_sha256": hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
                "digest_fidelity": "not attested; shared redaction may mask hex digit runs",
                "fixture": "fixed L01 planner and scoped read policy; real harness/audit/bank"}
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("report requires a fresh path outside the repository")
    result = probe(output.parent / (output.stem + "-work"))
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "issue": 145}))
    return int(result["status"] == "Failed")


if __name__ == "__main__":
    raise SystemExit(main())
