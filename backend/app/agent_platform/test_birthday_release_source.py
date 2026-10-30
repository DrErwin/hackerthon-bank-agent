"""Platform16: a new session ends against the exact original freeze approval."""

from copy import deepcopy

import pytest

from app.contracts.audit import AuthorizationSnapshot
from app.modules.cross.birthday_ports import BirthdayPlan
from app.storage.database import connect, transaction

from .test_birthday_harness_publication import drive_to_freeze_confirmation, harness_env
from .test_birthday_edit_continuation import settle_confirmation
from .test_birthday_runtime_wiring import DELIVER_DATE, _all_freezes
from .test_birthday_session_recovery import target_session
from .test_birthday_session_proof import recover_cached_card


def frozen(env, stage):
    card = drive_to_freeze_confirmation(env)
    source = env.runtime.confirmations.get(
        env.runtime._context(env.who, None, None), card.interaction.record_ref)
    card = settle_confirmation(env, card)
    if stage in {"capture", "paid"}:
        card = settle_confirmation(env, card)
    if stage == "paid":
        settle_confirmation(env, card)
    return source


def plan():
    return BirthdayPlan(payer_account_id="A1", budget_id=None, budget_version=None,
        budget_limit_fen=50000, freeze_amount_fen=50000,
        deliver_by=DELIVER_DATE + "T18:00:00+08:00", delivery_ref="unused-at-ending")


def operations(env):
    with connect(env.runtime.bank.store.path) as connection:
        return [tuple(row) for row in connection.execute(
            "SELECT operation_id, action_name, status FROM bank_operations ORDER BY operation_id")]


def recovery_for_ending(env):
    caller = target_session(env)
    # Provider15 explicitly injects a stale consumer. The real provider still
    # proves retirement and transfers task ownership before refusing that card.
    recover_cached_card(env, caller)
    assert env.runtime.birthday.handoff.session_recovery_status(caller)["status"] == "fresh"
    return caller


@pytest.mark.parametrize("stage", ["order", "capture", "paid"])
def test_new_session_ending_releases_only_unconsumed_funds_and_records_original_source(harness_env, stage):
    env = harness_env
    source = frozen(env, stage)
    caller = recovery_for_ending(env)
    original_actions = deepcopy(env.snapshot()["birthday_actions"])
    ports = env.runtime.birthday.ports_factory(caller)
    before = _all_freezes(env.runtime)[0]
    outcome = ports.finalize(caller, plan(), "user_cancelled")
    assert outcome.status == "released", outcome
    assert outcome.released_amount_fen == before["original_amount_fen"] - before["captured_total_fen"]
    assert outcome.consumed_total_fen == before["captured_total_fen"]
    assert outcome.remaining_fen == 0
    assert env.snapshot()["birthday_actions"] == original_actions
    ending = [event for event in env.runtime.audit._events("D1")
        if event.event_type == "security.decided" and
        event.payload.decision.action_name == "bank.release_frozen"][-1]
    assert ending.payload.decision.decision == "allow"
    ref = ending.payload.decision.authorization_snapshot_ref
    assert ref
    content, metadata = env.runtime.audit._evidence(ending, ref)
    assert metadata and content
    snapshot = AuthorizationSnapshot.model_validate_json(content)
    assert snapshot.session_id == caller.session_id
    assert snapshot.confirmation.confirmation_id == source.confirmation_id
    assert snapshot.confirmation.version == source.confirmation_version
    after = operations(env)
    repeated = ports.finalize(caller, plan(), "user_cancelled")
    assert repeated.status in {"released", "nothing_to_release"}
    assert operations(env) == after
    assert len([row for row in after if row[1] == "bank.release_frozen"]) == 1


def test_missing_original_approval_cannot_submit_release(harness_env):
    env = harness_env
    source = frozen(env, "capture")
    caller = recovery_for_ending(env)
    with transaction(env.runtime.application.path) as connection:
        connection.execute("DELETE FROM security_confirmation_history WHERE confirmation_id=? AND version=?",
            (source.confirmation_id, source.confirmation_version))
        connection.execute("DELETE FROM security_confirmations WHERE confirmation_id=? AND json_extract(confirmation_json, '$.confirmation_version')=?",
            (source.confirmation_id, source.confirmation_version))
    before = operations(env)
    outcome = env.runtime.birthday.ports_factory(caller).finalize(caller, plan(), "user_cancelled")
    assert outcome.status == "needs_attention", outcome
    assert operations(env) == before
    assert _all_freezes(env.runtime)[0]["released_total_fen"] == 0
