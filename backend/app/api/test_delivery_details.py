"""Ticket v05-cross-platform/08: the controlled F36 delivery entry over real HTTP."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.contracts.common import TaskStatus
from app.contracts.tasks import InteractionRequest, ModuleResult

from .test_app import enter, make_app, post


NOW = datetime.now(timezone.utc)
ORIGIN = {"Origin": "http://testserver"}
RAW = {"recipient_name": "张三丰", "phone": "13800001234", "address": "北京市西城区金融街 1 号"}


def waiting_result(task_id: str) -> ModuleResult:
    return ModuleResult(
        task_id=task_id, run_id="PR1", status=TaskStatus.WAITING_INPUT, data=None,
        message="请填写配送信息。", interaction=InteractionRequest(
            interaction_id="DI1", kind="input", prompt="收件信息",
            required_fields=["delivery"], options=[], record_ref=None,
        ), error=None, allowed_actions=["provide_input", "cancel"],
        recovery_required=False, recovery_reason=None,
    )


def prepared_client(tmp_path):
    application = make_app(tmp_path)
    client = TestClient(application)
    session = enter(client)
    api = application.state.api
    thread = post(client, "/threads").json()["data"]["thread_id"]
    api.runtime.application.create_task(
        "XDELIVERY", "U1", session["session_id"], "D1", "PR1", "waiting_input",
        {"capability_name": "cross.start_task", "trace_id": str(uuid4()),
         "request_id": str(uuid4()), "intent_text": "birthday",
         "config_version": "test-v1", "result": waiting_result("XDELIVERY").model_dump(mode="json")},
    )
    api.store.write(
        "INSERT INTO api_tasks (task_id,thread_id,user_id,session_id,demo_round_id,"
        "run_id,created_at,request_id,intent_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("XDELIVERY", thread, "U1", session["session_id"], "D1", "PR1",
         NOW.isoformat(), str(uuid4()), "birthday"),
    )
    return client, api


def delivery_body(**fields):
    return {"request_id": str(uuid4()), "interaction_id": "DI1", "kind": "delivery",
            "fields": fields or RAW}


def test_delivery_entry_returns_one_scoped_reference_and_masked_fields(tmp_path):
    client, api = prepared_client(tmp_path)
    response = client.post("/api/v1/tasks/XDELIVERY/details",
                           json=delivery_body(), headers=ORIGIN)
    assert response.status_code == 200, response.text
    body = json.dumps(response.json(), ensure_ascii=False)
    data = response.json()["data"]
    assert data["detail_ref"]
    # The answer never carries the raw facts, in any field.
    for raw in ("张三丰", "13800001234", "金融街"):
        assert raw not in body
    fields = {item["name"]: item["value_text"] for item in data["display_fields"]}
    assert fields["recipient"] == "张*"
    assert fields["phone"] == "****1234"
    assert fields["address"].startswith("北京") and "金融街" not in fields["address"]
    # The task did not advance from the delivery entry itself.
    assert data["task"]["status"] == "waiting_input"

    stored = api.runtime.application.get_controlled_detail("U1", "D1", data["detail_ref"])
    assert stored.payload == RAW and stored.task_id == "XDELIVERY" and stored.kind == "delivery"
    # A foreign owner or round resolves nothing through the same reference.
    assert api.runtime.application.get_controlled_detail("U2", "D1", data["detail_ref"]) is None
    assert api.runtime.application.get_controlled_detail("U1", "D2", data["detail_ref"]) is None


def test_delivery_replay_does_not_store_a_second_reference(tmp_path):
    client, api = prepared_client(tmp_path)
    request = delivery_body()
    first = client.post("/api/v1/tasks/XDELIVERY/details", json=request, headers=ORIGIN)
    assert first.status_code == 200
    second = client.post("/api/v1/tasks/XDELIVERY/details", json=request, headers=ORIGIN)
    assert second.status_code == 200 and second.json() == first.json()
    rows = api.store.rows("SELECT record_id FROM api_records WHERE kind='detail'")
    assert len(rows) == 1


def test_delivery_gates_reject_wrong_shape_interaction_and_session(tmp_path):
    client, _api = prepared_client(tmp_path)
    # Payee fields on a delivery-only input are a shape rejection first...
    assert client.post("/api/v1/tasks/XDELIVERY/details", json=delivery_body(
        **{"account_number": "6200", "account_name": "张三"},
    ), headers=ORIGIN).status_code == 400
    # ...and a well-formed payee payload is simply not what this task asked for.
    payee_payload = delivery_body(**{"account_number": "6200", "account_name": "张三"})
    payee_payload["kind"] = "payee"
    assert client.post("/api/v1/tasks/XDELIVERY/details",
                       json=payee_payload, headers=ORIGIN).status_code == 409

    stale = delivery_body()
    stale["interaction_id"] = "DI9"
    response = client.post("/api/v1/tasks/XDELIVERY/details", json=stale, headers=ORIGIN)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INTERACTION_STALE"

    # A fresh session cannot submit details on the old session's task.
    client.cookies.clear()
    enter(client)
    moved = client.post("/api/v1/tasks/XDELIVERY/details",
                        json=delivery_body(), headers=ORIGIN)
    assert moved.status_code == 409
    assert moved.json()["error"]["code"] == "SESSION_RECONFIRMATION_REQUIRED"
