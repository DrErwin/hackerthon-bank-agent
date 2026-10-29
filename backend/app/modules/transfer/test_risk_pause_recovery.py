"""Unsubmitted risk coverage pauses retain a usable owned draft, never funds authority."""

import pytest

from app.contracts.common import SecurityDecisionCode, TaskStatus
from app.security import ExecutionOutcome

from .test_workflow import Ports, request, trusted, workflow


class CoveragePorts(Ports):
    """A declared risk-decision substitute; the real workflow owns every transition."""

    def __init__(self):
        super().__init__()
        self.payer = None
        self.approved_operations = set()
        self.checked_operations = []

    def prepare_transfer(self, owner, operation_id, revision, payer, payee, amount):
        self.payer = payer
        return super().prepare_transfer(owner, operation_id, revision, payer, payee, amount)

    def check(self, _trusted, action):
        self.checked_operations.append(action.operation_id)
        if self.payer == "A5":
            return self.decision(action, SecurityDecisionCode.PAUSE).model_copy(update={
                "reason_codes": ["DEPENDENCY_UNAVAILABLE"],
                "rule_ids": ["risk-signal-coverage-required"],
                "interaction": None,
            })
        return self.decision(action, SecurityDecisionCode.ALLOW if action.operation_id
                             in self.approved_operations else SecurityDecisionCode.REQUIRE_CONFIRMATION)


def paused_after_card_change():
    flow, ports = workflow(CoveragePorts())
    original = flow.start(trusted(), request())
    ports.approved_operations.add(original.data.operation_id)
    paused = flow.resume(trusted(), {"fields": {"payer_account_id": "A5"}})
    return flow, ports, original, paused


def assert_editable_pause(result):
    assert result.status == TaskStatus.WAITING_INPUT
    assert result.allowed_actions == ["provide_input", "cancel"]
    assert not result.recovery_required
    assert result.interaction.kind == "input"
    assert {option.id for option in result.interaction.options} == {"resume", "cancel"}
    assert result.error.code == "DEPENDENCY_UNAVAILABLE"
    assert result.data.payer_account_id == "A5"
    assert result.data.amount_fen == 10_000
    assert result.data.payee.remark == "邻居"
    assert result.data.operation is None


def test_pre_submission_coverage_pause_can_recheck_and_cancel_original_task():
    flow, ports, original, paused = paused_after_card_change()
    assert_editable_pause(paused)
    assert paused.task_id == original.task_id
    assert paused.data.operation_id != original.data.operation_id
    assert ports.submissions == 0
    rechecked = flow.resume(trusted(), {"choice": "resume"})
    assert_editable_pause(rechecked)
    assert rechecked.data.operation_id == paused.data.operation_id
    assert ports.submissions == 0
    cancelled = flow.resume(trusted(), {"choice": "cancel"})
    assert cancelled.status == TaskStatus.CANCELLED
    assert cancelled.task_id == original.task_id
    assert cancelled.data.operation_id == paused.data.operation_id
    assert ports.submissions == 0


def test_pre_submission_coverage_pause_can_change_card_with_new_confirmation():
    flow, ports, original, paused = paused_after_card_change()
    assert_editable_pause(paused)
    reads_before = ports.read_calls.count("bank.precheck_transfer")
    changed = flow.resume(trusted(), {"fields": {"payer_account_id": "A1"}})
    assert changed.task_id == original.task_id
    assert changed.status == TaskStatus.WAITING_APPROVAL
    assert changed.data.payer_account_id == "A1"
    assert changed.data.amount_fen == original.data.amount_fen
    assert changed.data.payee == original.data.payee
    assert changed.data.operation_id not in {original.data.operation_id, paused.data.operation_id}
    assert ports.action.action_revision == 3
    assert ports.read_calls.count("bank.precheck_transfer") == reads_before + 1
    assert changed.allowed_actions == ["confirm", "cancel"]
    assert not changed.recovery_required and changed.error is None
    assert changed.interaction.kind == "confirmation"
    assert ports.submissions == 0
    still_unapproved = flow.resume(trusted(), {"choice": "approve"})
    assert still_unapproved.status == TaskStatus.WAITING_APPROVAL
    assert ports.submissions == 0


@pytest.mark.parametrize("reused", [False, True])
def test_same_coverage_pause_from_execute_is_not_editable(reused):
    class ExecutePausePorts(CoveragePorts):
        def execute(self, owner, action):
            pause = self.decision(action, SecurityDecisionCode.PAUSE).model_copy(update={
                "reason_codes": ["DEPENDENCY_UNAVAILABLE"],
                "rule_ids": ["risk-signal-coverage-required"],
                "interaction": None,
            })
            return ExecutionOutcome(pause, False, reused, "unknown" if reused else "not_started", None, None)

    flow, ports = workflow(ExecutePausePorts())
    original = flow.start(trusted(), request())
    ports.approved_operations.add(original.data.operation_id)
    paused = flow.resume(trusted(), {"choice": "approve"})
    assert paused.status == TaskStatus.NEEDS_ATTENTION
    assert paused.recovery_required and paused.allowed_actions == []
    unchanged = flow.resume(trusted(), {"fields": {"payer_account_id": "A5"}})
    assert unchanged.data == paused.data and unchanged.status == paused.status
    assert ports.submissions == 0


@pytest.mark.parametrize("rule", ["trusted-scope-required", "trusted-task-state-required"])
def test_authority_dependency_pause_is_not_editable(rule):
    class AuthorityPausePorts(Ports):
        def check(self, owner, action):
            return self.decision(action, SecurityDecisionCode.PAUSE).model_copy(update={
                "reason_codes": ["DEPENDENCY_UNAVAILABLE"], "rule_ids": [rule], "interaction": None,
            })

    flow, ports = workflow(AuthorityPausePorts())
    paused = flow.start(trusted(), request())
    assert paused.status == TaskStatus.NEEDS_ATTENTION
    assert paused.recovery_required and paused.allowed_actions == []
    assert ports.submissions == 0


def test_unknown_bank_result_keeps_original_operation_and_query_only():
    flow, ports = workflow()
    original = flow.start(trusted(), request())
    ports.approved = True
    ports.processing = True
    unknown = flow.resume(trusted(), {"choice": "approve"})
    assert unknown.recovery_reason == "OPERATION_UNKNOWN"
    assert unknown.allowed_actions == ["query"] and ports.submissions == 1
    unchanged = flow.resume(trusted(), {"fields": {"payer_account_id": "A5"}})
    assert unchanged.data.payer_account_id == "A1"
    assert unchanged.data.operation_id == original.data.operation_id
    assert unchanged.allowed_actions == ["query"] and ports.submissions == 1
