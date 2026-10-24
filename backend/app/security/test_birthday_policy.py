"""Ticket v05-cross-security/01: birthday purchase declarations through the gate.

Purchase-path failure modes enumerated before implementation:

1. bank.release_frozen is not a model tool: the normal executor refuses it
   (only the controlled finalization may release);
2. the registry rejects birthday write declarations without per_action;
3. scope authorization fails for foreign users/rounds or tampered declarations;
4. money writes classify as MEDIUM (step-up verification), reads as LOW;
5. the freeze confirmation carries the §3.5 limited-release clause, and an
   approved freeze confirmation yields a pending_freeze authorization;
6. without confirmation the executor submits nothing to the bank;
7. without step-up verification the executor submits nothing;
8. a parameter change invalidates the old approval (CONFIRMATION_STALE), so an
   old button replay submits nothing;
9. a cancelled confirmation stops the action with no bank write;
10. a terminated task blocks purchases while the limited finalization still
    releases the remaining frozen funds on the same state.

The bank is the real MockBankService behind a BankGateway wired with the
state-backed authorize_birthday callback (真实银行层).
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.contracts.bank import FreezeFundsInput, QueryFailure
from app.contracts.common import (
    DisplayField, OperationLevel, Phase, RiskLevel, SecurityDecisionCode,
)
from app.contracts.platform import CapabilityDefinition, TrustedContext
from app.contracts.security import (
    ActionDescriptor, ConfirmationAnswer, ConfirmationRecord,
    ExecutionSecurityContext, VerificationChallenge, VerificationRecord,
    VerificationSummary,
)
from app.security import (
    ConfirmationService, DeterministicExecutor, SecurityGate, ToolRegistrationError,
    ToolRegistry,
)
from app.security.birthday_policy import (
    BIRTHDAY_TOOLS, BirthdaySecurityPolicy, RELEASE_CLAUSE_FIELD, with_release_clause,
)
from app.security.birthday_release import (
    authorize_birthday_write, bind_freeze_result, grant_release_authorization,
)
from app.security.gate import RiskAssessment
from app.security.state import SQLiteSecurityState
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.storage.mock_bank.repository import BankAccount, MockBankStore


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **amount: int) -> None:
        self.value += timedelta(**amount)


def context(**changes) -> ExecutionSecurityContext:
    values = {
        "user_id": "U1",
        "session_id": "S1",
        "demo_round_id": "D1",
        "task_id": "T1",
        "run_id": "R1",
        "source_task_id": None,
        "operation_id": uuid4(),
        "action_revision": 1,
        "confirmation_id": None,
        "confirmation_version": None,
        "verification_ids": [],
        "release_authorization_id": None,
    }
    values.update(changes)
    return ExecutionSecurityContext(**values)


def trusted(source: ExecutionSecurityContext) -> TrustedContext:
    return TrustedContext(
        user_id=source.user_id, session_id=source.session_id,
        demo_round_id=source.demo_round_id, task_id=source.task_id,
        run_id=source.run_id, parent_task_id=source.source_task_id,
    )


class PurchaseRig:
    def __init__(self, tmp_path, *, task_terminated=False, current_round="D1"):
        self.clock = Clock()
        self.path = tmp_path / "application.sqlite3"
        self.state = SQLiteSecurityState(self.path)
        self.confirmations = ConfirmationService(self.path, clock=self.clock)
        self.bank = MockBankService(
            MockBankStore(tmp_path / "bank.sqlite3"), demo_secret=b"s" * 32,
        )
        self.bank.store.seed_account(
            BankAccount("BA1", "U1", "class_i", "active", 200000, 0, 0),
        )
        self.gateway = BankGateway(
            self.bank, authorize_birthday=authorize_birthday_write(self.state),
        )
        self.policy = BirthdaySecurityPolicy(
            demo_user_id="U1", current_demo_round=lambda: current_round,
        )
        self.bank_writes: list = []
        self.decisions: list = []
        self.snapshots: list = []
        self.challenges: list = []
        self.records: dict = {}
        self.payloads: dict = {}
        self.task_terminated = task_terminated
        registry = ToolRegistry()
        for declaration in BIRTHDAY_TOOLS:
            registry.register(declaration, self._handler)
        self.registry = registry
        self.gate = SecurityGate(
            registry,
            self.confirmations,
            scope_authorizer=self.policy.authorize_tool,
            task_state_resolver=lambda _context: self.task_terminated,
            risk_assessor=self.policy.assess_risk,
            confirmation_preparer=self._prepare_confirmation,
            verification_preparer=self._prepare_verification,
            verification_resolver=self._resolve_verification,
            challenge_resolver=self._resolve_challenge,
            decision_sink=self.decisions.append,
            snapshot_writer=self._write_snapshot,
            summary_validator=self._validate_summary,
            clock=self.clock,
        )
        self.executor = DeterministicExecutor(
            self.gate,
            parameter_resolver=self._resolve_parameters,
            operation_lookup=self._lookup,
            result_observer=self._observe,
        )

    # --- executor seams ---

    def _handler(self, security_context, payload):
        action_name = payload["action_name"]
        self.bank_writes.append(action_name)
        if action_name == "bank.freeze_funds":
            return self.gateway.freeze_funds(
                trusted(security_context), security_context.operation_id,
                FreezeFundsInput(account_id=payload["account_id"],
                                 amount_fen=payload["amount_fen"], reason="生日礼物"),
            )
        if action_name == "bank.create_order":
            from app.contracts.bank import CreateOrderInput
            return self.gateway.create_order(
                trusted(security_context), security_context.operation_id,
                CreateOrderInput(product_id=payload["product_id"],
                                 quantity=payload["quantity"],
                                 expected_total_fen=payload["expected_total_fen"],
                                 delivery=payload["delivery"]),
            )
        if action_name == "bank.capture_frozen":
            from app.contracts.bank import CaptureFrozenInput
            return self.gateway.capture_frozen(
                trusted(security_context), security_context.operation_id,
                CaptureFrozenInput(freeze_id=payload["freeze_id"],
                                   amount_fen=payload["amount_fen"],
                                   merchant_id=payload["merchant_id"],
                                   merchant_name=payload["merchant_name"],
                                   purpose=payload["purpose"],
                                   category=payload["category"],
                                   order_id=payload["order_id"]),
            )
        raise AssertionError("unexpected tool " + action_name)

    def _resolve_parameters(self, _security_context, action):
        return self.payloads[action.parameters_ref]

    def _lookup(self, _security_context, _action):
        from app.security import OperationObservation
        return OperationObservation(
            operation_id=_security_context.operation_id, state="processing",
            result=None, result_ref=None,
        )

    def _observe(self, result):
        from app.security import OperationObservation
        return OperationObservation(
            operation_id=result.operation_id, state="completed", result=result,
            result_ref=str(result.operation_id),
        )

    # --- gate seams ---

    def _prepare_confirmation(self, security_context, action):
        fields = [
            DisplayField(name="amount", label="金额", value_text="500 元"),
            DisplayField(name="account", label="账户", value_text="模拟账户 ****0001"),
        ]
        if action.action_name == "bank.freeze_funds":
            fields = with_release_clause(fields)
        return self.confirmations.create(security_context, action, fields)

    def _prepare_verification(self, security_context, action, confirmation, risk):
        action_step_up = risk == RiskLevel.MEDIUM
        summary = None
        if action_step_up:
            summary = VerificationSummary(
                operation_id=security_context.operation_id,
                action_revision=security_context.action_revision,
                source_confirmation_id=confirmation.confirmation_id,
                source_confirmation_version=confirmation.confirmation_version,
                action_name=action.action_name,
                amount_fen=self.payloads[action.parameters_ref].get(
                    "amount_fen", self.payloads[action.parameters_ref].get(
                        "expected_total_fen")),
                payee=None,
                display_fields=confirmation.display_fields,
            )
        challenge = VerificationChallenge(
            challenge_id=f"CH-{len(self.challenges) + 1}",
            user_id=security_context.user_id, session_id=security_context.session_id,
            demo_round_id=security_context.demo_round_id, task_id=security_context.task_id,
            purpose="action_step_up" if action_step_up else "basic_identity",
            operation_id=security_context.operation_id if action_step_up else None,
            action_revision=security_context.action_revision if action_step_up else None,
            summary=summary,
            required_methods=["code", "mock_face"] if action_step_up else ["code"],
            created_at=self.clock(), code_created_at=self.clock(),
            code_expires_at=self.clock() + timedelta(minutes=5),
            face_started_at=None, face_expires_at=None,
            challenge_status="pending", code_result="pending",
            face_result="pending" if action_step_up else "not_required",
            consecutive_code_failures=0,
        )
        self.challenges.append(challenge)
        return challenge

    def _resolve_verification(self, security_context, verification_id):
        record = self.records[verification_id]
        if (record.user_id, record.session_id, record.demo_round_id) != (
            security_context.user_id, security_context.session_id,
            security_context.demo_round_id,
        ):
            from app.security.gate import SecurityError
            raise SecurityError("ACCESS_DENIED")
        return record

    def _resolve_challenge(self, _security_context, challenge_id):
        return next(
            challenge.model_copy(update={"challenge_status": "passed"})
            for challenge in self.challenges
            if challenge.challenge_id == challenge_id
        )

    def _write_snapshot(self, security_context, confirmation, verifications, checked_at):
        self.snapshots.append((security_context, confirmation, verifications, checked_at))
        return f"AUTH-{len(self.snapshots)}"

    def _validate_summary(self, _context, _action, confirmation, summary):
        return summary.display_fields == confirmation.display_fields

    # --- helpers ---

    def freeze_action(self, parameters_ref="birthday:freeze:50000") -> ActionDescriptor:
        return ActionDescriptor(
            action_name="bank.freeze_funds", parameters_ref=parameters_ref,
            resource_refs=["BA1"], phase=Phase.EXECUTION,
        )

    def approve(self, security_context, action) -> ConfirmationRecord:
        record = self._prepare_confirmation(security_context, action)
        return self.confirmations.answer(security_context, ConfirmationAnswer(
            confirmation_id=record.confirmation_id,
            confirmation_version=record.confirmation_version, choice="approve",
        ))

    def pass_step_up(self, security_context, action, confirmation):
        if not self.challenges:
            self._prepare_verification(
                security_context, action, confirmation, RiskLevel.MEDIUM,
            )
        record = VerificationRecord(
            verification_id=str(uuid4()), user_id=security_context.user_id,
            session_id=security_context.session_id,
            demo_round_id=security_context.demo_round_id, scope="action",
            operation_id=security_context.operation_id,
            action_revision=security_context.action_revision,
            methods=["code", "mock_face"], verified_at=self.clock(),
            source_challenge_id=self.challenges[-1].challenge_id,
        )
        self.records[record.verification_id] = record
        return security_context.model_copy(update={
            "confirmation_id": confirmation.confirmation_id,
            "confirmation_version": confirmation.confirmation_version,
            "verification_ids": [record.verification_id],
        })


def test_release_is_not_a_model_tool(tmp_path):
    rig = PurchaseRig(tmp_path)
    release_action = ActionDescriptor(
        action_name="bank.release_frozen", parameters_ref="release:x",
        resource_refs=["frz_1"], phase=Phase.EXECUTION,
    )
    outcome = rig.executor.execute(context(), release_action)
    assert outcome.decision.decision is SecurityDecisionCode.BLOCK
    assert "registered-tools-only" in outcome.decision.rule_ids
    assert rig.bank_writes == []


def test_registry_requires_per_action_for_birthday_writes(tmp_path):
    from app.security import ToolRegistry
    registry = ToolRegistry()
    writes = [item for item in BIRTHDAY_TOOLS if item.side_effect]
    assert {item.name for item in writes} == {
        "bank.freeze_funds", "bank.create_order", "bank.capture_frozen",
    }
    for declaration in writes:
        with pytest.raises(ToolRegistrationError, match="CONFIRMATION_POLICY_REQUIRED"):
            registry.register(
                declaration.model_copy(update={"confirmation_policy": "none"}),
                lambda *_: None,
            )
        registry.register(declaration, lambda *_: None)


def test_scope_denies_foreign_identity_and_tampered_declarations(tmp_path):
    rig = PurchaseRig(tmp_path)
    action = rig.freeze_action()
    declaration = next(item for item in BIRTHDAY_TOOLS
                       if item.name == "bank.freeze_funds")
    assert rig.policy.authorize_tool(context(), action, declaration) is True
    assert rig.policy.authorize_tool(
        context(user_id="U2"), action, declaration) is False
    assert rig.policy.authorize_tool(
        context(demo_round_id="D2"), action, declaration) is False
    assert rig.policy.authorize_tool(
        context(), action,
        declaration.model_copy(update={"required_permissions": ["evil"]}),
    ) is False


def test_money_writes_are_medium_and_reads_are_low(tmp_path):
    rig = PurchaseRig(tmp_path)
    action = rig.freeze_action()
    for name in ("bank.freeze_funds", "bank.create_order", "bank.capture_frozen"):
        declaration = next(item for item in BIRTHDAY_TOOLS if item.name == name)
        assessment = rig.policy.assess_risk(
            context(), ActionDescriptor(
                action_name=name, parameters_ref="p", resource_refs=[], phase=Phase.EXECUTION,
            ), declaration,
        )
        assert isinstance(assessment, RiskAssessment)
        assert assessment.risk_level is RiskLevel.MEDIUM
    reads = [item for item in BIRTHDAY_TOOLS if not item.side_effect]
    assert {item.name for item in reads} == {
        "bank.get_freeze", "bank.get_order", "bank.list_products",
    }
    for declaration in reads:
        assessment = rig.policy.assess_risk(
            context(), ActionDescriptor(
                action_name=declaration.name, parameters_ref="p", resource_refs=[],
                phase=Phase.ADMISSION,
            ), declaration,
        )
        assert assessment.risk_level is RiskLevel.LOW


def test_full_freeze_path_confirms_verifies_and_freezes(tmp_path):
    rig = PurchaseRig(tmp_path)
    applicant = context()
    action = rig.freeze_action()
    rig.payloads[action.parameters_ref] = {
        "action_name": "bank.freeze_funds", "account_id": "BA1", "amount_fen": 50000,
    }

    first = rig.executor.execute(applicant, action)
    assert first.decision.decision is SecurityDecisionCode.REQUIRE_CONFIRMATION
    assert rig.bank_writes == []
    pending = rig.confirmations.get(applicant, first.decision.interaction.record_ref)
    assert any(field.name == RELEASE_CLAUSE_FIELD for field in pending.display_fields)

    approved = rig.approve(applicant, action)
    second = rig.executor.execute(applicant.model_copy(update={
        "confirmation_id": approved.confirmation_id,
        "confirmation_version": approved.confirmation_version,
    }), action)
    assert second.decision.decision is SecurityDecisionCode.REQUIRE_VERIFICATION
    assert rig.bank_writes == []
    assert rig.challenges[-1].purpose == "action_step_up"

    verified = rig.pass_step_up(applicant, action, approved)
    third = rig.executor.execute(verified, action)
    assert third.decision.decision is SecurityDecisionCode.ALLOW
    assert third.executed is True
    assert rig.bank_writes == ["bank.freeze_funds"]
    assert rig.snapshots and rig.snapshots[0][1].confirmation_id == approved.confirmation_id
    account = rig.bank.store.get_account("U1", "BA1")
    assert account.frozen_balance_fen == 50000

    authorization = grant_release_authorization(
        rig.state, verified, approved,
        account_id="BA1", amount_fen=50000, now=rig.clock(),
    )
    assert authorization.status == "pending_freeze"
    bound = bind_freeze_result(
        rig.state, verified, authorization.release_authorization_id,
        third.result, rig.clock(),
    )
    assert bound.status == "active"


def _confirmed_and_verified(rig, action, payload):
    """Drive one purchase action through confirmation and step-up to allow.

    Returns the verified context plus the bank OperationResult the executor
    observed, so callers read bank facts from real receipts.
    """
    rig.payloads[action.parameters_ref] = payload
    applicant = context()
    outcome = rig.executor.execute(applicant, action)
    assert outcome.decision.decision is SecurityDecisionCode.REQUIRE_CONFIRMATION
    approved = rig.approve(applicant, action)
    awaiting = rig.executor.execute(applicant.model_copy(update={
        "confirmation_id": approved.confirmation_id,
        "confirmation_version": approved.confirmation_version,
    }), action)
    assert awaiting.decision.decision is SecurityDecisionCode.REQUIRE_VERIFICATION
    verified = rig.pass_step_up(applicant, action, approved)
    result = rig.executor.execute(verified, action)
    assert result.decision.decision is SecurityDecisionCode.ALLOW
    assert result.executed is True
    return verified, result.result


def test_order_and_capture_run_the_full_gate_chain(tmp_path):
    """XL-B01: freeze, order, and capture each pass confirmation, step-up
    verification, the executor claim, and the bank authorization callback."""
    from datetime import datetime, timedelta, timezone
    from app.contracts.bank import DeliveryInput
    from app.contracts.common import Category

    rig = PurchaseRig(tmp_path)
    freeze = rig.freeze_action()
    _, frozen = _confirmed_and_verified(rig, freeze, {
        "action_name": "bank.freeze_funds", "account_id": "BA1", "amount_fen": 50000,
    })
    freeze_id = frozen.receipt.freeze_id
    assert frozen.receipt.remaining_fen == 50000

    order = ActionDescriptor(
        action_name="bank.create_order", parameters_ref="birthday:order:flower",
        resource_refs=["p_flower"], phase=Phase.EXECUTION,
    )
    deliver_by = datetime.now(timezone.utc) + timedelta(days=3)
    _, created = _confirmed_and_verified(rig, order, {
        "action_name": "bank.create_order", "product_id": "p_flower", "quantity": 1,
        "expected_total_fen": 19900,
        "delivery": DeliveryInput(recipient_name="李演示", phone="DEMO-PHONE-0001",
                                  address="演示市演示区示例路 1 号（虚构）",
                                  deliver_by=deliver_by),
    })
    order_id = created.receipt.order.order_id
    assert created.receipt.order.payment_status == "unpaid"

    capture = ActionDescriptor(
        action_name="bank.capture_frozen", parameters_ref="birthday:capture:flower",
        resource_refs=[freeze_id], phase=Phase.EXECUTION,
    )
    _, paid = _confirmed_and_verified(rig, capture, {
        "action_name": "bank.capture_frozen", "freeze_id": freeze_id,
        "amount_fen": 19900, "merchant_id": "m_flower", "merchant_name": "邻里花店",
        "purpose": "生日鲜花", "category": Category.SHOPPING,
        "order_id": order_id,
    })
    assert rig.bank_writes == [
        "bank.freeze_funds", "bank.create_order", "bank.capture_frozen",
    ]
    assert rig.bank.store.get_order("U1", order_id)["payment_status"] == "paid"
    freeze_row = rig.bank.store.get_freeze("U1", freeze_id)
    assert (
        freeze_row["original_amount_fen"]
        - freeze_row["captured_total_fen"]
        - freeze_row["released_total_fen"]
    ) == 30100
    assert paid.receipt.remaining_fen == 30100


def test_unconfirmed_or_unverified_paths_write_nothing(tmp_path):
    rig = PurchaseRig(tmp_path)
    action = rig.freeze_action()
    rig.payloads[action.parameters_ref] = {
        "action_name": "bank.freeze_funds", "account_id": "BA1", "amount_fen": 50000,
    }
    applicant = context()
    outcome = rig.executor.execute(applicant, action)
    assert outcome.decision.decision is SecurityDecisionCode.REQUIRE_CONFIRMATION

    approved = rig.approve(applicant, action)
    outcome = rig.executor.execute(applicant.model_copy(update={
        "confirmation_id": approved.confirmation_id,
        "confirmation_version": approved.confirmation_version,
    }), action)
    assert outcome.decision.decision is SecurityDecisionCode.REQUIRE_VERIFICATION
    assert rig.bank_writes == []


def test_parameter_change_invalidates_the_old_approval(tmp_path):
    rig = PurchaseRig(tmp_path)
    action = rig.freeze_action("birthday:freeze:50000")
    rig.payloads[action.parameters_ref] = {
        "action_name": "bank.freeze_funds", "account_id": "BA1", "amount_fen": 50000,
    }
    applicant = context()
    approved = rig.approve(applicant, action)
    verified = rig.pass_step_up(applicant, action, approved)
    outcome = rig.executor.execute(verified, action)
    assert outcome.decision.decision is SecurityDecisionCode.ALLOW

    replay = verified.model_copy(update={"operation_id": uuid4()})
    replayed = rig.executor.execute(replay, action.model_copy(update={
        "parameters_ref": "birthday:freeze:60000",
    }))
    assert replayed.decision.decision is SecurityDecisionCode.BLOCK
    assert "CONFIRMATION_STALE" in replayed.decision.reason_codes
    assert rig.bank_writes == ["bank.freeze_funds"]


def test_cancelled_confirmation_stops_the_action(tmp_path):
    rig = PurchaseRig(tmp_path)
    action = rig.freeze_action()
    rig.payloads[action.parameters_ref] = {
        "action_name": "bank.freeze_funds", "account_id": "BA1", "amount_fen": 50000,
    }
    applicant = context()
    record = rig.confirmations.create(
        applicant, action, rig._prepare_confirmation(applicant, action).display_fields,
    )
    cancelled = rig.confirmations.answer(applicant, ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version, choice="cancel",
    ))
    outcome = rig.executor.execute(applicant.model_copy(update={
        "confirmation_id": cancelled.confirmation_id,
        "confirmation_version": cancelled.confirmation_version,
    }), action)
    assert outcome.decision.decision is SecurityDecisionCode.BLOCK
    assert rig.bank_writes == []


def test_terminated_task_blocks_purchases_but_not_the_limited_release(tmp_path):
    rig = PurchaseRig(tmp_path, task_terminated=True)
    action = rig.freeze_action()
    rig.payloads[action.parameters_ref] = {
        "action_name": "bank.freeze_funds", "account_id": "BA1", "amount_fen": 50000,
    }
    applicant = context()
    approved = rig.approve(applicant, action)
    verified = rig.pass_step_up(applicant, action, approved)
    outcome = rig.executor.execute(verified, action)
    assert outcome.decision.decision is SecurityDecisionCode.BLOCK
    assert "TASK_TERMINATED" in outcome.decision.reason_codes
    assert rig.bank_writes == []

    # The same terminated state still finishes the limited release: an older
    # active authorization from a previous run keeps its funds claim.
    from app.security.birthday_release import LimitedReleaseFinalizer
    _, prior, grant = _preterminated_freeze(rig)
    finalizer = LimitedReleaseFinalizer(
        rig.state,
        decision_sink=lambda _decision: None,
        snapshot_writer=lambda *_args: "AUTH-REL",
        task_state_resolver=lambda _context: True,
        freeze_reader=rig.gateway.get_freeze,
        operation_reader=rig.gateway.get_operation,
        bank_release=lambda t, op, request: rig.gateway.release_frozen(t, op, request),
        clock=rig.clock,
    )
    ending = prior.model_copy(update={
        "session_id": "SYS-CONTROLLED", "operation_id": None, "action_revision": None,
        "release_authorization_id": grant.release_authorization_id,
    })
    result = finalizer.finalize(ending, "user_cancelled")
    assert result.status == "released"
    assert rig.bank.store.get_account("U1", "BA1").frozen_balance_fen == 0


def _preterminated_freeze(rig: PurchaseRig):
    """A freeze that succeeded before the task was terminated."""
    applicant = context(task_id="T0", session_id="S0")
    action = rig.freeze_action()
    rig.payloads.setdefault(action.parameters_ref, {
        "action_name": "bank.freeze_funds", "account_id": "BA1", "amount_fen": 50000,
    })
    approved = rig.approve(applicant, action)
    authorization = grant_release_authorization(
        rig.state, applicant, approved,
        account_id="BA1", amount_fen=50000, now=rig.clock(),
    )
    result = rig.bank.birthday.freeze_funds(
        trusted(applicant), applicant.operation_id, "BA1", 50000, "生日礼物",
    )
    bound = bind_freeze_result(
        rig.state, applicant, authorization.release_authorization_id,
        result, rig.clock(),
    )
    assert bound.status == "active"
    return approved, applicant, bound
