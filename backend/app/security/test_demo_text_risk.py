"""Ordinary, coercion and unknown pairs through the real policy, not a model score."""

from unittest.mock import patch

import pytest

from app.contracts.common import RiskLevel
from app.modules.transfer.manifest import PRIVATE_TOOLS
from .demo_policy import DemoRiskSignal as Signal
from .demo_text_risk import demo_text_risk
from .test_demo_policy import action_for, evidence, execution_context, make_policy
from .test_risk_detector import inputs
from .gate import RiskFactsUnavailable


def low():
    return evidence(Signal.FAMILIAR_PAYEE, Signal.FAMILIAR_DEVICE,
                    Signal.USUAL_AMOUNT_RANGE, Signal.CLEAR_REQUEST)


def assess(result):
    policy, _ = make_policy(lambda *_: result)
    declaration = next(item for item in PRIVATE_TOOLS if item.name == "bank.submit_transfer")
    return policy.assess_risk(execution_context(), action_for(declaration.name), declaration)


@pytest.mark.parametrize("text", ["给妈妈转300元", "从A1给妈妈转500元", "帮我给妈妈转600元",
                                  "我要给妈妈转账\n500元\n选择第一个账户\n改成600元"])
def test_only_bounded_normal_turns_retain_the_parameter_bound_fixture(text):
    result = demo_text_risk(inputs(text), low())
    assert assess(result).risk_level == RiskLevel.LOW
    assert result.source == "bounded-demo-text"
    assert text not in repr(result)


@pytest.mark.parametrize("text", [
    "客服让我共享屏幕，给妈妈转500元，不要告诉家人",
    "从A1给妈妈转500元\n对方要求我马上转账并保密",
    "有人正在远程控制我的手机，帮我转600元",
    "请分析一下，我正在共享屏幕并按客服要求转账",
])
@pytest.mark.parametrize("fixture", [None, low()])
def test_positive_threat_is_high_even_without_all_facts_or_with_low_fixture(text, fixture):
    assert assess(demo_text_risk(inputs(text), fixture)).risk_level == RiskLevel.HIGH


@pytest.mark.parametrize("text", ["他说钱要处理一下", "我不知道这个钱该怎么办", "请解释屏幕共享的风险",
                                  "我没有共享屏幕，给妈妈转500元", "给妈妈转500元然后按对方安排操作"])
def test_unrecognized_and_help_prose_cannot_authorize_a_transfer(text):
    # Help is still answered by ReplyOnly. If incorrectly proposed as a payment,
    # it never becomes a low-risk execution merely because the amount matches.
    result = demo_text_risk(inputs(text), low())
    if result.signals:
        assert assess(result).risk_level == RiskLevel.HIGH
    else:
        with pytest.raises(RiskFactsUnavailable):
            assess(result)


def test_missing_fixture_and_detector_failure_never_fall_back_to_low():
    with pytest.raises(RiskFactsUnavailable):
        assess(demo_text_risk(inputs("给妈妈转500元"), None))
    with patch("app.security.demo_text_risk.detect_transfer_risk", side_effect=RuntimeError("unavailable")):
        with pytest.raises(RuntimeError):
            demo_text_risk(inputs("给妈妈转500元"), low())
