"""The transfer suite imports this checkout rather than another editable install."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def pytest_addoption(parser):
    parser.addoption("--live-glm", action="store_true", help="Use configured real GLM, without offline fallback")
    parser.addoption("--glm-config", default=str(ROOT / ".env.local-demo.json"))
    parser.addoption("--react-dist", default=None, help="Existing real-api React build for browser cases")
