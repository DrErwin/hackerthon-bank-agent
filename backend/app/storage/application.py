"""Application-owned sessions, task positions, references and tool calls."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from app.contracts import TaskStatus

from .database import connect, parameter_digest, transaction


SCHEMA_VERSION = 1


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

    def create_session(
        self, session_id: str, user_id: str, demo_round_id: str, created_at: str, expires_at: str,
    ) -> None:
        with transaction(self.path) as connection:
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                (session_id, user_id, demo_round_id, created_at, expires_at),
            )

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
            return TaskRecord(
                row["task_id"], row["user_id"], row["session_id"], row["demo_round_id"],
                row["run_id"], TaskStatus(row["status"]), row["revision"],
                row["checkpoint_thread_id"], row["checkpoint_id"], json.loads(row["snapshot_json"]),
            )
        finally:
            connection.close()

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

    def bind_ref(self, user_id: str, demo_round_id: str, task_id: str, kind: str, record_id: str) -> None:
        if kind not in {"confirmation", "verification", "memory"}:
            raise ValueError("unsupported task reference")
        with transaction(self.path) as connection:
            task = connection.execute(
                "SELECT 1 FROM tasks WHERE task_id = ? AND user_id = ? AND demo_round_id = ?",
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
            if owner is None:
                connection.execute(
                    "INSERT INTO owned_refs VALUES (?, ?, ?, ?)",
                    (kind, record_id, user_id, demo_round_id),
                )
            connection.execute(
                "INSERT OR IGNORE INTO task_refs VALUES (?, ?, ?, ?, ?)",
                (task_id, user_id, demo_round_id, kind, record_id),
            )

    def has_ref(self, user_id: str, demo_round_id: str, task_id: str, kind: str, record_id: str) -> bool:
        connection = connect(self.path)
        try:
            return connection.execute(
                """SELECT 1 FROM task_refs WHERE user_id = ? AND demo_round_id = ?
                   AND task_id = ? AND kind = ? AND record_id = ?""",
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
                connection.execute(
                    "INSERT INTO tool_operations VALUES (?, ?, ?, ?, ?, ?, 'reserved', NULL)",
                    (operation_id, task_id, user_id, demo_round_id, action_name, digest),
                )
        return self.get_operation(user_id, demo_round_id, operation_id)

    def get_operation(
        self, user_id: str, demo_round_id: str, operation_id: str,
    ) -> ToolOperation | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                """SELECT * FROM tool_operations WHERE user_id = ? AND demo_round_id = ?
                   AND operation_id = ?""",
                (user_id, demo_round_id, operation_id),
            ).fetchone()
            if row is None:
                return None
            return ToolOperation(**dict(row))
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
