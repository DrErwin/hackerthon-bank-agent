"""A live ReplyOnly explanation must not be confused with its credential value."""
import pytest
from app.audit.journal import redact
from app.audit.output_guard import probe_output
from app.agent_platform.input_privacy import has_chat_secret
from app.audit.test_output_guard import store_and_replay
import json


@pytest.mark.parametrize("text", [
    "验证码是保护您资金安全的最后一道防线",
    "验证码是银行用来核验本人的，不要告诉陌生人。",
    "短信码为验证本人而设置，不要转发。",
    "验证码是6位数字，只能填写在可信页面。",
])
def test_explanation_keeps_meaning_in_output_and_persisted_audit(tmp_path, text):
    probe = probe_output(text)
    assert not probe.findings
    assert probe.text == text
    detail, _ = store_and_replay(tmp_path / "audit.sqlite", text)
    assert json.loads(detail.evidence)["text"] == text


@pytest.mark.parametrize("text,secret", [
    ("验证码是123456，请保密", "123456"),
    ("验证码：AB12CD", "AB12CD"),
    ("短信码为654321", "654321"),
    ("验证码是 **123456**", "123456"),
    ("验证码是１２３４５６", "１２３４５６"),
    ("验证码是（123456）", "123456"),
    ("验证码：【123456】", "123456"),
    ("验证码是：123456，请保密", "123456"),
    ("短信码为:654321", "654321"),
    ("验证码是数字123456", "123456"),
    ("验证码是（ 123456 ）", "123456"),
    ("验证码：【 123456 】", "123456"),
    ("密码是春暖花开", "春暖花开"),
    ("口令为abc123", "abc123"),
    ("token: secretValue", "secretValue"),
])
def test_actual_values_still_gate_and_redact(tmp_path, text, secret):
    assert has_chat_secret(text)
    assert any(f.kind == "credential" for f in probe_output(text).findings)
    assert secret not in str(redact(text, free_text=True))
    detail, _ = store_and_replay(tmp_path / "audit.sqlite", text)
    assert secret not in detail.evidence


def test_explanation_does_not_hide_a_later_value():
    text = "验证码是保护资金的。验证码是123456。"
    assert any(f.kind == "credential" for f in probe_output(text).findings)
    assert "123456" not in str(redact(text, free_text=True))
