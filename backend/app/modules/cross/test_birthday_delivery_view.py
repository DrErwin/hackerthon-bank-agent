"""v05-cross-business/05: controlled delivery and bank-backed task facts."""

from uuid import uuid4

import pytest

from app.contracts.common import TaskStatus
from app.contracts.cross import CrossStartInput
from app.modules.cross.test_cross_birthday import (
    ScriptedBirthdayPorts, birthday_composition, parent_trusted, store_delivery,
    run_to_freeze, confirm_until_settled, option_id, BUDGET_ID,
)


def test_delivery_is_requested_as_a_controlled_form(tmp_path):
    _, entry, application = birthday_composition(tmp_path, ScriptedBirthdayPorts())
    entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(), goal="给妈妈过生日"))
    entry.resume(parent_trusted(), {"text": "500元"})
    ask = entry.resume(parent_trusted(), {"text": "2026-10-30"})
    assert ask.interaction.required_fields == ["delivery"]
    assert "请输入引用编号" not in ask.message
    store_delivery(application)
    picked = entry.resume(parent_trusted(), {
        "interaction_id": ask.interaction.interaction_id, "text": "deliver-ref-0001",
    })
    assert picked.interaction.required_fields == ["cross_selection"]
    for raw in ("13800000000", "幸福小区"):
        assert raw not in picked.model_dump_json()


def test_waiting_and_unknown_payment_keep_verified_order_and_freeze(tmp_path):
    ports = ScriptedBirthdayPorts(captures=("unknown",))
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry, picks=("康乃馨",))
    entry.resume(parent_trusted(), {"choice": "approve"})
    waiting = entry.resume(parent_trusted(), {"choice": "approve"})
    order = next(s for s in waiting.data.steps if s.action == "bank.create_order")
    assert order.order_id == "ord_LOWER"
    assert order.status is TaskStatus.SUCCEEDED
    unknown = entry.resume(parent_trusted(), {"choice": "approve"})
    capture = next(s for s in unknown.data.steps if s.action == "bank.capture_frozen")
    assert capture.status is TaskStatus.NEEDS_ATTENTION
    assert str(capture.operation_id) == ports.last_capture_op
    assert capture.amount_fen is None and capture.payment_status is None
    order = next(s for s in unknown.data.steps if s.action == "bank.create_order")
    assert order.order_id == "ord_LOWER" and order.payment_status is None
    remaining = next(s for s in unknown.data.steps if s.step_id == "birthday-remaining")
    assert remaining.amount_fen is None


@pytest.mark.parametrize("owner,round_id,task_id,kind", [
    ("U2", "D1", "FOREIGN", "delivery"),
    ("U1", "D2", "FOREIGN", "delivery"),
    ("U1", "D1", "FOREIGN", "delivery"),
    ("U1", "D1", "PARENT", "payee"),
])
def test_unusable_delivery_reference_never_advances(tmp_path, owner, round_id, task_id, kind):
    from datetime import datetime, timedelta, timezone
    _, entry, application = birthday_composition(tmp_path, ScriptedBirthdayPorts())
    entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(), goal="给妈妈过生日"))
    entry.resume(parent_trusted(), {"text": "500元"})
    entry.resume(parent_trusted(), {"text": "2026-10-30"})
    if task_id != "PARENT":
        now = datetime.now(timezone.utc)
        application.create_session("FOREIGN_SESSION", owner, round_id, now.isoformat(),
                                   (now + timedelta(days=1)).isoformat())
        application.create_task(task_id, owner, "FOREIGN_SESSION", round_id, "R2", "running", {})
    application.store_controlled_detail("foreign-ref-0001", owner, round_id, task_id,
                                       kind, {"address": "秘密地址"}, "2026-10-25T00:00:00+00:00")
    rejected = entry.resume(parent_trusted(), {"text": "foreign-ref-0001"})
    assert rejected.interaction.required_fields == ["delivery"]
    assert "秘密地址" not in rejected.model_dump_json()


@pytest.mark.parametrize("release_status", ["needs_attention", "blocked"])
def test_unverified_ending_keeps_occupation_and_never_restarts_buying(tmp_path, release_status):
    ports = ScriptedBirthdayPorts(release_status=release_status)
    if release_status == "blocked":
        from app.modules.cross.birthday_ports import ReleaseOutcome
        ports.finalize = lambda *args: ReleaseOutcome(status="blocked")
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    entry.resume(parent_trusted(), {"choice": "approve"})
    stopped = entry.resume(parent_trusted(), {"cancel": True})
    assert stopped.status is TaskStatus.RUNNING
    assert next(s for s in stopped.data.steps if s.step_id == "birthday-release").amount_fen is None
    commitments = application.list_budget_commitments("U1", "D1", BUDGET_ID, include_closed=True)
    assert commitments[0].state == "active"
    replay = entry.resume(parent_trusted(), {})
    assert replay.status is TaskStatus.RUNNING and ports.order_executes == []


def test_stop_during_unknown_payment_only_queries_then_releases(tmp_path):
    ports = ScriptedBirthdayPorts(captures=("unknown",), requery_auto=True,
                                  released_amount_fen=30100)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    entry.resume(parent_trusted(), {"choice": "approve"})
    entry.resume(parent_trusted(), {"choice": "approve"})
    unknown = entry.resume(parent_trusted(), {"choice": "approve"})
    stopping = entry.resume(parent_trusted(), {"cancel": True})
    # Retrying the original pending operation after stop must not revive cake.
    stopped = entry.resume(parent_trusted(), {
        "selected_option_id": option_id(stopping, "核实原操作"),
    })
    assert stopped.status is TaskStatus.PARTIALLY_SUCCEEDED
    assert ports.order_executes == ["P_FLOWER"]
    assert ports.capture_executes == ["P_FLOWER"]


def test_verified_freeze_binding_clears_old_unknown_without_guessing_amount(tmp_path):
    ports = ScriptedBirthdayPorts(freeze="unknown")
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    held = entry.resume(parent_trusted(), {"choice": "approve"})
    entry.resume(parent_trusted(), {"selected_option_id": option_id(held, "核实原操作")})
    # Binding verified the original freeze id; the optional receipt read gave
    # no amount, so it stays empty while the verified ending is still visible.
    done = confirm_until_settled(entry)
    assert done.status is TaskStatus.SUCCEEDED
    frozen = next(s for s in done.data.steps if s.step_id == "birthday-freeze")
    assert frozen.status is TaskStatus.SUCCEEDED and frozen.result_ref == "fz_001"
    assert frozen.amount_fen is None
    remaining = next(s for s in done.data.steps if s.step_id == "birthday-remaining")
    assert remaining.status is TaskStatus.SUCCEEDED and remaining.amount_fen == 0


@pytest.mark.parametrize("stop_after_flower", [False, True])
def test_receipts_match_real_bank_at_waiting_and_complete_states(tmp_path, stop_after_flower):
    from app.agent_platform.test_birthday_runtime_wiring import (
        composition, trusted, run_to_freeze_question, approve_confirmation,
        answer_verification,
    )
    runtime, entry = composition(tmp_path)
    who = trusted(runtime)
    try:
        current = run_to_freeze_question(entry)
        snapshots = []
        for _ in range(24):
            snapshots.append(current)
            if current.status in (TaskStatus.SUCCEEDED, TaskStatus.PARTIALLY_SUCCEEDED):
                break
            if stop_after_flower and current.data and any(
                s.action == "bank.capture_frozen" and s.status is TaskStatus.SUCCEEDED
                for s in current.data.steps
            ):
                current = entry.resume(who, {"cancel": True})
                continue
            interaction = current.interaction
            if interaction.kind == "confirmation":
                approve_confirmation(runtime, who, interaction.record_ref)
                current = entry.resume(who, {"choice": "approve"})
            elif interaction.kind == "verification":
                answer_verification(runtime, who, "R1", interaction.record_ref)
                current = entry.resume(who, {"choice": "resume"})
            else:
                pytest.fail(f"Unexpected interaction: {interaction.kind}")
        assert current.status is (TaskStatus.PARTIALLY_SUCCEEDED if stop_after_flower else TaskStatus.SUCCEEDED)
        steps = current.data.steps
        freeze = next(s for s in steps if s.action == "bank.freeze_funds")
        captures = [s for s in steps if s.action == "bank.capture_frozen"]
        orders = [s for s in steps if s.action == "bank.create_order"]
        release = next(s for s in steps if s.action == "bank.release_frozen")
        remaining = next(s for s in steps if s.step_id == "birthday-remaining")
        assert freeze.amount_fen == 50000 and freeze.result_ref
        assert {s.amount_fen for s in captures} == ({19900} if stop_after_flower else {19900, 26800})
        assert release.amount_fen == (30100 if stop_after_flower else 3300)
        assert remaining.amount_fen == 0
        assert len(orders) == (1 if stop_after_flower else 2)
        assert all(s.order_id and s.payment_status == "paid" for s in orders)
        for step in [freeze, *captures, *orders, release]:
            assert step.operation_id and step.result_ref
        # The bank query, not message parsing or basket arithmetic, is our oracle.
        bank = runtime.gateway.get_freeze(who, freeze.result_ref).data
        assert bank.original_amount_fen == freeze.amount_fen
        assert bank.captured_total_fen == (19900 if stop_after_flower else 46700)
        consumed = next(s for s in steps if s.step_id == "birthday-consumed")
        assert consumed.amount_fen == bank.captured_total_fen
        assert bank.released_total_fen == release.amount_fen
        assert bank.remaining_fen == remaining.amount_fen
        waiting = next(s for s in snapshots if s.data and any(
            row.action == "bank.create_order" for row in s.data.steps))
        assert any(s.action == "bank.freeze_funds" and s.amount_fen == 50000
                   for s in waiting.data.steps)
        assert current.data.budget is None  # no fabricated adopted personal budget
        replay = entry.resume(who, {})
        assert replay.model_dump(mode="json")["data"] == current.model_dump(mode="json")["data"]
    finally:
        runtime.gateway.close()


def test_controlled_delivery_http_to_real_birthday_entry(tmp_path):
    import json
    from fastapi.testclient import TestClient
    from app.agent_platform.test_birthday_runtime_wiring import composition
    from app.api.app import ApiConfig, create_app
    from app.api.test_app import enter, post
    from app.contracts.platform import TrustedContext
    from app.memory.adapter import MemoryContext
    from app.modules.cross.entry import CrossEntry

    runtime, _ = composition(tmp_path)
    app = create_app(runtime, ApiConfig(secret=b"delivery-view-test-secret-32-bytes",
        admin_key="test", origins=("http://testserver",), demo_round_id="D1"))
    client = TestClient(app)
    api = app.state.api
    session = enter(client)
    thread = post(client, "/threads").json()["data"]["thread_id"]
    who = TrustedContext(user_id="U1", session_id=session["session_id"],
        demo_round_id="D1", task_id="FORM", run_id="RFORM", parent_task_id=None)
    metadata = {"capability_name": "cross.start_task", "trace_id": str(uuid4()),
                "request_id": str(uuid4()), "intent_text": "生日",
                "config_version": runtime.harness.planner.config_version}
    runtime.application.create_task("FORM", "U1", who.session_id, "D1", "RFORM", "running", metadata)
    saver = runtime.memory.checkpointer(MemoryContext("U1", who.session_id, "D1"), "FORM")
    entry = CrossEntry(runtime.harness, saver, None, runtime.gateway._bank.clock,
                       runtime.birthday.ports_factory)
    entry.start(who, CrossStartInput(request_id=uuid4(), goal="给妈妈过生日"))
    entry.resume(who, {"text": "500元"})
    ask = entry.resume(who, {"text": "2026-10-30"})
    task = runtime.application.get_task("U1", "D1", "FORM")
    runtime.application.update_task("U1", "D1", "FORM", task.revision, task.run_id,
        ask.status, None, {**metadata, "result": ask.model_dump(mode="json")})
    api.store.write("INSERT INTO api_tasks (task_id,thread_id,user_id,session_id,demo_round_id,"
        "run_id,created_at,request_id,intent_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("FORM", thread, "U1", who.session_id, "D1", "RFORM", session["created_at"], str(uuid4()), "生日"))
    fields = {"recipient_name": "张三丰", "phone": "13800001234", "address": "北京市金融街1号"}
    body = {"request_id": str(uuid4()), "interaction_id": ask.interaction.interaction_id,
            "kind": "delivery", "fields": fields}
    headers = {"Origin": "http://testserver"}
    try:
        api.current_input_task(api.identity(api.cookie(who.session_id)), "FORM",
                               ask.interaction.interaction_id)
        response = client.post("/api/v1/tasks/FORM/details", json=body, headers=headers)
        assert response.status_code == 200, response.text
        assert client.post("/api/v1/tasks/FORM/details", json=body, headers=headers).json() == response.json()
        ref = response.json()["data"]["detail_ref"]
        # The UI forwards the returned ref, never asks the user to type it.
        input_body = {
            "request_id": str(uuid4()), "interaction_id": ask.interaction.interaction_id,
            "text": ref}
        continued = client.post("/api/v1/tasks/FORM/inputs", json=input_body, headers=headers)
        assert continued.status_code == 200, continued.text
        assert client.post("/api/v1/tasks/FORM/inputs", json=input_body, headers=headers).json() == continued.json()
        assert continued.json()["data"]["interaction"]["required_fields"] == ["cross_selection"]
        stale = client.post("/api/v1/tasks/FORM/details", json={**body,
            "request_id": str(uuid4())}, headers=headers)
        assert stale.status_code == 409
        messages = client.get(f"/api/v1/threads/{thread}/messages").json()
        visible = json.dumps([response.json(), continued.json(), messages], ensure_ascii=False)
        for raw in fields.values():
            assert raw not in visible
        assert runtime.application.get_controlled_detail("U2", "D1", ref, task_id="FORM") is None
        assert runtime.application.get_controlled_detail("U1", "D2", ref, task_id="FORM") is None
        client.cookies.clear()
        enter(client)
        invalid_session = client.post("/api/v1/tasks/FORM/details", json={**body,
            "request_id": str(uuid4())}, headers=headers)
        assert invalid_session.status_code == 409
        assert invalid_session.json()["error"]["code"] == "SESSION_RECONFIRMATION_REQUIRED"
    finally:
        runtime.gateway.close()
