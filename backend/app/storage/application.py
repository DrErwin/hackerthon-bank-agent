"""Application-owned sessions, task positions, references and tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from app.contracts import AdoptedArrangement, AdoptedBudget, BudgetCommitment, BudgetRef, TaskStatus

from .database import connect, parameter_digest, transaction


SCHEMA_VERSION = 7


class ArrangementConflictError(ValueError):
    """D1: another task already holds the active arrangement for this account."""

    def __init__(self, holder_task_id: str, holder_arrangement_id: str, payer_account_id: str):
        self.holder_task_id = holder_task_id
        self.holder_arrangement_id = holder_arrangement_id
        self.payer_account_id = payer_account_id
        super().__init__("ARRANGEMENT_CONFLICT")


class BudgetOccupationExceededError(ValueError):
    """The serialized budget seam refused an occupation above the caller's cap."""

    def __init__(self, budget_id: str, in_flight_fen: int, max_in_flight_fen: int):
        self.budget_id = budget_id
        self.in_flight_fen = in_flight_fen
        self.max_in_flight_fen = max_in_flight_fen
        super().__init__("BUDGET_OCCUPATION_EXCEEDED")


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


@dataclass(frozen=True)
class TaskRelation:
    """One parent-child organization link; bill-source inheritance stays elsewhere."""

    parent_task_id: str
    child_task_id: str
    step_id: str
    plan_revision: int
    linked_at: str


@dataclass(frozen=True)
class ArrangementRecord:
    record: AdoptedArrangement
    payer_account_id: str
    status: str


@dataclass(frozen=True)
class ControlledDetail:
    detail_ref: str
    user_id: str
    demo_round_id: str
    task_id: str
    kind: str
    payload: dict
    created_at: str


def _stable_dump(model) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


def _require_task_in_scope(connection, user_id: str, demo_round_id: str, task_id: str) -> None:
    row = connection.execute(
        "SELECT 1 FROM tasks WHERE task_id = ? AND user_id = ? AND demo_round_id = ?",
        (task_id, user_id, demo_round_id),
    ).fetchone()
    if row is None:
        raise ValueError("task is not in scope")


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
            if version < 5:
                # v05-cross-platform/02: durable cross records. Plan versions stay in
                # the task snapshots; these tables own relations, D1 arrangements,
                # budget occupations and controlled detail references.
                connection.execute("""CREATE TABLE IF NOT EXISTS task_relations (
                    parent_task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    child_task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    plan_revision INTEGER NOT NULL,
                    linked_at TEXT NOT NULL,
                    PRIMARY KEY(parent_task_id, child_task_id),
                    UNIQUE(child_task_id)
                )""")
                connection.execute("""CREATE TABLE IF NOT EXISTS arrangements (
                    arrangement_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    payer_account_id TEXT NOT NULL,
                    source_task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    status TEXT NOT NULL CHECK(status IN ('active', 'superseded', 'closed')),
                    record_json TEXT NOT NULL,
                    adopted_at TEXT NOT NULL
                )""")
                # D1 backstop: at most one active arrangement per account per round.
                connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS
                    arrangements_one_active_per_account
                    ON arrangements(user_id, demo_round_id, payer_account_id)
                    WHERE status = 'active'""")
                connection.execute("""CREATE TABLE IF NOT EXISTS budget_commitments (
                    budget_id TEXT NOT NULL,
                    commitment_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    state TEXT NOT NULL CHECK(state IN ('pending', 'active', 'unknown', 'closed')),
                    record_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )""")
                connection.execute("""CREATE TABLE IF NOT EXISTS controlled_details (
                    detail_ref TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    kind TEXT NOT NULL CHECK(kind IN ('delivery', 'payee', 'payee_search')),
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )""")
                connection.execute("PRAGMA user_version = 5")
            if version < 6:
                connection.execute("""CREATE TABLE IF NOT EXISTS adopted_budgets (
                    user_id TEXT NOT NULL,
                    demo_round_id TEXT NOT NULL,
                    budget_id TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK(version >= 1),
                    source_task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    adoption_interaction_id TEXT NOT NULL,
                    task_revision INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active', 'superseded')),
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(user_id, demo_round_id, budget_id, version),
                    UNIQUE(user_id, demo_round_id, source_task_id, adoption_interaction_id)
                )""")
                connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS
                    adopted_budgets_one_active_version
                    ON adopted_budgets(user_id, demo_round_id, budget_id)
                    WHERE status = 'active'""")
                connection.execute("PRAGMA user_version = 6")
            if version < 7:
                # v05-birthday-platform-dependencies/05: one-shot G3 candidate
                # seals. Only this table and indexes are added; older checkpoints,
                # tasks and namespaces stay as they are.
                connection.execute("""CREATE TABLE IF NOT EXISTS checkpoint_seals (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('root', 'normal', 'edit')),
                    edit_ref TEXT,
                    source_checkpoint_ns TEXT,
                    source_checkpoint_id TEXT,
                    conversion_digest TEXT NOT NULL,
                    source_digest TEXT,
                    accepted_version INTEGER NOT NULL CHECK(accepted_version >= 0),
                    binding_digest TEXT NOT NULL,
                    content_digest TEXT NOT NULL,
                    sealed_at TEXT NOT NULL,
                    PRIMARY KEY(thread_id, checkpoint_ns, checkpoint_id),
                    UNIQUE(thread_id, binding_digest),
                    UNIQUE(thread_id, checkpoint_ns),
                    CHECK (
                        (kind = 'root' AND source_checkpoint_ns IS NULL
                         AND source_checkpoint_id IS NULL AND edit_ref IS NULL
                         AND source_digest IS NULL)
                        OR (kind = 'normal' AND source_checkpoint_ns IS NOT NULL
                         AND source_checkpoint_id IS NOT NULL AND edit_ref IS NULL
                         AND source_digest IS NOT NULL)
                        OR (kind = 'edit' AND source_checkpoint_ns IS NOT NULL
                         AND source_checkpoint_id IS NOT NULL AND edit_ref IS NOT NULL
                         AND source_digest IS NOT NULL)
                    ),
                    FOREIGN KEY(thread_id, source_checkpoint_ns, source_checkpoint_id)
                        REFERENCES checkpoints(thread_id, checkpoint_ns, checkpoint_id)
                )""")
                connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS
                    checkpoint_seals_single_root ON checkpoint_seals(thread_id)
                    WHERE kind = 'root'""")
                connection.execute("PRAGMA user_version = 7")

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

    # --- v05-cross-platform/02: task relations, arrangements, budget seams, details ---

    def link_child_task(
        self, user_id: str, demo_round_id: str, parent_task_id: str,
        child_task_id: str, step_id: str, plan_revision: int,
    ) -> None:
        """Idempotently record that a child task belongs to one parent step."""
        if parent_task_id == child_task_id:
            raise ValueError("a task cannot be its own child")
        with transaction(self.path) as connection:
            for role, task_id in (("parent", parent_task_id), ("child", child_task_id)):
                try:
                    _require_task_in_scope(connection, user_id, demo_round_id, task_id)
                except ValueError as exc:
                    raise ValueError(f"{role} task is not in scope") from exc
            existing = connection.execute(
                "SELECT parent_task_id FROM task_relations WHERE child_task_id = ?",
                (child_task_id,),
            ).fetchone()
            if existing is not None:
                if existing["parent_task_id"] != parent_task_id:
                    raise ValueError("child task already belongs to another parent")
                return
            connection.execute(
                "INSERT INTO task_relations VALUES (?, ?, ?, ?, ?, ?, ?)",
                (parent_task_id, child_task_id, user_id, demo_round_id,
                 step_id, plan_revision, datetime.now(timezone.utc).isoformat()),
            )

    def list_child_tasks(
        self, user_id: str, demo_round_id: str, parent_task_id: str,
    ) -> list[TaskRelation]:
        connection = connect(self.path)
        try:
            rows = connection.execute(
                """SELECT parent_task_id, child_task_id, step_id, plan_revision, linked_at
                   FROM task_relations
                   WHERE user_id = ? AND demo_round_id = ? AND parent_task_id = ?
                   ORDER BY linked_at, child_task_id""",
                (user_id, demo_round_id, parent_task_id),
            ).fetchall()
            return [TaskRelation(**dict(row)) for row in rows]
        finally:
            connection.close()

    def parent_of_task(self, user_id: str, demo_round_id: str, child_task_id: str) -> str | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                """SELECT parent_task_id FROM task_relations
                   WHERE user_id = ? AND demo_round_id = ? AND child_task_id = ?""",
                (user_id, demo_round_id, child_task_id),
            ).fetchone()
            return row["parent_task_id"] if row else None
        finally:
            connection.close()

    def task_lineage(self, user_id: str, demo_round_id: str, task_id: str) -> list[str]:
        """The task and its ancestors, nearest parent first (bounded walk)."""
        lineage = [task_id]
        connection = connect(self.path)
        try:
            current = task_id
            for _ in range(64):
                row = connection.execute(
                    """SELECT parent_task_id FROM task_relations
                       WHERE user_id = ? AND demo_round_id = ? AND child_task_id = ?""",
                    (user_id, demo_round_id, current),
                ).fetchone()
                if row is None or row["parent_task_id"] in lineage:
                    break
                lineage.append(row["parent_task_id"])
                current = row["parent_task_id"]
            return lineage
        finally:
            connection.close()

    def acquire_arrangement(self, record: AdoptedArrangement) -> AdoptedArrangement:
        """D1 seam: check-and-register in one serialized write.

        A different task's active arrangement on the same account raises
        ArrangementConflictError; the same task revising its plan supersedes its
        own previous arrangement and keeps the account's single active record.
        """
        with transaction(self.path) as connection:
            _require_task_in_scope(
                connection, record.user_id, record.demo_round_id, record.source_task_id,
            )
            existing = connection.execute(
                """SELECT source_task_id, status, record_json FROM arrangements
                   WHERE arrangement_id = ? AND user_id = ? AND demo_round_id = ?""",
                (record.arrangement_id, record.user_id, record.demo_round_id),
            ).fetchone()
            if existing is not None:
                if existing["record_json"] == _stable_dump(record):
                    return record
                raise ValueError("arrangement_id is already bound to a different record")
            active = connection.execute(
                """SELECT arrangement_id, source_task_id FROM arrangements
                   WHERE user_id = ? AND demo_round_id = ? AND payer_account_id = ?
                     AND status = 'active'""",
                (record.user_id, record.demo_round_id, record.payer_account_id),
            ).fetchone()
            if active is not None and active["source_task_id"] != record.source_task_id:
                raise ArrangementConflictError(
                    active["source_task_id"], active["arrangement_id"], record.payer_account_id,
                )
            if active is not None:
                connection.execute(
                    """UPDATE arrangements SET status = 'superseded'
                       WHERE arrangement_id = ? AND user_id = ? AND demo_round_id = ?""",
                    (active["arrangement_id"], record.user_id, record.demo_round_id),
                )
            connection.execute(
                "INSERT INTO arrangements VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
                (record.arrangement_id, record.user_id, record.demo_round_id,
                 record.payer_account_id, record.source_task_id,
                 _stable_dump(record), record.adopted_at.isoformat()),
            )
        return record

    def close_arrangement(self, user_id: str, demo_round_id: str, arrangement_id: str) -> None:
        """Close the active arrangement; the caller verifies in-flight facts first."""
        with transaction(self.path) as connection:
            changed = connection.execute(
                """UPDATE arrangements SET status = 'closed'
                   WHERE arrangement_id = ? AND user_id = ? AND demo_round_id = ?
                     AND status = 'active'""",
                (arrangement_id, user_id, demo_round_id),
            ).rowcount
            if changed != 1:
                raise ValueError("arrangement is not active")

    def get_arrangement(
        self, user_id: str, demo_round_id: str, arrangement_id: str,
    ) -> ArrangementRecord | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                """SELECT * FROM arrangements
                   WHERE arrangement_id = ? AND user_id = ? AND demo_round_id = ?""",
                (arrangement_id, user_id, demo_round_id),
            ).fetchone()
            return self._arrangement(row) if row else None
        finally:
            connection.close()

    def get_active_arrangement(
        self, user_id: str, demo_round_id: str, payer_account_id: str,
    ) -> ArrangementRecord | None:
        """Read-only D1 check for other in-app spend entry points."""
        connection = connect(self.path)
        try:
            row = connection.execute(
                """SELECT * FROM arrangements
                   WHERE user_id = ? AND demo_round_id = ? AND payer_account_id = ?
                     AND status = 'active'""",
                (user_id, demo_round_id, payer_account_id),
            ).fetchone()
            return self._arrangement(row) if row else None
        finally:
            connection.close()

    @staticmethod
    def _arrangement(row) -> ArrangementRecord:
        return ArrangementRecord(
            record=AdoptedArrangement.model_validate_json(row["record_json"]),
            payer_account_id=row["payer_account_id"],
            status=row["status"],
        )

    def adopt_budget(
        self, user_id: str, demo_round_id: str, record: AdoptedBudget, *,
        expected_task_revision: int, previous_version: int | None = None,
    ) -> AdoptedBudget:
        """Persist a caller-verified adoption; this is not an authorization API.

        The controlled cross caller verifies F10 adopt, the original interaction,
        plan version and scope/purpose/limit snapshot before calling. Here the
        trusted actor, source task revision, replay identity and version change
        are checked in one write transaction. Exact replays return the original
        version with its current status, even after the task has moved on.
        """
        if (record.user_id, record.demo_round_id) != (user_id, demo_round_id):
            raise ValueError("budget is not in scope")
        if record.status != "active":
            raise ValueError("only an active adoption may be submitted")
        if (previous_version is None and record.version != 1) or (
            previous_version is not None
            and (previous_version < 1 or record.version != previous_version + 1)
        ):
            raise ValueError("budget adoption must follow the previous version")
        with transaction(self.path) as connection:
            _require_task_in_scope(connection, user_id, demo_round_id, record.source_task_id)
            replay = connection.execute(
                """SELECT * FROM adopted_budgets WHERE user_id = ? AND demo_round_id = ?
                   AND source_task_id = ? AND adoption_interaction_id = ?""",
                (user_id, demo_round_id, record.source_task_id, record.adoption_interaction_id),
            ).fetchone()
            if replay is not None:
                if (replay["record_json"] != _stable_dump(record)
                        or replay["task_revision"] != expected_task_revision):
                    raise ValueError("budget adoption interaction conflicts with its original request")
                return self._adopted_budget(replay)
            task = connection.execute(
                "SELECT revision FROM tasks WHERE task_id = ?",
                (record.source_task_id,),
            ).fetchone()
            if task["revision"] != expected_task_revision:
                raise ValueError("budget source task changed concurrently")
            current = connection.execute(
                """SELECT version FROM adopted_budgets
                   WHERE user_id = ? AND demo_round_id = ? AND budget_id = ?
                   AND status = 'active'""",
                (user_id, demo_round_id, record.budget_id),
            ).fetchone()
            if (current["version"] if current else None) != previous_version:
                raise ValueError("budget active version changed concurrently")
            if current is not None:
                connection.execute(
                    """UPDATE adopted_budgets SET status = 'superseded'
                       WHERE user_id = ? AND demo_round_id = ? AND budget_id = ?
                       AND version = ?""",
                    (user_id, demo_round_id, record.budget_id, previous_version),
                )
            connection.execute(
                "INSERT INTO adopted_budgets VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)",
                (user_id, demo_round_id, record.budget_id, record.version,
                 record.source_task_id, record.adoption_interaction_id, expected_task_revision,
                 _stable_dump(record)),
            )
            return record

    @staticmethod
    def _adopted_budget(row) -> AdoptedBudget:
        # The immutable request snapshot permits replay after supersession.
        return AdoptedBudget.model_validate_json(row["record_json"]).model_copy(
            update={"status": row["status"]},
        )

    def get_adopted_budget(
        self, user_id: str, demo_round_id: str, budget_ref: BudgetRef,
    ) -> AdoptedBudget | None:
        """Read an exact version, including superseded history, within trusted scope."""
        connection = connect(self.path)
        try:
            row = connection.execute(
                """SELECT record_json, status FROM adopted_budgets
                   WHERE user_id = ? AND demo_round_id = ? AND budget_id = ? AND version = ?""",
                (user_id, demo_round_id, budget_ref.budget_id, budget_ref.version),
            ).fetchone()
            return self._adopted_budget(row) if row else None
        finally:
            connection.close()

    def list_adopted_budgets(
        self, user_id: str, demo_round_id: str, *, include_superseded: bool = False,
    ) -> list[AdoptedBudget]:
        """Return scoped candidates; cross decides account/date/purpose applicability."""
        connection = connect(self.path)
        try:
            rows = connection.execute(
                """SELECT record_json, status FROM adopted_budgets
                   WHERE user_id = ? AND demo_round_id = ?
                   AND (status = 'active' OR ?) ORDER BY budget_id, version""",
                (user_id, demo_round_id, include_superseded),
            ).fetchall()
            return [self._adopted_budget(row) for row in rows]
        finally:
            connection.close()

    def register_budget_commitment(
        self, user_id: str, demo_round_id: str, record: BudgetCommitment, *,
        max_in_flight_fen: int | None = None,
    ) -> BudgetCommitment:
        """Serialized check-and-register per budget_id (§5.4).

        max_in_flight_fen is the caller's own remaining cap; the sum of non-closed
        unconsumed occupations (this one included) must not exceed it inside the
        same write transaction, so two competing tasks cannot interleave.
        """
        with transaction(self.path) as connection:
            _require_task_in_scope(connection, user_id, demo_round_id, record.task_id)
            existing = connection.execute(
                """SELECT record_json FROM budget_commitments WHERE commitment_id = ?""",
                (record.commitment_id,),
            ).fetchone()
            if existing is not None:
                if existing["record_json"] == _stable_dump(record):
                    return record
                raise ValueError("commitment_id is already bound to a different record")
            if max_in_flight_fen is not None:
                rows = connection.execute(
                    """SELECT record_json FROM budget_commitments
                       WHERE user_id = ? AND demo_round_id = ? AND budget_id = ?
                         AND state != 'closed'""",
                    (user_id, demo_round_id, record.budget_ref.budget_id),
                ).fetchall()
                in_flight = sum(
                    BudgetCommitment.model_validate_json(row["record_json"]).unconsumed_fen
                    for row in rows
                ) + record.unconsumed_fen
                if in_flight > max_in_flight_fen:
                    raise BudgetOccupationExceededError(
                        record.budget_ref.budget_id, in_flight, max_in_flight_fen,
                    )
            connection.execute(
                "INSERT INTO budget_commitments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (record.budget_ref.budget_id, record.commitment_id, user_id, demo_round_id,
                 record.task_id, record.state, _stable_dump(record), record.updated_at.isoformat()),
            )
        return record

    def update_budget_commitment(
        self, user_id: str, demo_round_id: str, commitment_id: str, record: BudgetCommitment,
    ) -> BudgetCommitment:
        """Update one commitment in place; unknown occupations stay queryable."""
        with transaction(self.path) as connection:
            existing = connection.execute(
                """SELECT budget_id, task_id FROM budget_commitments
                   WHERE commitment_id = ? AND user_id = ? AND demo_round_id = ?""",
                (commitment_id, user_id, demo_round_id),
            ).fetchone()
            if existing is None:
                raise ValueError("commitment is not in scope")
            if (existing["budget_id"], existing["task_id"]) != (
                record.budget_ref.budget_id, record.task_id,
            ):
                raise ValueError("commitment identity cannot change")
            changed = connection.execute(
                """UPDATE budget_commitments SET state = ?, record_json = ?, updated_at = ?
                   WHERE commitment_id = ? AND user_id = ? AND demo_round_id = ?""",
                (record.state, _stable_dump(record), record.updated_at.isoformat(),
                 commitment_id, user_id, demo_round_id),
            ).rowcount
            if changed != 1:
                raise ValueError("commitment is not in scope")
        return record

    def list_budget_commitments(
        self, user_id: str, demo_round_id: str, budget_id: str, *, include_closed: bool = False,
    ) -> list[BudgetCommitment]:
        connection = connect(self.path)
        try:
            rows = connection.execute(
                """SELECT record_json FROM budget_commitments
                   WHERE user_id = ? AND demo_round_id = ? AND budget_id = ?
                     AND (? OR state != 'closed')
                   ORDER BY updated_at, commitment_id""",
                (user_id, demo_round_id, budget_id, include_closed),
            ).fetchall()
            return [BudgetCommitment.model_validate_json(row["record_json"]) for row in rows]
        finally:
            connection.close()

    def store_controlled_detail(
        self, detail_ref: str, user_id: str, demo_round_id: str, task_id: str,
        kind: str, payload: dict, created_at: str,
    ) -> None:
        """Store raw controlled facts (delivery etc.) under their owner's scope only."""
        if kind not in {"delivery", "payee", "payee_search"}:
            raise ValueError("unsupported controlled detail kind")
        with transaction(self.path) as connection:
            _require_task_in_scope(connection, user_id, demo_round_id, task_id)
            existing = connection.execute(
                """SELECT user_id, demo_round_id, kind, payload_json FROM controlled_details
                   WHERE detail_ref = ?""",
                (detail_ref,),
            ).fetchone()
            payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if existing is not None:
                same = (
                    existing["user_id"], existing["demo_round_id"], existing["kind"],
                    existing["payload_json"],
                ) == (user_id, demo_round_id, kind, payload_json)
                if not same:
                    raise ValueError("detail_ref is already bound to different facts")
                return
            connection.execute(
                "INSERT INTO controlled_details VALUES (?, ?, ?, ?, ?, ?, ?)",
                (detail_ref, user_id, demo_round_id, task_id, kind, payload_json, created_at),
            )

    def get_controlled_detail(
        self, user_id: str, demo_round_id: str, detail_ref: str, *, task_id: str | None = None,
    ) -> ControlledDetail | None:
        connection = connect(self.path)
        try:
            row = connection.execute(
                "SELECT * FROM controlled_details WHERE detail_ref = ?", (detail_ref,),
            ).fetchone()
            if row is None or (row["user_id"], row["demo_round_id"]) != (user_id, demo_round_id):
                return None
            if task_id is not None and row["task_id"] != task_id:
                return None
            return ControlledDetail(
                detail_ref=row["detail_ref"], user_id=row["user_id"],
                demo_round_id=row["demo_round_id"], task_id=row["task_id"],
                kind=row["kind"], payload=json.loads(row["payload_json"]),
                created_at=row["created_at"],
            )
        finally:
            connection.close()
