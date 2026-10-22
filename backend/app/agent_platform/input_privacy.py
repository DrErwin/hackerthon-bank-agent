"""Recognizable secret values are refused before chat persistence or model input."""

import re

from app.audit.output_guard import probe_output


_ENGLISH_PASSWORD = re.compile(
    r"(?:password|passwd|pwd)\s*(?:[:：=]|是|为)\s*\S+", re.I)
_BARE_CODE = re.compile(r"\s*[A-Za-z0-9]{4,8}\s*")


def has_chat_secret(text: str, *, numeric_field: bool = False) -> bool:
    return (
        any(item.kind == "credential" for item in probe_output(text).findings)
        or _ENGLISH_PASSWORD.search(text) is not None
        or not numeric_field and _BARE_CODE.fullmatch(text) is not None
        and any(char.isdigit() for char in text)
    )
