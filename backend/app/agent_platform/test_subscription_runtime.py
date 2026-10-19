"""Scenario 05 through the platform composition: real mock bank B29/B30, real gate.

The only stand-in here is the model entry (``RoutedPlanner``): this ticket wires the
platform and does not run a live GLM call. Everything else is the production path —
``MockBankService`` with its seeded mandates and flows, ``SecurityGate``,
``DeterministicExecutor``, ``ConfirmationService`` and ``DemoSecurityPolicy``.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from app.audit.journal import AuditJournal
from app.contracts.common import Phase, RiskLevel, SecurityDecisionCode, TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.security import ActionDescriptor, ConfirmationAnswer, ExecutionSecurityContext
from app.contracts.subscription import SubscriptionTaskView
from app.memory.adapter import MemoryAdapter
from app.modules.subscription.reads import PRIVATE_TOOLS as SUBSCRIPTION_PRIVATE_TOOLS
from app.security import SecurityError
from app.security.demo_policy import DemoRiskEvidence, DemoRiskSignal, DemoSecurityPolicy
from app.security.gate import RiskFactsUnavailable
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore
from app.storage.database import connect
from app.storage.mock_bank.repository import MockBankStore

from .model import TransferProposal
from .subscription_runtime import CANCEL_TOOL, register_subscription, subscription_risk_evidence
from .transfer_runtime import TransferRuntime


NOW = datetime(2026, 10, 19, 4, 0, tzinfo=timezone.utc)
CANCEL_CAPABILITY = "subscription.cancel_subscription"
LIST_CAPABILITY = "subscription.list_subscriptions"
ROUTINE_SIGNALS = frozenset({
    DemoRiskSignal.FAMILIAR_PAYEE, DemoRiskSignal.FAMILIAR_DEVICE,
    DemoRiskSignal.USUAL_AMOUNT_RANGE, DemoRiskSignal.CLEAR_REQUEST,
})
ALL_SIGNALS = frozenset(DemoRiskSignal)
FORBIDDEN_CANCEL_WORDS = ("会员可用至", "还能用到", "先退订再重新订阅", "先解约再重签")
# The bank's demo code is always six digits starting at 1, so this is never the code.
WRONG_CODE = "000000"


def trusted(task="T1", run="R1", session="S1"):
    return TrustedContext(user_id="U1", session_id=session, task_id=task, run_id=run,
                          parent_task_id=None, demo_round_id="D1")


class RoutedPlanner:
    """Scripted model entry: routes to the capability the test asks for."""

    provider = "scripted"
    model_name = "subscription-test"
    config_version = "test-v1"

    def __init__(self, capability=LIST_CAPABILITY):
        self.capability = capability
        self.calls = 0

    def select(self, intent_text, trusted, catalog, memory, thread_id, context_summary=None):
        self.calls += 1
        return TransferProposal(capability_name=self.capability)


def open_session(application, session_id="S1"):
    at = datetime.now(timezone.utc)
    application.create_session(session_id, "U1", "D1", at.isoformat(),
                               (at + timedelta(days=1)).isoformat())


def composition(tmp_path):
    """Real runtime + real fixed-clock bank + the real demo policy for scenario 05."""

    path = tmp_path / "application.sqlite"
    application = ApplicationStore(path)
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4,
                           clock=lambda: NOW)
    bank.seed_flow_history()
    wiring: dict = {}
    read_evidence = DemoRiskEvidence(
        source="server-test-fixture", source_version="facts-v1", evidence_ref="read",
        signals=ROUTINE_SIGNALS, checked_signals=ALL_SIGNALS,
    )

    def risk_facts(context, action, declaration):
        if not declaration.side_effect:
            return read_evidence
        if declaration.name == CANCEL_TOOL:
            subscription = wiring.get("subscription")
            payload = (subscription.binding(context.task_id, action.parameters_ref)
                       if subscription is not None else None)
            return subscription_risk_evidence(
                payload, source_version="facts-v1", checked_signals=ALL_SIGNALS,
            )
        raise RiskFactsUnavailable("no server-owned fixture covers this write",
                                   rule_id="test-fixture-required",
                                   policy_version=DemoSecurityPolicy.policy_version)

    policy = DemoSecurityPolicy(
        demo_user_id="U1", admin_actor_id="demo-admin", current_demo_round=lambda: "D1",
        risk_facts=risk_facts,
    )
    planner = RoutedPlanner()
    app = TransferRuntime(
        application, memory, AuditJournal(path), bank, planner,
        authorize_capability=policy.authorize_capability,
        authorize_tool=policy.authorize_tool, assess_risk=policy.assess_risk,
        authorize_face=policy.authorize_face,
    )
    wiring["subscription"] = register_subscription(app, clock=bank.clock)
    open_session(application)
    return app, bank, planner


def start(app, planner, text, *, task="T1", run="R1", capability=CANCEL_CAPABILITY):
    planner.capability = capability
    return app.harness.start(trusted(task, run), uuid4(), text)


def pending_binding(app, task_id):
    connection = connect(app.application.path)
    try:
        row = connection.execute(
            "SELECT operation_id, action_revision FROM agent_transfer_confirmations WHERE task_id = ?",
            (task_id,),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    return UUID(row["operation_id"]), row["action_revision"]


def confirmation_for(app, owner, pending=None):
    operation_id, revision = pending_binding(app, owner.task_id)
    context = app._context(owner, operation_id, revision)
    assert context.confirmation_id is not None
    record = app.confirmations.get(context, context.confirmation_id)
    if pending is not None:
        assert pending.interaction.record_ref == record.confirmation_id
    return record


def approve(app, owner, pending):
    record = confirmation_for(app, owner, pending)
    assert record.decision == "pending"
    app.answer_confirmation(owner, ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version, choice="approve",
    ))
    return record


def verify_by_code(app, owner, challenge_id):
    code = app.gateway.get_demo_code_for_api(owner, challenge_id)
    return app.gateway.verify_code(owner, challenge_id, uuid4(), code)


def mandate(bank, mandate_id):
    response = bank.list_subscriptions("U1")
    assert response.kind == "ok"
    return next(item for item in response.data.mandates if item.mandate_id == mandate_id)


def bank_operations(bank):
    connection = connect(bank.store.path)
    try:
        return connection.execute("SELECT COUNT(*) FROM bank_operations").fetchone()[0]
    finally:
        connection.close()


def security_confirmations(app, task_id):
    connection = connect(app.application.path)
    try:
        return connection.execute(
            "SELECT COUNT(*) FROM security_confirmations WHERE task_id = ?", (task_id,),
        ).fetchone()[0]
    finally:
        connection.close()


def events(app, task_id="T1"):
    return app.audit._events("D1", task_id)


def cancel_to_success(app, planner, text, *, task="T1", runs=("R1", "R2", "R3")):
    started = start(app, planner, text, task=task, run=runs[0])
    assert started.status == TaskStatus.WAITING_APPROVAL, started.error
    approve(app, trusted(task, runs[0]), started)
    verification = app.harness.resume(trusted(task, runs[1]), {"choice": "approve"})
    assert verification.interaction.kind == "verification", verification.error
    verified = verify_by_code(app, trusted(task, runs[1]), verification.interaction.record_ref)
    assert verified.verification_id is not None
    app.bind_verification(trusted(task, runs[1]), verified.verification_id)
    return app.harness.resume(trusted(task, runs[2]), {})


# --------------------------------------------------------------------------- SF01


def test_sf01_inventory_separates_facts_and_lists_the_next_30_days(tmp_path):
    app, bank, planner = composition(tmp_path)
    result = start(app, planner, "帮我查查有哪些自动扣费", capability=LIST_CAPABILITY)

    assert result.status == TaskStatus.SUCCEEDED, result.error
    view = result.data
    assert isinstance(view, SubscriptionTaskView) and view.action == "list"
    listed = {item.subscription_id: item for item in view.list_result.items}
    assert {"sub_001", "sub_002", "sub_003"} <= set(listed)
    youku = listed["sub_001"]
    assert (youku.merchant_name, youku.amount_fen, youku.status) == ("优酷视频", 2500, "active")
    assert (youku.billed_count, youku.billed_total_fen) == (6, 15000)
    assert (listed["sub_002"].billed_count, listed["sub_003"].status) == (3, "cancelled")
    # The shared demo ledger carries other monthly fixed-amount payments (rent, utilities,
    # canteen, bus), so the clue zone is every flow-only series the contract rules match —
    # not just the fitness one. The platform test pins the rules' behaviour, not a count.
    clues = [item for item in view.list_result.items if item.source_type == "suspected_ledger"]
    oasis = next(item for item in clues if item.merchant_name == "绿洲健身")
    assert (oasis.amount_fen, oasis.billed_count, oasis.can_cancel_in_bank) == (3900, 5, False)
    assert all(item.can_cancel_in_bank is False and item.status == "suspected" for item in clues)
    assert [item.subscription_id for item in view.list_result.items
            if item.source_type == "mandate"] == ["sub_001", "sub_002", "sub_003"]

    assert view.list_result.active_count == 2
    assert [item.subscription_id for item in view.list_result.upcoming_renewals] == ["sub_001", "sub_002"]
    assert view.list_result.upcoming_total_fen == 6400
    assert view.list_result.suspected_scan_status == "evaluated"
    assert "7 天内会扣款" in result.message
    assert "往后 30 天里还有 2 笔会自动扣" in result.message
    assert "一共 64.00 元" in result.message
    # every read went through the shared gate and executor, never the bank tables.
    assert any(event.event_type == "tool.started"
               and event.payload.tool_name == "subscription.bank.list_subscriptions"
               and event.module == "subscription" for event in events(app))
    assert bank_operations(bank) == 0


# --------------------------------------------------------------------------- SF02


def test_sf02_cancel_is_confirmed_then_session_code_then_bank_receipt(tmp_path):
    app, bank, planner = composition(tmp_path)
    started = start(app, planner, "把优酷视频自动扣费退了")

    assert started.status == TaskStatus.WAITING_APPROVAL, started.error
    assert started.interaction.kind == "confirmation"
    assert started.data is None
    record = confirmation_for(app, trusted(), started)
    fields = {field.name: field.value_text for field in record.display_fields}
    assert list(fields) == ["merchant", "account", "amount", "billed", "next_billing", "notice"]
    assert fields["merchant"] == "优酷视频（优酷 VIP 连续包月）"
    assert fields["amount"] == "每月 25.00 元"
    assert fields["billed"] == "已经扣了 6 次，共 150.00 元"
    expected_stop = (NOW + timedelta(days=5)).replace(
        hour=9, minute=0, second=0, microsecond=0).date().isoformat()
    assert fields["next_billing"] == expected_stop
    assert f"从下一期（{expected_stop}）起不再自动扣费" in fields["notice"]
    assert "之前已经扣掉的钱不退" in fields["notice"]
    assert not any(word in fields["notice"] for word in FORBIDDEN_CANCEL_WORDS)
    assert bank_operations(bank) == 0 and mandate(bank, "sub_001").status == "active"

    approve(app, trusted(), started)
    verification = app.harness.resume(trusted(run="R2"), {"choice": "approve"})
    assert verification.status == TaskStatus.WAITING_APPROVAL
    assert verification.interaction.kind == "verification"
    challenge = app.gateway.get_verification(trusted(run="R2"), verification.interaction.record_ref)
    assert challenge.purpose == "basic_identity"
    assert challenge.required_methods == ["code"]
    assert challenge.summary is None
    assert bank_operations(bank) == 0

    verified = verify_by_code(app, trusted(run="R2"), challenge.challenge_id)
    assert verified.verification_id is not None
    verification_record = app.gateway.get_verification_record(
        trusted(run="R2"), verified.verification_id)
    assert (verification_record.scope, verification_record.methods) == ("session", ["code"])
    app.bind_verification(trusted(run="R2"), verified.verification_id)

    done = app.harness.resume(trusted(run="R3"), {})
    assert done.status == TaskStatus.SUCCEEDED, done.error
    view = done.data
    assert view.action == "cancel"
    assert view.selected_item.subscription_id == "sub_001"
    assert view.selected_item.status == "cancelled"
    receipt = view.operation.receipt
    assert receipt.mandate_id == "sub_001"
    assert receipt.status == "cancelled"
    assert receipt.effective_stop_at.date().isoformat() == expected_stop
    assert receipt.effective_stop_at == receipt.previous_next_billing_at
    assert view.operation.operation_status == "succeeded"
    assert "从下一期" in done.message
    assert not any(word in done.message for word in FORBIDDEN_CANCEL_WORDS)
    assert mandate(bank, "sub_001").status == "cancelled"
    assert bank_operations(bank) == 1
    assert any(event.event_type == "security.decided"
               and event.payload.decision.phase == Phase.EXECUTION
               and event.payload.decision.decision == SecurityDecisionCode.ALLOW
               for event in events(app))
    assert any(event.event_type == "tool.finished"
               and event.payload.operation_id is not None and event.outcome == "succeeded"
               for event in events(app))


# --------------------------------------------------------------------------- SF03


def test_sf03_second_cancel_in_the_same_session_reuses_the_basic_identity(tmp_path):
    app, bank, planner = composition(tmp_path)
    first = cancel_to_success(app, planner, "把优酷视频自动扣费退了")
    assert first.status == TaskStatus.SUCCEEDED, first.error
    first_verification = app.gateway.list_verifications(trusted(), "T1")
    assert len([item for item in first_verification if item.challenge_status == "passed"]) == 1

    second = start(app, planner, "再把云端网盘自动续费退了", task="T2", run="R10")
    assert second.status == TaskStatus.WAITING_APPROVAL
    assert second.interaction.kind == "confirmation"
    approve(app, trusted("T2", "R10"), second)

    done = app.harness.resume(trusted("T2", "R11"), {"choice": "approve"})
    assert done.status == TaskStatus.SUCCEEDED, done.error
    assert done.data.selected_item.subscription_id == "sub_002"
    # No new challenge: the answered confirmation plus the session verification sufficed.
    assert app.gateway.list_verifications(trusted("T2", "R11"), "T2") == []
    assert mandate(bank, "sub_001").status == "cancelled"
    assert mandate(bank, "sub_002").status == "cancelled"
    assert bank_operations(bank) == 2


# --------------------------------------------------------------------------- SF04


def test_sf04_flow_only_clue_is_guided_outside_without_gate_or_bank_call(tmp_path):
    app, bank, planner = composition(tmp_path)
    result = start(app, planner, "帮我把绿洲健身的每月扣款退订")

    assert result.status == TaskStatus.SUCCEEDED, result.error
    assert result.interaction is None
    item = result.data.selected_item
    assert (item.source_type, item.merchant_name, item.can_cancel_in_bank) == (
        "suspected_ledger", "绿洲健身", False)
    assert "微信支付/支付宝" in result.message
    assert "绿洲健身" in result.message
    assert security_confirmations(app, "T1") == 0
    assert bank_operations(bank) == 0
    assert mandate(bank, "sub_001").status == "active"


# --------------------------------------------------------------------------- SF05


def test_sf05_batch_request_is_refused_and_one_choice_then_confirms(tmp_path):
    app, bank, planner = composition(tmp_path)
    started = start(app, planner, "把所有自动扣费都关了")

    assert started.status == TaskStatus.WAITING_INPUT
    assert started.interaction.kind == "input"
    assert [option.id for option in started.interaction.options] == ["sub_001", "sub_002"]
    assert "每次只能退订一项" in started.message
    assert security_confirmations(app, "T1") == 0
    assert bank_operations(bank) == 0

    chosen = app.harness.resume(trusted(run="R2"), {"selected_option_id": "sub_001"})
    assert chosen.status == TaskStatus.WAITING_APPROVAL, chosen.error
    assert chosen.interaction.kind == "confirmation"
    fields = {field.name: field.value_text
              for field in confirmation_for(app, trusted("T1", "R2"), chosen).display_fields}
    assert fields["merchant"].startswith("优酷视频")
    assert bank_operations(bank) == 0


# --------------------------------------------------------------------------- SF06


def test_sf06_already_cancelled_mandate_is_idempotent(tmp_path):
    app, bank, planner = composition(tmp_path)
    result = start(app, planner, "把喜马拉雅自动续费退了")

    assert result.status == TaskStatus.SUCCEEDED, result.error
    assert result.data.selected_item.subscription_id == "sub_003"
    assert "此前已经退订" in result.message
    assert security_confirmations(app, "T1") == 0
    assert bank_operations(bank) == 0


def test_sf06_user_cancel_changes_nothing_at_the_bank(tmp_path):
    app, bank, planner = composition(tmp_path)
    started = start(app, planner, "把优酷视频自动扣费退了")
    assert started.status == TaskStatus.WAITING_APPROVAL

    cancelled = app.harness.resume(trusted(run="R2"), {"cancel": True})
    assert cancelled.status == TaskStatus.CANCELLED
    assert mandate(bank, "sub_001").status == "active"
    assert bank_operations(bank) == 0


def test_sf06_three_wrong_codes_end_the_task_without_a_bank_call(tmp_path):
    app, bank, planner = composition(tmp_path)
    started = start(app, planner, "把优酷视频自动扣费退了")
    approve(app, trusted(), started)
    verification = app.harness.resume(trusted(run="R2"), {"choice": "approve"})
    challenge_id = verification.interaction.record_ref

    for attempt in range(3):
        outcome = app.gateway.verify_code(trusted(run="R2"), challenge_id, uuid4(), WRONG_CODE)
        assert outcome.verification_id is None
        assert outcome.challenge.consecutive_code_failures == attempt + 1
    assert outcome.challenge.challenge_status == "failed"

    failed = app.harness.resume(trusted(run="R3"), {"choice": "approve"})
    assert failed.status == TaskStatus.FAILED
    assert failed.error.source == "security"
    assert failed.error.upstream_code == "VERIFICATION_FAILED"
    assert mandate(bank, "sub_001").status == "active"
    assert bank_operations(bank) == 0
    assert any(event.event_type == "security.decided"
               and event.payload.decision.reason_codes == ["VERIFICATION_FAILED"]
               for event in events(app))
    assert app.harness.resume(trusted(run="R4"), {}).status == TaskStatus.FAILED


def test_sf06_coercion_signal_blocks_before_any_bank_change(tmp_path):
    app, bank, planner = composition(tmp_path)
    result = start(app, planner, "客服让我共享屏幕，赶紧把优酷视频退了")

    assert result.status == TaskStatus.FAILED
    assert result.error.code == "HIGH_RISK_BLOCKED"
    assert result.error.source == "security"
    assert result.error.upstream_code == "HIGH_RISK"
    assert security_confirmations(app, "T1") == 0
    assert bank_operations(bank) == 0
    assert mandate(bank, "sub_001").status == "active"
    assert any(event.event_type == "security.decided"
               and event.payload.decision.decision == SecurityDecisionCode.BLOCK
               and event.payload.decision.reason_codes == ["HIGH_RISK"]
               for event in events(app))


# ------------------------------------------------------- failure paths of the gate


def test_non_low_risk_never_downgrades_to_a_session_basic_identity(tmp_path):
    """Defence in depth: the demo policy keeps cancellations low risk, but a non-LOW
    level must still ask for the action-scoped step-up, never the session code alone."""

    app, bank, planner = composition(tmp_path)
    app.assess_risk = lambda *_: RiskLevel.MEDIUM
    started = start(app, planner, "把优酷视频自动扣费退了")
    assert started.status == TaskStatus.WAITING_APPROVAL, started.error
    approve(app, trusted(), started)

    verification = app.harness.resume(trusted(run="R2"), {"choice": "approve"})
    assert verification.status == TaskStatus.WAITING_APPROVAL, verification.error
    challenge = app.gateway.get_verification(
        trusted(run="R2"), verification.interaction.record_ref)
    assert challenge.purpose == "action_step_up"
    assert challenge.required_methods == ["code", "mock_face"]
    assert challenge.summary is not None
    assert challenge.summary.amount_fen == 2500
    assert challenge.summary.payee is None
    assert [field.name for field in challenge.summary.display_fields] == [
        "merchant", "account", "amount", "billed", "next_billing", "notice"]
    assert bank_operations(bank) == 0


def test_session_recovery_re_enters_the_gate_with_fresh_facts(tmp_path):
    app, bank, planner = composition(tmp_path)
    started = start(app, planner, "把优酷视频自动扣费退了")
    approve(app, trusted(), started)
    verification = app.harness.resume(trusted(run="R2"), {"choice": "approve"})
    verified = verify_by_code(app, trusted(run="R2"), verification.interaction.record_ref)
    app.bind_verification(trusted(run="R2"), verified.verification_id)

    open_session(app.application, "S2")
    current = trusted(run="R3", session="S2")
    recovered = app.harness.recover_session(current)

    assert recovered.status == TaskStatus.WAITING_APPROVAL, recovered.error
    assert recovered.interaction.kind == "confirmation"
    fresh = confirmation_for(app, current, recovered)
    assert fresh.confirmation_version == 2 and fresh.decision == "pending"
    # The previous login's session verification grants nothing to the new session.
    assert app._context(current, *pending_binding(app, "T1")).verification_ids == []
    assert bank_operations(bank) == 0
    assert mandate(bank, "sub_001").status == "active"


def test_audit_failure_before_the_decision_stops_the_write(tmp_path):
    app, bank, planner = composition(tmp_path)
    started = start(app, planner, "把优酷视频自动扣费退了")
    approve(app, trusted(), started)
    verification = app.harness.resume(trusted(run="R2"), {"choice": "approve"})
    verified = verify_by_code(app, trusted(run="R2"), verification.interaction.record_ref)
    app.bind_verification(trusted(run="R2"), verified.verification_id)

    append = app.audit.append_in_transaction

    def unavailable(connection, event, **kwargs):
        decision = getattr(event.payload, "decision", None)
        if (event.event_type == "security.decided" and decision is not None
                and decision.action_name == CANCEL_TOOL):
            raise RuntimeError("audit unavailable")
        return append(connection, event, **kwargs)

    with patch.object(app.audit, "append_in_transaction", side_effect=unavailable):
        result = app.harness.resume(trusted(run="R3"), {"choice": "approve"})

    assert result.status == TaskStatus.FAILED
    assert result.error.code == "SECURITY_REJECTED"
    assert result.error.source == "security"
    assert mandate(bank, "sub_001").status == "active"
    assert bank_operations(bank) == 0


def test_changed_bank_facts_cannot_reuse_the_answered_confirmation(tmp_path):
    app, bank, planner = composition(tmp_path)
    started = start(app, planner, "把优酷视频自动扣费退了")
    approving = approve(app, trusted(), started)
    _, original_revision = pending_binding(app, "T1")

    original = bank.list_subscriptions

    def tampered(user_id, account_id=None, status=None):
        response = original(user_id, account_id, status)
        if response.kind != "ok":
            return response
        mandates = [item.model_copy(update={"amount_fen": item.amount_fen + 100})
                    if item.mandate_id == "sub_001" else item
                    for item in response.data.mandates]
        data = response.data.model_copy(update={"mandates": mandates})
        return response.model_copy(update={"data": data})

    with patch.object(bank, "list_subscriptions", side_effect=tampered):
        result = app.harness.resume(trusted(run="R2"), {"choice": "approve"})

    assert result.status != TaskStatus.SUCCEEDED
    assert mandate(bank, "sub_001").status == "active"
    assert bank_operations(bank) == 0
    if result.status == TaskStatus.WAITING_APPROVAL:
        current = confirmation_for(app, trusted("T1", "R2"))
        assert current.decision == "pending"
        assert current.action_revision != original_revision
        with pytest.raises(SecurityError):
            # The answered version of the old facts is no longer current.
            app.answer_confirmation(trusted("T1", "R2"), ConfirmationAnswer(
                confirmation_id=approving.confirmation_id,
                confirmation_version=approving.confirmation_version, choice="approve",
            ))


# ------------------------------------------------------------------ platform wiring


def test_local_demo_registers_scenario_05_and_keeps_its_risk_facts_fail_closed(tmp_path):
    from . import local_demo
    from .test_local_demo import ConnectorTestModel, configuration

    config = configuration(tmp_path)
    with patch.object(local_demo, "ChatOpenAI", return_value=ConnectorTestModel()):
        runtime = local_demo.build_runtime(config)

    names = {item["name"] for item in runtime.harness.registry.public_catalog()}
    assert {LIST_CAPABILITY, CANCEL_CAPABILITY} <= names
    wiring = runtime.subscription
    assert wiring is not None and runtime.authorize_cancel is not None
    # No live security claim: B30 stays closed instead of trusting the caller.
    denied = runtime.gateway.cancel_subscription(trusted(), uuid4(), "sub_001")
    assert denied.error.code == "ACCESS_DENIED"

    declaration = next(item for item in SUBSCRIPTION_PRIVATE_TOOLS if item.name == CANCEL_TOOL)
    context = ExecutionSecurityContext(
        user_id="U1", session_id="S1", demo_round_id="D1", task_id="T1", run_id="R1",
        source_task_id=None, operation_id=uuid4(), action_revision=1,
        confirmation_id="conf-1", confirmation_version=1, verification_ids=[],
        release_authorization_id=None,
    )
    action = ActionDescriptor(action_name=CANCEL_TOOL, parameters_ref="sub-ref-test",
                              resource_refs=[], phase=Phase.ADMISSION)
    facts = {"mandate_id": "sub_001", "amount_fen": 2500, "risk_observations": []}
    wiring._remember(context, CANCEL_TOOL, "sub-ref-test", facts)
    assert runtime.assess_risk(context, action, declaration).risk_level == RiskLevel.LOW

    wiring._remember(context, CANCEL_TOOL, "sub-ref-test", {
        **facts, "risk_observations": ["screen_sharing", "third_party_instruction"]})
    assert runtime.assess_risk(context, action, declaration).risk_level == RiskLevel.HIGH

    wiring._remember(context, CANCEL_TOOL, "sub-ref-test",
                     {**facts, "risk_observations": ["unheard_of_signal"]})
    with pytest.raises(RiskFactsUnavailable):
        runtime.assess_risk(context, action, declaration)
    with pytest.raises(RiskFactsUnavailable):
        runtime.assess_risk(
            context, action.model_copy(update={"parameters_ref": "sub-ref-missing"}), declaration)


def test_planner_prompt_states_scenario_05_routing_only_when_registered(tmp_path):
    from app.modules.subscription.entry import register_subscription as register_module
    from app.modules.transfer.manifest import MANIFEST
    from pydantic import Field

    from .harness import AgentHarness
    from .model import DeepAgentPlanner, ModelSettings
    from .registry import CapabilityRegistry
    from .test_harness import ScriptedChatModel

    class PromptRecordingModel(ScriptedChatModel):
        model_name: str = "routing-test"
        prompts: list[str] = Field(default_factory=list)

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            self.prompts.append(str(messages[0].content))
            return super()._generate(messages, stop, run_manager, **kwargs)

    application = ApplicationStore(tmp_path / "app.sqlite")
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    registry = CapabilityRegistry()
    registry.register_transfer(MANIFEST, lambda *_: None)
    model = PromptRecordingModel()
    planner = DeepAgentPlanner(ModelSettings(model, "scripted", model.model_name, "test-v1"))
    harness = AgentHarness(application, memory, AuditJournal(application.path), registry, planner,
                           lambda *_: True)
    open_session(application)

    harness.understand(trusted(), "我都在哪自动扣钱")
    assert CANCEL_CAPABILITY not in model.prompts[-1]
    assert "代扣与订阅" not in model.prompts[-1]

    register_module(registry, lambda *_: None, lambda: NOW)
    harness.understand(trusted(), "我都在哪自动扣钱")
    prompt = model.prompts[-1]
    assert LIST_CAPABILITY in prompt and CANCEL_CAPABILITY in prompt
    assert "按退订处理" in prompt
