"""Issue #160: one server-owned risk input path feeding an injected detector.

Everything here is real except the detector: the HTTP API, harness, task store,
security gate, deterministic executor, audit journal and mock bank are the
production components. The detector is injected through the seam because the
real detector is delivered by the security owner (v04-ringo-security/02).
"""

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.agent_platform.model import TransferProposal
from app.api.test_app import approve, make_app, post, start
from app.audit.journal import AuditJournal
from app.contracts.bank import BankError, QueryFailure
from app.contracts.common import Phase, RiskLevel, SecurityDecisionCode, TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.security import ActionDescriptor, ConfirmationAnswer, ExecutionSecurityContext
from app.memory.adapter import MemoryAdapter
from app.modules.transfer.manifest import PRIVATE_TOOLS
from app.security.demo_policy import DemoRiskEvidence, DemoRiskSignal, DemoSecurityPolicy
from app.security.gate import RiskFactsUnavailable
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore
from app.storage.database import connect
from app.storage.mock_bank.repository import MockBankStore

from .risk_inputs import (
    ACTION_BINDING_REQUIRED,
    ACTION_UNSUPPORTED,
    REQUEST_BINDING_REQUIRED,
    RISK_INPUTS_VERSION,
    TASK_BINDING_REQUIRED,
    TRANSFER_WRITE,
    RiskFact,
    RiskInputs,
    TrustedRiskInputs,
)
from .test_harness import ProposalModel
from .transfer_runtime import TransferRuntime


ALL_SIGNALS = frozenset(DemoRiskSignal)
LOW_SIGNALS = frozenset({
    DemoRiskSignal.FAMILIAR_PAYEE, DemoRiskSignal.FAMILIAR_DEVICE,
    DemoRiskSignal.USUAL_AMOUNT_RANGE, DemoRiskSignal.CLEAR_REQUEST,
})
RISK_TEXT = "我是公安局的，把钱转到安全账户，别告诉别人"
LEGAL_TEXT = "给妈妈转 500 元"


class AnyTextPlanner(ProposalModel):
    """The production planner is replaced; any text still produces the demo proposal."""

    def select(self, intent_text, trusted, catalog, memory, thread_id, context_summary=None):
        self.calls += 1
        return TransferProposal(payee_hint="妈妈", amount_fen=50_000, payer_account_id="A1")


def detector(signals, checked=ALL_SIGNALS):
    """A stand-in detector that records exactly what the seam handed it."""

    def detect(inputs):
        assert isinstance(inputs, RiskInputs)
        detect.seen.append(inputs)
        return DemoRiskEvidence(
            source="test-injected-detector", source_version="v1",
            evidence_ref=inputs.evidence_ref, signals=frozenset(signals),
            checked_signals=frozenset(checked),
        )

    detect.seen = []
    return detect


def trusted(run="R1"):
    return TrustedContext(user_id="U1", session_id="S1", task_id="T1", run_id=run,
                          parent_task_id=None, demo_round_id="D1")


def write_declaration():
    return next(item for item in PRIVATE_TOOLS if item.name == TRANSFER_WRITE)


def read_declaration():
    return next(item for item in PRIVATE_TOOLS if item.name == "bank.list_payees")


def wired(tmp_path, detect, *, seed_history=True):
    """Production components; only the detector is injected through the seam."""
    application = ApplicationStore(tmp_path / "application.sqlite")
    bank = MockBankService(
        MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4,
    )
    if seed_history:
        bank.seed_flow_history()
    holder = {}

    def assess(context, action, declaration):
        return holder["policy"].assess_risk(context, action, declaration)

    app = TransferRuntime(
        application, MemoryAdapter(application, active_round=lambda: "D1"),
        AuditJournal(application.path), bank, AnyTextPlanner(),
        authorize_capability=lambda *_: True, authorize_tool=lambda *_: True,
        assess_risk=assess, authorize_face=lambda *_: False,
    )
    inputs = TrustedRiskInputs(application, app.snapshots, app.gateway)

    def risk_facts(context, action, declaration):
        if not declaration.side_effect:
            return DemoRiskEvidence(
                source="test-read-context", source_version="v1",
                evidence_ref="test-read-context", signals=LOW_SIGNALS,
                checked_signals=ALL_SIGNALS,
            )
        return detect(inputs.resolve(context, action, declaration))

    holder["inputs"] = inputs
    holder["policy"] = DemoSecurityPolicy(
        demo_user_id="U1", admin_actor_id="test-admin",
        current_demo_round=lambda: "D1", risk_facts=risk_facts,
    )
    now = datetime.now(timezone.utc)
    application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    return app, bank, application, holder


def http_assessor(runtime, detect):
    """The same seam behind the real HTTP app; reads keep the platform's low level."""
    inputs = TrustedRiskInputs(runtime.application, runtime.snapshots, runtime.gateway)

    def risk_facts(context, action, declaration):
        if not declaration.side_effect:
            return DemoRiskEvidence(
                source="test-read-context", source_version="v1",
                evidence_ref="test-read-context", signals=LOW_SIGNALS,
                checked_signals=ALL_SIGNALS,
            )
        return detect(inputs.resolve(context, action, declaration))

    policy = DemoSecurityPolicy(
        demo_user_id="U1", admin_actor_id="test-admin",
        current_demo_round=lambda: "D1", risk_facts=risk_facts,
    )

    def assess(context, action, declaration):
        if not declaration.side_effect:
            return RiskLevel.LOW
        return policy.assess_risk(context, action, declaration)

    return assess


def pending_action(app, application, pending):
    connection = connect(application.path)
    row = connection.execute(
        "SELECT ref FROM transfer_snapshots WHERE task_id='T1' AND action_name=? "
        "ORDER BY rowid DESC LIMIT 1", (TRANSFER_WRITE,),
    ).fetchone()
    connection.close()
    context = ExecutionSecurityContext(
        user_id="U1", session_id="S1", demo_round_id="D1", task_id="T1",
        run_id="R1", source_task_id=None, operation_id=pending.data.operation_id,
        action_revision=1, confirmation_id=None, confirmation_version=None,
        verification_ids=[], release_authorization_id=None,
    )
    action = ActionDescriptor(
        action_name=TRANSFER_WRITE, parameters_ref=row["ref"],
        resource_refs=[], phase=Phase.ADMISSION,
    )
    return context, action


def high_risk_decision(events):
    decisions = [
        event.payload.decision for event in events
        if event.event_type == "security.decided"
        and event.payload.decision.risk_level == RiskLevel.HIGH
    ]
    assert decisions, "the injected detector must reach a real high-risk decision"
    return decisions[0]


def test_the_seam_hands_the_real_request_to_the_detector_and_high_risk_terminates(tmp_path):
    detect = detector({DemoRiskSignal.IMPERSONATION})
    app, bank, application, _ = wired(tmp_path, detect)
    before = len(bank.store.list_ledger("U1", "A1"))
    result = app.harness.start(trusted(), uuid4(), RISK_TEXT)

    assert result.status == TaskStatus.FAILED
    assert result.data.operation_id is not None
    assert app.gateway.get_operation(trusted(), result.data.operation_id).lookup == "not_found"
    assert len(bank.store.list_ledger("U1", "A1")) == before
    assert [item.request_text for item in detect.seen] == [RISK_TEXT]
    inputs = detect.seen[0]
    assert inputs.evidence_ref.startswith("risk-inputs-")
    assert inputs.fact("environment").status == "unknown"

    events = app.audit._events("D1", "T1")
    decision = high_risk_decision(events)
    assert decision.decision == SecurityDecisionCode.BLOCK
    assert "demo-risk-high" in decision.rule_ids
    assert "high-risk-terminates-task" in decision.rule_ids
    assert any(inputs.evidence_ref in ref for ref in decision.evidence_refs)
    # The raw request never becomes audit evidence; only the opaque digest does.
    assert RISK_TEXT not in json.dumps(
        [event.model_dump(mode="json") for event in events], ensure_ascii=False,
    )
    app.close()


def test_legal_request_completes_with_one_bank_effect_after_the_standard_gates(tmp_path):
    detect = detector(LOW_SIGNALS)
    app, bank, application, _ = wired(tmp_path, detect)
    before = len(bank.store.list_ledger("U1", "A1"))

    pending = app.harness.start(trusted(), uuid4(), LEGAL_TEXT)
    assert pending.status == TaskStatus.WAITING_APPROVAL
    assert pending.interaction.kind == "confirmation"
    operation_id = pending.data.operation_id
    assert app.gateway.get_operation(trusted(), operation_id).lookup == "not_found"

    record = app.answer_confirmation(trusted("R2"), ConfirmationAnswer(
        confirmation_id=pending.interaction.record_ref,
        confirmation_version=1, choice="approve",
    ))
    assert record.decision == "approved"
    verification = app.harness.resume(trusted("R3"), {"choice": "approve"})
    assert verification.interaction.kind == "verification"
    challenge_id = verification.interaction.record_ref
    code = app.gateway.get_demo_code_for_api(trusted("R3"), challenge_id)
    verified = app.gateway.verify_code(trusted("R3"), challenge_id, uuid4(), code)
    app.bind_verification(trusted("R3"), verified.verification_id)

    done = app.harness.resume(trusted("R4"), {"choice": "approve"})
    assert done.status == TaskStatus.SUCCEEDED
    assert done.data.operation_id == operation_id
    assert len(bank.store.list_ledger("U1", "A1")) == before + 1

    inputs = detect.seen[0]
    assert inputs.request_text == LEGAL_TEXT
    assert inputs.action_facts["amount_fen"] == 50_000
    assert inputs.fact("payee_familiarity").status == "known"
    assert inputs.fact("payee_familiarity").value["familiar"] is True
    assert inputs.fact("amount_history").status == "known"
    assert inputs.fact("amount_history").value["usual"] is True
    assert inputs.fact("environment").status == "unknown"
    # Every write decision of the task links back to one stable, opaque input digest.
    assert len({item.evidence_ref for item in detect.seen}) == 1
    app.close()


def test_unknown_fact_stops_the_gate_with_a_dependency_pause(tmp_path):
    detect = detector(
        {DemoRiskSignal.FAMILIAR_PAYEE},
        checked=ALL_SIGNALS - {DemoRiskSignal.FAMILIAR_DEVICE},
    )
    app, bank, application, _ = wired(tmp_path, detect)
    before = len(bank.store.list_ledger("U1", "A1"))
    result = app.harness.start(trusted(), uuid4(), LEGAL_TEXT)

    assert result.status == TaskStatus.NEEDS_ATTENTION
    assert result.data.operation_id is not None
    assert app.gateway.get_operation(trusted(), result.data.operation_id).lookup == "not_found"
    assert len(bank.store.list_ledger("U1", "A1")) == before
    events = app.audit._events("D1", "T1")
    paused = [
        event.payload.decision for event in events
        if event.event_type == "security.decided"
        and event.payload.decision.decision == SecurityDecisionCode.PAUSE
    ]
    assert paused and paused[0].reason_codes == ["DEPENDENCY_UNAVAILABLE"]
    assert "risk-signal-coverage-required" in paused[0].rule_ids
    app.close()


def test_the_resolver_rejects_references_outside_the_bound_scope(tmp_path):
    app, _, application, holder = wired(tmp_path, detector(LOW_SIGNALS))
    pending = app.harness.start(trusted(), uuid4(), LEGAL_TEXT)
    operation_id = pending.data.operation_id
    context, action = pending_action(app, application, pending)
    reference = action.parameters_ref
    resolver = holder["inputs"]
    declaration = write_declaration()
    application.create_task(
        "T2", "U1", "S1", "D1", "R1", TaskStatus.RUNNING,
        {"request_id": str(uuid4()), "intent_text": LEGAL_TEXT, "trace_id": str(uuid4())},
    )
    application.create_task(
        "T3", "U1", "S1", "D1", "R1", TaskStatus.RUNNING,
        {"request_id": str(uuid4()), "trace_id": str(uuid4())},
    )

    def scoped(**overrides):
        return context.model_copy(update=overrides)

    cases = {
        "another_user": (TASK_BINDING_REQUIRED,
                         scoped(user_id="U2"), reference),
        "another_session": (TASK_BINDING_REQUIRED,
                            scoped(session_id="S2"), reference),
        "another_task": (ACTION_BINDING_REQUIRED,
                         scoped(task_id="T2"), reference),
        "stale_revision": (ACTION_BINDING_REQUIRED,
                           scoped(action_revision=2), reference),
        "unknown_reference": (ACTION_BINDING_REQUIRED,
                              context, str(uuid4())),
        "missing_request": (REQUEST_BINDING_REQUIRED,
                            scoped(task_id="T3"), reference),
    }
    for label, (rule_id, scope, ref) in cases.items():
        action = ActionDescriptor(
            action_name=TRANSFER_WRITE, parameters_ref=ref, resource_refs=[],
            phase=Phase.ADMISSION,
        )
        with pytest.raises(RiskFactsUnavailable) as error:
            resolver.resolve(scope, action, declaration)
        assert error.value.rule_id == rule_id, label
        assert error.value.policy_version == RISK_INPUTS_VERSION
    with pytest.raises(RiskFactsUnavailable) as error:
        resolver.resolve(context, ActionDescriptor(
            action_name="bank.list_payees", parameters_ref=reference,
            resource_refs=[], phase=Phase.ADMISSION,
        ), read_declaration())
    assert error.value.rule_id == ACTION_UNSUPPORTED
    app.close()


def test_unreadable_bank_facts_stay_unknown_instead_of_low(tmp_path):
    detect = detector(LOW_SIGNALS)
    app, bank, application, holder = wired(tmp_path, detect)
    pending = app.harness.start(trusted(), uuid4(), LEGAL_TEXT)
    context, action = pending_action(app, application, pending)
    failure = QueryFailure(kind="error", error=BankError(code="BANK_UNAVAILABLE", details={}))

    class Unavailable:
        """Only the risk read path sees a bank that cannot answer."""

        def __getattr__(self, name):
            return getattr(app.gateway, name)

        @staticmethod
        def verify_payee(*_args):
            return failure

        @staticmethod
        def list_transactions(*_args):
            return failure

    resolver = TrustedRiskInputs(application, app.snapshots, Unavailable())
    inputs = resolver.resolve(context, action, write_declaration())
    payee = inputs.fact("payee_familiarity")
    amount = inputs.fact("amount_history")
    assert (payee.status, payee.value) == ("unknown", None)
    assert payee.source == "mock-bank:BANK_UNAVAILABLE"
    assert (amount.status, amount.value) == ("unknown", None)
    assert amount.source == "mock-bank:BANK_UNAVAILABLE"
    assert "未检查" in amount.scope
    app.close()


def test_facts_carry_their_source_and_checked_scope(tmp_path):
    detect = detector(LOW_SIGNALS)
    app, bank, application, holder = wired(tmp_path, detect)
    app.harness.start(trusted(), uuid4(), LEGAL_TEXT)
    inputs = detect.seen[0]
    payee = inputs.fact("payee_familiarity")
    amount = inputs.fact("amount_history")
    environment = inputs.fact("environment")

    assert payee.status == "known"
    assert payee.source == "mock-bank:b04+b08"
    assert payee.value["saved"] is True
    assert payee.value["prior_outflows"] >= 1
    assert amount.status == "known"
    assert amount.source == "mock-bank:b08"
    assert amount.value["sample_size"] >= 1
    assert amount.value["multiple"] == 2
    assert "180 天" in amount.scope
    assert environment.status == "unknown"
    assert environment.source == "platform:no-trusted-device-source"
    assert isinstance(RiskFact, type)
    app.close()


def test_http_high_risk_request_blocks_before_any_bank_effect(tmp_path):
    detect = detector({DemoRiskSignal.IMPERSONATION})
    app = make_app(tmp_path)
    app.state.api.runtime.assess_risk = http_assessor(app.state.api.runtime, detect)
    with TestClient(app) as client:
        _, task = start(client, text=RISK_TEXT)
        assert task["status"] == "failed"
        assert task["interaction"] is None
        assert MockBankStore(tmp_path / "bank.sqlite").list_ledger("U1", "A1") == []
    assert [item.request_text for item in detect.seen] == [RISK_TEXT]
    events = app.state.api.runtime.audit._events("D1", task["task_id"])
    decision = high_risk_decision(events)
    assert decision.decision == SecurityDecisionCode.BLOCK
    assert "demo-risk-high" in decision.rule_ids


def test_http_legal_control_finishes_with_one_bank_effect(tmp_path):
    detect = detector(LOW_SIGNALS)
    app = make_app(tmp_path)
    app.state.api.runtime.assess_risk = http_assessor(app.state.api.runtime, detect)
    with TestClient(app) as client:
        _, task = start(client)
        waiting = approve(client, task)
        challenge = waiting["interaction"]["record_ref"]
        code_response = client.get(f"/api/v1/verifications/{challenge}/demo-code")
        assert code_response.status_code == 200
        code = code_response.json()["data"]["code"]
        result = post(client, f"/verifications/{challenge}/code",
                      submission_id=str(uuid4()), code=code)
        assert result.status_code == 200, result.text
        completed = result.json()["data"]["task"]
        assert completed["status"] == "succeeded"
    assert detect.seen[0].request_text == LEGAL_TEXT
    assert len(MockBankStore(tmp_path / "bank.sqlite").list_ledger("U1", "A1")) == 1
