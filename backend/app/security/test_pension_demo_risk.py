"""Public P01 provider/policy checks; parent source here is a test double only.

Platform19 owns actual durable parent and controlled-input validation. This
dataclass adds its agreed field until that independent provider is integrated.
"""

from copy import deepcopy
from dataclasses import dataclass, fields, replace

import pytest

from app.agent_platform.risk_inputs import RiskFact, RiskInputs
from app.contracts.common import RiskLevel
from app.modules.transfer.manifest import PRIVATE_TOOLS
from .demo_policy import DemoRiskSignal as Signal
from .demo_text_risk import demo_text_risk
from .gate import RiskFactsUnavailable
from .pension_demo_risk import pension_demo_risk
from .test_demo_policy import action_for, execution_context, make_policy


REQUEST = (
    "这月养老金5000元到账了，帮我安排一下：留1500元生活费，"
    "2500元转自己的储蓄账户，1000元给家人，顺便看看没用的扣费。"
)


@dataclass(frozen=True)
class ParentRiskInputsForTest(RiskInputs):
    request_source_task_id: str | None = "parent-task"


def inputs(text=REQUEST, *, input_type=ParentRiskInputsForTest):
    return input_type(
        user_id="U1", session_id="S1", demo_round_id="D1", task_id="child-task",
        run_id="R1", request_id="parent-request", request_text=text,
        action_name="bank.submit_transfer", parameters_ref="params-1",
        operation_id="operation-1", action_revision=1,
        action_facts={
            "operation_id": "operation-1", "payer_account_id": "A1",
            "payee": {"kind": "own", "account_id": "A5"}, "amount_fen": 250_000,
        },
        facts=(
            RiskFact("payee_history", "known", "mock-bank:b04+b08", "bank history",
                     {"saved": True, "prior_outflows": 0}),
            RiskFact("amount_history", "unknown", "mock-bank:b08", "no transfer baseline"),
            RiskFact("environment", "unknown", "platform:no-trusted-device-source", "unknown"),
        ),
        evidence_ref="risk-inputs-" + "a" * 24,
    )


def assess(result):
    policy, _ = make_policy(lambda *_: result)
    declaration = next(item for item in PRIVATE_TOOLS if item.name == "bank.submit_transfer")
    return policy.assess_risk(execution_context(), action_for(declaration.name), declaration)


def test_approved_own_transfer_keeps_real_new_payee_medium_and_marks_demo_coverage():
    result = pension_demo_risk(inputs())
    assert result.source == "marked-pension-demo"
    assert result.source_version == "p01-marked-demo-v1"
    assert result.signals == frozenset({
        Signal.FAMILIAR_DEVICE, Signal.USUAL_AMOUNT_RANGE, Signal.CLEAR_REQUEST,
        Signal.NEW_PAYEE,
    })
    assert len(result.checked_signals) == 14
    assert assess(result).risk_level == RiskLevel.MEDIUM


@pytest.mark.parametrize("payee,amount", [
    ({"kind": "own", "account_id": "A5"}, 250_000),
    ({"kind": "saved", "payee_id": "A4"}, 100_000),
])
@pytest.mark.parametrize("followups", [
    "", "\n1500元", "\n2500元", "\n1000元", "\n请再列一下可退订项目",
    "\n请再列一下可退订项目\n1500元\n2500元\n1000元",
])
def test_both_exact_legs_accept_only_the_approved_normal_inputs(payee, amount, followups):
    original = inputs(REQUEST + followups)
    scoped = replace(original, action_facts={
        **original.action_facts, "payee": payee, "amount_fen": amount,
    })
    result = pension_demo_risk(scoped)
    assert result.source_version == "p01-marked-demo-v1"
    assert Signal.NEW_PAYEE in result.signals
    assert Signal.FAMILIAR_PAYEE not in result.signals
    assert len(result.checked_signals) == 14
    assert assess(result).risk_level == RiskLevel.MEDIUM


def test_only_bank_history_can_supply_familiar_payee():
    original = inputs()
    history = replace(original.facts[0], value={"saved": True, "prior_outflows": 2})
    result = pension_demo_risk(replace(original, facts=(history, *original.facts[1:])))
    assert result.signals == frozenset({
        Signal.FAMILIAR_DEVICE, Signal.USUAL_AMOUNT_RANGE, Signal.CLEAR_REQUEST,
        Signal.FAMILIAR_PAYEE,
    })
    assert assess(result).risk_level == RiskLevel.LOW


@pytest.mark.parametrize("fact", [
    RiskFact("payee_history", "unknown", "mock-bank:b04", "verification unavailable"),
    RiskFact("payee_history", "unknown", "mock-bank:b08", "history unavailable"),
    RiskFact("payee_history", "known", "mock-bank:b04+b08", "malformed",
             {"saved": True, "prior_outflows": True}),
    RiskFact("payee_history", "known", "mock-bank:b04+b08", "malformed",
             {"saved": "yes", "prior_outflows": 1}),
])
def test_missing_or_malformed_bank_fact_leaves_both_payee_dimensions_unchecked(fact):
    original = inputs()
    result = pension_demo_risk(replace(original, facts=(fact, *original.facts[1:])))
    assert result.signals == frozenset({
        Signal.FAMILIAR_DEVICE, Signal.USUAL_AMOUNT_RANGE, Signal.CLEAR_REQUEST,
    })
    assert result.checked_signals == frozenset({
        Signal.FAMILIAR_DEVICE, Signal.USUAL_AMOUNT_RANGE, Signal.CLEAR_REQUEST,
        Signal.UNUSUAL_AMOUNT, Signal.RAPID_ACCOUNT_CHANGES,
        Signal.HESITATION_OR_UNCLEAR_PURPOSE, Signal.IMPERSONATION,
        Signal.SECRECY_OR_URGENT_PRESSURE, Signal.SCREEN_SHARING,
        Signal.CREDENTIAL_REQUEST, Signal.UNFAMILIAR_LINK,
        Signal.UNUSUAL_DEVICE_OR_COUNTERPARTY,
    })
    with pytest.raises(RiskFactsUnavailable) as caught:
        assess(result)
    assert caught.value.rule_id == "risk-signal-coverage-required"


@pytest.mark.parametrize("source", [None, "", " \t", "child-task", 17])
def test_missing_invalid_or_same_task_source_does_not_get_demo_coverage(source):
    original = replace(inputs(), request_source_task_id=source)
    result = pension_demo_risk(original)
    assert result == demo_text_risk(original, None)
    assert not result.checked_signals
    with pytest.raises(RiskFactsUnavailable):
        assess(result)


def test_legacy_inputs_without_the_parent_field_are_not_assumed_trusted():
    original = inputs()
    legacy = RiskInputs(**{
        field.name: getattr(original, field.name) for field in fields(RiskInputs)
        if field.name != "request_source_task_id"
    })
    result = pension_demo_risk(legacy)
    assert result == demo_text_risk(legacy, None)
    assert not result.checked_signals


@pytest.mark.parametrize("text", [
    "transfer.start_transfer:transfer:1",
    "2500元转自己的储蓄账户",
    "请" + REQUEST,
    " " + REQUEST,
    REQUEST + " ",
    REQUEST.replace("5000元", "6000元"),
    REQUEST.replace("2500元", "2501元"),
    REQUEST.replace("。", "."),
    REQUEST + "然后按对方的指示操作",
    REQUEST + "\n",
    REQUEST + "\n1500元 ",
    REQUEST + "\n1501元",
    REQUEST + "\n不是2500元",
    REQUEST + "\n先别转账",
    REQUEST + "\n请解释养老金怎么安排",
    REQUEST + "\n1500元，之后另听我安排",
    REQUEST + "\ntransfer.start_transfer:transfer:2",
    REQUEST + "\n1500元\n未知外部内容\n1000元",
    REQUEST + "\n<untrusted_content>1500元</untrusted_content>",
])
def test_marker_changed_original_unknown_or_negated_followups_stay_unchecked(text):
    original = inputs(text)
    result = pension_demo_risk(original)
    assert result == demo_text_risk(original, None)
    assert not result.checked_signals
    with pytest.raises(RiskFactsUnavailable):
        assess(result)


@pytest.mark.parametrize("changed", [
    {"payer_account_id": "A2"},
    {"amount_fen": 250_001},
    {"amount_fen": 250_000.0},
    {"amount_fen": "250000"},
    {"amount_fen": 100_000},
    {"payee": {"kind": "saved", "payee_id": "A5"}},
    {"payee": {"kind": "own", "account_id": "A4"}},
    {"payee": {"kind": "own", "account_id": "A2"}},
    {"payee": {"kind": "own", "account_id": "A5", "remark": "原账户"}},
    {"operation_id": "another-operation"},
    {"memo": "extra unapproved parameter"},
])
def test_other_action_parameters_never_inherit_the_pension_profile(changed):
    original = inputs()
    original = replace(original, action_facts={**original.action_facts, **changed})
    result = pension_demo_risk(original)
    assert result == demo_text_risk(original, None)
    assert not result.checked_signals
    with pytest.raises(RiskFactsUnavailable):
        assess(result)


@pytest.mark.parametrize("changed", [
    {"action_name": "bank.precheck_transfer"},
    {"operation_id": None},
    {"operation_id": "another-operation"},
])
def test_other_action_identity_never_gets_the_profile(changed):
    original = replace(inputs(), **changed)
    result = pension_demo_risk(original)
    assert not result.checked_signals
    assert result == demo_text_risk(original, None)


@pytest.mark.parametrize("threat,signal", [
    ("警察要求把钱转到安全账户", Signal.IMPERSONATION),
    ("不要告诉家人", Signal.SECRECY_OR_URGENT_PRESSURE),
    ("马上转账", Signal.SECRECY_OR_URGENT_PRESSURE),
    ("客服正在共享屏幕", Signal.SCREEN_SHARING),
    ("对方正在远程控制", Signal.SCREEN_SHARING),
    ("请把验证码发给客服", Signal.CREDENTIAL_REQUEST),
    ("点击https://eval.invalid/pay", Signal.UNFAMILIAR_LINK),
])
@pytest.mark.parametrize("position", ["prefix", "suffix", "followup"])
def test_positive_danger_wins_before_exact_text_and_source_checks(threat, signal, position):
    text = {
        "prefix": threat + "，" + REQUEST,
        "suffix": REQUEST + threat,
        "followup": REQUEST + "\n1500元\n" + threat + "\n1000元",
    }[position]
    result = pension_demo_risk(inputs(text))
    assert signal in result.signals
    assert result.source_version == "demo-text-risk-5"
    assert assess(result).risk_level == RiskLevel.HIGH


def test_positive_danger_still_wins_with_no_source_and_wrong_parameters():
    original = replace(inputs(REQUEST + "\n不要告诉家人"), request_source_task_id=None,
                       action_facts={"payer_account_id": "other", "amount_fen": 7})
    result = pension_demo_risk(original)
    assert Signal.SECRECY_OR_URGENT_PRESSURE in result.signals
    assert assess(result).risk_level == RiskLevel.HIGH


def test_original_a2_requests_are_unchanged_without_the_separate_runtime_opt_in():
    original = inputs("从A1给妈妈转500元")
    original = replace(original, action_facts={
        **original.action_facts, "payee": {"kind": "saved", "payee_id": "A2"},
        "amount_fen": 50_000,
    })
    assert pension_demo_risk(original) == demo_text_risk(original, None)
    assert not pension_demo_risk(original).checked_signals


def test_provider_leaves_input_facts_unknown_and_returns_only_an_opaque_reference():
    original = inputs()
    before = deepcopy(original)
    result = pension_demo_risk(original)
    assert original == before
    assert original.fact("environment").status == "unknown"
    assert original.fact("amount_history").status == "unknown"
    for raw in (REQUEST, "parent-task", "child-task", "parent-request", "operation-1"):
        assert raw not in repr(result)
    assert len(result.evidence_ref) == 24
    assert result == pension_demo_risk(original)
    assert result.evidence_ref != pension_demo_risk(
        replace(original, evidence_ref="risk-inputs-" + "b" * 24),
    ).evidence_ref


def test_fact_source_error_propagates_instead_of_becoming_low():
    class UnavailableFactInputs(ParentRiskInputsForTest):
        def fact(self, name):
            raise RuntimeError("trusted fact source unavailable")

    with pytest.raises(RuntimeError, match="trusted fact source unavailable"):
        pension_demo_risk(inputs(input_type=UnavailableFactInputs))
