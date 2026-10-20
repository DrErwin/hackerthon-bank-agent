"""Repeatable real-GLM acceptance for v04-platform/05 stage two (L03) in the default runtime.

The runner is evidence tooling, not product code: it builds the deployment composition
`app.agent_platform.local_demo:build_runtime`, drives the real HTTP app in-process and
records what happened. The model is the real configured GLM (Coding Plan endpoint); no
planner stub is involved. Credentials, verification codes and cookies never enter the
output file.

Usage (from the repo root, with a configured local demo file):
    backend/.venv/Scripts/python.exe \
        .scratch/v04-platform/evidence/2026-10-20/run_real_model_l03.py \
        [config.json] [output.json]

`config.json` defaults to `$BANK_LOCAL_CONFIG` or `<repo>/.env.local-demo.json`.
The data directory is a fresh temporary directory, so seeded bank history is rebuilt
at the bank clock and runs do not touch each other or a developer's demo state.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.agent_platform.local_demo import build_runtime, load_config  # noqa: E402
from app.api.app import ApiConfig, create_app  # noqa: E402
from app.contracts.platform import TrustedContext  # noqa: E402

PHRASINGS = [
    "帮我生成一份上个月的账单报告",
    "我想看看上个月花了多少钱，帮我生成一份账单报告",
    "生成上个月所有账户的账单报告",
]
REPORT_FIELDS = {"report_id", "scope", "summary", "spoken_summary",
                 "monthly_average_fen", "statistical_days", "average_basis",
                 "generated_at"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def post(client, path, **body):
    return client.post("/api/v1" + path, json={"request_id": str(uuid4()), **body},
                       headers={"Origin": "http://testserver"})


def enter(client):
    response = post(client, "/session/enter")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def git_head():
    return subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=False).stdout.strip()


def checks_summary(evidence):
    """Explicit pass/fail list so the file can be read without re-deriving it."""
    routing = evidence["routing_attempts"]
    chosen = next((item for item in routing if item.get("capability_name")), {})
    report_check = evidence.get("report_check") or {}
    events_check = evidence.get("events_check") or {}
    card = evidence.get("card_export") or {}
    details = evidence.get("details_export") or {}
    cross = (evidence.get("security") or {}).get("cross_identity") or {}
    audit = evidence.get("audit") or {}
    pairing = audit.get("pairing") or {}
    bank = evidence.get("bank") or {}
    share = (evidence.get("security") or {}).get("share_request") or {}
    return {
        "routed_to_bills_generate_report": chosen.get("capability_name")
        == "bills.generate_report",
        "task_is_bills_module": (evidence.get("task") or {}).get("module") == "bills",
        "task_succeeded": (evidence.get("task") or {}).get("status") == "succeeded",
        "report_matches_contract_fields": report_check.get("contract_fields_present"),
        "report_transaction_count_matches_bank": report_check.get("count_matches_bank"),
        "report_has_no_raw_transactions": report_check.get("no_raw_transactions_in_card"),
        "f21_returns_task_report": (evidence.get("f21") or {}).get("matches_task_data"),
        "report_ready_event_named": events_check.get("report_ready_count") == 1,
        "task_updated_carries_bills_payload":
            events_check.get("last_task_updated_has_payload") is True,
        "card_export_ready_without_verification":
            card.get("view", {}).get("status") == "ready"
            and card.get("view", {}).get("task_id") is None,
        "card_download_no_store": card.get("cache_control") == "no-store",
        "card_has_no_transaction_ids": card.get("contains_transaction_ids") is False,
        "details_export_requires_verification": details.get("view", {}).get("status")
        == "waiting_verification",
        "details_task_is_bills_domain": (details.get("task") or {}).get("module") == "bills",
        "details_download_gated_before_verification":
            details.get("download_before_verification") == 409,
        "details_verification_passed": (details.get("verification") or {}).get("kind")
        == "verified",
        "csv_uses_frozen_header": details.get("csv_header") == ",".join([
            "occurred_at", "account_id", "direction", "nature", "category",
            "amount_fen", "counterparty_name", "counterparty_account_masked",
            "channel", "summary", "transaction_id"]),
        "csv_rows_match_report": details.get("csv_row_count_matches_report") is True,
        "cross_identity_report_denied": cross.get("f21") == 404,
        "cross_identity_exports_denied": all(
            cross.get(key) == 404 for key in
            ("f23_card", "f24_card", "f23_details", "f24_details")),
        "audit_tool_pairs_match": pairing.get("ids_match") is True,
        "audit_security_decided_present": pairing.get("security_decided", 0) > 0,
        "zero_fund_actions": bank.get("zero_fund_actions") is True,
        "bank_balances_unchanged": bank.get("balances_unchanged") is True,
        "share_request_keeps_verification_gate":
            (share.get("details_export") or {}).get("status") == "waiting_verification",
    }


def main():
    config_path = Path(sys.argv[1] if len(sys.argv) > 1
                       else os.environ.get("BANK_LOCAL_CONFIG")
                       or (REPO_ROOT / ".env.local-demo.json"))
    out_path = Path(sys.argv[2] if len(sys.argv) > 2
                    else Path(__file__).with_name("real-model-run.json"))
    started_at = time.time()
    config = load_config(config_path)
    fresh = Path(tempfile.mkdtemp(prefix="l03-real-accept-"))
    config = config.model_copy(update={"data_directory": fresh})
    build_begin = time.monotonic()
    runtime = build_runtime(config)
    app = create_app(runtime, ApiConfig(
        secret=config.api_secret.get_secret_value().encode(),
        demo_user_id=config.demo_user_id, demo_round_id=config.demo_round_id,
        admin_user_id=config.admin_actor_id,
        admin_key=config.admin_key.get_secret_value(),
        origins=("http://testserver",),
    ))
    service = app.state.api
    bank = runtime.gateway._bank.store
    accounts = ("A1", "A5")
    balances_before = {account: bank.get_account("U1", account).book_balance_fen
                       for account in accounts}
    non_seed_before = {account: len([row for row in bank.list_ledger("U1", account)
                                     if not row["operation_id"].startswith("seed:")])
                       for account in accounts}
    evidence = {
        "run": {
            "kind": "l03_default_runtime_real_model",
            "started_at": now_iso(), "finished_at": None, "duration_s": None,
            "repo_root": str(REPO_ROOT), "base_commit": git_head(),
            "python": sys.version.split()[0],
            "runtime_factory": "app.agent_platform.local_demo:build_runtime",
            "planner": "DeepAgentPlanner (real GLM chat completion)",
            "model_name": config.model_name, "base_url": config.base_url,
            "planner_config_version": runtime.harness.planner.config_version,
            "config_source": str(config_path), "build_runtime_s":
            round(time.monotonic() - build_begin, 2),
            "data_directory_mode": "fresh temporary directory (bank reseeded at clock)",
            "transport": "FastAPI TestClient (in-process ASGI), not a deployed TCP server",
            "browser": False,
            "note": "real model + real API + real bills module + real local security "
                    "policy + real seeded mock bank; no planner stub in this run",
        },
        "catalog": [item["name"] for item in runtime.harness.registry.public_catalog()],
        "phrasings": PHRASINGS,
        "routing_attempts": [],
        "task": None, "events": None, "report": None,
        "security": {}, "audit": {}, "bank": {},
    }

    selected = None
    with TestClient(app) as client:
        session = enter(client)
        for text in PHRASINGS:
            thread = post(client, "/threads").json()["data"]["thread_id"]
            attempt = {"phrasing": text, "thread_id": thread}
            accepted = post(client, f"/threads/{thread}/messages", text=text)
            attempt["accepted_status"] = accepted.status_code
            items = client.get("/api/v1/tasks",
                               params={"thread_id": thread}).json()["data"]["items"]
            attempt["tasks"] = len(items)
            attempt["assistant_replies"] = [
                message["text"] for message in client.get(
                    f"/api/v1/threads/{thread}/messages").json()["data"]["items"]
                if message["role"] == "assistant"]
            if items:
                task = items[0]
                record = runtime.application.get_task(
                    config.demo_user_id, config.demo_round_id, task["task_id"])
                capability = (record.snapshot or {}).get("capability_name") if record else None
                attempt.update(task_id=task["task_id"], module=task["module"],
                               status=task["status"], capability_name=capability,
                               data_keys=sorted((task.get("data") or {}).keys()))
                if capability == "bills.generate_report":
                    selected = (task, client, thread, attempt)
                    evidence["routing_attempts"].append(attempt)
                    break
            evidence["routing_attempts"].append(attempt)

        if selected is None:
            evidence["verdict"] = "not_completed_L03_routing"
        else:
            task, client, thread, attempt = selected
            attempt["selected_for_chain"] = True
            if task["status"] in {"waiting_input", "waiting_approval"}:
                interaction = task["interaction"]
                options = interaction["options"]
                chosen = next((option for option in options
                               if "所有" in option["label"]), options[-1])
                chosen_response = post(
                    client, f"/tasks/{task['task_id']}/inputs",
                    interaction_id=interaction["interaction_id"],
                    selected_option_id=chosen["id"])
                evidence["resume"] = {
                    "wait_label_options": [option["label"] for option in options],
                    "selected_option": chosen["label"],
                    "http_status": chosen_response.status_code,
                }
                task = chosen_response.json()["data"]

            evidence["task"] = {key: task[key] for key in
                                ("task_id", "module", "status", "message",
                                 "run_id", "task_revision")}
            events = service.store.events(thread, None)
            evidence["events"] = [
                {"event_type": event["event_type"], "module": event["module"],
                 "task_id": event["task_id"], "event_id": event["event_id"],
                 "payload": ({key: event["payload"].get(key) for key in
                              ("report_id", "task_id", "message_id")
                              if key in event["payload"]}
                             if event["event_type"] != "task_updated" else
                             {"status": event["payload"].get("status"),
                              "module": event["payload"].get("module"),
                              "data_keys": sorted(
                                  (event["payload"].get("data") or {}).keys())})}
                for event in events]

            report = task["data"]
            evidence["report"] = report
            ready = [event for event in events if event["event_type"] == "report_ready"]
            updates = [event for event in events if event["event_type"] == "task_updated"]
            evidence["events_check"] = {
                "report_ready_count": len(ready),
                "report_ready_payload": ready[0]["payload"] if ready else None,
                "last_task_updated_module": updates[-1]["module"] if updates else None,
                "last_task_updated_has_payload": bool(
                    updates and updates[-1]["payload"].get("data")),
                "last_task_updated_report_id": (
                    updates[-1]["payload"].get("data", {}).get("report_id")
                    if updates else None),
            }

            start = datetime.fromisoformat(report["scope"]["start_at"])
            end = datetime.fromisoformat(report["scope"]["end_at"])
            context = TrustedContext(
                user_id=config.demo_user_id, session_id=session["session_id"],
                task_id=task["task_id"], run_id=task["run_id"],
                demo_round_id=config.demo_round_id, parent_task_id=None)
            bank_rows = {}
            total_rows = 0
            for account_id in report["scope"]["account_ids"]:
                result = runtime.gateway.list_transactions(context, account_id, start, end)
                rows = result.data.transactions if result.kind == "ok" else []
                bank_rows[account_id] = len(rows)
                total_rows += len(rows)
            evidence["report_check"] = {
                "contract_fields_present": set(report) == REPORT_FIELDS,
                "scope_account_ids": report["scope"]["account_ids"],
                "scope_start": report["scope"]["start_at"],
                "scope_end": report["scope"]["end_at"],
                "transaction_count": report["summary"]["transaction_count"],
                "bank_b08_rows_in_scope": total_rows,
                "bank_rows_per_account": bank_rows,
                "count_matches_bank": report["summary"]["transaction_count"] == total_rows,
                "no_raw_transactions_in_card": "transactions" not in report
                                               and "transactions" not in report["summary"],
            }

            card = client.get(f"/api/v1/reports/{report['report_id']}")
            evidence["f21"] = {"status_code": card.status_code,
                               "matches_task_data": card.json()["data"] == report}

            card_export = post(client, f"/reports/{report['report_id']}/exports",
                               kind="card")
            card_view = card_export.json()["data"]
            card_status = client.get(f"/api/v1/exports/{card_view['export_id']}")
            card_download = client.get(
                f"/api/v1/exports/{card_view['export_id']}/download")
            evidence["card_export"] = {
                "create_status": card_export.status_code, "view": card_view,
                "f23_status": card_status.json()["data"]["status"],
                "f24_status": card_download.status_code,
                "content_type": card_download.headers.get("content-type"),
                "cache_control": card_download.headers.get("cache-control"),
                "bytes": len(card_download.content),
                "sha256": hashlib.sha256(card_download.content).hexdigest(),
                "contains_transaction_ids": any(
                    row["transaction_id"] in card_download.text
                    for account in accounts
                    for row in bank.list_ledger("U1", account)),
            }

            details_export = post(client, f"/reports/{report['report_id']}/exports",
                                  kind="details")
            details = details_export.json()["data"]
            details_task = client.get(
                f"/api/v1/tasks/{details['task_id']}").json()["data"]
            before_download = client.get(
                f"/api/v1/exports/{details['export_id']}/download")
            challenge = details_task["interaction"]["record_ref"]
            demo_code = client.get(f"/api/v1/verifications/{challenge}/demo-code")
            code = demo_code.json()["data"]["code"]
            verified = post(client, f"/verifications/{challenge}/code",
                            submission_id=str(uuid4()), code=code)
            after_view = client.get(f"/api/v1/exports/{details['export_id']}")
            download = client.get(f"/api/v1/exports/{details['export_id']}/download")
            rows = list(csv.DictReader(io.StringIO(download.text)))
            export_events = [event for event in service.store.events(thread, None)
                             if event["task_id"] == details["task_id"]]
            evidence["details_export"] = {
                "create_status": details_export.status_code, "view": details,
                "task": {key: details_task[key] for key in
                         ("task_id", "module", "status", "message")},
                "task_interaction_kind": details_task["interaction"]["kind"],
                "download_before_verification": before_download.status_code,
                "verification": {
                    "demo_code_status": demo_code.status_code,
                    "demo_code_cache_control": demo_code.headers.get("cache-control"),
                    "submit_status": verified.status_code,
                    "kind": verified.json()["data"]["kind"],
                    "task_status_after": verified.json()["data"]["task"]["status"],
                },
                "f23_after": after_view.json()["data"],
                "f24_status": download.status_code,
                "content_type": download.headers.get("content-type"),
                "cache_control": download.headers.get("cache-control"),
                "csv_header": download.text.splitlines()[0],
                "csv_rows": len(rows),
                "csv_row_count_matches_report": len(rows)
                == report["summary"]["transaction_count"],
                "sha256": hashlib.sha256(download.content).hexdigest(),
                "task_updated_events": [
                    {"event_type": event["event_type"], "module": event["module"]}
                    for event in export_events
                    if event["event_type"] == "task_updated"],
            }

            with TestClient(app) as admin:
                admin_enter = admin.post(
                    "/api/v1/session/enter", json={"request_id": str(uuid4())},
                    headers={"Origin": "http://testserver",
                             "X-Demo-Admin-Key": config.admin_key.get_secret_value()})
                evidence["security"]["admin_login"] = {
                    "status": admin_enter.status_code,
                    "role": admin_enter.json()["data"]["role"],
                }
                evidence["security"]["cross_identity"] = {
                    "f21": admin.get(f"/api/v1/reports/{report['report_id']}").status_code,
                    "f23_card": admin.get(
                        f"/api/v1/exports/{card_view['export_id']}").status_code,
                    "f24_card": admin.get(
                        f"/api/v1/exports/{card_view['export_id']}/download").status_code,
                    "f23_details": admin.get(
                        f"/api/v1/exports/{details['export_id']}").status_code,
                    "f24_details": admin.get(
                        f"/api/v1/exports/{details['export_id']}/download").status_code,
                    "random_report": admin.get(f"/api/v1/reports/{uuid4()}").status_code,
                }
                audit = admin.get("/api/v1/admin/audit/events",
                                  params={"task_id": task["task_id"], "limit": 100})
                audit_items = (audit.json()["data"]["items"]
                               if audit.status_code == 200 else [])
                evidence["audit"]["http"] = {
                    "status": audit.status_code,
                    "count": len(audit_items),
                    "types": dict(Counter(item["event_type"] for item in audit_items)),
                    "modules": dict(Counter(item["module"] for item in audit_items)),
                }
                for item in audit_items:
                    if item["event_type"] in {"tool.started", "tool.finished"}:
                        detail = admin.get(
                            f"/api/v1/admin/audit/events/{item['event_id']}")
                        if detail.status_code == 200:
                            payload = detail.json()["data"].get("payload") or {}
                            item["_tool_call_id"] = payload.get("tool_call_id")
                            item["_tool_name"] = payload.get("tool_name")
                started_ids = {item["_tool_call_id"] for item in audit_items
                               if item["event_type"] == "tool.started"}
                finished_ids = {item["_tool_call_id"] for item in audit_items
                                if item["event_type"] == "tool.finished"}
                evidence["audit"]["pairing"] = {
                    "tool_started": len(started_ids),
                    "tool_finished": len(finished_ids),
                    "ids_match": started_ids == finished_ids,
                    "tool_names": sorted({item["_tool_name"] for item in audit_items
                                          if item.get("_tool_name")}),
                    "security_decided": sum(
                        1 for item in audit_items
                        if item["event_type"] == "security.decided"),
                    "outcomes": dict(Counter(item["outcome"] for item in audit_items)),
                }

            share_thread = post(client, "/threads").json()["data"]["thread_id"]
            share_message = post(client, f"/threads/{share_thread}/messages",
                                 text="帮我生成上个月所有账户的账单报告，分享给孩子看")
            share_items = client.get("/api/v1/tasks", params={
                "thread_id": share_thread}).json()["data"]["items"]
            share_task = share_items[0] if share_items else None
            share_report_id = (share_task or {}).get("data", {}).get("report_id")
            share_details = None
            if share_report_id:
                share_export = post(client, f"/reports/{share_report_id}/exports",
                                    kind="details")
                share_details = {
                    "create_status": share_export.status_code,
                    "status": share_export.json()["data"]["status"],
                    "task_id": share_export.json()["data"]["task_id"],
                }
            evidence["security"]["share_request"] = {
                "message_status": share_message.status_code,
                "report_generated": bool(share_report_id),
                "details_export": share_details,
                "note": "share_request 只记录意图；无第三方身份、无外发通道，"
                        "明细仍需本人本次验证",
            }

        balances_after = {account: bank.get_account("U1", account).book_balance_fen
                          for account in accounts}
        non_seed_after = {account: len([row for row in bank.list_ledger("U1", account)
                                        if not row["operation_id"].startswith("seed:")])
                          for account in accounts}
        evidence["bank"] = {
            "balances_before": balances_before, "balances_after": balances_after,
            "balances_unchanged": balances_before == balances_after,
            "non_seed_ledger_before": non_seed_before,
            "non_seed_ledger_after": non_seed_after,
            "zero_fund_actions": sum(non_seed_after.values()) == 0,
            "seeded_ledger_rows": {account: len(bank.list_ledger("U1", account))
                                   - non_seed_after[account] for account in accounts},
        }
        evidence["run"]["finished_at"] = now_iso()
        evidence["run"]["duration_s"] = round(time.time() - started_at, 2)
        evidence["verdict"] = evidence.get("verdict", "completed")

    evidence["checks"] = checks_summary(evidence)
    evidence["checks"]["all_passed"] = all(evidence["checks"].values())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print("EVIDENCE", out_path)
    print("VERDICT", evidence["verdict"], "ALL_CHECKS_PASSED", evidence["checks"]["all_passed"])
    print("DURATION_S", evidence["run"]["duration_s"])
    failed = [name for name, passed in evidence["checks"].items() if passed is not True]
    if failed:
        print("FAILED_CHECKS", failed)


if __name__ == "__main__":
    main()
