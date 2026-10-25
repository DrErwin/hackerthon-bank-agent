"""Failure modes of the one-shot G3 candidate seal (v05-birthday-platform-dependencies/05).

Written before the seal exists. These are the ways this boundary can lose the winner
or let a later write touch it:

1. A second checkpoint id in the same namespace reuses a channel version row, so
   reading the first exact id returns the second value (``INSERT OR REPLACE``).
2. A candidate that only changes the checkpoint UUID still shares channel versions
   with its source or another candidate; UUID-only "isolation" is fake.
3. The same edit/source/conversion retried (or prepared from two processes) writes
   twice, so the publisher may publish a different new-input id.
4. A different binding presented for the pre-reserved candidate ref overwrites the
   first content instead of conflicting, or writes before comparing.
5. After sealing, ordinary ``put``/``put_writes``/``delete_thread`` can still change
   or erase the sealed state, including after publication.
6. A task that already published state seals a "root" without a predecessor.
7. A second root with a fresh conversion association creates a second winner.
8. A normal successor binds a legacy overwritable blob instead of a sealed source.
9. An edit candidate hides behind the normal path without its ``edit_ref``.
10. A ref from another task/user/round/thread is sealed into this task.
11. The content is addressed to a different checkpoint id than the reserved ref.
12. A mid-write serialization failure leaves checkpoint rows/blobs/writes/seal behind.
13. A restart loses the first-winner readback or the overwrite protection.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sqlite3
from uuid import uuid4

import pytest

from app.storage import ApplicationStore, StoragePaths
from app.storage.application import SCHEMA_VERSION
from app.storage.checkpoints import (
    CandidateBindingConflictError, CheckpointRef, SqliteCheckpointSaver,
)


NOW = "2026-09-28T10:00:00+08:00"
CHANNEL = "cross_state"


def prepared_task(path):
    store = ApplicationStore(path)
    store.create_session("S1", "U1", "D1", NOW, "2026-09-28T12:00:00+08:00")
    task = store.create_task("T1", "U1", "S1", "D1", "R1", "running", {})
    return store, task


def candidate_ref(task, namespace, checkpoint_id=None) -> CheckpointRef:
    return CheckpointRef(
        task.checkpoint_thread_id, namespace, checkpoint_id or str(uuid4()),
    )


def make_checkpoint(ref, state, version=1):
    return {
        "v": 1, "id": ref.checkpoint_id, "ts": NOW,
        "channel_values": {CHANNEL: state},
        "channel_versions": {CHANNEL: version},
        "versions_seen": {}, "pending_sends": [],
    }


def seal(saver: SqliteCheckpointSaver, ref, task, *, kind="normal", source=None,
         source_digest=None, edit_ref=None, state=None, conversion_digest="request-1",
         accepted_version=0, writes=(), writes_task_id="", metadata=None):
    return saver.seal_candidate(
        "U1", "D1", task.task_id,
        kind=kind, candidate=ref, accepted_version=accepted_version,
        conversion_digest=conversion_digest,
        checkpoint=make_checkpoint(ref, state or {"new_input_id": "I1"}),
        metadata=metadata or {"source": "loop", "step": 1},
        new_versions={CHANNEL: 1},
        source=source, source_digest=source_digest, edit_ref=edit_ref,
        writes=writes, writes_task_id=writes_task_id,
    )


def exact_config(task, ref):
    return {"configurable": {
        "thread_id": task.checkpoint_thread_id,
        "checkpoint_ns": ref.checkpoint_ns,
        "checkpoint_id": ref.checkpoint_id,
    }}


def count(path, table, namespace):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            f"SELECT count(*) FROM {table} WHERE checkpoint_ns = ?", (namespace,),
        ).fetchone()[0]


def test_exact_ref_alone_is_not_isolation_and_seal_rejects_overwrite(tmp_path):
    store, task = prepared_task(StoragePaths(tmp_path).application)
    saver = store.checkpoint_saver("U1", "D1", "T1")
    thread = task.checkpoint_thread_id

    # Once sealed in its own namespace the same overwrite pattern is rejected.
    root = candidate_ref(task, "root-ns")
    winner = seal(saver, root, task, kind="root", state={"new_input_id": "I-root"})
    assert winner.ref == root

    # Counterexample: today another checkpoint id in a different, unsealed
    # namespace reusing channel version 1 rewrites what the first exact id reads.
    first = candidate_ref(task, "legacy")
    saver.put(
        {"configurable": {"thread_id": thread, "checkpoint_ns": "legacy"}},
        make_checkpoint(first, {"new_input_id": "I-first"}), {"step": 1},
        {CHANNEL: 1},
    )
    second = candidate_ref(task, "legacy")
    saver.put(
        {"configurable": {"thread_id": thread, "checkpoint_ns": "legacy",
                          "checkpoint_id": first.checkpoint_id}},
        make_checkpoint(second, {"new_input_id": "I-second"}), {"step": 2},
        {CHANNEL: 1},
    )
    stale = saver.get_tuple(exact_config(task, first))
    assert stale.checkpoint["channel_values"][CHANNEL]["new_input_id"] == "I-second"

    # A candidate may not reuse that populated namespace; a new UUID is not isolation.
    with pytest.raises(ValueError, match="candidate namespace"):
        seal(saver, candidate_ref(task, "legacy"), task, kind="normal",
             source=winner.ref, source_digest="source-digest")

    # Pending writes left in the pre-reserved namespace also make it non-empty.
    dirty = candidate_ref(task, "prewritten")
    saver.put_writes(
        {"configurable": {"thread_id": thread, "checkpoint_ns": "prewritten",
                          "checkpoint_id": dirty.checkpoint_id}},
        [(CHANNEL, {"new_input_id": "I-dirty"})], "task-9",
    )
    with pytest.raises(ValueError, match="candidate namespace"):
        seal(saver, dirty, task, kind="normal", source=winner.ref,
             source_digest="source-digest")

    with pytest.raises(ValueError, match="immutable"):
        saver.put(
            {"configurable": {"thread_id": thread, "checkpoint_ns": "root-ns",
                              "checkpoint_id": root.checkpoint_id}},
            make_checkpoint(candidate_ref(task, "root-ns"),
                            {"new_input_id": "I-overwrite"}),
            {"step": 2}, {CHANNEL: 1},
        )
    with pytest.raises(ValueError, match="immutable"):
        saver.put_writes(
            {"configurable": {"thread_id": thread, "checkpoint_ns": "root-ns",
                              "checkpoint_id": root.checkpoint_id}},
            [(CHANNEL, {"new_input_id": "I-pending"})], "task-1",
        )
    kept = saver.get_tuple(exact_config(task, root))
    assert kept.checkpoint["channel_values"][CHANNEL]["new_input_id"] == "I-root"
    assert kept.pending_writes == []


def test_same_binding_reads_first_winner_across_retries_refs_and_publication(tmp_path):
    path = StoragePaths(tmp_path).application
    store, task = prepared_task(path)
    saver = store.checkpoint_saver("U1", "D1", "T1")
    first_ref = candidate_ref(task, "root-ns")
    first = seal(saver, first_ref, task, kind="root", state={"new_input_id": "I-first"})

    # Exact retry with different content still reads the persisted first winner.
    retried = seal(saver, first_ref, task, kind="root", state={"new_input_id": "I-second"})
    assert retried.ref == first_ref
    assert retried.checkpoint["channel_values"][CHANNEL]["new_input_id"] == "I-first"

    # 03 publishes this very ref through its task CAS; later G3 restarts must still
    # reach the first winner instead of tripping the "unpublished root" condition.
    store.update_task(
        "U1", "D1", "T1", 0, "R1", "running", first_ref.checkpoint_id,
        {"published_ref": {"checkpoint_ns": first_ref.checkpoint_ns,
                           "checkpoint_id": first_ref.checkpoint_id}},
    )
    after_publish = seal(saver, first_ref, task, kind="root",
                         state={"new_input_id": "I-third"})
    assert after_publish.checkpoint["channel_values"][CHANNEL]["new_input_id"] == "I-first"
    with pytest.raises(ValueError, match="immutable"):
        saver.put(
            {"configurable": {"thread_id": task.checkpoint_thread_id,
                              "checkpoint_ns": first_ref.checkpoint_ns,
                              "checkpoint_id": first_ref.checkpoint_id}},
            make_checkpoint(candidate_ref(task, first_ref.checkpoint_ns),
                            {"new_input_id": "I-published-overwrite"}),
            {"step": 2}, {CHANNEL: 1},
        )

    # A second pre-reserved ref for the same trusted transition is not a second winner.
    other_ref = candidate_ref(task, "root-other")
    alternate = seal(saver, other_ref, task, kind="root",
                     state={"new_input_id": "I-fourth"})
    assert alternate.ref == first_ref
    assert saver.get_tuple({"configurable": {
        "thread_id": task.checkpoint_thread_id, "checkpoint_ns": "root-other",
    }}) is None
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM checkpoint_seals").fetchone()[0] == 1


def test_concurrent_same_binding_seals_one_winner(tmp_path):
    path = StoragePaths(tmp_path).application
    store, task = prepared_task(path)
    saver = store.checkpoint_saver("U1", "D1", "T1")
    refs = [candidate_ref(task, "root-a"), candidate_ref(task, "root-b")]

    def prepare(ref):
        return seal(saver, ref, task, kind="root",
                    state={"new_input_id": ref.checkpoint_ns})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result() for future in [pool.submit(prepare, ref) for ref in refs]]

    assert results[0].ref == results[1].ref
    winner_namespace = results[0].ref.checkpoint_ns
    loser_namespace = "root-b" if winner_namespace == "root-a" else "root-a"
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM checkpoint_seals").fetchone()[0] == 1
    assert count(path, "checkpoints", loser_namespace) == 0


def test_conflicting_binding_on_reserved_ref_fails_without_touching_content(tmp_path):
    path = StoragePaths(tmp_path).application
    store, task = prepared_task(path)
    saver = store.checkpoint_saver("U1", "D1", "T1")
    root = candidate_ref(task, "root-ns")
    seal(saver, root, task, kind="root", state={"new_input_id": "I-first"})

    with pytest.raises(CandidateBindingConflictError) as conflict:
        seal(saver, root, task, kind="root", conversion_digest="request-2",
             state={"new_input_id": "I-conflict"})
    assert conflict.value.existing == root
    with pytest.raises(CandidateBindingConflictError):
        seal(saver, root, task, kind="root", accepted_version=3,
             state={"new_input_id": "I-conflict"})

    kept = saver.get_tuple(exact_config(task, root))
    assert kept.checkpoint["channel_values"][CHANNEL]["new_input_id"] == "I-first"
    assert count(path, "checkpoints", "root-ns") == 1
    assert count(path, "checkpoint_blobs", "root-ns") == 1
    assert count(path, "checkpoint_seals", "root-ns") == 1


def test_initial_root_requires_unpublished_task_and_no_predecessor(tmp_path):
    path = StoragePaths(tmp_path).application
    store, task = prepared_task(path)
    saver = store.checkpoint_saver("U1", "D1", "T1")

    # A task that already published a checkpoint cannot be treated as a new root,
    # even though it has no seal of its own yet.
    store.update_task("U1", "D1", "T1", 0, "R1", "running", "published-checkpoint",
                      {"published_ref": {"checkpoint_id": "published-checkpoint"}})
    with pytest.raises(ValueError, match="published"):
        seal(saver, candidate_ref(task, "root-ns"), task, kind="root")
    assert count(path, "checkpoint_seals", "root-ns") == 0

    # Existing thread history without a published pointer is an old task missing
    # its published id, not a new root either.
    store.create_task("T3", "U1", "S1", "D1", "R3", "running", {})
    old_task = store.get_task("U1", "D1", "T3")
    old_saver = store.checkpoint_saver("U1", "D1", "T3")
    legacy = candidate_ref(old_task, "legacy")
    old_saver.put(
        {"configurable": {"thread_id": old_task.checkpoint_thread_id,
                          "checkpoint_ns": "legacy"}},
        make_checkpoint(legacy, {"new_input_id": "I-old"}), {"step": 1}, {CHANNEL: 1},
    )
    with pytest.raises(ValueError, match="predecessor"):
        seal(old_saver, candidate_ref(old_task, "root-old"), old_task, kind="root")

    # A clean task seals one root; a different conversion association is a second
    # root (no predecessor allowed) and is refused, not sealed as a new winner.
    store.create_task("T2", "U1", "S1", "D1", "R2", "running", {})
    task = store.get_task("U1", "D1", "T2")
    saver = store.checkpoint_saver("U1", "D1", "T2")
    first = seal(saver, candidate_ref(task, "root-first"), task, kind="root")
    with pytest.raises(ValueError, match="predecessor"):
        seal(saver, candidate_ref(task, "root-second"), task, kind="root",
             conversion_digest="request-2")

    # The root is defined by the absence of edit/source bindings, not by silence.
    with pytest.raises(ValueError, match="no source"):
        seal(saver, candidate_ref(task, "root-sourced"), task, kind="root",
             source=first.ref, source_digest="source-digest")
    with pytest.raises(ValueError, match="source digest"):
        seal(saver, candidate_ref(task, "root-digest"), task, kind="root",
             source_digest="source-digest")
    with pytest.raises(ValueError, match="edit_ref"):
        seal(saver, candidate_ref(task, "root-edit"), task, kind="root",
             edit_ref="edit-1")


def test_normal_successor_requires_sealed_source_and_new_namespace(tmp_path):
    path = StoragePaths(tmp_path).application
    store, task = prepared_task(path)
    saver = store.checkpoint_saver("U1", "D1", "T1")
    root = candidate_ref(task, "root-ns")
    root_winner = seal(saver, root, task, kind="root", state={"new_input_id": "I-root"})

    with pytest.raises(ValueError, match="sealed source"):
        seal(saver, candidate_ref(task, "normal-no-source"), task, kind="normal",
             source_digest="source-digest", state={"new_input_id": "I-normal"})

    # A legacy (unsealed) checkpoint is not a protected source, only the exact
    # sealed candidate ref of the previous published state is.
    legacy = candidate_ref(task, "legacy")
    saver.put({"configurable": {"thread_id": task.checkpoint_thread_id,
                                "checkpoint_ns": "legacy"}},
              make_checkpoint(legacy, {"new_input_id": "I-legacy"}), {"step": 1},
              {CHANNEL: 1})
    with pytest.raises(ValueError, match="sealed candidate"):
        seal(saver, candidate_ref(task, "normal-legacy-source"), task, kind="normal",
             source=legacy, source_digest="source-digest")

    normal_ref = candidate_ref(task, "normal-ns")
    winner = seal(saver, normal_ref, task, kind="normal", source=root_winner.ref,
                  source_digest="source-digest", state={"new_input_id": "I-normal"})
    assert winner.source == root_winner.ref
    assert winner.edit_ref is None
    stored = saver.get_tuple(exact_config(task, normal_ref))
    assert stored.checkpoint["channel_values"][CHANNEL]["new_input_id"] == "I-normal"

    # Sharing the source namespace is not isolation even with a fresh UUID.
    with pytest.raises(ValueError, match="candidate namespace"):
        seal(saver, candidate_ref(task, "root-ns"), task, kind="normal",
             source=root_winner.ref, source_digest="source-digest",
             conversion_digest="request-3")
    # A normal successor never carries an edit request.
    with pytest.raises(ValueError, match="edit_ref"):
        seal(saver, candidate_ref(task, "normal-edit"), task, kind="normal",
             source=root_winner.ref, source_digest="source-digest", edit_ref="edit-1")
    # The full source ref is owned by this task/worktree thread.
    other_thread = CheckpointRef("another-thread", root.checkpoint_ns,
                                 root.checkpoint_id)
    with pytest.raises(ValueError, match="candidate thread"):
        seal(saver, candidate_ref(task, "normal-cross-thread"), task, kind="normal",
             source=other_thread, source_digest="source-digest")


def test_edit_candidate_requires_edit_ref_and_sealed_source(tmp_path):
    path = StoragePaths(tmp_path).application
    store, task = prepared_task(path)
    saver = store.checkpoint_saver("U1", "D1", "T1")
    root = candidate_ref(task, "root-ns")
    root_winner = seal(saver, root, task, kind="root", state={"new_input_id": "I-root"})

    with pytest.raises(ValueError, match="sealed source"):
        seal(saver, candidate_ref(task, "edit-no-source"), task, kind="edit",
             edit_ref="edit-1", state={"new_input_id": "I-edit"})
    with pytest.raises(ValueError, match="edit_ref"):
        seal(saver, candidate_ref(task, "edit-no-ref"), task, kind="edit",
             source=root_winner.ref, source_digest="source-digest")

    edit_ref = "edit-1"
    edit = candidate_ref(task, "edit-ns")
    winner = seal(saver, edit, task, kind="edit", source=root_winner.ref,
                  source_digest="source-digest", edit_ref=edit_ref,
                  state={"new_input_id": "I-edit"})
    assert winner.edit_ref == edit_ref
    assert winner.source == root_winner.ref
    assert saver.get_tuple(exact_config(task, edit)).checkpoint["channel_values"][
        CHANNEL]["new_input_id"] == "I-edit"

    # A second candidate ref prepared for the same edit still reads the first winner.
    duplicate = seal(saver, candidate_ref(task, "edit-other"), task, kind="edit",
                     source=root_winner.ref, source_digest="source-digest",
                     edit_ref=edit_ref, state={"new_input_id": "I-other"})
    assert duplicate.ref == edit
    assert saver.get_tuple({"configurable": {
        "thread_id": task.checkpoint_thread_id, "checkpoint_ns": "edit-other",
    }}) is None


def test_seal_keeps_task_scope_thread_owner_and_reserved_checkpoint_id(tmp_path):
    path = StoragePaths(tmp_path).application
    store, task = prepared_task(path)
    saver = store.checkpoint_saver("U1", "D1", "T1")
    candidate = candidate_ref(task, "root-ns")
    bindings = {
        "kind": "root", "candidate": candidate, "accepted_version": 0,
        "conversion_digest": "request-1",
        "checkpoint": make_checkpoint(candidate, {"new_input_id": "I1"}),
        "metadata": {"step": 1}, "new_versions": {CHANNEL: 1},
    }
    with pytest.raises(ValueError, match="not in scope"):
        saver.seal_candidate("U2", "D1", "T1", **bindings)
    with pytest.raises(ValueError, match="not in scope"):
        saver.seal_candidate("U1", "D2", "T1", **bindings)
    with pytest.raises(ValueError, match="not in scope"):
        saver.seal_candidate("U1", "D1", "missing-task", **bindings)

    other_thread = CheckpointRef("another-thread", "root-ns", candidate.checkpoint_id)
    with pytest.raises(ValueError, match="not in task scope"):
        saver.seal_candidate(
            "U1", "D1", "T1",
            **{**bindings, "candidate": other_thread,
               "checkpoint": make_checkpoint(other_thread, {"new_input_id": "I1"})},
        )

    # Content must be addressed to the pre-reserved ref id, not a fresh UUID.
    with pytest.raises(ValueError, match="checkpoint id"):
        saver.seal_candidate(
            "U1", "D1", "T1",
            **{**bindings, "checkpoint": make_checkpoint(
                candidate_ref(task, "root-ns"), {"new_input_id": "I1"})},
        )
    # The default namespace is the legacy latest-readable one, not a candidate.
    default_ref = CheckpointRef(task.checkpoint_thread_id, "", str(uuid4()))
    with pytest.raises(ValueError, match="isolated"):
        saver.seal_candidate(
            "U1", "D1", "T1",
            **{**bindings, "candidate": default_ref,
               "checkpoint": make_checkpoint(default_ref, {"new_input_id": "I1"})},
        )
    assert count(path, "checkpoint_seals", "root-ns") == 0


def test_sealed_winner_reads_back_with_metadata_and_writes_after_reopen(tmp_path):
    path = StoragePaths(tmp_path).application
    store, task = prepared_task(path)
    saver = store.checkpoint_saver("U1", "D1", "T1")
    root = candidate_ref(task, "root-ns")
    winner = seal(saver, root, task, kind="root", state={"new_input_id": "I-root"},
                  metadata={"source": "loop", "step": 7},
                  writes=[(CHANNEL, {"queued": True})], writes_task_id="task-1")
    assert winner.metadata["step"] == 7
    assert winner.metadata["source"] == "loop"
    assert winner.writes == (("task-1", CHANNEL, {"queued": True}),)
    assert len(winner.content_digest) == 64

    reopened = ApplicationStore(path)
    saver = reopened.checkpoint_saver("U1", "D1", "T1")
    stored = saver.get_tuple(exact_config(task, root))
    assert stored.checkpoint["channel_values"][CHANNEL]["new_input_id"] == "I-root"
    assert stored.pending_writes == [("task-1", CHANNEL, {"queued": True})]
    assert stored.metadata["step"] == 7

    retried = seal(saver, root, task, kind="root", state={"new_input_id": "I-other"})
    assert retried.checkpoint["channel_values"][CHANNEL]["new_input_id"] == "I-root"
    with pytest.raises(ValueError, match="immutable"):
        saver.put(
            {"configurable": {"thread_id": task.checkpoint_thread_id,
                              "checkpoint_ns": "root-ns",
                              "checkpoint_id": root.checkpoint_id}},
            make_checkpoint(candidate_ref(task, "root-ns"), {"new_input_id": "I-x"}),
            {"step": 2}, {CHANNEL: 1},
        )
    with pytest.raises(ValueError, match="immutable"):
        saver.put_writes(
            {"configurable": {"thread_id": task.checkpoint_thread_id,
                              "checkpoint_ns": "root-ns",
                              "checkpoint_id": root.checkpoint_id}},
            [(CHANNEL, {"new_input_id": "I-x"})], "task-1",
        )
    with pytest.raises(ValueError, match="sealed"):
        saver.delete_thread(task.checkpoint_thread_id)
    assert saver.get_tuple(exact_config(task, root)) is not None


def test_failed_seal_rolls_back_all_rows(tmp_path):
    path = StoragePaths(tmp_path).application
    store, task = prepared_task(path)
    saver = store.checkpoint_saver("U1", "D1", "T1")
    root = candidate_ref(task, "root-ns")
    root_winner = seal(saver, root, task, kind="root")

    rollback_ref = candidate_ref(task, "rollback-ns")
    checkpoint = {
        "v": 1, "id": rollback_ref.checkpoint_id, "ts": NOW,
        "channel_values": {"a_ok": {"new_input_id": "I1"}, "z_bad": lambda: None},
        "channel_versions": {"a_ok": 1, "z_bad": 2},
        "versions_seen": {}, "pending_sends": [],
    }
    with pytest.raises(TypeError):
        saver.seal_candidate(
            "U1", "D1", "T1", kind="normal", candidate=rollback_ref,
            accepted_version=0, conversion_digest="request-2",
            checkpoint=checkpoint, metadata={"step": 1},
            new_versions={"a_ok": 1, "z_bad": 2},
            source=root_winner.ref, source_digest="source-digest",
        )
    for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes",
                  "checkpoint_seals"):
        assert count(path, table, "rollback-ns") == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM checkpoint_seals").fetchone()[0] == 1
    assert saver.get_tuple(exact_config(task, rollback_ref)) is None


def test_application_v6_database_gains_seal_table_without_losing_state(tmp_path):
    path = StoragePaths(tmp_path).application
    store, task = prepared_task(path)
    saver = store.checkpoint_saver("U1", "D1", "T1")
    legacy = candidate_ref(task, "legacy")
    saver.put({"configurable": {"thread_id": task.checkpoint_thread_id,
                                "checkpoint_ns": "legacy"}},
              make_checkpoint(legacy, {"new_input_id": "I-legacy"}), {"step": 1},
              {CHANNEL: 1})
    store.create_task("T2", "U1", "S1", "D1", "R2", "running", {})
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE checkpoint_seals")
        connection.execute("PRAGMA user_version = 6")

    reopened = ApplicationStore(path)
    assert SCHEMA_VERSION == 7
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    saver = reopened.checkpoint_saver("U1", "D1", "T1")
    assert saver.get_tuple(exact_config(task, legacy)).checkpoint["channel_values"][
        CHANNEL]["new_input_id"] == "I-legacy"
    fresh_task = reopened.get_task("U1", "D1", "T2")
    winner = seal(reopened.checkpoint_saver("U1", "D1", "T2"),
                  candidate_ref(fresh_task, "root-ns"), fresh_task, kind="root")
    assert winner.checkpoint["channel_values"][CHANNEL]["new_input_id"] == "I1"


def test_sealing_does_not_freeze_legacy_namespace_flow(tmp_path):
    store, task = prepared_task(StoragePaths(tmp_path).application)
    saver = store.checkpoint_saver("U1", "D1", "T1")
    root = candidate_ref(task, "root-ns")
    seal(saver, root, task, kind="root", state={"new_input_id": "I-root"})

    # The ordinary LangGraph latest-namespace flow keeps working after sealing,
    # and its writes cannot leak into the sealed candidate.
    legacy = candidate_ref(task, "")
    saver.put(
        {"configurable": {"thread_id": task.checkpoint_thread_id}},
        make_checkpoint(legacy, {"new_input_id": "I-legacy"}), {"step": 1},
        {CHANNEL: 1},
    )
    latest = saver.get_tuple({"configurable": {
        "thread_id": task.checkpoint_thread_id}})
    assert latest.config["configurable"]["checkpoint_id"] == legacy.checkpoint_id
    assert latest.checkpoint["channel_values"][CHANNEL]["new_input_id"] == "I-legacy"
    assert saver.get_tuple(exact_config(task, root)).checkpoint["channel_values"][
        CHANNEL]["new_input_id"] == "I-root"
