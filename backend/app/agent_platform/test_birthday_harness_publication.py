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

Controlled substitutes only: the *planner* is a stub returning one
``TransferProposal`` in the new-task test, and two tests temporarily wrap the
registered cross factory to remove the birthday execution ports (a real Cross
failure result) or fail one ticket-05 seal call. Everything else (Harness,
stores, security, bank, Cross flow) is the real composition.
"""

from uuid import UUID, uuid4

import pytest

from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext

from .birthday_edit import BirthdayEditError
from .test_birthday_edit_handoff import StandInCrossHandoff
from .test_birthday_runtime_wiring import (
    DELIVER_DATE, DELIVERY_REF, answer_verification, approve_confirmation, composition, option_id,
    trusted,
)

INTENT = "给妈妈过生日，安排花和蛋糕"
CHANNEL = "cross_state"
_UNSET = object()


class HarnessEnvironment:
    def __init__(self, runtime, request_id, who):
        self.runtime = runtime
        self.request_id = request_id
        self.who = who
        self.resumes = 0
        self.last_run_id = who.run_id

    def task(self):
        return self.runtime.application.get_task("U1", "D1", "BIRTHDAY")

    def snapshot(self) -> dict:
        return self.task().snapshot or {}

    def published_ref(self) -> dict:
        return self.snapshot()["birthday_g3"]["published_ref"]

    def start(self):
        return self.runtime.harness.handle_message(self.who, self.request_id, INTENT)

    def resume(self, response: dict, *, request_id=_UNSET):
        self.resumes += 1
        who = self.who.model_copy(update={"run_id": str(uuid4())})
        self.last_run_id = who.run_id
        return self.runtime.harness.resume(
            who, response,
            request_id=uuid4() if request_id is _UNSET else request_id)

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
    current = env.resume({"text": DELIVER_DATE})
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


def _remove_birthday_ports(runtime) -> None:
    """Make the real Cross birthday advance return its real FAILED result.

    The registered entry keeps its real code path; without the platform birthday
    ports it returns the documented "execution seam not assembled" failure, which
    is a genuine non-publishable first/normal state for N1.
    """
    from dataclasses import replace

    registry = runtime.harness.registry
    registration = registry._entries["cross.start_task"]

    def factory(trusted_context, saver, trace):
        entry = registration.factory(trusted_context, saver, trace)
        entry.birthday_ports_factory = None
        return entry

    registry._entries["cross.start_task"] = replace(registration, factory=factory)


def _fail_next_seal(runtime):
    """Behavioral fault injection: the ticket-05 seal is unavailable once."""
    from unittest.mock import patch

    original = runtime.memory.checkpointer
    state = {"once": True}

    class FailingSealSaver:
        def __init__(self, inner):
            self._inner = inner
            self.thread_id = getattr(inner, "thread_id", None)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def seal_candidate(self, *args, **kwargs):
            if state["once"]:
                state["once"] = False
                raise ValueError("sealed storage unavailable")
            return self._inner.seal_candidate(*args, **kwargs)

    def factory(context, task_id):
        return FailingSealSaver(original(context, task_id))

    return patch.object(runtime.memory, "checkpointer", side_effect=factory)


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


def test_harness_keeps_a_failed_first_result_when_g3_publication_is_skipped(
    tmp_path,
):
    """N1: a non-publishable first state still reaches the task result."""
    runtime, _entry = composition(tmp_path)
    _remove_birthday_ports(runtime)
    request_id, who = _seeded_task(runtime, "HARNESS_ROOT_FAIL", INTENT)
    try:
        result = runtime.harness.handle_message(who, request_id, INTENT)

        # The real Cross failure result is kept; the task is NOT left without a
        # result and no fake/sealed root is exposed.
        assert result.status is TaskStatus.FAILED, result.message
        task = runtime.application.get_task("U1", "D1", "HARNESS_ROOT_FAIL")
        assert task.snapshot["result"]["status"] == "failed"
        assert "birthday_g3" not in task.snapshot
        assert task.checkpoint_id is None
        stored = runtime.harness.get(who)
        assert stored.status is TaskStatus.FAILED
        from app.memory.adapter import MemoryContext

        saver = runtime.memory.checkpointer(
            MemoryContext("U1", "S1", "D1"), "HARNESS_ROOT_FAIL")
        assert saver.get_tuple({
            "configurable": {"thread_id": task.checkpoint_thread_id}}) is None
    finally:
        runtime.gateway.close()


def test_harness_clarification_then_birthday_failure_is_a_normal_successor(
    tmp_path,
):
    """N1: the second (birthday) conversion publishes its real failure result."""
    runtime, _entry = composition(tmp_path)
    intent = "帮我安排一下"
    request_id, who = _seeded_task(runtime, "HARNESS_CLARIFY_FAIL", intent)
    try:
        started = runtime.harness.handle_message(who, request_id, intent)
        assert started.status is TaskStatus.WAITING_INPUT, started.message
        root = runtime.application.get_task(
            "U1", "D1", "HARNESS_CLARIFY_FAIL").snapshot["birthday_g3"][
                "published_ref"]
        assert root["kind"] == "root"

        _remove_birthday_ports(runtime)
        chosen = runtime.harness.resume(
            who.model_copy(update={"run_id": str(uuid4())}),
            {"selected_option_id": option_id(started, "生日")},
            request_id=uuid4())

        assert chosen.status is TaskStatus.FAILED, chosen.message
        task = runtime.application.get_task("U1", "D1", "HARNESS_CLARIFY_FAIL")
        assert task.snapshot["result"]["status"] == "failed"
        published = task.snapshot["birthday_g3"]["published_ref"]
        assert published["kind"] == "normal"
        assert published["checkpoint_id"] != root["checkpoint_id"]
        assert task.checkpoint_id == published["checkpoint_id"]
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


def _paid_amounts(runtime) -> set[int]:
    ledger = runtime.gateway._bank.store.list_ledger("U1", "A1")
    return {row["amount_fen"] for row in ledger
            if row["nature"] == "consumption"
            and not row["operation_id"].startswith("seed:")}


def drive_until_flower_is_paid(env: HarnessEnvironment, current):
    """Settle the flute until the second (cake) confirmation is waiting."""
    for _ in range(20):
        if current.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED,
                              TaskStatus.CANCELLED,
                              TaskStatus.PARTIALLY_SUCCEEDED}:
            return current
        interaction = current.interaction
        if interaction is None:
            current = env.resume({})
        elif interaction.kind == "confirmation":
            if _paid_amounts(env.runtime) == {19900}:
                return current  # the settled flower is paid; this is the cake
            approve_confirmation(env.runtime, env.who, interaction.record_ref)
            current = env.resume({"choice": "approve"})
        else:
            answer_verification(env.runtime, env.who, "R1",
                                interaction.record_ref)
            current = env.resume({"choice": "resume"})
    return current


def test_harness_partially_succeeded_resume_returns_the_published_result(
    harness_env,
):
    """M5: a partial-success refresh returns history and opens no conversion."""
    env = harness_env
    current = drive_to_freeze_confirmation(env)
    card = drive_until_flower_is_paid(env, current)
    assert _paid_amounts(env.runtime) == {19900}

    stopped = env.resume({"cancel": True})

    assert stopped.status is TaskStatus.PARTIALLY_SUCCEEDED, stopped.message
    task = env.task()
    assert task.status is TaskStatus.PARTIALLY_SUCCEEDED
    published = env.published_ref()
    revision = task.revision
    completed = len(env.snapshot()["birthday_g3"]["completed"])

    # B04 refresh/continue: the published historical result comes back unchanged;
    # no new conversion is reserved/published and no CANDIDATE_INVALID surfaces.
    refreshed = env.resume({})

    assert refreshed.status is TaskStatus.PARTIALLY_SUCCEEDED
    assert refreshed.task_id == stopped.task_id
    assert refreshed.message == stopped.message
    assert env.published_ref() == published
    assert env.task().revision == revision
    assert len(env.snapshot()["birthday_g3"]["completed"]) == completed
    assert env.snapshot()["birthday_g3"]["pending"] is None


def test_harness_ordinary_resume_does_not_replay_an_unpublished_conversion(
    harness_env,
):
    """A seal failure leaves no active state; the same F10 request retries it."""
    env = harness_env
    env.start()
    assert env.published_ref()["kind"] == "root"

    request_id = uuid4()
    with _fail_next_seal(env.runtime):
        with pytest.raises(ValueError):
            env.resume({"text": "500元"}, request_id=request_id)
    # The reservation is durable, the publication is not: no new active state.
    assert env.published_ref()["kind"] == "root"
    assert env.snapshot()["birthday_g3"]["pending"] is not None
    assert env.task().checkpoint_id == env.published_ref()["checkpoint_id"]

    current = env.resume({"text": "500元"}, request_id=request_id)
    assert current.status is TaskStatus.WAITING_INPUT
    assert "哪一天" in current.message
    assert env.published_ref()["kind"] == "normal"
    assert env.snapshot()["birthday_g3"]["pending"] is None


def test_harness_answer_identity_without_request_id_survives_a_retry(
    harness_env,
):
    """N2: with no F10 request id the current card + answer identify the retry."""
    env = harness_env
    env.start()

    with _fail_next_seal(env.runtime):
        with pytest.raises(ValueError):
            env.resume({"text": "500元"}, request_id=None)
    pending = env.snapshot()["birthday_g3"]["pending"]
    assert pending is not None
    first_conversion = pending["association"]

    # Same answer, different run id, still no request_id: one conversion.
    current = env.resume({"text": "500元"}, request_id=None)

    assert current.status is TaskStatus.WAITING_INPUT
    assert "哪一天" in current.message
    assert env.published_ref()["kind"] == "normal"
    assert env.snapshot()["birthday_g3"]["pending"] is None
    completed = env.snapshot()["birthday_g3"]["completed"][0]
    assert completed["conversion_digest"] == pending["conversion_digest"]
    # The identity is the card + accepted revision + answer, not the run id.
    assert first_conversion["kind"] == "input"
    assert first_conversion["interaction_id"]
    assert first_conversion["accepted_version"] >= 0
    assert first_conversion["answer_digest"]
    assert "request_id" not in first_conversion


def test_harness_different_answer_without_request_id_is_still_refused(
    harness_env,
):
    """N2: an unpublished conversion cannot be crossed by a different answer."""
    env = harness_env
    env.start()
    with _fail_next_seal(env.runtime):
        with pytest.raises(ValueError):
            env.resume({"text": "500元"}, request_id=None)
    assert env.snapshot()["birthday_g3"]["pending"] is not None

    with pytest.raises(BirthdayEditError) as conflict:
        env.resume({"text": "800元"}, request_id=None)
    assert conflict.value.code == "TRANSITION_PENDING"
    # Nothing was published or overwritten by the competing answer.
    assert env.published_ref()["kind"] == "root"
    assert env.snapshot()["birthday_g3"]["pending"] is not None


def test_harness_replays_a_published_conversion_with_the_current_run_id(
    harness_env,
):
    env = harness_env
    env.start()
    request_id = uuid4()
    first = env.resume({"text": "500元"}, request_id=request_id)
    published = env.published_ref()
    revision = env.task().revision

    replay = env.resume({"text": "500元"}, request_id=request_id)

    assert replay.status is first.status
    assert replay.interaction.interaction_id == first.interaction.interaction_id
    # The per-run identity is rebound; the published result/content is untouched.
    assert replay.run_id == env.last_run_id
    assert env.published_ref() == published
    assert env.task().revision == revision


def test_harness_cross_session_recovery_refuses_a_missing_g3_source(tmp_path):
    """R1: an unprovable G3 source refuses before any migration."""
    from datetime import datetime, timedelta, timezone

    runtime, _entry = composition(tmp_path)
    request_id, who = _seeded_task(runtime, "HARNESS_RECOVER", INTENT)
    try:
        started = runtime.harness.handle_message(who, request_id, INTENT)
        assert started.status is TaskStatus.WAITING_INPUT, started.message
        task = runtime.application.get_task("U1", "D1", "HARNESS_RECOVER")
        published = {**task.snapshot["birthday_g3"]["published_ref"],
                     "checkpoint_id": str(uuid4())}
        task = runtime.application.update_task(
            "U1", "D1", "HARNESS_RECOVER", task.revision, task.run_id,
            task.status, task.checkpoint_id,
            {**task.snapshot, "birthday_g3": {
                **task.snapshot["birthday_g3"], "published_ref": published}})
        completed = len(task.snapshot["birthday_g3"]["completed"])
        result_before = task.snapshot["result"]
        thread_id = task.checkpoint_thread_id

        now = datetime.now(timezone.utc)
        runtime.application.create_session(
            "S2", "U1", "D1", now.isoformat(),
            (now + timedelta(days=1)).isoformat())
        stranger = TrustedContext(
            user_id="U1", session_id="S2", task_id="HARNESS_RECOVER",
            run_id=str(uuid4()), parent_task_id=None, demo_round_id="D1")

        # A missing immutable source fails explicitly and returns no old card.
        with pytest.raises(BirthdayEditError) as refused:
            returned = runtime.harness.recover_session(stranger)
            assert returned is not None  # never reached
        assert str(refused.value) == "SOURCE_UNAVAILABLE"
        # The ordinary same-session contract is unchanged (no recovery needed).
        with pytest.raises(ValueError, match="SESSION_RECOVERY_NOT_REQUIRED"):
            runtime.harness.recover_session(who)

        # No migration and no completion marker were written before the refusal.
        current = runtime.application.get_task("U1", "D1", "HARNESS_RECOVER")
        assert current.session_id == "S1"
        assert "session_recovery" not in current.snapshot
        assert current.snapshot["birthday_g3"]["published_ref"] == published
        assert len(current.snapshot["birthday_g3"]["completed"]) == completed
        assert current.snapshot["result"] == result_before
        # It never silently wrote the legacy latest namespace or a new result.
        saver = runtime.application.checkpoint_saver(
            "U1", "D1", "HARNESS_RECOVER")
        assert saver.get_tuple({
            "configurable": {"thread_id": thread_id}}) is None
    finally:
        runtime.gateway.close()


def test_harness_legacy_non_g3_task_still_recovers_to_a_new_session(tmp_path):
    """Control: the R1 refusal does not disable ordinary (non-G3) recovery."""
    from datetime import datetime, timedelta, timezone

    runtime, _entry = composition(tmp_path)
    intent = "养老金到了，帮我安排本月的钱"
    request_id, who = _seeded_task(runtime, "HARNESS_LEGACY", intent)
    try:
        started = runtime.harness.handle_message(who, request_id, intent)
        assert started.status is TaskStatus.WAITING_INPUT, started.message
        task = runtime.application.get_task("U1", "D1", "HARNESS_LEGACY")
        assert "birthday_g3" not in task.snapshot
        assert task.session_id == "S1"

        now = datetime.now(timezone.utc)
        runtime.application.create_session(
            "S2", "U1", "D1", now.isoformat(),
            (now + timedelta(days=1)).isoformat())
        stranger = TrustedContext(
            user_id="U1", session_id="S2", task_id="HARNESS_LEGACY",
            run_id=str(uuid4()), parent_task_id=None, demo_round_id="D1")

        recovered = runtime.harness.recover_session(stranger)

        assert recovered.task_id == "HARNESS_LEGACY"
        current = runtime.application.get_task("U1", "D1", "HARNESS_LEGACY")
        assert current.session_id == "S2"
        assert current.snapshot["session_recovery"]["phase"] == "complete"
        assert "result" in current.snapshot
        assert "birthday_g3" not in current.snapshot
    finally:
        runtime.gateway.close()
