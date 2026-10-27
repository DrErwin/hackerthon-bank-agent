"""Bounded demo text evidence. Unknown prose never inherits a low-risk fixture."""

from hashlib import sha256
import re
import unicodedata

from .demo_policy import DemoRiskEvidence, DemoRiskSignal as Signal, _HIGH_RISK_SIGNALS
from .risk_detector import detect_transfer_risk


VERSION = "demo-text-risk-5"
# This is deliberately a small language surface for the local demonstration,
# not a claim that arbitrary Chinese prose has been classified as safe.
_ACCOUNT = r"(?:A[123]|(?:主账户|付款账户)A[123]|日常账户|储蓄账户|养老金账户)"
_PAYEE = r"(?:妈妈|爸爸|家人|P[12]|A2)"
_AMOUNT = r"\d+(?:\.\d{1,2})?(?:元|块钱|块)?"
_NORMAL_TURN = re.compile(
    rf"(?:(?:请|麻烦|帮我|我要|我想|请帮我)?(?:从{_ACCOUNT}|用{_ACCOUNT})?"
    rf"(?:(?:给|向){_PAYEE}(?:转账?|汇款)(?:{_AMOUNT})?"
    rf"|(?:转账?|汇款){_AMOUNT}(?:给|向){_PAYEE})"
    r"|(?:请|麻烦|帮我|我要|我想|请帮我)?(?:转账|汇款)"
    r"|(?:我(?:有|的)?(?:哪些|什么)(?:收款人|账户)(?:和余额)?|"
    r"(?:请|帮我|请帮我)?(?:查看|查询|看看)(?:我的)?(?:收款人|账户|账户和余额)|"
    r"我的(?:账户|收款人))"
    rf"|(?:请)?(?:改成|改为|修改为|金额改成|金额改为){_AMOUNT}"
    rf"|{_AMOUNT}|{_ACCOUNT}|(?:用|使用|选择?){_ACCOUNT}"
    r"|选择?第[一二三123]个(?:付款)?账户|继续办理|请继续办理|查询原结果|取消)"
)
_PRESSURE = re.compile(r"(?:不要|别|不能).{0,4}告诉(?:家人|别人|子女)|对家人保密|保密.{0,12}(?:转账|汇款)|(?:马上|立刻|立即).{0,8}(?:转账|转钱|汇款|转\d)")
_SCREEN = re.compile(r"屏幕共享|共享屏幕|远程控制")
_SCREEN_NEGATION = re.compile(r"(?:不要|拒绝|没有|未曾|关闭|停止).{0,6}$")


def demo_text_risk(inputs, fixture: DemoRiskEvidence | None) -> DemoRiskEvidence:
    """Overlay actual text on an already parameter-bound server fixture.

    Positive threats win, including when fixture facts are missing. Only finite
    ordinary transfer/continuation phrases may retain a configured fixture.
    Other text remains unchecked. Detector exceptions propagate to the existing
    fail-closed gate; there is no exception-to-low fallback.
    """
    detected = detect_transfer_risk(inputs)
    text = unicodedata.normalize("NFKC", inputs.request_text)
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    threats = set(detected.signals & _HIGH_RISK_SIGNALS)
    for clause in re.split(r"[，,。；;！!？?\n]", text):
        if _PRESSURE.search(clause):
            threats.add(Signal.SECRECY_OR_URGENT_PRESSURE)
        for match in _SCREEN.finditer(clause):
            if not _SCREEN_NEGATION.search(clause[:match.start()]):
                threats.add(Signal.SCREEN_SHARING)
    # A server fixture with a positive high-risk scenario also cannot be erased.
    if fixture is not None:
        threats.update(fixture.signals & _HIGH_RISK_SIGNALS)
    reference = sha256((inputs.evidence_ref + ":" + (
        f"{fixture.source}:{fixture.source_version}:{fixture.evidence_ref}" if fixture else "no-fixture"
    )).encode()).hexdigest()[:24]
    if threats:
        return DemoRiskEvidence("bounded-demo-text", VERSION, reference,
                                frozenset(threats), frozenset(threats))
    # Each clause must independently match the finite normal grammar. Never
    # discard trailing prose: one unknown clause still leaves facts unchecked.
    turns = [re.sub(r"\s+", "", line).strip() for line in
             re.split(r"[，,。!！？?；;\n]|(?<!\d)\.|\.(?!\d)", text) if line.strip()]
    if fixture is not None and turns and all(_NORMAL_TURN.fullmatch(turn) for turn in turns):
        # Real checked bank facts replace the fictional value in those dimensions.
        # In particular NEW_PAYEE must not disappear behind a familiar-payee fixture.
        signals = (fixture.signals - detected.checked_signals) | detected.signals
        return DemoRiskEvidence("bounded-demo-text", VERSION, reference,
                                signals, fixture.checked_signals | detected.checked_signals)
    return DemoRiskEvidence("bounded-demo-text", VERSION, reference,
                            frozenset(), frozenset())
