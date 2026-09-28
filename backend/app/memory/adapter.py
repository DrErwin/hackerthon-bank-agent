"""Trusted user/round adapter for Deep Agents memory and task context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Callable
from uuid import UUID

from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from deepagents.middleware.memory import MemoryMiddleware

from app.storage.application import ApplicationStore
from app.storage.checkpoints import SqliteCheckpointSaver
from app.storage.database import connect, transaction

from .store import (
    MEMORY_INDEX, MEMORY_ROOT, SqliteMemoryStore, content_hash, namespace_for,
    validate_memory,
)


@dataclass(frozen=True)
class MemoryContext:
    user_id: str
    session_id: str
    demo_round_id: str


@dataclass(frozen=True)
class MemoryItem:
    memory_id: str
    version: int
    content: str
    updated_at: str


@dataclass(frozen=True)
class MemoryDeleteResult:
    deleted_ids: list[str]
    deleted_at: str
    demo_round_id: str


class ReloadingMemoryMiddleware(MemoryMiddleware):
    """Reload store content so deleted memories cannot survive in checkpoint cache."""

    def before_agent(self, state, runtime, config):
        return super().before_agent({k: v for k, v in state.items() if k != "memory_contents"}, runtime, config)

    async def abefore_agent(self, state, runtime, config):
        return await super().abefore_agent(
            {k: v for k, v in state.items() if k != "memory_contents"}, runtime, config,
        )


class MemoryAdapter:
    def __init__(self, application: ApplicationStore, active_round: Callable[[], str]):
        self.application = application
        self.store = SqliteMemoryStore(application.path)
        self.active_round = active_round

    def _scope(self, context: MemoryContext) -> tuple[str, ...]:
        if context.demo_round_id != self.active_round():
            raise ValueError("STALE_ROUND")
        session = self.application.get_session(
            context.user_id, context.demo_round_id, context.session_id,
        )
        if session is None:
            raise PermissionError("ACCESS_DENIED")
        if datetime.fromisoformat(session.expires_at) <= datetime.now(timezone.utc):
            raise PermissionError("AUTH_REQUIRED")
        return namespace_for(context.user_id, context.demo_round_id)

    def backend(self, context: MemoryContext) -> StoreBackend:
        self._scope(context)
        return StoreBackend(store=self.store, namespace=lambda _: self._scope(context))

    def agent_backend(self, context: MemoryContext) -> CompositeBackend:
        return CompositeBackend(
            default=StateBackend(), routes={MEMORY_ROOT: self.backend(context)},
        )

    def middleware(self, context: MemoryContext) -> ReloadingMemoryMiddleware:
        return ReloadingMemoryMiddleware(
            backend=self.backend(context), sources=[MEMORY_INDEX],
        )

    def checkpointer(self, context: MemoryContext, task_id: str):
        self._scope(context)
        task = self.application.get_task(context.user_id, context.demo_round_id, task_id)
        if task is None or task.session_id != context.session_id:
            raise PermissionError("ACCESS_DENIED")
        return self.application.checkpoint_saver(context.user_id, context.demo_round_id, task_id)

    def conversation_thread_id(self, context: MemoryContext) -> str:
        self._scope(context)
        return json.dumps(
            ["conversation", context.demo_round_id, context.user_id, context.session_id],
            ensure_ascii=False, separators=(",", ":"),
        )

    def conversation_checkpointer(self, context: MemoryContext) -> SqliteCheckpointSaver:
        return SqliteCheckpointSaver(self.application.path, self.conversation_thread_id(context))

    def list(self, context: MemoryContext) -> list[MemoryItem]:
        namespace = self._scope(context)
        connection = connect(self.application.path)
        try:
            rows = connection.execute(
                """SELECT key, value_json, version, updated_at FROM memory_files
                   WHERE namespace = ? AND key != ? ORDER BY key""",
                (self.store._namespace(namespace), MEMORY_INDEX),
            ).fetchall()
            return [MemoryItem(
                memory_id=row["key"][len(MEMORY_ROOT):-3], version=row["version"],
                content=json.loads(row["value_json"])["content"], updated_at=row["updated_at"],
            ) for row in rows]
        finally:
            connection.close()

    def delete(self, context: MemoryContext, request_id: str,
               memory_ids: list[str], expected_versions: dict[str, int]) -> MemoryDeleteResult:
        namespace = self.store._namespace(self._scope(context))
        UUID(request_id)
        if (not memory_ids or len(set(memory_ids)) != len(memory_ids)
                or set(memory_ids) != set(expected_versions)
                or any(version <= 0 for version in expected_versions.values())):
            raise ValueError("INVALID_ARGUMENT")
        selected = json.dumps(
            {memory_id: expected_versions[memory_id] for memory_id in sorted(memory_ids)},
            sort_keys=True,
        )
        with transaction(self.application.path) as connection:
            previous = connection.execute(
                "SELECT selected_json, result_json FROM memory_deletions WHERE namespace = ? AND request_id = ?",
                (namespace, request_id),
            ).fetchone()
            if previous is not None:
                if previous["selected_json"] != selected:
                    raise ValueError("REQUEST_CONFLICT")
                return MemoryDeleteResult(**json.loads(previous["result_json"]))
            for memory_id in memory_ids:
                self.store._check_path(f"{MEMORY_ROOT}{memory_id}.md")
                row = connection.execute(
                    "SELECT version FROM memory_files WHERE namespace = ? AND key = ?",
                    (namespace, f"{MEMORY_ROOT}{memory_id}.md"),
                ).fetchone()
                if row is None:
                    raise PermissionError("ACCESS_DENIED")
                if row["version"] != expected_versions[memory_id]:
                    raise ValueError("MEMORY_VERSION_CONFLICT")
            for memory_id in memory_ids:
                content = connection.execute(
                    "SELECT value_json FROM memory_files WHERE namespace = ? AND key = ?",
                    (namespace, f"{MEMORY_ROOT}{memory_id}.md"),
                ).fetchone()["value_json"]
                connection.execute(
                    "INSERT INTO memory_tombstones VALUES (?, ?, ?)",
                    (namespace, f"{MEMORY_ROOT}{memory_id}.md",
                     content_hash(json.loads(content)["content"])),
                )
                connection.execute(
                    "DELETE FROM memory_files WHERE namespace = ? AND key = ?",
                    (namespace, f"{MEMORY_ROOT}{memory_id}.md"),
                )
            self.store._write_index(connection, namespace)
            result = MemoryDeleteResult(
                deleted_ids=memory_ids, deleted_at=datetime.now(timezone.utc).isoformat(),
                demo_round_id=context.demo_round_id,
            )
            connection.execute(
                "INSERT INTO memory_deletions VALUES (?, ?, ?, ?)",
                (namespace, request_id, selected, json.dumps(result.__dict__, ensure_ascii=False)),
            )
            return result

    def seed_demo(self, user_id: str, demo_round_id: str, start_month: str) -> None:
        if demo_round_id != self.active_round():
            raise ValueError("STALE_ROUND")
        if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", start_month):
            raise ValueError("INVALID_ARGUMENT")
        namespace = self.store._namespace(namespace_for(user_id, demo_round_id))
        with transaction(self.application.path) as connection:
            self._seed_in_transaction(connection, namespace, start_month)

    def _seed_in_transaction(self, connection, namespace: str, start_month: str) -> None:
        seeds = {
            "alias-mother": "称呼线索：妈妈 → 银行种子 A2；办理时重新查询并核验收款人。",
            "alias-family": "称呼线索：家庭账户 → 银行种子 A4；办理时重新查询账户。",
            "alias-savings": "称呼线索：储蓄账户 → 银行种子 A5；办理时重新查询账户。",
            "allocation": "收入分配偏好：60% 转 A5 储蓄，20% 转 A4 家庭，20% 留 A1 主账户；实际收入以银行查询为准，逐笔确认。",
            "budget": f"月度预算偏好：{start_month} 个人预算 300000 分；跨到下月不自动沿用。",
            "birthday-delivery": "生日配送演示资料：李演示；DEMO-PHONE-0001；演示市演示区示例路 1 号（虚构）。生日和本次预算由用户当次提供。",
        }
        inserted = connection.execute(
            "INSERT OR IGNORE INTO memory_seeded VALUES (?)", (namespace,),
        ).rowcount
        if not inserted:
            return
        now = datetime.now(timezone.utc).isoformat()
        for memory_id, content in seeds.items():
            validate_memory(content)
            connection.execute(
                "INSERT INTO memory_files VALUES (?, ?, ?, 1, ?, ?)",
                (namespace, f"{MEMORY_ROOT}{memory_id}.md",
                 json.dumps({"content": content, "encoding": "utf-8"}, ensure_ascii=False), now, now),
            )
        self.store._write_index(connection, namespace)

    def reset_user(self, user_id: str, new_round_id: str, start_month: str) -> None:
        if new_round_id != self.active_round():
            raise ValueError("STALE_ROUND")
        if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", start_month):
            raise ValueError("INVALID_ARGUMENT")
        with transaction(self.application.path) as connection:
            new_namespace = self.store._namespace(namespace_for(user_id, new_round_id))
            seeded = connection.execute(
                "SELECT 1 FROM memory_seeded WHERE namespace = ?", (new_namespace,),
            ).fetchone() is not None
            rows = connection.execute("SELECT DISTINCT namespace FROM memory_files").fetchall()
            namespaces = [row["namespace"] for row in rows
                          if tuple(json.loads(row["namespace"]))[-1] == user_id
                          and row["namespace"] != new_namespace]
            for namespace in namespaces:
                connection.execute("DELETE FROM memory_files WHERE namespace = ?", (namespace,))
                connection.execute("DELETE FROM memory_deletions WHERE namespace = ?", (namespace,))
                connection.execute("DELETE FROM memory_seeded WHERE namespace = ?", (namespace,))
                connection.execute("DELETE FROM memory_tombstones WHERE namespace = ?", (namespace,))
            if not seeded:
                self._seed_in_transaction(connection, new_namespace, start_month)
