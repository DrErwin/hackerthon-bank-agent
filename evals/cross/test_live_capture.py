"""Offline tests of the observer only; never counted as live E2E evidence."""

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.contracts.bank import BankError, QueryFailure
from evals.cross.case_runner import create_case_app, prepare_case
from evals.cross.live_capture import Capture, observe
from evals.cross.test_case_runner import source  # shared isolated test configuration fixture


def test_capture_masks_known_credentials_and_provider_errors(tmp_path, source):
    directory = prepare_case(source, "XL-S01", "observer-redaction", workspace=tmp_path)
    recorder = Capture(directory)
    recorder.on_llm_error(ValueError("DO-NOT-PRINT-API-KEY"), run_id=uuid4())
    recorder.write("probe", credential="private-credential", content="DO-NOT-PRINT-API-KEY")
    text = recorder.path.read_text(encoding="utf-8")
    assert "DO-NOT-PRINT" not in text and "private-credential" not in text
    assert [json.loads(line)["kind"] for line in text.splitlines()] == ["model.error", "probe"]


def test_bank_observer_delegates_once_and_returns_original_result(tmp_path, source):
    directory = prepare_case(source, "XL-S01", "observer-delegation", workspace=tmp_path)
    app = create_case_app(directory, workspace=tmp_path)
    runtime = app.state.api.runtime
    expected = QueryFailure(kind="error", error=BankError(code="TEST_REFUSAL", details={}))
    calls = []
    def original(*args):
        calls.append(args)
        return expected
    runtime.gateway._bank.cancel_subscription = original
    observe(app, directory)
    operation = uuid4()
    actual = runtime.gateway._bank.cancel_subscription(None, operation, "sub_001")
    assert actual is expected
    assert calls == [(None, operation, "sub_001")]
    rows = [json.loads(line) for line in (directory / "observations.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["kind"] for row in rows] == ["capture.ready", "bank.write_request", "bank.write_response"]
    runtime.close()


def test_http_observer_preserves_response_without_logging_authentication(tmp_path, source):
    directory = prepare_case(source, "XL-S01", "observer-http", workspace=tmp_path)
    app = observe(create_case_app(directory, workspace=tmp_path), directory)
    with TestClient(app) as client:
        response = client.get("/not-a-business-endpoint", headers={"authorization": "Bearer secret-test-only"})
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}
    text = (directory / "observations.jsonl").read_text(encoding="utf-8")
    assert "secret-test-only" not in text and "Bearer" not in text
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[-1]["kind"] == "http.response" and rows[-1]["status"] == 404
