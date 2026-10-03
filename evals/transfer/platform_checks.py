"""Current-checkout evidence for the two retired platform regression references."""

import os
from pathlib import Path
import subprocess
import sys

from environment import Environment
from plans import Plan


def run_platform_regressions(directory, revision):
    directory.mkdir(parents=True, exist_ok=True)
    case = {"id": "TF-INP-19", "scenario_id": "TF-INP-19"}
    env = Environment(directory / "blank-input", case, Plan())
    try:
        env.start("   ")
        env.check("platform.blank_rejected_before_model", env.message_response.status_code == 400 and not env.planner.records and env.task is None)
        env.zero()
        blank = {"id": "TF-INP-19", "status": "Passed" if all(a["passed"] for a in env.assertions) else "Failed",
                 "revision": revision, "layer": "real-HTTP-ASGI", "assertions": env.assertions,
                 "source": "app.api.app.send -> safe_text (before model/task dispatch)"}
    finally: env.close()
    root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=str(root / "backend"))
    command = [sys.executable, "-m", "pytest", "-q", "backend/app/agent_platform/test_harness.py::test_invalid_model_amount_does_not_start_a_bank_task"]
    completed = subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True)
    invalid = {"id": "TF-INP-20", "status": "Passed" if completed.returncode == 0 else "Failed",
               "revision": revision, "layer": "offline-model-output-validation", "command": command[2:],
               "exit_code": completed.returncode,
               "source": "backend/app/agent_platform/test_harness.py::test_invalid_model_amount_does_not_start_a_bank_task"}
    return [blank, invalid]
