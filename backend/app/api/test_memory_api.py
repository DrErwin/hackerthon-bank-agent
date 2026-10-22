"""F37 / F38: memory viewing and explicit deletion over the real HTTP boundary.

The fixtures are the same ones ``test_app.py`` uses: a real FastAPI application, the
real application store, the real mock bank and audit journal, and the real
``MemoryAdapter`` with seeded demo memories. The endpoints are exercised only through
HTTP, except where a memory write has no HTTP path (tombstone restoration checks).
"""

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.api.test_app import enter, make_app
from app.memory.adapter import MemoryContext
from app.memory.store import MEMORY_INDEX
from app.storage.database import connect

ORIGIN = {"Origin": "http://testserver"}
DELETE_PATH = "/api/v1/memories/delete"
MEMORY_IDS = {
    "alias-mother", "alias-family", "alias-savings", "allocation", "budget",
    "birthday-delivery",
}


def seed(app, *, user="U1", demo_round_id="D1", start_month="2026-09"):
    app.state.api.runtime.memory.seed_demo(user, demo_round_id, start_month)


def other_user_memory(app):
    """A second demo user's own memory; it must never reach U1's endpoints."""

    application = app.state.api.runtime.application
    at = datetime.now(timezone.utc)
    application.create_session("S2", "U2", "D1", at.isoformat(),
                               (at + timedelta(hours=1)).isoformat())
    app.state.api.runtime.memory.backend(MemoryContext("U2", "S2", "D1")).write(
        "/memories/preference.md", "用户偏好：喜欢简短说明。")
    return "preference"


def list_memories(client):
    response = client.get("/api/v1/memories")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def delete_body(memory_ids, expected_versions, request_id=None):
    return {"request_id": request_id or str(uuid4()), "memory_ids": memory_ids,
            "expected_versions": expected_versions}


def delete(client, body):
    return client.post(DELETE_PATH, json=body, headers=ORIGIN)


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


def context_for(app, client):
    return app.state.api.memory_context(
        app.state.api.identity(client.cookies.get("bank_session")))


def test_f37_lists_only_current_users_current_round_memories(tmp_path):
    app = make_app(tmp_path)
    seed(app)
    with TestClient(app) as client:
        enter(client)
        other_user_memory(app)
        # Another round of the same user stays out of the current-round entry.
        app.state.api.runtime.memory.store.put(
            ("memory", "D2", "U1"), "/memories/old-round.md",
            {"content": "用户偏好：喜欢简短说明。", "encoding": "utf-8"})

        data = list_memories(client)
        assert data["demo_round_id"] == "D1"
        assert {item["memory_id"] for item in data["items"]} == MEMORY_IDS
        assert all(set(item) == {"memory_id", "version", "content", "updated_at"}
                   for item in data["items"])
        assert all(item["version"] == 1 for item in data["items"])
        assert all("喜欢简短说明" not in item["content"] for item in data["items"])

        saved = dict(client.cookies)
        client.cookies.clear()
        anonymous = client.get("/api/v1/memories")
        assert_error(anonymous, 401, "AUTH_REQUIRED")
        assert "alias-mother" not in anonymous.text
        client.cookies.update(saved)


def test_f38_deletes_selected_memory_idempotently_and_refreshes_context(tmp_path):
    app = make_app(tmp_path)
    seed(app)
    with TestClient(app) as client:
        enter(client)
        listed = {item["memory_id"]: item for item in list_memories(client)["items"]}
        body = delete_body(["alias-mother"], {"alias-mother": listed["alias-mother"]["version"]})

        deleted = delete(client, body)
        assert deleted.status_code == 200, deleted.text
        result = deleted.json()["data"]
        assert result["deleted_ids"] == ["alias-mother"]
        assert result["demo_round_id"] == "D1"
        assert result["deleted_at"]

        remaining = {item["memory_id"] for item in list_memories(client)["items"]}
        assert remaining == MEMORY_IDS - {"alias-mother"}

        replay = delete(client, body)
        assert replay.status_code == 200
        assert replay.json() == deleted.json()

        context = context_for(app, client)
        index = app.state.api.runtime.memory.backend(context).read(
            MEMORY_INDEX).file_data["content"]
        assert "妈妈" not in index
        assert "家庭账户" in index
        # The next task reload drops a cached copy of the deleted memory as well.
        stale = {"memory_contents": {MEMORY_INDEX: "称呼线索：妈妈 → 银行种子 A2"}}
        refreshed = app.state.api.runtime.memory.middleware(context).before_agent(
            stale, None, {})
        assert "妈妈" not in refreshed["memory_contents"][MEMORY_INDEX]


def test_f38_old_version_foreign_owner_and_invalid_arguments(tmp_path):
    app = make_app(tmp_path)
    seed(app)
    with TestClient(app) as client:
        enter(client)
        assert_error(delete(client, delete_body(["alias-mother"], {"alias-mother": 2})),
                     409, "MEMORY_VERSION_CONFLICT")
        assert {item["memory_id"] for item in list_memories(client)["items"]} == MEMORY_IDS

        foreign = other_user_memory(app)
        assert_error(delete(client, delete_body([foreign], {foreign: 1})),
                     403, "ACCESS_DENIED")
        assert_error(delete(client, delete_body([], {})), 400, "INVALID_ARGUMENT")
        assert_error(delete(client, delete_body(["alias-mother", "alias-mother"],
                                                {"alias-mother": 1})),
                     400, "INVALID_ARGUMENT")
        assert_error(delete(client, delete_body(["alias-mother"], {"alias-mother": 0})),
                     400, "INVALID_ARGUMENT")
        # The same request id with a different selection is a fingerprint conflict.
        request_id = str(uuid4())
        first = delete(client, delete_body(["alias-family"], {"alias-family": 1},
                                           request_id=request_id))
        assert first.status_code == 200, first.text
        assert_error(delete(client, delete_body(["alias-savings"], {"alias-savings": 1},
                                                request_id=request_id)),
                     409, "REQUEST_CONFLICT")
        assert {item["memory_id"] for item in list_memories(client)["items"]} == (
            MEMORY_IDS - {"alias-family"})
        # A malformed body is rejected by the generic validation envelope, not 500.
        malformed = client.post(DELETE_PATH, json={"request_id": str(uuid4()),
                                                   "memory_ids": "alias-mother"},
                                headers=ORIGIN)
        assert_error(malformed, 400, "INVALID_ARGUMENT")


def test_f38_stale_round_and_expired_session_do_not_delete(tmp_path):
    active = ["D1"]
    app = make_app(tmp_path, active_round=lambda: active[0])
    seed(app)
    with TestClient(app) as client:
        session = enter(client)
        listed = {item["memory_id"]: item["version"] for item in list_memories(client)["items"]}

        active[0] = "D2"
        assert_error(client.get("/api/v1/memories"), 409, "STALE_ROUND")
        assert_error(delete(client, delete_body(["alias-mother"],
                                                {"alias-mother": listed["alias-mother"]})),
                     409, "STALE_ROUND")
        active[0] = "D1"
        assert {item["memory_id"] for item in list_memories(client)["items"]} == MEMORY_IDS

        app.state.api.store.write(
            "UPDATE sessions SET expires_at=? WHERE session_id=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
             session["session_id"]))
        assert_error(client.get("/api/v1/memories"), 401, "AUTH_REQUIRED")
        assert_error(delete(client, delete_body(["alias-mother"],
                                                {"alias-mother": listed["alias-mother"]})),
                     401, "AUTH_REQUIRED")
        app.state.api.store.write(
            "UPDATE sessions SET expires_at=? WHERE session_id=?",
            ((datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
             session["session_id"]))
        assert {item["memory_id"] for item in list_memories(client)["items"]} == MEMORY_IDS


def test_f38_tombstone_blocks_restoration_and_keeps_the_request_record(tmp_path):
    app = make_app(tmp_path)
    seed(app)
    with TestClient(app) as client:
        enter(client)
        listed = {item["memory_id"]: item for item in list_memories(client)["items"]}
        content = listed["alias-mother"]["content"]
        body = delete_body(["alias-mother"], {"alias-mother": listed["alias-mother"]["version"]})
        deleted = delete(client, body)
        assert deleted.status_code == 200, deleted.text

        context = context_for(app, client)
        backend = app.state.api.runtime.memory.backend(context)
        # Same key and same content (including a copied file) cannot re-enter the round.
        with pytest.raises(ValueError, match="deleted memory"):
            backend.write("/memories/alias-mother.md", content)
        with pytest.raises(ValueError, match="deleted memory"):
            backend.write("/memories/copied-alias.md", content)
        # The prohibited-content path still rejects new credentials independently.
        with pytest.raises(ValueError, match="prohibited"):
            backend.write("/memories/credential.md", "用户偏好：验证码 123456")
        index = backend.read(MEMORY_INDEX).file_data["content"]
        assert index and "妈妈" not in index

        with closing(connect(app.state.api.runtime.application.path)) as connection:
            rows = connection.execute(
                "SELECT * FROM memory_deletions WHERE request_id=?",
                (body["request_id"],)).fetchall()
        assert len(rows) == 1
        saved = json.loads(rows[0]["result_json"])
        assert saved["deleted_ids"] == ["alias-mother"]
        assert saved["demo_round_id"] == "D1"
        replay = delete(client, body)
        assert replay.json()["data"] == deleted.json()["data"]
