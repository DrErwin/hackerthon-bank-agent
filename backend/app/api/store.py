"""API-owned conversation, request receipts and reconnectable event history."""

from contextlib import closing
import hashlib
import hmac
import json

from app.storage.database import connect, transaction


class ApiProblem(ValueError):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


def dump(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ApiStore:
    EVENT_PAGE_SIZE = 100

    def __init__(self, path, secret):
        self.path, self.secret = path, secret
        with transaction(path) as c:
            for sql in (
                """CREATE TABLE IF NOT EXISTS api_sessions (
                    session_id TEXT PRIMARY KEY, role TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS api_threads (
                    thread_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL, created_at TEXT NOT NULL, view_json TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS api_messages (
                    message_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, view_json TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS api_tasks (
                    task_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL, demo_round_id TEXT NOT NULL,
                    run_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    request_id TEXT NOT NULL, intent_text TEXT NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0)""",
                """CREATE TABLE IF NOT EXISTS api_records (
                    kind TEXT NOT NULL, record_id TEXT NOT NULL, task_id TEXT NOT NULL,
                    PRIMARY KEY(kind, record_id))""",
                """CREATE TABLE IF NOT EXISTS api_payee_searches (
                    task_id TEXT PRIMARY KEY, interaction_id TEXT NOT NULL,
                    candidates_json TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS api_requests (
                    user_id TEXT NOT NULL, demo_round_id TEXT NOT NULL, endpoint TEXT NOT NULL,
                    request_id TEXT NOT NULL, digest TEXT NOT NULL, response_json TEXT,
                    PRIMARY KEY(user_id, demo_round_id, endpoint, request_id))""",
                """CREATE TABLE IF NOT EXISTS api_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
                    thread_id TEXT NOT NULL, event_json TEXT NOT NULL)""",
            ):
                c.execute(sql)

    def rows(self, sql, parameters=()):
        with closing(connect(self.path)) as c:
            return [dict(row) for row in c.execute(sql, parameters)]

    def write(self, sql, parameters=()):
        with transaction(self.path) as c:
            return c.execute(sql, parameters).rowcount

    def receipt(self, identity, endpoint, request_id, body, *, recover_verification=False,
                retry_interrupted=False):
        key = (identity.user_id, identity.demo_round_id, endpoint, str(request_id))
        digest = hmac.new(self.secret, dump(body).encode(), hashlib.sha256).hexdigest()
        with transaction(self.path) as c:
            row = c.execute("""SELECT digest, response_json FROM api_requests
                WHERE user_id=? AND demo_round_id=? AND endpoint=? AND request_id=?""", key).fetchone()
            if row:
                if row["digest"] != digest:
                    raise ApiProblem(409, "REQUEST_CONFLICT")
                if row["response_json"] is None:
                    if recover_verification or retry_interrupted:
                        # Verification uses the bank submission_id; task recovery
                        # uses the Harness transition marker and original operation_id.
                        return None
                    # An interrupted request is never automatically replayed.
                    raise ApiProblem(409, "REQUEST_IN_PROGRESS")
                return json.loads(row["response_json"])
            c.execute("INSERT INTO api_requests VALUES (?, ?, ?, ?, ?, NULL)", (*key, digest))
        return None

    def finish(self, identity, endpoint, request_id, response):
        self.write("""UPDATE api_requests SET response_json=? WHERE user_id=?
            AND demo_round_id=? AND endpoint=? AND request_id=?""",
            (dump(response), identity.user_id, identity.demo_round_id, endpoint, str(request_id)))

    def page(self, items, identity, scope, cursor, limit):
        """Opaque, scope-bound keyset cursor; items must be sorted by immutable key."""
        from base64 import urlsafe_b64decode, urlsafe_b64encode
        key = None
        binding = [identity.user_id, identity.demo_round_id, scope]
        if cursor:
            try:
                encoded, signature = cursor.split(".")
                expected = hmac.new(self.secret, encoded.encode(), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(signature, expected):
                    raise ValueError()
                decoded = json.loads(urlsafe_b64decode(encoded))
                if decoded["scope"] != binding:
                    raise ValueError()
                key = tuple(decoded["key"])
            except (ValueError, KeyError, TypeError):
                raise ApiProblem(400, "INVALID_CURSOR") from None
        remaining = [(sort_key, item) for sort_key, item in items if key is None or sort_key > key]
        selected = remaining[:limit]
        next_cursor = None
        if len(remaining) > limit:
            encoded = urlsafe_b64encode(dump({"scope": binding, "key": selected[-1][0]}).encode()).decode()
            next_cursor = encoded + "." + hmac.new(self.secret, encoded.encode(), hashlib.sha256).hexdigest()
        return {"items": [item for _, item in selected], "next_cursor": next_cursor}

    def event(self, event):
        self.write("INSERT INTO api_events(event_id, thread_id, event_json) VALUES (?, ?, ?)",
                   (event.event_id, event.thread_id, dump(event)))

    def events(self, thread_id, cursor):
        sequence = 0
        if cursor:
            rows = self.rows("SELECT sequence FROM api_events WHERE event_id=? AND thread_id=?",
                             (cursor, thread_id))
            if not rows:
                raise ApiProblem(409, "EVENT_CURSOR_STALE")
            sequence = rows[0]["sequence"]
        return [json.loads(row["event_json"]) for row in self.rows(
            "SELECT event_json FROM api_events WHERE thread_id=? AND sequence>? ORDER BY sequence LIMIT ?",
            (thread_id, sequence, self.EVENT_PAGE_SIZE))]
