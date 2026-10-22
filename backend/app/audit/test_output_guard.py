"""Output probe: reported categories must match the audit redaction boundary."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import uuid4

from app.audit.journal import AuditJournal, AuditReader, AuditViewer, redact
from app.audit.output_guard import OutputFinding, OutputProbe, probe_output, probe_secrets
from app.contracts.audit import AuditEvent, ChatMessagePayload
from app.storage import StoragePaths

TRANSACTION_ID = "3f9a1c7e-5b2d-4e8a-9c1f-7a2b4d6e8f0a"
VIEWER = AuditViewer("admin", "AS1", "D1")


def assistant_reply_event(*, sequence=0, evidence_ref="REPLY1"):
    return AuditEvent(
        event_id=str(uuid4()), trace_id="TRACE1", span_id=f"SPAN{sequence}",
        sequence=sequence, parent_span_id=None, demo_round_id="D1", actor_id="U1",
        session_id="S1", target_session_id=None, target_user_id="U1",
        thread_id="TH1", task_id="T1", run_id="R1", module="chat",
        event_type="chat.message", timestamp=datetime.now(timezone.utc),
        logical_at=None, outcome="succeeded", evidence_ref=evidence_ref,
        evidence_status="available", missing_reason=None,
        payload=ChatMessagePayload(
            message_id=f"M{sequence}", role="assistant", content_ref=evidence_ref,
            related_task_ids=["T1"],
        ),
    )


def store_and_replay(path, text):
    """Write the probed reply as real audit evidence, then read it back."""
    journal = AuditJournal(path)
    journal.append(assistant_reply_event(), evidence={"text": text})
    reader = AuditReader(journal, authorize=lambda *_: True)
    detail = reader.timeline(VIEWER, "D1", "T1")[0]
    package = json.loads(reader.export_json(VIEWER, "D1", "T1"))
    return detail, package


LEAKY_REPLY = (
    "王阿姨您好，这笔转账已提交成功。验证码是 123456，请勿告诉他人。"
    "收款卡号 6222021234567890123，户名：李华，联系电话 13900000002。"
    f"金额 500.00 元，时间 2026-10-22 09:30，商户 示例超市，交易号 {TRANSACTION_ID}。"
)


def test_leaked_credentials_are_reported_and_replayed_with_audit_redaction(tmp_path):
    """C01/C02/C05: assistant reply leaks a code, an account, a name and a phone."""

    path = StoragePaths(tmp_path).application
    probe = probe_output(LEAKY_REPLY)

    assert probe.findings == (
        OutputFinding("credential"), OutputFinding("full_account"),
        OutputFinding("personal_name"), OutputFinding("personal_phone"),
    )
    for secret in ("123456", "6222021234567890123", "李华", "13900000002"):
        assert secret not in probe.text
    for masked in ("[REDACTED]", "****0123", "李*", "139****0002"):
        assert masked in probe.text
    for untouched in ("500.00", "2026-10-22 09:30", "示例超市", TRANSACTION_ID):
        assert untouched in probe.text
    assert probe.text == redact(LEAKY_REPLY, free_text=True)  # C05: one redaction boundary

    detail, package = store_and_replay(path, probe.text)
    assert detail.evidence_status == "available"
    assert json.loads(detail.evidence)["text"] == probe.text
    assert package["evidence"]["REPLY1"]["content"]["text"] == probe.text
    persisted = path.read_bytes()
    for secret in (b"123456", b"6222021234567890123", "李华".encode(),
                   b"13900000002"):
        assert secret not in persisted

    # The audit journal redacts the raw reply to exactly the text the probe returned.
    journal = AuditJournal(path)
    journal.append(assistant_reply_event(sequence=1, evidence_ref="REPLY2"),
                   evidence=LEAKY_REPLY)
    replay = AuditReader(journal, authorize=lambda *_: True).timeline(VIEWER, "D1", "T1")
    assert json.loads(replay[1].evidence) == probe.text


CLEAN_REPLY = (
    "王阿姨您好，本次向示例超市转账 500.00 元已成功。"
    f"时间 2026-10-22 09:30，交易号 {TRANSACTION_ID}，"
    "付款账户 ****0002，余额 1,234.56 元。如有疑问请联系开户网点。"
)


def test_normal_reply_is_untouched_and_replays_unchanged(tmp_path):
    """C03: amounts, times, merchants, UUID transaction ids and masked accounts pass."""

    path = StoragePaths(tmp_path).application
    probe = probe_output(CLEAN_REPLY)

    assert probe.findings == ()
    assert probe.text == CLEAN_REPLY
    assert probe.text == redact(CLEAN_REPLY, free_text=True)
    assert probe_secrets(CLEAN_REPLY) == (False, CLEAN_REPLY)

    detail, package = store_and_replay(path, probe.text)
    assert json.loads(detail.evidence)["text"] == CLEAN_REPLY
    assert package["evidence"]["REPLY1"]["content"]["text"] == CLEAN_REPLY
    assert CLEAN_REPLY.encode() in path.read_bytes()


PERSONAL_ONLY_REPLY = "户名：李华，手机 13900000002，卡号 6222021234567890123。"


def test_probe_secrets_only_reports_credentials_for_export_gating(tmp_path):
    """C04: export checks credentials only; personal data is masked but not a secret."""

    leaked, text = probe_secrets(PERSONAL_ONLY_REPLY)
    assert leaked is False
    for personal in ("李华", "13900000002", "6222021234567890123"):
        assert personal not in text
    assert text == redact(PERSONAL_ONLY_REPLY, free_text=True)
    assert [finding.kind for finding in probe_output(PERSONAL_ONLY_REPLY).findings] == [
        "full_account", "personal_name", "personal_phone",
    ]

    leaked, text = probe_secrets("您的验证码是 123456，请勿转发。")
    assert leaked is True
    assert "123456" not in text
    assert text == redact("您的验证码是 123456，请勿转发。", free_text=True)

    # The export gate runs over the real exported package of a safe reply.
    path = StoragePaths(tmp_path).application
    _, package = store_and_replay(path, probe_output(CLEAN_REPLY).text)
    exported = json.dumps(package, ensure_ascii=False, sort_keys=True)
    assert probe_secrets(exported)[0] is False


def test_empty_and_already_masked_text_produce_no_findings():
    for text in ("", "   ", "\n"):
        assert probe_output(text) == OutputProbe(findings=(), text=text)
        assert probe_secrets(text) == (False, text)

    masked = (
        f"户名：李*，手机 139****0002，卡号 ****0002，"
        f"交易号 {TRANSACTION_ID}，金额 500.00 元。"
    )
    probe = probe_output(masked)
    assert probe.findings == ()
    assert probe.text == masked


def test_duplicate_categories_are_reported_once_in_a_stable_order():
    text = (
        "验证码是 111111，备用验证码是 222222。"
        "手机 13900000002、13700000003；卡号 6222021234567890123、6222021234567890456；"
        "姓名：李华，收件人：王小明。"
    )
    probe = probe_output(text)

    assert probe.findings == (
        OutputFinding("credential"), OutputFinding("full_account"),
        OutputFinding("personal_name"), OutputFinding("personal_phone"),
    )
    for secret in ("111111", "222222", "13900000002", "13700000003",
                   "6222021234567890123", "6222021234567890456", "李华", "王小明"):
        assert secret not in probe.text


def test_code_shaped_digits_are_reported_even_without_an_audit_label_separator():
    """The audit regex only masks labelled secrets; the probe still flags code shapes."""

    for text in ("验证码123456，5 分钟内有效。", "123456 是本次登录的验证码。",
                 "code: 123456"):
        probe = probe_output(text)
        assert [finding.kind for finding in probe.findings] == ["credential"]
        assert probe.text == redact(text, free_text=True)

    # A six-digit run with no code word around it is not a credential.
    assert probe_output("订单号 123456，尾号 654321。").findings == ()
