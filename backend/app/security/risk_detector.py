"""Bounded offline recognition over server-resolved inputs, never authorization.

Positive lexical matches are risk evidence. A lexical non-match is NOT evidence
that a semantic risk dimension is clear. Missing dimensions remain unchecked.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
import unicodedata

from app.security.demo_policy import DemoRiskEvidence, DemoRiskSignal as Signal

if TYPE_CHECKING:
    from app.agent_platform.risk_inputs import RiskInputs


DETECTOR_VERSION = "v04-lexical-risk-1"
# Stable rule identifiers are the existing signal names, not matched raw strings.
_PATTERNS = {
    Signal.IMPERSONATION: re.compile(r"(?:公安|警察|检察院|法院|办案人员).{0,48}(?:安全账户|转账|转到|资金审查)"),
    Signal.SECRECY_OR_URGENT_PRESSURE: re.compile(
        r"(?:别|不能)告诉(?:家人|别人|子女)|别让其他人知道|对家人保密|"
        r"保密.{0,12}转账|(?:马上|立即|立刻|紧急).{0,8}(?:转账|转钱|转\d)"),
    Signal.SCREEN_SHARING: re.compile(r"(?:打开|开启|进行|要求|让我).{0,12}(?:屏幕共享|共享屏幕)"),
    Signal.CREDENTIAL_REQUEST: re.compile(r"(?:把|将)[^，,。;；]{0,12}(?:验证码|密码|口令)[^，,。;；]{0,12}(?:发给|告诉|提供给)|(?:索取|交出|提供)(?:验证码|密码|口令)"),
    Signal.UNFAMILIAR_LINK: re.compile(r"(?:https?://|www\.)\S+"),
}
_EDUCATION = re.compile(r"(?:请|帮我)(?:解释|分析|识别|判断)|反诈|防骗|诈骗案例")
_NEGATED = re.compile(r"不要|切勿|禁止|拒绝|没有|未曾")


def detect_transfer_risk(inputs: RiskInputs) -> DemoRiskEvidence:
    """Consume the trusted seam; output only checked facts and opaque provenance.

    Not a full language classifier. Education/negative controls suppress a match
    only within that clause. Unsupported wording stays unknown and cannot grant
    permission. Pending PM amount defaults and device claims are not consumed.
    """
    text = unicodedata.normalize("NFKC", inputs.request_text)
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    signals: set[Signal] = set()
    for clause in re.split(r"[。！!？?\n；;]", text):
        if _EDUCATION.search(clause):
            continue
        for signal, pattern in _PATTERNS.items():
            for match in pattern.finditer(clause):
                # A negated action suppresses that match, not other actions or a
                # later secrecy clause. Whole-clause negation hides real threats.
                prefix = clause[max(0, match.start() - 4):match.start()]
                if not _NEGATED.search(prefix + match.group()):
                    signals.add(signal)
    checked = set(signals)
    history = inputs.fact("payee_history")
    if history.status == "known" and history.value is not None:
        saved, prior = history.value.get("saved"), history.value.get("prior_outflows")
        if type(saved) is bool and type(prior) is int and prior >= 0:
            checked.update({Signal.FAMILIAR_PAYEE, Signal.NEW_PAYEE})
            signals.add(Signal.FAMILIAR_PAYEE if saved and prior > 0 else Signal.NEW_PAYEE)
    return DemoRiskEvidence(
        source="trusted-request-lexical-detector", source_version=DETECTOR_VERSION,
        evidence_ref=inputs.evidence_ref,
        signals=frozenset(signals), checked_signals=frozenset(checked),
    )
