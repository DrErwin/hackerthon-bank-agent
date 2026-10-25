"""Ticket v05-birthday-platform-dependencies/04: the F10 controlled-edit diversion.

The public HTTP boundary runs on the real composition: the real cross birthday
flow, ticket 03's handoff, ticket 02's retirement guard, ticket 06's real bank
challenge retirement, ticket 05's saver and the real security gate. Only the
Cross candidate preparation side of ticket 08 is an explicit stand-in: the
Protocol is the seam, not the implementation.

Failure modes pinned down first:

1. F10 must only divert when the platform published this exact edit option for
   this exact current card; an unpublished/old/foreign/other-module option, a
   stale interaction, a foreign session/user or a non-empty ``text`` is refused
   before any success card is shown.
2. The successful diversion keeps the same task, publishes a new task revision
   and a new waiting input interaction, while the original confirmation facts
   survive untouched.
3. Receipt semantics stay the ordinary ones: same parameters replay, same
   request id with different parameters conflicts, and an interrupted request is
   retried only when the exact original request already owns the platform's
   durable edit record; without that fact it is never replayed as a new edit.
4. A lost HTTP receipt recovers the frozen published winner, not a second
   publication; a claim that won first keeps the old action observed and never
   returns a success card; internal platform refusal codes never reach the body.
5. A new session does not inherit the old receipt or the old card's edit right.
"""

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from app.agent_platform.birthday_edit import (
    EDIT_OPTION_LABEL, CandidateRequest, CrossCandidate,
)
from app.agent_platform.model import TransferProposal
from app.agent_platform.test_birthday_runtime_wiring import (
    RAW_DELIVERY, approve_confirmation, option_id,
)
from app.agent_platform.test_local_demo import app_for, configuration
from app.contracts.common import (
    OperationLevel, Phase, RiskLevel, SecurityDecisionCode, TaskStatus,
)
from app.contracts.platform import StartTransferInput, TrustedContext
from app.contracts.security import ActionDescriptor, SecurityDecision
from app.contracts.tasks import (
    InteractionOption, InteractionRequest, ModuleResult,
)
from app.memory.adapter import MemoryContext
from app.modules.cross.entry import CrossEntry
from app.storage.database import connect

from .store import dump
from .test_app import approve, make_app, post, start

INTENT_TEXT = "给妈妈过生日，安排花和蛋糕"
CHANNEL = "cross_state"
ROUND = "D1"
USER = "U1"
INTERNAL_EDIT_CODES = (
    "OPERATION_UNKNOWN", "OPERATION_CONFLICT", "EDIT_NOT_PROVABLE",
    "RETIREMENT_STALE", "SOURCE_UNAVAILABLE", "CANDIDATE_INVALID",
    "CANDIDATE_CONFLICT", "TASK_CHANGED", "TRANSITION_PENDING",
    "PUBLISH_CONFLICT", "CROSS_HANDOFF_UNAVAILABLE", "CROSS_UNAVAILABLE",
    "AUDIT_UNAVAILABLE", "INVALID_CONVERSION",
)
PUBLIC_EDIT_CODES = {
    "INTERACTION_STALE", "TASK_TERMINATED", "REQUEST_CONFLICT",
    "INVALID_OPTION", "NOT_FOUND", "ACCESS_DENIED",
    "DEPENDENCY_UNAVAILABLE", "REQUEST_IN_PROGRESS",
    "SESSION_RECONFIRMATION_REQUIRED",
}


class StandInCrossHandoff:
    """Explicit stand-in for ticket 08's Cross candidate preparation.

    Ticket 08 owns reading the exact published source ref and building the
    isolated candidate; this double returns the same shape with plain
    dictionaries so the API/platform seam can be verified before that wiring.
    """

    def __init__(self, clock):
        self.clock = clock
        self.requests: list[CandidateRequest] = []
        self.fail_next = False

    def prepare(self, trusted: TrustedContext, request: CandidateRequest) -> CrossCandidate:
        self.requests.append(request)
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("cross candidate unavailable")
        interaction_id = str(uuid4())
        result = ModuleResult(
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
        version = 1
        if request.source_checkpoint is not None:
            versions = request.source_checkpoint.get("channel_versions") or {}
            version = int(versions.get(CHANNEL, 0)) + 1
        checkpoint = {
            "v": 1, "id": request.candidate.checkpoint_id,
            "ts": self.clock().isoformat(),
            "channel_values": {CHANNEL: {
                "actor": [trusted.user_id, trusted.demo_round_id, trusted.task_id],
                "kind": request.kind, "edit_ref": request.edit_ref,
                "association": request.association,
                "interaction_id": interaction_id,
            }},
            "channel_versions": {CHANNEL: version},
            "versions_seen": {}, "pending_sends": [],
        }
        return CrossCandidate(
            checkpoint=checkpoint,
            metadata={"source": "api-edit-stand-in", "step": version},
            new_versions={CHANNEL: version}, result=result,
        )


@dataclass
class World:
    client: TestClient
    api: object
    runtime: object
    entry: CrossEntry
    who: TrustedContext
    task_id: str
    card: ModuleResult


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    # The real local-demo composition (real cross, security, saver and bank);
    # the chat model is the repository's scripted test connector and is never
    # consulted by the entry-driven birthday flow below.
    config = configuration(tmp_path_factory.mktemp("f10-edit-entry"))
    app = app_for(config, response_mode="none")
    with TestClient(app) as client:
        yield {"client": client, "api": app.state.api, "runtime": app.state.api.runtime}


@pytest.fixture()
def world(demo):
    runtime, api, client = demo["runtime"], demo["api"], demo["client"]
    session_id = f"S-{uuid4()}"
    task_id = f"BIRTHDAY-{uuid4()}"
    thread_id = str(uuid4())
    # A controlled detail reference is single-owner and immutable, so every world
    # gets its own reference for its own task.
    delivery_ref = f"deliver-birthday-{uuid4().hex}"
    at = datetime.now(timezone.utc)
    runtime.application.create_session(
        session_id, USER, ROUND, at.isoformat(),
        (at + timedelta(hours=2)).isoformat(),
    )
    runtime.application.create_task(
        task_id, USER, session_id, ROUND, str(uuid4()), "running",
        {"capability_name": "cross.start_task", "trace_id": str(uuid4())},
    )
    runtime.application.store_controlled_detail(
        delivery_ref, USER, ROUND, task_id, "delivery", RAW_DELIVERY,
        at.isoformat(),
    )
    task = runtime.application.get_task(USER, ROUND, task_id)
    runtime.application.update_task(
        USER, ROUND, task_id, task.revision, task.run_id, task.status,
        task.checkpoint_id,
        {**task.snapshot, "request_id": str(uuid4()), "intent_text": INTENT_TEXT},
    )
    # Ticket 03's public publication entry; its Cross/harness wiring is ticket
    # 08's, so the fixture publishes the predecessor-less root source explicitly.
    handoff = runtime.birthday.handoff
    handoff.cross = StandInCrossHandoff(runtime.gateway._bank.clock)
    who = TrustedContext(
        user_id=USER, session_id=session_id, demo_round_id=ROUND,
        task_id=task_id, run_id=str(uuid4()), parent_task_id=None,
    )
    handoff.publish_initial_state(who)
    entry = CrossEntry(
        runtime.harness,
        runtime.memory.checkpointer(MemoryContext(USER, session_id, ROUND), task_id),
        None, runtime.gateway._bank.clock,
        birthday_ports_factory=runtime.birthday.ports_factory,
    )
    api.store.write("INSERT INTO api_sessions VALUES (?, ?)", (session_id, "user"))
    api.store.write(
        "INSERT INTO api_threads VALUES (?, ?, ?, ?, ?)",
        (thread_id, USER, ROUND, at.isoformat(), dump({"thread_id": thread_id})),
    )
    saved = runtime.application.get_task(USER, ROUND, task_id)
    api.store.write(
        """INSERT INTO api_tasks (task_id, thread_id, user_id, session_id,
            demo_round_id, run_id, created_at, request_id, intent_text)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, thread_id, USER, session_id, ROUND, saved.run_id,
         at.isoformat(), str(uuid4()), INTENT_TEXT),
    )
    client.cookies.clear()
    client.cookies.set("bank_session", api.cookie(session_id))
    card = _freeze_card(entry, who, delivery_ref)
    # Ticket 08's harness wiring would persist this card; until then the fixture
    # records the card the real flow returned (same application-store write the
    # harness makes) so the task view and its status reflect the current card.
    _persist_card(runtime, task_id, card)
    return World(client, api, runtime, entry, who, task_id, card)


def _persist_card(runtime, task_id: str, result: ModuleResult) -> None:
    task = runtime.application.get_task(USER, ROUND, task_id)
    runtime.application.update_task(
        USER, ROUND, task_id, task.revision, task.run_id, result.status,
        task.checkpoint_id,
        {**task.snapshot, "result": result.model_dump(mode="json")},
    )


def _freeze_card(entry: CrossEntry, who: TrustedContext,
                 delivery_ref: str) -> ModuleResult:
    started = entry.start(who, StartTransferInput(
        request_id=uuid4(), intent_text=INTENT_TEXT))
    assert started.status is TaskStatus.WAITING_INPUT, started.message
    current = entry.resume(who, {"text": "500元"})
    current = entry.resume(who, {"text": "2026-10-30"})
    current = entry.resume(who, {"text": delivery_ref})
    current = entry.resume(
        who, {"selected_option_id": option_id(current, "鲜花")})
    current = entry.resume(
        who, {"selected_option_id": option_id(current, "蛋糕")})
    current = entry.resume(
        who, {"selected_option_id": option_id(current, "就选这些")})
    current = entry.resume(
        who, {"selected_option_id": option_id(current, "采用并开始办理")})
    assert current.interaction is not None, current.message
    assert current.interaction.kind == "confirmation", current.message
    return current


def edit_option(card: ModuleResult) -> str:
    matches = [item.id for item in card.interaction.options
               if item.label == EDIT_OPTION_LABEL]
    assert len(matches) == 1, [item.label for item in card.interaction.options]
    return matches[0]


def stored_task(world: World):
    return world.runtime.application.get_task(USER, ROUND, world.task_id)


def submit_inputs(world: World, *, request_id=None, **body):
    return world.client.post(
        f"/api/v1/tasks/{world.task_id}/inputs",
        json={"request_id": str(request_id or uuid4()), **body},
        headers={"Origin": "http://testserver"},
    )


def submit_edit(world: World, *, request_id=None, text=None):
    return submit_inputs(
        world, request_id=request_id, text=text,
        interaction_id=world.card.interaction.interaction_id,
        selected_option_id=edit_option(world.card),
    )


def assert_public_edit_error(response, *, status: int) -> None:
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] in PUBLIC_EDIT_CODES, error
    body = json.dumps(response.json(), ensure_ascii=False)
    for code in INTERNAL_EDIT_CODES:
        assert code not in body, code


def retirement_count(world: World) -> int:
    with closing(connect(world.runtime.application.path)) as connection:
        return connection.execute(
            "SELECT COUNT(*) FROM security_retirements WHERE task_id=?",
            (world.task_id,)).fetchone()[0]


def option_record(world: World) -> dict:
    return stored_task(world).snapshot["birthday_edit_option"]


def allow_decision(world: World, record: dict) -> SecurityDecision:
    return SecurityDecision(
        decision_id=str(uuid4()), task_id=world.task_id, run_id=world.who.run_id,
        action_name=record["action_name"],
        parameters_ref=str(record["operation_id"]),
        operation_id=UUID(str(record["operation_id"])),
        action_revision=int(record["action_revision"]),
        phase=Phase.EXECUTION, operation_level=OperationLevel.SENSITIVE,
        risk_level=RiskLevel.MEDIUM, decision=SecurityDecisionCode.ALLOW,
        reason_codes=[], rule_ids=[], policy_version="test",
        authorization_snapshot_ref=str(uuid4()), evidence_refs=[],
        interaction=None, checked_at=datetime.now(timezone.utc), message="test",
    )


def claim_original(world: World):
    record = option_record(world)
    context = world.runtime._context(
        world.who, UUID(str(record["operation_id"])),
        int(record["action_revision"]),
    )
    descriptor = ActionDescriptor(
        action_name=record["action_name"],
        parameters_ref=str(record["operation_id"]),
        resource_refs=[], phase=Phase.EXECUTION,
    )
    claim, created = world.runtime.confirmations.state.claim_execution(
        context, descriptor, allow_decision(world, record),
        datetime.now(timezone.utc), world.runtime._task_terminated,
    )
    assert created is True
    return context, descriptor


# ------------------------------------------------------------- entry diversion


def test_a_published_edit_option_enters_the_same_task_waiting_input(world):
    before = stored_task(world)
    old_card = world.card.interaction
    actions_before = before.snapshot.get("birthday_actions")
    assert before.status is TaskStatus.WAITING_APPROVAL

    response = submit_edit(world)
    assert response.status_code == 200, response.text
    view = response.json()["data"]
    assert view["task_id"] == world.task_id
    assert view["module"] == "cross"
    assert view["status"] == "waiting_input"
    assert view["interaction"]["kind"] == "input"
    assert view["interaction"]["interaction_id"] != old_card.interaction_id
    # One task CAS reserves the accepted edit, one publishes the sealed winner.
    assert view["task_revision"] == before.revision + 2

    after = stored_task(world)
    assert after.status is TaskStatus.WAITING_INPUT
    assert after.revision == view["task_revision"]
    assert after.snapshot["result"]["interaction"]["interaction_id"] == \
        view["interaction"]["interaction_id"]
    edit = after.snapshot["birthday_edit"]
    assert edit["published"]["task_revision"] == view["task_revision"]
    # The original item/attempt facts survive; the original attempt is retired
    # once, not rewritten, and the old action can no longer be claimed.
    assert after.snapshot.get("birthday_actions") == actions_before
    assert retirement_count(world) == 1
    # The original confirmation and its pending decision survive unchanged.
    confirmation = world.runtime.confirmations.get(
        world.runtime._context(world.who, None, None), old_card.record_ref)
    assert confirmation.decision == "pending"


def test_a_verification_card_enters_the_same_controlled_edit(world):
    # The freeze confirmation answered on its own durable record leads to the
    # real step-up verification card, which must offer the same controlled edit.
    approve_confirmation(
        world.runtime, world.who, world.card.interaction.record_ref)
    verification = world.entry.resume(world.who, {"choice": "approve"})
    assert verification.interaction is not None, verification.message
    assert verification.interaction.kind == "verification", verification.message
    _persist_card(world.runtime, world.task_id, verification)
    before = stored_task(world)
    world.card = verification

    response = submit_edit(world)
    assert response.status_code == 200, response.text
    view = response.json()["data"]
    assert view["task_id"] == world.task_id
    assert view["status"] == "waiting_input"
    assert view["interaction"]["interaction_id"] != \
        verification.interaction.interaction_id
    assert view["task_revision"] == before.revision + 2


def test_the_same_request_replays_the_same_published_result(world):
    request_id = uuid4()
    first = submit_edit(world, request_id=request_id)
    assert first.status_code == 200, first.text
    published = stored_task(world).snapshot["birthday_edit"]["published"]
    edit_ref = stored_task(world).snapshot["birthday_edit"]["edit_ref"]

    second = submit_edit(world, request_id=request_id)
    assert second.status_code == 200, second.text
    assert second.json() == first.json()
    task = stored_task(world)
    assert task.revision == published["task_revision"]
    assert task.snapshot["birthday_edit"]["edit_ref"] == edit_ref


def test_the_same_request_id_with_other_parameters_conflicts(world):
    request_id = uuid4()
    first = submit_edit(world, request_id=request_id)
    assert first.status_code == 200, first.text
    before = stored_task(world)

    conflict = submit_inputs(
        world, request_id=request_id, text=None,
        interaction_id=world.card.interaction.interaction_id,
        selected_option_id="birthday-edit-" + str(uuid4()),
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "REQUEST_CONFLICT"
    assert stored_task(world).revision == before.revision


def test_a_non_empty_text_never_enters_the_controlled_edit(world):
    before = stored_task(world)

    response = submit_edit(world, text="把蛋糕换成别的")
    assert_public_edit_error(response, status=400)
    assert response.json()["error"]["code"] == "INVALID_OPTION"
    after = stored_task(world)
    assert after.revision == before.revision
    assert "birthday_edit" not in after.snapshot
    assert retirement_count(world) == 0


def test_unpublished_options_and_old_interactions_are_refused(world):
    before = stored_task(world)
    interaction_id = world.card.interaction.interaction_id
    for option in ("birthday-edit-" + str(uuid4()), "continue", "approve"):
        stale = submit_inputs(
            world, interaction_id=interaction_id, selected_option_id=option)
        assert_public_edit_error(stale, status=409)
        assert stale.json()["error"]["code"] == "INTERACTION_STALE"
    old = submit_inputs(
        world, interaction_id=str(uuid4()),
        selected_option_id=edit_option(world.card))
    assert_public_edit_error(old, status=409)
    assert old.json()["error"]["code"] == "INTERACTION_STALE"
    after = stored_task(world)
    assert after.revision == before.revision
    assert "birthday_edit" not in after.snapshot
    assert retirement_count(world) == 0
    assert after.status is TaskStatus.WAITING_APPROVAL


def test_the_old_card_replays_the_frozen_winner_without_a_second_retirement(world):
    first = submit_edit(world)
    assert first.status_code == 200, first.text
    published = stored_task(world).snapshot["birthday_edit"]["published"]
    retirements = retirement_count(world)

    # A fresh request id on the old card recovers the accepted edit: the platform
    # replays its frozen winner and never retires the original attempt twice.
    replay = submit_edit(world)
    assert replay.status_code == 200, replay.text
    view = replay.json()["data"]
    assert view["task_revision"] == published["task_revision"]
    assert view["interaction"]["interaction_id"] == \
        published["result"]["interaction"]["interaction_id"]
    assert retirement_count(world) == retirements


# -------------------------------------------------------- refusal / interruption


def test_a_claim_that_ran_first_is_observed_never_edited(world):
    approve_confirmation(
        world.runtime, world.who, world.card.interaction.record_ref)
    context, descriptor = claim_original(world)
    result_before = stored_task(world).snapshot.get("result")

    response = submit_edit(world)
    assert_public_edit_error(response, status=409)
    assert response.json()["error"]["code"] == "INTERACTION_STALE"

    task = stored_task(world)
    assert task.status is TaskStatus.WAITING_APPROVAL
    assert task.snapshot.get("result") == result_before
    edit = task.snapshot.get("birthday_edit")
    assert edit is not None and edit["published"] is None
    # The original attempt keeps its own rules: it is claimed, not retired.
    record = option_record(world)
    assert world.runtime.confirmations.state.get_execution(context, descriptor)
    assert world.runtime.confirmations.state.get_retirement(
        context, world.task_id, UUID(str(record["operation_id"])),
        int(record["action_revision"])) is None


def test_a_lost_http_receipt_recovers_the_same_published_winner(world, monkeypatch):
    request_id = uuid4()
    store = world.api.store
    original_finish = store.finish
    crashed = {"done": False}

    def crash_once(*args, **kwargs):
        if not crashed["done"]:
            crashed["done"] = True
            raise RuntimeError("simulated crash after publication")
        return original_finish(*args, **kwargs)

    monkeypatch.setattr(store, "finish", crash_once)
    first = submit_edit(world, request_id=request_id)
    assert first.status_code == 503, first.text
    published = stored_task(world).snapshot["birthday_edit"]["published"]

    recovered = submit_edit(world, request_id=request_id)
    assert recovered.status_code == 200, recovered.text
    view = recovered.json()["data"]
    assert view["task_id"] == world.task_id
    assert view["task_revision"] == published["task_revision"]
    assert view["interaction"]["interaction_id"] == \
        published["result"]["interaction"]["interaction_id"]
    assert stored_task(world).revision == published["task_revision"]


def test_a_break_after_retirement_recovers_the_same_original_request(world):
    """Security retirement succeeds, the candidate/publication does not.

    No success card is shown and the old card is unchanged, but the accepted
    edit record (by this exact request id) makes a same-request retry recover
    through the platform; nothing is replayed as a brand new edit.
    """
    request_id = uuid4()
    world.runtime.birthday.handoff.cross.fail_next = True
    first = submit_edit(world, request_id=request_id)
    assert first.status_code == 503, first.text
    held = stored_task(world)
    edit = held.snapshot["birthday_edit"]
    assert edit["request_id"] == str(request_id)
    assert edit["published"] is None
    assert retirement_count(world) == 1
    assert held.status is TaskStatus.WAITING_APPROVAL
    assert held.snapshot["result"]["interaction"]["interaction_id"] == \
        world.card.interaction.interaction_id

    recovered = submit_edit(world, request_id=request_id)
    assert recovered.status_code == 200, recovered.text
    published = stored_task(world).snapshot["birthday_edit"]["published"]
    assert recovered.json()["data"]["task_revision"] == \
        published["task_revision"]
    assert stored_task(world).status is TaskStatus.WAITING_INPUT


def test_an_interrupted_request_without_a_durable_record_is_not_retried(
    world, monkeypatch,
):
    request_id = uuid4()
    handoff = world.runtime.birthday.handoff
    store = world.api.store

    def crash(*args, **kwargs):
        raise RuntimeError("simulated crash before the platform accepted the edit")

    def crash_finish(*args, **kwargs):
        raise RuntimeError("simulated crash before the receipt was written")

    monkeypatch.setattr(handoff, "begin_birthday_edit", crash)
    monkeypatch.setattr(store, "finish", crash_finish)
    first = submit_edit(world, request_id=request_id)
    assert first.status_code == 503, first.text
    assert "birthday_edit" not in stored_task(world).snapshot

    retry = submit_edit(world, request_id=request_id)
    assert retry.status_code == 409
    assert retry.json()["error"]["code"] == "REQUEST_IN_PROGRESS"
    task = stored_task(world)
    assert "birthday_edit" not in task.snapshot
    assert task.status is TaskStatus.WAITING_APPROVAL
    assert retirement_count(world) == 0


def test_a_terminated_task_is_not_edited(world):
    task = stored_task(world)
    world.runtime.application.update_task(
        USER, ROUND, world.task_id, task.revision, task.run_id,
        TaskStatus.CANCELLED, task.checkpoint_id, task.snapshot,
    )
    response = submit_edit(world)
    assert_public_edit_error(response, status=409)
    assert response.json()["error"]["code"] == "TASK_TERMINATED"
    task = stored_task(world)
    assert task.status is TaskStatus.CANCELLED
    assert "birthday_edit" not in task.snapshot
    assert retirement_count(world) == 0


# --------------------------------------------------------------- session/identity


def test_a_new_session_does_not_inherit_the_old_edit_receipt(world):
    request_id = uuid4()
    first = submit_edit(world, request_id=request_id)
    assert first.status_code == 200, first.text
    published = stored_task(world).snapshot["birthday_edit"]["published"]

    at = datetime.now(timezone.utc)
    new_session = f"S-{uuid4()}"
    world.runtime.application.create_session(
        new_session, USER, ROUND, at.isoformat(),
        (at + timedelta(hours=2)).isoformat(),
    )
    world.api.store.write(
        "INSERT INTO api_sessions VALUES (?, ?)", (new_session, "user"))
    world.client.cookies.clear()
    world.client.cookies.set("bank_session", world.api.cookie(new_session))

    replay = submit_edit(world, request_id=request_id)
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "SESSION_RECONFIRMATION_REQUIRED"
    fresh = submit_edit(world)
    assert fresh.status_code == 409
    assert fresh.json()["error"]["code"] == "SESSION_RECONFIRMATION_REQUIRED"
    # The published card is unchanged; a new session gains no write right.
    assert stored_task(world).revision == published["task_revision"]
    assert retirement_count(world) == 1


def test_a_foreign_user_gets_the_ordinary_not_found(world):
    at = datetime.now(timezone.utc)
    foreign_session = f"S-{uuid4()}"
    world.runtime.application.create_session(
        foreign_session, "U2", ROUND, at.isoformat(),
        (at + timedelta(hours=2)).isoformat(),
    )
    world.api.store.write(
        "INSERT INTO api_sessions VALUES (?, ?)", (foreign_session, "user"))
    world.client.cookies.clear()
    world.client.cookies.set("bank_session", world.api.cookie(foreign_session))

    response = submit_edit(world)
    assert_public_edit_error(response, status=404)
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert "birthday_edit" not in stored_task(world).snapshot


# ------------------------------------------------------- unchanged ordinary F10


def test_ordinary_f10_input_and_confirmation_stay_unchanged(tmp_path):
    proposal = TransferProposal(payee_hint="妈妈", payer_account_id="A1")
    with TestClient(make_app(tmp_path, proposal=proposal)) as client:
        _thread, task = start(client, text="给妈妈转 500 元")
        assert task["status"] == "waiting_input"
        filled = post(
            client, f"/tasks/{task['task_id']}/inputs",
            interaction_id=task["interaction"]["interaction_id"], text="500",
        )
        assert filled.status_code == 200, filled.text
        task = filled.json()["data"]
        assert task["status"] == "waiting_approval"
        # F10 on a confirmation card is still the ordinary stale-interaction
        # refusal: no birthday edit option was published for a transfer task.
        stale = post(
            client, f"/tasks/{task['task_id']}/inputs",
            interaction_id=task["interaction"]["interaction_id"],
            selected_option_id="birthday-edit-" + str(uuid4()),
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "INTERACTION_STALE"
        answered = approve(client, task)
        assert answered["task_id"] == task["task_id"]
