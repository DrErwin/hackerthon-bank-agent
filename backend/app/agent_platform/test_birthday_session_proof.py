"""Provider 13: real retirement proof precedes every new-session gate card.

An explicit faulty consumer returns the old cached card and is refused. This
provider test stays valid when the real Cross consumer learns session recovery.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import pytest

from app.contracts.common import SecurityDecisionCode
from app.contracts.tasks import ModuleResult
from app.modules.cross.entry import CrossEntry
from app.storage.database import connect
from app.security.test_retirement import insert_claim_row

from .birthday_edit import BirthdayEditError
from .test_birthday_harness_publication import drive_to_freeze_confirmation, harness_env
from .test_birthday_edit_continuation import settle_confirmation
from .test_birthday_runtime_wiring import approve_confirmation, answer_verification
from .test_birthday_session_recovery import target_session


STAGES = ("freeze_confirmation", "freeze_verification", "order_confirmation",
          "order_verification", "capture_confirmation", "capture_verification")


def waiting_at(env, stage):
    current = drive_to_freeze_confirmation(env)
    for _ in range(STAGES.index(stage) // 2):
        current = settle_confirmation(env, current)
    if stage.endswith("verification"):
        approve_confirmation(env.runtime, env.who, current.interaction.record_ref)
        current = env.resume({"choice": "approve"})
        assert current.interaction.kind == "verification"
    return current


def operations(env):
    with connect(env.runtime.bank.store.path) as connection:
        return [tuple(row) for row in connection.execute(
            "SELECT operation_id, action_name, status FROM bank_operations ORDER BY operation_id")]


def recover_cached_card(env, caller):
    def cached_result(_entry, trusted, **_kwargs):
        task = env.runtime.application.get_task(
            trusted.user_id, trusted.demo_round_id, trusted.task_id)
        return ModuleResult.model_validate(task.snapshot["result"]).model_copy(
            update={"run_id": trusted.run_id})

    with patch.object(CrossEntry, "recover_session", cached_result):
        with pytest.raises(BirthdayEditError, match="DEPENDENCY_UNAVAILABLE"):
            env.runtime.harness.recover_session(caller)


@pytest.mark.parametrize("stage", STAGES)
def test_unsubmitted_session_attempt_is_proved_and_linked_once(harness_env, stage):
    env = harness_env
    current = waiting_at(env, stage)
    option = deepcopy(env.snapshot()["birthday_edit_option"])
    original = deepcopy(env.snapshot()["birthday_actions"][option["item"]])
    published = deepcopy(env.published_ref())
    before_operations = operations(env)
    old_history = list(env.snapshot().get("birthday_attempts") or [])
    caller = target_session(env)
    before = datetime.now(timezone.utc)

    recover_cached_card(env, caller)

    projection = env.runtime.birthday.handoff.session_recovery_status(caller)
    assert projection["status"] == "fresh"
    assert projection["original_operation_id"] == original["operation_id"]
    replacement = env.snapshot()["birthday_actions"][option["item"]]
    assert replacement["operation_id"] == projection["replacement_operation_id"]
    assert replacement["operation_id"] != original["operation_id"]
    assert replacement["action_revision"] > original["action_revision"]
    assert replacement["parameters"] == original["parameters"]
    assert env.snapshot()["birthday_attempts"] == [*old_history, original]
    assert env.published_ref() == published
    assert operations(env) == before_operations
    context = env.runtime._context(caller, UUID(original["operation_id"]), original["action_revision"])
    retirement = env.runtime.confirmations.state.get_retirement(
        context, caller.task_id, UUID(original["operation_id"]), original["action_revision"])
    assert retirement.state == "sealed"
    assert retirement.original_binding["session_id"] == env.who.session_id
    assert retirement.original_binding["recovery_target_session_id"] == caller.session_id
    assert before <= retirement.created_at <= retirement.sealed_at <= datetime.now(timezone.utc)

    # The provider completed before a new gate call, so the current-session card
    # is for a new operation, never a grant rebound onto the old operation.
    ports = env.runtime.birthday.ports_factory(caller)
    answer = ports._check(caller, option["item"], original["parameters"], original.get("facts"))
    assert answer.decision is SecurityDecisionCode.REQUIRE_CONFIRMATION
    confirmation = env.runtime.confirmations.get(
        env.runtime._context(caller, None, None), answer.interaction.record_ref)
    assert confirmation.session_id == caller.session_id
    assert str(confirmation.operation_id) == replacement["operation_id"]
    assert confirmation.decision == "pending"
    recover_cached_card(env, caller.model_copy(update={"run_id": str(uuid4())}))
    assert env.runtime.birthday.handoff.session_recovery_status(caller) == projection
    assert env.snapshot()["birthday_attempts"] == [*old_history, original]
    assert env.snapshot()["birthday_actions"][option["item"]] == replacement
    assert operations(env) == before_operations


@pytest.mark.parametrize("fault", ["before_link", "after_link"])
def test_sealed_and_linked_breakpoints_reuse_the_one_attempt(harness_env, monkeypatch, fault):
    from . import birthday_session

    env = harness_env
    waiting_at(env, "freeze_verification")
    original = deepcopy(env.snapshot()["birthday_actions"]["freeze"])
    caller = target_session(env)
    finish = birthday_session._finish
    fired = False

    def interrupted(*args, **kwargs):
        nonlocal fired
        if not fired:
            fired = True
            if fault == "after_link":
                finish(*args, **kwargs)
            raise OSError("lost link receipt")
        return finish(*args, **kwargs)

    monkeypatch.setattr(birthday_session, "_finish", interrupted)
    with pytest.raises(OSError, match="lost link receipt"):
        env.runtime.harness.recover_session(caller)
    context = env.runtime._context(caller, UUID(original["operation_id"]), original["action_revision"])
    sealed = env.runtime.confirmations.state.get_retirement(
        context, caller.task_id, UUID(original["operation_id"]), original["action_revision"])
    assert sealed.state == "sealed"
    after_break = env.runtime.birthday.handoff.session_recovery_status(caller)
    assert (after_break is not None) == (fault == "after_link")
    recover_cached_card(env, caller.model_copy(update={"run_id": str(uuid4())}))
    linked = env.runtime.birthday.handoff.session_recovery_status(caller)
    assert linked["status"] == "fresh"
    if after_break is not None:
        assert linked == after_break
    assert env.snapshot()["birthday_attempts"] == [original]
    assert env.runtime.confirmations.state.get_retirement(
        context, caller.task_id, UUID(original["operation_id"]), original["action_revision"]).audit_ref == sealed.audit_ref
    assert operations(env) == []


@pytest.mark.parametrize("changed", ["revision", "parameters", "publication", "target_session", "marker", "terminated"])
def test_session_validator_reads_the_same_transaction_and_refuses_changed_source(
    harness_env, monkeypatch, changed,
):
    env = harness_env
    waiting_at(env, "freeze_verification")
    original = deepcopy(env.snapshot()["birthday_actions"]["freeze"])
    caller = target_session(env)
    target_session(env, "S3")
    security = env.runtime.confirmations.state
    begin = security.begin_session_retirement
    calls = 0

    def changed_begin(*args, **kwargs):
        validator = kwargs["recovery_validator"]

        def mutate(connection, context, binding):
            nonlocal calls
            assert connection.in_transaction
            calls += 1
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (context.task_id,)).fetchone()
            snapshot = json.loads(row["snapshot_json"])
            if changed == "revision":
                connection.execute("UPDATE tasks SET revision = revision + 1 WHERE task_id = ?", (context.task_id,))
            elif changed == "target_session":
                connection.execute("UPDATE tasks SET session_id = 'S3' WHERE task_id = ?", (context.task_id,))
            elif changed == "terminated":
                connection.execute("UPDATE tasks SET status = 'failed' WHERE task_id = ?", (context.task_id,))
            else:
                if changed == "parameters":
                    snapshot["birthday_actions"]["freeze"]["parameters"]["amount_fen"] += 1
                elif changed == "publication":
                    snapshot["birthday_g3"]["published_ref"]["content_digest"] = "changed"
                else:
                    snapshot["session_recovery"]["expected_revision"] += 1
                connection.execute("UPDATE tasks SET snapshot_json = ? WHERE task_id = ?",
                    (json.dumps(snapshot), context.task_id))
            return validator(connection, context, binding)

        return begin(*args, **{**kwargs, "recovery_validator": mutate})

    monkeypatch.setattr(security, "begin_session_retirement", changed_begin)
    gateway = env.runtime.gateway
    with patch.object(gateway, "retire_action_challenges", wraps=gateway.retire_action_challenges) as bank:
        with pytest.raises(BirthdayEditError, match="RETIREMENT_STALE"):
            env.runtime.harness.recover_session(caller)
        bank.assert_not_called()
    assert calls == 1
    assert env.snapshot()["birthday_actions"]["freeze"] == original
    assert not env.snapshot().get("birthday_attempts")
    assert operations(env) == []


@pytest.mark.parametrize("claim_state", ["processing", "unknown", "completed"])
def test_existing_claim_is_observed_without_retiring_or_replacing(harness_env, claim_state, monkeypatch):
    env = harness_env
    waiting_at(env, "freeze_verification")
    option = deepcopy(env.snapshot()["birthday_edit_option"])
    original = deepcopy(env.snapshot()["birthday_actions"]["freeze"])
    context = env.runtime._context(env.who, UUID(option["operation_id"]), option["action_revision"])
    insert_claim_row(SimpleNamespace(path=env.runtime.application.path), context,
                     env.runtime.birthday.handoff._descriptor(option), claim_state)
    caller = target_session(env)
    bank = Mock(side_effect=AssertionError("CLAIMED_ATTEMPT_MUST_NOT_RETIRE"))
    monkeypatch.setattr(env.runtime.gateway, "retire_action_challenges", bank)
    recover_cached_card(env, caller)
    observed = env.runtime.birthday.handoff.session_recovery_status(caller)
    assert observed["status"] == "observe"
    assert observed["original_operation_id"] == original["operation_id"]
    assert observed["replacement_operation_id"] is None
    assert env.snapshot()["birthday_actions"]["freeze"] == original
    assert not env.snapshot().get("birthday_attempts")
    bank.assert_not_called()
    assert operations(env) == []


def test_real_active_freeze_is_only_observed_and_not_invalidated(harness_env, monkeypatch):
    env = harness_env
    current = waiting_at(env, "freeze_verification")
    original = deepcopy(env.snapshot()["birthday_actions"]["freeze"])
    answer_verification(env.runtime, env.who, "R1", current.interaction.record_ref)
    ports = env.runtime.birthday.ports_factory(env.who)
    outcome = ports._execute_verified(env.who, "freeze", original["parameters"], original["operation_id"])
    assert outcome.state == "completed"
    assert ports.bind_freeze(env.who, None, original["operation_id"])
    context = env.runtime._context(env.who, UUID(original["operation_id"]), original["action_revision"])
    release_id = env.snapshot()["birthday_release"]
    active = env.runtime.confirmations.state.get_release_authorization(context, release_id)
    assert active.status == "active"
    before_operations = operations(env)
    caller = target_session(env)
    bank = Mock(side_effect=AssertionError("ACTIVE_FREEZE_MUST_NOT_RETIRE"))
    monkeypatch.setattr(env.runtime.gateway, "retire_action_challenges", bank)
    recover_cached_card(env, caller)
    assert env.runtime.birthday.handoff.session_recovery_status(caller)["status"] == "observe"
    assert env.runtime.confirmations.state.get_release_authorization(context, release_id) == active
    assert env.snapshot()["birthday_actions"]["freeze"] == original
    assert not env.snapshot().get("birthday_attempts")
    assert operations(env) == before_operations
    bank.assert_not_called()


@pytest.mark.parametrize("offset", [-8000, 1800])
def test_session_retirement_evidence_keeps_real_time(harness_env, offset):
    env = harness_env
    waiting_at(env, "freeze_verification")
    option = deepcopy(env.snapshot()["birthday_edit_option"])
    caller = target_session(env)
    env.runtime.set_demo_clock(datetime.now(timezone.utc) + timedelta(days=offset))
    before = datetime.now(timezone.utc)
    recover_cached_card(env, caller)
    context = env.runtime._context(caller, UUID(option["operation_id"]), option["action_revision"])
    sealed = env.runtime.confirmations.state.get_retirement(
        context, caller.task_id, UUID(option["operation_id"]), option["action_revision"])
    retired_at = datetime.fromisoformat(sealed.bank_evidence["retired_at"])
    assert before <= sealed.created_at <= retired_at <= sealed.sealed_at <= datetime.now(timezone.utc)


def test_task_cas_drift_after_bank_proof_cannot_be_sealed_or_rebased(harness_env, monkeypatch):
    env = harness_env
    waiting_at(env, "freeze_verification")
    option = deepcopy(env.snapshot()["birthday_edit_option"])
    original = deepcopy(env.snapshot()["birthday_actions"]["freeze"])
    caller = target_session(env)
    retire = env.runtime.gateway.retire_action_challenges
    bank_calls = 0

    def external_write(*args, **kwargs):
        nonlocal bank_calls
        bank_calls += 1
        evidence = retire(*args, **kwargs)
        task = env.task()
        env.runtime.application.update_task("U1", "D1", task.task_id,
            task.revision, task.run_id, task.status, task.checkpoint_id,
            {**task.snapshot, "unrelated_writer": True})
        return evidence

    monkeypatch.setattr(env.runtime.gateway, "retire_action_challenges", external_write)
    for _ in range(2):
        with pytest.raises(BirthdayEditError, match="RETIREMENT_STALE"):
            env.runtime.harness.recover_session(caller.model_copy(update={"run_id": str(uuid4())}))
    context = env.runtime._context(caller, UUID(option["operation_id"]), option["action_revision"])
    pending = env.runtime.confirmations.state.get_retirement(
        context, caller.task_id, UUID(option["operation_id"]), option["action_revision"])
    assert pending.state == "pending_proof"
    assert pending.audit_ref is None
    assert env.runtime.birthday.handoff.session_recovery_status(caller) is None
    assert env.snapshot()["birthday_actions"]["freeze"] == original
    assert bank_calls == 1
    assert operations(env) == []


def test_retirement_audit_failure_retries_original_proof_before_linking(harness_env, monkeypatch):
    env = harness_env
    waiting_at(env, "freeze_verification")
    original = deepcopy(env.snapshot()["birthday_actions"]["freeze"])
    release_id = env.snapshot()["birthday_release"]
    caller = target_session(env)
    writer = env.runtime.audit.append_in_transaction
    failed = False

    def unavailable(connection, event, **kwargs):
        nonlocal failed
        if event.event_type == "security.decided" and "RETIRED_UNSUBMITTED" in event.payload.decision.reason_codes and not failed:
            failed = True
            raise OSError("retirement audit unavailable")
        return writer(connection, event, **kwargs)

    monkeypatch.setattr(env.runtime.audit, "append_in_transaction", unavailable)
    with pytest.raises(BirthdayEditError, match="AUDIT_UNAVAILABLE"):
        env.runtime.harness.recover_session(caller)
    context = env.runtime._context(caller, UUID(original["operation_id"]), original["action_revision"])
    assert env.runtime.confirmations.state.get_release_authorization(context, release_id).status == "pending_freeze"
    assert env.snapshot()["birthday_actions"]["freeze"] == original
    recover_cached_card(env, caller.model_copy(update={"run_id": str(uuid4())}))
    assert env.runtime.birthday.handoff.session_recovery_status(caller)["status"] == "fresh"
    assert env.runtime.confirmations.state.get_release_authorization(context, release_id).status == "invalid"
    decisions = [event for event in env.runtime.audit._events("D1", caller.task_id)
                 if event.event_type == "security.decided"
                 and "RETIRED_UNSUBMITTED" in event.payload.decision.reason_codes]
    assert len(decisions) == 1
    assert env.snapshot()["birthday_attempts"] == [original]
    assert operations(env) == []


def test_new_confirmation_id_reuse_cannot_make_the_old_card_current(harness_env, monkeypatch):
    env = harness_env
    old = waiting_at(env, "freeze_confirmation")
    option = deepcopy(env.snapshot()["birthday_edit_option"])
    original = deepcopy(env.snapshot()["birthday_actions"][option["item"]])
    caller = target_session(env)
    checked = False

    def new_check_then_cached(entry, trusted, **kwargs):
        nonlocal checked
        assert env.runtime.birthday.handoff.session_recovery_status(trusted)["status"] == "fresh"
        answer = env.runtime.birthday.ports_factory(trusted)._check(
            trusted, option["item"], original["parameters"], original.get("facts"))
        assert answer.interaction.record_ref == old.interaction.record_ref
        assert answer.interaction.interaction_id != old.interaction.interaction_id
        checked = True
        return old.model_copy(update={"run_id": trusted.run_id})

    monkeypatch.setattr(CrossEntry, "recover_session", new_check_then_cached)
    with pytest.raises(BirthdayEditError, match="DEPENDENCY_UNAVAILABLE"):
        env.runtime.harness.recover_session(caller)
    assert checked
    assert env.snapshot()["session_recovery"]["phase"] == "transitioned"
    assert env.snapshot()["result"]["interaction"]["interaction_id"] == old.interaction.interaction_id
    assert operations(env) == []


@pytest.mark.parametrize("foreign", [{"user_id": "U2"}, {"round_id": "D2"}, {}],
                         ids=["user", "round", "session"])
def test_session_recovery_projection_cannot_be_read_from_a_foreign_scope(harness_env, foreign):
    env = harness_env
    waiting_at(env, "freeze_confirmation")
    caller = target_session(env)
    recover_cached_card(env, caller)
    other = target_session(env, "FOREIGN", **foreign)
    with pytest.raises((PermissionError, ValueError)):
        env.runtime.birthday.handoff.session_recovery_status(other)


def test_historical_sensitive_source_without_parameter_digests_is_not_backfilled(harness_env):
    from . import birthday_session

    env = harness_env
    with patch.object(birthday_session, "publication_binding", return_value=None):
        waiting_at(env, "freeze_verification")
    before = env.task()
    caller = target_session(env)
    with pytest.raises(BirthdayEditError, match="SOURCE_UNAVAILABLE"):
        env.runtime.harness.recover_session(caller)
    assert env.task() == before
    assert env.runtime.birthday.handoff.session_recovery_status(env.who) is None
    assert operations(env) == []


def test_current_parameter_drift_cannot_impersonate_the_published_action(harness_env):
    env = harness_env
    waiting_at(env, "freeze_verification")
    task = env.task()
    changed = deepcopy(task.snapshot)
    changed["birthday_actions"]["freeze"]["parameters"]["amount_fen"] += 1
    env.runtime.application.update_task("U1", "D1", task.task_id, task.revision,
        task.run_id, task.status, task.checkpoint_id, changed)
    before = env.task()
    caller = target_session(env)
    with pytest.raises(BirthdayEditError, match="SOURCE_UNAVAILABLE"):
        env.runtime.harness.recover_session(caller)
    assert env.task() == before
    assert not env.snapshot().get("birthday_session_recoveries")
    assert operations(env) == []
