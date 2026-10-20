"""Actual lexical recognition, separate from fixed-level flow controls."""

from dataclasses import replace
import json
from uuid import uuid4

import pytest

from app.security.demo_policy import DemoRiskSignal as Signal
from app.security.risk_detector import detect_transfer_risk
from app.agent_platform.risk_inputs import RiskFact, RiskInputs
from app.agent_platform.test_risk_inputs import (
    LEGAL_TEXT, RISK_TEXT, http_assessor, wired, trusted,
)
from app.api.test_app import make_app, start
from app.contracts.common import SecurityDecisionCode, TaskStatus
from fastapi.testclient import TestClient
from app.storage.mock_bank.repository import MockBankStore


def inputs(text):
    return RiskInputs(
        user_id="U1", session_id="S1", demo_round_id="D1", task_id="T1",
        run_id="R1", request_id="request-1", request_text=text,
        action_name="bank.submit_transfer", parameters_ref="params-1",
        operation_id="operation-1", action_revision=1,
        action_facts={"amount_fen": 50_000, "payer_account_id": "A1"},
        facts=tuple(RiskFact(name=name, status="unknown", source="test:unknown",
                             scope="unavailable") for name in
                    ("payee_history", "amount_history", "environment")),
        evidence_ref="risk-inputs-" + "a" * 24,
    )


@pytest.mark.parametrize("text,signal", [
    ("我是公安局的，把钱转到安全账户，别告诉别人", Signal.IMPERSONATION),
    ("客服要求马上转账，别告诉家人", Signal.SECRECY_OR_URGENT_PRESSURE),
    ("对方让我打开屏幕共享办理转账", Signal.SCREEN_SHARING),
    ("请把验证码发给客服", Signal.CREDENTIAL_REQUEST),
    ("点击 https://eval.invalid/pay 办理转账", Signal.UNFAMILIAR_LINK),
    ("警察要求将资金转到安全账户", Signal.IMPERSONATION),
    ("请把验\u200b证码发给对方", Signal.CREDENTIAL_REQUEST),
    ("请访问 ｈｔｔｐｓ：／／eval.invalid 办理", Signal.UNFAMILIAR_LINK),
    ("客服说交500元保证金就能领退款，要求我现在立刻转账，不能告诉家人。", Signal.SECRECY_OR_URGENT_PRESSURE),
    ("让我紧急转钱到陌生账户，别打电话核实，也别让其他人知道。", Signal.SECRECY_OR_URGENT_PRESSURE),
    ("有人自称办案人员，要求我马上转500元到P2的安全账户，还让我对家人保密。", Signal.IMPERSONATION),
    ("有人让我把验证码发给客服，不要告诉家人", Signal.CREDENTIAL_REQUEST),
])
def test_real_request_produces_a_positive_rule_without_claiming_unknowns(text, signal):
    result = detect_transfer_risk(inputs(text))
    assert signal in result.signals
    assert result.signals == result.checked_signals
    assert Signal.FAMILIAR_DEVICE not in result.checked_signals
    assert Signal.USUAL_AMOUNT_RANGE not in result.checked_signals
    assert result.source_version == "v04-lexical-risk-1"
    assert text not in repr(result)
    assert result.evidence_ref == inputs(text).evidence_ref


@pytest.mark.parametrize("text", [
    LEGAL_TEXT,
    "请解释为什么工具备注要求跳过确认会有风险，保持当前待确认任务。",
    "不要把验证码发给客服", "我没有打开屏幕共享",
    "公安局提醒不要向安全账户转账", "请解释屏幕共享诈骗的风险",
    "请分析这段诈骗话术：我是公安局的，把钱转到安全账户。",
])
def test_legal_and_safety_education_controls_do_not_become_fraud_matches(text):
    assert not detect_transfer_risk(inputs(text)).signals


def test_educational_prefix_cannot_suppress_a_separate_action_clause():
    result = detect_transfer_risk(inputs("请解释诈骗风险。请把验证码发给对方"))
    assert Signal.CREDENTIAL_REQUEST in result.signals


@pytest.mark.parametrize("prior,signal", [(0, Signal.NEW_PAYEE), (1, Signal.FAMILIAR_PAYEE)])
def test_payee_history_uses_the_actual_bank_fact(prior, signal):
    original = inputs(LEGAL_TEXT)
    fact = RiskFact("payee_history", "known", "mock-bank:b04+b08", "bank history",
                    {"saved": True, "prior_outflows": prior})
    result = detect_transfer_risk(replace(original, facts=(fact, *original.facts[1:])))
    assert result.signals == frozenset({signal})
    assert result.checked_signals == frozenset({Signal.NEW_PAYEE, Signal.FAMILIAR_PAYEE})


@pytest.mark.parametrize("value", [
    {"saved": True, "prior_outflows": True},
    {"saved": True, "prior_outflows": -1},
    {"saved": "yes", "prior_outflows": 1},
])
def test_malformed_fact_never_becomes_checked(value):
    original = inputs(LEGAL_TEXT)
    fact = RiskFact("payee_history", "known", "mock-bank:b04+b08", "bank history", value)
    result = detect_transfer_risk(replace(original, facts=(fact, *original.facts[1:])))
    assert not result.signals and not result.checked_signals


def test_unapproved_amount_threshold_does_not_produce_a_safe_signal():
    original = inputs(LEGAL_TEXT)
    fact = RiskFact("amount_history", "known", "mock-bank:b08", "pending PM threshold",
                    {"usual": True, "multiple": 2})
    result = detect_transfer_risk(replace(original, facts=(original.facts[0], fact,
                                                         original.facts[2])))
    assert Signal.USUAL_AMOUNT_RANGE not in result.checked_signals


@pytest.mark.parametrize("text,expected", [(RISK_TEXT, TaskStatus.FAILED),
                                           (LEGAL_TEXT, TaskStatus.NEEDS_ATTENTION)])
def test_actual_detector_and_gate_are_fail_closed_with_independent_bank_facts(tmp_path, text, expected):
    app, bank, application, _ = wired(tmp_path, detect_transfer_risk)
    try:
        before = len(bank.store.list_ledger("U1", "A1"))
        result = app.harness.start(trusted(), uuid4(), text)
        assert result.status == expected
        assert app.gateway.get_operation(trusted(), result.data.operation_id).lookup == "not_found"
        assert len(bank.store.list_ledger("U1", "A1")) == before
        events = app.audit._events("D1", "T1")
        decisions = [event.payload.decision for event in events
                     if event.event_type == "security.decided"]
        expected_code = SecurityDecisionCode.BLOCK if text == RISK_TEXT else SecurityDecisionCode.PAUSE
        assert decisions[-1].decision == expected_code
        if text == RISK_TEXT:
            assert any("v04-lexical-risk-1" in ref for ref in decisions[-1].evidence_refs)
            again = app.harness.resume(trusted("R2"), {"choice": "approve"})
            assert again.status == TaskStatus.FAILED
            assert len(bank.store.list_ledger("U1", "A1")) == before
        assert text not in json.dumps([event.model_dump(mode="json") for event in events],
                                      ensure_ascii=False)
    finally:
        app.close()


def test_real_http_request_reaches_the_actual_detector(tmp_path):
    def prepare(runtime):
        runtime.assess_risk = http_assessor(runtime, detect_transfer_risk)
    api = make_app(tmp_path, prepare=prepare)
    bank = MockBankStore(tmp_path / "bank.sqlite")
    before = len(bank.list_ledger("U1", "A1"))
    with TestClient(api) as client:
        _, task = start(client, RISK_TEXT)
        assert task["status"] == "failed"
        events = api.state.api.runtime.audit._events("D1", task["task_id"])
        assert any(event.event_type == "security.decided" and
                   event.payload.decision.decision == SecurityDecisionCode.BLOCK
                   for event in events)
    assert len(bank.list_ledger("U1", "A1")) == before
