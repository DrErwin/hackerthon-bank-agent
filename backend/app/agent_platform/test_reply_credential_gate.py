"""Model replies may explain credential safety but never carry a credential value (v05-observer-seams/07).

Every test runs the real harness, application store, audit journal and transfer
registry; only the planner is scripted (or the scripted chat model behind the real
DeepAgentPlanner).
"""

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import pytest

from app.audit.journal import AuditReader, AuditViewer
from app.modules.transfer.test_workflow import Ports
from app.storage.database import connect

from .model import DeepAgentPlanner, ModelSettings, ReplyOnly
from .test_harness import ScriptedChatModel, runtime, trusted


REMINDER = "这条短信里的验证码不要告诉任何人，请通过官方渠道核实，不要向陌生账户转账。"
FULL_ACCOUNT = "6222000000000002"
PHONE = "13912345678"
REPLY_WITH_PII = (
    f"联系人姓名：张三，手机号 {PHONE}，账号 {FULL_ACCOUNT}；验证码不要告诉他人。"
)


def open_session(harness):
    now = datetime.now(timezone.utc)
    harness.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )


def viewer():
    return AuditViewer("auditor", "AS", "D1")


def platform_text(path):
    """Every stored value in the application database, so a new table is covered."""

    connection = connect(path)
    try:
        names = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return " ".join(str(cell) for name in names
                        for row in connection.execute(f'SELECT * FROM "{name}"')
                        for cell in row)
    finally:
        connection.close()


class ReplyPlanner:
    provider = "scripted"
    model_name = "reply-gate-test"
    config_version = "test-v1"

    def __init__(self, message):
        self.message = message
        self.calls = 0

    def select(self, intent_text, trusted, catalog, memory, thread_id, context_summary=None):
        self.calls += 1
        return ReplyOnly(message=self.message)


def test_g01_explanatory_reply_is_published_and_audited(tmp_path):
    path = tmp_path / "app.sqlite"
    ports = Ports()
    planner = ReplyPlanner(REMINDER)
    harness = runtime(path, ports, planner)
    open_session(harness)

    outcome = harness.handle_message(trusted(), uuid4(), "这条短信是真的吗？")

    assert outcome == ReplyOnly(message=REMINDER)
    assert planner.calls == 1
    assert harness.application.get_task("U1", "D1", "T1") is None
    assert ports.read_calls == [] and ports.submissions == 0
    events = harness.audit._events("D1", "T1")
    assert [event.event_type for event in events] == ["model.started", "model.finished"]
    assert events[-1].outcome == "succeeded"
    details = AuditReader(harness.audit, authorize=lambda *_: True).timeline(
        viewer(), "D1", "T1",
    )
    finished = next(item for item in details if item.event_type == "model.finished")
    assert finished.evidence_status == "available"
    assert json.loads(finished.evidence)["response"]["message"] == REMINDER


def test_g01_real_planner_reminder_is_not_a_model_failure(tmp_path):
    path = tmp_path / "app.sqlite"
    model = ScriptedChatModel(response_mode="reply", reply_text=REMINDER)
    planner = DeepAgentPlanner(ModelSettings(model, "scripted", model.model_name, "scripted-v1"))
    harness = runtime(path, Ports(), planner)
    open_session(harness)

    outcome = harness.handle_message(trusted(), uuid4(), "这条短信是真的吗？")

    assert outcome == ReplyOnly(message=REMINDER)
    task = harness.application.get_task("U1", "D1", "T1")
    assert task is None
    finished = [event for event in harness.audit._events("D1", "T1")
                if event.event_type == "model.finished"]
    assert [event.outcome for event in finished] == ["succeeded"]


def test_g02_credential_value_in_reply_still_fails_closed(tmp_path):
    path = tmp_path / "app.sqlite"
    ports = Ports()
    planner = ReplyPlanner("验证码是 123456，请不要告诉他人。")
    harness = runtime(path, ports, planner)
    open_session(harness)

    with pytest.raises(ValueError, match="MODEL_UNDERSTANDING_FAILED"):
        harness.handle_message(trusted(), uuid4(), "你好")

    assert harness.application.get_task("U1", "D1", "T1") is None
    assert ports.read_calls == [] and ports.submissions == 0
    events = harness.audit._events("D1", "T1")
    assert [event.event_type for event in events] == ["model.started", "model.finished"]
    assert events[-1].outcome == "failed"
    assert events[-1].payload.error.code == "MODEL_UNDERSTANDING_FAILED"
    assert "123456" not in platform_text(path)


def test_g02_english_password_label_still_fails_closed(tmp_path):
    """The audit probe has no English password label; the reply gate must not widen.

    ``journal.redact`` keeps ``password: SECRET789`` verbatim, so a narrowed gate
    without a supplementary rule would persist the secret in the model evidence.
    """

    path = tmp_path / "app.sqlite"
    ports = Ports()
    planner = ReplyPlanner("password: SECRET789")
    harness = runtime(path, ports, planner)
    open_session(harness)

    with pytest.raises(ValueError, match="MODEL_UNDERSTANDING_FAILED"):
        harness.handle_message(trusted(), uuid4(), "你好")

    assert harness.application.get_task("U1", "D1", "T1") is None
    assert ports.read_calls == [] and ports.submissions == 0
    events = harness.audit._events("D1", "T1")
    assert [event.event_type for event in events] == ["model.started", "model.finished"]
    assert events[-1].outcome == "failed"
    assert events[-1].payload.error.code == "MODEL_UNDERSTANDING_FAILED"
    assert "SECRET789" not in platform_text(path)


def test_g02_english_password_word_reminder_is_allowed(tmp_path):
    reply = "请不要把 password 或密码告诉别人，银行不会向您索要任何凭据。"
    path = tmp_path / "app.sqlite"
    planner = ReplyPlanner(reply)
    harness = runtime(path, Ports(), planner)
    open_session(harness)

    outcome = harness.handle_message(trusted(), uuid4(), "这条短信是真的吗？")

    assert outcome == ReplyOnly(message=reply)
    assert harness.application.get_task("U1", "D1", "T1") is None
    assert "SECRET789" not in platform_text(path)


def test_g03_unlabelled_six_digit_code_still_fails_closed(tmp_path):
    path = tmp_path / "app.sqlite"
    planner = ReplyPlanner("登录码 135790 已发送，请注意查收。")
    harness = runtime(path, Ports(), planner)
    open_session(harness)

    with pytest.raises(ValueError, match="MODEL_UNDERSTANDING_FAILED"):
        harness.handle_message(trusted(), uuid4(), "你好")

    assert harness.application.get_task("U1", "D1", "T1") is None
    events = harness.audit._events("D1", "T1")
    assert events[-1].outcome == "failed"
    assert "135790" not in platform_text(path)


def test_g04_user_input_credential_words_are_still_rejected(tmp_path):
    path = tmp_path / "app.sqlite"
    planner = ReplyPlanner(REMINDER)
    harness = runtime(path, Ports(), planner)
    open_session(harness)

    with pytest.raises(ValueError, match="CREDENTIAL_IN_REQUEST"):
        harness.handle_message(trusted(), uuid4(), "我的验证码是 123456，帮我看看这条短信")

    assert planner.calls == 0
    assert harness.audit._events("D1", "T1") == []
    assert harness.application.get_task("U1", "D1", "T1") is None


def test_g05_passed_reply_is_still_redacted(tmp_path):
    path = tmp_path / "app.sqlite"
    planner = ReplyPlanner(REPLY_WITH_PII)
    harness = runtime(path, Ports(), planner)
    open_session(harness)

    outcome = harness.handle_message(trusted(), uuid4(), "请再说明一下")

    masked = (
        "联系人姓名：张*，手机号 139****5678，账号 ****0002；验证码不要告诉他人。"
    )
    assert outcome == ReplyOnly(message=masked)
    for raw in (PHONE, FULL_ACCOUNT, "张三"):
        assert raw not in outcome.message
    details = AuditReader(harness.audit, authorize=lambda *_: True).timeline(
        viewer(), "D1", "T1",
    )
    finished = next(item for item in details if item.event_type == "model.finished")
    assert json.loads(finished.evidence)["response"]["message"] == masked
    stored = platform_text(path)
    for raw in (PHONE, FULL_ACCOUNT):
        assert raw not in stored
