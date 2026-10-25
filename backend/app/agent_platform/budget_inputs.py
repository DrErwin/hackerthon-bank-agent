"""Private F10 budget provenance; a submission fact, never adoption authority.

Only the authenticated API's dedicated budget path calls ``submit``. Model
continuations keep using ordinary resume. Cross owns the option/attempt/adoption
semantics; its optional reconciliation hook is read-only and has no active origin.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from threading import get_ident
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.contracts.common import TaskStatus
from app.contracts.cross import CrossTaskView
from app.contracts.tasks import ModuleResult


_KEY = "budget_input_origins"


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value):
    return sha256(_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class BudgetInputOrigin:
    """Immutable current-call projection; ``facts`` returns a detached copy."""

    origin_id: str
    input_request_id: str
    dispatch_task_revision: int
    accepted_at: str
    facts_json: str

    @property
    def facts(self):
        return json.loads(self.facts_json)


@dataclass(frozen=True)
class BudgetInputCompletion:
    origin_id: str
    input_request_id: str
    task_revision: int
    result_json: str

    @property
    def result(self):
        return ModuleResult.model_validate_json(self.result_json)


@dataclass(frozen=True)
class BudgetInputRecovery:
    """Cross's exact persisted attempt/result, obtained without re-adoption."""

    attempt_ref: str
    result: ModuleResult


@dataclass
class _Call:
    owner: object
    thread_id: int
    origin_id: str
    request_id: str
    actor: tuple
    active: bool = True


_CURRENT: ContextVar[_Call | None] = ContextVar("budget_input_call", default=None)


def _actor(context):
    return context.user_id, context.session_id, context.demo_round_id, context.task_id


def _projection(record):
    return BudgetInputOrigin(record["origin_id"], record["input_request_id"],
        record["dispatch_task_revision"], record["accepted_at"], _json(record))


def _completion(record):
    complete = record["completion"]
    return BudgetInputCompletion(record["origin_id"], record["input_request_id"],
                                 complete["task_revision"], _json(complete["result"]))


class BudgetInputs:
    def __init__(self, harness):
        self.harness = harness

    @contextmanager
    def suspended(self):
        token = _CURRENT.set(None)
        try:
            yield
        finally:
            _CURRENT.reset(token)

    def _task(self, trusted):
        self.harness._scope(trusted)
        task = self.harness.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
        if task is None:
            raise ValueError("TASK_NOT_FOUND")
        self.harness._check_task(task, trusted)
        return task

    @staticmethod
    def _records(task):
        return deepcopy(task.snapshot.get(_KEY, {}))

    @staticmethod
    def _check_record(record, trusted):
        if (record["user_id"], record["demo_round_id"], record["task_id"]) != (
                trusted.user_id, trusted.demo_round_id, trusted.task_id):
            raise PermissionError("ACCESS_DENIED")

    def stored(self, trusted, input_request_id):
        """Backend lookup for API receipt recovery; does not activate provenance."""
        record = self._records(self._task(trusted)).get(str(UUID(str(input_request_id))))
        if record is not None:
            self._check_record(record, trusted)
        return record

    @staticmethod
    def _candidate(task, interaction_id, selected_option_id):
        if task.snapshot.get("capability_name") != "cross.start_task" or task.status is not TaskStatus.WAITING_INPUT:
            raise ValueError("BUDGET_INPUT_NOT_CURRENT")
        result = ModuleResult.model_validate(task.snapshot["result"])
        interaction = result.interaction
        if (result.status is not TaskStatus.WAITING_INPUT or interaction is None
                or interaction.kind != "input" or interaction.interaction_id != interaction_id
                or selected_option_id not in {item.id for item in interaction.options}):
            raise ValueError("BUDGET_INPUT_NOT_CURRENT")
        try:
            view = CrossTaskView.model_validate(result.data)
        except ValidationError:
            raise ValueError("BUDGET_CANDIDATE_REQUIRED") from None
        if view.budget is None or view.budget.adopted or view.budget.budget_ref is not None:
            raise ValueError("BUDGET_CANDIDATE_REQUIRED")
        candidate = {"plan_revision": view.plan_revision,
            "scope": view.budget.scope.model_dump(mode="json"), "purpose": view.budget.purpose,
            "personal_limit_fen": view.budget.personal_limit_fen}
        return candidate, _digest(task.snapshot["result"])

    def _strict(self, task, record, trusted):
        if (record["phase"] != "accepted" or record["session_id"] != trusted.session_id
                or task.revision != record["dispatch_task_revision"]):
            raise ValueError("BUDGET_INPUT_STALE")
        candidate, binding = self._candidate(task, record["interaction_id"], record["selected_option_id"])
        if binding != record["binding_digest"] or _digest(candidate) != record["candidate_digest"]:
            raise ValueError("BUDGET_INPUT_STALE")

    def current(self, trusted):
        call = _CURRENT.get()
        if (call is None or call.owner is not self or not call.active
                or call.thread_id != get_ident() or call.actor != _actor(trusted)):
            return None
        try:
            task = self._task(trusted)
            record = self._records(task).get(call.request_id)
            if record is None or record["origin_id"] != call.origin_id:
                return None
            self._strict(task, record, trusted)
        except (PermissionError, ValueError):
            return None
        return _projection(record)

    def _entry(self, trusted, task):
        context = self.harness._scope(trusted)
        registration = self.harness.registry.get(task.snapshot["capability_name"])
        return registration.factory(trusted, self.harness.memory.checkpointer(context, trusted.task_id),
                                    self.harness._trace(trusted, task))

    def _reconcile(self, entry, trusted, task, record):
        reconcile = getattr(entry, "reconcile_budget_input", None)
        if reconcile is None:
            return None
        with self.suspended():
            recovery = reconcile(trusted, _projection(record), thread_id=task.checkpoint_thread_id)
        if recovery is not None:
            if not isinstance(recovery, BudgetInputRecovery) or not recovery.attempt_ref:
                raise ValueError("BUDGET_INPUT_RECOVERY_INVALID")
            original = trusted.model_copy(update={"run_id": record["run_id"]})
            self.harness._check_result_scope(recovery.result, original)
        return recovery

    def completed_snapshot(self, task, trusted, result, entry):
        """Called by the existing result CAS: result and completion commit together."""
        snapshot = dict(task.snapshot)
        records = self._records(task)
        if not records:
            return snapshot
        call = _CURRENT.get()
        for key, record in records.items():
            if record["phase"] != "accepted":
                continue
            if (call is not None and call.owner is self and call.active
                    and call.thread_id == get_ident() and call.actor == _actor(trusted)
                    and call.request_id == key and call.origin_id == record["origin_id"]):
                self._strict(task, record, trusted)
                recovery = self._reconcile(entry, trusted, task, record)
                record.update(phase="completed", completion={"result": result.model_dump(mode="json"),
                    "task_revision": task.revision + 1,
                    "attempt_ref": recovery.attempt_ref if recovery is not None else None})
            else:
                record["phase"] = "invalidated"
        snapshot[_KEY] = records
        return snapshot

    def _invalidate(self, task, record):
        records = self._records(task)
        records[record["input_request_id"]]["phase"] = "invalidated"
        self.harness.application.update_task(task.user_id, task.demo_round_id, task.task_id,
            task.revision, task.run_id, task.status, task.checkpoint_id,
            {**task.snapshot, _KEY: records})

    def submit(self, trusted, *, input_request_id, interaction_id, selected_option_id):
        from .harness import _task_lock

        request_id = str(UUID(str(input_request_id)))
        with _task_lock(self.harness.application.path, trusted.task_id):
            task = self._task(trusted)
            records = self._records(task)
            record = records.get(request_id)
            if record is not None:
                self._check_record(record, trusted)
                if (record["interaction_id"], record["selected_option_id"]) != (interaction_id, selected_option_id):
                    raise ValueError("REQUEST_CONFLICT")
                if record["phase"] == "completed":
                    return _completion(record)
                # History is checked before current-input validation: an interrupted
                # adoption may have persisted NEEDS_ATTENTION / interaction=None.
                recovery = self._reconcile(self._entry(trusted, task), trusted, task, record)
                if recovery is not None:
                    record.update(phase="completed", completion={"result": recovery.result.model_dump(mode="json"),
                        "task_revision": task.revision + 1, "attempt_ref": recovery.attempt_ref})
                    records[request_id] = record
                    # Preserve the current plan/terminal status. This is only the
                    # original request's historical response, never a new step.
                    self.harness.application.update_task(task.user_id, task.demo_round_id, task.task_id,
                        task.revision, task.run_id, task.status, task.checkpoint_id,
                        {**task.snapshot, _KEY: records})
                    return _completion(record)
                try:
                    self._strict(task, record, trusted)
                except ValueError:
                    self._invalidate(task, record)
                    raise
            else:
                candidate, binding = self._candidate(task, interaction_id, selected_option_id)
                for prior in records.values():
                    if prior["interaction_id"] == interaction_id:
                        if prior["phase"] == "completed" and prior["selected_option_id"] == selected_option_id:
                            return _completion(prior)
                        raise ValueError("REQUEST_CONFLICT")
                    if prior["phase"] == "accepted":
                        prior["phase"] = "invalidated"
                self.harness._authorize(trusted, task.snapshot["capability_name"])
                record = {"origin_id": str(uuid4()), "accepted_at": datetime.now(timezone.utc).isoformat(),
                    "user_id": trusted.user_id, "session_id": trusted.session_id,
                    "demo_round_id": trusted.demo_round_id, "task_id": trusted.task_id, "run_id": trusted.run_id,
                    "input_request_id": request_id, "endpoint_tag": "budget-f10-input",
                    "interaction_id": interaction_id, "selected_option_id": selected_option_id,
                    "accepted_task_revision": task.revision, "dispatch_task_revision": task.revision + 1,
                    "plan_revision": candidate["plan_revision"], "candidate_snapshot": candidate,
                    "candidate_digest": _digest(candidate), "binding_digest": binding, "phase": "accepted"}
                records[request_id] = record
                self.harness.application.update_task(task.user_id, task.demo_round_id, task.task_id,
                    task.revision, trusted.run_id, task.status, task.checkpoint_id,
                    {**task.snapshot, _KEY: records})
            # Only this exact invocation activates the persisted accepted record.
            # Ordinary resume and history reconciliation never enter this scope.
            dispatch = trusted.model_copy(update={"run_id": record["run_id"]})
            self.harness._authorize(dispatch, task.snapshot["capability_name"])
            current = self._task(dispatch)
            try:
                self._strict(current, record, dispatch)
            except ValueError:
                self._invalidate(current, record)
                raise
            call = _Call(self, get_ident(), record["origin_id"], request_id, _actor(dispatch))
            token = _CURRENT.set(call)
            try:
                self.harness._resume(dispatch, {"choice": selected_option_id})
            finally:
                call.active = False
                _CURRENT.reset(token)
            completed = self._records(self._task(trusted))[request_id]
            if completed["phase"] != "completed":
                raise ValueError("BUDGET_INPUT_INCOMPLETE")
            return _completion(completed)
