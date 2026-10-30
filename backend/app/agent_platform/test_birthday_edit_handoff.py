"""Ticket v05-birthday-platform-dependencies/03: the controlled birthday handoff.

The platform boundary is exercised with the real composition only: the real
security state (isolated temporary application database), ticket 02's retirement
guard, ticket 06's real mock-bank verification, ticket 05's real saver and the
real cross birthday flow. The cross *candidate preparation* side (ticket 08) is
an explicit stand-in: the Protocol is the seam, not the implementation.

Failure modes this file pins down first:

1. An edit option that is not the platform's current publication (old card, old
   interaction, another module's option, a changed option id) must never start a
   retirement.
2. The same accepted request must replay one result; a different request on the
   same card, a foreign session or a terminated task must be refused.
3. The original attempt can be claimed before acceptance or between acceptance
   and sealing: the platform must observe it and never fake a new input.
4. Every persistent breakpoint — after the security seal, after the candidate
   seal, after a lost receipt — must recover along the same accepted record and
   publish the first sealed winner only.
5. A published edit must be immutable and must not rewrite the original attempt,
   its action history or the published source.
6. Root and ordinary states use the same publication boundary: a normal
   successor without a published source must not pose as a root; a root retry
   must not create a second winner; a failed publication must not expose the
   sealed candidate as active state.
"""

from datetime import datetime, timezone
import inspect
import json
from uuid import UUID, uuid4

import pytest

from app.contracts.common import OperationLevel, Phase, RiskLevel, SecurityDecisionCode, TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.security import ActionDescriptor, SecurityDecision
from app.contracts.tasks import InteractionOption, InteractionRequest
from app.security.state import SecurityStateError
from app.services.mock_bank.verification import ChallengeRetired
from app.storage.checkpoints import CheckpointRef

from .birthday_edit import (
    EDIT_OPTION_LABEL, BirthdayEditError, BirthdayHandoff, CandidateRequest,
    CrossCandidate, publish_edit_option,
)
from .test_birthday_runtime_wiring import (
    DELIVER_DATE, DELIVERY_REF, _all_freezes, answer_verification, approve_confirmation,
    composition, option_id, trusted,
)

START_REQUEST = str(uuid4())
INTENT_TEXT = "给妈妈过生日，安排花和蛋糕"
CHANNEL = "cross_state"

CARD_STAGES = (
    "freeze_confirmation", "freeze_verification",
    "order_confirmation", "order_verification",
    "capture_confirmation", "capture_verification",
)


class StandInCrossHandoff:
    """Explicit stand-in for ticket 08; builds content, never touches the saver.

    The real implementation reads the exact source ref and returns the complete
    candidate; this stand-in does the same shape with plain dictionaries so the
    platform boundary can be verified without the cross module's new flow.
    """

    def __init__(self, clock):
        self.clock = clock
        self.requests: list[CandidateRequest] = []
        self.results = []
        self.fail_next = False

    def prepare(self, trusted: TrustedContext, request: CandidateRequest) -> CrossCandidate:
        self.requests.append(request)
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("cross unavailable")
        interaction_id = str(uuid4())
        result = _waiting_input(trusted, interaction_id)
        self.results.append(result)
        version = 1
        source_state = None
        if request.source_checkpoint is not None:
            versions = request.source_checkpoint.get("channel_versions") or {}
            version = int(versions.get(CHANNEL, 0)) + 1
            source_state = (request.source_checkpoint.get("channel_values")
                            or {}).get(CHANNEL)
        state = {
            "actor": [trusted.user_id, trusted.demo_round_id, trusted.task_id],
            "kind": request.kind,
            "edit_ref": request.edit_ref,
            "source_checkpoint_id": (None if request.source is None
                                     else request.source.checkpoint_id),
            "source_state": source_state,
            "association": request.association,
            "interaction_id": interaction_id,
        }
        checkpoint = {
            "v": 1, "id": request.candidate.checkpoint_id,
            "ts": self.clock().isoformat(),
            "channel_values": {CHANNEL: state},
            "channel_versions": {CHANNEL: version},
            "versions_seen": {}, "pending_sends": [],
        }
        return CrossCandidate(
            checkpoint=checkpoint,
            metadata={"source": "cross-stand-in", "step": version},
            new_versions={CHANNEL: version},
            result=result,
        )


def _waiting_input(trusted: TrustedContext, interaction_id: str):
    from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult

    return ModuleResult(
        task_id=trusted.task_id, run_id=trusted.run_id,
        status=TaskStatus.WAITING_INPUT,
        data={"scenario": "birthday", "plan_revision": 1, "steps": [],
              "summary": "已受理修改，请继续补充生日方案。"},
        message="已受理修改，请继续补充生日方案。",
        interaction=InteractionRequest(
            interaction_id=interaction_id, kind="input",
            prompt="已受理修改，请继续补充生日方案。",
            required_fields=[],
            options=[InteractionOption(id="continue", label="继续")],
            record_ref=None),
        error=None, allowed_actions=["provide_input", "cancel"],
        recovery_required=False, recovery_reason=None)


def _add_start_association(runtime) -> None:
    task = runtime.application.get_task("U1", "D1", "BIRTHDAY")
    runtime.application.update_task(
        "U1", "D1", "BIRTHDAY", task.revision, task.run_id, task.status,
        task.checkpoint_id,
        {**task.snapshot, "request_id": START_REQUEST, "intent_text": INTENT_TEXT},
    )


class Environment:
    def __init__(self, runtime, entry, who, handoff, cross):
        self.runtime = runtime
        self.entry = entry
        self.who = who
        self.handoff = handoff
        self.cross = cross

    def task(self):
        return self.runtime.application.get_task("U1", "D1", "BIRTHDAY")

    def snapshot(self) -> dict:
        return self.task().snapshot or {}

    def published_ref(self) -> dict:
        return self.snapshot()["birthday_g3"]["published_ref"]

    def option_record(self) -> dict:
        return self.snapshot()["birthday_edit_option"]

    def saver(self):
        from app.memory.adapter import MemoryContext

        return self.runtime.memory.checkpointer(
            MemoryContext("U1", "S1", "D1"), "BIRTHDAY")

    def ref(self, record: dict) -> CheckpointRef:
        return CheckpointRef(record["thread_id"], record["checkpoint_ns"],
                             record["checkpoint_id"])


@pytest.fixture()
def build(tmp_path):
    created = []

    def factory(*, publish_root=True):
        case_dir = tmp_path / f"case-{len(created)}"
        case_dir.mkdir()
        runtime, entry = composition(case_dir)
        created.append(runtime)
        _add_start_association(runtime)
        cross = StandInCrossHandoff(runtime.gateway._bank.clock)
        handoff = BirthdayHandoff(runtime, cross=cross)
        who = trusted(runtime)
        if publish_root:
            handoff.publish_initial_state(who)
        yield_env = Environment(runtime, entry, who, handoff, cross)
        return yield_env

    try:
        yield factory
    finally:
        for runtime in created:
            runtime.gateway.close()


def edit_option(card) -> str:
    return option_id(card, "修改尚未提交")


def advance_to(env: Environment, target: str):
    """Drive the real birthday flow to one of the six waiting cards."""
    current = _freeze_confirmation(env)
    index = CARD_STAGES.index(target)
    for stage in CARD_STAGES[:index]:
        current = _advance_one(env, current, stage)
    assert current.interaction is not None, current.message
    assert current.status is TaskStatus.WAITING_APPROVAL, current.message
    return current


def _freeze_confirmation(env: Environment):
    from app.contracts.platform import StartTransferInput

    entry = env.entry
    started = entry.start(env.who, StartTransferInput(
        request_id=uuid4(), intent_text=INTENT_TEXT))
    assert started.status is TaskStatus.WAITING_INPUT, started.message
    current = entry.resume(env.who, {"text": "500元"})
    current = entry.resume(env.who, {"text": DELIVER_DATE})
    current = entry.resume(env.who, {"text": DELIVERY_REF})
    current = entry.resume(env.who, {"selected_option_id": option_id(current, "鲜花")})
    current = entry.resume(env.who, {"selected_option_id": option_id(current, "蛋糕")})
    current = entry.resume(env.who, {"selected_option_id": option_id(current, "就选这些")})
    current = entry.resume(
        env.who, {"selected_option_id": option_id(current, "采用并开始办理")})
    assert current.interaction is not None and current.interaction.kind == "confirmation"
    return current


def _advance_one(env: Environment, card, stage: str):
    entry = env.entry
    if stage.endswith("_confirmation"):
        approve_confirmation(env.runtime, env.who, card.interaction.record_ref)
        return entry.resume(env.who, {"choice": "approve"})
    answer_verification(env.runtime, env.who, "R1", card.interaction.record_ref)
    return entry.resume(env.who, {"choice": "resume"})


def begin_edit(env: Environment, card, *, request_id=None):
    return env.handoff.begin_birthday_edit(
        env.who, request_id=request_id or uuid4(),
        interaction_id=card.interaction.interaction_id,
        option_id=edit_option(card))


def allow_decision(record: dict) -> SecurityDecision:
    return SecurityDecision(
        decision_id=str(uuid4()), task_id="BIRTHDAY", run_id="R1",
        action_name=record["action_name"], parameters_ref=str(record["operation_id"]),
        operation_id=UUID(str(record["operation_id"])),
        action_revision=int(record["action_revision"]),
        phase=Phase.EXECUTION, operation_level=OperationLevel.SENSITIVE,
        risk_level=RiskLevel.MEDIUM, decision=SecurityDecisionCode.ALLOW,
        reason_codes=[], rule_ids=[], policy_version="test",
        authorization_snapshot_ref=str(uuid4()), evidence_refs=[], interaction=None,
        checked_at=datetime.now(timezone.utc), message="test",
    )


def claim_code(env: Environment, record: dict) -> str:
    context = env.runtime._context(
        env.who, UUID(str(record["operation_id"])),
        int(record["action_revision"]))
    descriptor = ActionDescriptor(
        action_name=record["action_name"], parameters_ref=str(record["operation_id"]),
        resource_refs=[], phase=Phase.EXECUTION)
    with pytest.raises(SecurityStateError) as refused:
        env.runtime.confirmations.state.claim_execution(
            context, descriptor, allow_decision(record),
            datetime.now(timezone.utc), env.runtime._task_terminated,
        )
    return refused.value.code


def sealed_content(env: Environment, record: dict):
    ref = env.ref(record)
    saved = env.saver().get_tuple({"configurable": {
        "thread_id": ref.thread_id, "checkpoint_ns": ref.checkpoint_ns,
        "checkpoint_id": ref.checkpoint_id,
    }})
    assert saved is not None
    return saved


# ---------------------------------------------------------------- A. edit entry


@pytest.mark.parametrize("stage", CARD_STAGES)
def test_every_birthday_confirmation_and_verification_can_enter_a_controlled_edit(
    build, stage,
):
    env = build()
    source_before = env.published_ref()
    card = advance_to(env, stage)
    assert card.interaction.kind in {"confirmation", "verification"}
    # The platform publishes exactly one edit option bound to this card.
    options = [item for item in card.interaction.options
               if item.label == EDIT_OPTION_LABEL]
    assert len(options) == 1, [item.label for item in card.interaction.options]
    option = env.option_record()
    assert option["interaction_id"] == card.interaction.interaction_id
    assert option["option_id"] == options[0].id
    actions_before = env.snapshot().get("birthday_actions") or {}
    attempts_before = list(env.snapshot().get("birthday_attempts") or [])
    accepted_revision = env.task().revision

    outcome = begin_edit(env, card)

    assert outcome.result.status is TaskStatus.WAITING_INPUT
    assert outcome.result.task_id == "BIRTHDAY"
    assert outcome.result.interaction.kind == "input"
    assert outcome.result.interaction.interaction_id != card.interaction.interaction_id
    # One CAS reserves the edit, one publishes the winner.
    assert outcome.task_revision == accepted_revision + 2
    task = env.task()
    assert task.revision == outcome.task_revision
    assert task.status is TaskStatus.WAITING_INPUT
    assert task.checkpoint_id == outcome.published_ref.checkpoint_id
    published = env.snapshot()["birthday_g3"]["published_ref"]
    assert published["kind"] == "edit"
    assert (published["thread_id"], published["checkpoint_ns"],
            published["checkpoint_id"]) == (
        outcome.published_ref.thread_id, outcome.published_ref.checkpoint_ns,
        outcome.published_ref.checkpoint_id)
    edit = env.snapshot()["birthday_edit"]
    assert edit["published"]["task_revision"] == outcome.task_revision
    # The original item/attempt/history facts survive; the old action cannot write.
    assert env.snapshot().get("birthday_actions") == actions_before
    assert list(env.snapshot().get("birthday_attempts") or []) == attempts_before
    # The sealed retirement blocks a later claim of the original attempt.
    assert claim_code(env, option) == "ACTION_RETIRED"
    if card.interaction.kind == "verification":
        with pytest.raises(ChallengeRetired):
            env.runtime.gateway.get_demo_code_for_api(
                env.who, card.interaction.record_ref)
    # The published candidate is immutable: no overwrite path can touch it.
    with pytest.raises(ValueError, match="immutable"):
        env.saver().put({"configurable": {
            "thread_id": outcome.published_ref.thread_id,
            "checkpoint_ns": outcome.published_ref.checkpoint_ns,
            "checkpoint_id": outcome.published_ref.checkpoint_id,
        }}, {"v": 1, "id": outcome.published_ref.checkpoint_id, "ts": "now",
             "channel_values": {}, "channel_versions": {},
             "versions_seen": {}, "pending_sends": []},
            {"step": 2}, {})
    # The source that was published before the edit is untouched.
    assert (source_before["checkpoint_ns"], source_before["checkpoint_id"]) != (
        published["checkpoint_ns"], published["checkpoint_id"])
    source = sealed_content(env, source_before)
    assert source.checkpoint["channel_values"][CHANNEL]["kind"] == "root"


@pytest.mark.parametrize("stage", CARD_STAGES)
def test_same_edit_request_replays_one_result(build, stage):
    env = build()
    card = advance_to(env, stage)
    request_id = uuid4()
    first = begin_edit(env, card, request_id=request_id)
    revision = env.task().revision
    calls = len(env.cross.requests)

    replay = begin_edit(env, card, request_id=request_id)

    assert replay.result.interaction.interaction_id == (
        first.result.interaction.interaction_id)
    assert replay.task_revision == first.task_revision == revision
    assert replay.published_ref == first.published_ref
    assert env.task().revision == revision
    assert len(env.cross.requests) == calls  # no new candidate preparation


def test_a_new_request_on_the_same_card_recovers_the_accepted_edit(build):
    env = build()
    card = advance_to(env, "freeze_confirmation")
    env.cross.fail_next = True
    with pytest.raises(BirthdayEditError) as unavailable:
        begin_edit(env, card, request_id=uuid4())
    assert unavailable.value.code == "CROSS_UNAVAILABLE"
    accepted = env.snapshot()["birthday_edit"]

    # A retried click carries a new F10 request id but the same trusted card; it
    # recovers the accepted record instead of opening a second edit.
    outcome = begin_edit(env, card, request_id=uuid4())
    assert env.snapshot()["birthday_edit"]["edit_ref"] == accepted["edit_ref"]
    assert outcome.edit_ref == accepted["edit_ref"]
    assert env.snapshot()["birthday_edit"]["published"] is not None


def test_an_accepted_card_that_was_replaced_is_stale(build):
    env = build()
    old_card = advance_to(env, "freeze_confirmation")
    option = env.option_record()
    approve_confirmation(env.runtime, env.who, old_card.interaction.record_ref)
    context = env.runtime._context(
        env.who, UUID(option["operation_id"]), int(option["action_revision"]))
    descriptor = ActionDescriptor(
        action_name=option["action_name"], parameters_ref=option["operation_id"],
        resource_refs=[], phase=Phase.EXECUTION)
    env.runtime.confirmations.state.claim_execution(
        context, descriptor, allow_decision(option),
        datetime.now(timezone.utc), env.runtime._task_terminated,
    )
    # The claim wins: the edit is accepted but can never retire the attempt.
    with pytest.raises(BirthdayEditError) as refused:
        begin_edit(env, old_card)
    assert refused.value.code == "OPERATION_UNKNOWN"
    from app.contracts.bank import FreezeFundsInput

    env.runtime.gateway.freeze_funds(
        env.who, UUID(option["operation_id"]),
        FreezeFundsInput(account_id="A1", amount_fen=50000, reason="生日安排"))
    replacement = env.entry.resume(env.who, {"choice": "approve"})
    assert replacement.interaction.interaction_id != old_card.interaction.interaction_id
    # The accepted edit belongs to the replaced card: it cannot be recovered.
    with pytest.raises(BirthdayEditError) as stale:
        begin_edit(env, old_card)
    assert stale.value.code == "INTERACTION_STALE"
    # The current card starts a fresh, provable edit request.
    outcome = begin_edit(env, replacement)
    assert outcome.result.status is TaskStatus.WAITING_INPUT
    assert env.snapshot()["birthday_edit"]["interaction_id"] == (
        replacement.interaction.interaction_id)


def test_old_cards_and_foreign_options_are_never_recognised(build):
    env = build()
    old_card = advance_to(env, "freeze_confirmation")
    approve_confirmation(env.runtime, env.who, old_card.interaction.record_ref)
    new_card = env.entry.resume(env.who, {"choice": "approve"})
    assert new_card.interaction.interaction_id != old_card.interaction.interaction_id

    with pytest.raises(BirthdayEditError) as stale:
        begin_edit(env, old_card)
    assert stale.value.code == "INTERACTION_STALE"
    # The current card's ordinary approve option is not an edit option.
    with pytest.raises(BirthdayEditError) as wrong_option:
        env.handoff.begin_birthday_edit(
            env.who, request_id=uuid4(),
            interaction_id=new_card.interaction.interaction_id,
            option_id="approve")
    assert wrong_option.value.code == "INTERACTION_STALE"
    # A client-invented option id on the real card is refused too.
    with pytest.raises(BirthdayEditError) as invented:
        env.handoff.begin_birthday_edit(
            env.who, request_id=uuid4(),
            interaction_id=new_card.interaction.interaction_id,
            option_id="birthday-edit-made-up")
    assert invented.value.code == "INTERACTION_STALE"
    assert "birthday_edit" not in env.snapshot()


def test_an_edit_option_never_starts_from_a_waiting_input_state(build):
    env = build()
    root = env.published_ref()
    # The published root is a waiting_input card; it carries no edit option and
    # the safe input node must not pretend a retirement is needed.
    assert root["kind"] == "root"
    result = env.snapshot()["result"]
    interaction = result["interaction"]
    with pytest.raises(BirthdayEditError) as stale:
        env.handoff.begin_birthday_edit(
            env.who, request_id=uuid4(),
            interaction_id=interaction["interaction_id"],
            option_id=interaction["options"][0]["id"])
    assert stale.value.code == "INTERACTION_STALE"


def test_foreign_session_and_terminated_task_are_refused(build):
    env = build()
    card = advance_to(env, "freeze_confirmation")
    now = datetime.now(timezone.utc)
    env.runtime.application.create_session(
        "S2", "U1", "D1", now.isoformat(), (now.timestamp() + 86400).__str__())
    stranger = TrustedContext(
        user_id="U1", session_id="S2", task_id="BIRTHDAY", run_id="R1",
        parent_task_id=None, demo_round_id="D1")
    with pytest.raises(BirthdayEditError) as denied:
        env.handoff.begin_birthday_edit(
            stranger, request_id=uuid4(),
            interaction_id=card.interaction.interaction_id,
            option_id=edit_option(card))
    assert denied.value.code == "ACCESS_DENIED"

    task = env.task()
    env.runtime.application.update_task(
        "U1", "D1", "BIRTHDAY", task.revision, task.run_id,
        TaskStatus.CANCELLED, task.checkpoint_id, task.snapshot)
    with pytest.raises(BirthdayEditError) as ended:
        begin_edit(env, card)
    assert ended.value.code == "TASK_TERMINATED"
    assert "birthday_edit" not in env.snapshot()


def test_edit_entry_accepts_only_the_f10_control_references():
    params = list(inspect.signature(BirthdayHandoff.begin_birthday_edit).parameters.values())
    assert [item.name for item in params] == [
        "self", "trusted", "request_id", "interaction_id", "option_id"]
    assert all(item.kind is inspect.Parameter.KEYWORD_ONLY for item in params[2:])


def test_the_handoff_is_not_a_registered_model_tool(build):
    env = build()
    catalog = env.runtime.harness.registry.public_catalog()
    names = {item["name"] for item in catalog}
    assert all(not name.startswith("birthday") for name in names)
    assert "birthday-edit" not in json.dumps(catalog)
    # Ticket 08 mounts Cross's real implementation in its own assembly
    # (`register_cross` -> `install_cross_handoff`); that assembly-level wiring
    # is pinned by the Cross suite, so the platform test no longer asserts the
    # (now outdated) "production keeps the cross side absent" seam.


def test_an_unmounted_cross_handoff_refuses_instead_of_improvising(build):
    """The documented fallback: without a Cross implementation, no new input."""
    env = build()
    card = advance_to(env, "freeze_confirmation")
    env.handoff.cross = None
    with pytest.raises(BirthdayEditError) as unavailable:
        begin_edit(env, card)
    assert unavailable.value.code == "CROSS_HANDOFF_UNAVAILABLE"
    # Nothing is fabricated: the accepted edit stays unpublished, the G3 source
    # is unchanged and the sealed retirement still blocks the old operation.
    assert env.snapshot()["birthday_edit"]["published"] is None
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "root"
    assert claim_code(env, env.option_record()) == "ACTION_RETIRED"


def _confirmation_card(record_ref: str | None = None) -> InteractionRequest:
    return InteractionRequest(
        interaction_id=str(uuid4()), kind="confirmation",
        prompt="请核对当前操作并在确认按钮中作答。", required_fields=[],
        options=[InteractionOption(id="approve", label="确认办理"),
                 InteractionOption(id="cancel", label="取消")],
        record_ref=record_ref or str(uuid4()))


def test_the_edit_option_binds_the_card_to_the_confirmation_version(build):
    env = build()
    without_binding = publish_edit_option(
        env.runtime, env.who, interaction=_confirmation_card(), item="freeze",
        action_name="bank.freeze_funds", operation_id=str(uuid4()),
        action_revision=1, confirmation_id=None, confirmation_version=None)
    assert [item.label for item in without_binding.options] == ["确认办理", "取消"]
    assert "birthday_edit_option" not in env.snapshot()

    operation_id, confirmation_id = str(uuid4()), str(uuid4())
    amended = publish_edit_option(
        env.runtime, env.who, interaction=_confirmation_card(), item="freeze",
        action_name="bank.freeze_funds", operation_id=operation_id,
        action_revision=2, confirmation_id=confirmation_id,
        confirmation_version=3)
    assert [item.label for item in amended.options] == [
        "确认办理", "取消", EDIT_OPTION_LABEL]
    record = env.snapshot()["birthday_edit_option"]
    assert record["interaction_id"] == amended.interaction_id
    assert record["option_id"] == amended.options[-1].id
    assert record["operation_id"] == operation_id
    assert record["action_revision"] == 2
    assert record["confirmation_id"] == confirmation_id
    assert record["confirmation_version"] == 3


def test_a_failed_option_publication_refuses_the_card(build):
    from unittest.mock import patch

    env = build()
    card = _confirmation_card()
    with patch.object(env.runtime.application, "update_task",
                      side_effect=ValueError("changed concurrently")):
        with pytest.raises(BirthdayEditError) as refused:
            publish_edit_option(
                env.runtime, env.who, interaction=card, item="freeze",
                action_name="bank.freeze_funds", operation_id=str(uuid4()),
                action_revision=1, confirmation_id=str(uuid4()),
                confirmation_version=1)
    # A concurrent task write is a stale-request conflict, never a dependency
    # failure (the API maps this platform code to a 409 refresh path).
    assert refused.value.code == "REQUEST_CONFLICT"
    assert "birthday_edit_option" not in env.snapshot()


# ------------------------------------------------- claim competition / M1 winner


def test_a_claim_that_already_exists_is_observed_never_edited(build):
    env = build()
    card = advance_to(env, "freeze_confirmation")
    result_before = env.snapshot().get("result")
    option = env.option_record()
    approve_confirmation(env.runtime, env.who, card.interaction.record_ref)
    context = env.runtime._context(
        env.who, UUID(option["operation_id"]), int(option["action_revision"]))
    descriptor = ActionDescriptor(
        action_name=option["action_name"],
        parameters_ref=option["operation_id"], resource_refs=[],
        phase=Phase.EXECUTION)
    claim, created = env.runtime.confirmations.state.claim_execution(
        context, descriptor, allow_decision(option),
        datetime.now(timezone.utc), env.runtime._task_terminated,
    )
    assert created is True

    with pytest.raises(BirthdayEditError) as refused:
        begin_edit(env, card)
    assert refused.value.code == "OPERATION_UNKNOWN"
    # The acceptance (step 1) was reserved before safety, but nothing was sealed
    # or published: the original operation is only observed from now on.
    edit = env.snapshot()["birthday_edit"]
    assert edit["published"] is None
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "root"
    assert env.runtime.confirmations.state.get_execution(context, descriptor) is not None
    assert env.snapshot().get("result") == result_before
    # The edit never reached the bank retirement, so the old attempt keeps its
    # own rules; a late code is still the original challenge's, not an edit path.
    assert env.runtime.confirmations.state.get_retirement(
        context, "BIRTHDAY", UUID(option["operation_id"]),
        int(option["action_revision"])) is None


def test_claim_between_acceptance_and_seal_keeps_the_old_action_executable(build):
    """M1: begin accepts, the executor claims and writes, the seal must refuse."""
    env = build()
    card = advance_to(env, "freeze_confirmation")
    option = env.option_record()
    approve_confirmation(env.runtime, env.who, card.interaction.record_ref)
    from app.contracts.bank import FreezeFundsInput, OperationResult

    original = env.runtime.gateway.retire_action_challenges
    raced = {}

    def racing(*args, **kwargs):
        context = env.runtime._context(
            env.who, UUID(option["operation_id"]), int(option["action_revision"]))
        descriptor = ActionDescriptor(
            action_name=option["action_name"],
            parameters_ref=option["operation_id"], resource_refs=[],
            phase=Phase.EXECUTION)
        claim, created = env.runtime.confirmations.state.claim_execution(
            context, descriptor, allow_decision(option),
            datetime.now(timezone.utc), env.runtime._task_terminated,
        )
        assert created is True
        result = env.runtime.gateway.freeze_funds(
            env.who, UUID(option["operation_id"]),
            FreezeFundsInput(account_id="A1", amount_fen=50000,
                             reason="生日安排"))
        raced["claim"] = claim
        raced["result"] = result
        return original(*args, **kwargs)

    from unittest.mock import patch

    with patch.object(env.runtime.gateway, "retire_action_challenges",
                      side_effect=racing):
        with pytest.raises(BirthdayEditError) as refused:
            begin_edit(env, card)
    assert refused.value.code == "OPERATION_UNKNOWN"
    # The old action really executed and keeps its result; the edit did not win.
    assert isinstance(raced["result"], OperationResult)
    assert raced["result"].operation_status.value == "succeeded"
    assert len(_all_freezes(env.runtime)) == 1
    assert "birthday_edit" in env.snapshot()
    assert env.snapshot()["birthday_edit"]["published"] is None
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "root"


def test_needs_attention_and_other_unsettled_states_cannot_edit(build):
    env = build()
    card = advance_to(env, "freeze_confirmation")
    task = env.task()
    env.runtime.application.update_task(
        "U1", "D1", "BIRTHDAY", task.revision, task.run_id,
        TaskStatus.NEEDS_ATTENTION, task.checkpoint_id, task.snapshot)
    with pytest.raises(BirthdayEditError) as blocked:
        begin_edit(env, card)
    assert blocked.value.code == "TASK_TERMINATED"
    assert "birthday_edit" not in env.snapshot()

    # An already accepted edit may not publish onto a needs-attention task either.
    env = build()
    card = advance_to(env, "freeze_confirmation")
    env.cross.fail_next = True
    with pytest.raises(BirthdayEditError) as unavailable:
        begin_edit(env, card)
    assert unavailable.value.code == "CROSS_UNAVAILABLE"
    task = env.task()
    env.runtime.application.update_task(
        "U1", "D1", "BIRTHDAY", task.revision, task.run_id,
        TaskStatus.NEEDS_ATTENTION, task.checkpoint_id, task.snapshot)
    with pytest.raises(BirthdayEditError) as refused:
        begin_edit(env, card)
    assert refused.value.code == "TASK_TERMINATED"
    assert env.snapshot()["birthday_edit"]["published"] is None


def test_edited_publication_uses_the_accepted_strict_revision(build):
    from unittest.mock import patch

    env = build()
    card = advance_to(env, "freeze_confirmation")
    original = env.runtime.gateway.retire_action_challenges

    def competing_write(*args, **kwargs):
        # A different legitimate write lands between the edit acceptance and its
        # publication; the strict accepted revision must make the CAS refuse.
        task = env.task()
        env.runtime.application.update_task(
            "U1", "D1", "BIRTHDAY", task.revision, task.run_id, task.status,
            task.checkpoint_id, {**task.snapshot, "competing_write": True},
        )
        return original(*args, **kwargs)

    with patch.object(env.runtime.gateway, "retire_action_challenges",
                      side_effect=competing_write):
        with pytest.raises(BirthdayEditError) as conflict:
            begin_edit(env, card)
    assert conflict.value.code == "PUBLISH_CONFLICT"
    assert env.snapshot()["birthday_edit"]["published"] is None
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "root"
    # The competing write was not overwritten by a fresher revision.
    assert env.snapshot().get("competing_write") is True


def test_normal_publication_uses_the_reserved_strict_revision(build):
    env = build()
    original = env.cross.prepare

    def competing_prepare(trusted, request):
        candidate = original(trusted, request)
        task = env.task()
        env.runtime.application.update_task(
            "U1", "D1", "BIRTHDAY", task.revision, task.run_id, task.status,
            task.checkpoint_id, {**task.snapshot, "competing_write": True},
        )
        return candidate

    env.cross.prepare = competing_prepare
    with pytest.raises(BirthdayEditError) as conflict:
        env.handoff.publish_normal_state(
            env.who, conversion={"kind": "input", "request_id": str(uuid4())})
    assert conflict.value.code == "PUBLISH_CONFLICT"
    assert env.published_ref()["kind"] == "root"
    assert env.snapshot()["birthday_g3"]["pending"] is not None
    assert env.snapshot().get("competing_write") is True


def test_candidate_writes_must_belong_to_the_trusted_task(build):
    env = build(publish_root=False)

    class ForeignWrites(StandInCrossHandoff):
        def prepare(self, trusted, request):
            candidate = super().prepare(trusted, request)
            return CrossCandidate(
                checkpoint=candidate.checkpoint, metadata=candidate.metadata,
                new_versions=candidate.new_versions, result=candidate.result,
                writes=(("cross_state", {"x": 1}),),
                writes_task_id="another-task",
            )

    env.handoff.cross = ForeignWrites(env.runtime.gateway._bank.clock)
    with pytest.raises(BirthdayEditError) as invalid:
        env.handoff.publish_initial_state(env.who)
    assert invalid.value.code == "CANDIDATE_INVALID"
    assert "birthday_g3" in env.snapshot()
    assert env.snapshot()["birthday_g3"].get("published_ref") is None

    class OwnedWrites(ForeignWrites):
        def prepare(self, trusted, request):
            candidate = super().prepare(trusted, request)
            return CrossCandidate(
                checkpoint=candidate.checkpoint, metadata=candidate.metadata,
                new_versions=candidate.new_versions, result=candidate.result,
                writes=candidate.writes, writes_task_id=trusted.task_id,
            )

    env.handoff.cross = OwnedWrites(env.runtime.gateway._bank.clock)
    outcome = env.handoff.publish_initial_state(env.who)
    assert outcome.kind == "root"
    sealed = sealed_content(env, env.published_ref())
    assert sealed.checkpoint["channel_values"][CHANNEL]["kind"] == "root"


# ------------------------------------------------------------- persistent breaks


def test_a_break_between_seal_and_candidate_recovers_the_same_edit(build):
    env = build()
    card = advance_to(env, "freeze_confirmation")
    result_before = env.snapshot().get("result")
    env.cross.fail_next = True
    with pytest.raises(BirthdayEditError) as unavailable:
        begin_edit(env, card)
    assert unavailable.value.code == "CROSS_UNAVAILABLE"
    accepted = env.snapshot()["birthday_edit"]
    option = env.option_record()
    # The old action is already irreversibly retired; no new input is pretended.
    assert claim_code(env, option) == "ACTION_RETIRED"
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "root"
    assert env.snapshot().get("result") == result_before
    # The unfinished acceptance is a transition in flight: no ordinary successor
    # may cross it while the edit itself has not published.
    with pytest.raises(BirthdayEditError) as blocked:
        env.handoff.publish_normal_state(
            env.who, conversion={"kind": "fact", "event_ref": "orig-event"})
    assert blocked.value.code == "TRANSITION_PENDING"

    outcome = begin_edit(env, card)
    assert outcome.edit_ref == accepted["edit_ref"]
    assert env.snapshot()["birthday_edit"]["published"]["task_revision"] == (
        outcome.task_revision)
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "edit"


def test_a_break_after_the_candidate_seal_recovers_the_first_winner(build):
    env = build()
    card = advance_to(env, "freeze_confirmation")
    first_edit_run = len(env.cross.requests)
    original = env.runtime.application.update_task

    def failing(*args, **kwargs):
        # Behavior-based fault injection: only the edit publication CAS fails
        # (its snapshot carries a `published` edit projection); the reservation
        # and every other task write pass through.
        snapshot = args[7] if len(args) > 7 else kwargs.get("snapshot")
        edit = (snapshot or {}).get("birthday_edit") or {}
        if edit.get("published") is not None:
            raise ValueError("task changed concurrently")
        return original(*args, **kwargs)

    from unittest.mock import patch

    with patch.object(env.runtime.application, "update_task", failing):
        with pytest.raises(BirthdayEditError) as conflict:
            begin_edit(env, card)
    assert conflict.value.code == "PUBLISH_CONFLICT"
    assert env.snapshot()["birthday_edit"]["published"] is None
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "root"
    reserved = env.snapshot()["birthday_edit"]["candidate"]
    assert sealed_content(env, reserved) is not None  # sealed but not published
    first_interaction = env.cross.results[first_edit_run].interaction.interaction_id

    outcome = begin_edit(env, card)

    assert len(env.cross.requests) == first_edit_run + 2  # re-prepared, first won
    assert outcome.result.interaction.interaction_id == first_interaction
    assert outcome.published_ref.checkpoint_id == reserved["checkpoint_id"]
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "edit"


def test_a_failed_security_audit_stops_the_edit(build):
    from unittest.mock import patch

    env = build()
    card = advance_to(env, "freeze_confirmation")
    result_before = env.snapshot().get("result")
    with patch.object(env.runtime.audit, "append_in_transaction",
                      side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(BirthdayEditError) as unavailable:
            begin_edit(env, card)
    assert unavailable.value.code == "AUDIT_UNAVAILABLE"
    # No editable fact was published; the acceptance stays a pending proof and
    # the old action remains under its own rules (no edit evidence).
    assert env.snapshot()["birthday_edit"]["published"] is None
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "root"
    assert env.snapshot().get("result") == result_before
    option = env.option_record()
    context = env.runtime._context(
        env.who, UUID(option["operation_id"]), int(option["action_revision"]))
    retirement = env.runtime.confirmations.state.get_retirement(
        context, "BIRTHDAY", UUID(option["operation_id"]),
        int(option["action_revision"]))
    assert retirement is not None and retirement.state == "pending_proof"

    outcome = begin_edit(env, card)
    assert outcome.result.status is TaskStatus.WAITING_INPUT


def test_a_lost_receipt_replays_the_published_edit_without_a_new_publication(build):
    env = build()
    card = advance_to(env, "freeze_confirmation")
    request_id = uuid4()
    outcome = begin_edit(env, card, request_id=request_id)
    task = env.task()

    replayed = begin_edit(env, card, request_id=request_id)

    assert replayed.result == outcome.result
    assert replayed.task_revision == outcome.task_revision
    assert env.task().revision == task.revision
    assert env.snapshot()["birthday_edit"]["published"]["task_revision"] == (
        outcome.task_revision)


# ------------------------------------------------------------- source refusals


def test_a_task_without_a_published_source_cannot_be_edited(build):
    env = build(publish_root=False)
    card = advance_to(env, "freeze_confirmation")
    with pytest.raises(BirthdayEditError) as missing:
        begin_edit(env, card)
    assert missing.value.code == "SOURCE_UNAVAILABLE"
    # Nothing was reserved or published; the card and the task stay as they were.
    assert "birthday_edit" not in env.snapshot()
    assert "birthday_g3" not in env.snapshot()
    assert env.snapshot()["birthday_edit_option"]["option_id"] == edit_option(card)


def test_a_source_that_no_longer_matches_is_refused(build):
    env = build()
    card = advance_to(env, "freeze_confirmation")
    task = env.task()
    g3 = dict(task.snapshot["birthday_g3"])
    tampered = dict(g3["published_ref"])
    tampered["checkpoint_id"] = str(uuid4())
    env.runtime.application.update_task(
        "U1", "D1", "BIRTHDAY", task.revision, task.run_id, task.status,
        task.checkpoint_id,
        {**task.snapshot, "birthday_g3": {**g3, "published_ref": tampered}},
    )
    with pytest.raises(BirthdayEditError) as unavailable:
        begin_edit(env, card)
    assert unavailable.value.code == "SOURCE_UNAVAILABLE"
    assert "birthday_edit" not in env.snapshot()


# --------------------------------------------------- B. initial / normal publish


def test_the_initial_root_is_sealed_and_published_exactly_once(build):
    env = build(publish_root=False)
    outcome = env.handoff.publish_initial_state(env.who)

    assert outcome.kind == "root"
    assert outcome.result.status is TaskStatus.WAITING_INPUT
    task = env.task()
    published = env.snapshot()["birthday_g3"]["published_ref"]
    assert published["kind"] == "root"
    assert task.checkpoint_id == outcome.published_ref.checkpoint_id
    assert task.revision == outcome.task_revision
    assert env.snapshot()["result"]["status"] == "waiting_input"
    sealed = sealed_content(env, published)
    assert sealed.checkpoint["channel_values"][CHANNEL]["kind"] == "root"
    assert sealed.checkpoint["channel_values"][CHANNEL]["source_checkpoint_id"] is None
    with pytest.raises(ValueError, match="immutable"):
        env.saver().put({"configurable": {
            "thread_id": outcome.published_ref.thread_id,
            "checkpoint_ns": outcome.published_ref.checkpoint_ns,
            "checkpoint_id": outcome.published_ref.checkpoint_id,
        }}, {"v": 1, "id": outcome.published_ref.checkpoint_id, "ts": "now",
             "channel_values": {}, "channel_versions": {},
             "versions_seen": {}, "pending_sends": []},
            {"step": 2}, {})

    replay = env.handoff.publish_initial_state(env.who)
    assert replay.published_ref == outcome.published_ref
    assert replay.task_revision == outcome.task_revision
    assert len(env.cross.requests) == 1


def test_a_normal_successor_binds_the_published_source(build):
    env = build()
    root = env.published_ref()
    first_conversion = {"kind": "input", "request_id": str(uuid4())}
    outcome = env.handoff.publish_normal_state(
        env.who, conversion=first_conversion)

    assert outcome.kind == "normal"
    published = env.published_ref()
    assert published["kind"] == "normal"
    assert env.task().checkpoint_id == outcome.published_ref.checkpoint_id
    assert env.task().revision == outcome.task_revision
    sealed = sealed_content(env, published)
    state = sealed.checkpoint["channel_values"][CHANNEL]
    assert state["source_checkpoint_id"] == root["checkpoint_id"]
    assert state["edit_ref"] is None  # an ordinary successor never fakes an edit
    with pytest.raises(ValueError, match="immutable"):
        env.saver().put({"configurable": {
            "thread_id": outcome.published_ref.thread_id,
            "checkpoint_ns": outcome.published_ref.checkpoint_ns,
            "checkpoint_id": outcome.published_ref.checkpoint_id,
        }}, {"v": 1, "id": outcome.published_ref.checkpoint_id, "ts": "now",
             "channel_values": {}, "channel_versions": {},
             "versions_seen": {}, "pending_sends": []},
            {"step": 2}, {})

    second = env.handoff.publish_normal_state(
        env.who, conversion={"kind": "exception", "event_ref": "run-event-1"})
    # A different conversion is a new successor from the just-published source.
    assert second.published_ref != outcome.published_ref
    assert env.published_ref()["checkpoint_id"] == second.published_ref.checkpoint_id
    second_source = sealed_content(env, env.published_ref())
    state = second_source.checkpoint["channel_values"][CHANNEL]
    assert state["source_checkpoint_id"] == outcome.published_ref.checkpoint_id

    # The first conversion's lost receipt still replays its own projection even
    # after a later successor was published; it never becomes active again.
    replay = env.handoff.publish_normal_state(
        env.who, conversion=first_conversion)
    assert replay.published_ref == outcome.published_ref
    assert replay.result == outcome.result
    assert env.published_ref()["checkpoint_id"] == second.published_ref.checkpoint_id


def test_an_ordinary_successor_after_an_edit_binds_the_edit_ref(build):
    env = build()
    card = advance_to(env, "freeze_confirmation")
    outcome = begin_edit(env, card)
    assert env.published_ref()["kind"] == "edit"

    successor = env.handoff.publish_normal_state(
        env.who, conversion={"kind": "input", "request_id": str(uuid4())})

    assert successor.kind == "normal"
    sealed = sealed_content(env, env.published_ref())
    state = sealed.checkpoint["channel_values"][CHANNEL]
    assert state["source_checkpoint_id"] == outcome.published_ref.checkpoint_id
    assert env.task().checkpoint_id == successor.published_ref.checkpoint_id


@pytest.mark.parametrize("conversion", [
    {"kind": "edit", "request_id": "r1"},
    {"kind": "input"},
    {"kind": "fact"},
    {"kind": "input", "request_id": "r1", "event_ref": "e1"},
    {"kind": "input", "request_id": "r1", "editable": True},
    {"kind": "normal", "request_id": "r1"},
])
def test_normal_publication_rejects_untrusted_conversion_shapes(build, conversion):
    env = build()
    with pytest.raises(BirthdayEditError) as refused:
        env.handoff.publish_normal_state(env.who, conversion=conversion)
    assert refused.value.code == "INVALID_CONVERSION"
    assert env.published_ref()["kind"] == "root"


def test_a_root_retry_must_match_the_accepted_start(build):
    env = build(publish_root=False)
    env.cross.fail_next = True
    with pytest.raises(BirthdayEditError) as unavailable:
        env.handoff.publish_initial_state(env.who)
    assert unavailable.value.code == "CROSS_UNAVAILABLE"
    pending = env.snapshot()["birthday_g3"]["pending"]
    task = env.task()
    env.runtime.application.update_task(
        "U1", "D1", "BIRTHDAY", task.revision, task.run_id, task.status,
        task.checkpoint_id,
        {**task.snapshot, "request_id": str(uuid4())},
    )
    # A different accepted start is not the same root transition.
    with pytest.raises(BirthdayEditError) as conflict:
        env.handoff.publish_initial_state(env.who)
    assert conflict.value.code == "ROOT_CONFLICT"
    assert env.snapshot()["birthday_g3"]["pending"] == pending
    assert env.snapshot()["birthday_g3"].get("published_ref") is None


def test_publication_refuses_an_ended_task_or_a_foreign_session(build):
    env = build()
    now = datetime.now(timezone.utc)
    env.runtime.application.create_session(
        "S9", "U1", "D1", now.isoformat(), "2099-01-01T00:00:00+00:00")
    stranger = TrustedContext(
        user_id="U1", session_id="S9", task_id="BIRTHDAY", run_id="R1",
        parent_task_id=None, demo_round_id="D1")
    with pytest.raises(BirthdayEditError) as denied:
        env.handoff.publish_normal_state(
            stranger, conversion={"kind": "input", "request_id": str(uuid4())})
    assert denied.value.code == "ACCESS_DENIED"

    task = env.task()
    env.runtime.application.update_task(
        "U1", "D1", "BIRTHDAY", task.revision, task.run_id,
        TaskStatus.CANCELLED, task.checkpoint_id, task.snapshot)
    with pytest.raises(BirthdayEditError) as ended:
        env.handoff.publish_normal_state(
            env.who, conversion={"kind": "input", "request_id": str(uuid4())})
    assert ended.value.code == "TASK_TERMINATED"
    assert env.published_ref()["kind"] == "root"


def test_a_normal_successor_without_a_published_source_cannot_pose_as_root(build):
    env = build(publish_root=False)
    with pytest.raises(BirthdayEditError) as missing:
        env.handoff.publish_normal_state(
            env.who, conversion={"kind": "input", "request_id": str(uuid4())})
    assert missing.value.code == "SOURCE_UNAVAILABLE"
    assert "birthday_g3" not in env.snapshot()
    assert env.task().checkpoint_id is None


def test_an_unpublished_conversion_blocks_the_next_one(build):
    env = build()
    env.cross.fail_next = True
    first = {"kind": "fact", "event_ref": "run-event-1"}
    with pytest.raises(BirthdayEditError) as unavailable:
        env.handoff.publish_normal_state(env.who, conversion=first)
    assert unavailable.value.code == "CROSS_UNAVAILABLE"
    pending = env.snapshot()["birthday_g3"]["pending"]
    assert pending["conversion_digest"]
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "root"

    with pytest.raises(BirthdayEditError) as blocked:
        env.handoff.publish_normal_state(
            env.who, conversion={"kind": "fact", "event_ref": "run-event-2"})
    assert blocked.value.code == "TRANSITION_PENDING"
    assert env.snapshot()["birthday_g3"]["pending"] == pending

    outcome = env.handoff.publish_normal_state(env.who, conversion=first)
    assert outcome.kind == "normal"
    assert env.snapshot()["birthday_g3"]["pending"] is None
    assert env.published_ref()["kind"] == "normal"


def test_a_failed_initial_publication_does_not_expose_the_candidate(build):
    env = build(publish_root=False)
    original = env.runtime.application.update_task

    def failing(*args, **kwargs):
        # Behavior-based fault injection: only the root publication CAS fails
        # (its snapshot carries a published_ref); the reservation passes.
        snapshot = args[7] if len(args) > 7 else kwargs.get("snapshot")
        g3 = (snapshot or {}).get("birthday_g3") or {}
        if g3.get("published_ref") is not None:
            raise ValueError("task changed concurrently")
        return original(*args, **kwargs)

    from unittest.mock import patch

    with patch.object(env.runtime.application, "update_task", failing):
        with pytest.raises(BirthdayEditError) as conflict:
            env.handoff.publish_initial_state(env.who)
    assert conflict.value.code == "PUBLISH_CONFLICT"
    assert "birthday_g3" in env.snapshot()
    assert env.snapshot()["birthday_g3"].get("published_ref") is None
    assert "result" not in env.snapshot()
    pending = env.snapshot()["birthday_g3"]["pending"]
    assert sealed_content(env, pending["candidate"]) is not None
    first_interaction = env.cross.results[0].interaction.interaction_id

    outcome = env.handoff.publish_initial_state(env.who)

    assert outcome.published_ref.checkpoint_id == pending["candidate"]["checkpoint_id"]
    assert outcome.result.interaction.interaction_id == first_interaction
    assert env.snapshot()["birthday_g3"]["published_ref"]["kind"] == "root"


def test_a_root_with_existing_history_is_never_reinitialised(build):
    env = build(publish_root=False)
    task = env.task()
    saver = env.saver()
    saver.put({"configurable": {"thread_id": task.checkpoint_thread_id,
                                "checkpoint_ns": ""}},
              {"v": 1, "id": str(uuid4()), "ts": "now",
               "channel_values": {CHANNEL: {"legacy": True}},
               "channel_versions": {CHANNEL: 1},
               "versions_seen": {}, "pending_sends": []},
              {"step": 1}, {CHANNEL: 1})
    with pytest.raises(BirthdayEditError) as refused:
        env.handoff.publish_initial_state(env.who)
    assert refused.value.code == "INITIAL_NOT_FIRST"
    assert env.snapshot()["birthday_g3"].get("published_ref") is None
    assert "result" not in env.snapshot()


def test_an_initial_root_needs_the_original_start_association(build):
    env = build(publish_root=False)
    task = env.task()
    env.runtime.application.update_task(
        "U1", "D1", "BIRTHDAY", task.revision, task.run_id, task.status,
        task.checkpoint_id,
        {key: value for key, value in task.snapshot.items()
         if key not in {"request_id", "intent_text"}},
    )
    with pytest.raises(BirthdayEditError) as unknown:
        env.handoff.publish_initial_state(env.who)
    assert unknown.value.code == "INITIAL_REQUEST_UNKNOWN"
    assert "birthday_g3" not in env.snapshot()
