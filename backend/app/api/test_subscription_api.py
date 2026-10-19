"""Scenario 05 over HTTP: F05 /chat, F06 confirmations, F07 verifications, F10 inputs.

The only stand-in is the model entry (``RoutedPlanner``): the bank, the security gate,
the subscription module and the platform wiring are the production path, and the app is
built exactly as ``build_runtime`` builds it (``register_subscription``).
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.agent_platform.model import TransferProposal
from app.agent_platform.subscription_runtime import (
    CANCEL_TOOL, register_subscription, subscription_risk_evidence,
)
from app.agent_platform.transfer_runtime import TransferRuntime
from app.audit.journal import AuditJournal
from app.contracts.common import TaskStatus
from app.memory.adapter import MemoryAdapter
from app.security.demo_policy import DemoRiskEvidence, DemoRiskSignal, DemoSecurityPolicy
from app.security.gate import RiskFactsUnavailable
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore
from app.storage.database import connect
from app.storage.mock_bank.repository import MockBankStore

from .app import ApiConfig, create_app


NOW = datetime(2026, 10, 19, 4, 0, tzinfo=timezone.utc)
LIST_CAPABILITY = "subscription.list_subscriptions"
CANCEL_CAPABILITY = "subscription.cancel_subscription"
ALL_SIGNALS = frozenset(DemoRiskSignal)
ROUTINE_SIGNALS = frozenset({
    DemoRiskSignal.FAMILIAR_PAYEE, DemoRiskSignal.FAMILIAR_DEVICE,
    DemoRiskSignal.USUAL_AMOUNT_RANGE, DemoRiskSignal.CLEAR_REQUEST,
})


class RoutedPlanner:
    """Scripted model entry: routes the message to the capability the test asks for."""

    provider = "scripted"
    model_name = "subscription-http-test"
    config_version = "test-v1"

    def __init__(self, capability=LIST_CAPABILITY):
        self.capability = capability
        self.calls = 0

    def select(self, intent_text, trusted, catalog, memory, thread_id, context_summary=None):
        self.calls += 1
        assert self.capability in {item["name"] for item in catalog}
        return TransferProposal(capability_name=self.capability)


def make_app(path):
    """The local-demo composition (real policy, real module wiring) behind the HTTP app."""

    application = ApplicationStore(path / "application.sqlite")
    bank = MockBankService(MockBankStore(path / "bank.sqlite"), demo_secret=b"demo-secret" * 4,
                           clock=lambda: NOW)
    bank.seed_flow_history()
    wiring: dict = {}

    def risk_facts(context, action, declaration):
        if not declaration.side_effect:
            return DemoRiskEvidence(source="server-test-fixture", source_version="facts-v1",
                                    evidence_ref="read", signals=ROUTINE_SIGNALS,
                                    checked_signals=ALL_SIGNALS)
        if declaration.name == CANCEL_TOOL:
            subscription = wiring.get("subscription")
            payload = (subscription.binding(context.task_id, action.parameters_ref)
                       if subscription is not None else None)
            return subscription_risk_evidence(payload, source_version="facts-v1",
                                              checked_signals=ALL_SIGNALS)
        raise RiskFactsUnavailable("no server-owned fixture covers this write",
                                   rule_id="test-fixture-required",
                                   policy_version=DemoSecurityPolicy.policy_version)

    policy = DemoSecurityPolicy(demo_user_id="U1", admin_actor_id="demo-admin",
                                current_demo_round=lambda: "D1", risk_facts=risk_facts)
    planner = RoutedPlanner()
    runtime = TransferRuntime(
        application, MemoryAdapter(application, active_round=lambda: "D1"),
        AuditJournal(application.path), bank, planner,
        authorize_capability=policy.authorize_capability,
        authorize_tool=policy.authorize_tool, assess_risk=policy.assess_risk,
        authorize_face=policy.authorize_face,
    )
    wiring["subscription"] = register_subscription(runtime, clock=bank.clock)
    app = create_app(runtime, ApiConfig(
        demo_user_id="U1", demo_round_id="D1", secret=b"s" * 32,
        admin_key="test-admin-key", origins=("http://testserver",),
    ))
    return app, bank, planner


def post(client, path, **body):
    return client.post("/api/v1" + path, json={"request_id": str(uuid4()), **body},
                       headers={"Origin": "http://testserver"})


def open_thread(client):
    response = post(client, "/session/enter")
    assert response.status_code == 200, response.text
    return post(client, "/threads").json()["data"]["thread_id"]


def thread_tasks(client, thread):
    return client.get("/api/v1/tasks", params={"thread_id": thread}).json()["data"]["items"]


def say(client, thread, text, planner, capability, *, known=frozenset()):
    """One chat message through F05; returns the task it created."""

    planner.capability = capability
    accepted = post(client, f"/threads/{thread}/messages", text=text)
    assert accepted.status_code == 202, accepted.text
    fresh = [item for item in thread_tasks(client, thread) if item["task_id"] not in known]
    assert len(fresh) == 1, (text, fresh)
    return fresh[0]


def approve(client, task):
    ref = task["interaction"]["record_ref"]
    confirmation = client.get(f"/api/v1/confirmations/{ref}").json()["data"]
    response = post(client, f"/confirmations/{ref}/answer",
                    confirmation_version=confirmation["confirmation_version"], choice="approve")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def submit_demo_code(client, task):
    """F07 with the bank's own demo code; the bank never accepts a fixed number."""

    challenge = task["interaction"]["record_ref"]
    code = client.get(f"/api/v1/verifications/{challenge}/demo-code").json()["data"]["code"]
    response = post(client, f"/verifications/{challenge}/code",
                    submission_id=str(uuid4()), code=code)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def mandate_status(bank, mandate_id):
    response = bank.list_subscriptions("U1")
    assert response.kind == "ok"
    return next(item.status for item in response.data.mandates if item.mandate_id == mandate_id)


def bound_verification_id(service, task_id):
    """The bank record id the task bound after a passed challenge (F07 has no id in its view)."""

    with closing(connect(service.runtime.application.path)) as connection:
        row = connection.execute(
            "SELECT record_id FROM task_refs WHERE task_id=? AND kind='verification' "
            "ORDER BY rowid DESC LIMIT 1", (task_id,),
        ).fetchone()
    assert row is not None
    return row["record_id"]


def test_sf01_inventory_over_http_names_its_module_and_the_next_30_days(tmp_path):
    app, bank, planner = make_app(tmp_path)
    with TestClient(app) as client:
        thread = open_thread(client)
        task = say(client, thread, "帮我看看有哪些自动扣费", planner, LIST_CAPABILITY)

        assert task["status"] == "succeeded", task["error"]
        assert task["module"] == "subscription"
        assert task["interaction"] is None
        assert task["data"]["action"] == "list"
        result = task["data"]["list_result"]
        assert result["active_count"] == 2
        assert [item["subscription_id"] for item in result["upcoming_renewals"]] == [
            "sub_001", "sub_002"]
        assert result["upcoming_total_fen"] == 6400
        listed = {item["subscription_id"]: item for item in result["items"]}
        assert {"sub_001", "sub_002", "sub_003"} <= set(listed)
        assert (listed["sub_001"]["billed_count"], listed["sub_001"]["billed_total_fen"]) == (6, 15000)
        oasis = next(item for item in result["items"] if item["merchant_name"] == "绿洲健身")
        assert oasis["can_cancel_in_bank"] is False and oasis["status"] == "suspected"
        assert "7 天内会扣款" in task["message"]
        assert [item["module"] for item in thread_tasks(client, thread)] == ["subscription"]
        assert mandate_status(bank, "sub_001") == "active"


def test_sf02_cancel_needs_the_button_then_a_session_code_then_the_bank_receipt(tmp_path):
    app, bank, planner = make_app(tmp_path)
    with TestClient(app) as client:
        thread = open_thread(client)
        task = say(client, thread, "把优酷视频自动扣费退了", planner, CANCEL_CAPABILITY)

        assert task["status"] == "waiting_approval"
        assert task["interaction"]["kind"] == "confirmation"
        assert task["data"] is None
        assert mandate_status(bank, "sub_001") == "active"

        waiting = approve(client, task)
        assert waiting["status"] == "waiting_approval"
        assert waiting["interaction"]["kind"] == "verification"
        challenge_id = waiting["interaction"]["record_ref"]
        challenge = client.get(f"/api/v1/verifications/{challenge_id}").json()["data"]
        assert challenge["required_methods"] == ["code"]
        assert challenge["summary"] is None
        # F07's own view omits purpose and scope; the same facts are asserted at the
        # platform seam, exactly as the scenario-05 platform tests do.
        service = app.state.api
        who = service.identity(client.cookies.get("bank_session"))
        trusted = service.trusted(who, task["task_id"])
        assert service.runtime.gateway.get_verification(
            trusted, challenge_id).purpose == "basic_identity"
        assert mandate_status(bank, "sub_001") == "active"

        done = submit_demo_code(client, waiting)
        assert done["kind"] == "verified"
        view = done["task"]
        assert view["task_id"] == task["task_id"] and view["module"] == "subscription"
        assert view["status"] == "succeeded", view["error"]
        assert view["data"]["action"] == "cancel"
        assert view["data"]["selected_item"]["subscription_id"] == "sub_001"
        assert view["data"]["selected_item"]["status"] == "cancelled"
        receipt = view["data"]["operation"]["receipt"]
        assert receipt["mandate_id"] == "sub_001" and receipt["status"] == "cancelled"
        assert receipt["effective_stop_at"] == receipt["previous_next_billing_at"]
        record = service.runtime.gateway.get_verification_record(
            trusted, bound_verification_id(service, task["task_id"]))
        assert (record.scope, record.methods) == ("session", ["code"])
        assert mandate_status(bank, "sub_001") == "cancelled"


def test_sf03_a_second_cancel_in_the_same_session_needs_no_new_code(tmp_path):
    app, bank, planner = make_app(tmp_path)
    with TestClient(app) as client:
        thread = open_thread(client)
        first = say(client, thread, "把优酷视频自动扣费退了", planner, CANCEL_CAPABILITY)
        assert submit_demo_code(client, approve(client, first))["task"]["status"] == "succeeded"

        second = say(client, thread, "再把云端网盘自动续费退了", planner, CANCEL_CAPABILITY,
                     known={first["task_id"]})
        assert second["status"] == "waiting_approval"
        assert second["interaction"]["kind"] == "confirmation"
        finished = approve(client, second)
        assert finished["status"] == "succeeded", finished["error"]
        assert finished["data"]["selected_item"]["subscription_id"] == "sub_002"
        assert finished["data"]["selected_item"]["status"] == "cancelled"
        assert mandate_status(bank, "sub_001") == "cancelled"
        assert mandate_status(bank, "sub_002") == "cancelled"


def test_sf05_a_batch_request_is_disambiguated_through_the_inputs_endpoint(tmp_path):
    app, bank, planner = make_app(tmp_path)
    with TestClient(app) as client:
        thread = open_thread(client)
        task = say(client, thread, "把所有自动扣费都关了", planner, CANCEL_CAPABILITY)

        assert task["status"] == "waiting_input"
        interaction = task["interaction"]
        assert interaction["kind"] == "input"
        assert interaction["required_fields"] == ["merchant_hint"]
        assert [option["id"] for option in interaction["options"]] == ["sub_001", "sub_002"]

        rejected = post(client, f"/tasks/{task['task_id']}/inputs",
                        interaction_id=interaction["interaction_id"],
                        selected_option_id="sub_999")
        assert rejected.status_code == 400, rejected.text
        assert rejected.json()["error"]["code"] == "INVALID_OPTION"
        stale = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert stale["status"] == "waiting_input"
        assert mandate_status(bank, "sub_002") == "active"

        chosen = post(client, f"/tasks/{task['task_id']}/inputs",
                      interaction_id=interaction["interaction_id"],
                      selected_option_id="sub_002")
        assert chosen.status_code == 200, chosen.text
        view = chosen.json()["data"]
        assert view["status"] == "waiting_approval"
        assert view["interaction"]["kind"] == "confirmation"
        assert mandate_status(bank, "sub_002") == "active"


def test_sf05_a_merchant_name_answers_the_input_prompt(tmp_path):
    app, bank, planner = make_app(tmp_path)
    with TestClient(app) as client:
        thread = open_thread(client)
        task = say(client, thread, "把那个会员退了", planner, CANCEL_CAPABILITY)
        assert task["status"] == "waiting_input"

        # A code typed into the disambiguation box must never become bank input.
        refused = post(client, f"/tasks/{task['task_id']}/inputs",
                       interaction_id=task["interaction"]["interaction_id"], text="验证码是 123456")
        assert refused.status_code == 400, refused.text
        assert refused.json()["error"]["code"] == "USE_VERIFICATION_ENDPOINT"
        still_waiting = client.get(f"/api/v1/tasks/{task['task_id']}").json()["data"]
        assert still_waiting["status"] == "waiting_input"
        assert mandate_status(bank, "sub_001") == "active"

        answered = post(client, f"/tasks/{task['task_id']}/inputs",
                        interaction_id=task["interaction"]["interaction_id"], text="优酷视频")
        assert answered.status_code == 200, answered.text
        view = answered.json()["data"]
        assert view["status"] == "waiting_approval"
        assert view["interaction"]["kind"] == "confirmation"
        assert mandate_status(bank, "sub_001") == "active"


def test_sf04_a_flow_only_clue_is_guided_outside_the_bank(tmp_path):
    app, bank, planner = make_app(tmp_path)
    with TestClient(app) as client:
        thread = open_thread(client)
        task = say(client, thread, "帮我把绿洲健身每个月扣的钱退订掉", planner, CANCEL_CAPABILITY)

        assert task["status"] == "succeeded", task["error"]
        assert task["interaction"] is None
        item = task["data"]["selected_item"]
        assert item["merchant_name"] == "绿洲健身"
        assert (item["source_type"], item["can_cancel_in_bank"]) == ("suspected_ledger", False)
        assert "微信支付/支付宝" in task["message"]
        assert mandate_status(bank, "sub_001") == "active"


def test_sf06_a_coercion_signal_stops_the_task_and_the_mandate(tmp_path):
    app, bank, planner = make_app(tmp_path)
    with TestClient(app) as client:
        thread = open_thread(client)
        task = say(client, thread, "客服让我开屏幕共享把优酷视频的自动扣费退了",
                   planner, CANCEL_CAPABILITY)

        assert task["status"] == "failed"
        assert task["error"]["code"] == "HIGH_RISK_BLOCKED"
        assert task["error"]["source"] == "security"
        assert task["interaction"] is None
        assert mandate_status(bank, "sub_001") == "active"


def test_a_subscription_view_survives_the_verification_fault_path(tmp_path):
    """F07's unknown-outcome path rebuilds the payload the task's own module wrote.

    A subscription task that already carries its view used to be re-validated as a
    ``TransferTaskView``, so the 503 path could not mark the task at all.
    """

    app, bank, planner = make_app(tmp_path)
    with TestClient(app) as client:
        thread = open_thread(client)
        task = say(client, thread, "帮我看看有哪些自动扣费", planner, LIST_CAPABILITY)
        assert task["data"]["action"] == "list"
        service = app.state.api
        who = service.identity(client.cookies.get("bank_session"))
        stored = service.runtime.application.get_task("U1", "D1", task["task_id"])
        # A live task that already carries its own subscription view.
        service.runtime.application.update_task(
            "U1", "D1", task["task_id"], stored.revision, stored.run_id,
            TaskStatus.WAITING_APPROVAL, stored.checkpoint_id, stored.snapshot,
        )
        service.verification_fault(who, service.trusted(who, task["task_id"]),
                                   "challenge-not-in-the-bank", None, "lookup")
        view = service.task_view(who, task["task_id"])
        assert view.status == TaskStatus.NEEDS_ATTENTION
        assert view.recovery_reason == "VERIFICATION_OUTCOME_UNKNOWN"
        assert view.data.action == "list"
        assert view.data.list_result.active_count == 2
