"""SQLite-backed LangGraph checkpoints bound to one authorized task."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, Sequence

from langgraph.checkpoint.base import (
    BaseCheckpointSaver, CheckpointTuple, WRITES_IDX_MAP, get_checkpoint_id,
    get_checkpoint_metadata,
)

from .database import connect, transaction

_CANDIDATE_KINDS = {"root", "normal", "edit"}


@dataclass(frozen=True)
class CheckpointRef:
    """One full checkpoint reference inside a task-owned thread."""

    thread_id: str
    checkpoint_ns: str
    checkpoint_id: str


@dataclass(frozen=True)
class SealedCandidate:
    """The first persisted winner of one controlled G3 transition."""

    ref: CheckpointRef
    kind: str
    source: CheckpointRef | None
    edit_ref: str | None
    accepted_version: int
    conversion_digest: str
    source_digest: str | None
    content_digest: str
    checkpoint: dict
    metadata: dict
    writes: tuple[tuple[str, str, Any], ...]


class CandidateBindingConflictError(ValueError):
    """The reserved candidate ref already holds a different trusted binding."""

    def __init__(self, existing: CheckpointRef):
        self.existing = existing
        super().__init__("CANDIDATE_BINDING_CONFLICT")


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
            self._reject_sealed(connection, thread_id, namespace)
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
            self._reject_sealed(connection, thread_id, namespace)
            for index, (channel, value) in enumerate(writes):
                write_index = WRITES_IDX_MAP.get(channel, index)
                value_type, value_blob = self.serde.dumps_typed(value)
                statement = "INSERT OR IGNORE" if write_index >= 0 else "INSERT OR REPLACE"
                connection.execute(
                    statement + " INTO checkpoint_writes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (thread_id, namespace, checkpoint_id, task_id, write_index,
                     channel, value_type, value_blob, task_path),
                )

    # --- v05-birthday-platform-dependencies/05: one-shot candidate seal ---

    def _reject_sealed(self, connection, thread_id: str, namespace: str) -> None:
        """A sealed candidate namespace is frozen; overwrite paths cannot touch it."""
        sealed = connection.execute(
            """SELECT 1 FROM checkpoint_seals
               WHERE thread_id = ? AND checkpoint_ns = ? LIMIT 1""",
            (thread_id, namespace),
        ).fetchone()
        if sealed is not None:
            raise ValueError("sealed checkpoint namespace is immutable")

    @staticmethod
    def _sealed_row(connection, ref: CheckpointRef):
        return connection.execute(
            """SELECT * FROM checkpoint_seals
               WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?""",
            (ref.thread_id, ref.checkpoint_ns, ref.checkpoint_id),
        ).fetchone()

    @staticmethod
    def _ref_from(row) -> CheckpointRef:
        return CheckpointRef(row["thread_id"], row["checkpoint_ns"], row["checkpoint_id"])

    def _sealed(self, connection, row) -> SealedCandidate:
        stored = connection.execute(
            """SELECT * FROM checkpoints
               WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?""",
            (row["thread_id"], row["checkpoint_ns"], row["checkpoint_id"]),
        ).fetchone()
        if stored is None:
            raise RuntimeError("sealed checkpoint content is missing")
        winner = self._tuple(connection, stored)
        source = None
        if row["source_checkpoint_ns"] is not None:
            source = CheckpointRef(
                row["thread_id"], row["source_checkpoint_ns"],
                row["source_checkpoint_id"],
            )
        return SealedCandidate(
            ref=self._ref_from(row),
            kind=row["kind"], source=source, edit_ref=row["edit_ref"],
            accepted_version=row["accepted_version"],
            conversion_digest=row["conversion_digest"],
            source_digest=row["source_digest"], content_digest=row["content_digest"],
            checkpoint=winner.checkpoint, metadata=winner.metadata,
            writes=tuple(winner.pending_writes),
        )

    @staticmethod
    def _binding_digest(
        kind: str, source: CheckpointRef | None, edit_ref: str | None,
        conversion_digest: str, source_digest: str | None, accepted_version: int,
    ) -> str:
        binding = {
            "kind": kind, "edit_ref": edit_ref, "conversion_digest": conversion_digest,
            "source_digest": source_digest, "accepted_version": accepted_version,
            "source": None if source is None else [
                source.thread_id, source.checkpoint_ns, source.checkpoint_id,
            ],
        }
        encoded = json.dumps(
            binding, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _content_digest(entries: Sequence[tuple[str, bytes]]) -> str:
        digest = hashlib.sha256()
        for label, payload in entries:
            digest.update(label.encode("utf-8"))
            digest.update(len(payload).to_bytes(8, "big"))
            digest.update(payload)
        return digest.hexdigest()

    def _write_sealed_content(
        self, connection, candidate: CheckpointRef, checkpoint: dict, metadata: dict,
        new_versions: dict, writes: Sequence[tuple[str, Any]],
        writes_task_id: str, writes_task_path: str,
    ) -> str:
        values = checkpoint["channel_values"]
        without_values = {
            key: value for key, value in checkpoint.items() if key != "channel_values"
        }
        config = {"configurable": {
            "thread_id": candidate.thread_id, "checkpoint_ns": candidate.checkpoint_ns,
            "checkpoint_id": candidate.checkpoint_id,
        }}
        checkpoint_type, checkpoint_blob = self.serde.dumps_typed(without_values)
        metadata_type, metadata_blob = self.serde.dumps_typed(
            get_checkpoint_metadata(config, metadata),
        )
        entries = [
            (f"checkpoint:{checkpoint_type}", checkpoint_blob),
            (f"metadata:{metadata_type}", metadata_blob),
        ]
        connection.execute(
            """INSERT INTO checkpoints (
                   thread_id, checkpoint_ns, checkpoint_id, parent_id,
                   checkpoint_type, checkpoint_blob, metadata_type, metadata_blob
               ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?)""",
            (candidate.thread_id, candidate.checkpoint_ns, candidate.checkpoint_id,
             checkpoint_type, checkpoint_blob, metadata_type, metadata_blob),
        )
        for channel, version in new_versions.items():
            value_type, value_blob = (
                self.serde.dumps_typed(values[channel]) if channel in values
                else ("empty", b"")
            )
            connection.execute(
                "INSERT INTO checkpoint_blobs VALUES (?, ?, ?, ?, ?, ?)",
                (candidate.thread_id, candidate.checkpoint_ns, channel, str(version),
                 value_type, value_blob),
            )
            entries.append((f"blob:{channel}:{version}:{value_type}", value_blob))
        for index, (channel, value) in enumerate(writes):
            write_index = WRITES_IDX_MAP.get(channel, index)
            value_type, value_blob = self.serde.dumps_typed(value)
            connection.execute(
                "INSERT INTO checkpoint_writes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (candidate.thread_id, candidate.checkpoint_ns,
                 candidate.checkpoint_id, writes_task_id, write_index, channel,
                 value_type, value_blob, writes_task_path),
            )
            entries.append((
                f"write:{writes_task_id}:{writes_task_path}:{write_index}:"
                f"{channel}:{value_type}",
                value_blob,
            ))
        return self._content_digest(entries)

    def seal_candidate(
        self, user_id: str, demo_round_id: str, task_id: str, *,
        kind: str, candidate: CheckpointRef, accepted_version: int,
        conversion_digest: str, checkpoint: dict, metadata: dict, new_versions: dict,
        source: CheckpointRef | None = None, source_digest: str | None = None,
        edit_ref: str | None = None,
        writes: Sequence[tuple[str, Any]] = (),
        writes_task_id: str = "", writes_task_path: str = "",
    ) -> SealedCandidate:
        """Persist one controlled G3 state exactly once and keep it immutable.

        03 already reserved ``candidate`` through its own task CAS before calling
        this. The trusted binding (kind, edit/source association, conversion
        digest, source digest, accepted version) selects the single winner:
        retries/competition with the same binding read the first stored content,
        a different binding for the same ref raises
        ``CandidateBindingConflictError`` and never touches the stored blob.

        ``kind="root"`` seals the first state of a task (no predecessor, no edit
        request); ``kind="normal"`` seals an input/fact/exception successor bound
        to a previously sealed source; ``kind="edit"`` additionally binds the
        original edit request. The returned ``ref`` is the first sealed ref for
        the binding: on a lost race it can differ from the candidate ref the caller
        reserved. The candidate namespace must be a fresh, isolated namespace: the
        default latest-readable namespace stays for the legacy LangGraph flow, and
        neither channel versions of the source nor of another candidate are shared
        or rewritten.
        """
        if kind not in _CANDIDATE_KINDS:
            raise ValueError("unsupported candidate kind")
        self._scope({"configurable": {
            "thread_id": candidate.thread_id, "checkpoint_ns": candidate.checkpoint_ns,
        }})
        if not candidate.checkpoint_ns:
            raise ValueError("candidate namespace must be isolated")
        if checkpoint.get("id") != candidate.checkpoint_id:
            raise ValueError("candidate ref does not match the checkpoint id")
        if (not isinstance(accepted_version, int) or isinstance(accepted_version, bool)
                or accepted_version < 0):
            raise ValueError("accepted version must be a non-negative integer")
        if not conversion_digest:
            raise ValueError("conversion digest is required")
        if source is None:
            if kind != "root":
                raise ValueError("a successor candidate requires a sealed source")
            if source_digest is not None:
                raise ValueError("an initial root has no source digest")
        else:
            if kind == "root":
                raise ValueError("an initial root has no source")
            if source.thread_id != candidate.thread_id:
                raise ValueError("source checkpoint is not in the candidate thread")
            if not source_digest:
                raise ValueError("a source digest is required")
        if kind == "edit":
            if not edit_ref:
                raise ValueError("an edit candidate requires its edit_ref")
        elif edit_ref is not None:
            raise ValueError("only an edit candidate binds an edit_ref")
        if writes and not writes_task_id:
            raise ValueError("associated writes require their task_id")

        binding_digest = self._binding_digest(
            kind, source, edit_ref, conversion_digest, source_digest, accepted_version,
        )
        with transaction(self.path) as connection:
            task = connection.execute(
                """SELECT checkpoint_thread_id, checkpoint_id FROM tasks
                   WHERE task_id = ? AND user_id = ? AND demo_round_id = ?""",
                (task_id, user_id, demo_round_id),
            ).fetchone()
            if task is None:
                raise ValueError("task is not in scope")
            if task["checkpoint_thread_id"] != candidate.thread_id:
                raise ValueError("checkpoint thread is not in task scope")

            sealed = self._sealed_row(connection, candidate)
            if sealed is not None:
                if sealed["binding_digest"] != binding_digest:
                    raise CandidateBindingConflictError(self._ref_from(sealed))
                return self._sealed(connection, sealed)
            winner = connection.execute(
                """SELECT * FROM checkpoint_seals
                   WHERE thread_id = ? AND binding_digest = ?""",
                (candidate.thread_id, binding_digest),
            ).fetchone()
            if winner is not None:
                return self._sealed(connection, winner)

            if kind == "root":
                if task["checkpoint_id"] is not None:
                    raise ValueError(
                        "an initial root requires no published checkpoint",
                    )
                predecessor = connection.execute(
                    """SELECT 1 FROM checkpoints WHERE thread_id = ?
                       UNION ALL
                       SELECT 1 FROM checkpoint_blobs WHERE thread_id = ?
                       UNION ALL
                       SELECT 1 FROM checkpoint_writes WHERE thread_id = ?
                       LIMIT 1""",
                    (candidate.thread_id,) * 3,
                ).fetchone()
                if predecessor is not None:
                    raise ValueError("an initial root requires no predecessor state")
            elif self._sealed_row(connection, source) is None:
                raise ValueError("source checkpoint is not a sealed candidate")
            occupied = connection.execute(
                """SELECT 1 FROM checkpoints
                       WHERE thread_id = ? AND checkpoint_ns = ?
                   UNION ALL
                   SELECT 1 FROM checkpoint_blobs
                       WHERE thread_id = ? AND checkpoint_ns = ?
                   UNION ALL
                   SELECT 1 FROM checkpoint_writes
                       WHERE thread_id = ? AND checkpoint_ns = ?
                   LIMIT 1""",
                (candidate.thread_id, candidate.checkpoint_ns) * 3,
            ).fetchone()
            if occupied is not None:
                raise ValueError("candidate namespace already contains checkpoint state")

            content_digest = self._write_sealed_content(
                connection, candidate, checkpoint, metadata, new_versions, writes,
                writes_task_id, writes_task_path,
            )
            connection.execute(
                "INSERT INTO checkpoint_seals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (candidate.thread_id, candidate.checkpoint_ns, candidate.checkpoint_id,
                 kind, edit_ref,
                 None if source is None else source.checkpoint_ns,
                 None if source is None else source.checkpoint_id,
                 conversion_digest, source_digest, accepted_version, binding_digest,
                 content_digest, datetime.now(timezone.utc).isoformat()),
            )
            sealed = self._sealed_row(connection, candidate)
            return self._sealed(connection, sealed)

    def delete_thread(self, thread_id: str) -> None:
        if thread_id != self.thread_id:
            raise ValueError("checkpoint thread is not in task scope")
        with transaction(self.path) as connection:
            if connection.execute(
                "SELECT 1 FROM checkpoint_seals WHERE thread_id = ? LIMIT 1",
                (thread_id,),
            ).fetchone() is not None:
                raise ValueError("thread contains sealed checkpoints")
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
