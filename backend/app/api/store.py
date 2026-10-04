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
                """CREATE TABLE IF NOT EXISTS api_message_jobs (
                    job_id TEXT PRIMARY KEY, candidate_task_id TEXT UNIQUE NOT NULL,
                    user_message_id TEXT UNIQUE NOT NULL, assistant_message_id TEXT UNIQUE NOT NULL,
                    thread_id TEXT NOT NULL, user_id TEXT NOT NULL, session_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL, run_id TEXT NOT NULL, request_id TEXT NOT NULL,
                    intent_text TEXT NOT NULL, status TEXT NOT NULL, task_id TEXT,
                    created_at TEXT NOT NULL, user_event_id TEXT NOT NULL,
                    assistant_event_id TEXT NOT NULL, user_task_event_id TEXT NOT NULL,
                    task_updated_event_id TEXT NOT NULL, interaction_event_id TEXT NOT NULL,
                    error_event_id TEXT NOT NULL,
                    UNIQUE(user_id, demo_round_id, thread_id, request_id))""",
                """CREATE TABLE IF NOT EXISTS api_message_replies (
                    job_id TEXT PRIMARY KEY, reply_text TEXT NOT NULL)""",
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
                saved = json.loads(row["response_json"])
                if recover_verification and saved["status"] == 503:
                    # Same fingerprint and bank submission identity recover an unknown outcome.
                    return None
                return saved
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
        self.write("INSERT OR IGNORE INTO api_events(event_id, thread_id, event_json) VALUES (?, ?, ?)",
                   (event.event_id, event.thread_id, dump(event)))

    def message_job(self, job_id):
        rows = self.rows("SELECT * FROM api_message_jobs WHERE job_id=?", (job_id,))
        if not rows:
            raise ApiProblem(404, "MESSAGE_NOT_FOUND")
        return rows[0]

    def message_job_for_request(self, identity, thread_id, request_id):
        rows = self.rows("""SELECT * FROM api_message_jobs
            WHERE user_id=? AND demo_round_id=? AND thread_id=? AND request_id=?""",
            (identity.user_id, identity.demo_round_id, thread_id, str(request_id)))
        return rows[0] if rows else None

    def enqueue_message_job(self, job, message_json, event_json):
        """Persist an accepted chat message and its resumable job as one unit."""
        with transaction(self.path) as c:
            row = c.execute("""SELECT * FROM api_message_jobs
                WHERE user_id=? AND demo_round_id=? AND thread_id=? AND request_id=?""",
                (job["user_id"], job["demo_round_id"], job["thread_id"], job["request_id"])).fetchone()
            if row:
                return dict(row), False
            c.execute("INSERT INTO api_messages VALUES (?, ?, ?, ?)",
                      (job["user_message_id"], job["thread_id"], job["created_at"], message_json))
            c.execute("INSERT OR IGNORE INTO api_events(event_id, thread_id, event_json) VALUES (?, ?, ?)",
                      (job["user_event_id"], job["thread_id"], event_json))
            c.execute("""INSERT INTO api_message_jobs VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)""",
                (job["job_id"], job["candidate_task_id"], job["user_message_id"],
                 job["assistant_message_id"], job["thread_id"], job["user_id"],
                 job["session_id"], job["demo_round_id"], job["run_id"], job["request_id"],
                 job["intent_text"], "queued", job["created_at"], job["user_event_id"],
                 job["assistant_event_id"], job["user_task_event_id"],
                 job["task_updated_event_id"], job["interaction_event_id"], job["error_event_id"]))
            row = c.execute("SELECT * FROM api_message_jobs WHERE job_id=?", (job["job_id"],)).fetchone()
            return dict(row), True

    def set_message_job_status(self, job_id, status):
        self.write("UPDATE api_message_jobs SET status=? WHERE job_id=?", (status, job_id))

    def save_message_reply(self, job_id, text):
        with transaction(self.path) as c:
            c.execute("INSERT OR IGNORE INTO api_message_replies VALUES (?, ?)", (job_id, text))
            c.execute("UPDATE api_message_jobs SET status='reply_ready' WHERE job_id=?", (job_id,))

    def complete_reply_job(self, job_id, created_at, message_json, event_json):
        with transaction(self.path) as c:
            job = c.execute("SELECT * FROM api_message_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not job or job["status"] in {"reply_completed", "task_completed", "error_completed"}:
                return
            c.execute("INSERT OR IGNORE INTO api_messages VALUES (?, ?, ?, ?)",
                      (job["assistant_message_id"], job["thread_id"], created_at, message_json))
            c.execute("INSERT OR IGNORE INTO api_events(event_id, thread_id, event_json) VALUES (?, ?, ?)",
                      (job["assistant_event_id"], job["thread_id"], event_json))
            c.execute("UPDATE api_message_jobs SET status='reply_completed' WHERE job_id=?", (job_id,))

    def link_message_job_task(self, job_id, api_task, message_json, event_json):
        with transaction(self.path) as c:
            job = c.execute("SELECT * FROM api_message_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not job:
                raise ApiProblem(404, "MESSAGE_NOT_FOUND")
            if job["status"] in {"task_linked", "task_completed"}:
                if job["task_id"] != api_task["task_id"]:
                    raise ApiProblem(409, "REQUEST_CONFLICT")
                return
            c.execute("""INSERT OR IGNORE INTO api_tasks(
                task_id,thread_id,user_id,session_id,demo_round_id,run_id,created_at,request_id,intent_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (api_task["task_id"], api_task["thread_id"], api_task["user_id"],
                 api_task["session_id"], api_task["demo_round_id"], api_task["run_id"],
                 api_task["created_at"], api_task["request_id"], api_task["intent_text"]))
            c.execute("UPDATE api_messages SET view_json=? WHERE message_id=?",
                      (message_json, job["user_message_id"]))
            c.execute("INSERT OR IGNORE INTO api_events(event_id, thread_id, event_json) VALUES (?, ?, ?)",
                      (job["user_task_event_id"], job["thread_id"], event_json))
            c.execute("UPDATE api_message_jobs SET status='task_linked', task_id=? WHERE job_id=?",
                      (api_task["task_id"], job_id))

    def complete_task_job(self, job_id, created_at, message_json, event_jsons):
        with transaction(self.path) as c:
            job = c.execute("SELECT * FROM api_message_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not job or job["status"] == "task_completed":
                return
            if job["status"] != "task_linked":
                raise ApiProblem(409, "MESSAGE_NOT_READY")
            c.execute("INSERT OR IGNORE INTO api_messages VALUES (?, ?, ?, ?)",
                      (job["assistant_message_id"], job["thread_id"], created_at, message_json))
            for event_id, event_json in event_jsons:
                c.execute("INSERT OR IGNORE INTO api_events(event_id, thread_id, event_json) VALUES (?, ?, ?)",
                          (event_id, job["thread_id"], event_json))
            c.execute("UPDATE api_message_jobs SET status='task_completed' WHERE job_id=?", (job_id,))

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
