"""Repeat-first-start stability sample for scenario 05 (rerunnable observation).

Ticket 05's review saw an intermittent first-start failure (~3/60, ending in
``SUBSCRIPTION_INTERNAL_ERROR``). This tool reproduces that observation at scale on one
assembly: it starts ``--attempts`` fresh tasks and records every failure with its code,
message and audit/decision context, so the sample can be compared before and after a
platform fix instead of being retold from memory.

    python evals/subscription/stability_sample.py --attempts 100 --label pre-fix \
        --out evals/subscription/evidence/2026-10-19/stability-pre-fix.json

Like ``conftest.py`` this puts *this checkout's* ``backend`` first on ``sys.path``: the
shared venv has the main checkout installed editable, so running without it would
silently sample whichever code the interpreter happens to resolve, not this tree.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for entry in (str(ROOT / "backend"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import harness  # noqa: E402  (path bootstrap above)


def sample(attempts: int, *, capability: str, intent: str, tmp_root: Path) -> dict:
    started_at = datetime.now(timezone.utc)
    composition = harness.composition(tmp_root)
    failures: list[dict] = []
    statuses: dict[str, int] = {}
    try:
        for index in range(1, attempts + 1):
            task_id = f"T{index:04d}"
            run_id = f"R{index:04d}"
            try:
                result = harness.start(composition, intent, task=task_id, run=run_id,
                                       capability=capability)
                code = result.error.code if result.error is not None else None
                statuses[result.status.value] = statuses.get(result.status.value, 0) + 1
                if result.status.value == "failed" or code == "SUBSCRIPTION_INTERNAL_ERROR":
                    failures.append({
                        "attempt": index, "task_id": task_id,
                        "status": result.status.value, "error_code": code,
                        "message": result.message, "upstream_code": (
                            result.error.upstream_code if result.error else None),
                        "decisions": _decision_trace(composition, task_id),
                    })
            except Exception as error:  # a raised failure is a failure of the sample too
                statuses["raised"] = statuses.get("raised", 0) + 1
                failures.append({
                    "attempt": index, "task_id": task_id, "status": "raised",
                    "error_code": type(error).__name__, "message": str(error),
                    "decisions": _decision_trace(composition, task_id),
                })
    finally:
        composition.close()
    return {
        "tool": "stability_sample",
        "label": None,
        "capability": capability,
        "intent": intent,
        "attempts": attempts,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "statuses": statuses,
        "failure_count": len(failures),
        "failures": failures,
        # Which checkout was sampled: a sample that quietly measured another tree is
        # worthless, so the resolved package path travels with the numbers.
        "app_file": harness.app_file(),
    }


def _decision_trace(composition, task_id: str, limit: int = 4) -> list[dict]:
    """The gate decisions of that task: the platform's own account of the failure."""

    trace: list[dict] = []
    try:
        for event in harness.events(composition, task_id):
            if event.event_type != "security.decided":
                continue
            decision = event.payload.decision
            trace.append({
                "action_name": decision.action_name,
                "phase": decision.phase.value,
                "decision": decision.decision.value,
                "reason_codes": list(decision.reason_codes),
                "join": f"{decision.parameters_ref}#{decision.action_revision}",
            })
    except Exception as error:
        trace.append({"trace_error": type(error).__name__})
    return trace[-limit:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempts", type=int, default=100)
    parser.add_argument("--capability", default=harness.LIST_CAPABILITY,
                        choices=[harness.LIST_CAPABILITY, harness.CANCEL_CAPABILITY])
    parser.add_argument("--intent", default="帮我查查有哪些自动扣费")
    parser.add_argument("--label", default="unspecified")
    parser.add_argument("--out", required=True)
    parser.add_argument("--workdir", default=None)
    arguments = parser.parse_args()

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(arguments.workdir or temporary)
        report = sample(arguments.attempts, capability=arguments.capability,
                        intent=arguments.intent, tmp_root=root)
    report["label"] = arguments.label
    out = Path(arguments.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": arguments.label, "attempts": arguments.attempts,
                      "statuses": report["statuses"],
                      "failure_count": report["failure_count"],
                      "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
