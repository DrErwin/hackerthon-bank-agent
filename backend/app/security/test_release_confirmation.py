"""Only an already-effective limited release can read its exact old source."""

from datetime import timedelta
import json

import pytest

from app.contracts.security import ConfirmationAnswer
from app.security import ConfirmationService
from app.security.birthday_release import grant_release_authorization
from app.security.gate import SecurityError
from app.security.state import SecurityStateError
from app.security.test_birthday_release import Rig, freeze_action
from app.storage.application import ApplicationStore
from app.storage.database import connect, transaction


def rows(path):
    connection = connect(path)
    try:
        names = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name: sorted((tuple(row) for row in connection.execute('SELECT * FROM "' + name + '"')), key=repr)
                for name in names}
    finally:
        connection.close()


def active(tmp_path):
    rig = Rig(tmp_path)
    record, source, authorization, freeze = rig.active_authorization()
    return rig, record, source, authorization, rig.ending_context(authorization, session_id="S2")


def replace_confirmation(rig, source, record):
    target = source.model_copy(update={"session_id": "S2"})
    return ConfirmationService(rig.path, clock=rig.clock).create(
        target, freeze_action(record.parameters_ref), record.display_fields)


def test_overwritten_source_is_read_exactly_without_rebinding_the_new_session(tmp_path):
    rig, record, source, authorization, target = active(tmp_path)
    try:
        newer = replace_confirmation(rig, source, record)
        assert newer.confirmation_id == record.confirmation_id
        assert newer.confirmation_version == record.confirmation_version + 1
        before, bank = rows(rig.path), rows(rig.bank.store.path)
        read = rig.state.get_release_confirmation(target, authorization.release_authorization_id)
        assert read == record and read.session_id == "S1" and read.decision == "approved"
        assert rows(rig.path) == before and rows(rig.bank.store.path) == bank
        assert rig.state.get_confirmation_history(source, record.confirmation_id) == [record]
        with pytest.raises(SecurityStateError, match="ACCESS_DENIED"):
            rig.state.get_confirmation_history(target, record.confirmation_id, record.confirmation_version)
        confirmations = ConfirmationService(rig.path, clock=rig.clock)
        assert confirmations.get(target, newer.confirmation_id) == newer
        with pytest.raises(SecurityError, match="ACCESS_DENIED"):
            confirmations.answer(source, ConfirmationAnswer(confirmation_id=record.confirmation_id,
                confirmation_version=record.confirmation_version, choice="approve"))
        with pytest.raises(SecurityError, match="ACCESS_DENIED"):
            grant_release_authorization(rig.state, target, read, account_id="BA1", amount_fen=50000, now=rig.clock())
        with pytest.raises(SecurityError, match="OPERATION_CONFLICT"):
            grant_release_authorization(rig.state, source, read, account_id="BA1", amount_fen=50000, now=rig.clock())
        assert rows(rig.path) == before and rows(rig.bank.store.path) == bank
    finally:
        rig.gateway.close()


@pytest.mark.parametrize("status", ["active", "completed"])
def test_effective_source_stays_readable_after_its_original_session_and_card_expire(tmp_path, status):
    rig, record, source, authorization, target = active(tmp_path)
    try:
        if status == "completed":
            rig.state.update_release_authorization(target, authorization.model_copy(update={"status": status}))
        rig.clock.advance(hours=2)
        app = ApplicationStore(rig.path)
        app.create_session("S1", "U1", "D1", record.created_at.isoformat(), record.expires_at.isoformat())
        app.create_session("S2", "U1", "D1", rig.clock().isoformat(), (rig.clock() + timedelta(hours=1)).isoformat())
        before = rows(rig.path)
        assert rig.state.get_release_confirmation(target, authorization.release_authorization_id) == record
        assert rows(rig.path) == before
        assert rig.state.get_release_authorization(target, authorization.release_authorization_id).status == status
    finally:
        rig.gateway.close()


@pytest.mark.parametrize("change", [{"user_id": "U2"}, {"task_id": "OTHER"},
    {"demo_round_id": "D2"}, {"release_authorization_id": "rel_foreign"}, {"release_authorization_id": None}])
def test_foreign_identity_or_context_authorization_cannot_read_the_source(tmp_path, change):
    rig, record, source, authorization, target = active(tmp_path)
    try:
        before = rows(rig.path)
        with pytest.raises(SecurityStateError, match="ACCESS_DENIED"):
            rig.state.get_release_confirmation(target.model_copy(update=change), authorization.release_authorization_id)
        assert rows(rig.path) == before
    finally:
        rig.gateway.close()


@pytest.mark.parametrize("fault", ["missing_authorization", "invalid", "pending_freeze", "missing_source", "duplicate_source"])
def test_missing_invalid_unbound_or_ambiguous_authority_is_refused_without_writes(tmp_path, fault):
    rig, record, source, authorization, target = active(tmp_path)
    try:
        if fault == "invalid":
            rig.state.update_release_authorization(target, authorization.model_copy(update={"status": "invalid"}))
        with transaction(rig.path) as connection:
            if fault == "missing_authorization":
                connection.execute("DELETE FROM security_release_authorizations")
            elif fault == "pending_freeze":
                changed = authorization.model_copy(update={"status": "pending_freeze", "freeze_id": None})
                connection.execute("UPDATE security_release_authorizations SET authorization_json=?", (changed.model_dump_json(),))
            elif fault == "missing_source":
                connection.execute("DELETE FROM security_confirmations")
            elif fault == "duplicate_source":
                connection.execute("INSERT INTO security_confirmation_history VALUES (?, ?, ?, ?)",
                    (record.confirmation_id, record.confirmation_version, record.model_dump_json(), rig.clock().isoformat()))
        before = rows(rig.path)
        with pytest.raises(SecurityStateError):
            rig.state.get_release_confirmation(target, authorization.release_authorization_id)
        assert rows(rig.path) == before
    finally:
        rig.gateway.close()


@pytest.mark.parametrize("location", ["current", "history"])
@pytest.mark.parametrize("change", [{"confirmation_id": "wrong"}, {"confirmation_version": 99},
    {"session_id": "FOREIGN"}, {"user_id": "U2"}, {"task_id": "OTHER"}, {"demo_round_id": "D2"},
    {"operation_id": "different-operation"}, {"action_name": "bank.create_order"}, {"action_revision": 99},
    {"decision": "pending", "decided_at": None},
    {"display_fields": [{"name": "amount", "label": "冻结金额", "value_text": "500元"}]},
    {"decided_at": "2099-01-01T00:00:00Z"}])
def test_corrupt_or_misbound_source_never_becomes_a_release_confirmation(tmp_path, change, location):
    rig, record, source, authorization, target = active(tmp_path)
    try:
        encoded = record.model_dump(mode="json")
        encoded.update(change)
        if location == "history":
            replace_confirmation(rig, source, record)
        with transaction(rig.path) as connection:
            if location == "current":
                connection.execute("UPDATE security_confirmations SET confirmation_json=?", (json.dumps(encoded),))
            else:
                connection.execute("UPDATE security_confirmation_history SET record_json=?", (json.dumps(encoded),))
        before = rows(rig.path)
        with pytest.raises(SecurityStateError):
            rig.state.get_release_confirmation(target, authorization.release_authorization_id)
        assert rows(rig.path) == before
    finally:
        rig.gateway.close()


@pytest.mark.parametrize("change", [{"release_authorization_id": "rel_other"}, {"session_id": "FOREIGN"},
    {"confirmation_id": "other-confirmation"}, {"confirmation_version": 99},
    {"freeze_operation_id": "different-operation"}, {"action_revision": 99}, {"freeze_id": None}])
def test_authorization_binding_must_match_the_exact_original_record(tmp_path, change):
    rig, record, source, authorization, target = active(tmp_path)
    try:
        encoded = authorization.model_dump(mode="json")
        encoded.update(change)
        with transaction(rig.path) as connection:
            connection.execute("UPDATE security_release_authorizations SET authorization_json=?", (json.dumps(encoded),))
        before = rows(rig.path)
        with pytest.raises(SecurityStateError):
            rig.state.get_release_confirmation(target, authorization.release_authorization_id)
        assert rows(rig.path) == before
    finally:
        rig.gateway.close()


def test_legacy_authorization_without_redundant_revision_still_names_one_exact_version(tmp_path):
    rig, record, source, authorization, target = active(tmp_path)
    try:
        encoded = authorization.model_dump(mode="json")
        encoded.pop("action_revision")
        with transaction(rig.path) as connection:
            connection.execute("UPDATE security_release_authorizations SET authorization_json=?", (json.dumps(encoded),))
        replace_confirmation(rig, source, record)
        before = rows(rig.path)
        assert rig.state.get_release_confirmation(target, authorization.release_authorization_id) == record
        assert rows(rig.path) == before
    finally:
        rig.gateway.close()


def test_missing_history_does_not_fall_back_to_a_newer_approved_confirmation(tmp_path):
    rig, record, source, authorization, target = active(tmp_path)
    try:
        newer = replace_confirmation(rig, source, record)
        confirmations = ConfirmationService(rig.path, clock=rig.clock)
        confirmations.answer(source.model_copy(update={"session_id": "S2"}), ConfirmationAnswer(
            confirmation_id=newer.confirmation_id, confirmation_version=newer.confirmation_version, choice="approve"))
        with transaction(rig.path) as connection:
            connection.execute("DELETE FROM security_confirmation_history")
        before = rows(rig.path)
        with pytest.raises(SecurityStateError, match="CONFIRMATION_STALE"):
            rig.state.get_release_confirmation(target, authorization.release_authorization_id)
        assert rows(rig.path) == before
    finally:
        rig.gateway.close()


def test_authorization_and_source_share_one_read_snapshot_without_blocking_a_writer(tmp_path, monkeypatch):
    rig, record, source, authorization, target = active(tmp_path)
    original = rig.state._read_release_authorization
    observed = {}

    def read_then_change(connection, context, identifier):
        result = original(connection, context, identifier)
        assert connection.in_transaction
        # A different real transaction commits while the getter's snapshot is
        # open. The reader must not combine the old authorization with new data.
        rig.state.update_release_authorization(target, authorization.model_copy(update={"status": "invalid"}))
        replace_confirmation(rig, source, record)
        observed["after_writer"] = rows(rig.path)
        return result

    try:
        bank = rows(rig.bank.store.path)
        with monkeypatch.context() as patcher:
            patcher.setattr(rig.state, "_read_release_authorization", read_then_change)
            assert rig.state.get_release_confirmation(target, authorization.release_authorization_id) == record
        assert rows(rig.path) == observed["after_writer"] and rows(rig.bank.store.path) == bank
        with pytest.raises(SecurityStateError, match="POLICY_VIOLATION"):
            rig.state.get_release_confirmation(target, authorization.release_authorization_id)
        assert rows(rig.path) == observed["after_writer"]
    finally:
        rig.gateway.close()
