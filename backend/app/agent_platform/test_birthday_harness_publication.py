"""Ticket v05-birthday-platform-dependencies/03: the real Harness publication path.

M1/M2 of the two-axis review: the platform seam must be reachable from the real
Harness, not only by calling ``publish_*`` directly. A new cross birthday task
goes through ``handle_message``/``resume`` with the publication saver adapter, so
the first state is a sealed root, every ordinary successor binds the previous
sealed published source and the default latest namespace stays untouched; the
birthday card's controlled edit option is then visible to the edit entry.

The entry-internal task writes (birthday attempts, the published edit option)
would otherwise make the pre-entry revision stale, so these tests also pin the
Harness result CAS to a re-read task: a stale revision must never surface as
TASK_CHANGED / DEPENDENCY_UNAVAILABLE.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext

from .test_birthday_edit_handoff import StandInCrossHandoff
from .test_birthday_runtime_wiring import (
    DELIVERY_REF, answer_verification, approve_confirmation, composition, option_id,
    trusted,
)

INTENT = "给妈妈过生日，安排花和蛋糕"
CHANNEL = "cross_state"


class HarnessEnvironment:
    def __init__(self, runtime, request_id, who):
        self.runtime = runtime
        self.request_id = request_id
        self.who = who
        self.resumes = 0

    def task(self):
        return self.runtime.application.get_task("U1", "D1", "BIRTHDAY")

    def snapshot(self) -> dict:
        return self.task().snapshot or {}

    def published_ref(self) -> dict:
        return self.snapshot()["birthday_g3"]["published_ref"]

    def start(self):
        return self.runtime.harness.handle_message(self.who, self.request_id, INTENT)

    def resume(self, response: dict, *, request_id=None):
        self.resumes += 1
        who = self.who.model_copy(update={"run_id": str(uuid4())})
        return self.runtime.harness.resume(
            who, response, request_id=request_id or uuid4())

    def saver(self):
        from app.memory.adapter import MemoryContext

        return self.runtime.memory.checkpointer(
            MemoryContext("U1", "S1", "D1"), "BIRTHDAY")


@pytest.fixture()
def harness_env(tmp_path):
    runtime, _entry = composition(tmp_path)
    who = trusted(runtime)
    request_id = uuid4()
    task = runtime.application.get_task("U1", "D1", "BIRTHDAY")
    runtime.application.update_task(
        "U1", "D1", "BIRTHDAY", task.revision, task.run_id, task.status,
        task.checkpoint_id,
        {
            **task.snapshot,
            "request_id": str(request_id),
            "intent_text": INTENT,
            "config_version": runtime.harness.planner.config_version,
            "proposal": {"capability_name": "cross.start_task"},
            "bill_source_task_id": None,
            "bill_scope": None,
            "selected_capability": None,
        },
    )
    env = HarnessEnvironment(runtime, request_id, who)
    try:
        yield env
    finally:
        runtime.gateway.close()


def drive_to_freeze_confirmation(env: HarnessEnvironment, current=None):
    if current is None:
        current = env.start()
    assert current.status is TaskStatus.WAITING_INPUT, current.message
    assert "预算" in current.message
    current = env.resume({"text": "500元"})
    assert current.status is TaskStatus.WAITING_INPUT, current.message
    assert "哪一天" in current.message
    current = env.resume({"text": "2026-10-30"})
    current = env.resume({"text": DELIVERY_REF})
    current = env.resume({"selected_option_id": option_id(current, "鲜花")})
    current = env.resume({"selected_option_id": option_id(current, "蛋糕")})
    current = env.resume({"selected_option_id": option_id(current, "就选这些")})
    current = env.resume(
        {"selected_option_id": option_id(current, "采用并开始办理")})
    assert current.status is TaskStatus.WAITING_APPROVAL, current.message
    assert current.interaction is not None and current.interaction.kind == "confirmation"
    return current


def test_harness_new_task_creates_and_publishes_the_root(tmp_path):
    """The real new-task path (planner proposal -> create_task -> entry.start)."""
    from unittest.mock import patch

    from app.agent_platform.model import TransferProposal

    runtime, _entry = composition(tmp_path)
    who = TrustedContext(user_id="U1", session_id="S1", task_id="HARNESS_NEW",
                         run_id="R1", parent_task_id=None, demo_round_id="D1")
    try:
        with patch.object(runtime.harness.planner, "select",
                          return_value=TransferProposal(
                              capability_name="cross.start_task")):
            result = runtime.harness.handle_message(who, uuid4(), INTENT)

        assert result.status is TaskStatus.WAITING_INPUT, result.message
        assert "预算" in result.message
        task = runtime.application.get_task("U1", "D1", "HARNESS_NEW")
        assert task.snapshot["capability_name"] == "cross.start_task"
        published = task.snapshot["birthday_g3"]["published_ref"]
        assert published["kind"] == "root"
        assert task.checkpoint_id == published["checkpoint_id"]
        from app.memory.adapter import MemoryContext

        saver = runtime.memory.checkpointer(
            MemoryContext("U1", "S1", "D1"), "HARNESS_NEW")
        assert saver.get_tuple({
            "configurable": {"thread_id": task.checkpoint_thread_id}}) is None
        sealed = saver.get_tuple({"configurable": {
            "thread_id": published["thread_id"],
            "checkpoint_ns": published["checkpoint_ns"],
            "checkpoint_id": published["checkpoint_id"]}})
        assert sealed is not None
        assert sealed.checkpoint["channel_values"][CHANNEL]["scenario"] == "birthday"
    finally:
        runtime.gateway.close()


def _seeded_task(runtime, task_id: str, intent: str):
    request_id = uuid4()
    runtime.application.create_task(
        task_id, "U1", "S1", "D1", "R1", TaskStatus.RUNNING,
        {
            "request_id": str(request_id),
            "intent_text": intent,
            "config_version": runtime.harness.planner.config_version,
            "proposal": {"capability_name": "cross.start_task"},
            "bill_source_task_id": None,
            "bill_scope": None,
            "selected_capability": None,
            "trace_id": str(uuid4()),
            "capability_name": "cross.start_task",
        },
    )
    who = TrustedContext(user_id="U1", session_id="S1", task_id=task_id,
                         run_id="R1", parent_task_id=None, demo_round_id="D1")
    return request_id, who


def test_harness_non_birthday_cross_goal_keeps_the_legacy_path(tmp_path):
    runtime, _entry = composition(tmp_path)
    intent = "养老金到了，帮我安排本月的钱"
    request_id, who = _seeded_task(runtime, "HARNESS_PENSION", intent)
    try:
        result = runtime.harness.handle_message(who, request_id, intent)
        assert result.status is TaskStatus.WAITING_INPUT, result.message
        task = runtime.application.get_task("U1", "D1", "HARNESS_PENSION")
        # Clearly another life goal is not intercepted: no G3 publication at all.
        assert "birthday_g3" not in task.snapshot
        assert "birthday_edit_option" not in task.snapshot
        assert task.checkpoint_id is not None
        from app.memory.adapter import MemoryContext

        saver = runtime.memory.checkpointer(
            MemoryContext("U1", "S1", "D1"), "HARNESS_PENSION")
        assert saver.get_tuple({
            "configurable": {"thread_id": task.checkpoint_thread_id}}) is not None
    finally:
        runtime.gateway.close()


def test_harness_clarification_root_then_birthday_successor(tmp_path):
    runtime, _entry = composition(tmp_path)
    intent = "帮我安排一下"  # ambiguous: Cross asks which life goal first
    request_id, who = _seeded_task(runtime, "HARNESS_CLARIFY", intent)
    try:
        started = runtime.harness.handle_message(who, request_id, intent)
        assert started.status is TaskStatus.WAITING_INPUT, started.message
        task = runtime.application.get_task("U1", "D1", "HARNESS_CLARIFY")
        root = task.snapshot["birthday_g3"]["published_ref"]
        assert root["kind"] == "root"
        birthday_option = option_id(started, "生日")

        chosen = runtime.harness.resume(
            who.model_copy(update={"run_id": str(uuid4())}),
            {"selected_option_id": birthday_option}, request_id=uuid4())

        assert chosen.status is TaskStatus.WAITING_INPUT, chosen.message
        assert "预算" in chosen.message
        task = runtime.application.get_task("U1", "D1", "HARNESS_CLARIFY")
        published = task.snapshot["birthday_g3"]["published_ref"]
        assert published["kind"] == "normal"
        assert published["checkpoint_id"] != root["checkpoint_id"]
        assert task.checkpoint_id == published["checkpoint_id"]
        # The clarification root stays sealed and readable as the predecessor.
        from app.memory.adapter import MemoryContext

        saver = runtime.memory.checkpointer(
            MemoryContext("U1", "S1", "D1"), "HARNESS_CLARIFY")
        predecessor = saver.get_tuple({"configurable": {
            "thread_id": root["thread_id"], "checkpoint_ns": root["checkpoint_ns"],
            "checkpoint_id": root["checkpoint_id"]}})
        assert predecessor is not None
        assert (predecessor.checkpoint["channel_values"][CHANNEL].get("scenario")
                is None)
        assert saver.get_tuple({
            "configurable": {"thread_id": task.checkpoint_thread_id}}) is None
    finally:
        runtime.gateway.close()


def test_harness_publishes_root_then_ordinary_states_and_reaches_the_edit_entry(
    harness_env,
):
    env = harness_env
    started = env.start()

    task = env.task()
    root = env.published_ref()
    assert root["kind"] == "root"
    assert task.checkpoint_id == root["checkpoint_id"]
    assert task.status is TaskStatus.WAITING_INPUT
    assert started.status is TaskStatus.WAITING_INPUT
    # No Cross state ever reached the default latest namespace.
    assert env.saver().get_tuple({
        "configurable": {"thread_id": task.checkpoint_thread_id}}) is None
    # The published root is the sealed content the entry wrote.
    sealed_root = env.saver().get_tuple({"configurable": {
        "thread_id": root["thread_id"], "checkpoint_ns": root["checkpoint_ns"],
        "checkpoint_id": root["checkpoint_id"]}})
    assert sealed_root is not None
    assert sealed_root.checkpoint["channel_values"][CHANNEL]["scenario"] == "birthday"

    current = drive_to_freeze_confirmation(env, started)

    task = env.task()
    published = env.published_ref()
    completed = env.snapshot()["birthday_g3"]["completed"]
    assert published["kind"] == "normal"
    assert task.checkpoint_id == published["checkpoint_id"]
    assert task.status is TaskStatus.WAITING_APPROVAL
    # Root first, then one ordinary successor per accepted F10 input; every one
    # of them is a published conversion of its own original request.
    assert [entry["kind"] for entry in completed] == (
        ["normal"] * 7 + ["root"])
    assert all(entry["conversion_digest"] for entry in completed)
    assert env.saver().get_tuple({
        "configurable": {"thread_id": task.checkpoint_thread_id}}) is None
    assert current.interaction.kind == "confirmation"
    # The controlled edit option was published on the real card.
    options = [item for item in current.interaction.options
               if item.label == "修改尚未提交的部分"]
    assert len(options) == 1
    assert env.runtime.birthday.handoff.is_published_edit_option(
        env.who, interaction_id=current.interaction.interaction_id,
        option_id=options[0].id)

    # With the explicit ticket-08 stand-in the edit entry enters the new input.
    env.runtime.birthday.handoff.cross = StandInCrossHandoff(
        env.runtime.gateway._bank.clock)
    outcome = env.runtime.birthday.handoff.begin_birthday_edit(
        env.who, request_id=uuid4(),
        interaction_id=current.interaction.interaction_id,
        option_id=options[0].id)
    assert outcome.result.status is TaskStatus.WAITING_INPUT
    assert outcome.result.interaction.kind == "input"
    assert env.task().revision == outcome.task_revision
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "edit"


def test_harness_verify_wait_and_edit_cards_use_a_fresh_revision(harness_env):
    env = harness_env
    current = drive_to_freeze_confirmation(env)
    task_before = env.task()
    approve_confirmation(env.runtime, env.who, current.interaction.record_ref)

    waiting = env.resume({"choice": "approve"})

    # The entry writes its task snapshot (attempt/option facts) inside the call;
    # the Harness result CAS must still succeed with a re-read revision.
    assert waiting.status is TaskStatus.WAITING_APPROVAL, waiting.message
    assert waiting.interaction.kind == "verification"
    task = env.task()
    assert task.revision > task_before.revision
    assert task.checkpoint_id == env.published_ref()["checkpoint_id"]
    published = env.published_ref()
    assert published["kind"] == "normal"
    assert env.snapshot()["result"]["status"] == "waiting_approval"
    verification_record = env.snapshot()["birthday_edit_option"]
    assert verification_record["interaction_id"] == waiting.interaction.interaction_id
    option = [item for item in waiting.interaction.options
              if item.label == "修改尚未提交的部分"]
    assert len(option) == 1

    # The edit card itself publishes through the accepted task revision.
    env.runtime.birthday.handoff.cross = StandInCrossHandoff(
        env.runtime.gateway._bank.clock)
    outcome = env.runtime.birthday.handoff.begin_birthday_edit(
        env.who, request_id=uuid4(),
        interaction_id=waiting.interaction.interaction_id,
        option_id=option[0].id)
    assert outcome.result.status is TaskStatus.WAITING_INPUT
    assert outcome.task_revision == env.task().revision
    assert env.snapshot()["birthday_edit"]["published"] is not None


def test_harness_ordinary_resume_does_not_replay_an_unpublished_conversion(
    harness_env,
):
    """A publish failure leaves no active state and a retry continues the same one."""
    env = harness_env
    current = env.start()
    assert env.published_ref()["kind"] == "root"
    original = env.runtime.application.update_task
    calls = {"count": 0}

    def failing(*args, **kwargs):
        calls["count"] += 1
        # reservation is first, publication is second within the transition
        if calls["count"] == 2:
            raise ValueError("task changed concurrently")
        return original(*args, **kwargs)

    from unittest.mock import patch

    request_id = uuid4()
    with patch.object(env.runtime.application, "update_task", failing):
        with pytest.raises(ValueError):
            env.resume({"text": "500元"}, request_id=request_id)
    # The reservation is durable, the publication is not: no new active state.
    assert env.published_ref()["kind"] == "root"
    assert env.snapshot()["birthday_g3"]["pending"] is not None
    assert env.task().checkpoint_id == env.published_ref()["checkpoint_id"]

    # The same original request retries along the accepted conversion.
    current = env.resume({"text": "500元"}, request_id=request_id)
    assert current.status is TaskStatus.WAITING_INPUT
    assert "哪一天" in current.message
    assert env.published_ref()["kind"] == "normal"
    assert env.snapshot()["birthday_g3"]["pending"] is None
