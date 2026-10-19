"""Ticket04: public export boundaries using existing platform test factories.

Authorization/risk callbacks and the L03 card are controlled fixtures. These
tests prove HTTP/export behavior, not production fraud detection or L01-L03.
"""

import csv
import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.test_app import _bill_report, _seed_details_row, enter, make_app, post, start


def prepare_export(app, client):
    _, task = start(client)
    service = app.state.api
    owner = service.identity(client.cookies.get("bank_session"))
    report = service.capture_report(owner, task["task_id"], _bill_report())
    return service, report


def verify_details(client, report):
    created = post(client, f"/reports/{report.report_id}/exports", kind="details")
    assert created.status_code == 200
    export = created.json()["data"]
    waiting = client.get(f"/api/v1/tasks/{export['task_id']}")
    assert waiting.status_code == 200
    challenge = waiting.json()["data"]["interaction"]["record_ref"]
    demo = client.get(f"/api/v1/verifications/{challenge}/demo-code")
    assert demo.status_code == 200
    assert demo.headers["cache-control"] == "no-store"
    # The synthetic code stays local to the dedicated verification route.
    done = post(client, f"/verifications/{challenge}/code",
                submission_id=str(uuid4()), code=demo.json()["data"]["code"])
    assert done.status_code == 200
    assert done.json()["data"]["kind"] == "verified"
    return export


def test_same_valid_session_download_reuses_authorization_without_new_effect(tmp_path):
    app = make_app(tmp_path)
    _seed_details_row(tmp_path)
    with TestClient(app) as client:
        service, report = prepare_export(app, client)
        bank = service.runtime.gateway._bank
        bank_before = (bank.list_accounts("U1"), bank.store.list_ledger("U1", "A1"))
        export = verify_details(client, report)
        records_path = f"/api/v1/tasks/{export['task_id']}/records"
        records = client.get(records_path)
        assert records.status_code == 200
        assert service.store.rows("SELECT export_id FROM api_exports")
        for _ in range(2):
            download = client.get(f"/api/v1/exports/{export['export_id']}/download")
            assert download.status_code == 200
            assert download.headers["cache-control"] == "no-store"
            assert "楼下面馆" in download.text
            assert "6222****1234" in download.text
        assert client.get(records_path).json() == records.json()
        assert len(service.store.rows("SELECT export_id FROM api_exports")) == 1
        assert bank_before == (bank.list_accounts("U1"), bank.store.list_ledger("U1", "A1"))


def test_same_endpoint_request_id_changed_kind_conflicts_without_new_challenge(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        service, report = prepare_export(app, client)
        path = f"/reports/{report.report_id}/exports"
        request_id = str(uuid4())
        original = post(client, path, request_id=request_id, kind="card")
        assert original.status_code == 200
        records_before = service.store.rows("SELECT * FROM api_records")
        changed = post(client, path, request_id=request_id, kind="details")
        assert changed.status_code == 409
        assert changed.json()["error"]["code"] == "REQUEST_CONFLICT"
        assert len(service.store.rows("SELECT export_id FROM api_exports")) == 1
        assert service.store.rows("SELECT * FROM api_records") == records_before
        assert post(client, path, request_id=request_id, kind="card").json() == original.json()


def test_other_user_cannot_download_ready_verified_details(tmp_path):
    app = make_app(tmp_path)
    _seed_details_row(tmp_path)
    with TestClient(app) as owner_client:
        service, report = prepare_export(app, owner_client)
        export = verify_details(owner_client, report)
        path = f"/api/v1/exports/{export['export_id']}/download"
        assert owner_client.get(path).status_code == 200
        bank = service.runtime.gateway._bank
        before = (bank.list_accounts("U1"), bank.store.list_ledger("U1", "A1"))
        exports_before = service.store.rows("SELECT * FROM api_exports")
        with TestClient(make_app(tmp_path, user="U2")) as other:
            enter(other)
            actor = other.app.state.api.identity(other.cookies.get("bank_session"))
            assert actor.user_id == "U2"
            denied = other.get(path)
            unknown = other.get(f"/api/v1/exports/{uuid4()}/download")
            assert denied.status_code == unknown.status_code == 404
            assert denied.json() == unknown.json()
            assert "楼下面馆" not in denied.text
        assert owner_client.get(path).status_code == 200
        assert service.store.rows("SELECT * FROM api_exports") == exports_before
        assert before == (bank.list_accounts("U1"), bank.store.list_ledger("U1", "A1"))


def test_card_html_escapes_report_text(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        service = app.state.api
        owner = service.identity(client.cookies.get("bank_session"))
        report = _bill_report().model_copy(update={"spoken_summary": "<script>eval_marker()</script>"})
        service.capture_report(owner, task["task_id"], report)
        created = post(client, f"/reports/{report.report_id}/exports", kind="card")
        assert created.status_code == 200
        download = client.get(created.json()["data"]["download_path"])
        assert download.status_code == 200
        assert "<script>eval_marker()</script>" not in download.text
        assert "&lt;script&gt;eval_marker()&lt;/script&gt;" in download.text


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_details_csv_treats_formula_shaped_text_as_literal(tmp_path, prefix):
    app = make_app(tmp_path)
    # Synthetic arithmetic text, no external links and no spreadsheet execution.
    _seed_details_row(tmp_path, counterparty_name=prefix + "1+1", summary=prefix + "2+2")
    with TestClient(app) as client:
        _, report = prepare_export(app, client)
        export = verify_details(client, report)
        download = client.get(f"/api/v1/exports/{export['export_id']}/download")
        assert download.status_code == 200
        rows = list(csv.DictReader(io.StringIO(download.text)))
        assert len(rows) == 1
        for key in ("counterparty_name", "summary"):
            value = rows[0][key]
            assert value, "cell observation must be nonempty"
            assert not value.lstrip().startswith(("=", "+", "-", "@")), key
