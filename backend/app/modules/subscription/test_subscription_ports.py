"""The write path against the real security gate and the shared executor.

The module's own unit tests inject a gate double; these tests keep ``reads.py`` honest
with the production pieces: a real ``SecurityGate`` + ``DeterministicExecutor``, a
confirmation the user answers, a session-scoped verification, and a bank gateway double.
Scope and risk stay minimal doubles here — the demo policy that owns them is covered by
its own ticket. These tests are the regression that fails if the action phase, the frozen
parameter reference, the context hand-off or the replay result mapping regress.
"""

from __future__ import annotations

from datetime import timedelta
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.contracts.bank import (
    BankError, OperationFound, OperationNotFound, OperationResult, QueryFailure, QueryOk,
)
from app.contracts.common import DisplayField, RiskLevel, TaskStatus
from app.contracts.security import ConfirmationAnswer, ExecutionSecurityContext, VerificationChallenge, VerificationRecord
from app.contracts.subscription import SubscriptionCancelReceipt
from app.modules.subscription.entry import SubscriptionEntry
from app.modules.subscription.ports import RISK_OBSERVATIONS  # noqa: F401  (documents the payload field)
from app.modules.subscription.reads import PRIVATE_TOOLS, GatewaySubscriptionPorts
from app.modules.subscription.service import _MESSAGES, SubscriptionService
from app.modules.subscription.test_subscription import (
    NOW, FakeBank, MemorySaver, Ports, at, context, start_request,
)
from app.security import ConfirmationService, SecurityGate, ToolRegistry


DECLARED = {item.name for item in PRIVATE_TOOLS}
DEMO_USER, DEMO_ROUND = "U1", "D1"


class FakeGateway:
    """Only the bank calls this module actually makes; it never touches storage."""

    def __init__(self, bank: FakeBank):
        self.bank, self.cancels, self.operations = bank, 0, {}

    def list_accounts(self, trusted):
        return self.bank.accounts(trusted)

    def list_subscriptions(self, trusted, account_id=None, status=None):
        return self.bank.mandates_for(trusted, account_id, status)

    def list_transactions(self, trusted, account_id, start_at, end_at):
        return self.bank.transactions(trusted, account_id, start_at, end_at)

    def cancel_subscription(self, trusted, operation_id, mandate_id):
        self.cancels += 1
        result = self.bank.cancel(trusted, operation_id, mandate_id)
        if isinstance(result, OperationResult):
            self.operations[str(operation_id)] = result
        return result

    def get_operation(self, trusted, operation_id):
        result = self.operations.get(str(operation_id))
        if result is None:
            return OperationNotFound(lookup="not_found", operation=None)
        return OperationFound[SubscriptionCancelReceipt](lookup="found", operation=result)


class Trace:
    def __init__(self):
        self.events = []
        self.evidence_ids = []

    def record(self, event_type, payload, outcome, **kwargs):
        self.events.append((event_type, outcome))
        if kwargs.get("evidence_id"):
            # ``audit_evidence.evidence_id`` is unique: a deterministic parameter
            # reference must never be reused as an evidence key.
            self.evidence_ids.append(kwargs["evidence_id"])
        return SimpleNamespace(span_id=f"S{len(self.events)}")


class Harness:
    """A task-scoped gate, its ports and the mutable security state they share."""

    def __init__(self, tmp_path, *, allow_scope=True, db="subscription.sqlite3",
                 gateway_factory=None):
        self.bank = FakeBank()
        self.gateway = (gateway_factory or FakeGateway)(self.bank)
        self.trace = Trace()
        self.state = {"answered": None, "challenges": [], "records": {}, "verification_ids": [],
                      "operation_id": None, "operations": {}, "refs": [], "payloads": []}
        self.confirmations = ConfirmationService(tmp_path / db, clock=lambda: NOW)
        self.ports = GatewaySubscriptionPorts(
            self.gateway, self._build_gate(allow_scope), self._context_factory,
            self.trace, operation_reserver=self._reserve, on_bind=self._on_bind)

    # -- gate wiring -------------------------------------------------------------
    # Scope and risk decisions stay minimal here: the demo policy that owns them is
    # covered by its own ticket, these tests are about the gate/executor hand-off.

    @staticmethod
    def _scope(context, action, declaration):
        return (declaration.name in DECLARED and action.action_name == declaration.name
                and context.user_id == DEMO_USER and context.demo_round_id == DEMO_ROUND)

    def _build_gate(self, allow_scope):
        def prepare_confirmation(context, action):
            payload = self.ports.resolve(context, action)
            return self.confirmations.create(context, action, [
                DisplayField.model_validate(field) for field in payload["display_fields"]])

        def prepare_verification(context, action, confirmation, risk):
            step_up = risk != RiskLevel.LOW
            challenge = VerificationChallenge(
                challenge_id=f"CH-{len(self.state['challenges']) + 1}", user_id=context.user_id,
                session_id=context.session_id, demo_round_id=context.demo_round_id,
                task_id=context.task_id,
                purpose="action_step_up" if step_up else "basic_identity",
                operation_id=context.operation_id if step_up else None,
                action_revision=context.action_revision if step_up else None, summary=None,
                required_methods=["code", "mock_face"] if step_up else ["code"],
                created_at=NOW, code_created_at=NOW, code_expires_at=NOW + timedelta(minutes=5),
                face_started_at=None, face_expires_at=None, challenge_status="pending",
                code_result="pending", face_result="pending" if step_up else "not_required",
                consecutive_code_failures=0)
            self.state["challenges"].append(challenge)
            return challenge

        return SecurityGate(
            ToolRegistry(), self.confirmations,
            scope_authorizer=(self._scope if allow_scope else lambda *_: False),
            task_state_resolver=lambda *_: False,
            risk_assessor=lambda *_: RiskLevel.LOW,
            confirmation_preparer=prepare_confirmation, verification_preparer=prepare_verification,
            verification_resolver=lambda context, verification_id: self.state["records"][verification_id],
            challenge_resolver=lambda context, challenge_id: next(
                item.model_copy(update={"challenge_status": "passed"})
                for item in self.state["challenges"] if item.challenge_id == challenge_id),
            decision_sink=lambda decision: None, snapshot_writer=lambda *_: "AUTH-1",
            summary_validator=lambda *_: False, clock=lambda: NOW)

    def _context_factory(self, trusted, operation_id=None, action_revision=None):
        answered = self.state["answered"]
        if answered is not None and (
                answered.operation_id != operation_id
                or answered.action_revision != action_revision):
            # The platform binds a confirmation only to the exact action it was answered
            # for; changed facts therefore start a fresh confirmation instead of a stale one.
            answered = None
        return ExecutionSecurityContext(
            user_id=trusted.user_id, session_id=trusted.session_id,
            demo_round_id=trusted.demo_round_id, task_id=trusted.task_id, run_id=trusted.run_id,
            source_task_id=None, operation_id=operation_id, action_revision=action_revision,
            confirmation_id=answered.confirmation_id if answered else None,
            confirmation_version=answered.confirmation_version if answered else None,
            verification_ids=list(self.state["verification_ids"]),
            release_authorization_id=None)

    def _reserve(self, trusted, payload):
        # One operation per frozen fact set, like the production platform reserver.
        digest = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        operation_id = self.state["operations"].get(digest)
        if operation_id is None:
            operation_id = uuid4()
            self.state["operations"][digest] = operation_id
        self.state["operation_id"] = operation_id
        return operation_id

    def _on_bind(self, context, action_name, ref, payload):
        if action_name == "subscription.bank.cancel_subscription":
            self.state["refs"].append(ref)
            self.state["payloads"].append(payload)

    # -- helpers -----------------------------------------------------------------

    def plan(self):
        service = SubscriptionService(Ports(self.bank, None), lambda: NOW)
        return service.plan_for(service.resolve_cancel(context(), subscription_id="sub_001").item)

    def lookup_context(self):
        return self._context_factory(context(), None, None)

    def answer_confirmation(self, answer):
        record = self.confirmations.get(self.lookup_context(), answer.interaction.record_ref)
        self.state["answered"] = self.confirmations.answer(
            self.lookup_context(), ConfirmationAnswer(
                confirmation_id=record.confirmation_id,
                confirmation_version=record.confirmation_version, choice="approve"))
        return self.state["answered"]

    def pass_session_verification(self):
        challenge = self.state["challenges"][-1]
        record = VerificationRecord(
            verification_id=str(uuid4()), user_id="U1", session_id="S1", demo_round_id="D1",
            scope="session", operation_id=None, action_revision=None, methods=["code"],
            verified_at=NOW, source_challenge_id=challenge.challenge_id)
        self.state["records"][record.verification_id] = record
        self.state["verification_ids"] = [record.verification_id]
        return record


def test_real_gate_runs_the_write_once_with_a_stable_reference(tmp_path):
    harness = Harness(tmp_path)
    plan = harness.plan()

    first = harness.ports.check_cancel(context(), plan)
    assert first.decision.value == "require_confirmation"
    assert first.interaction.kind == "confirmation" and first.interaction.record_ref

    harness.answer_confirmation(first)
    second = harness.ports.check_cancel(context(), plan)
    assert second.decision.value == "require_verification"
    challenge = harness.state["challenges"][-1]
    assert challenge.purpose == "basic_identity" and challenge.required_methods == ["code"]

    harness.pass_session_verification()
    outcome = harness.ports.execute_cancel(context(), plan)
    assert outcome.executed is True and outcome.state == "completed"
    assert harness.gateway.cancels == 1
    assert outcome.result.receipt.mandate_id == "sub_001"
    assert outcome.result.receipt.effective_stop_at == at(2026, 10, 25)

    # Same frozen facts must reuse one parameter reference, so the answered
    # confirmation still matches when the execution claim is made.
    assert len(set(harness.state["refs"])) == 1
    assert harness.state["payloads"][0]["mandate_id"] == "sub_001"
    assert harness.state["payloads"][0]["risk_observations"] == []
    events = [name for name, _ in harness.trace.events]
    assert events.count("tool.started") == 1 and events.count("tool.finished") == 1
    assert "bank.observed" in events


def test_changed_facts_always_reissue_confirmation_v2_never_an_operation_conflict(tmp_path):
    """Issue #176: 关键内容变化后的确认失效必须确定地重出确认单 v2。

    安全状态只保留任务最近一张确认单，新动作的修订号不高于它时按 OPERATION_CONFLICT
    拒绝；模块因此像转账工作流一样给出单调修订号（1、2、…），而不是对参数做哈希。
    """

    harness = Harness(tmp_path)
    first_plan = harness.plan()
    first = harness.ports.check_cancel(context(), first_plan, revision=1)
    assert first.decision.value == "require_confirmation"
    harness.answer_confirmation(first)

    # The bank changes the amount after the user pressed the button: new frozen facts,
    # a new operation number and the next revision on the same task.
    harness.bank.mandates = [
        item.model_copy(update={"amount_fen": 2600}) if item.mandate_id == "sub_001" else item
        for item in harness.bank.mandates
    ]
    changed_plan = harness.plan()
    assert changed_plan.payload() != first_plan.payload()

    second = harness.ports.check_cancel(context(), changed_plan, revision=2)
    assert second.decision.value == "require_confirmation", second.reason_code
    record = harness.confirmations.get(
        harness._context_factory(context(), second.operation_id, 2),
        second.interaction.record_ref)
    assert record.confirmation_version == 2
    assert record.action_revision == 2
    assert record.operation_id != first.operation_id
    assert harness.gateway.cancels == 0


def test_real_gate_refuses_to_execute_without_the_session_verification(tmp_path):
    harness = Harness(tmp_path)
    plan = harness.plan()
    first = harness.ports.check_cancel(context(), plan)
    harness.answer_confirmation(first)
    assert harness.ports.check_cancel(context(), plan).decision.value == "require_verification"

    outcome = harness.ports.execute_cancel(context(), plan)
    assert harness.gateway.cancels == 0
    assert outcome.executed is False
    assert outcome.decision is not None and outcome.decision.decision.value != "allow"


def test_read_path_records_paired_events_and_never_bypasses_the_gate(tmp_path):
    harness = Harness(tmp_path)
    response = harness.ports.mandates(context())
    assert isinstance(response, QueryOk)
    assert [item.mandate_id for item in response.data.mandates] == ["sub_001", "sub_002", "sub_003"]
    events = [name for name, _ in harness.trace.events]
    assert events.count("tool.started") == 1 and events.count("tool.finished") == 1

    denied = Harness(tmp_path, allow_scope=False, db="denied.sqlite3")
    with pytest.raises(ValueError, match="SECURITY_REJECTED"):
        denied.ports.mandates(context())
    assert denied.trace.events == []


def test_repeating_the_same_read_keeps_the_audit_evidence_keys_unique(tmp_path):
    """The parameter reference is deterministic, so it cannot double as an evidence key."""

    harness = Harness(tmp_path)
    for _ in range(3):
        assert isinstance(harness.ports.mandates(context()), QueryOk)
    assert isinstance(harness.ports.accounts(context()), QueryOk)
    assert len(harness.trace.evidence_ids) == 8
    assert len(set(harness.trace.evidence_ids)) == 8


def test_write_refuses_a_context_factory_that_loses_the_task_binding(tmp_path):
    """A platform that hands back a context without our operation must not execute."""

    harness = Harness(tmp_path)
    plan = harness.plan()
    first = harness.ports.check_cancel(context(), plan)
    harness.answer_confirmation(first)
    original = harness.ports.context_factory
    harness.ports.context_factory = lambda trusted, operation_id, revision: original(trusted, None, None)
    with pytest.raises(ValueError, match="ACCESS_DENIED"):
        harness.ports.execute_cancel(context(), plan)
    assert harness.gateway.cancels == 0


# -------------------------------------- explicit refusals and unknown write outcomes


class RefusingGateway(FakeGateway):
    """B30 answers with a business refusal; the bank records no operation at all."""

    def __init__(self, bank, code):
        super().__init__(bank)
        self.code = code
        self.lookups = []

    def cancel_subscription(self, trusted, operation_id, mandate_id):
        self.cancels += 1
        return QueryFailure(kind="error", error=BankError(code=self.code, details={}))

    def get_operation(self, trusted, operation_id):
        self.lookups.append(operation_id)
        return super().get_operation(trusted, operation_id)


class TimingOutGateway(FakeGateway):
    """B30 times out; the bank's own thread may still settle the agreement later."""

    def __init__(self, bank, *, settles):
        super().__init__(bank)
        self.settles = settles
        self.timeouts = 0
        self.lookups = []

    def cancel_subscription(self, trusted, operation_id, mandate_id):
        self.cancels += 1
        if self.timeouts == 0:
            self.timeouts += 1
            if self.settles:
                result = self.bank.cancel(trusted, operation_id, mandate_id)
                if isinstance(result, OperationResult):
                    self.operations[str(operation_id)] = result
            return QueryFailure(kind="error", error=BankError(code="CALL_TIMEOUT", details={}))
        # A second submission would reach the bank again: the red line is never to resubmit.
        return super().cancel_subscription(trusted, operation_id, mandate_id)

    def get_operation(self, trusted, operation_id):
        self.lookups.append(operation_id)
        return super().get_operation(trusted, operation_id)


def real_entry(harness, saver=None):
    """The module's own entry on top of the *real* gate + shared executor ports."""

    return SubscriptionEntry(SubscriptionService(harness.ports, lambda: NOW),
                             saver or MemorySaver(), None)


def drive_to_bank_execution(harness, entry_task):
    """Start one cancel and answer the confirmation plus the session verification."""

    started = entry_task.start(context(), start_request("把优酷视频的自动扣费退了"))
    assert started.status == TaskStatus.WAITING_APPROVAL, started.error
    assert started.interaction.kind == "confirmation"
    harness.answer_confirmation(started)
    verifying = entry_task.resume(context(), {"choice": "approve"})
    assert verifying.status == TaskStatus.WAITING_APPROVAL, verifying.error
    assert verifying.interaction.kind == "verification"
    assert verifying.allowed_actions == ["verify", "cancel"]
    harness.pass_session_verification()


@pytest.mark.parametrize("code", [
    "ACCOUNT_UNAVAILABLE", "STATE_CONFLICT", "RECORD_NOT_FOUND",
    "OPERATION_CONFLICT", "ACCESS_DENIED", "BANK_REJECTED",
])
def test_a_definitive_bank_refusal_keeps_the_bank_code_and_wording(tmp_path, code):
    harness = Harness(tmp_path, db=f"refusal-{code}.sqlite3",
                      gateway_factory=lambda bank: RefusingGateway(bank, code))
    task = real_entry(harness)
    drive_to_bank_execution(harness, task)

    result = task.resume(context(), {"choice": "resume"})

    assert result.status == TaskStatus.FAILED, result.message
    assert result.error.code == code and result.error.source == "bank"
    assert result.error.upstream_code == code
    assert result.message == _MESSAGES[code]
    assert result.message != _MESSAGES["SUBSCRIPTION_INTERNAL_ERROR"]
    assert harness.gateway.cancels == 1
    # A confirmed refusal is final: it must not be kept in the unknown bucket for B14.
    assert harness.gateway.lookups == []
    assert [mandate.status for mandate in harness.bank.mandates
            if mandate.mandate_id == "sub_001"] == ["active"]
    # A refusal is this operation's final answer: no retry on a later resume either.
    replay = task.resume(context(), {})
    assert replay.status == TaskStatus.FAILED and replay.error.code == code
    assert harness.gateway.cancels == 1


def test_an_unrecognized_bank_refusal_still_reads_as_a_bank_refusal(tmp_path):
    harness = Harness(tmp_path, db="refusal-unknown.sqlite3",
                      gateway_factory=lambda bank: RefusingGateway(bank, "INTERNAL_MELTDOWN"))
    task = real_entry(harness)
    drive_to_bank_execution(harness, task)

    result = task.resume(context(), {"choice": "resume"})
    assert result.status == TaskStatus.FAILED
    assert (result.error.code, result.error.source, result.error.upstream_code) == (
        "BANK_REJECTED", "bank", "INTERNAL_MELTDOWN")
    assert result.message == _MESSAGES["BANK_REJECTED"]


def test_a_b30_timeout_is_needs_attention_not_failed(tmp_path):
    harness = Harness(tmp_path, db="timeout-unknown.sqlite3",
                      gateway_factory=lambda bank: TimingOutGateway(bank, settles=False))
    task = real_entry(harness)
    drive_to_bank_execution(harness, task)

    pending = task.resume(context(), {"choice": "resume"})

    assert pending.status == TaskStatus.NEEDS_ATTENTION, pending.message
    assert pending.recovery_required is True and pending.recovery_reason == "OPERATION_UNKNOWN"
    assert pending.error is None
    assert pending.message == _MESSAGES["CALL_TIMEOUT"]
    assert pending.data.action == "cancel"
    assert pending.data.selected_item.subscription_id == "sub_001"
    assert "query" in pending.allowed_actions
    assert harness.gateway.cancels == 1

    still = task.resume(context(), {"query": True})
    assert still.status == TaskStatus.NEEDS_ATTENTION
    assert still.recovery_reason == "OPERATION_UNKNOWN"
    assert still.message == _MESSAGES["CALL_TIMEOUT"]
    assert harness.gateway.cancels == 1
    # The resume went through the shared executor's B14 lookup, on the original id.
    assert [str(item) for item in harness.gateway.lookups] == [str(harness.state["operation_id"])]


def test_b14_finds_the_settled_cancel_and_reports_the_real_receipt(tmp_path):
    harness = Harness(tmp_path, db="timeout-settled.sqlite3",
                      gateway_factory=lambda bank: TimingOutGateway(bank, settles=True))
    task = real_entry(harness)
    drive_to_bank_execution(harness, task)

    assert task.resume(context(), {"choice": "resume"}).status == TaskStatus.NEEDS_ATTENTION

    done = task.resume(context(), {"query": True})

    assert done.status == TaskStatus.SUCCEEDED, done.error
    receipt = done.data.operation.receipt
    assert receipt.mandate_id == "sub_001" and receipt.status == "cancelled"
    assert receipt.effective_stop_at == at(2026, 10, 25)
    assert "已经退了" in done.message
    assert done.data.selected_item.status == "cancelled"
    assert harness.gateway.cancels == 1  # never resubmitted, same operation number
    assert [str(item) for item in harness.gateway.lookups] == [str(harness.state["operation_id"])]
    assert [mandate.status for mandate in harness.bank.mandates
            if mandate.mandate_id == "sub_001"] == ["cancelled"]


def test_b14_finds_a_failed_operation_and_reports_it_honestly(tmp_path):
    gateways: list[TimingOutGateway] = []

    def factory(bank):
        gateway = TimingOutGateway(bank, settles=False)
        gateways.append(gateway)
        return gateway

    harness = Harness(tmp_path, db="timeout-failed.sqlite3", gateway_factory=factory)
    task = real_entry(harness)
    drive_to_bank_execution(harness, task)

    assert task.resume(context(), {"choice": "resume"}).status == TaskStatus.NEEDS_ATTENTION
    gateway = gateways[0]
    gateway.operations[str(harness.state["operation_id"])] = OperationResult[
        SubscriptionCancelReceipt](
        operation_id=UUID(str(harness.state["operation_id"])),
        operation_type="bank.cancel_subscription",
        operation_status="failed", recorded_at=NOW, updated_at=NOW,
        receipt=None, failure=BankError(code="ACCOUNT_UNAVAILABLE", details={}),
    )

    result = task.resume(context(), {"query": True})
    assert result.status == TaskStatus.FAILED
    assert (result.error.code, result.error.source, result.error.upstream_code) == (
        "ACCOUNT_UNAVAILABLE", "bank", "ACCOUNT_UNAVAILABLE")
    assert result.message == _MESSAGES["ACCOUNT_UNAVAILABLE"]
    assert harness.gateway.cancels == 1


def test_a_replayed_execution_reports_the_bank_receipt_not_a_refusal(tmp_path):
    """A crash after the bank call must replay as the bank's own outcome."""

    harness = Harness(tmp_path)
    plan = harness.plan()
    harness.answer_confirmation(harness.ports.check_cancel(context(), plan))
    harness.ports.check_cancel(context(), plan)
    harness.pass_session_verification()
    assert harness.ports.execute_cancel(context(), plan).executed is True
    assert harness.gateway.cancels == 1

    replay = harness.ports.execute_cancel(context(), plan)
    assert replay.executed is False and replay.state == "completed"
    assert harness.gateway.cancels == 1

    service = SubscriptionService(Ports(harness.bank, None), lambda: NOW)
    item = service.resolve_cancel(context(), subscription_id="sub_001").item
    result = service.cancel_task(context(), item, plan, replay)
    assert result.status == TaskStatus.SUCCEEDED
    assert result.data.operation.receipt.mandate_id == "sub_001"
    assert "已经退了" in result.message and "没有通过安全检查" not in result.message
