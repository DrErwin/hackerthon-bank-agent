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
from app.agent_platform.model import ReplyOnly
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
        self.active_message_jobs: set[str] = set()
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

    def link(self, identity, task_id, *, mutate=False, allow_session_recovery=False):
        rows = self.store.rows("SELECT * FROM api_tasks WHERE task_id=? AND user_id=? AND demo_round_id=?",
                               (task_id, identity.user_id, identity.demo_round_id))
        if not rows:
            raise ApiProblem(404, "NOT_FOUND")
        link = rows[0]
        self.thread(identity, link["thread_id"])
        if (mutate and link["session_id"] != identity.session_id
                and not allow_session_recovery):
            raise ApiProblem(409, "SESSION_RECONFIRMATION_REQUIRED")
        return link

    def trusted(self, identity, task_id, *, new_run=False, allow_session_recovery=False):
        link = self.link(
            identity, task_id, mutate=True,
            allow_session_recovery=allow_session_recovery,
        )
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
                view.message = "原任务已保留；请通过恢复入口在当前会话重新确认或查询。"
        return view

    def stream_event(self, identity, thread_id, event_type, payload, task=None, event_id=None):
        return StreamEvent(event_id=event_id or str(uuid4()), thread_id=thread_id,
            session_id=identity.session_id, task_id=task.task_id if task else None,
            run_id=task.run_id if task else None, module="transfer" if task else "platform",
            event_type=event_type, occurred_at=now(), payload=payload)

    def emit(self, identity, thread_id, event_type, payload, task=None, event_id=None):
        event = self.stream_event(identity, thread_id, event_type, payload, task, event_id)
        self.store.event(event)
        return event

    def message_view(self, thread_id, text, role, task_id=None, message_id=None):
        return MessageView(message_id=message_id or str(uuid4()), thread_id=thread_id, role=role,
            text=cast(str, redact(text, free_text=True)), created_at=now(),
            task_ids=[task_id] if task_id else [], report_ids=[])

    def message(self, identity, thread_id, text, role, task_id=None, message_id=None):
        message = self.message_view(thread_id, text, role, task_id, message_id)
        self.store.write("INSERT INTO api_messages VALUES (?, ?, ?, ?)",
                         (message.message_id, thread_id, message.created_at.isoformat(), dump(message)))
        self.emit(identity, thread_id, "message_completed", message)
        return message

    def accept_message_job(self, identity, thread_id, request_id, text):
        message = self.message_view(thread_id, text, "user")
        job = {
            "job_id": str(uuid4()), "candidate_task_id": str(uuid4()),
            "user_message_id": message.message_id, "assistant_message_id": str(uuid4()),
            "thread_id": thread_id, "user_id": identity.user_id,
            "session_id": identity.session_id, "demo_round_id": identity.demo_round_id,
            "run_id": str(uuid4()), "request_id": str(request_id), "intent_text": text,
            "created_at": message.created_at.isoformat(), "user_event_id": str(uuid4()),
            "assistant_event_id": str(uuid4()), "user_task_event_id": str(uuid4()),
            "task_updated_event_id": str(uuid4()), "interaction_event_id": str(uuid4()),
            "error_event_id": str(uuid4()),
        }
        event = self.stream_event(identity, thread_id, "message_completed", message,
                                  event_id=job["user_event_id"])
        stored, _created = self.store.enqueue_message_job(job, dump(message), dump(event))
        return stored

    def schedule_message_job(self, job_id, background):
        job = self.store.message_job(job_id)
        if job["status"] not in {"queued", "running", "interrupted", "task_linked"}:
            return
        if job_id in self.active_message_jobs:
            return
        self.active_message_jobs.add(job_id)
        background.add_task(self.process_message_job, job_id)

    def link_message_job_task(self, job, identity, outcome):
        user_rows = self.store.rows("SELECT view_json FROM api_messages WHERE message_id=?",
                                    (job["user_message_id"],))
        message = MessageView.model_validate(json.loads(user_rows[0]["view_json"]))
        if job["candidate_task_id"] not in message.task_ids:
            message = message.model_copy(update={"task_ids": [job["candidate_task_id"]]})
        event = self.stream_event(identity, job["thread_id"], "message_completed", message,
                                  event_id=job["user_task_event_id"])
        self.store.link_message_job_task(job["job_id"], {
            "task_id": job["candidate_task_id"], "thread_id": job["thread_id"],
            "user_id": job["user_id"], "session_id": job["session_id"],
            "demo_round_id": job["demo_round_id"], "run_id": outcome.run_id,
            "created_at": job["created_at"], "request_id": job["request_id"],
            "intent_text": job["intent_text"],
        }, dump(message), dump(event))

    def publish_message_job_task(self, job_id):
        job = self.store.message_job(job_id)
        identity = Identity(job["user_id"], job["session_id"], job["demo_round_id"], "user")
        task = self.task_view(identity, job["task_id"])
        if task.interaction and task.interaction.record_ref:
            self.store.write("INSERT OR IGNORE INTO api_records VALUES (?, ?, ?)",
                             (task.interaction.kind, task.interaction.record_ref, task.task_id))
        events = [self.stream_event(
            identity, task.thread_id, "task_updated", task, task,
            event_id=job["task_updated_event_id"],
        )]
        if task.interaction:
            from app.contracts.api import InteractionRequired
            events.append(self.stream_event(
                identity, task.thread_id, "interaction_required",
                InteractionRequired(task_id=task.task_id, interaction=task.interaction), task,
                event_id=job["interaction_event_id"],
            ))
        assistant = self.message_view(task.thread_id, task.message, "assistant",
                                      task.task_id, job["assistant_message_id"])
        events.append(self.stream_event(
            identity, task.thread_id, "message_completed", assistant,
            event_id=job["assistant_event_id"],
        ))
        self.store.complete_task_job(
            job_id, assistant.created_at.isoformat(), dump(assistant),
            [(event.event_id, dump(event)) for event in events],
        )

    def process_message_job(self, job_id):
        try:
            with self.mutation_lock:
                job = self.store.message_job(job_id)
                if job["status"] in {"reply_completed", "task_completed", "error_completed"}:
                    return
                if job["status"] == "task_linked":
                    self.publish_message_job_task(job_id)
                    return
                self.store.set_message_job_status(job_id, "running")
                identity = Identity(job["user_id"], job["session_id"], job["demo_round_id"], "user")
                trusted = TrustedContext(
                    user_id=job["user_id"], session_id=job["session_id"],
                    demo_round_id=job["demo_round_id"], task_id=job["candidate_task_id"],
                    run_id=job["run_id"], parent_task_id=None,
                )
                outcome = self.runtime.harness.handle_message(
                    trusted, UUID(job["request_id"]), job["intent_text"],
                )
                if isinstance(outcome, ReplyOnly):
                    assistant = self.message_view(
                        job["thread_id"], outcome.message, "assistant",
                        message_id=job["assistant_message_id"],
                    )
                    event = self.stream_event(
                        identity, job["thread_id"], "message_completed", assistant,
                        event_id=job["assistant_event_id"],
                    )
                    self.store.complete_reply_job(
                        job_id, assistant.created_at.isoformat(), dump(assistant), dump(event),
                    )
                    return
                if outcome.error and outcome.error.code == "MODEL_PROPOSAL_FAILED":
                    self.emit(identity, job["thread_id"], "stream_error", outcome.error,
                              event_id=job["error_event_id"])
                    self.store.set_message_job_status(job_id, "error_completed")
                    return
                self.link_message_job_task(job, identity, outcome)
                self.publish_message_job_task(job_id)
        except Exception:
            with self.mutation_lock:
                job = self.store.message_job(job_id)
                identity = Identity(job["user_id"], job["session_id"], job["demo_round_id"], "user")
                platform_task = self.runtime.application.get_task(
                    job["user_id"], job["demo_round_id"], job["candidate_task_id"],
                )
                if platform_task is not None:
                    try:
                        self.link_message_job_task(job, identity, platform_task)
                        self.publish_message_job_task(job_id)
                        return
                    except Exception:
                        # Keep the durable message job retryable if linking or
                        # publishing is interrupted after Harness created a task.
                        job = self.store.message_job(job_id)
                if job["status"] not in {"task_linked", "reply_completed", "task_completed", "error_completed"}:
                    self.store.set_message_job_status(job_id, "interrupted")
                if job["status"] not in {"reply_completed", "task_completed", "error_completed"}:
                    from app.contracts.tasks import ModuleError
                    self.emit(identity, job["thread_id"], "stream_error", ModuleError(
                        code="DEPENDENCY_UNAVAILABLE", source="platform", field=None,
                        reason="消息处理中断，请重试以恢复原请求。", upstream_code=None,
                    ), event_id=job["error_event_id"])
        finally:
            with self.mutation_lock:
                self.active_message_jobs.discard(job_id)

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

    def events_for_session(self, identity, thread_id, cursor):
        """Do not replay old-session task controls into a newly authenticated view."""
        visible = []
        scanned_cursor = cursor
        while True:
            page = self.store.events(thread_id, scanned_cursor)
            if not page:
                break
            scanned_cursor = page[-1]["event_id"]
            visible.extend(event for event in page if not (
                event["session_id"] != identity.session_id
                and event["event_type"] in {"task_updated", "interaction_required"}
            ))
            if visible or len(page) < self.store.EVENT_PAGE_SIZE:
                break
        return visible, scanned_cursor

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

    def continue_task(self, identity, task_id, response, *, recover_session=False):
        link = self.link(
            identity, task_id, mutate=True,
            allow_session_recovery=recover_session,
        )
        trusted = self.trusted(
            identity, task_id, new_run=True,
            allow_session_recovery=recover_session,
        )
        task = self.runtime.application.get_task(identity.user_id, identity.demo_round_id, task_id)
        session_changed = (
            link["session_id"] != identity.session_id
            or task is not None and task.session_id != identity.session_id
        )
        if session_changed and recover_session:
            if task is None:
                if not link["cancel_requested"]:
                    self.runtime.harness.start(
                        trusted, UUID(link["request_id"]), link["intent_text"],
                    )
            else:
                marker = task.snapshot.get("session_recovery")
                already_recovered = (
                    isinstance(marker, dict)
                    and marker.get("target_session_id") == identity.session_id
                    and marker.get("phase") == "complete"
                )
                already_started_here = (
                    task.session_id == identity.session_id and marker is None
                )
                if not already_recovered and not already_started_here:
                    self.runtime.harness.recover_session(trusted)
            current = self.runtime.application.get_task(
                identity.user_id, identity.demo_round_id, task_id,
            )
            self.store.write(
                """UPDATE api_tasks SET session_id=?, run_id=?
                   WHERE task_id=? AND user_id=? AND demo_round_id=?""",
                (identity.session_id, current.run_id if current else trusted.run_id, task_id,
                 identity.user_id, identity.demo_round_id),
            )
        elif task is None:
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
