"""Run the v05-platform/01 pytest evidence commands and write LF-only logs.

Repeatable with the project venv (from any directory):

    python .scratch/v05-platform/evidence/2026-10-21/capture_pytest_evidence.py

Writes pytest-api-audit.txt and pytest-mockbank.txt next to this script. Text files are
normalized to LF so the repository whitespace check stays clean on Windows.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
HERE = Path(__file__).resolve().parent

COMMANDS = (
    ("pytest-backend-full.txt", ["-m", "pytest", "-q"]),
    ("pytest-api-audit.txt", ["-m", "pytest", "app/api", "app/audit", "-q"]),
    ("pytest-mockbank.txt", ["-m", "pytest", "-q", "../evals/mockbank/test_mockbank_eval.py"]),
)


def main() -> int:
    for name, arguments in COMMANDS:
        completed = subprocess.run(
            [sys.executable, *arguments], cwd=BACKEND, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        output = (completed.stdout + completed.stderr).replace("\r\n", "\n")
        if not output.endswith("\n"):
            output += "\n"
        (HERE / name).write_text(output, encoding="utf-8", newline="\n")
        print(f"{name}: exit={completed.returncode}")
        if completed.returncode != 0:
            tail = "\n".join(output.splitlines()[-15:])
            print(tail)
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
