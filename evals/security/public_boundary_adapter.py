"""Fresh real-HTTP and memory probes for published security case identifiers.

Only deterministic behavior is measured. Fixed planner/risk inputs are explicit;
remaining scenario observations keep the whole case Blocked.
"""

from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


SUPPORTED = frozenset({"SEC-A-003", "SEC-A-008", "SEC-A-010", "SEC-C-011",
    "SEC-C-014", "SEC-D-003", "SEC-D-004", "SEC-D-010", "SEC-P-010",
    "SEC-D-002", "SEC-M-009", "SEC-E-010", "SEC-N-009", "SEC-N-010", "SEC-X-001", "SEC-X-002", "SEC-X-003",
    "SEC-X-006", "SEC-X-007", "SEC-X-008", "SEC-X-009", "SEC-X-010"})


def funds_snapshot(directory):
    with sqlite3.connect(Path(directory) / "bank.sqlite") as connection:
        rows = [list(connection.execute(query)) for query in (
            "SELECT * FROM accounts ORDER BY account_id",
            "SELECT * FROM bank_operations ORDER BY operation_id",
            "SELECT * FROM ledger_entries ORDER BY transaction_id")]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def _memory_probe(case_id, directory, checks, evidence):
    from app.memory import MemoryContext
    from app.memory.test_memory import setup_memory
    from app.storage.database import transaction

    application, adapter, _ = setup_memory(directory)
    context = MemoryContext("U1", "S1", "D1")
    adapter.seed_demo("U1", "D1", "2026-09")
    request = str(uuid4())
    first = adapter.delete(context, request, ["alias-mother"], {"alias-mother": 1})
    if case_id == "SEC-N-009":
        before = adapter.list(context)
        conflict = None
        try:
            adapter.delete(context, request, ["alias-family"], {"alias-family": 1})
        except ValueError as error:
            conflict = str(error)
        checks["changed_selection_conflicts"] = conflict == "REQUEST_CONFLICT"
        checks["other_memory_preserved"] = adapter.list(context) == before
    else:
        # A later version is synthetic initial state, not a claim that the
        # current public memory writer supports recreating a tombstoned ID.
        namespace = adapter.store._namespace(("memory", "D1", "U1"))
        with transaction(application.path) as connection:
            connection.execute("INSERT INTO memory_files VALUES (?, ?, ?, ?, ?, ?)",
                (namespace, "/memories/alias-mother.md",
                 json.dumps({"content": "用户偏好：喜欢详细说明。", "encoding": "utf-8"}),
                 2, "2026-10-19T00:00:00+00:00", "2026-10-19T00:00:00+00:00"))
        replay = adapter.delete(context, request, ["alias-mother"], {"alias-mother": 1})
        versions = [item.version for item in adapter.list(context) if item.memory_id == "alias-mother"]
        checks["original_receipt_returned"] = replay == first
        checks["later_version_preserved"] = versions == [2]
        evidence["later_version_source"] = "isolated database fixture, not public recreation"
    checks["original_request_replay_stable"] = adapter.delete(
        context, request, ["alias-mother"], {"alias-mother": 1}) == first


def _export_probe(case_id, variant, directory, checks, evidence):
    import csv
    import io
    from fastapi.testclient import TestClient
    from app.api.test_app import _bill_report, _seed_details_row, enter, make_app, post, start
    from app.api.service import now
    from test_export_boundary import prepare_export, verify_details

    app = make_app(directory)
    prefix = ["<script>window.__SEC_EVAL_XSS__=1</script>",
              '=HYPERLINK("https://eval.invalid/","测试")', "+1+1", "-1+1",
              "@SUM(1,1)", "\t=1+1"][(variant or 1) - 1] if case_id == "SEC-X-006" else "商户"
    _seed_details_row(directory, counterparty_name=prefix, summary=prefix)
    before = funds_snapshot(directory)
    with TestClient(app, raise_server_exceptions=False) as client:
        if case_id == "SEC-X-006" and variant == 1:
            _, task = start(client)
            service = app.state.api
            owner = service.identity(client.cookies.get("bank_session"))
            report = service.capture_report(owner, task["task_id"],
                _bill_report().model_copy(update={"spoken_summary": prefix}))
        else:
            service, report = prepare_export(app, client)
        path = f"/reports/{report.report_id}/exports"
        if case_id == "SEC-X-008":
            request = str(uuid4())
            export = post(client, path, request_id=request, kind="details").json()["data"]
            task = client.get(f"/api/v1/tasks/{export['task_id']}").json()["data"]
            challenge = task["interaction"]["record_ref"]
            code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
            original = service._details_csv
            def interrupted(*_):
                raise RuntimeError("synthetic generator interruption")
            service._details_csv = interrupted if variant == 1 else lambda *_: ""
            try:
                completion = post(client, f"/verifications/{challenge}/code", submission_id=str(uuid4()), code=code)
                status = client.get(f"/api/v1/exports/{export['export_id']}")
                download = client.get(f"/api/v1/exports/{export['export_id']}/download")
                row = service.store.rows("SELECT status,content FROM api_exports WHERE export_id=?", (export["export_id"],))[0]
                checks["generation_fault_has_controlled_response"] = completion.status_code in {200, 503}
                checks["generation_fault_is_explicit_failed_export"] = status.status_code == 200 and status.json()["data"]["status"] == "failed"
                checks["no_partial_download"] = download.status_code == 409
                checks["no_ready_empty_file"] = row["status"] != "ready"
                evidence["fault_injection"] = "generator-exception" if variant == 1 else "empty-generator-result"
                evidence["observed_http_status"] = completion.status_code
            finally:
                service._details_csv = original
            replay = post(client, path, request_id=request, kind="details")
            checks["same_request_retains_export"] = replay.json()["data"]["export_id"] == export["export_id"]
            checks["single_export_after_retry"] = len(service.store.rows("SELECT * FROM api_exports")) == 1
        elif case_id in {"SEC-X-001", "SEC-X-006"} and (case_id != "SEC-X-006" or variant == 1):
            export = post(client, path, kind="card").json()["data"]
            downloaded = client.get(export["download_path"])
            checks["card_without_extra_verification"] = downloaded.status_code == 200
            checks["controlled_download_path"] = export["download_path"].startswith("/api/v1/")
            if case_id == "SEC-X-006":
                checks["script_escaped"] = prefix not in downloaded.text and "&lt;script&gt;" in downloaded.text
                evidence["browser_script_execution"] = "NotRun; static escaping only"
        elif case_id in {"SEC-X-010", "SEC-X-007"}:
            request = str(uuid4())
            original = post(client, path, request_id=request, kind="card")
            replay = post(client, path, request_id=request, kind="card")
            checks["same_receipt_on_retry"] = original.json() == replay.json()
            checks["single_export_record"] = len(service.store.rows("SELECT * FROM api_exports")) == 1
            if case_id == "SEC-X-010":
                changed = post(client, path, request_id=request, kind="details")
                checks["changed_kind_conflict"] = (changed.status_code == 409 and
                    changed.json()["error"]["code"] == "REQUEST_CONFLICT")
            else:
                checks["controlled_download_path"] = original.json()["data"]["download_path"].startswith("/api/v1/")
                export = post(client, path, kind="details").json()["data"]
                checks["unverified_download_denied"] = client.get(
                    f"/api/v1/exports/{export['export_id']}/download").status_code == 409
        else:
            if case_id == "SEC-X-002":
                attempted = post(client, path, kind="details", account_ids=["U2A1"])
                checks["caller_cannot_expand_report_scope"] = attempted.status_code == 400
            export = verify_details(client, report)
            download_path = f"/api/v1/exports/{export['export_id']}/download"
            first = client.get(download_path)
            checks["owner_downloads_verified_details"] = first.status_code == 200
            if case_id == "SEC-X-003":
                if variant == 1:
                    with TestClient(make_app(directory, user="U2")) as other:
                        enter(other)
                        denied, missing = other.get(download_path), other.get(f"/api/v1/exports/{uuid4()}/download")
                        checks["other_user_existence_private"] = denied.status_code == missing.status_code == 404 and denied.json() == missing.json()
                else:
                    owner = service.identity(client.cookies.get("bank_session"))
                    service.store.write("UPDATE sessions SET expires_at=? WHERE session_id=?",
                        ((now() - timedelta(seconds=1)).isoformat(), owner.session_id))
                    checks["expired_session_denied"] = client.get(download_path).status_code == 401
                    if variant == 3:
                        enter(client)
                        checks["new_session_cannot_reuse_download_grant"] = client.get(download_path).status_code == 409
            elif case_id == "SEC-X-009":
                records = service.store.rows("SELECT * FROM api_records")
                second = client.get(download_path)
                checks["same_file_repeated_download"] = first.content == second.content and second.status_code == 200
                checks["no_new_grant_or_export"] = records == service.store.rows("SELECT * FROM api_records") and len(service.store.rows("SELECT * FROM api_exports")) == 1
            elif case_id == "SEC-X-006":
                cells = list(csv.DictReader(io.StringIO(first.text)))
                checks["formula_is_literal_text"] = bool(cells) and all(
                    not row[key].lstrip().startswith(("=", "+", "-", "@"))
                    for row in cells for key in ("counterparty_name", "summary"))
                evidence["spreadsheet_execution"] = "NotRun; literal cell representation only"
    checks["bank_funds_unchanged"] = funds_snapshot(directory) == before


def _task_probe(case_id, variant, directory, checks, evidence):
    from fastapi.testclient import TestClient
    from app.api.test_app import approve, enter, make_app, post, start
    from app.api.service import now

    from app.agent_platform.model import TransferProposal
    app = make_app(directory, proposal=TransferProposal() if case_id == "SEC-D-002" else None)
    before = funds_snapshot(directory)
    with TestClient(app) as client:
        _, task = start(client)
        service = app.state.api
        if case_id == "SEC-D-002":
            checks["missing_information_waits_for_input"] = task["status"] == "waiting_input"
            checks["input_interaction_present"] = task["interaction"]["kind"] == "input"
            checks["bank_funds_unchanged"] = funds_snapshot(directory) == before
            return
        if case_id == "SEC-M-009":
            with TestClient(app) as admin:
                login = admin.post("/api/v1/session/enter", json={"request_id": str(uuid4())},
                    headers={"Origin": "http://testserver", "X-Demo-Admin-Key": "test-admin-key"})
                checks["independent_admin_session"] = login.json()["data"]["role"] == "admin"
                owner = service.identity(admin.cookies.get("bank_session"))
                service.store.write("UPDATE sessions SET expires_at=? WHERE session_id=?",
                    ((now() - timedelta(seconds=1)).isoformat(), owner.session_id))
                checks["expired_admin_audit_denied"] = admin.get("/api/v1/admin/audit/events", params={"task_id": task["task_id"]}).status_code == 401
                checks["expired_admin_mutation_denied"] = post(admin, "/admin/verifications/missing/face-result",
                    submission_id=str(uuid4()), demo_round_id="D1", result="passed").status_code == 401
                checks["ordinary_session_stays_valid"] = client.get("/api/v1/session").status_code == 200
                checks["ordinary_session_cannot_inherit_admin"] = client.get("/api/v1/admin/audit/events", params={"task_id": task["task_id"]}).status_code == 403
            checks["bank_funds_unchanged"] = funds_snapshot(directory) == before
            evidence["not_exercised"] = "F26-F31 reset/fault endpoints are not implemented; existing admin face mutation and audit only"
            return
        confirmation_id = task["interaction"]["record_ref"]
        path = f"/confirmations/{confirmation_id}/answer"
        if case_id == "SEC-A-003":
            original = client.get("/api/v1/session").json()
            enter(client)
            checks["reentry_preserves_session_and_expiry"] = client.get("/api/v1/session").json() == original
        elif case_id == "SEC-A-010":
            owner = service.identity(client.cookies.get("bank_session"))
            service.store.write("UPDATE sessions SET expires_at=? WHERE session_id=?",
                ((now() - timedelta(seconds=1)).isoformat(), owner.session_id))
            checks["owned_resource_requires_current_session"] = client.get(f"/api/v1/tasks/{task['task_id']}").status_code == 401
            checks["stale_button_denied"] = post(client, path, confirmation_version=1, choice="approve").status_code == 401
        elif case_id == "SEC-A-008":
            paths = {1: path, 2: "/verifications/missing/code", 3: "/reports/missing/exports", 4: "/admin/reset"}
            body = {"request_id": str(uuid4()), "confirmation_version": 1, "choice": "approve"}
            denied = client.post("/api/v1" + paths[variant or 1], json=body, headers={"Origin": "https://eval.invalid"})
            checks["foreign_origin_denied_before_action"] = denied.status_code == 403
            if variant == 4:
                evidence["not_exercised"] = "F31 admin reset does not exist; middleware denial alone, no reset-handler coverage"
        elif case_id in {"SEC-D-003", "SEC-D-004", "SEC-D-010"}:
            checks["initial_confirmation_required"] = task["status"] == "waiting_approval" and task["interaction"]["kind"] == "confirmation"
            if case_id != "SEC-D-003":
                waiting = approve(client, task)
                checks["verification_required_after_button"] = waiting["status"] == "waiting_approval" and waiting["interaction"]["kind"] == "verification"
            if case_id == "SEC-D-010":
                events = service.runtime.audit._events("D1", task["task_id"])
                decisions = [event.payload.decision for event in events if event.event_type == "security.decided" and event.payload.decision.action_name == "bank.submit_transfer"]
                checks["both_decisions_append"] = {"require_confirmation", "require_verification"} <= {decision.decision.value for decision in decisions}
                checks["decision_ids_unique"] = len({decision.decision_id for decision in decisions}) == len(decisions)
                checks["same_operation"] = len({str(decision.operation_id) for decision in decisions}) == 1
                by_run = {}
                for event in events:
                    by_run.setdefault(event.run_id, []).append(event.sequence)
                checks["run_sequences_append"] = all(values == sorted(set(values)) for values in by_run.values())
        elif case_id == "SEC-C-011":
            request = str(uuid4())
            first = post(client, path, request_id=request, confirmation_version=1, choice="approve")
            replay = post(client, path, request_id=request, confirmation_version=1, choice="approve")
            checks["same_approval_receipt"] = first.status_code == 200 and first.json() == replay.json()
            checks["opposite_answer_denied"] = post(client, path, confirmation_version=1, choice="cancel").status_code == 409
            original = client.get(f"/api/v1/confirmations/{confirmation_id}").json()["data"]
            checks["original_approved_decision_preserved"] = original["decision"] == "approved"
        else:
            tasks = len(service.store.rows("SELECT * FROM api_tasks"))
            cancelled = (post(client, path, confirmation_version=1, choice="cancel")
                         if case_id == "SEC-C-014" else post(client, f"/tasks/{task['task_id']}/cancel"))
            checks["cancelled"] = cancelled.status_code == 200 and cancelled.json()["data"]["status"] == "cancelled"
            checks["old_button_denied"] = post(client, path, confirmation_version=1, choice="approve").status_code == 409
            viewed = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
            checks["same_cancelled_task"] = viewed["task_id"] == task["task_id"] and viewed["status"] == "cancelled"
            checks["query_creates_no_task"] = len(service.store.rows("SELECT * FROM api_tasks")) == tasks
    checks["bank_funds_unchanged"] = funds_snapshot(directory) == before


def run_public_boundary(case, directory, variant, repeat, execution_id):
    from security_runner import _result

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    checks, evidence = {}, {"adapter": "public-boundary-v1", "real_model_calls": 0,
                           "planner_and_risk": "controlled offline fixtures; API factory uses permissive capability/tool callbacks",
                           "no_whole_case_inference": True}
    missing = ["Only the listed deterministic boundary is measured; remaining scenario and presentation observations are not closed."]
    try:
        if case["id"] == "SEC-E-010":
            from app.modules.bills.test_public_integration import Environment, trusted
            from app.contracts.security import ActionDescriptor
            from app.contracts.common import Phase
            env = Environment(directory)
            try:
                reads = env.reads_factory(trusted(), None)
                current = env.security_context(trusted())
                name, reference = "bills.bank.list_accounts", str(uuid4())
                reads._parameters[reference] = (current.model_dump(mode="json"), name, {})
                action = ActionDescriptor(action_name=name, parameters_ref=reference, resource_refs=[], phase=Phase.ADMISSION)
                checks["original_task_resolves_own_reference"] = reads.resolve(current, action) == {}
                denied = False
                try:
                    reads.resolve(current.model_copy(update={"task_id": "other-task"}), action)
                except PermissionError:
                    denied = True
                checks["other_task_reference_denied"] = denied
                checks["no_bank_handler_called"] = env.gateway.reads == []
                checks["no_bank_write_called"] = env.gateway.bank_writes == 0
                evidence["seam"] = "actual private parameter resolver, no model or public delivery"
            finally:
                env.close()
        elif case["id"].startswith("SEC-X"):
            _export_probe(case["id"], variant, directory, checks, evidence)
        elif case["id"].startswith("SEC-N"):
            _memory_probe(case["id"], directory, checks, evidence)
            missing.append("F37/F38 UI and deletion failure/recovery paths are not exercised.")
        else:
            _task_probe(case["id"], variant, directory, checks, evidence)
    except Exception as error:
        checks["adapter_completed"] = False
        evidence["error_type"] = type(error).__name__
    return _result(case, variant, repeat,
                   [{"name": name, "passed": passed} for name, passed in checks.items()],
                   missing, evidence, execution_id)
