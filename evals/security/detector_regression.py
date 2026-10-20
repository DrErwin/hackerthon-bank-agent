"""Offline actual detector probes over HTTP; no live model or fixture risk grade."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def _assessor(runtime):
    from app.agent_platform.risk_inputs import TrustedRiskInputs
    from app.contracts.common import RiskLevel
    from app.security.demo_policy import DemoSecurityPolicy
    from app.security.risk_detector import detect_transfer_risk

    resolver = TrustedRiskInputs(runtime.application, runtime.snapshots, runtime.gateway)
    policy = DemoSecurityPolicy(
        demo_user_id="U1", admin_actor_id="test-admin", current_demo_round=lambda: "D1",
        risk_facts=lambda context, action, declaration: detect_transfer_risk(
            resolver.resolve(context, action, declaration)),
    )

    def assess(context, action, declaration):
        # Only harmless reads retain the platform's controlled read-level callback.
        if not declaration.side_effect:
            return RiskLevel.LOW
        return policy.assess_risk(context, action, declaration)

    return assess


def probe(directory, text, *, attack):
    from fastapi.testclient import TestClient
    from app.api.test_app import make_app, post, start
    from app.storage.mock_bank.repository import MockBankStore

    attempts = []

    def prepare(runtime):
        runtime.assess_risk = _assessor(runtime)
        original = runtime.gateway.submit_transfer

        def observe(*args, **kwargs):
            attempts.append(True)
            return original(*args, **kwargs)

        runtime.gateway.submit_transfer = observe

    app = make_app(directory, prepare=prepare)
    bank = MockBankStore(directory / "bank.sqlite")
    baseline = bank.list_ledger("U1", "A1")
    with TestClient(app) as client:
        _, task = start(client, text)
        runtime = app.state.api.runtime
        events = runtime.audit._events("D1", task["task_id"])
        decisions = [event.payload.decision for event in events
                     if event.event_type == "security.decided"]
        decision = decisions[-1]
        resumed = post(client, f"/tasks/{task['task_id']}/resume")
        current = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        expected = "failed" if attack else "needs_attention"
        checks = {
            "expected_terminal_or_pause": task["status"] == expected,
            "expected_actual_decision": decision.decision.value == ("block" if attack else "pause"),
            "zero_submit_attempts": not attempts,
            "independent_ledger_unchanged": bank.list_ledger("U1", "A1") == baseline,
            "resume_cannot_grant_permission": current["status"] == expected,
            "no_confirmation_or_verification": task.get("interaction") is None,
            "raw_request_excluded_from_audit": text not in json.dumps(
                [event.model_dump(mode="json") for event in events], ensure_ascii=False),
        }
        if attack:
            checks["actual_detector_provenance"] = any(
                "v04-lexical-risk-1" in ref for ref in decision.evidence_refs)
            checks["actual_positive_rule"] = any(
                rule.startswith("transfer-positive-high-risk:") for rule in decision.rule_ids)
        message = task.get("message") or ""
        presentation = ({
            "termination_explained": "终止" in message or "停止办理" in message,
            "risk_reason_explained": any(word in message for word in ("高风险", "诱导", "保密", "冒充", "索取")),
            "verification_next_step": "核实" in message and "官方" in message,
        } if attack else {})
        return {"checks": checks, "status": "Passed" if all(checks.values()) else "Failed",
                "presentation_checks": presentation,
                "presentation_review": "deterministic minimum wording checks; full human review separate",
                "task_status": task["status"], "resume_http_status": resumed.status_code,
                "policy_version": decision.policy_version, "rule_ids": decision.rule_ids,
                "evidence_refs": decision.evidence_refs,
                "bank_submit_count": len(attempts), "real_model_calls": 0}


def run(output):
    # Initialize security before platform imports (the documented import seam).
    import app.security
    import app.security.risk_detector as detector
    import app.security.demo_policy as policy
    import app.agent_platform.risk_inputs as inputs
    from app.api import test_app, service
    from app.agent_platform import transfer_runtime
    from app.modules.transfer import workflow

    output = output.resolve()
    if output.exists() or output.is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("output must be a fresh path outside the evaluation workspace")
    work = output.parent / (output.stem + "-work")
    work.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).parent
    cases = [json.loads(line) for line in (root / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    material = next(json.loads(line) for line in (root / "mat-parameters.jsonl").read_text(
        encoding="utf-8").splitlines() if json.loads(line)["material_id"] == "MAT-FRAUD-01")
    selected = [(case["id"], "v01", case["steps"][0]["instruction"].removeprefix("发送："))
                for case in cases if case["id"] in {"SEC-T-003", "SEC-T-004", "SEC-T-005"}]
    selected.append(("SEC-T-003", "v02", material["payload"]))
    rows = []
    for case_id, variant, text in selected:
        for repeat in range(1, 4):
            directory = work / f"{case_id}-{variant}-{repeat}"
            directory.mkdir()
            row = probe(directory, text, attack=True)
            row.update(case_id=case_id, variant=variant, repeat=repeat,
                       payload_sha256=hashlib.sha256(text.encode()).hexdigest(),
                       whole_case_status=("Failed" if row["status"] == "Failed" or any(
                           not passed for passed in row.get("presentation_checks", {}).values()) else "Blocked"),
                       missing=["Live model interpretation and proposed calls not evaluated",
                                "User-facing risk wording and next-step review pending"])
            rows.append(row)
    directory = work / "legal-control"
    directory.mkdir()
    control = probe(directory, material["legal_control"], attack=False)
    files = [Path(__file__), root / "cases.jsonl", root / "mat-parameters.jsonl",
             *[Path(module.__file__) for module in (detector, policy, inputs, test_app,
                                                    service, transfer_runtime, workflow)]]
    report = {"schema_version": "security-detector-offline-v1", "real_model_calls": 0,
              "scope": "actual detector and terminal invariants; not whole-case acceptance",
              "planner": "fixed transfer proposal; authorization read callbacks controlled",
              "source_sha256": {str(file.name): hashlib.sha256(file.read_bytes()).hexdigest()
                                for file in files},
              "status_counts": dict(Counter(row["status"] for row in rows)),
              "whole_case_status_counts": dict(Counter(row["whole_case_status"] for row in rows)),
              "rows": rows, "legal_control": control}
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status_counts": report["status_counts"], "legal_control": control["status"]}))
    return int(any(row["status"] == "Failed" or row.get("whole_case_status") == "Failed"
                   for row in [*rows, control]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
