"""All 153 approved samples, including per-sample evidence and honest blockers."""

from pathlib import Path
from datetime import datetime, timezone
import subprocess

import pytest

from catalog import STANDARD_IDS, load_cases
from plans import plan_for
from runner import capture_metadata, run_case, write_report

CASES = load_cases()


@pytest.fixture(scope="session")
def evidence(request):
    root = Path(__file__).resolve().parents[2]
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    state = {"results": [], "platform": [], "revision": revision, "output": root / ".mnemon" / "transfer-evals" / datetime.now(timezone.utc).strftime("pytest-%Y%m%dT%H%M%S%fZ")}
    metadata = capture_metadata(revision)
    yield state
    state["results"].sort(key=lambda r: next(i for i, c in enumerate(CASES) if c["id"] == r["id"]))
    write_report(state["output"], state["results"], revision=revision, metadata=metadata,
                 config_summary={"mode": "live-glm" if request.config.getoption("--live-glm") else "offline-fixed-proposal"}, platform=state["platform"])


def test_platform_regressions(tmp_path, evidence):
    from platform_checks import run_platform_regressions
    evidence["platform"] = run_platform_regressions(tmp_path, evidence["revision"])
    assert all(r["status"] == "Passed" for r in evidence["platform"]), evidence["platform"]


def test_catalog_has_all_current_samples():
    assert len(CASES) == 153
    assert len({c["scenario_id"] for c in CASES}) == 151
    assert len({c["id"] for c in CASES}) == 153
    assert len(STANDARD_IDS) == 21
    assert {c["scenario_id"] for c in CASES if c["standard"]} == set(STANDARD_IDS)
    assert all(plan_for(c).variant for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_transfer_eval(case, tmp_path, request, evidence):
    delegate, blocker = None, None
    if request.config.getoption("--live-glm"):
        from run_live_eval import live_planner
        try: delegate, _ = live_planner(Path(request.config.getoption("--glm-config")))
        except Exception as exc: blocker = f"GLM dependency/config unavailable: {type(exc).__name__}"
    react = request.config.getoption("--react-dist")
    result = run_case(case, tmp_path, delegate, blocker, Path(react) if react else None, evidence["output"] / "browser")
    evidence["results"].append(result)
    if result["status"] == "Blocked": pytest.skip("Blocked: " + result["reason"])
    assert result["status"] == "Passed", {"status": result["status"], "assertions": result.get("failed_assertions"), "error_type": result.get("error_type")}
