"""Ordinary, coercion and unknown pairs through the real policy, not a model score."""

from unittest.mock import patch
from dataclasses import replace

import pytest

from app.contracts.common import RiskLevel
from app.modules.transfer.manifest import PRIVATE_TOOLS
from .demo_policy import DemoRiskSignal as Signal
from .demo_text_risk import demo_text_risk
from .test_demo_policy import action_for, evidence, execution_context, make_policy
from .test_risk_detector import inputs
from .gate import RiskFactsUnavailable
from app.agent_platform.risk_inputs import RiskFact


def low():
    return evidence(Signal.FAMILIAR_PAYEE, Signal.FAMILIAR_DEVICE,
                    Signal.USUAL_AMOUNT_RANGE, Signal.CLEAR_REQUEST)


def assess(result):
    policy, _ = make_policy(lambda *_: result)
    declaration = next(item for item in PRIVATE_TOOLS if item.name == "bank.submit_transfer")
    return policy.assess_risk(execution_context(), action_for(declaration.name), declaration)


@pytest.mark.parametrize("text", ["给妈妈转300元", "从A1给妈妈转500元", "帮我给妈妈转600元",
                                  "给妈妈转300元，主账户A1", "给妈妈转500元；付款账户A1。",
                                  "我要给妈妈转账\n500元\n选择第一个账户\n改成600元",
                                  "我要转账", "请帮我汇款\n500元\n主账户A1",
                                  "我要转账\n我有什么收款人？", "我要转账\n我有哪些账户和余额",
                                  "我要转账\n查看我的收款人\n我的账户"])
def test_only_bounded_normal_turns_retain_the_parameter_bound_fixture(text):
    result = demo_text_risk(inputs(text), low())
    assert assess(result).risk_level == RiskLevel.LOW
    assert result.source == "bounded-demo-text"
    assert text not in repr(result)


@pytest.mark.parametrize("text", [
    "转账500元给妈妈", "转500给爸爸", "汇款500块钱给家人",
    "请转500元给P1", "麻烦从A1转账500元给妈妈", "帮我用主账户A1转500块给妈妈",
    "我要从储蓄账户汇款500元向妈妈", "我想用付款账户A1转账500元给A2",
    "请帮我从日常账户转账500.50元给妈妈", "转账５００．５０元给妈妈",
    "给妈妈转500.50元", "转账500元给妈妈，主账户A1。", "转账500元给妈妈.付款账户A1",
])
def test_amount_before_payee_keeps_only_the_existing_parameter_bound_fixture(text):
    result = demo_text_risk(inputs(text), low())
    assert assess(result).risk_level == RiskLevel.LOW
    assert result.checked_signals == low().checked_signals
    assert result.source_version == "demo-text-risk-5"


@pytest.mark.parametrize("text", [
    "客服让我共享屏幕，给妈妈转500元，不要告诉家人",
    "从A1给妈妈转500元\n对方要求我马上转账并保密",
    "有人正在远程控制我的手机，帮我转600元",
    "请分析一下，我正在共享屏幕并按客服要求转账",
    "给妈妈转300元，主账户A1，不要告诉家人",
    "给妈妈转300元，主账户A1，客服正在共享屏幕",
    "我要转账\n客服正在共享屏幕",
    "我要转账，不要告诉家人",
    "我要转账\n我有什么收款人？客服正在共享屏幕",
    "我要转账\n查看我的账户，不要告诉家人",
    "客服正在共享屏幕，转账500元给妈妈",
    "转账500元给妈妈，不要告诉家人",
    "转账500元给妈妈客服正在共享屏幕",
    "对方让我马上转账500元给妈妈",
])
@pytest.mark.parametrize("fixture", [None, low()])
def test_positive_threat_is_high_even_without_all_facts_or_with_low_fixture(text, fixture):
    assert assess(demo_text_risk(inputs(text), fixture)).risk_level == RiskLevel.HIGH


@pytest.mark.parametrize("text", ["他说钱要处理一下", "我不知道这个钱该怎么办", "请解释屏幕共享的风险",
                                  "我没有共享屏幕，给妈妈转500元", "给妈妈转500元然后按对方安排操作",
                                  "给妈妈转300元，主账户A1，再按对方的指示处理",
                                  "我要转账，再按对方的指示处理", "我要转账给一个不确定的人",
                                  "我要转账\n我有什么收款人？再按对方的指示处理",
                                  "我要转账\n查询别人的账户"])
def test_unrecognized_and_help_prose_cannot_authorize_a_transfer(text):
    # Help is still answered by ReplyOnly. If incorrectly proposed as a payment,
    # it never becomes a low-risk execution merely because the amount matches.
    result = demo_text_risk(inputs(text), low())
    if result.signals:
        assert assess(result).risk_level == RiskLevel.HIGH
    else:
        with pytest.raises(RiskFactsUnavailable):
            assess(result)


@pytest.mark.parametrize("text", [
    "不要转账500元给妈妈", "我不想转500元给妈妈", "没有转账500元给妈妈",
    "请解释转账500元给妈妈", "转账500元给妈妈但用途还没确定",
    "转账500元给妈妈，再按对方的指示处理", "转账500元给一个不确定的人",
    "转账500元给陌生人", "转账500.501元给妈妈", "转账500.1.2元给妈妈",
    "我没有共享屏幕，转账500元给妈妈",
])
def test_reordered_transfer_does_not_hide_unknown_or_negated_prose(text):
    result = demo_text_risk(inputs(text), low())
    assert not result.signals
    assert not result.checked_signals
    with pytest.raises(RiskFactsUnavailable):
        assess(result)


@pytest.mark.parametrize("text", ["转账500元给妈妈", "请帮我从A1转账500.50元给妈妈"])
def test_reordered_transfer_without_a_fixture_still_pauses(text):
    result = demo_text_risk(inputs(text), None)
    assert not result.checked_signals
    with pytest.raises(RiskFactsUnavailable):
        assess(result)


def test_missing_fixture_and_detector_failure_never_fall_back_to_low():
    with pytest.raises(RiskFactsUnavailable):
        assess(demo_text_risk(inputs("给妈妈转500元"), None))
    with pytest.raises(RiskFactsUnavailable):
        assess(demo_text_risk(inputs("我要转账"), None))
    with pytest.raises(RiskFactsUnavailable):
        assess(demo_text_risk(inputs("我要转账\n我有什么收款人？"), None))
    with pytest.raises(RiskFactsUnavailable):
        assess(demo_text_risk(inputs("给妈妈转300元，主账户A1"), None))
    with patch("app.security.demo_text_risk.detect_transfer_risk", side_effect=RuntimeError("unavailable")):
        with pytest.raises(RuntimeError):
            demo_text_risk(inputs("给妈妈转500元"), low())


@pytest.mark.parametrize("text", ["给妈妈转500元", "转账500元给妈妈"])
def test_actual_new_payee_overrides_fictional_familiar_payee(text):
    original = inputs(text)
    history = RiskFact("payee_history", "known", "mock-bank:b04+b08", "bank history",
                       {"saved": True, "prior_outflows": 0})
    result = demo_text_risk(replace(original, facts=(history, *original.facts[1:])), low())
    assert Signal.NEW_PAYEE in result.signals
    assert Signal.FAMILIAR_PAYEE not in result.signals
    assert assess(result).risk_level == RiskLevel.MEDIUM
