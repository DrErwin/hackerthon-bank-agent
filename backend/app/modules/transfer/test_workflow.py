"""The reference graph's business branches and funds boundary."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.contracts.bank import (
    AccountList, AccountSummary, BankError, OperationResult, PayeeCandidate,
    PayeeDisplay, PayeeList, PayeeVerification, QueryOk, SavedPayee,
    TransferPrecheck, TransferReceipt, BalanceSnapshot,
)
from app.contracts.common import DisplayField, OperationLevel, Phase, RiskLevel, SecurityDecisionCode, TaskStatus
from app.contracts.platform import StartTransferInput, TrustedContext
from app.contracts.security import ConfirmationAnswer, ExecutionSecurityContext, SecurityDecision, VerificationRecord
from app.contracts.tasks import InteractionRequest
from app.security import ConfirmationService, ExecutionOutcome, SecurityGate, ToolRegistry
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.storage.mock_bank.repository import MockBankStore

from .tools import GatewayTransferTools, TransferAction, TransferSnapshots
from .workflow import TransferWorkflow


NOW = datetime(2026, 9, 29, tzinfo=timezone.utc)
PAYEE = PayeeDisplay(payee_id="P1", name_masked="张*", account_masked="****1234", remark="邻居", bank_name="模拟银行")


def trusted(user="U1", task="T1"):
    return TrustedContext(user_id=user, session_id="S1", task_id=task, run_id="R1", parent_task_id=None, demo_round_id="D1")


def request(**updates):
    data = dict(request_id=uuid4(), intent_text="转给邻居 100 元", payer_account_id="A1",
                payee=SavedPayee(kind="saved", payee_id="P1"), amount_fen=10_000)
    data.update(updates)
    return StartTransferInput(**data)


def operation(action, status="succeeded"):
    receipt = TransferReceipt(
        transaction_id="TX1", payer_account_id="A1", payee=PAYEE,
        amount_fen=10_000, fee_fen=0, arrival_mode="instant", completed_at=NOW,
        balance=BalanceSnapshot(account_id="A1", book_balance_fen=90_000,
                                frozen_balance_fen=0, available_balance_fen=90_000, as_of=NOW),
    ) if status == "succeeded" else None
    return OperationResult(
        operation_id=action.operation_id, operation_type="transfer",
        operation_status=status, recorded_at=NOW, updated_at=NOW,
        receipt=receipt, failure=BankError(code="INSUFFICIENT_FUNDS", details={"available_fen": 3_200})
        if status == "failed" else None,
    )


class Ports:
    def __init__(self):
        self.approved = False
        self.read_calls = []
        self.precheck_ok = True
        self.precheck_error_code = "INSUFFICIENT_FUNDS"
        self.payees = [PayeeCandidate(**PAYEE.model_dump(), last_transfer_at=None)]
        self.submissions = 0
        self.observations = 0
        self.bank_status = "succeeded"
        self.processing = False
        self.block = False
        self.expired = False
        self.action = None

    def read(self, _trusted, name, parameters):
        self.read_calls.append(name)
        if name == "bank.list_accounts":
            data = AccountList(accounts=[AccountSummary(account_id="A1", account_type="class_i",
                account_masked="****0001", available_balance_fen=100_000,
                display_name="工资卡", bank_name="模拟银行")])
        elif name == "bank.list_payees":
            data = PayeeList(payees=self.payees)
        elif name == "bank.verify_payee":
            data = PayeeVerification(matched=True, payee=PAYEE)
        elif name == "bank.precheck_transfer":
            data = TransferPrecheck(can_proceed=self.precheck_ok,
                failure=None if self.precheck_ok else BankError(
                    code=self.precheck_error_code,
                    details={"available_fen": 3_200} if self.precheck_error_code == "INSUFFICIENT_FUNDS" else {}),
                fee_fen=0, arrival_mode="instant", checked_at=NOW)
        else:
            raise AssertionError(name)
        decision = SecurityDecision(
            decision_id=str(uuid4()), task_id="T1", run_id="R1", action_name=name,
            parameters_ref="READ", operation_id=None, action_revision=None,
            phase=Phase.ADMISSION, operation_level=OperationLevel.READ, risk_level=RiskLevel.LOW,
            decision=SecurityDecisionCode.ALLOW, reason_codes=[], rule_ids=["test"],
            policy_version="test", authorization_snapshot_ref=None, evidence_refs=[],
            interaction=None, checked_at=NOW, message="test",
        )
        return ExecutionOutcome(decision, True, False, "completed", QueryOk(kind="ok", data=data), None)

    def prepare_transfer(self, _trusted, operation_id, revision, _payer, _payee, _amount):
        self.action = TransferAction(operation_id, revision, f"SNAP-{revision}")
        return self.action

    def decision(self, action, code):
        interaction = (InteractionRequest(interaction_id="I1", kind="confirmation", prompt="请确认",
            required_fields=[], options=[], record_ref="C1") if code == SecurityDecisionCode.REQUIRE_CONFIRMATION else None)
        return SecurityDecision(
            decision_id=str(uuid4()), task_id="T1", run_id="R1", action_name="bank.submit_transfer",
            parameters_ref=action.parameters_ref, operation_id=action.operation_id,
            action_revision=action.action_revision, phase=Phase.ADMISSION,
            operation_level=OperationLevel.SENSITIVE, risk_level=RiskLevel.LOW,
            decision=code, reason_codes=[] if code == SecurityDecisionCode.ALLOW else [
                "CONFIRMATION_EXPIRED" if self.expired else "CONFIRMATION_REQUIRED"
            ],
            rule_ids=["test"], policy_version="test", authorization_snapshot_ref=None,
            evidence_refs=[], interaction=interaction, checked_at=NOW, message="test",
        )

    def check(self, _trusted, action):
        code = (SecurityDecisionCode.BLOCK if self.block else
                SecurityDecisionCode.REQUIRE_CONFIRMATION if self.expired else
                SecurityDecisionCode.ALLOW if self.approved else SecurityDecisionCode.REQUIRE_CONFIRMATION)
        return self.decision(action, code)

    def execute(self, _trusted, action):
        decision = self.check(_trusted, action)
        if decision.decision != SecurityDecisionCode.ALLOW:
            return ExecutionOutcome(decision, False, False, "not_started", None, None)
        self.submissions += 1
        if self.processing:
            return ExecutionOutcome(decision, True, False, "unknown", None, None)
        state = "processing" if self.bank_status == "processing" else "completed"
        return ExecutionOutcome(decision, True, False, state, operation(action, self.bank_status),
                                None if state == "processing" else "TX1")

    def observe(self, _trusted, action):
        self.observations += 1
        if self.processing:
            return ExecutionOutcome(None, False, True, "unknown", None, None)
        state = "processing" if self.bank_status == "processing" else "completed"
        return ExecutionOutcome(None, False, True, state, operation(action, self.bank_status),
                                None if state == "processing" else "TX1")


def workflow(ports=None):
    ports = ports or Ports()
    clock = [0]
    def sleep(seconds):
        clock[0] += seconds
    return TransferWorkflow(ports, InMemorySaver(), monotonic=lambda: clock[0], sleep=sleep), ports


def test_normal_transfer_requires_external_confirmation_and_deduplicates_start():
    flow, ports = workflow()
    req = request()
    pending = flow.start(trusted(), req)
    assert pending.status == TaskStatus.WAITING_APPROVAL
    assert ports.submissions == 0
    assert flow.start(trusted(), req).status == TaskStatus.WAITING_APPROVAL
    ports.approved = True
    done = flow.resume(trusted(), {"choice": "approve"})
    assert done.status == TaskStatus.SUCCEEDED
    assert done.data.operation.receipt.transaction_id == "TX1"
    assert ports.submissions == 1
    assert flow.resume(trusted(), {"choice": "approve"}).status == TaskStatus.SUCCEEDED
    assert ports.submissions == 1


def test_chat_confirmation_alone_cannot_submit():
    flow, ports = workflow()
    flow.start(trusted(), request())
    still_waiting = flow.resume(trusted(), {"choice": "approve"})
    assert still_waiting.status == TaskStatus.WAITING_APPROVAL
    assert ports.submissions == 0


def test_expired_confirmation_requires_fresh_authorization():
    flow, ports = workflow()
    flow.start(trusted(), request())
    ports.approved = True
    ports.expired = True
    result = flow.resume(trusted(), {"choice": "approve"})
    assert result.status == TaskStatus.WAITING_APPROVAL
    assert ports.submissions == 0


def test_missing_amount_and_account_resume_same_task():
    flow, ports = workflow()
    result = flow.start(trusted(), request(amount_fen=None, payer_account_id=None))
    assert result.status == TaskStatus.WAITING_INPUT
    result = flow.resume(trusted(), {"fields": {"amount_fen": 10_000}})
    assert result.status == TaskStatus.WAITING_INPUT
    assert result.interaction.options[0].id == "A1"
    result = flow.resume(trusted(), {"fields": {"payer_account_id": "A1"}})
    assert result.status == TaskStatus.WAITING_APPROVAL
    assert ports.submissions == 0


def test_ambiguous_payee_needs_explicit_choice():
    flow, ports = workflow()
    ports.payees.append(PayeeCandidate(payee_id="P2", name_masked="张*", account_masked="****5678",
        remark="邻居", bank_name="模拟银行", last_transfer_at=None))
    pending = flow.start(trusted(), request(payee=None, payee_hint="邻居"))
    assert pending.status == TaskStatus.WAITING_INPUT
    assert len(pending.interaction.options) == 2
    assert ports.submissions == 0
    assert flow.resume(trusted(), {"choice": "unknown"}).status == TaskStatus.WAITING_INPUT
    assert flow.resume(trusted(), {"choice": "P2"}).status == TaskStatus.WAITING_APPROVAL


def test_name_and_remark_matches_are_combined_before_selection():
    class SplitMatches(Ports):
        def read(self, trusted_context, name, parameters):
            if name == "bank.list_payees":
                item = (self.payees[0] if parameters["kind"] == "remark" else
                        PayeeCandidate(payee_id="P2", name_masked="张*", account_masked="****5678",
                                       remark=None, bank_name="另一银行", last_transfer_at=None))
                original = self.payees
                self.payees = [item]
                try:
                    return super().read(trusted_context, name, parameters)
                finally:
                    self.payees = original
            return super().read(trusted_context, name, parameters)

    flow, ports = workflow(SplitMatches())
    pending = flow.start(trusted(), request(payee=None, payee_hint="张三"))
    assert pending.status == TaskStatus.WAITING_INPUT
    assert {option.id for option in pending.interaction.options} == {"P1", "P2"}
    assert any("模拟银行" in option.label and "****1234" in option.label
               for option in pending.interaction.options)
    assert any("另一银行" in option.label and "****5678" in option.label
               for option in pending.interaction.options)
    assert ports.submissions == 0


@pytest.mark.parametrize("tool,changes", [
    ("bank.list_accounts", {"payer_account_id": None}),
    ("bank.list_payees", {"payee": None, "payee_hint": "邻居"}),
    ("bank.verify_payee", {}),
    ("bank.precheck_transfer", {}),
])
def test_temporary_read_failure_resumes_original_task(tool, changes):
    class Flaky(Ports):
        failures_left = 2

        def read(self, trusted_context, name, parameters):
            if name == tool and self.failures_left:
                self.failures_left -= 1
                raise TimeoutError("temporary read failure")
            return super().read(trusted_context, name, parameters)

    ports = Flaky()
    saver = InMemorySaver()
    flow = TransferWorkflow(ports, saver)
    pending = flow.start(trusted(), request(**changes))
    assert pending.status == TaskStatus.WAITING_INPUT
    assert pending.recovery_required
    assert pending.allowed_actions == ["resume", "cancel"]
    resumed = TransferWorkflow(ports, saver).resume(trusted(), {"choice": "resume"})
    assert resumed.task_id == pending.task_id
    assert resumed.status in {TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL}
    assert ports.submissions == 0


def test_read_permission_denial_is_terminal():
    class Denied(Ports):
        def read(self, trusted_context, name, parameters):
            return ExecutionOutcome(None, False, False, "not_started", None, None)

    flow, ports = workflow(Denied())
    result = flow.start(trusted(), request(payer_account_id=None))
    assert result.status == TaskStatus.FAILED
    assert result.error.code == "ACCESS_DENIED"
    assert not result.recovery_required
    assert ports.submissions == 0


def test_adjustment_gets_new_operation_and_confirmation():
    flow, ports = workflow()
    first = flow.start(trusted(), request())
    first_id = first.data.operation_id
    old_action = ports.action
    changed = flow.resume(trusted(), {"fields": {"amount_fen": 12_000}})
    assert changed.data.operation_id != first_id
    assert changed.status == TaskStatus.WAITING_APPROVAL
    assert ports.action.action_revision == 2
    assert ports.submissions == 0
    old_context = ExecutionSecurityContext(
        user_id="U1", session_id="S1", demo_round_id="D1", task_id="T1", run_id="R1",
        source_task_id=None, operation_id=old_action.operation_id,
        action_revision=old_action.action_revision, confirmation_id="C1",
        confirmation_version=1, verification_ids=[], release_authorization_id=None,
    )
    assert not flow.is_current_action(old_context, old_action.descriptor(Phase.EXECUTION))


def test_cancel_and_owner_rejection():
    flow, ports = workflow()
    flow.start(trusted(), request())
    with pytest.raises(ValueError, match="ACCESS_DENIED"):
        flow.resume(trusted(user="U2"), {"choice": "approve"})
    cancelled = flow.resume(trusted(), {"choice": "cancel"})
    assert cancelled.status == TaskStatus.CANCELLED
    assert ports.submissions == 0


def test_checkpoint_recovery_and_bank_failure():
    ports = Ports()
    saver = InMemorySaver()
    flow = TransferWorkflow(ports, saver)
    flow.start(trusted(), request())
    ports.approved = True
    ports.bank_status = "failed"
    recovered = TransferWorkflow(ports, saver)
    done = recovered.resume(trusted(), {"choice": "approve"})
    assert done.status == TaskStatus.FAILED
    assert done.error.upstream_code == "INSUFFICIENT_FUNDS"
    assert "可用余额不足" in done.message
    assert "32.00 元" in done.message
    assert ports.submissions == 1


def test_unknown_result_queries_only_original_operation():
    flow, ports = workflow()
    flow.start(trusted(), request())
    ports.approved = True
    ports.processing = True
    unknown = flow.resume(trusted(), {"choice": "approve"})
    assert unknown.status == TaskStatus.NEEDS_ATTENTION
    assert unknown.recovery_reason == "OPERATION_UNKNOWN"
    assert ports.submissions == 1
    assert ports.observations >= 3
    ports.processing = False
    done = flow.resume(trusted(), {"query": True})
    assert done.status == TaskStatus.SUCCEEDED
    assert done.data.operation_id == unknown.data.operation_id
    assert ports.submissions == 1


def test_processing_result_survives_restart_without_resubmission():
    ports = Ports()
    saver = InMemorySaver()
    time_now = [0]
    def sleep(seconds):
        time_now[0] += seconds
    flow = TransferWorkflow(ports, saver, monotonic=lambda: time_now[0], sleep=sleep)
    flow.start(trusted(), request())
    ports.approved = True
    ports.bank_status = "processing"
    pending = flow.resume(trusted(), {"choice": "approve"})
    assert pending.status == TaskStatus.NEEDS_ATTENTION
    assert pending.recovery_reason == "OPERATION_PROCESSING"
    assert pending.data.operation.operation_status == "processing"
    assert ports.submissions == 1
    recovered = TransferWorkflow(ports, saver, monotonic=lambda: time_now[0], sleep=sleep)
    ports.bank_status = "succeeded"
    done = recovered.resume(trusted(), {"query": True})
    assert done.status == TaskStatus.SUCCEEDED
    assert done.data.operation_id == pending.data.operation_id
    assert ports.submissions == 1


def test_precheck_and_security_denial_never_submit():
    flow, ports = workflow()
    ports.precheck_ok = False
    result = flow.start(trusted(), request())
    assert result.status == TaskStatus.WAITING_INPUT
    assert "可用余额不足" in result.message
    assert "32.00 元" in result.message
    assert ports.submissions == 0
    flow, ports = workflow()
    ports.block = True
    result = flow.start(trusted(), request())
    assert result.status == TaskStatus.FAILED
    assert ports.submissions == 0


def test_bank_risk_rejection_stops_without_adjustment():
    ports = Ports()
    ports.precheck_ok = False
    ports.precheck_error_code = "RISK_REJECTED"
    flow, _ = workflow(ports)
    result = flow.start(trusted(), request())
    assert result.status == TaskStatus.FAILED
    assert result.error.code == "RISK_REJECTED"
    assert result.interaction is None
    assert result.allowed_actions == []
    assert ports.submissions == 0


def test_read_failure_retries_at_most_twice():
    class Flaky(Ports):
        attempts = 0
        def read(self, trusted_context, name, parameters):
            if name == "bank.verify_payee":
                self.attempts += 1
                if self.attempts == 1:
                    raise TimeoutError("temporary read failure")
            return super().read(trusted_context, name, parameters)

    ports = Flaky()
    flow, _ = workflow(ports)
    result = flow.start(trusted(), request())
    assert result.status == TaskStatus.WAITING_APPROVAL
    assert ports.attempts == 2
    assert ports.submissions == 0


def test_real_gateway_and_security_executor_in_same_graph(tmp_path):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    gateway = BankGateway(bank, authorize_transfer=lambda *_: True)
    snapshots = TransferSnapshots(tmp_path / "app.sqlite")
    confirmations = ConfirmationService(tmp_path / "security.sqlite", clock=lambda: NOW)
    auth = {"confirmation": None}
    session_verification = VerificationRecord(
        verification_id="V1", user_id="U1", session_id="S1", demo_round_id="D1",
        scope="session", operation_id=None, action_revision=None,
        methods=["code"], verified_at=NOW, source_challenge_id="CH1",
    )

    def security_context(trusted_context, operation_id, revision):
        confirmation = auth["confirmation"]
        return ExecutionSecurityContext(
            user_id=trusted_context.user_id, session_id=trusted_context.session_id,
            demo_round_id=trusted_context.demo_round_id, task_id=trusted_context.task_id,
            run_id=trusted_context.run_id, source_task_id=None,
            operation_id=operation_id, action_revision=revision,
            confirmation_id=confirmation.confirmation_id if confirmation else None,
            confirmation_version=confirmation.confirmation_version if confirmation else None,
            verification_ids=["V1"], release_authorization_id=None,
        )

    def prepare_confirmation(context, descriptor):
        payload = snapshots.resolve(context, descriptor)
        record = confirmations.create(context, descriptor, [
            DisplayField(name="amount", label="金额", value_text=f"{payload['amount_fen'] / 100:.2f} 元"),
            DisplayField(name="payee", label="收款人", value_text="王阿姨 ****0002"),
        ])
        auth["confirmation"] = record
        return record

    flow = None
    gate = SecurityGate(
        ToolRegistry(), confirmations,
        scope_authorizer=lambda context, action, declaration: (
            context.user_id == "U1" and context.task_id == "T1"
            and (not declaration.side_effect or flow.is_current_action(context, action))
        ),
        task_state_resolver=lambda _context: False,
        risk_assessor=lambda *_: RiskLevel.LOW,
        confirmation_preparer=prepare_confirmation,
        verification_preparer=lambda *_: pytest.fail("session verification already exists"),
        verification_resolver=lambda _context, _id: session_verification,
        challenge_resolver=lambda *_: pytest.fail("no challenge needed"),
        decision_sink=lambda _decision: None,
        snapshot_writer=lambda *_: "AUTH1",
        summary_validator=lambda *_: True,
        clock=lambda: NOW,
    )
    try:
        ports = GatewayTransferTools(gateway, gate, snapshots, security_context)
        flow = TransferWorkflow(ports, InMemorySaver())
        pending = flow.start(trusted(), request(payee=SavedPayee(kind="saved", payee_id="A2")))
        assert pending.status == TaskStatus.WAITING_APPROVAL
        assert bank.get_operation(trusted(), pending.data.operation_id).lookup == "not_found"
        auth["confirmation"] = confirmations.answer(
            security_context(trusted(), pending.data.operation_id, 1),
            ConfirmationAnswer(confirmation_id=auth["confirmation"].confirmation_id,
                               confirmation_version=auth["confirmation"].confirmation_version,
                               choice="approve"),
        )
        done = flow.resume(trusted(), {"choice": "approve"})
        assert done.status == TaskStatus.SUCCEEDED
        assert done.data.operation.receipt.transaction_id
        assert bank.get_operation(trusted(), done.data.operation_id).lookup == "found"
    finally:
        gateway.close()
