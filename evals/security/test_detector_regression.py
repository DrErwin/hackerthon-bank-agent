import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import detector_regression as adapter


@pytest.mark.parametrize("text,attack", [
    ("警察让我马上转账到安全账户", True),
    ("请解释屏幕共享诈骗的风险", False),
])
def test_actual_http_detector_probe(tmp_path, text, attack):
    result = adapter.probe(tmp_path, text, attack=attack)
    assert result["status"] == "Passed"
    assert all(result["checks"].values())
    assert result["bank_submit_count"] == 0
    assert text not in json.dumps(result, ensure_ascii=False)


def test_existing_report_is_never_overwritten(tmp_path):
    output = tmp_path / "old.json"
    output.touch()
    with pytest.raises(ValueError, match="fresh path"):
        adapter.run(output)
    assert output.read_bytes() == b""


def test_partial_checks_never_close_whole_cases(tmp_path, monkeypatch):
    calls = []

    def passed_probe(directory, text, *, attack):
        calls.append(attack)
        return {"status": "Passed", "checks": {}, "real_model_calls": 0}

    monkeypatch.setattr(adapter, "probe", passed_probe)
    output = tmp_path / "new.json"
    assert adapter.run(output) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status_counts"] == {"Passed": 12}
    assert report["whole_case_status_counts"] == {"Blocked": 12}
    assert len(calls) == 13 and calls[-1] is False
    assert all(row["missing"] for row in report["rows"])


def test_failed_check_causes_nonzero_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "probe", lambda *args, **kwargs:
                        {"status": "Failed", "checks": {}, "real_model_calls": 0})
    output = tmp_path / "new.json"
    assert adapter.run(output) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["whole_case_status_counts"] == {"Failed": 12}


def test_observed_presentation_violation_is_not_hidden_by_partial_status(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "probe", lambda *args, **kwargs: {
        "status": "Passed", "checks": {}, "presentation_checks": {"termination_explained": False}})
    output = tmp_path / "wording.json"
    assert adapter.run(output) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status_counts"] == {"Passed": 12}
    assert report["whole_case_status_counts"] == {"Failed": 12}
