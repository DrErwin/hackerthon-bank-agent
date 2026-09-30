"""Identity and transport coordination over public platform entry points."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import re
from threading import RLock
from typing import cast
from uuid import UUID, uuid4

from app.audit.journal import AuditReader, AuditViewer, redact
from app.contracts.audit import AuditEvent, TaskTransitionPayload, VerificationChangedPayload
from app.contracts.api import MessageView, StreamEvent
from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.security import ConfirmationView, ExecutionSecurityContext, VerificationView
from app.contracts.tasks import ModuleResult, TaskView, TransferTaskView

from .store import ApiProblem, ApiStore, dump


def now():
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Identity:
    user_id: str
    session_id: str
    demo_round_id: str
    role: str


def safe_text(text: str, *, numeric_field: bool = False) -> str:
    # Reject recognizable credentials before persistence, model input or SSE.
    if re.search(r"验证码|短信码|动态码|一次性密码|otp|password|密码|口令|token|bearer|api[_ -]?key", text, re.I) or not numeric_field and re.fullmatch(r"\s*[A-Za-z0-9]{4,8}\s*", text) and re.search(r"\d", text):
        raise ApiProblem(400, "USE_VERIFICATION_ENDPOINT")
    if not text.strip():
        raise ApiProblem(400, "INVALID_ARGUMENT")
    return cast(str, redact(text, free_text=not numeric_field))


class ApiService:
    def __init__(self, runtime, config):
        self.runtime, self.config = runtime, config
        self.store = ApiStore(runtime.application.path, config.secret)
        self.active_tasks: set[str] = set()
        # The supported demo deployment uses one ASGI worker. Harness also locks
        # individual tasks across processes; this lock spans API validation + dispatch.
        self.mutation_lock = RLock()

    def cookie(self, session_id):
        signature = hmac.new(self.config.secret, session_id.encode(), hashlib.sha256).hexdigest()
        return session_id + "." + signature

    def identity(self, cookie):
        try:
            session_id, signature = (cookie or "").split(".")
            if not hmac.compare_digest(self.cookie(session_id).encode(), cookie.encode()):
                raise ValueError()
        except ValueError:
            raise ApiProblem(401, "AUTH_REQUIRED") from None
        rows = self.store.rows("""SELECT s.*, a.role FROM sessions s JOIN api_sessions a
            ON s.session_id=a.session_id WHERE s.session_id=? AND s.demo_round_id=?""",
            (session_id, self.config.demo_round_id))
        if not rows or datetime.fromisoformat(rows[0]["expires_at"]) <= now():
            raise ApiProblem(401, "AUTH_REQUIRED")
        row = rows[0]
        return Identity(row["user_id"], session_id, row["demo_round_id"], row["role"])

    def session_view(self, identity):
        session = self.runtime.application.get_session(identity.user_id, identity.demo_round_id, identity.session_id)
        return {"session_id": session.session_id, "user_display": self.config.user_display
                if identity.role == "user" else "演示管理员", "role": identity.role,
                "demo_round_id": identity.demo_round_id, "created_at": session.created_at,
                "expires_at": session.expires_at}

    def enter(self, cookie, request_id, admin_key):
        role = "user"
        if admin_key is not None:
            if not self.config.admin_key or not hmac.compare_digest(admin_key.encode(), self.config.admin_key.encode()):
                raise ApiProblem(403, "ACCESS_DENIED")
            role = "admin"
        user_id = self.config.demo_user_id if role == "user" else self.config.admin_user_id
        try:
            identity = self.identity(cookie)
            if identity.role != role or identity.user_id != user_id:
                raise ApiProblem(409, "SESSION_ROLE_CONFLICT")
        except ApiProblem as exc:
            if exc.status != 401:
                raise
            identity = Identity(user_id, str(uuid4()), self.config.demo_round_id, role)
        previous = self.store.receipt(identity, "/session/enter", request_id, {"role": role})
        if previous:
            identity = self.identity(self.cookie(previous["session_id"]))
            return identity, previous
        if self.runtime.application.get_session(user_id, identity.demo_round_id, identity.session_id) is None:
            at = now()
            self.runtime.application.create_session(identity.session_id, user_id, identity.demo_round_id,
                                                    at.isoformat(), (at + timedelta(hours=2)).isoformat())
            self.store.write("INSERT INTO api_sessions VALUES (?, ?)", (identity.session_id, role))
        view = self.session_view(identity)
        self.store.finish(identity, "/session/enter", request_id, view)
        return identity, view

    def thread(self, identity, thread_id):
        rows = self.store.rows("SELECT * FROM api_threads WHERE thread_id=? AND user_id=? AND demo_round_id=?",
                               (thread_id, identity.user_id, identity.demo_round_id))
        if not rows:
            raise ApiProblem(404, "NOT_FOUND")
        return rows[0]

    def link(self, identity, task_id, *, mutate=False):
        rows = self.store.rows("SELECT * FROM api_tasks WHERE task_id=? AND user_id=? AND demo_round_id=?",
                               (task_id, identity.user_id, identity.demo_round_id))
        if not rows:
            raise ApiProblem(404, "NOT_FOUND")
        link = rows[0]
        self.thread(identity, link["thread_id"])
        if mutate and link["session_id"] != identity.session_id:
            # The current public Harness cannot rebind an old checkpoint to a new
            # login. Fail closed rather than impersonating its expired session.
            raise ApiProblem(409, "SESSION_RECONFIRMATION_REQUIRED")
        return link

    def trusted(self, identity, task_id, *, new_run=False):
        link = self.link(identity, task_id, mutate=True)
        task = self.runtime.application.get_task(identity.user_id, identity.demo_round_id, task_id)
        return TrustedContext(user_id=identity.user_id, session_id=identity.session_id,
            demo_round_id=identity.demo_round_id, task_id=task_id,
            run_id=str(uuid4()) if new_run else task.run_id if task else link["run_id"], parent_task_id=None)

    def task_view(self, identity, task_id):
        link = self.link(identity, task_id)
        task = self.runtime.application.get_task(identity.user_id, identity.demo_round_id, task_id)
        if task and "result" in task.snapshot:
            result = ModuleResult[TransferTaskView].model_validate(task.snapshot["result"])
        else:
            interrupted = task_id not in self.active_tasks
            cancelled = task is None and bool(link["cancel_requested"])
            result = ModuleResult[TransferTaskView](task_id=task_id, run_id=task.run_id if task else link["run_id"],
                status=TaskStatus.CANCELLED if cancelled else TaskStatus.RUNNING, data=None,
                message="请求尚未开始处理，已取消。" if cancelled else "正在处理请求。", interaction=None,
                error=None, allowed_actions=[] if cancelled else
                ["resume", "cancel"] if interrupted and task is None else
                ["resume"] if interrupted else ["cancel"] if task is None else [],
                recovery_required=interrupted and not cancelled,
                recovery_reason="INTERRUPTED_REQUEST" if interrupted and not cancelled else None)
        view = TaskView[TransferTaskView](**result.model_dump(), thread_id=link["thread_id"],
            demo_round_id=identity.demo_round_id, snapshot_at=now(), task_revision=task.revision if task else int(link["cancel_requested"]),
            cancel_requested=bool(link["cancel_requested"]))
        if "query" in view.allowed_actions and "cancel" not in view.allowed_actions:
            # For an in-flight action, cancel records intent and only queries the
            # original operation. It never promises that the bank can reverse it.
            view.allowed_actions.append("cancel")
        if link["session_id"] != identity.session_id:
            view.allowed_actions = []
            if view.status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
                view.recovery_reason = "SESSION_RECONFIRMATION_REQUIRED"
                view.recovery_required = True
                view.message = "原任务已保留；新登录会话的重新确认与恢复能力尚未提供。"
        return view

    def emit(self, identity, thread_id, event_type, payload, task=None):
        self.store.event(StreamEvent(event_id=str(uuid4()), thread_id=thread_id,
            session_id=identity.session_id, task_id=task.task_id if task else None,
            run_id=task.run_id if task else None, module="transfer" if task else "platform",
            event_type=event_type, occurred_at=now(), payload=payload))

    def message(self, identity, thread_id, text, role, task_id=None, message_id=None):
        message = MessageView(message_id=message_id or str(uuid4()), thread_id=thread_id, role=role,
            text=cast(str, redact(text, free_text=True)), created_at=now(), task_ids=[task_id] if task_id else [], report_ids=[])
        self.store.write("INSERT INTO api_messages VALUES (?, ?, ?, ?)",
                         (message.message_id, thread_id, message.created_at.isoformat(), dump(message)))
        self.emit(identity, thread_id, "message_completed", message)
        return message

    def publish_task(self, identity, task_id):
        task = self.task_view(identity, task_id)
        if task.interaction and task.interaction.record_ref:
            self.store.write("INSERT OR IGNORE INTO api_records VALUES (?, ?, ?)",
                             (task.interaction.kind, task.interaction.record_ref, task_id))
        self.emit(identity, task.thread_id, "task_updated", task, task)
        if task.interaction:
            from app.contracts.api import InteractionRequired
            self.emit(identity, task.thread_id, "interaction_required",
                      InteractionRequired(task_id=task_id, interaction=task.interaction), task)
        self.message(identity, task.thread_id, task.message, "assistant", task_id)
        return task

    def record_context(self, identity, kind, record_id):
        rows = self.store.rows("SELECT task_id FROM api_records WHERE kind=? AND record_id=?", (kind, record_id))
        if not rows:
            raise ApiProblem(404, "NOT_FOUND")
        return self.trusted(identity, rows[0]["task_id"])

    def confirmation(self, identity, confirmation_id):
        trusted = self.record_context(identity, "confirmation", confirmation_id)
        # Read through the public security service. Lookup only needs the trusted
        # owner; execution bindings are resolved by TransferRuntime when answering.
        context = ExecutionSecurityContext(**trusted.model_dump(exclude={"parent_task_id"}),
            source_task_id=None, operation_id=None, action_revision=None,
            confirmation_id=None, confirmation_version=None,
            verification_ids=[], release_authorization_id=None)
        record = self.runtime.confirmations.get(context, confirmation_id)
        return trusted, ConfirmationView.model_validate(record.model_dump(include=set(ConfirmationView.model_fields)))

    def verification(self, identity, challenge_id):
        trusted = self.record_context(identity, "verification", challenge_id)
        challenge = self.runtime.gateway.get_verification(trusted, challenge_id)
        return trusted, challenge

    @staticmethod
    def verification_view(challenge):
        return VerificationView.model_validate(challenge.model_dump(include=set(VerificationView.model_fields)))

    def audit_step(self, actor, trusted, event_type, payload, outcome):
        """An API invocation has its own run; link it to the original task trace."""
        task = self.runtime.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
        link = self.link(Identity(trusted.user_id, trusted.session_id, trusted.demo_round_id, "user"), trusted.task_id)
        self.runtime.audit.append(AuditEvent(
            event_id=str(uuid4()), trace_id=task.snapshot["trace_id"], span_id=str(uuid4()),
            sequence=0, parent_span_id=None, demo_round_id=trusted.demo_round_id,
            actor_id=actor.user_id, session_id=actor.session_id,
            target_session_id=trusted.session_id, target_user_id=trusted.user_id,
            thread_id=link["thread_id"], task_id=trusted.task_id, run_id=str(uuid4()),
            module="api", event_type=event_type, timestamp=now(), logical_at=None,
            outcome=outcome, evidence_ref=None, evidence_status="missing",
            missing_reason="API step has no secret content snapshot", payload=payload,
        ))

    def begin_verification(self, actor, trusted, step, *, terminal_challenge=False):
        self.identity(self.cookie(trusted.session_id))
        task = self.runtime.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
        # A terminal bank challenge can only return a saved submission. Allow
        # that read-only replay if the task finished before the API receipt did.
        if task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED} and not terminal_challenge:
            raise ApiProblem(409, "TASK_TERMINATED")
        self.audit_step(actor, trusted, "task.transition", TaskTransitionPayload(
            previous_status=task.status, status=task.status, plan_revision=None,
            step_id=step, reason_code="API_WRITE_STARTED", checkpoint_ref=None,
        ), "started")

    def record_verification(self, actor, trusted, outcome, method):
        challenge = outcome.challenge
        self.audit_step(actor, trusted, "verification.changed", VerificationChangedPayload(
            challenge_id=challenge.challenge_id, method=method,
            result="passed" if outcome.kind == "verified" else "rejected", purpose=challenge.purpose,
            operation_id=challenge.operation_id, verification_id=outcome.verification_id,
            consecutive_code_failures=challenge.consecutive_code_failures,
            expires_at=challenge.face_expires_at if method == "mock_face" else challenge.code_expires_at,
            reason_code=outcome.reason_code or "VERIFICATION_METHOD_PASSED",
        ), "succeeded" if outcome.kind == "verified" else "denied")

    def continue_task(self, identity, task_id, response):
        trusted = self.trusted(identity, task_id, new_run=True)
        task = self.runtime.application.get_task(identity.user_id, identity.demo_round_id, task_id)
        if task is None:
            link = self.link(identity, task_id, mutate=True)
            if not link["cancel_requested"]:
                self.runtime.harness.start(trusted, UUID(link["request_id"]), link["intent_text"])
        else:
            self.runtime.harness.resume(trusted, response)
        return self.publish_task(identity, task_id)

    def current_interaction(self, identity, task_id, interaction_id):
        self.link(identity, task_id, mutate=True)
        task = self.task_view(identity, task_id)
        if not task.interaction or task.interaction.kind != "input" or task.interaction.interaction_id != interaction_id:
            raise ApiProblem(409, "INTERACTION_STALE")
        return task.interaction

    def input_response(self, task_id, interaction, request):
        if request.selected_option_id is not None:
            searches = self.store.rows("SELECT candidates_json FROM api_payee_searches WHERE task_id=? AND interaction_id=?",
                                       (task_id, interaction.interaction_id))
            if searches and interaction.required_fields == ["payee_hint"]:
                candidates = json.loads(searches[0]["candidates_json"])
                if request.text is not None or request.selected_option_id not in {item["payee_id"] for item in candidates}:
                    raise ApiProblem(400, "INVALID_OPTION")
                return {"fields": {"payee_input": {"kind": "saved", "payee_id": request.selected_option_id}}}
            if request.text is not None or request.selected_option_id not in {item.id for item in interaction.options}:
                raise ApiProblem(400, "INVALID_OPTION")
            if interaction.required_fields == ["payer_account_id"]:
                return {"fields": {"payer_account_id": request.selected_option_id}}
            return {"choice": request.selected_option_id}
        fields = interaction.required_fields
        amount_field = fields == ["amount_fen"] or not fields and {item.id for item in interaction.options} <= {"cancel"}
        text = safe_text(request.text, numeric_field=amount_field)
        if amount_field:
            try:
                amount = Decimal(text.strip().removesuffix("元").strip()) * 100
                if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
                    raise InvalidOperation()
            except InvalidOperation:
                raise ApiProblem(400, "INVALID_AMOUNT") from None
            return {"fields": {"amount_fen": int(amount)}}
        if fields == ["payee_hint"]:
            return {"fields": {"payee_hint": text}}
        raise ApiProblem(400, "USE_CURRENT_INPUT_FIELDS")

    def audit_reader(self, identity):
        if identity.role != "admin":
            raise ApiProblem(403, "ACCESS_DENIED")
        def authorize(viewer, action, target_round, target):
            try:
                current = self.identity(self.cookie(viewer.session_id))
                if current.role != "admin" or target_round != current.demo_round_id:
                    return False
                if action == "list":
                    return bool(self.store.rows("SELECT task_id FROM api_tasks WHERE task_id=? AND demo_round_id=?",
                                               (target, target_round)))
                return bool(self.store.rows("""SELECT e.event_id FROM audit_events e JOIN api_tasks t
                    ON e.task_id=t.task_id WHERE e.event_id=? AND e.demo_round_id=?
                    AND t.demo_round_id=?""", (target, target_round, target_round)))
            except ApiProblem:
                return False
        return AuditReader(self.runtime.audit, authorize), AuditViewer(identity.user_id, identity.session_id, identity.demo_round_id)
