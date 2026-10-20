import pytest
from bills_audit_probe import minimal_read_evidence, probe


def test_audit_probe_exposes_the_registered_mainline_gap(tmp_path):
    # This tests the evaluator's oracle, not a product pass. Mainline findings
    # are adjudicated from the actual checkout; provider fixes may pass here.
    result = probe(tmp_path / "audit")
    assert result["checks"]["query_still_succeeds"]
    assert result["checks"]["bank_unchanged"]
    assert result["read_events"]
    assert result["status"] == ("Passed" if result["checks"]["bank_facts_not_in_audit"] else "Failed")
    assert all(set(row) == {"event_type", "minimum_only", "has_evidence"}
               for row in result["read_events"])


@pytest.mark.parametrize("event_type,value", [
    ("tool.started", {}), ("tool.finished", {}),
    ("tool.started", {"parameters_sha256": {"counterparty_name": "合成值"}}),
    ("tool.started", {"parameters_sha256": "合成银行事实"}),
    ("tool.finished", {"result_ref": {"available_balance_fen": 12345}}),
    ("tool.finished", {"result_ref": "12345", "status": "succeeded", "row_count": 1}),
    ("tool.finished", {"result_ref": "10000000-0000-0000-0000-000000000000", "status": "succeeded", "row_count": True}),
])
def test_audit_oracle_rejects_empty_nested_or_wrong_typed_evidence(event_type, value):
    assert not minimal_read_evidence(event_type, value)


def test_audit_oracle_accepts_minimum_scalars_without_claiming_digest_fidelity():
    assert minimal_read_evidence("tool.started", {"parameters_sha256": "a" * 64})
    assert minimal_read_evidence("tool.started", {"parameters_sha256": "b" * 24 + "****" + "c" * 28})
    assert minimal_read_evidence("tool.finished", {
        "result_ref": "10000000-0000-0000-0000-000000000000", "status": "succeeded", "row_count": 0})
