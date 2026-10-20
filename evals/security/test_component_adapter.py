import ast
from pathlib import Path
from types import SimpleNamespace

from component_adapter import BINDINGS, ROOT, SafeCollector
from security_runner import load_security_catalog, run_instance


def test_every_registered_component_target_exists():
    known = {case["id"] for case in load_security_catalog().cases}
    assert set(BINDINGS) <= known
    for targets in BINDINGS.values():
        for target in targets:
            path, function = target.split("::", 1)
            tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
            assert function in {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}, target


def test_parameterized_credentials_are_never_exported_and_teardown_failure_wins():
    collector = SafeCollector()
    value = dict(nodeid="file.py::test_fake[verification-code-secret]", skipped=False)
    collector.pytest_runtest_logreport(SimpleNamespace(**value, when="call", passed=True, failed=False))
    collector.pytest_runtest_logreport(SimpleNamespace(**value, when="teardown", passed=False, failed=True))
    assert list(collector.results.values()) == ["Failed"]
    assert all("secret" not in key and "verification" not in key for key in collector.results)


def test_component_execution_is_real_but_does_not_claim_whole_scenario_pass(tmp_path):
    case = next(case for case in load_security_catalog().cases if case["id"] == "SEC-D-006")
    result = run_instance(case, tmp_path / "component")
    assert result["evidence"]["adapter"] == "component-observations-v1"
    assert result["observed_assertion_status"] == "Passed"
    assert result["status"] == "Blocked"
    assert result["evidence"]["original_stimulus_delivered"] is False
    assert result["evidence"]["component_results"]["results"]


def test_termination_component_is_not_assigned_to_expired_session_variant(tmp_path):
    case = next(case for case in load_security_catalog().cases if case["id"] == "SEC-E-003")
    result = run_instance(case, tmp_path / "not-substituted", 1)
    assert result["status"] == "Blocked" and result["assertions"] == []
    assert not (tmp_path / "not-substituted").exists()
    assert result["evidence"]["original_stimulus_delivered"] is False
