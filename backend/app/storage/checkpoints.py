"""SQLite-backed LangGraph checkpoints bound to one authorized task."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, Sequence

from langgraph.checkpoint.base import (
    BaseCheckpointSaver, CheckpointTuple, WRITES_IDX_MAP, get_checkpoint_id,
    get_checkpoint_metadata,
)

from .database import connect, transaction


class SqliteCheckpointSaver(BaseCheckpointSaver):
    def __init__(self, path: Path, thread_id: str):
        super().__init__()
        self.path = path
        self.thread_id = thread_id

    def _scope(self, config: dict | None) -> tuple[str, str]:
        configurable = (config or {}).get("configurable", {})
        requested = configurable.get("thread_id", self.thread_id)
        if requested != self.thread_id:
            raise ValueError("checkpoint thread is not in task scope")
        return self.thread_id, configurable.get("checkpoint_ns", "")

    def _tuple(self, connection, row) -> CheckpointTuple:
        thread_id, namespace, checkpoint_id = (
            row["thread_id"], row["checkpoint_ns"], row["checkpoint_id"],
        )
        checkpoint = self.serde.loads_typed((row["checkpoint_type"], row["checkpoint_blob"]))
        values = {}
        for channel, version in checkpoint["channel_versions"].items():
            blob = connection.execute(
                """SELECT value_type, value_blob FROM checkpoint_blobs
                   WHERE thread_id = ? AND checkpoint_ns = ? AND channel = ? AND version = ?""",
                (thread_id, namespace, channel, str(version)),
            ).fetchone()
            if blob is not None and blob["value_type"] != "empty":
                values[channel] = self.serde.loads_typed((blob["value_type"], blob["value_blob"]))
        writes = connection.execute(
            """SELECT task_id, channel, value_type, value_blob FROM checkpoint_writes
               WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?
               ORDER BY rowid""",
            (thread_id, namespace, checkpoint_id),
        ).fetchall()
        config = {"configurable": {
            "thread_id": thread_id, "checkpoint_ns": namespace, "checkpoint_id": checkpoint_id,
        }}
        parent_config = (
            {"configurable": {
                "thread_id": thread_id, "checkpoint_ns": namespace,
                "checkpoint_id": row["parent_id"],
            }} if row["parent_id"] else None
        )
        return CheckpointTuple(
            config=config,
            checkpoint={**checkpoint, "channel_values": values},
            metadata=self.serde.loads_typed((row["metadata_type"], row["metadata_blob"])),
            parent_config=parent_config,
            pending_writes=[
                (write["task_id"], write["channel"],
                 self.serde.loads_typed((write["value_type"], write["value_blob"])))
                for write in writes
            ],
        )

    def get_tuple(self, config: dict) -> CheckpointTuple | None:
        thread_id, namespace = self._scope(config)
        checkpoint_id = get_checkpoint_id(config)
        connection = connect(self.path)
        try:
            if checkpoint_id:
                row = connection.execute(
                    """SELECT * FROM checkpoints WHERE thread_id = ?
                       AND checkpoint_ns = ? AND checkpoint_id = ?""",
                    (thread_id, namespace, checkpoint_id),
                ).fetchone()
            else:
                row = connection.execute(
                    """SELECT * FROM checkpoints WHERE thread_id = ?
                       AND checkpoint_ns = ? ORDER BY row_id DESC LIMIT 1""",
                    (thread_id, namespace),
                ).fetchone()
            return self._tuple(connection, row) if row else None
        finally:
            connection.close()

    def list(
        self, config: dict | None, *, filter: dict[str, Any] | None = None,
        before: dict | None = None, limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        thread_id, namespace = self._scope(config)
        if before is not None:
            self._scope(before)
        connection = connect(self.path)
        try:
            query = "SELECT * FROM checkpoints WHERE thread_id = ?"
            parameters: list[Any] = [thread_id]
            if config is not None and "checkpoint_ns" in config.get("configurable", {}):
                query += " AND checkpoint_ns = ?"
                parameters.append(namespace)
            if config is not None and (checkpoint_id := get_checkpoint_id(config)):
                query += " AND checkpoint_id = ?"
                parameters.append(checkpoint_id)
            if before is not None and (before_id := get_checkpoint_id(before)):
                preceding = connection.execute(
                    """SELECT row_id FROM checkpoints WHERE thread_id = ? AND checkpoint_id = ?""",
                    (thread_id, before_id),
                ).fetchone()
                if preceding is None:
                    return
                query += " AND row_id < ?"
                parameters.append(preceding["row_id"])
            for row in connection.execute(query + " ORDER BY row_id DESC", parameters):
                item = self._tuple(connection, row)
                if filter and any(item.metadata.get(key) != value for key, value in filter.items()):
                    continue
                if limit is not None and limit <= 0:
                    break
                yield item
                if limit is not None:
                    limit -= 1
        finally:
            connection.close()

    def put(
        self, config: dict, checkpoint: dict, metadata: dict, new_versions: dict,
    ) -> dict:
        thread_id, namespace = self._scope(config)
        values = checkpoint["channel_values"]
        without_values = {key: value for key, value in checkpoint.items() if key != "channel_values"}
        checkpoint_type, checkpoint_blob = self.serde.dumps_typed(without_values)
        metadata_type, metadata_blob = self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
        with transaction(self.path) as connection:
            for channel, version in new_versions.items():
                value_type, value_blob = (
                    self.serde.dumps_typed(values[channel]) if channel in values else ("empty", b"")
                )
                connection.execute(
                    """INSERT OR REPLACE INTO checkpoint_blobs VALUES (?, ?, ?, ?, ?, ?)""",
                    (thread_id, namespace, channel, str(version), value_type, value_blob),
                )
            connection.execute(
                """INSERT INTO checkpoints (
                       thread_id, checkpoint_ns, checkpoint_id, parent_id,
                       checkpoint_type, checkpoint_blob, metadata_type, metadata_blob
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (thread_id, namespace, checkpoint["id"],
                 config["configurable"].get("checkpoint_id"), checkpoint_type,
                 checkpoint_blob, metadata_type, metadata_blob),
            )
        return {"configurable": {
            "thread_id": thread_id, "checkpoint_ns": namespace, "checkpoint_id": checkpoint["id"],
        }}

    def put_writes(
        self, config: dict, writes: Sequence[tuple[str, Any]], task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id, namespace = self._scope(config)
        checkpoint_id = config["configurable"]["checkpoint_id"]
        with transaction(self.path) as connection:
            for index, (channel, value) in enumerate(writes):
                write_index = WRITES_IDX_MAP.get(channel, index)
                value_type, value_blob = self.serde.dumps_typed(value)
                statement = "INSERT OR IGNORE" if write_index >= 0 else "INSERT OR REPLACE"
                connection.execute(
                    statement + " INTO checkpoint_writes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (thread_id, namespace, checkpoint_id, task_id, write_index,
                     channel, value_type, value_blob, task_path),
                )

    def delete_thread(self, thread_id: str) -> None:
        if thread_id != self.thread_id:
            raise ValueError("checkpoint thread is not in task scope")
        with transaction(self.path) as connection:
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                connection.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))

    async def aget_tuple(self, config: dict) -> CheckpointTuple | None:
        return await asyncio.to_thread(self.get_tuple, config)

    async def alist(
        self, config: dict | None, *, filter: dict[str, Any] | None = None,
        before: dict | None = None, limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        items = await asyncio.to_thread(
            lambda: list(self.list(config, filter=filter, before=before, limit=limit)),
        )
        for item in items:
            yield item

    async def aput(
        self, config: dict, checkpoint: dict, metadata: dict, new_versions: dict,
    ) -> dict:
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self, config: dict, writes: Sequence[tuple[str, Any]], task_id: str,
        task_path: str = "",
    ) -> None:
        await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        await asyncio.to_thread(self.delete_thread, thread_id)
