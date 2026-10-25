"""English password labels share the output/export/audit secret boundary."""

import json

import pytest

from app.audit.journal import redact
from app.audit.output_guard import OutputFinding, OutputProbe, probe_output, probe_secrets
from app.audit.test_output_guard import store_and_replay


@pytest.mark.parametrize("label", ["password", "passwd", "pwd", "PASSWORD", "PassWd", "PwD"])
@pytest.mark.parametrize("separator", [":", "：", "=", " 是 ", " 为 "])
def test_english_password_values_are_reported_and_redacted(label, separator):
    secret = "Dummy271!"
    text = f"测试凭据 {label}{separator}{secret}，请保密。"
    expected = f"测试凭据 {label}{separator}[REDACTED]，请保密。"

    assert probe_output(text) == OutputProbe((OutputFinding("credential"),), expected)
    assert probe_secrets(text) == (True, expected)
    assert redact(text, free_text=True) == expected
    assert secret not in expected


@pytest.mark.parametrize("secret", [
    "a", "7", "春暖花开", "!Dummy271", "**Dummy271!**", '"Dummy271!"',
    "!@#$", "____", "****",
])
def test_values_have_no_minimum_length_and_keep_existing_wrappers(secret):
    text = f"password: {secret}"
    assert probe_output(text).findings == (OutputFinding("credential"),)
    assert probe_secrets(text) == (True, "password: [REDACTED]")
    assert redact(text, free_text=True) == "password: [REDACTED]"


@pytest.mark.parametrize("label", ["password", "passwd", "pwd"])
@pytest.mark.parametrize("template", [
    "请不要把 {label} 告诉别人",
    "{label} 不要告诉陌生人。",
    "{label}",
    "{label}: ",
    "{label}：。",
    "{label}=\t",
    "{label} 是 ",
    "{label} 为；",
    '{label}: ""',
    "{label}: （ ）",
    "{label} policy: protect your account",
    "my_{label}: metadata",
    "{label}_hint: metadata",
    "new{label}: metadata",
    "{label}less: metadata",
])
def test_education_empty_values_and_similar_words_are_unchanged(label, template):
    text = template.format(label=label)
    assert probe_output(text) == OutputProbe((), text)
    assert probe_secrets(text) == (False, text)
    assert redact(text, free_text=True) == text


@pytest.mark.parametrize("label", ["password", "passwd", "pwd"])
@pytest.mark.parametrize("secret", ["Dummy271!", "!@#$", "____", "****"])
def test_raw_english_password_is_redacted_before_audit_write_and_export(tmp_path, label, secret):
    text = f"{label}: {secret}"
    expected = f"{label}: [REDACTED]"
    path = tmp_path / "audit.sqlite"

    # Pass RAW text to the real journal; a pre-redacted fixture could hide a leak.
    detail, package = store_and_replay(path, text)
    assert json.loads(detail.evidence)["text"] == expected
    assert package["evidence"]["REPLY1"]["content"]["text"] == expected
    assert secret.encode() not in path.read_bytes()
    assert secret not in json.dumps(package)
    assert probe_output(expected) == OutputProbe((), expected)
    assert probe_secrets(expected) == (False, expected)
    assert redact(expected, free_text=True) == expected


def test_safety_reminder_does_not_hide_a_later_password_value():
    text = "请不要把 password 告诉别人。passwd=Dummy271!，请保密。"
    expected = "请不要把 password 告诉别人。passwd=[REDACTED]，请保密。"
    assert probe_output(text) == OutputProbe((OutputFinding("credential"),), expected)
    assert probe_secrets(text) == (True, expected)
    assert redact(text, free_text=True) == expected


@pytest.mark.parametrize("text", ["password: Dummy271!", "passwd=Dummy271!", "pwd 是 Dummy271!"])
@pytest.mark.parametrize("kind", ["card", "audit"])
def test_english_password_export_is_blocked_over_http(tmp_path, text, kind):
    """Exercise the existing download consumer without changing API implementation."""
    from fastapi.testclient import TestClient

    from app.api.test_app import _bill_report, admin_login, make_app, post, start

    app = make_app(tmp_path)
    with TestClient(app) as user, TestClient(make_app(tmp_path)) as admin:
        client = user
        _, task = start(user)
        service = app.state.api
        owner = service.identity(client.cookies.get("bank_session"))
        report = service.capture_report(owner, task["task_id"], _bill_report())
        if kind == "audit":
            client = admin
            admin_login(client)
            created = post(client, "/admin/audit/exports", demo_round_id="D1")
            export_owner = "demo-admin"
        else:
            created = post(client, f"/reports/{report.report_id}/exports", kind="card")
            export_owner = owner.user_id
        assert created.status_code == 200, created.text
        export_id = created.json()["data"]["export_id"]
        row = service.store.export_row(export_id, export_owner, "D1")
        # Simulate a faulty producer in this test's isolated database.
        service.store.finish_export(
            export_id, "ready", file_name=row["file_name"], media_type=row["media_type"],
            content=(json.dumps({"leak": text}, ensure_ascii=False)
                     if kind == "audit" else f"<html>{text}</html>"),
        )

        blocked = client.get(f"/api/v1/exports/{export_id}/download")
        assert blocked.status_code == 503, blocked.text
        assert blocked.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
        assert "content-disposition" not in blocked.headers
        assert "Dummy271!" not in blocked.text
        denied = [event for event in service.runtime.audit._events("D1")
                  if event.event_type == "audit.accessed"
                  and event.payload.export_id == export_id
                  and event.payload.action == "download"]
        assert len(denied) == 1
        assert (denied[0].outcome, denied[0].payload.permitted,
                denied[0].payload.reason_code) == ("denied", False, "OUTPUT_PROBE_BLOCKED")
