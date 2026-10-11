"""Application-owned sessions, task positions, references and tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from app.contracts import TaskStatus

from .database import connect, parameter_digest, transaction


SCHEMA_VERSION = 4


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    user_id: str
    demo_round_id: str
    created_at: str
    expires_at: str


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    user_id: str
    session_id: str
    demo_round_id: str
    run_id: str
    status: TaskStatus
    revision: int
    checkpoint_thread_id: str
    checkpoint_id: str | None
    snapshot: dict


@dataclass(frozen=True)
class ToolOperation:
    operation_id: str
    task_id: str
    user_id: str
    demo_round_id: str
    action_name: str
    parameters_digest: str
    state: str
    result_ref: str | None


class ApplicationStore:
    def __init__(self, path: Path):
        self.path = path
        self.initialize()

    def initialize(self) -> None:
        with transaction(self.path) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError("application database is newer than this code")
            if version == 0:
                connection.execute("""
                    CREATE TABLE sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        demo_round_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        UNIQUE(session_id, user_id, demo_round_id)
                    )
                """)
                connection.execute("""
                    CREATE TABLE tasks (
                        task_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        demo_round_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        revision INTEGER NOT NULL CHECK(revision >= 0),
                        checkpoint_thread_id TEXT NOT NULL UNIQUE,
                        checkpoint_id TEXT,
                        snapshot_json TEXT NOT NULL,
                        FOREIGN KEY(session_id, user_id, demo_round_id)
                            REFERENCES sessions(session_id, user_id, demo_round_id)
                    )
                """)
                connection.execute("""
                    CREATE TABLE owned_refs (
                        kind TEXT NOT NULL CHECK(kind IN ('confirmation', 'verification', 'memory')),
                        record_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        demo_round_id TEXT NOT NULL,
                        PRIMARY KEY(kind, record_id)
                    )
                """)
                connection.execute("""
                    CREATE TABLE task_refs (
                        task_id TEXT NOT NULL REFERENCES tasks(task_id),
                        user_id TEXT NOT NULL,
                        demo_round_id TEXT NOT NULL,
                        kind TEXT NOT NULL CHECK(kind IN ('confirmation', 'verification', 'memory')),
                        record_id TEXT NOT NULL,
                        PRIMARY KEY(task_id, kind, record_id),
                        FOREIGN KEY(kind, record_id) REFERENCES owned_refs(kind, record_id)
                    )
                """)
                connection.execute("""
                    CREATE TABLE tool_operations (
                        operation_id TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL REFERENCES tasks(task_id),
                        user_id TEXT NOT NULL,
                        demo_round_id TEXT NOT NULL,
                        action_name TEXT NOT NULL,
                        parameters_digest TEXT NOT NULL,
                        state TEXT NOT NULL,
                        result_ref TEXT
                    )
                """)
                connection.execute("""
                    CREATE TABLE checkpoints (
                        row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        thread_id TEXT NOT NULL,
                        checkpoint_ns TEXT NOT NULL,
                        checkpoint_id TEXT NOT NULL,
                        parent_id TEXT,
                        checkpoint_type TEXT NOT NULL,
                        checkpoint_blob BLOB NOT NULL,
                        metadata_type TEXT NOT NULL,
                        metadata_blob BLOB NOT NULL,
                        UNIQUE(thread_id, checkpoint_ns, checkpoint_id)
                    )
                """)
                connection.execute("""
                    CREATE TABLE checkpoint_blobs (
                        thread_id TEXT NOT NULL,
                        checkpoint_ns TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        version TEXT NOT NULL,
                        value_type TEXT NOT NULL,
                        value_blob BLOB NOT NULL,
                        PRIMARY KEY(thread_id, checkpoint_ns, channel, version)
                    )
                """)
                connection.execute("""
                    CREATE TABLE checkpoint_writes (
                        thread_id TEXT NOT NULL,
                        checkpoint_ns TEXT NOT NULL,
                        checkpoint_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        write_idx INTEGER NOT NULL,
                        channel TEXT NOT NULL,
                        value_type TEXT NOT NULL,
                        value_blob BLOB NOT NULL,
                        task_path TEXT NOT NULL,
                        PRIMARY KEY(thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx)
                    )
                """)
                connection.execute("PRAGMA user_version = 1")
            if version < 2:
                columns = {
                    row["name"] for row in connection.execute("PRAGMA table_info(task_refs)")
                }
                if "session_id" not in columns:
                    connection.execute("ALTER TABLE task_refs ADD COLUMN session_id TEXT")
                connection.execute("""UPDATE task_refs SET session_id = (
                    SELECT session_id FROM tasks WHERE tasks.task_id = task_refs.task_id
                ) WHERE session_id IS NULL""")
                connection.execute("PRAGMA user_version = 2")
            if version < 3:
                connection.execute("""CREATE TABLE IF NOT EXISTS task_session_transitions (
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    source_session_id TEXT NOT NULL,
                    target_session_id TEXT NOT NULL,
                    source_revision INTEGER NOT NULL,
                    target_revision INTEGER NOT NULL,
                    occurred_at TEXT NOT NULL,
                    PRIMARY KEY(task_id, source_revision),
                    FOREIGN KEY(source_session_id, user_id, demo_round_id)
                        REFERENCES sessions(session_id, user_id, demo_round_id),
                    FOREIGN KEY(target_session_id, user_id, demo_round_id)
                        REFERENCES sessions(session_id, user_id, demo_round_id)
                )""")
                connection.execute("PRAGMA user_version = 3")
            if version < 4:
                columns = {
                    row["name"] for row in connection.execute("PRAGMA table_info(tool_operations)")
                }
                if not columns:
                    connection.execute("""CREATE TABLE tool_operations (
                        operation_id TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL REFERENCES tasks(task_id),
                        user_id TEXT NOT NULL,
                        demo_round_id TEXT NOT NULL,
                        action_name TEXT NOT NULL,
                        parameters_digest TEXT NOT NULL,
                        state TEXT NOT NULL,
                        result_ref TEXT,
                        created_sequence INTEGER NOT NULL DEFAULT 0
                    )""")
                elif "created_sequence" not in columns:
                    connection.execute(
                        "ALTER TABLE tool_operations ADD COLUMN created_sequence INTEGER NOT NULL DEFAULT 0",
                    )
                    connection.execute(
                        "UPDATE tool_operations SET created_sequence = rowid",
                    )
                connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS
                    tool_operations_created_sequence ON tool_operations(created_sequence)""")
                connection.execute("PRAGMA user_version = 4")

    def create_session(
        self, session_id: str, user_id: str, demo_round_id: str, created_at: str, expires_at: str,
    ) -> None:
        with transaction(self.path) as connection:
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                (session_id, user_id, demo_round_id, created_at, expires_at),
            )

    def get_session(self, user_id: str, demo_round_id: str, session_id: str) -> SessionRecord | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                """SELECT * FROM sessions WHERE user_id = ? AND demo_round_id = ?
                   AND session_id = ?""",
                (user_id, demo_round_id, session_id),
            ).fetchone()
            return SessionRecord(**dict(row)) if row else None
        finally:
            connection.close()

    def create_task(
        self, task_id: str, user_id: str, session_id: str, demo_round_id: str,
        run_id: str, status: TaskStatus, snapshot: dict,
    ) -> TaskRecord:
        with transaction(self.path) as connection:
            connection.execute(
                """INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, ?)""",
                (task_id, user_id, session_id, demo_round_id, run_id, TaskStatus(status).value,
                 str(uuid4()), json.dumps(snapshot, ensure_ascii=False)),
            )
        return self.get_task(user_id, demo_round_id, task_id)

    def get_task(self, user_id: str, demo_round_id: str, task_id: str) -> TaskRecord | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND demo_round_id = ? AND task_id = ?",
                (user_id, demo_round_id, task_id),
            ).fetchone()
            if row is None:
                return None
            return self._task_record(row)
        finally:
            connection.close()

    def list_session_tasks(self, user_id: str, demo_round_id: str,
                           session_id: str) -> list[TaskRecord]:
        """Trusted planning context: this session's tasks, active first, newest first."""
        connection = connect(self.path)
        try:
            rows = connection.execute(
                """SELECT rowid AS row_order, * FROM tasks
                   WHERE user_id = ? AND demo_round_id = ? AND session_id = ?""",
                (user_id, demo_round_id, session_id),
            ).fetchall()
        finally:
            connection.close()
        terminal = {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        records = [(row["row_order"], self._task_record(row)) for row in rows]
        records.sort(key=lambda item: (item[1].status in terminal, -item[0]))
        return [record for _, record in records]

    @staticmethod
    def _task_record(row) -> TaskRecord:
        return TaskRecord(
            row["task_id"], row["user_id"], row["session_id"], row["demo_round_id"],
            row["run_id"], TaskStatus(row["status"]), row["revision"],
            row["checkpoint_thread_id"], row["checkpoint_id"], json.loads(row["snapshot_json"]),
        )

    def checkpoint_saver(self, user_id: str, demo_round_id: str, task_id: str):
        from .checkpoints import SqliteCheckpointSaver

        task = self.get_task(user_id, demo_round_id, task_id)
        if task is None:
            raise ValueError("task is not in scope")
        return SqliteCheckpointSaver(self.path, task.checkpoint_thread_id)

    def update_task(
        self, user_id: str, demo_round_id: str, task_id: str, expected_revision: int,
        run_id: str, status: TaskStatus, checkpoint_id: str | None, snapshot: dict,
    ) -> TaskRecord:
        with transaction(self.path) as connection:
            changed = connection.execute(
                """UPDATE tasks SET run_id = ?, status = ?, revision = revision + 1,
                       checkpoint_id = ?, snapshot_json = ?
                   WHERE task_id = ? AND user_id = ? AND demo_round_id = ? AND revision = ?""",
                (run_id, TaskStatus(status).value, checkpoint_id,
                 json.dumps(snapshot, ensure_ascii=False), task_id, user_id, demo_round_id,
                 expected_revision),
            ).rowcount
            if changed != 1:
                raise ValueError("task is missing, out of scope, or changed concurrently")
        return self.get_task(user_id, demo_round_id, task_id)

    def transition_task_session(
        self, user_id: str, demo_round_id: str, task_id: str, source_session_id: str,
        target_session_id: str, expected_revision: int,
    ) -> TaskRecord:
        if source_session_id == target_session_id:
            raise ValueError("source and target sessions must differ")
        with transaction(self.path) as connection:
            row = connection.execute(
                """SELECT * FROM tasks WHERE task_id = ? AND user_id = ?
                   AND demo_round_id = ?""",
                (task_id, user_id, demo_round_id),
            ).fetchone()
            if row is None:
                raise ValueError("task is not in scope")
            previous = connection.execute(
                """SELECT target_revision FROM task_session_transitions
                   WHERE task_id = ? AND user_id = ? AND demo_round_id = ?
                     AND source_session_id = ? AND target_session_id = ?
                     AND source_revision = ?""",
                (task_id, user_id, demo_round_id, source_session_id,
                 target_session_id, expected_revision),
            ).fetchone()
            if previous is not None:
                if row["session_id"] == target_session_id and row["revision"] == previous["target_revision"]:
                    return self._task_record(row)
                raise ValueError("task changed after the session transition")
            if row["session_id"] != source_session_id or row["revision"] != expected_revision:
                raise ValueError("task is missing, out of scope, or changed concurrently")

            target = connection.execute(
                """SELECT created_at, expires_at FROM sessions WHERE session_id = ?
                   AND user_id = ? AND demo_round_id = ?""",
                (target_session_id, user_id, demo_round_id),
            ).fetchone()
            if target is None:
                raise ValueError("target session is not in scope")
            transition_time = datetime.now(timezone.utc)
            if not (
                datetime.fromisoformat(target["created_at"]) <= transition_time
                < datetime.fromisoformat(target["expires_at"])
            ):
                raise ValueError("target session is not active")

            changed = connection.execute(
                """UPDATE tasks SET session_id = ?, revision = revision + 1
                   WHERE task_id = ? AND user_id = ? AND demo_round_id = ?
                     AND session_id = ? AND revision = ?""",
                (target_session_id, task_id, user_id, demo_round_id,
                 source_session_id, expected_revision),
            ).rowcount
            if changed != 1:
                raise ValueError("task is missing, out of scope, or changed concurrently")
            transition_time = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """INSERT INTO task_session_transitions VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, user_id, demo_round_id, source_session_id, target_session_id,
                 expected_revision, expected_revision + 1, transition_time),
            )
            transitioned = connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,),
            ).fetchone()
            return self._task_record(transitioned)

    def bind_ref(self, user_id: str, demo_round_id: str, task_id: str, kind: str, record_id: str) -> None:
        if kind not in {"confirmation", "verification", "memory"}:
            raise ValueError("unsupported task reference")
        with transaction(self.path) as connection:
            task = connection.execute(
                "SELECT session_id FROM tasks WHERE task_id = ? AND user_id = ? AND demo_round_id = ?",
                (task_id, user_id, demo_round_id),
            ).fetchone()
            if task is None:
                raise ValueError("task is not in scope")
            owner = connection.execute(
                "SELECT user_id, demo_round_id FROM owned_refs WHERE kind = ? AND record_id = ?",
                (kind, record_id),
            ).fetchone()
            if owner is not None and (owner["user_id"], owner["demo_round_id"]) != (
                user_id, demo_round_id,
            ):
                raise ValueError("record reference belongs to another user or round")
            if kind in {"confirmation", "verification"}:
                bindings = connection.execute(
                    """SELECT task_id, session_id FROM task_refs
                       WHERE task_refs.kind = ? AND task_refs.record_id = ?""",
                    (kind, record_id),
                ).fetchall()
                if kind == "confirmation" and any(
                    bound["task_id"] != task_id for bound in bindings
                ):
                    raise ValueError("confirmation reference belongs to another task")
                if kind == "verification" and any(
                    bound["session_id"] != task["session_id"] for bound in bindings
                ):
                    raise ValueError("verification reference belongs to another session")
            if owner is None:
                connection.execute(
                    "INSERT INTO owned_refs VALUES (?, ?, ?, ?)",
                    (kind, record_id, user_id, demo_round_id),
                )
            existing = connection.execute(
                """SELECT session_id FROM task_refs
                   WHERE task_id = ? AND kind = ? AND record_id = ?""",
                (task_id, kind, record_id),
            ).fetchone()
            if kind == "confirmation" and existing is not None:
                # A confirmation ID can advance to a newer version when a task
                # moves sessions. The security store checks that version; bind
                # the current task reference to the new session after it issues it.
                connection.execute(
                    """UPDATE task_refs SET session_id = ?
                       WHERE task_id = ? AND kind = ? AND record_id = ?""",
                    (task["session_id"], task_id, kind, record_id),
                )
            else:
                connection.execute(
                    """INSERT OR IGNORE INTO task_refs
                       (task_id, user_id, demo_round_id, kind, record_id, session_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (task_id, user_id, demo_round_id, kind, record_id, task["session_id"]),
                )

    def has_ref(self, user_id: str, demo_round_id: str, task_id: str, kind: str, record_id: str) -> bool:
        connection = connect(self.path)
        try:
            return connection.execute(
                """SELECT 1 FROM task_refs refs JOIN tasks ON tasks.task_id = refs.task_id
                   WHERE refs.user_id = ? AND refs.demo_round_id = ?
                     AND refs.task_id = ? AND refs.kind = ? AND refs.record_id = ?
                     AND (refs.kind = 'memory' OR refs.session_id = tasks.session_id)""",
                (user_id, demo_round_id, task_id, kind, record_id),
            ).fetchone() is not None
        finally:
            connection.close()

    def reserve_operation(
        self, user_id: str, demo_round_id: str, task_id: str, operation_id: str,
        action_name: str, parameters: dict,
    ) -> ToolOperation:
        digest = parameter_digest(parameters)
        with transaction(self.path) as connection:
            task = connection.execute(
                "SELECT 1 FROM tasks WHERE task_id = ? AND user_id = ? AND demo_round_id = ?",
                (task_id, user_id, demo_round_id),
            ).fetchone()
            if task is None:
                raise ValueError("task is not in scope")
            existing = connection.execute(
                "SELECT * FROM tool_operations WHERE operation_id = ?", (operation_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["user_id"], existing["demo_round_id"], existing["task_id"],
                    existing["action_name"], existing["parameters_digest"],
                ) != (user_id, demo_round_id, task_id, action_name, digest):
                    raise ValueError("operation_id is already bound to a different action")
            else:
                created_sequence = connection.execute(
                    "SELECT COALESCE(MAX(created_sequence), 0) + 1 FROM tool_operations",
                ).fetchone()[0]
                connection.execute(
                    """INSERT INTO tool_operations
                       (operation_id, task_id, user_id, demo_round_id, action_name,
                        parameters_digest, state, result_ref, created_sequence)
                       VALUES (?, ?, ?, ?, ?, ?, 'reserved', NULL, ?)""",
                    (operation_id, task_id, user_id, demo_round_id, action_name,
                     digest, created_sequence),
                )
        return self.get_operation(user_id, demo_round_id, operation_id)

    def get_operation(
        self, user_id: str, demo_round_id: str, operation_id: str,
    ) -> ToolOperation | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                """SELECT operation_id, task_id, user_id, demo_round_id, action_name,
                          parameters_digest, state, result_ref
                   FROM tool_operations WHERE user_id = ? AND demo_round_id = ?
                   AND operation_id = ?""",
                (user_id, demo_round_id, operation_id),
            ).fetchone()
            if row is None:
                return None
            return ToolOperation(**dict(row))
        finally:
            connection.close()

    def list_task_operations(
        self, user_id: str, demo_round_id: str, task_id: str,
    ) -> list[ToolOperation]:
        """Return the durable operation records owned by one scoped task."""
        connection = connect(self.path)
        try:
            task = connection.execute(
                "SELECT 1 FROM tasks WHERE task_id = ? AND user_id = ? AND demo_round_id = ?",
                (task_id, user_id, demo_round_id),
            ).fetchone()
            if task is None:
                raise ValueError("task is not in scope")
            rows = connection.execute(
                """SELECT operation_id, task_id, user_id, demo_round_id, action_name,
                          parameters_digest, state, result_ref
                   FROM tool_operations
                   WHERE task_id = ? AND user_id = ? AND demo_round_id = ?
                   ORDER BY created_sequence""",
                (task_id, user_id, demo_round_id),
            ).fetchall()
            return [ToolOperation(**dict(row)) for row in rows]
        finally:
            connection.close()

    def record_operation_result(
        self, user_id: str, demo_round_id: str, operation_id: str, state: str,
        result_ref: str | None,
    ) -> ToolOperation:
        if state not in {"succeeded", "failed", "processing", "unknown"}:
            raise ValueError("invalid observed state")
        with transaction(self.path) as connection:
            existing = connection.execute(
                """SELECT state, result_ref FROM tool_operations
                   WHERE user_id = ? AND demo_round_id = ? AND operation_id = ?""",
                (user_id, demo_round_id, operation_id),
            ).fetchone()
            if existing is None:
                raise ValueError("operation is not in scope")
            if existing["state"] in {"succeeded", "failed"} and (
                existing["state"], existing["result_ref"]
            ) != (state, result_ref):
                raise ValueError("terminal operation result cannot be overwritten")
            connection.execute(
                """UPDATE tool_operations SET state = ?, result_ref = ?
                   WHERE user_id = ? AND demo_round_id = ? AND operation_id = ?""",
                (state, result_ref, user_id, demo_round_id, operation_id),
            )
        return self.get_operation(user_id, demo_round_id, operation_id)
