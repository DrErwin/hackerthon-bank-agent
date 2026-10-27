"""Offline boundary checks; no provider request is made by these tests."""

import json
from types import SimpleNamespace

import httpx
import pytest

from classification_runner import (
    PROMPT, classify, load_cases, request_hooks, run_cases, sha256, summarize,
)


class Model:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(content=reply, usage_metadata={"input_tokens": 10, "output_tokens": 2},
                               response_metadata={"model_name": "offline-test"})


def test_exact_current_corpus_and_input_only_preserves_all_turns_and_channels():
    cases = load_cases()
    assert len(cases) == 96
    selected = next(case for case in cases if len(case["input"]["messages"]) > 1)
    for case in (selected, next(case for case in cases if case["input"]["untrusted_content"])):
        model = Model(['{"label":"risk"}'])
        assert classify(model, case)["prediction"] == "risk"
        assert model.messages == [[("system", PROMPT), ("human", json.dumps(case["input"], ensure_ascii=False, sort_keys=True))]]
        assert case["id"] not in model.messages[0][1][1]
        assert case["execution_status"] == "NOT_RUN"


@pytest.mark.parametrize("reply", ['```json\n{"label":"risk"}\n```', '{"label":"safe"}',
                                   '{"label":"risk","extra":"value"}', '[]', 'not json'])
def test_invalid_format_is_error_with_raw_sanitized_evidence(reply):
    row = classify(Model([reply]), load_cases()[0])
    assert row["prediction"] == "ERROR" and row["execution_status"] == "ERROR"
    assert row["response_content"] == reply
    assert row["response_sha256"] == sha256(reply)


def test_provider_error_never_persists_exception_text_and_raw_reply_is_redacted():
    case = load_cases()[0]
    row = classify(Model([RuntimeError("api_key: DO_NOT_SAVE_ME")]), case)
    assert row["prediction"] == "ERROR" and row["error_type"] == "RuntimeError"
    assert "DO_NOT_SAVE_ME" not in json.dumps(row)
    row = classify(Model(['{"label":"risk","leak":"SECRET_VALUE"}']), case, known_secrets=("SECRET_VALUE",))
    assert "SECRET_VALUE" not in json.dumps(row)
    assert row["prediction"] == "ERROR"


def test_quota_stops_without_retry_and_not_run_rows_remain_in_denominator(tmp_path):
    error = RuntimeError("must never be exported")
    error.status_code = 429
    cases = load_cases()[:3]
    model = Model(['{"label":"risk"}', error])
    output = tmp_path / "fresh.json"
    report = run_cases(model, cases, output, model_summary={"model": "offline-test"})
    assert len(model.messages) == 2
    assert report["stopped_reason"] == "rate_limit_429"
    assert report["summary"]["all"]["count"] == 3
    assert report["summary"]["all"]["errors"] == 1
    assert report["summary"]["all"]["not_run"] == 1
    assert len(output.with_suffix(".rows.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert json.loads(output.read_text(encoding="utf-8"))["run_status"] == "stopped"
    with pytest.raises(ValueError, match="FRESH_EXTERNAL_PATH"):
        run_cases(model, cases, output, model_summary={})
    assert len(model.messages) == 2


def test_http_audit_counts_actual_attempts_without_headers_or_secret_values():
    events = []
    body = {"model": "glm-5.3", "messages": [{"role": "system", "content": PROMPT},
                                             {"role": "user", "content": "test-input"}]}
    request = httpx.Request("POST", "https://eval.invalid/chat", json=body,
                            headers={"Authorization": "Bearer NEVER_STORE"})
    hooks = request_hooks(events)
    hooks["request"][0](request)
    hooks["response"][0](httpx.Response(200, request=request))
    assert len(events) == 1 and events[0]["http_status"] == 200
    assert events[0]["input_sha256"] == sha256("test-input")
    assert "NEVER_STORE" not in json.dumps(events)


def test_errors_and_not_run_do_not_disappear_from_metrics():
    rows = [{"split": "dev", "dimension": "fraud", "expected": "risk", "prediction": prediction}
            for prediction in ("benign", "unclear", "ERROR", "NOT_RUN")]
    summary = summarize(rows)["all"]
    assert (summary["count"], summary["risk_to_benign"], summary["risk_to_unclear"], summary["errors"], summary["not_run"]) == (4, 1, 1, 1, 1)
