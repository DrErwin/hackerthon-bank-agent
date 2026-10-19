"""L02 integration with real Harness, scoped SQLite, security executor and B08.

The planner and LOW-risk policy are explicit test doubles. F10's real generic
option adapter is exercised; this is not live-model, HTTP or frontend evidence.
"""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agent_platform.harness import AgentHarness
from app.agent_platform.model import TransferProposal
from app.api.service import ApiService
from app.contracts.api import ProvideInputRequest
from app.contracts.bills import AnomalyResult, TransactionCandidates
from app.modules.bills.anomaly_entry import register_bills_anomalies
from app.modules.bills.test_public_integration import BANK_NOW, END, START, Environment, trusted


class AnomalyPlanner:
    provider = "scripted"
    model_name = "test-bills-L02"
    config_version = "test-l02-v1"

    def select(self, intent_text, context, catalog, memory, thread_id, context_summary=None):
        assert "bills.detect_anomalies" in {item["name"] for item in catalog}
        return TransferProposal(capability_name="bills.detect_anomalies")


@pytest.fixture
def env(tmp_path):
    result = Environment(tmp_path)
    result.now = BANK_NOW

    def advancing_clock():
        result.now += timedelta(microseconds=1)
        return result.now

    # Bank/entry share a live advancing demo clock, as in production assembly.
    result.gateway._bank.clock = advancing_clock
    register_bills_anomalies(result.registry, result.reads_factory, advancing_clock)
    result.harness = AgentHarness(result.application, result.memory, result.audit,
        result.registry, AnomalyPlanner(), lambda context, definition: result.valid_session(context))
    yield result
    result.close()


def payload(result, model=AnomalyResult):
    return model.model_validate(result.data.model_dump() if hasattr(result.data, "model_dump") else result.data)


def f10(result, index=0):
    request = ProvideInputRequest(request_id=uuid4(), interaction_id=result.interaction.interaction_id,
                                  selected_option_id=result.interaction.options[index].id)
    # No payee-search records for a bills input. All option validation and
    # conversion below is the production F10 implementation, not a copied map.
    adapter = SimpleNamespace(store=SimpleNamespace(rows=lambda *_: []))
    # Current F10 adapter receives the type-shaped task view, not separate
    # task_id/interaction positional arguments (subscription API update).
    task = SimpleNamespace(task_id=result.task_id, module="bills", interaction=result.interaction)
    return ApiService.input_response(adapter, task, request)


def test_real_candidate_f10_and_single_recheck_survive_advancing_bank_clock(env):
    balances = env.balances()
    request_id = uuid4()
    first = env.harness.start(trusted(), request_id, "核对交易，2026年9月所有账户")
    assert first.status == "waiting_input", first
    candidates = payload(first, TransactionCandidates)
    assert len(candidates.candidates) > 1
    reads_before = len(env.gateway.reads)
    # Replayed start returns the original interaction and never repeats reads.
    replay = env.harness.start(trusted(), request_id, "核对交易，2026年9月所有账户")
    assert replay.interaction == first.interaction and len(env.gateway.reads) == reads_before
    selected = candidates.candidates[1]
    response = f10(first, 1)
    assert response == {"choice": first.interaction.options[1].id}
    result = env.harness.resume(trusted(run="R2"), response)
    assert result.status == "succeeded", result
    assert result.task_id == "T1" and payload(result).transaction == selected
    assert [check.rule_id for check in payload(result).checks] == [1, 2, 3, 4]
    assert payload(result).as_of <= env.now
    new_ranges = [call for call in env.gateway.reads[reads_before:] if call[0] == "transactions"]
    assert new_ranges[0][2:] == (selected.account_id, START, END)
    assert len(new_ranges) == 2  # selected scope, then baseline; no moving 24-month lookup
    assert env.gateway.bank_writes == 0 and env.balances() == balances
    task = env.application.get_task("U1", "D1", "T1")
    assert task.snapshot["capability_name"] == "bills.detect_anomalies" and task.checkpoint_id


def test_candidate_selection_rechecks_real_security_before_another_bank_read(env):
    first = env.harness.start(trusted(), uuid4(), "核对交易，2026年9月所有账户")
    assert first.status == "waiting_input"
    count = len(env.gateway.reads)
    env.permission = False
    result = env.harness.resume(trusted(run="R2"), f10(first))
    assert result.status == "failed" and result.error.source == "security"
    assert result.data is None and len(env.gateway.reads) == count
    assert env.gateway.bank_writes == 0 and any(decision.decision == "block" for decision in env.decisions)


def test_real_cross_session_recovery_requeries_candidates_in_original_task(env):
    first = env.harness.start(trusted(), uuid4(), "核对交易，2026年9月所有账户")
    old_options = {option.id for option in first.interaction.options}
    env.session("S2")
    moved = env.harness.recover_session(trusted(session="S2", run="R2"))
    assert moved.status == "waiting_input" and moved.task_id == "T1"
    assert not old_options & {option.id for option in moved.interaction.options}
    count = len(env.gateway.reads)
    result = env.harness.resume(trusted(session="S2", run="R3"), f10(moved))
    assert result.status == "waiting_input" and len(env.gateway.reads) > count
    assert payload(result, TransactionCandidates).scope.start_at == START
    assert not old_options & {option.id for option in result.interaction.options}
    result = env.harness.resume(trusted(session="S2", run="R4"), f10(result))
    assert result.status == "succeeded" and result.task_id == "T1" and env.gateway.bank_writes == 0


def test_real_scan_is_rule4_only_and_has_no_banking_side_effects(env):
    balances = env.balances()
    result = env.harness.start(trusted(), uuid4(), "所有账户最近三个完整月份检查周期扣款")
    assert result.status == "succeeded", result
    data = payload(result)
    assert data.transaction is None and [check.rule_id for check in data.checks] == [4]
    assert all(finding.rule_id == 4 for finding in data.findings)
    assert env.gateway.bank_writes == 0 and env.balances() == balances
