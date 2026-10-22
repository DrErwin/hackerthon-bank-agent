"""Read-only output probe: report sensitive categories and return audit-redacted text.

The probe never allows or denies anything by itself; it only reports what it found and
the text after ``journal.redact``. Detection reuses the audit regular expressions so the
reported boundary stays aligned with what the audit journal would mask. One credential
shape (a six-digit code next to a "码 / code" word but without the separator
``journal.redact`` requires, e.g. ``验证码123456`` or ``code: 123456``) is reported but is
not masked by the audit regex; callers must treat any ``credential`` finding as a gate
instead of relying on the returned text alone.

The six-digit rule matches a *phrase*, not a proximity window: a machine payload such as
``{"duration_ms": 123456, "reason_code": "..."}`` or a UUID that happens to contain six
digits is not a verification code and must not block an export (v05-observer-seams/08).
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
# ("验证码123456", "code: 123456", "123456 是本次登录的验证码"). Each pattern keeps the
# code word adjacent to its value, and the trailing lookahead keeps the integer part of
# a decimal amount out of the code shape. Machine payloads therefore stay clean: a JSON
# key like ``reason_code`` is not the standalone word ``code``, and a quoted value such
# as ``"method": "code"`` is not followed by a bare digit run.
_NOT_DECIMAL = r"(?![.,]\d)"
_CODE_SEPARATORS = r"[\s：:\"']*"
_SIX_DIGITS = r"(?<!\d)\d{6}(?!\d)"
_CHINESE_CODE_LABELS = "验证码|短信码|动态码|登录码|校验码"
_LABELED_CODE = re.compile(
    rf"(?:{_CHINESE_CODE_LABELS}){_CODE_SEPARATORS}(?:是|为)?{_CODE_SEPARATORS}"
    rf"{_SIX_DIGITS}{_NOT_DECIMAL}"
)
_DIGITS_THEN_LABEL = re.compile(
    rf"{_SIX_DIGITS}{_NOT_DECIMAL}\s*(?:是|为)[^，,。;；\n:：]{{0,10}}"
    rf"(?:{_CHINESE_CODE_LABELS})"
)
# The English word must be standalone (``reason_code`` / ``verification_code`` do not
# count) and the quoted JSON value ``"code"`` never reaches a bare digit run.
_ENGLISH_CODE = re.compile(
    rf"(?<![A-Za-z0-9_])(?:code|otp)(?![A-Za-z0-9_]){_CODE_SEPARATORS}"
    rf"{_SIX_DIGITS}{_NOT_DECIMAL}",
    re.IGNORECASE,
)
_CODE_SHAPES = (_LABELED_CODE, _DIGITS_THEN_LABEL, _ENGLISH_CODE)


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
    return any(shape.search(text) is not None for shape in _CODE_SHAPES)


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
