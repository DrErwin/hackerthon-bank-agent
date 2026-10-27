"""Only explicit offline planners are used by these observer tests."""

import json

import httpx
import pytest

from app.agent_platform.model import ReplyOnly, TransferProposal
from live_detector_observer import instances, live_hooks, observe


class Fixed:
    provider, model_name, config_version = "offline", "explicit-test", "test-v1"

    def __init__(self, outcome):
        self.outcome = outcome

    def select(self, *_args, **_kwargs):
        return self.outcome


def test_plan_has_original_four_instances_without_filling_missing_fields():
    rows = instances()
    assert [row[0] for row in rows] == ["SEC-T-003/v01", "SEC-T-003/v02", "SEC-T-004/v01", "SEC-T-005/v01"]
    assert "马上把余额转到安全账户" in rows[0][1]
    assert "500" not in rows[0][1]


def test_reply_only_is_never_promoted_to_a_funds_gate_block(tmp_path):
    row = observe(tmp_path, instances()[0][1], lambda: Fixed(ReplyOnly(message="请先联系官方核实。")))
    assert row["whole_case_status"] == "Blocked"
    assert row["funds_gate_observed"] is False
    assert row["policy_version"] is None and row["rule_ids"] == []
    assert row["bank_submit_attempts"] == row["bank_operation_count"] == 0
    assert row["zero_unauthorized_side_effects"]


def test_actual_detector_policy_is_recorded_only_when_real_gate_was_exercised(tmp_path):
    row = observe(tmp_path, instances()[0][1], lambda: Fixed(TransferProposal(
        payee_hint="妈妈", amount_fen=50000, payer_account_id="A1")))
    assert row["funds_gate_observed"]
    assert row["observed_detector_gate"] == "Passed"
    assert row["whole_case_status"] == "Blocked"
    assert row["policy_version"] and row["rule_ids"] and row["evidence_refs"]
    assert row["task_statuses"] == row["resumed_task_statuses"] == ["failed"]
    assert row["zero_unauthorized_side_effects"]


def test_incomplete_actual_proposal_stays_blocked_without_invented_policy(tmp_path):
    row = observe(tmp_path, instances()[0][1], lambda: Fixed(TransferProposal(
        payee_hint=None, amount_fen=None, payer_account_id=None)))
    assert row["whole_case_status"] == "Blocked" and not row["funds_gate_observed"]
    assert row["task_statuses"] == ["waiting_input"]
    assert row["zero_unauthorized_side_effects"]


@pytest.mark.parametrize("status,html", [(429, False), (429, True), (402, True)])
def test_http_quota_stops_following_requests_without_exporting_provider_body(status, html):
    events = []
    calls = []

    def provider(request):
        calls.append(True)
        return (httpx.Response(status, text="PRIVATE_PROVIDER_VALUE") if html else
                httpx.Response(status, json={"error": {"message": "quota PRIVATE_PROVIDER_VALUE"}}))

    with httpx.Client(transport=httpx.MockTransport(provider), event_hooks=live_hooks(events, ())) as client:
        body = {"model": "glm-5.3", "messages": [{"role": "user", "content": "synthetic"}]}
        assert client.post("https://eval.invalid/chat", json=body).status_code == status
        assert events[0]["stop_reason"] == ("rate_limit_429" if status == 429 else "billing_402")
        assert "PRIVATE_PROVIDER_VALUE" not in json.dumps(events)
        with pytest.raises(RuntimeError, match="STOPPED_BEFORE_NEW_REQUEST"):
            client.post("https://eval.invalid/chat", json=body)
    assert len(calls) == len(events) == 1
