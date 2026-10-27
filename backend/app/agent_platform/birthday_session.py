"""Same-task session recovery: freeze, prove retirement, link one new attempt."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import UUID

from app.contracts.common import Phase, TaskStatus
from app.security.state import SecurityStateError
from app.services.mock_bank.verification import ChallengeNotRetireable

from .birthday_edit import BirthdayEditError, RESULT_METADATA_KEY, _digest, _validated_result


_RECEIPTS = "birthday_session_recoveries"
ACTION_METADATA_KEY = "birthday_platform_action"
_TERMINAL = {TaskStatus.SUCCEEDED.value, TaskStatus.FAILED.value,
             TaskStatus.CANCELLED.value, TaskStatus.PARTIALLY_SUCCEEDED.value}


def publication_binding(task, result):
    """Only digests enter the sealed checkpoint, never private action values."""
    interaction = result.interaction
    if interaction is None or interaction.kind not in {"confirmation", "verification"}:
        return None
    option = task.snapshot.get("birthday_edit_option") or {}
    action = (task.snapshot.get("birthday_actions") or {}).get(option.get("item"))
    if (option.get("interaction_id") != interaction.interaction_id
            or option.get("kind") != interaction.kind
            or option.get("record_ref") != interaction.record_ref
            or option.get("option_id") not in {item.id for item in interaction.options}
            or not option.get("confirmation_id") or not option.get("confirmation_version")
            or not isinstance(action, dict)
            or action.get("operation_id") != option.get("operation_id")
            or action.get("action_revision") != option.get("action_revision")
            or (action.get("parameters") or {}).get("__action__") != option.get("action_name")):
        return None
    return {"item": option["item"], "action_digest": _digest(action), "option_digest": _digest(option)}


def freeze_source(runtime, trusted, task, published, saved):
    """Read the public sealed result, never the Cross module's private state."""
    result = _validated_result(saved.metadata.get(RESULT_METADATA_KEY), "SOURCE_UNAVAILABLE")
    interaction = result.interaction
    marker = task.snapshot.get("session_recovery") or {}
    if (marker.get("target_session_id") == trusted.session_id
            and marker.get("phase") in {"prepared", "transitioned"}):
        if "birthday_source" not in marker and interaction and interaction.kind in {
                "confirmation", "verification"}:
            raise BirthdayEditError("SOURCE_UNAVAILABLE", "recovery predates its frozen proof")
        frozen = deepcopy(marker.get("birthday_source"))
        if frozen is not None:
            saver = runtime.application.checkpoint_saver(trusted.user_id, trusted.demo_round_id, trusted.task_id)
            original = runtime.birthday.handoff._read_source(saver, frozen["source"], task.checkpoint_thread_id)
            binding = original.metadata.get(ACTION_METADATA_KEY)
            if (not isinstance(binding, dict) or frozen.get("binding") != binding
                    or _digest(frozen["action"]) != binding.get("action_digest")
                    or _digest(frozen["option"]) != binding.get("option_digest")):
                raise BirthdayEditError("SOURCE_UNAVAILABLE", "the frozen action differs from its sealed source")
        return frozen
    if interaction is None or interaction.kind not in {"confirmation", "verification"}:
        return None
    option = task.snapshot.get("birthday_edit_option") or {}
    current = (task.snapshot.get("result") or {}).get("interaction")
    action = (task.snapshot.get("birthday_actions") or {}).get(option.get("item"))
    binding = publication_binding(task, result)
    if (current != interaction.model_dump(mode="json") or binding is None
            or saved.metadata.get(ACTION_METADATA_KEY) != binding):
        raise BirthdayEditError("SOURCE_UNAVAILABLE", "the current action has no exact published binding")
    source = {
        "source_session_id": task.session_id, "target_session_id": trusted.session_id,
        "source_revision": task.revision, "source": deepcopy(published),
        "binding": binding,
        "key": option["item"], "option": deepcopy(option), "action": deepcopy(action),
        "parameters_digest": _digest(action["parameters"]),
    }
    return {**source, "recovery_id": _digest(source)}


def _source(task):
    return (task.snapshot.get("session_recovery") or {}).get("birthday_source")


def _receipt(task, source):
    return (task.snapshot.get(_RECEIPTS) or {}).get(source["recovery_id"])


def _projection(receipt):
    source = receipt["source"]
    option = source["option"]
    return {"status": receipt["status"], "original_operation_id": option["operation_id"],
            "action_name": option["action_name"], "action_revision": option["action_revision"],
            "replacement_operation_id": receipt.get("replacement_operation_id")}


def _completed(runtime, trusted, task, source, receipt):
    current = (task.snapshot.get("birthday_actions") or {}).get(source["key"])
    operation = (receipt.get("replacement_operation_id") if receipt["status"] == "fresh"
                 else source["option"]["operation_id"])
    if (receipt.get("source") != source or _source(task) != source
            or current is None or current.get("operation_id") != operation
            or current.get("parameters") != source["action"]["parameters"]
            or (receipt["status"] == "fresh"
                and source["action"] not in (task.snapshot.get("birthday_attempts") or []))):
        raise BirthdayEditError("TASK_CHANGED")
    if receipt["status"] == "fresh":
        option = source["option"]
        context = runtime._context(trusted, UUID(option["operation_id"]), option["action_revision"])
        sealed = runtime.confirmations.state.get_retirement(
            context, trusted.task_id, UUID(option["operation_id"]), option["action_revision"])
        if (sealed is None or sealed.state != "sealed"
                or sealed.original_binding.get("session_id") != source["source_session_id"]
                or sealed.original_binding.get("recovery_target_session_id") != trusted.session_id):
            raise BirthdayEditError("DEPENDENCY_UNAVAILABLE")
    return _projection(receipt)


def status(runtime, trusted):
    """Only the owned task's completed provider projection reaches Cross."""
    task = runtime._task(trusted)
    source = _source(task)
    receipt = _receipt(task, source) if source is not None else None
    if receipt is None or receipt.get("status") not in {"fresh", "observe"}:
        return None
    return _completed(runtime, trusted, task, source, receipt)


def _context(runtime, trusted, source, marker):
    option = source["option"]
    return runtime._context(trusted, UUID(option["operation_id"]), option["action_revision"]).model_copy(
        update={"confirmation_id": None, "confirmation_version": None,
                "verification_ids": [], "release_authorization_id": None,
                "run_id": marker["target_run_id"]})


def _validator(source, accepted_revision):
    def validate(connection, context, binding):
        row = connection.execute("SELECT * FROM tasks WHERE task_id = ? AND user_id = ? "
            "AND demo_round_id = ?", (context.task_id, context.user_id, context.demo_round_id)).fetchone()
        if (row is None or row["session_id"] != context.session_id
                or row["revision"] != accepted_revision or row["status"] in _TERMINAL):
            return False
        snapshot = json.loads(row["snapshot_json"])
        marker = snapshot.get("session_recovery") or {}
        receipt = (snapshot.get(_RECEIPTS) or {}).get(source["recovery_id"])
        option = source["option"]
        expected = {
            "session_id": source["source_session_id"],
            "recovery_target_session_id": source["target_session_id"],
            "confirmation_id": option["confirmation_id"],
            "confirmation_version": option["confirmation_version"],
            "action_name": option["action_name"], "parameters_ref": option["operation_id"],
            "operation_id": option["operation_id"], "action_revision": option["action_revision"],
            "resource_refs": [], "phase": Phase.EXECUTION.value,
            "run_id": marker.get("target_run_id"), "source_task_id": context.source_task_id,
            "user_id": context.user_id, "demo_round_id": context.demo_round_id,
            "task_id": context.task_id,
        }
        if (marker.get("birthday_source") != source or marker.get("phase") != "transitioned"
                or marker.get("source_session_id") != source["source_session_id"]
                or marker.get("target_session_id") != context.session_id
                or marker.get("expected_revision") != source["source_revision"] + 1
                or receipt is None or receipt.get("source") != source
                or receipt.get("status") != "preparing"
                or receipt.get("accepted_revision") != accepted_revision
                or row["checkpoint_id"] != source["source"]["checkpoint_id"]
                or row["checkpoint_thread_id"] != source["source"]["thread_id"]
                or (snapshot.get("birthday_g3") or {}).get("published_ref") != source["source"]
                or (snapshot.get("birthday_g3") or {}).get("pending") is not None
                or snapshot.get("birthday_edit_option") != option
                or (snapshot.get("birthday_actions") or {}).get(source["key"]) != source["action"]
                or _digest(source["action"]) != source["binding"]["action_digest"]
                or _digest(option) != source["binding"]["option_digest"]
                or _digest(source["action"]["parameters"]) != source["parameters_digest"]
                or any(binding.get(key) != value for key, value in expected.items())):
            return False
        transition = connection.execute("SELECT target_revision FROM task_session_transitions "
            "WHERE task_id = ? AND user_id = ? AND demo_round_id = ? AND source_session_id = ? "
            "AND target_session_id = ? AND source_revision = ?",
            (context.task_id, context.user_id, context.demo_round_id, source["source_session_id"],
             context.session_id, source["source_revision"] + 1)).fetchone()
        if transition is None or transition["target_revision"] + 1 != marker.get("transitioned_revision"):
            return False
        session = connection.execute("SELECT created_at, expires_at FROM sessions WHERE session_id = ? "
            "AND user_id = ? AND demo_round_id = ?",
            (context.session_id, context.user_id, context.demo_round_id)).fetchone()
        now = datetime.now(timezone.utc)
        return session is not None and datetime.fromisoformat(session["created_at"]) <= now < datetime.fromisoformat(session["expires_at"])
    return validate


def _finish(runtime, trusted, source, receipt, *, observed=False):
    task = runtime._task(trusted)
    if task.revision != receipt["accepted_revision"]:
        raise BirthdayEditError("TASK_CHANGED")
    snapshot = task.snapshot
    actions = snapshot.get("birthday_actions") or {}
    if actions.get(source["key"]) != source["action"]:
        raise BirthdayEditError("TASK_CHANGED")
    if observed:
        completed = {**receipt, "status": "observe"}
        changes = {}
    else:
        ports = runtime.birthday.ports_factory(trusted)
        replacement = ports._new_action(trusted, source["action"]["parameters"],
                                        source["action"].get("facts"))
        completed = {**receipt, "status": "fresh",
                     "replacement_operation_id": replacement["operation_id"]}
        changes = {"birthday_actions": {**actions, source["key"]: replacement},
                   "birthday_attempts": [*(snapshot.get("birthday_attempts") or []), source["action"]]}
    receipts = {**(snapshot.get(_RECEIPTS) or {}), source["recovery_id"]: completed}
    try:
        runtime.application.update_task(trusted.user_id, trusted.demo_round_id, trusted.task_id,
            receipt["accepted_revision"], task.run_id, task.status, task.checkpoint_id,
            {**snapshot, **changes, _RECEIPTS: receipts})
    except ValueError as exc:
        latest = runtime._task(trusted)
        winner = _receipt(latest, source)
        if winner is None or winner.get("status") not in {"fresh", "observe"}:
            raise BirthdayEditError("TASK_CHANGED") from exc
        return _completed(runtime, trusted, latest, source, winner)
    return _projection(completed)


def prepare(runtime, trusted, source):
    task = runtime._task(trusted)
    if _source(task) != source:
        raise BirthdayEditError("TASK_CHANGED")
    if source is None:
        return None
    marker = task.snapshot.get("session_recovery") or {}
    if (source["target_session_id"] != trusted.session_id
            or marker.get("phase") != "transitioned"):
        raise BirthdayEditError("ACCESS_DENIED")
    receipt = _receipt(task, source)
    if receipt is not None and receipt.get("status") in {"fresh", "observe"}:
        return _completed(runtime, trusted, task, source, receipt)
    if receipt is None:
        if task.revision != marker.get("transitioned_revision"):
            raise BirthdayEditError("TASK_CHANGED")
        receipt = {"source": source, "status": "preparing", "accepted_revision": task.revision + 1}
        task = runtime.application.update_task(trusted.user_id, trusted.demo_round_id, trusted.task_id,
            task.revision, task.run_id, task.status, task.checkpoint_id,
            {**task.snapshot, _RECEIPTS: {**(task.snapshot.get(_RECEIPTS) or {}), source["recovery_id"]: receipt}})
    validator = _validator(source, receipt["accepted_revision"])
    context = _context(runtime, trusted, source, marker)
    option = source["option"]
    descriptor = runtime.birthday.handoff._descriptor(option)
    try:
        retirement = runtime.confirmations.state.begin_session_retirement(
            context, descriptor, datetime.now(timezone.utc),
            source_session_id=source["source_session_id"],
            source_confirmation_id=option["confirmation_id"],
            source_confirmation_version=option["confirmation_version"],
            recovery_validator=validator)
        evidence = runtime.gateway.retire_action_challenges(trusted,
            operation_id=UUID(option["operation_id"]), action_revision=option["action_revision"])
        runtime.confirmations.state.seal_session_retirement(
            context, retirement.retirement_id, evidence, datetime.now(timezone.utc),
            audit_writer=runtime.audit.append_in_transaction, recovery_validator=validator)
    except SecurityStateError as exc:
        if exc.code == "OPERATION_UNKNOWN":
            return _finish(runtime, trusted, source, receipt, observed=True)
        raise BirthdayEditError(exc.code) from exc
    except ChallengeNotRetireable:
        return _finish(runtime, trusted, source, receipt, observed=True)
    return _finish(runtime, trusted, source, receipt)
