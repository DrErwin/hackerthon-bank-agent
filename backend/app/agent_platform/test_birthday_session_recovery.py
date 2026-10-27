"""Ticket 10: owned G3 recovery uses its sealed source, never latest state.

Planner output is the existing explicit test proposal; Harness, Cross,
checkpoints, confirmation, verification and bank are the real local composition.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.contracts.common import TaskStatus
from app.memory.adapter import MemoryContext

from .birthday_edit import BirthdayEditError
from .test_birthday_harness_publication import (
    drive_to_freeze_confirmation, harness_env,
)
from .test_birthday_runtime_wiring import approve_confirmation
from .test_cross_runtime_wiring import submitted_ledger_count


def target_session(env, session_id="S2", *, user_id="U1", round_id="D1"):
    now = datetime.now(timezone.utc)
    env.runtime.application.create_session(
        session_id, user_id, round_id, now.isoformat(),
        (now + timedelta(days=1)).isoformat())
    return env.who.model_copy(update={
        "session_id": session_id, "user_id": user_id,
        "demo_round_id": round_id, "run_id": str(uuid4()),
    })


def test_g3_recovery_publishes_a_new_session_from_the_exact_source(harness_env):
    env = harness_env
    started = env.start()
    source = env.published_ref()
    saved = env.saver().get_tuple({"configurable": {
        "thread_id": source["thread_id"],
        "checkpoint_ns": source["checkpoint_ns"],
        "checkpoint_id": source["checkpoint_id"],
    }})
    caller = target_session(env)

    recovered = env.runtime.harness.recover_session(caller)

    assert recovered.status is TaskStatus.WAITING_INPUT
    assert recovered.interaction.interaction_id != started.interaction.interaction_id
    assert env.task().session_id == "S2"
    assert env.snapshot()["session_recovery"]["phase"] == "complete"
    published = env.published_ref()
    assert published["checkpoint_id"] != source["checkpoint_id"]
    assert env.task().checkpoint_id == published["checkpoint_id"]
    saver = env.runtime.memory.checkpointer(MemoryContext("U1", "S2", "D1"), "BIRTHDAY")
    assert saver.get_tuple({"configurable": {"thread_id": source["thread_id"]}}) is None
    old = saver.get_tuple({"configurable": {
        "thread_id": source["thread_id"], "checkpoint_ns": source["checkpoint_ns"],
        "checkpoint_id": source["checkpoint_id"],
    }})
    assert old.checkpoint == saved.checkpoint
    assert old.checkpoint["channel_values"]["cross_state"]["session_id"] == "S1"
    continued = env.runtime.harness.resume(
        caller.model_copy(update={"run_id": str(uuid4())}),
        {"text": "500元"}, request_id=uuid4())
    assert continued.status is TaskStatus.WAITING_INPUT
    assert "哪一天" in continued.message
    assert submitted_ledger_count(env.runtime) == 0
    with pytest.raises(PermissionError, match="ACCESS_DENIED"):
        env.runtime.harness.resume(env.who, {"text": "600元"}, request_id=uuid4())


@pytest.mark.parametrize("verification", [False, True])
def test_g3_provider_refuses_a_cached_old_session_sensitive_card(
    harness_env, verification, monkeypatch,
):
    env = harness_env
    current = drive_to_freeze_confirmation(env)
    old_confirmation = current.interaction.record_ref
    if verification:
        approve_confirmation(env.runtime, env.who, old_confirmation)
        current = env.resume({"choice": "approve"})
        assert current.interaction.kind == "verification"
    old_interaction = current.interaction.interaction_id
    caller = target_session(env)
    published = env.published_ref()
    from app.modules.cross.entry import CrossEntry

    # Explicit faulty consumer: a stale card must never become current-session
    # authority, even after the separate Cross recovery fix is delivered.
    def stale_card(_entry, trusted, *, source_session_id, thread_id=None):
        return current.model_copy(update={"run_id": trusted.run_id})

    monkeypatch.setattr(CrossEntry, "recover_session", stale_card)

    with pytest.raises(BirthdayEditError, match="DEPENDENCY_UNAVAILABLE"):
        env.runtime.harness.recover_session(caller)

    assert env.task().session_id == "S2"
    assert env.snapshot()["session_recovery"]["phase"] == "transitioned"
    assert env.published_ref() == published
    assert env.snapshot()["result"]["interaction"]["interaction_id"] == old_interaction
    assert submitted_ledger_count(env.runtime) == 0


@pytest.mark.parametrize("user_id,round_id", [("U2", "D1"), ("U1", "D2")])
def test_g3_recovery_rejects_foreign_ownership_before_moving(harness_env, user_id, round_id):
    env = harness_env
    env.start()
    before = env.task()
    caller = target_session(env, user_id=user_id, round_id=round_id)

    expected = ValueError if round_id != "D1" else PermissionError
    with pytest.raises(expected):
        env.runtime.harness.recover_session(caller)

    assert env.task() == before


def test_exact_input_conversion_query_does_not_accept_another_request(harness_env):
    env = harness_env
    env.start()
    request_id = uuid4()
    handoff = env.runtime.birthday.handoff
    assert handoff.find_input_conversion(env.who, request_id) is None

    result = env.resume({"text": "500元"}, request_id=request_id)
    publication = handoff.find_input_conversion(env.who, request_id)
    assert publication.result.interaction.interaction_id == result.interaction.interaction_id
    revision = publication.task_revision
    env.resume({"text": "2026-10-30"})
    before = env.task()

    publication = handoff.find_input_conversion(env.who, request_id)
    assert publication.task_revision == revision < env.task().revision
    assert publication.result.interaction.interaction_id == result.interaction.interaction_id
    assert handoff.find_input_conversion(env.who, uuid4()) is None
    assert env.task() == before


def test_g3_recovery_retries_its_own_unpublished_winner(harness_env, monkeypatch):
    env = harness_env
    env.start()
    handoff = env.runtime.birthday.handoff
    publish = handoff._publish_successor
    failures = 0

    def interrupt(*args, **kwargs):
        nonlocal failures
        if failures == 0:
            failures += 1
            raise BirthdayEditError("PUBLISH_CONFLICT", "simulated before publication")
        return publish(*args, **kwargs)

    monkeypatch.setattr(handoff, "_publish_successor", interrupt)
    caller = target_session(env)
    with pytest.raises(BirthdayEditError, match="PUBLISH_CONFLICT"):
        env.runtime.harness.recover_session(caller)
    pending = env.snapshot()["birthday_g3"]["pending"]
    candidate = pending["candidate"]

    recovered = env.runtime.harness.recover_session(
        caller.model_copy(update={"run_id": str(uuid4())}))

    assert recovered.status is TaskStatus.WAITING_INPUT
    assert env.published_ref()["checkpoint_id"] == candidate["checkpoint_id"]
    assert env.snapshot()["birthday_g3"]["pending"] is None
    assert env.snapshot()["session_recovery"]["phase"] == "complete"
    assert submitted_ledger_count(env.runtime) == 0


def test_completed_session_recovery_never_rolls_back_a_later_input(harness_env):
    env = harness_env
    env.start()
    caller = target_session(env)
    env.runtime.harness.recover_session(caller)
    latest = env.runtime.harness.resume(
        caller.model_copy(update={"run_id": str(uuid4())}),
        {"text": "500元"}, request_id=uuid4())
    task = env.task()

    replay = env.runtime.harness.recover_session(
        caller.model_copy(update={"run_id": str(uuid4())}))

    assert replay.interaction.interaction_id == latest.interaction.interaction_id
    assert "哪一天" in replay.message
    assert env.task() == task


def test_input_conversion_query_distinguishes_pending_from_published(
    harness_env, monkeypatch,
):
    env = harness_env
    env.start()
    handoff = env.runtime.birthday.handoff
    publish = handoff._publish_successor

    def interrupt(*args, **kwargs):
        raise BirthdayEditError("PUBLISH_CONFLICT", "simulated lost publication")

    monkeypatch.setattr(handoff, "_publish_successor", interrupt)
    request_id = uuid4()
    with pytest.raises(BirthdayEditError, match="PUBLISH_CONFLICT"):
        env.resume({"text": "500元"}, request_id=request_id)
    before = env.task()
    assert handoff.find_input_conversion(env.who, request_id) == "pending"
    assert handoff.find_input_conversion(env.who, uuid4()) is None
    assert env.task() == before

    monkeypatch.setattr(handoff, "_publish_successor", publish)
    result = env.resume({"text": "500元"}, request_id=request_id)
    publication = handoff.find_input_conversion(env.who, request_id)
    assert publication.result.interaction.interaction_id == result.interaction.interaction_id
    assert publication.task_revision == env.published_ref()["task_revision"]


def test_g3_recovery_replays_publication_after_lost_completion(harness_env, monkeypatch):
    env = harness_env
    env.start()
    update_task = env.runtime.application.update_task
    failures = 0

    def interrupt(*args, **kwargs):
        nonlocal failures
        snapshot = args[7] if len(args) > 7 else kwargs["snapshot"]
        if (snapshot.get("session_recovery") or {}).get("phase") == "complete" and failures == 0:
            failures += 1
            raise RuntimeError("simulated lost completion")
        return update_task(*args, **kwargs)

    monkeypatch.setattr(env.runtime.application, "update_task", interrupt)
    caller = target_session(env)
    with pytest.raises(RuntimeError, match="lost completion"):
        env.runtime.harness.recover_session(caller)
    published = env.published_ref()
    assert env.snapshot()["session_recovery"]["phase"] == "transitioned"

    recovered = env.runtime.harness.recover_session(
        caller.model_copy(update={"run_id": str(uuid4())}))

    assert recovered.status is TaskStatus.WAITING_INPUT
    assert env.published_ref() == published
    assert env.snapshot()["session_recovery"]["phase"] == "complete"
    assert submitted_ledger_count(env.runtime) == 0


def test_g3_recovery_rejects_an_unrelated_pending_conversion(harness_env):
    env = harness_env
    env.start()
    task = env.task()
    snapshot = {**task.snapshot, "birthday_g3": {
        **task.snapshot["birthday_g3"],
        "pending": {"conversion_digest": "different-accepted-input"},
    }}
    env.runtime.application.update_task(
        "U1", "D1", "BIRTHDAY", task.revision, task.run_id,
        task.status, task.checkpoint_id, snapshot)
    before = env.task()

    with pytest.raises(BirthdayEditError, match="TRANSITION_PENDING"):
        env.runtime.harness.recover_session(target_session(env))

    assert env.task() == before

