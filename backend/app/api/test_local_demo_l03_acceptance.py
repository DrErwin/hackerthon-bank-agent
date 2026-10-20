"""v04-platform/05 stage two acceptance: L03 report chain in the default runtime.

`local_demo.build_runtime` is the deployment factory: it assembles the real API, the
real bills module (L01 + L03), the real local security policy and the seeded mock
bank. Only the model replies are scripted here so the acceptance runs in CI; the same
chain driven by the real GLM is recorded in
`.scratch/v04-platform/evidence/2026-10-20/` (real-model-run*.json).

Two facts are shared by every test: L03 is reached from a natural-language message
through the real Deep Agents planning entry (scripted completion), and no money moves
on any path.

Run from `backend/`: `python -m pytest -q app/api/test_local_demo_l03_acceptance.py`
"""

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.agent_platform.local_demo import LocalDemoConfig, build_runtime
from app.agent_platform.test_harness import ScriptedChatModel
from app.api.app import ApiConfig, create_app
from app.api.service import DETAILS_CSV_HEADER
from app.contracts.common import SecurityDecisionCode
from app.contracts.platform import TrustedContext
from app.modules.bills.manifest import REPORT_MANIFEST

from .test_app import enter, post

ADMIN_KEY = "l03-acceptance-admin"
BEIJING = timezone(timedelta(hours=8))
EXAMPLE_CONFIG = Path(__file__).parents[1] / "agent_platform" / "local_demo.example.json"
REPORT_FIELDS = {"report_id", "scope", "summary", "spoken_summary",
                 "monthly_average_fen", "statistical_days", "average_basis",
                 "generated_at"}


class ReportModel(ScriptedChatModel):
    """Controlled completion for the real planner; it proposes the real L03 name."""

    model_name: str = "glm-4.7"

    def _get_ls_params(self, **kwargs):
        return {"ls_provider": "openai", "ls_model_name": self.model_name}

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if any(isinstance(item, ToolMessage) for item in messages):
            return ChatResult(generations=[ChatGeneration(
                message=AIMessage(content="已记录账单报告候选。"))])
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[{
            "name": "propose_transfer",
            "args": {"capability_name": "bills.generate_report"},
            "id": "call-l03", "type": "tool_call",
        }]))])


def local_demo_app(tmp_path):
    """The production composition with only the model substituted."""
    content = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    content.update(api_key="l03-acceptance-model-key", api_secret="s" * 32,
                   bank_secret="b" * 32, admin_key=ADMIN_KEY,
                   data_directory=str(tmp_path.resolve()),
                   # LocalDemoConfig only accepts browser-local origins; the app under
                   # test keeps TestClient's own origin, exactly like test_local_demo.
                   origins=["http://localhost:5173"])
    config = LocalDemoConfig.model_validate(content)
    with patch("app.agent_platform.local_demo.ChatOpenAI", return_value=ReportModel()):
        runtime = build_runtime(config)
    app = create_app(runtime, ApiConfig(
        secret=config.api_secret.get_secret_value().encode(),
        demo_user_id=config.demo_user_id, demo_round_id=config.demo_round_id,
        admin_user_id=config.admin_actor_id, admin_key=ADMIN_KEY,
        origins=("http://testserver",)))
    return app, runtime, config


def start_report_task(client):
    """Natural-language message -> real L03 task waiting for its account choice."""
    entered = enter(client)
    thread = post(client, "/threads").json()["data"]["thread_id"]
    accepted = post(client, f"/threads/{thread}/messages", text="帮我生成上个月的账单报告")
    assert accepted.status_code == 202, accepted.text
    items = client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"]
    assert len(items) == 1
    return entered, thread, items[0]


def choose_all_accounts(client, task):
    """F10 option reply resumes the waiting L03 task on real data (#122 seam 2)."""
    interaction = task["interaction"]
    assert interaction["kind"] == "input"
    option = next(item for item in interaction["options"]
                  if item["label"] == "所有本人账户")
    response = post(client, f"/tasks/{task['task_id']}/inputs",
                    interaction_id=interaction["interaction_id"],
                    selected_option_id=option["id"])
    assert response.status_code == 200, response.text
    return response.json()["data"]


def assert_zero_fund_actions(bank):
    for account_id in ("A1", "A5"):
        rows = bank.list_ledger("U1", account_id)
        assert rows and all(row["operation_id"].startswith("seed:") for row in rows)


def entered_context(entered, task):
    return TrustedContext(
        user_id="U1", session_id=entered["session_id"],
        task_id=task["task_id"], run_id=task["run_id"],
        demo_round_id="D1", parent_task_id=None)


def bank_rows_for_report(runtime, entered, task):
    report = task["data"]
    start = datetime.fromisoformat(report["scope"]["start_at"])
    end = datetime.fromisoformat(report["scope"]["end_at"])
    context = entered_context(entered, task)
    rows = []
    for account_id in report["scope"]["account_ids"]:
        result = runtime.gateway.list_transactions(context, account_id, start, end)
        assert result.kind == "ok"
        rows.extend(result.data.transactions)
    return rows


def assert_report_matches_contract(report):
    assert set(report) == REPORT_FIELDS
    assert report["scope"]["account_ids"] == ["A1", "A5"]
    scope_start = datetime.fromisoformat(report["scope"]["start_at"])
    scope_end = datetime.fromisoformat(report["scope"]["end_at"])
    now = datetime.now(BEIJING)
    first_of_month = datetime(now.year, now.month, 1, tzinfo=BEIJING)
    previous_month = (first_of_month - timedelta(days=1)).replace(day=1)
    assert scope_start == previous_month
    assert scope_end == first_of_month
    summary = report["summary"]
    assert summary["transaction_count"] > 0
    assert summary["consumption_net_fen"] == (
        summary["consumption_gross_fen"] - summary["consumption_refund_fen"])
    assert report["monthly_average_fen"] is not None
    # Contract §5.3 wording: a 30-day conversion, never a calendar-month claim.
    assert "每月30天" in report["average_basis"] or "30 天" in report["average_basis"]
    # A report card is the controlled summary only; raw flows never ride along.
    assert "transactions" not in report and "transactions" not in summary


def test_l03_report_chain_f21_f22_f24_and_122_seams(tmp_path):
    app, runtime, _config = local_demo_app(tmp_path)
    service = app.state.api
    bank = runtime.gateway._bank.store
    registry = runtime.harness.registry
    assert registry.get("bills.generate_report").manifest is REPORT_MANIFEST

    with TestClient(app) as client:
        entered, thread, task = start_report_task(client)

        # P01/P02: the second module owns the task and its events.
        assert task["module"] == "bills"
        assert task["status"] == "waiting_input"
        assert task["interaction"]["kind"] == "input"
        first_events = service.store.events(thread, None)
        first_updates = [event for event in first_events
                         if event["event_type"] == "task_updated"]
        assert first_updates and first_updates[-1]["module"] == "bills"

        # Issue #122 seam 2: resume through the platform input entry, no transfer typing.
        task = choose_all_accounts(client, task)
        assert task["module"] == "bills"
        assert task["status"] == "succeeded", task
        report = task["data"]
        assert "operation_id" not in report
        assert_report_matches_contract(report)

        # The module result came from the real report service, not the contract stub.
        assert "契约形状桩" not in task["message"]
        assert str(report["summary"]["transaction_count"]) in task["message"]

        # Report storage: F21 returns the exact card the task produced.
        card = client.get(f"/api/v1/reports/{report['report_id']}")
        assert card.status_code == 200, card.text
        assert card.json()["data"] == report

        # §6.6: report_ready names the card; Issue #122 seam 1: task_updated carries
        # the second module's own payload from real data.
        events = service.store.events(thread, None)
        ready = [event for event in events if event["event_type"] == "report_ready"]
        assert len(ready) == 1
        assert ready[0]["module"] == "bills"
        assert ready[0]["payload"] == {"task_id": task["task_id"],
                                       "report_id": report["report_id"]}
        updates = [event for event in events if event["event_type"] == "task_updated"]
        assert updates[-1]["module"] == "bills"
        assert updates[-1]["payload"]["data"]["report_id"] == report["report_id"]
        assert updates[-1]["payload"]["data"]["scope"] == report["scope"]
        assert updates[-1]["payload"]["data"]["summary"] == report["summary"]
        messages = client.get(f"/api/v1/threads/{thread}/messages").json()["data"]["items"]
        assert report["report_id"] in [item for message in messages
                                       if message["role"] == "assistant"
                                       for item in message["report_ids"]]

        # Real bank facts behind the card: the count is the scoped B08 row count.
        bank_rows = bank_rows_for_report(runtime, entered, task)
        assert report["summary"]["transaction_count"] == len(bank_rows)
        assert {row.account_id for row in bank_rows} == {"A1", "A5"}

        # F22 card export is an ordinary operation: ready at once, no verification.
        card_export = post(client, f"/reports/{report['report_id']}/exports", kind="card")
        assert card_export.status_code == 200, card_export.text
        card_view = card_export.json()["data"]
        assert card_view["kind"] == "card" and card_view["status"] == "ready"
        assert card_view["task_id"] is None
        assert card_view["media_type"] == "text/html"
        assert client.get(f"/api/v1/exports/{card_view['export_id']}") \
            .json()["data"]["status"] == "ready"
        card_file = client.get(f"/api/v1/exports/{card_view['export_id']}/download")
        assert card_file.status_code == 200
        assert card_file.headers["cache-control"] == "no-store"
        assert report["spoken_summary"] in card_file.text
        assert report["report_id"] in card_file.text
        assert not any(row.transaction_id in card_file.text for row in bank_rows)

        # F22 details: a sensitive export opens its own bills-domain platform task.
        details_export = post(client, f"/reports/{report['report_id']}/exports",
                              kind="details")
        assert details_export.status_code == 200, details_export.text
        details = details_export.json()["data"]
        assert details["status"] == "waiting_verification"
        assert details["task_id"] and details["download_path"] is None
        export_task = client.get(f"/api/v1/tasks/{details['task_id']}").json()["data"]
        assert export_task["module"] == "bills"                      # Issue #122 seam 3
        assert export_task["status"] == "waiting_approval"
        assert export_task["interaction"]["kind"] == "verification"
        export_events = [event for event in service.store.events(thread, None)
                         if event["task_id"] == details["task_id"]]
        assert export_events
        assert {event["module"] for event in export_events} == {"bills"}
        assert client.get(f"/api/v1/exports/{details['export_id']}/download") \
            .status_code == 409

        # F17/F19: the fresh code is no-store and never leaks into chat or events.
        challenge = export_task["interaction"]["record_ref"]
        demo_code = client.get(f"/api/v1/verifications/{challenge}/demo-code")
        assert demo_code.status_code == 200
        assert demo_code.headers["cache-control"] == "no-store"
        code = demo_code.json()["data"]["code"]
        verified = post(client, f"/verifications/{challenge}/code",
                        submission_id=str(uuid4()), code=code)
        assert verified.status_code == 200, verified.text
        assert verified.json()["data"]["kind"] == "verified"
        assert verified.json()["data"]["task"]["status"] == "succeeded"
        assert code not in client.get(f"/api/v1/threads/{thread}/messages").text
        assert code not in json.dumps(service.store.events(thread, None),
                                      ensure_ascii=False)

        # F23/F24: the CSV follows the frozen header and the same report scope.
        ready_view = client.get(f"/api/v1/exports/{details['export_id']}").json()["data"]
        assert ready_view["status"] == "ready"
        assert ready_view["media_type"] == "text/csv"
        download = client.get(f"/api/v1/exports/{details['export_id']}/download")
        assert download.status_code == 200
        assert download.headers["cache-control"] == "no-store"
        rows = list(csv.DictReader(io.StringIO(download.text)))
        assert download.text.splitlines()[0] == ",".join(DETAILS_CSV_HEADER)
        assert len(rows) == report["summary"]["transaction_count"] == len(bank_rows)
        by_id = {row["transaction_id"]: row for row in rows}
        assert set(by_id) == {row.transaction_id for row in bank_rows}
        for fact in bank_rows:
            written = by_id[fact.transaction_id]
            assert written["account_id"] == fact.account_id
            assert written["occurred_at"] == fact.occurred_at.isoformat()
            assert written["direction"] == fact.direction
            assert written["nature"] == fact.nature
            assert written["category"] == fact.category
            assert int(written["amount_fen"]) == fact.amount_fen
            assert written["counterparty_name"] == fact.counterparty_name
            assert written["counterparty_account_masked"] == (
                fact.counterparty_account_masked or "")

    assert_zero_fund_actions(bank)


def test_l03_cross_identity_denials_share_intent_and_audit(tmp_path):
    app, runtime, config = local_demo_app(tmp_path)
    service = app.state.api
    with TestClient(app) as client:
        _entered, thread, task = start_report_task(client)
        task = choose_all_accounts(client, task)
        report = task["data"]
        card = post(client, f"/reports/{report['report_id']}/exports",
                    kind="card").json()["data"]
        details = post(client, f"/reports/{report['report_id']}/exports",
                       kind="details").json()["data"]

        # Another authenticated identity (the demo admin) gets no access at all.
        with TestClient(app) as admin:
            login = admin.post("/api/v1/session/enter", json={"request_id": str(uuid4())},
                               headers={"Origin": "http://testserver",
                                        "X-Demo-Admin-Key": ADMIN_KEY})
            assert login.status_code == 200 and login.json()["data"]["role"] == "admin"
            assert admin.get(f"/api/v1/reports/{report['report_id']}").status_code == 404
            assert admin.get(f"/api/v1/exports/{card['export_id']}").status_code == 404
            assert admin.get(
                f"/api/v1/exports/{card['export_id']}/download").status_code == 404
            assert admin.get(f"/api/v1/exports/{details['export_id']}").status_code == 404
            assert admin.get(
                f"/api/v1/exports/{details['export_id']}/download").status_code == 404
            assert admin.get(f"/api/v1/reports/{uuid4()}").status_code == 404

            # Audit trail: tool pairs, security decisions and transitions exist.
            audit = admin.get("/api/v1/admin/audit/events",
                              params={"task_id": task["task_id"], "limit": 100})
            assert audit.status_code == 200, audit.text
            event_types = {item["event_type"] for item in audit.json()["data"]["items"]}
            assert {"tool.started", "tool.finished",
                    "security.decided", "task.transition"} <= event_types

        journal = runtime.audit._events(config.demo_round_id, task["task_id"])
        started = {event.payload.tool_call_id for event in journal
                   if event.event_type == "tool.started"}
        finished = {event.payload.tool_call_id for event in journal
                    if event.event_type == "tool.finished"}
        assert started and started == finished
        decisions = [event.payload.decision for event in journal
                     if event.event_type == "security.decided"]
        assert decisions
        assert all(decision.decision == SecurityDecisionCode.ALLOW
                   for decision in decisions)

        # share_request only states intent: the card stays owner-only and the details
        # export still requires this user's fresh verification (no third-party grant).
        share_thread = post(client, "/threads").json()["data"]["thread_id"]
        shared = post(client, f"/threads/{share_thread}/messages",
                      text="帮我生成上个月所有账户的账单报告，分享给孩子看")
        assert shared.status_code == 202, shared.text
        share_task = client.get("/api/v1/tasks", params={
            "thread_id": share_thread}).json()["data"]["items"][0]
        assert share_task["module"] == "bills" and share_task["status"] == "succeeded"
        share_report = share_task["data"]
        assert share_report["report_id"] != report["report_id"]
        assert client.get(f"/api/v1/reports/{share_report['report_id']}").status_code == 200
        share_export = post(client, f"/reports/{share_report['report_id']}/exports",
                            kind="details").json()["data"]
        assert share_export["status"] == "waiting_verification"
        assert share_export["task_id"]
        assert client.get(f"/api/v1/exports/{share_export['export_id']}/download") \
            .status_code == 409
        with TestClient(app) as admin:
            admin.post("/api/v1/session/enter", json={"request_id": str(uuid4())},
                       headers={"Origin": "http://testserver",
                                "X-Demo-Admin-Key": ADMIN_KEY})
            assert admin.get(
                f"/api/v1/reports/{share_report['report_id']}").status_code == 404
            assert admin.get(
                f"/api/v1/exports/{share_export['export_id']}").status_code == 404

    assert_zero_fund_actions(runtime.gateway._bank.store)
