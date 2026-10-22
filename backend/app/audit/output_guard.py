"""Read-only output probe: report sensitive categories and return audit-redacted text.

The probe never allows or denies anything by itself; it only reports what it found and
the text after ``journal.redact``. Detection reuses the audit regular expressions so the
reported boundary stays aligned with what the audit journal would mask. One credential
shape (a six-digit code with a nearby "码 / code" word but no separator, e.g.
``验证码123456``) is reported but is not masked by the audit regex; callers must treat any
``credential`` finding as a gate instead of relying on the returned text alone.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from app.audit.journal import ACCOUNT, NAME, PHONE, SECRET_LABEL, redact

OutputKind = Literal["credential", "full_account", "personal_name", "personal_phone"]

# Stable report order; each category appears at most once.
_KINDS: tuple[OutputKind, ...] = (
    "credential", "full_account", "personal_name", "personal_phone",
)
_REDACTED = "[REDACTED]"
# A six-digit code may appear without the separator SECRET_LABEL requires
# ("验证码123456", "code: 123456", "123456 是本次登录的验证码"). The trailing
# lookahead keeps a six-digit integer part of a decimal amount out of the code shape.
_SIX_DIGITS = re.compile(r"(?<!\d)\d{6}(?!\d)(?![.,]\d)")
_CODE_CONTEXT = re.compile(r"码|code", re.I)
# How far around the digit run a code word may sit and still mark it as a code.
_CODE_CONTEXT_WINDOW = 20


@dataclass(frozen=True)
class OutputFinding:
    kind: OutputKind


@dataclass(frozen=True)
class OutputProbe:
    findings: tuple[OutputFinding, ...]
    text: str


def _has_credential(text: str) -> bool:
    for match in SECRET_LABEL.finditer(text):
        if match.group(2).strip() != _REDACTED:
            return True
    for match in _SIX_DIGITS.finditer(text):
        start = max(0, match.start() - _CODE_CONTEXT_WINDOW)
        end = min(len(text), match.end() + _CODE_CONTEXT_WINDOW)
        if _CODE_CONTEXT.search(text[start:end]):
            return True
    return False


def probe_output(text: str) -> OutputProbe:
    """Report the sensitive categories found in text and the audit-redacted text."""
    hits = {
        "credential": _has_credential(text),
        "full_account": ACCOUNT.search(text) is not None,
        "personal_name": NAME.search(text) is not None,
        "personal_phone": PHONE.search(text) is not None,
    }
    findings = tuple(OutputFinding(kind) for kind in _KINDS if hits[kind])
    return OutputProbe(findings=findings, text=str(redact(text, free_text=True)))


def probe_secrets(text: str) -> tuple[bool, str]:
    """Credential-only check for export paths; personal data is masked, not gated."""
    probe = probe_output(text)
    return any(finding.kind == "credential" for finding in probe.findings), probe.text
