"""F10 resumes a durable G3 input after publication/receipt interruption."""

import json
from uuid import uuid4

from app.contracts.api import ProvideInputRequest
from app.memory.adapter import MemoryContext

from .store import ApiStore
from .test_edit_entry import _build_world, demo, started_world, stored_task, submit_inputs


def answer(world, request_id, interaction_id, text="500元"):
    return submit_inputs(world, request_id=request_id,
                         interaction_id=interaction_id, text=text)


def counts(world):
    return tuple(len(world.api.store.rows(f"SELECT * FROM {table}"))
                 for table in ("api_messages", "api_events"))


def test_original_input_recovers_after_its_task_publication_fails(
    started_world, monkeypatch,
):
    world = started_world
    request_id = uuid4()
    interaction_id = world.card.interaction.interaction_id
    publish = world.api.publish_task
    failed = False

    def interrupt_once(*args, **kwargs):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("task publication unavailable")
        return publish(*args, **kwargs)

    monkeypatch.setattr(world.api, "publish_task", interrupt_once)
    first = answer(world, request_id, interaction_id)
    assert first.status_code == 503
    completed = stored_task(world)
    assert completed.snapshot["birthday_g3"]["pending"] is None

    recovered = answer(world, request_id, interaction_id)
    assert recovered.status_code == 200, recovered.text
    assert "哪一天" in recovered.json()["data"]["message"]
    after_recovery = counts(world)
    assert answer(world, request_id, interaction_id).json() == recovered.json()
    assert counts(world) == after_recovery
    assert stored_task(world).revision == completed.revision


def test_lost_receipt_does_not_duplicate_the_input_history(
    started_world, monkeypatch,
):
    world = started_world
    request_id = uuid4()
    interaction_id = world.card.interaction.interaction_id
    finish = world.api.store.finish
    failed = False

    def interrupt_once(identity, endpoint, received_id, response):
        nonlocal failed
        if endpoint.endswith("/inputs") and not failed:
            failed = True
            raise OSError("receipt unavailable")
        return finish(identity, endpoint, received_id, response)

    monkeypatch.setattr(world.api.store, "finish", interrupt_once)
    first = answer(world, request_id, interaction_id)
    assert first.status_code == 503
    completed = stored_task(world)
    before_recovery = counts(world)

    recovered = answer(world, request_id, interaction_id)
    assert recovered.status_code == 200, recovered.text
    assert counts(world) == before_recovery
    assert stored_task(world).revision == completed.revision


def test_recovery_still_rejects_changed_parameters(started_world, monkeypatch):
    world = started_world
    request_id = uuid4()
    interaction_id = world.card.interaction.interaction_id
    publish = world.api.publish_task

    def unavailable(*args, **kwargs):
        raise OSError("task publication unavailable")

    monkeypatch.setattr(world.api, "publish_task", unavailable)
    assert answer(world, request_id, interaction_id).status_code == 503
    monkeypatch.setattr(world.api, "publish_task", publish)
    before = stored_task(world)
    changed = answer(world, request_id, interaction_id, "600元")
    assert changed.status_code == 409, changed.text
    assert changed.json()["error"]["code"] == "REQUEST_CONFLICT"
    assert stored_task(world).revision == before.revision


def test_original_input_resumes_its_pending_seal(started_world, monkeypatch):
    world = started_world
    request_id = uuid4()
    interaction_id = world.card.interaction.interaction_id
    saver_type = type(world.runtime.memory.checkpointer(
        MemoryContext(world.who.user_id, world.who.session_id,
                      world.who.demo_round_id), world.task_id,
    ))
    seal = saver_type.seal_candidate
    failed = False

    def interrupt_once(saver, *args, **kwargs):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("sealed storage unavailable")
        return seal(saver, *args, **kwargs)

    monkeypatch.setattr(saver_type, "seal_candidate", interrupt_once)
    first = answer(world, request_id, interaction_id)
    assert first.status_code == 503, first.text
    assert stored_task(world).snapshot["birthday_g3"]["pending"] is not None

    recovered = answer(world, request_id, interaction_id)
    assert recovered.status_code == 200, recovered.text
    assert "哪一天" in recovered.json()["data"]["message"]
    assert stored_task(world).snapshot["birthday_g3"]["pending"] is None


def test_old_input_returns_its_winner_without_republishing_old_state(
    started_world, monkeypatch,
):
    world = started_world
    request_id = uuid4()
    interaction_id = world.card.interaction.interaction_id
    publish = world.api.publish_task
    failed = False

    def interrupt_once(*args, **kwargs):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("task publication unavailable")
        return publish(*args, **kwargs)

    monkeypatch.setattr(world.api, "publish_task", interrupt_once)
    assert answer(world, request_id, interaction_id).status_code == 503
    original = stored_task(world)
    next_id = original.snapshot["result"]["interaction"]["interaction_id"]
    later = answer(world, uuid4(), next_id, "2026-10-30")
    assert later.status_code == 200, later.text
    current = stored_task(world)
    before_recovery = counts(world)

    recovered = answer(world, request_id, interaction_id)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["data"]["task_revision"] == original.revision
    assert "哪一天" in recovered.json()["data"]["message"]
    assert stored_task(world).revision == current.revision
    assert counts(world) == before_recovery


def test_unaccepted_input_receipt_is_not_replayed(started_world):
    world = started_world
    request_id = uuid4()
    interaction_id = world.card.interaction.interaction_id
    identity = world.api.identity(world.api.cookie(world.who.session_id))
    request = ProvideInputRequest(request_id=request_id,
                                 interaction_id=interaction_id, text="500元")
    world.api.store.receipt(identity,
                            f"/api/v1/tasks/{world.task_id}/inputs",
                            request_id, request)
    before = stored_task(world)

    response = answer(world, request_id, interaction_id)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "REQUEST_IN_PROGRESS"
    assert stored_task(world).revision == before.revision


def test_input_completion_survives_reopening_the_api_store(
    started_world, monkeypatch,
):
    world = started_world
    request_id = uuid4()
    interaction_id = world.card.interaction.interaction_id
    publish = world.api.publish_task

    def unavailable(*args, **kwargs):
        raise OSError("task publication unavailable")

    monkeypatch.setattr(world.api, "publish_task", unavailable)
    assert answer(world, request_id, interaction_id).status_code == 503
    old_store = world.api.store
    world.api.store = ApiStore(old_store.path, old_store.secret)
    monkeypatch.setattr(world.api, "publish_task", publish)

    recovered = answer(world, request_id, interaction_id)
    assert recovered.status_code == 200, recovered.text
    assert "哪一天" in recovered.json()["data"]["message"]


def test_completion_save_failure_still_recovers_the_older_platform_winner(
    started_world, monkeypatch,
):
    world = started_world
    request_id = uuid4()
    interaction_id = world.card.interaction.interaction_id
    save = world.api.store.save_input_completion
    failed = False

    def interrupt_once(*args, **kwargs):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("completion view unavailable")
        return save(*args, **kwargs)

    monkeypatch.setattr(world.api.store, "save_input_completion", interrupt_once)
    assert answer(world, request_id, interaction_id).status_code == 503
    original = world.runtime.birthday.handoff.find_input_conversion(world.who, request_id)
    next_id = stored_task(world).snapshot["result"]["interaction"]["interaction_id"]
    assert answer(world, uuid4(), next_id, "2026-10-30").status_code == 200
    current = stored_task(world)
    before_recovery = counts(world)

    recovered = answer(world, request_id, interaction_id)
    assert recovered.status_code == 200, recovered.text
    view = recovered.json()["data"]
    assert view["task_revision"] == original.task_revision
    assert view["message"] == original.result.message
    assert view["data"] == original.result.model_dump(mode="json")["data"]
    assert stored_task(world).revision == current.revision
    assert counts(world) == before_recovery


def test_distinct_tasks_can_reuse_the_same_request_id_without_losing_history(demo):
    worlds = [_build_world(demo, stage="start"), _build_world(demo, stage="start")]
    request_id = uuid4()
    for world in worlds:
        world.client.cookies.set("bank_session", world.api.cookie(world.who.session_id))
        response = answer(world, request_id, world.card.interaction.interaction_id)
        assert response.status_code == 200, response.text
        messages = world.api.store.rows(
            "SELECT view_json FROM api_messages WHERE thread_id=?", (world.thread_id,),
        )
        events = world.api.store.rows(
            "SELECT event_json FROM api_events WHERE thread_id=?", (world.thread_id,),
        )
        assert any(world.task_id in json.loads(row["view_json"])["task_ids"]
                   for row in messages)
        assert any(json.loads(row["event_json"])["task_id"] == world.task_id
                   for row in events)
