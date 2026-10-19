"""Evidence/ID safeguards; these checks are not new banking business scenarios."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("bills_evidence_runner", HERE / "run_evidence.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def design_inputs():
    cases = json.loads((HERE / "fixtures/arithmetic-cases.json").read_text(encoding="utf-8"))["cases"]
    mapping = json.loads((HERE / "fixture_map.json").read_text(encoding="utf-8"))
    return [cases, mapping, *( (HERE / p).read_text(encoding="utf-8") for p in
                            ("representative-cases.md", "expanded-cases.md", "coverage-matrix.md"))]


def test_real_fixture_and_human_document_graph_has_no_dangling_ids():
    result = runner.validate_case_links(*design_inputs())
    assert result == {"core_designs": 21, "expanded_designs": 79, "overlap_designs": 4,
                      "unique_designs": 96, "golden_fixtures": 33, "partially_linked_designs": 24}


@pytest.mark.parametrize("defect", ["undefined", "missing_reverse", "missing_matrix", "duplicate_fixture", "map_mismatch"])
def test_broken_case_links_cannot_be_reported_as_complete(defect):
    args = deepcopy(design_inputs())
    if defect == "undefined":
        args[0][0]["case_ids"] = ["BILL-NOT-999"]
        args[1]["ARITH-01"] = ["BILL-NOT-999"]
    elif defect == "missing_reverse":
        args[3] = args[3].replace("ARITH-27", "REMOVED")
    elif defect == "missing_matrix":
        args[4] = args[4].replace("| ARITH-27 |", "| REMOVED |")
    elif defect == "duplicate_fixture":
        args[0].append(deepcopy(args[0][0]))
    else:
        args[1]["ARITH-01"] = ["BILL-002"]
    with pytest.raises(ValueError):
        runner.validate_case_links(*args)


def test_crlf_checkout_is_equivalent_but_spaces_or_code_changes_are_not():
    lf = b"amount = 1\nassert amount == 1\n"
    assert runner.fingerprints(lf) == runner.fingerprints(lf.replace(b"\n", b"\r\n"))
    assert runner.fingerprints(lf) != runner.fingerprints(lf.replace(b"= 1", b"= 2"))
    assert runner.fingerprints(lf) != runner.fingerprints(lf.replace(b"1\n", b"1 \n"))


@pytest.mark.parametrize("revision", ["main", "HEAD", "65d1a70", "g" * 40, "a" * 39])
def test_revision_must_be_exact_before_a_run(revision):
    with pytest.raises(ValueError, match="40-character"):
        runner.verify_sources(revision, None)


def source_tree(tmp_path, newline=b"\n"):
    files = {}
    for name in runner.SOURCE_PATHS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"exact pinned data" + newline)
        files[name] = runner.fingerprints(b"exact pinned data\n")
    manifest = tmp_path / "source-manifest.json"
    manifest.write_text(json.dumps({"tested_revision": "a" * 40,
                                   "repository": runner.REPOSITORY, "files": files}))
    return manifest


def test_source_verification_accepts_crlf_without_weakening_hash_check(tmp_path):
    manifest = source_tree(tmp_path, b"\r\n")
    mode, records = runner.verify_sources("a" * 40, manifest, root=tmp_path)
    assert mode == "connector_verified_file_slice"
    assert all(r["crlf_normalized"] for r in records.values())
    (tmp_path / runner.SOURCE_PATHS[0]).write_text("changed logic\n")
    with pytest.raises(ValueError, match="differ"):
        runner.verify_sources("a" * 40, manifest, root=tmp_path)


@pytest.mark.parametrize("field,value", [("tested_revision", "b" * 40), ("repository", "other/repository"), ("files", {})])
def test_wrong_manifest_provenance_is_rejected(tmp_path, field, value):
    path = source_tree(tmp_path)
    data = json.loads(path.read_text())
    data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="mismatch"):
        runner.verify_sources("a" * 40, path, root=tmp_path)


def test_each_record_is_timestamped_and_teardown_failure_cannot_pass():
    plugin = runner.EvidencePlugin({"ARITH-01": ["BILL-001"]})
    item = SimpleNamespace(nodeid="test_statistics_eval.py::test_arithmetic_golden[ARITH-01]",
                           callspec=SimpleNamespace(id="ARITH-01"))
    hook = plugin.pytest_runtest_protocol(item, None)
    next(hook)
    plugin.pytest_runtest_logreport(SimpleNamespace(nodeid=item.nodeid, when="call", outcome="passed", duration=.1, failed=False))
    plugin.pytest_runtest_logreport(SimpleNamespace(nodeid=item.nodeid, when="teardown", outcome="failed", duration=.1, failed=True, longrepr="teardown error"))
    with pytest.raises(StopIteration):
        next(hook)
    counts, records = plugin.results()
    assert counts["passed"] == 0 and counts["error"] == 1
    assert records[0]["started_at"] <= records[0]["finished_at"]
    assert records[0]["business_case_ids"] == ["BILL-001"]
