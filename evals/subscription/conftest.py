"""Bootstrap and fixtures for the scenario-05 evaluation suite.

Importing this checkout's ``backend`` first keeps the suite independent of whichever
editable install the interpreter has (the main checkout is installed editable into the
shared venv, so ``pytest evals/subscription`` from a worktree would otherwise import the
wrong ``app``).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for entry in (str(ROOT / "backend"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import pytest  # noqa: E402

from harness import composition, evidence_directory, write_evidence  # noqa: E402


@pytest.fixture
def subscription_runtime(tmp_path):
    """Assemble the real platform runtime; every assembly is closed at test end."""

    assembled = []

    def build(**options):
        runtime = composition(tmp_path, **options)
        assembled.append(runtime)
        return runtime

    yield build
    for runtime in assembled:
        runtime.close()


@pytest.fixture(scope="session")
def case_reports():
    """Where cases publish their structured assertions, and how they reach evidence."""

    store = {"reports": [], "outcomes": {}}
    yield store
    target = evidence_directory()
    if target is not None and store["reports"]:
        write_evidence(target, store["reports"], store["outcomes"],
                       commands=[[sys.executable, *sys.argv]])


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    store = item.funcargs.get("case_reports")
    if store is not None:
        store["outcomes"][item.nodeid] = "Passed" if report.passed else "Failed"


def pytest_configure(config):
    # Keep the case ids discoverable in the summary without extra markers.
    config.addinivalue_line("markers", "subscription_eval: scenario-05 golden case")
