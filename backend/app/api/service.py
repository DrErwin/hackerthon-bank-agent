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
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from app.audit.journal import AuditReader, AuditViewer, redact
from app.audit.output_guard import probe_output, probe_secrets
from app.agent_platform.bills_stub import register_bills_stub
from app.agent_platform.model import ContinueProposal, ReplyOnly
from app.agent_platform.input_privacy import has_chat_secret
from app.contracts.audit import (
    AuditAccessedPayload, AuditEvent, ChatMessagePayload, TaskTransitionPayload,
    VerificationChangedPayload,
)
from app.contracts.api import (
    ExportView, MessageView, ReportReady, StreamEvent, TaskRecordsView, VerificationResponse,
)
from app.contracts.bills import BillDetails, BillReport, SpendingSummary
from app.contracts.bank import AccountList, PayeeList
from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.security import ConfirmationView, ExecutionSecurityContext, VerificationView
from app.contracts.subscription import SubscriptionTaskView
from app.contracts.tasks import InteractionRequest, ModuleError, ModuleResult, TaskView, TransferTaskView
from app.memory.adapter import MemoryContext

from .store import ApiProblem, ApiStore, dump


def now():
    return datetime.now(timezone.utc)


# The deployed API serves the one registered business runtime; task views and events
# both name it, so a second module resolves its name here instead of in two places.
SERVED_MODULE = "transfer"

# Contract §6.5: each business module owns its payload schema, so the API keeps a typed
# view for the modules it serves and leaves any other payload opaque to the frontend.
MODULE_TASK_VIEWS = {"transfer": TransferTaskView, "subscription": SubscriptionTaskView}


def task_view_model(module: str | None, capability: str | None = None):
    """The typed task view for one module, or None when its payload stays generic."""

    if module == "transfer":
        if capability == "transfer.list_accounts":
            return AccountList
        if capability == "transfer.list_payees":
            return PayeeList
    return MODULE_TASK_VIEWS.get(module)


@dataclass(frozen=True)
class Identity:
    user_id: str
    session_id: str
    demo_round_id: str
    role: str


def safe_text(text: str, *, numeric_field: bool = False) -> str:
    # Reject recognizable credentials before persistence, model input or SSE.
    if has_chat_secret(text, numeric_field=numeric_field):
        raise ApiProblem(400, "USE_VERIFICATION_ENDPOINT")
    if not text.strip():
        raise ApiProblem(400, "INVALID_ARGUMENT")
    return cast(str, redact(text, free_text=not numeric_field))


def untrusted_material(text: str | None) -> str | None:
    """Sanitize a pasted external datablock (v05-observer-seams/02 compatible extension).

    Unlike `safe_text`, credential-looking words are allowed here: the user may be
    asking about a suspicious message. Only the secret and personal values are
    replaced, and the material is always data, never an instruction.
    """

    if text is None or not text.strip():
        return None
    return cast(str, redact(text, free_text=True))


# v05-observer-seams/04: a reply that carries a credential is replaced whole, not
# partially masked — the probe reports six-digit codes the audit regex cannot remove
# from `probe.text` alone (issue #216). Other personal data is redacted in place.
OUTPUT_BLOCKED_REPLY = "这条回复包含敏感信息，已拦截，未展示原文。请通过银行官方渠道核实后再继续。"
OUTPUT_BLOCKED_MEMORY = "这条记忆包含敏感信息，已隐藏。"


# Contract §6.7: the exporter owns CSV cell safety. Quoting only protects the syntax —
# a cell opening with a formula character would still be evaluated by a spreadsheet, so
# text cells get the literal apostrophe prefix. Non-strings (amounts) keep their type.
CSV_FORMULA_OPENERS = ("=", "+", "-", "@")

# Issue #174: the details export has one frozen header row. Generation and validation
# share this constant so an accepted product can never drift from what we emit.
DETAILS_CSV_HEADER = (
    "occurred_at", "account_id", "direction", "nature", "category", "amount_fen",
    "counterparty_name", "counterparty_account_masked", "channel", "summary",
    "transaction_id",
)


def safe_csv_cell(value):
    """One spreadsheet-literal cell honouring the value's own semantics."""

    if not isinstance(value, str):
        return value
    return f"'{value}" if value.lstrip().startswith(CSV_FORMULA_OPENERS) else value


class ApiService:
    def __init__(self, runtime, config):
        self.runtime, self.config = runtime, config
        self.store = ApiStore(runtime.application.path, config.secret)
        # The platform serves every registered business module; the bills stub
        # keeps the second slot contract-shaped until the real module lands
        # (v04-platform/03). A runtime can back more than one ApiService, and a
        # real bills module replaces the stub — only fill an empty slot.
        if not any(name.startswith("bills.")
                   for name in (entry["name"]
                                for entry in self.runtime.harness.registry.public_catalog())):
            register_bills_stub(self.runtime.harness.registry)
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

    @staticmethod
    def _task_module(task):
        """Contract §6.5: the platform names each task's business module."""
        if task is None:
            return SERVED_MODULE
        capability = task.snapshot.get("capability_name")
        return capability.split(".", 1)[0] if capability else SERVED_MODULE

    def card_source(self, identity, task_id, revision):
        self.link(identity, task_id, mutate=True)
        task = self.runtime.application.get_task(identity.user_id, identity.demo_round_id, task_id)
        if (task is None or task.session_id != identity.session_id or task.revision != revision
                or task.status != TaskStatus.SUCCEEDED):
            raise ApiProblem(409, "REQUEST_CONFLICT")
        return task

    def card_action(self, identity, source_id, body):
        source = self.card_source(identity, source_id, body.source_revision)
        link = self.link(identity, source_id, mutate=True)
        kind = source.snapshot.get("capability_name")
        data = (source.snapshot.get("result") or {}).get("data")
        if body.action == "subscription_cancel":
            if body.category is not None or kind != "subscription.list_subscriptions":
                raise ApiProblem(400, "INVALID_ARGUMENT")
            inventory = SubscriptionTaskView.model_validate(data)
            item = next((row for row in inventory.list_result.items
                         if row.subscription_id == body.subscription_id), None) if inventory.list_result else None
            if (item is None or not item.can_cancel_in_bank or item.source_type != "mandate"
                    or item.status != "active" or not re.fullmatch(r"sub_[A-Za-z0-9_]+", item.mandate_id or "")):
                raise ApiProblem(400, "INVALID_ARGUMENT")
            capability, intent = "subscription.cancel_subscription", "取消 " + item.mandate_id
            parent_id = None
        else:
            if body.subscription_id is not None or (body.action == "bill_check" and body.category is not None):
                raise ApiProblem(400, "INVALID_ARGUMENT")
            if kind == "bills.generate_report":
                BillReport.model_validate(data)
            elif kind == "bills.summarize" and isinstance(data, dict):
                (BillDetails if "transactions" in data else SpendingSummary).model_validate(data)
            else:
                raise ApiProblem(400, "INVALID_ARGUMENT")
            labels = {"dining": "餐饮", "transport": "交通", "medical": "医疗", "shopping": "购物",
                      "housing": "居住", "transfer": "转账", "other": "其他"}
            capability = "bills.summarize" if body.action == "bill_details" else "bills.detect_anomalies"
            intent = "查看" + labels.get(body.category, "账单") + "明细" if body.action == "bill_details" else "核对陌生扣款"
            parent_id = source_id
        task_id = str(uuid5(NAMESPACE_URL, json.dumps([identity.user_id, identity.demo_round_id,
                                                     source_id, str(body.request_id), "card-action"])))
        run_id = str(uuid5(UUID(task_id), "run"))
        self.store.write("""INSERT OR IGNORE INTO api_tasks (
            task_id,thread_id,user_id,session_id,demo_round_id,run_id,created_at,request_id,intent_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (task_id, link["thread_id"], identity.user_id,
                identity.session_id, identity.demo_round_id, run_id, now().isoformat(), str(body.request_id), intent))
        existing = self.runtime.application.get_task(identity.user_id, identity.demo_round_id, task_id)
        if existing is None or "result" not in existing.snapshot:
            trusted = TrustedContext(user_id=identity.user_id, session_id=identity.session_id,
                demo_round_id=identity.demo_round_id, task_id=task_id,
                run_id=existing.run_id if existing else run_id, parent_task_id=parent_id)
            self.runtime.harness.start_selected(trusted, body.request_id, intent, capability)
        task = self.task_view(identity, task_id)
        if task.interaction and task.interaction.record_ref:
            self.store.write("INSERT OR IGNORE INTO api_records VALUES (?, ?, ?)",
                (task.interaction.kind, task.interaction.record_ref, task_id))
        self.emit(identity, task.thread_id, "task_updated", task, task,
                  event_id=str(uuid5(UUID(task_id), "card-updated")))
        if task.interaction:
            from app.contracts.api import InteractionRequired
            self.emit(identity, task.thread_id, "interaction_required",
                InteractionRequired(task_id=task_id, interaction=task.interaction), task,
                event_id=str(uuid5(UUID(task_id), "card-interaction")))
        return task

    def task_view(self, identity, task_id):
        link = self.link(identity, task_id)
        task = self.runtime.application.get_task(identity.user_id, identity.demo_round_id, task_id)
        module = self._task_module(task)
        # A second module's payload is its own displayable result (§6.5); transfer and
        # subscription keep their typed views so existing consumers stay typed.
        model = task_view_model(module, task.snapshot.get("capability_name") if task else None)
        if task and "result" in task.snapshot:
            result = (ModuleResult[model] if model is not None else ModuleResult) \
                .model_validate(task.snapshot["result"])
        else:
            interrupted = task_id not in self.active_tasks
            cancelled = task is None and bool(link["cancel_requested"])
            result = (ModuleResult[model] if model is not None else ModuleResult)(
                task_id=task_id, run_id=task.run_id if task else link["run_id"],
                status=TaskStatus.CANCELLED if cancelled else TaskStatus.RUNNING, data=None,
                message="请求尚未开始处理，已取消。" if cancelled else "正在处理请求。", interaction=None,
                error=None, allowed_actions=[] if cancelled else
                ["resume", "cancel"] if interrupted and task is None else
                ["resume"] if interrupted else ["cancel"] if task is None else [],
                recovery_required=interrupted and not cancelled,
                recovery_reason="INTERRUPTED_REQUEST" if interrupted and not cancelled else None)
        view = (TaskView[model] if model is not None else TaskView)(**result.model_dump(),
            module=module, thread_id=link["thread_id"],
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
        # §6.5/§6.6: a second module's `data` travels in its own `task_updated` event
        # and is interpreted by `module`; the payload union is generic (v04-platform/06).
        return StreamEvent(event_id=event_id or str(uuid4()), thread_id=thread_id,
            session_id=identity.session_id, task_id=task.task_id if task else None,
            run_id=task.run_id if task else None, module=task.module if task else "platform",
            event_type=event_type, occurred_at=now(), payload=payload)

    def emit(self, identity, thread_id, event_type, payload, task=None, event_id=None):
        event = self.stream_event(identity, thread_id, event_type, payload, task, event_id)
        self.store.event(event)
        return event

    def message_view(self, thread_id, text, role, task_id=None, message_id=None,
                     identity=None):
        view_id = message_id or str(uuid4())
        related_task_ids = [task_id] if task_id else []
        if role == "assistant":
            text = self._observed_reply(identity, thread_id, view_id, text, related_task_ids)
        else:
            text = cast(str, redact(text, free_text=True))
        return MessageView(message_id=view_id, thread_id=thread_id, role=role,
            text=text, created_at=now(), task_ids=related_task_ids, report_ids=[])

    def _observed_reply(self, identity, thread_id, message_id, text, related_task_ids):
        """§v05-observer-seams/04: the last output seam before a reply is stored or sent.

        A credential hit replaces the whole reply with fixed safe text; the returned
        `probe.text` is never trusted to hide a no-separator code. Other personal data
        is redacted in place and the business facts stay untouched.
        """

        probe = probe_output(text)
        kinds = [finding.kind for finding in probe.findings]
        if "credential" in kinds:
            self._record_output_probe(identity, thread_id, message_id, related_task_ids,
                                      kinds, "blocked")
            return OUTPUT_BLOCKED_REPLY
        if kinds:
            self._record_output_probe(identity, thread_id, message_id, related_task_ids,
                                      kinds, "redacted")
        return probe.text

    def _record_output_probe(self, identity, thread_id, message_id, related_task_ids,
                             kinds, action):
        """Audit a hit with categories and action only — never the original text."""
        evidence_ref = str(uuid4())
        self.runtime.audit.append(AuditEvent(
            event_id=str(uuid4()), trace_id=str(uuid4()), span_id=str(uuid4()),
            sequence=0, parent_span_id=None, demo_round_id=identity.demo_round_id,
            actor_id=identity.user_id, session_id=identity.session_id,
            target_session_id=None, target_user_id=None, thread_id=thread_id,
            task_id=related_task_ids[0] if len(related_task_ids) == 1 else None,
            run_id=None, module="api", event_type="chat.message", timestamp=now(),
            logical_at=None, outcome="denied",
            evidence_ref=evidence_ref, evidence_status="available", missing_reason=None,
            payload=ChatMessagePayload(message_id=message_id, role="assistant",
                content_ref=evidence_ref, related_task_ids=list(related_task_ids)),
        ), evidence={
            "findings": kinds, "action": action,
            "reason_code": ("OUTPUT_PROBE_BLOCKED" if action == "blocked"
                            else "OUTPUT_PROBE_REDACTED"),
        })

    def message(self, identity, thread_id, text, role, task_id=None, message_id=None,
                report_ids=None):
        message = self.message_view(thread_id, text, role, task_id, message_id,
                                    identity=identity)
        if report_ids:
            message = message.model_copy(update={"report_ids": list(report_ids)})
        self.store.write("INSERT INTO api_messages VALUES (?, ?, ?, ?)",
                         (message.message_id, thread_id, message.created_at.isoformat(), dump(message)))
        self.emit(identity, thread_id, "message_completed", message)
        return message

    def _capture_task_reports(self, identity, task):
        """Store report cards carried by a module result; each report fires once."""
        data = task.data if isinstance(task.data, dict) else None
        if not data or "report_id" not in data:
            return []
        try:
            report = BillReport.model_validate(data)
        except Exception:
            return []
        inserted = self.store.save_report(report, identity, task.task_id,
                                          task.thread_id, now().isoformat())
        return [report.report_id] if inserted else []

    def bill_parent(self, identity, thread_id, task_id=None):
        """Bind the latest completed bill in this chat, never another chat's scope."""
        self.thread(identity, thread_id)
        rows = self.store.rows("""SELECT * FROM api_tasks WHERE thread_id=?
            AND user_id=? AND demo_round_id=? ORDER BY created_at DESC, rowid DESC""",
            (thread_id, identity.user_id, identity.demo_round_id)) if task_id is None else self.store.rows(
            """SELECT * FROM api_tasks WHERE task_id=? AND thread_id=?
            AND user_id=? AND demo_round_id=?""", (task_id, thread_id, identity.user_id, identity.demo_round_id))
        for row in rows:
            if row["session_id"] != identity.session_id:
                continue
            task = self.runtime.application.get_task(identity.user_id, identity.demo_round_id, row["task_id"])
            if (task is not None and task.session_id == identity.session_id and task.status == TaskStatus.SUCCEEDED
                    and task.snapshot.get("capability_name") in {"bills.summarize", "bills.generate_report",
                                                                 "bills.detect_anomalies"}):
                return task.task_id
        return None

    def accept_message_job(self, identity, thread_id, request_id, text, untrusted_content=None):
        message = self.message_view(thread_id, text, "user", identity=identity)
        job = {
            "job_id": str(uuid4()), "candidate_task_id": str(uuid4()),
            "user_message_id": message.message_id, "assistant_message_id": str(uuid4()),
            "thread_id": thread_id, "user_id": identity.user_id,
            "session_id": identity.session_id, "demo_round_id": identity.demo_round_id,
            "run_id": str(uuid4()), "request_id": str(request_id), "intent_text": text,
            "untrusted_content": untrusted_content,
            "parent_task_id": self.bill_parent(identity, thread_id),
            "created_at": message.created_at.isoformat(), "user_event_id": str(uuid4()),
            "assistant_event_id": str(uuid4()), "user_task_event_id": str(uuid4()),
            "task_updated_event_id": str(uuid4()), "interaction_event_id": str(uuid4()),
            "error_event_id": str(uuid4()),
        }
        event = self.stream_event(identity, thread_id, "message_completed", message,
                                  event_id=job["user_event_id"])
        stored, _created = self.store.enqueue_message_job(job, dump(message), dump(event))
        return stored

    def schedule_message_job(self, job_id, background, identity):
        job = self.store.message_job(job_id)
        if job["status"] not in {"queued", "running", "interrupted", "task_linked", "reply_ready", "continuation_ready"}:
            return
        if job_id in self.active_message_jobs:
            return
        if job["session_id"] != identity.session_id:
            if job.get("continuation_json"):
                # A saved candidate is tied to the old session; never rebind its authority.
                self.store.save_message_reply(job_id, "会话已变化，请先查看并恢复原任务，再重新补充信息。")
                self.active_message_jobs.add(job_id)
                background.add_task(self.process_message_job, job_id)
                return
            task = self.runtime.application.get_task(
                identity.user_id, identity.demo_round_id, job["candidate_task_id"],
            )
            if task is not None:
                # Expose the original task for explicit session recovery; do not
                # rerun its model or carry its old authorization into this session.
                original = Identity(job["user_id"], job["session_id"], job["demo_round_id"], "user")
                self.link_message_job_task(job, original, task)
            else:
                # No business task exists yet. The authenticated same-owner replay
                # may continue this message using the current session.
                self.store.write("UPDATE api_message_jobs SET session_id=? WHERE job_id=?",
                                 (identity.session_id, job_id))
        self.active_message_jobs.add(job_id)
        background.add_task(self.process_message_job, job_id)

    def link_message_job_task(self, job, identity, outcome):
        task_id = outcome.task_id
        user_rows = self.store.rows("SELECT view_json FROM api_messages WHERE message_id=?",
                                    (job["user_message_id"],))
        message = MessageView.model_validate(json.loads(user_rows[0]["view_json"]))
        if task_id not in message.task_ids:
            message = message.model_copy(update={"task_ids": [task_id]})
        event = self.stream_event(identity, job["thread_id"], "message_completed", message,
                                  event_id=job["user_task_event_id"])
        self.store.link_message_job_task(job["job_id"], {
            "task_id": task_id, "thread_id": job["thread_id"],
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
                                      task.task_id, job["assistant_message_id"],
                                      identity=identity)
        reports = self._capture_task_reports(identity, task)
        if reports:
            assistant = assistant.model_copy(update={"report_ids": reports})
        events.append(self.stream_event(
            identity, task.thread_id, "message_completed", assistant,
            event_id=job["assistant_event_id"],
        ))
        for report_id in reports:
            # §6.6: the card is named by reference; raw details are never broadcast.
            events.append(self.stream_event(
                identity, task.thread_id, "report_ready",
                ReportReady(task_id=task.task_id, report_id=report_id), task,
            ))
        self.store.complete_task_job(
            job_id, assistant.created_at.isoformat(), dump(assistant),
            [(event.event_id, dump(event)) for event in events],
        )

    def dispatch_continuation(self, job, identity):
        """Persist before dispatch; an interrupted reservation is read back, never rerun."""
        proposal = ContinueProposal.model_validate_json(job["continuation_json"])
        self.identity(self.cookie(identity.session_id))
        link = self.link(identity, proposal.task_id, mutate=True)
        if link["thread_id"] != job["thread_id"]:
            raise ApiProblem(409, "TASK_THREAD_MISMATCH")
        endpoint = "/message-continuation/" + job["job_id"]
        try:
            previous = self.store.receipt(identity, endpoint, job["request_id"], proposal)
        except ApiProblem as error:
            if error.code != "REQUEST_IN_PROGRESS":
                raise
            # We cannot tell whether the prior attempt changed state. Show the original
            # task and require a fresh user action instead of replaying a mutation.
            previous = {"interrupted": True}
        if previous is None:
            task = self.task_view(identity, proposal.task_id)
            try:
                if task.task_revision != proposal.task_revision:
                    raise ApiProblem(409, "TASK_REVISION_STALE")
                read_unknown = proposal.action == "query" and task.recovery_reason == "OPERATION_UNKNOWN"
                if task.recovery_required and not read_unknown:
                    raise ApiProblem(409, "SESSION_RECONFIRMATION_REQUIRED")
                if proposal.action == "revise":
                    if proposal.amount_fen is not None and proposal.amount_fen <= 0:
                        raise ApiProblem(400, "INVALID_AMOUNT")
                    fields = proposal.model_dump(include={"amount_fen", "payee_hint", "payer_account_id"}, exclude_none=True)
                    self.revise_draft(identity, task.task_id, proposal.task_revision, fields, publish=False)
                else:
                    if proposal.action not in task.allowed_actions:
                        raise ApiProblem(409, "ACTION_UNAVAILABLE")
                    if proposal.action == "provide_input":
                        if not task.interaction or task.interaction.kind != "input":
                            raise ApiProblem(409, "INTERACTION_STALE")
                        response = self.input_response(task, proposal)
                    elif proposal.action == "cancel":
                        response = {"query": True} if "query" in task.allowed_actions else {"cancel": True}
                    else:
                        response = {"query": True}
                    self.continue_task(identity, task.task_id, response, publish=False)
            except ApiProblem:
                self.store.finish(identity, endpoint, job["request_id"], {"rejected": True})
                self.store.save_message_reply(job["job_id"], "当前任务已变化或补充内容不适用，请查看原任务卡片后继续。")
                self.publish_message_reply(job)
                return
            self.store.finish(identity, endpoint, job["request_id"], {"completed": True})
        elif previous.get("rejected"):
            self.store.save_message_reply(job["job_id"], "当前任务已变化，请查看原任务卡片后继续。")
            self.publish_message_reply(job)
            return
        current = self.runtime.application.get_task(identity.user_id, identity.demo_round_id, proposal.task_id)
        self.link_message_job_task(job, identity, current)
        self.publish_message_job_task(job["job_id"])

    def process_message_job(self, job_id):
        try:
            with self.mutation_lock:
                job = self.store.message_job(job_id)
                if job["status"] in {"reply_completed", "task_completed", "error_completed"}:
                    return
                if job["status"] == "task_linked":
                    self.publish_message_job_task(job_id)
                    return
                if job["status"] == "reply_ready":
                    self.publish_message_reply(job)
                    return
                if job.get("continuation_json"):
                    identity = Identity(job["user_id"], job["session_id"], job["demo_round_id"], "user")
                    self.dispatch_continuation(job, identity)
                    return
                if job["status"] in {"running", "interrupted"}:
                    task = self.runtime.application.get_task(
                        job["user_id"], job["demo_round_id"], job["candidate_task_id"],
                    )
                    if task is not None:
                        identity = Identity(job["user_id"], job["session_id"], job["demo_round_id"], "user")
                        self.link_message_job_task(job, identity, task)
                        self.publish_message_job_task(job_id)
                        return
                    # A crash may have lost a chat classification. Do not call
                    # the model again and turn the original message into a task.
                    raise RuntimeError("MESSAGE_OUTCOME_UNAVAILABLE")
                self.store.set_message_job_status(job_id, "running")
                identity = Identity(job["user_id"], job["session_id"], job["demo_round_id"], "user")
                trusted = TrustedContext(
                    user_id=job["user_id"], session_id=job["session_id"],
                    demo_round_id=job["demo_round_id"], task_id=job["candidate_task_id"],
                    run_id=job["run_id"], parent_task_id=(self.bill_parent(identity, job["thread_id"],
                        job["parent_task_id"]) if job.get("parent_task_id") else None),
                )
                # The datablock keyword is only passed when a sanitized material exists,
                # so an injected harness stand-in with the older signature keeps working
                # for plain messages (same rule as the harness' context_summary).
                options = ({"untrusted_content": job["untrusted_content"]}
                           if job["untrusted_content"] else {})
                options["allow_continuation"] = True
                outcome = self.runtime.harness.handle_message(
                    trusted, UUID(job["request_id"]), job["intent_text"], **options,
                )
                if isinstance(outcome, ReplyOnly):
                    self.store.save_message_reply(job_id, cast(str, redact(outcome.message, free_text=True)))
                    self.publish_message_reply(job)
                    return
                if isinstance(outcome, ContinueProposal):
                    self.store.save_continuation(job_id, outcome)
                    self.dispatch_continuation(self.store.message_job(job_id), identity)
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
                if job["status"] not in {"task_linked", "reply_ready", "reply_completed", "task_completed", "error_completed"}:
                    self.store.set_message_job_status(job_id, "continuation_ready" if job.get("continuation_json") else "interrupted")
                if job["status"] not in {"reply_completed", "task_completed", "error_completed"}:
                    from app.contracts.tasks import ModuleError
                    self.emit(identity, job["thread_id"], "stream_error", ModuleError(
                        code="DEPENDENCY_UNAVAILABLE", source="platform", field=None,
                        reason="消息处理中断，请重试以恢复原请求。" if platform_task is not None or job.get("continuation_json") or job["status"] in {"reply_ready", "task_linked"}
                            else "无法确定原消息处理结果，请重新发起并核对信息。", upstream_code=None,
                    ), event_id=job["error_event_id"])
                    if platform_task is None and not job.get("continuation_json") and job["status"] not in {"reply_ready", "task_linked"}:
                        self.store.set_message_job_status(job_id, "error_completed")
        finally:
            with self.mutation_lock:
                self.active_message_jobs.discard(job_id)

    def publish_message_reply(self, job):
        text = self.store.rows("SELECT reply_text FROM api_message_replies WHERE job_id=?",
                               (job["job_id"],))[0]["reply_text"]
        identity = Identity(job["user_id"], job["session_id"], job["demo_round_id"], "user")
        assistant = self.message_view(job["thread_id"], text, "assistant",
                                      message_id=job["assistant_message_id"],
                                      identity=identity)
        event = self.stream_event(identity, job["thread_id"], "message_completed", assistant,
                                  event_id=job["assistant_event_id"])
        self.store.complete_reply_job(job["job_id"], assistant.created_at.isoformat(),
                                      dump(assistant), dump(event))

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
        reports = self._capture_task_reports(identity, task)
        self.message(identity, task.thread_id, task.message, "assistant", task_id,
                     report_ids=reports or None)
        for report_id in reports:
            self.emit(identity, task.thread_id, "report_ready",
                      ReportReady(task_id=task_id, report_id=report_id), task)
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

    def capture_report(self, identity, task_id, report):
        """Persist a module-produced report card for its task owner (F21 source of truth)."""
        link = self.link(identity, task_id)
        self.store.save_report(report, identity, task_id, link["thread_id"], now().isoformat())
        return report

    def report(self, identity, report_id):
        """F21: the controlled report card, only inside the caller's own scope."""
        rows = self.store.rows("""SELECT report_json FROM api_reports
            WHERE report_id=? AND user_id=? AND demo_round_id=?""",
            (report_id, identity.user_id, identity.demo_round_id))
        if not rows:
            raise ApiProblem(404, "NOT_FOUND")
        return BillReport.model_validate(json.loads(rows[0]["report_json"]))

    def memory_context(self, identity):
        """§7.6: the same controlled adapter the harness uses, scoped to this session."""
        return MemoryContext(identity.user_id, identity.session_id, identity.demo_round_id)

    def memories(self, identity):
        """F37: only the caller's current-round memories, through the controlled adapter.

        Contents pass the output probe as defence in depth; the memory vocabulary
        already blocks credentials, so this normally changes nothing.
        """

        items = []
        for item in self.runtime.memory.list(self.memory_context(identity)):
            probe = probe_output(item.content)
            content = item.content
            if any(finding.kind == "credential" for finding in probe.findings):
                content = OUTPUT_BLOCKED_MEMORY
            elif probe.findings:
                content = probe.text
            items.append({"memory_id": item.memory_id, "version": item.version,
                          "content": content, "updated_at": item.updated_at})
        return {"items": items, "demo_round_id": identity.demo_round_id}

    def delete_memories(self, identity, request_id, memory_ids, expected_versions):
        """F38: explicit, whole-batch, versioned deletion; the adapter keeps tombstones."""
        result = self.runtime.memory.delete(
            self.memory_context(identity), str(request_id), memory_ids, expected_versions)
        return {"deleted_ids": result.deleted_ids, "deleted_at": result.deleted_at,
                "demo_round_id": result.demo_round_id}

    def create_export(self, identity, report_id, kind):
        """F22: card exports render at once; details exports open a verified platform task."""
        rows = self.store.rows("""SELECT * FROM api_reports
            WHERE report_id=? AND user_id=? AND demo_round_id=?""",
            (report_id, identity.user_id, identity.demo_round_id))
        if not rows:
            raise ApiProblem(404, "NOT_FOUND")
        report = BillReport.model_validate(json.loads(rows[0]["report_json"]))
        if kind == "card":
            export_id = str(uuid4())
            self.store.save_export({"export_id": export_id, "report_id": report_id,
                "kind": "card", "user_id": identity.user_id,
                "demo_round_id": identity.demo_round_id, "session_id": identity.session_id,
                "task_id": None, "challenge_id": None, "thread_id": rows[0]["thread_id"],
                "status": "ready", "created_at": now().isoformat()})
            self.store.finish_export(export_id, "ready",
                file_name=f"bill-report-{report_id}.html", media_type="text/html",
                content=self._card_html(report))
            return self.export_view(self.store.export_row(export_id, identity.user_id,
                                                          identity.demo_round_id))
        existing = self.store.pending_details_export(report_id, identity.user_id,
                                                     identity.demo_round_id,
                                                     identity.session_id)
        if existing:
            return self.export_view(existing)
        export_id, task_id, run_id = str(uuid4()), str(uuid4()), str(uuid4())
        trusted = TrustedContext(user_id=identity.user_id, session_id=identity.session_id,
            demo_round_id=identity.demo_round_id, task_id=task_id, run_id=run_id,
            parent_task_id=None)
        challenge = self.runtime.gateway.create_verification(trusted, "basic_identity")
        result = ModuleResult[TransferTaskView](task_id=task_id, run_id=run_id,
            status=TaskStatus.WAITING_APPROVAL, data=None,
            message="请完成身份验证以导出账单明细。",
            interaction=InteractionRequest(interaction_id=str(uuid4()), kind="verification",
                prompt="请输入验证码完成身份验证，再导出账单明细。",
                required_fields=["code"], options=[], record_ref=challenge.challenge_id),
            error=None, allowed_actions=["cancel"], recovery_required=False, recovery_reason=None)
        # §6.5: the platform names a task's module from the capability prefix, so a
        # sensitive details export is a bills-domain task, not a transfer fallback.
        self.runtime.application.create_task(task_id, identity.user_id, identity.session_id,
            identity.demo_round_id, run_id, TaskStatus.WAITING_APPROVAL,
            {"trace_id": str(uuid4()), "capability_name": "bills.export_details",
             "result": result.model_dump(mode="json")})
        self.store.write("""INSERT INTO api_tasks (
            task_id,thread_id,user_id,session_id,demo_round_id,run_id,created_at,request_id,intent_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, rows[0]["thread_id"], identity.user_id, identity.session_id,
             identity.demo_round_id, run_id, now().isoformat(), export_id, "导出账单明细"))
        self.store.write("INSERT INTO api_records VALUES (?, ?, ?)",
                         ("verification", challenge.challenge_id, task_id))
        self.store.save_export({"export_id": export_id, "report_id": report_id,
            "kind": "details", "user_id": identity.user_id,
            "demo_round_id": identity.demo_round_id, "session_id": identity.session_id,
            "task_id": task_id, "challenge_id": challenge.challenge_id,
            "thread_id": rows[0]["thread_id"], "status": "waiting_verification",
            "created_at": now().isoformat()})
        self.publish_task(identity, task_id)
        return self.export_view(self.store.export_row(export_id, identity.user_id,
                                                      identity.demo_round_id))

    def create_audit_export(self, identity, demo_round_id, task_id):
        """F35: freeze the admin's audit filter and render one redacted evidence package."""
        reader, viewer = self.audit_reader(identity)
        export_id = str(uuid4())
        # The row is written first so the export's own audit.accessed event can point
        # at it; a denied scope closes the row and still leaves the denied event.
        self.store.save_export({"export_id": export_id, "report_id": None, "kind": "audit",
            "user_id": identity.user_id, "demo_round_id": demo_round_id,
            "session_id": identity.session_id, "task_id": task_id, "challenge_id": None,
            "thread_id": None, "status": "preparing", "created_at": now().isoformat()})
        try:
            content = reader.export_json(viewer, demo_round_id, task_id, export_id=export_id)
        except PermissionError:
            self.store.finish_export(export_id, "failed", error_code="ACCESS_DENIED",
                error_reason="没有操作或查看权限。")
            raise
        except Exception:
            # A generation fault closes the row instead of leaving it "preparing".
            self.store.finish_export(export_id, "failed", error_code="DEPENDENCY_UNAVAILABLE",
                error_reason="暂时无法生成审计证据包，导出未完成。")
            raise
        # The file name only carries the server-generated export id, never request text.
        self.store.finish_export(export_id, "ready",
            file_name=f"audit-{export_id}.json", media_type="application/json",
            content=content.decode("utf-8"))
        return self.export_view(self.store.export_row(export_id, identity.user_id,
                                                      identity.demo_round_id))

    def export_view(self, row):
        error = None
        if row["error_code"]:
            error = ModuleError(code=row["error_code"], source="platform", field=None,
                                reason=row["error_reason"] or "", upstream_code=None)
        return ExportView(export_id=row["export_id"], kind=row["kind"], status=row["status"],
            task_id=row["task_id"], file_name=row["file_name"], media_type=row["media_type"],
            download_path=f"/api/v1/exports/{row['export_id']}/download"
                if row["status"] == "ready" else None,
            error=error)

    def export_status(self, identity, export_id):
        """F23: read the export; a waiting details export also refreshes its challenge."""
        row = self.store.export_row(export_id, identity.user_id, identity.demo_round_id)
        if not row:
            raise ApiProblem(404, "NOT_FOUND")
        if row["kind"] == "details" and row["status"] == "waiting_verification":
            self._refresh_waiting_export(row)
            row = self.store.export_row(export_id, identity.user_id, identity.demo_round_id)
        return self.export_view(row)

    def export_file(self, identity, export_id):
        """F24: the file leaves only through the owner, session and verification checks."""
        row = self.store.export_row(export_id, identity.user_id, identity.demo_round_id)
        if not row:
            raise ApiProblem(404, "NOT_FOUND")
        if row["kind"] == "audit":
            # §6.7 F24: an audit download re-checks the independent management identity
            # and reuses the scope frozen at creation: no fresh verification, no session
            # binding. Every attempt on the frozen row is trail-recorded, including refusals.
            if identity.role != "admin":
                self.record_audit_download(identity, row, permitted=False,
                                           reason_code="ACCESS_DENIED")
                raise ApiProblem(403, "ACCESS_DENIED")
            if row["status"] != "ready":
                self.record_audit_download(identity, row, permitted=False,
                                           reason_code="EXPORT_NOT_READY")
                raise ApiProblem(409, "EXPORT_NOT_READY")
        elif row["status"] != "ready":
            raise ApiProblem(409, "EXPORT_NOT_READY")
        elif row["kind"] == "details":
            if row["session_id"] != identity.session_id:
                # §6.7: a session change voids the old export authorization.
                raise ApiProblem(409, "SESSION_RECONFIRMATION_REQUIRED")
            challenge = self.runtime.gateway.get_verification(
                self._export_trusted(row), row["challenge_id"])
            if challenge.challenge_status != "passed":
                raise ApiProblem(409, "EXPORT_NOT_READY")
        # §v05-observer-seams/04: a delivered file must not carry an authentication
        # secret. Only the boolean gate is used here — the file's own personal data is
        # the legitimate export content and stays byte-for-byte (issue #216).
        blocked, _ = probe_secrets(row["content"] or "")
        if blocked:
            self.record_audit_download(identity, row, permitted=False,
                                       reason_code="OUTPUT_PROBE_BLOCKED")
            raise ApiProblem(503, "DEPENDENCY_UNAVAILABLE")
        if row["kind"] == "audit":
            self.record_audit_download(identity, row)
        return row["file_name"], row["media_type"], row["content"]

    def record_audit_download(self, identity, row, *, permitted=True, reason_code="ALLOWED"):
        """§6.8: audit reads leave a trail, and a download names the export it delivered."""
        self.runtime.audit.append(AuditEvent(
            event_id=str(uuid4()), trace_id=str(uuid4()), span_id=str(uuid4()),
            sequence=0, parent_span_id=None, demo_round_id=row["demo_round_id"],
            actor_id=identity.user_id, session_id=identity.session_id,
            target_session_id=None, target_user_id=None, thread_id=None,
            task_id=row["task_id"], run_id=None, module="audit",
            event_type="audit.accessed", timestamp=now(), logical_at=None,
            outcome="succeeded" if permitted else "denied",
            evidence_ref=None, evidence_status="missing",
            missing_reason="download event has no content snapshot",
            payload=AuditAccessedPayload(
                action="download", filter_ref=row["demo_round_id"],
                target_refs=[] if row["task_id"] is None else [row["task_id"]],
                export_id=row["export_id"], permitted=permitted,
                reason_code=reason_code,
            ),
        ))

    def export_for_task(self, identity, task_id):
        rows = self.store.rows("""SELECT * FROM api_exports
            WHERE task_id=? AND user_id=? AND demo_round_id=?""",
            (task_id, identity.user_id, identity.demo_round_id))
        return rows[0] if rows else None

    def export_for_challenge(self, trusted, challenge_id):
        rows = self.store.rows("""SELECT * FROM api_exports
            WHERE challenge_id=? AND user_id=? AND demo_round_id=?""",
            (challenge_id, trusted.user_id, trusted.demo_round_id))
        return rows[0] if rows else None

    def rebind_export_challenge(self, trusted, old_challenge_id, new_challenge):
        """F18: a resend supersedes the old code; the waiting export follows the new one."""
        export = self.export_for_challenge(trusted, old_challenge_id)
        if export is None or export["status"] != "waiting_verification":
            return False
        if new_challenge.challenge_id == old_challenge_id:
            return False
        self._bind_export_challenge(export, new_challenge)
        self.publish_task(Identity(trusted.user_id, trusted.session_id,
                                   trusted.demo_round_id, "user"), export["task_id"])
        return True

    def _bind_export_challenge(self, export, challenge):
        """Point the export row and its task interaction at the current challenge."""
        self.store.write("UPDATE api_exports SET challenge_id=? WHERE export_id=?",
                         (challenge.challenge_id, export["export_id"]))
        task = self.runtime.application.get_task(export["user_id"], export["demo_round_id"],
                                                 export["task_id"])
        result = ModuleResult.model_validate(task.snapshot["result"])
        if result.interaction is not None:
            result = result.model_copy(update={"interaction": result.interaction.model_copy(
                update={"record_ref": challenge.challenge_id})})
        self.runtime.application.update_task(export["user_id"], export["demo_round_id"],
            export["task_id"], task.revision, task.run_id, task.status, task.checkpoint_id,
            {**task.snapshot, "result": result.model_dump(mode="json")})

    def export_verification_result(self, identity, export, challenge):
        """The details export owns its verification outcome instead of the transfer graph."""
        view = self.verification_view(challenge)
        if challenge.challenge_status == "passed":
            self._complete_export(export)
            task = self.task_view(identity, export["task_id"])
            return self.verification_response("verified", view, task, None)
        if challenge.challenge_status != "pending":
            code = ("VERIFICATION_EXPIRED" if challenge.challenge_status == "expired"
                    else "VERIFICATION_REJECTED")
            self._fail_export(export, code=code,
                reason="验证未通过，导出未完成；请重新发起明细导出。",
                task_status=TaskStatus.FAILED, message="验证未通过，账单明细导出未完成。",
                publish=True)
            task = self.task_view(identity, export["task_id"])
            return self.verification_response("rejected", view, task,
                ModuleError(code=code, source="platform", field=None,
                            reason="验证尚未通过。", upstream_code=None))
        # Wrong code with attempts left: the export keeps waiting on the same task.
        task = self.publish_task(identity, export["task_id"])
        return self.verification_response("rejected", view, task,
            ModuleError(code="VERIFICATION_REJECTED", source="bank", field=None,
                        reason="验证尚未通过。", upstream_code=None))

    def fail_export_for_challenge(self, trusted, challenge):
        """A terminal challenge fails its export; returns False for business tasks."""
        export = self.export_for_challenge(trusted, challenge.challenge_id)
        if export is None:
            return False
        code = ("VERIFICATION_EXPIRED" if challenge.challenge_status == "expired"
                else "VERIFICATION_REJECTED")
        self._fail_export(export, code=code,
            reason="验证已失效，导出未完成；请重新发起明细导出。",
            task_status=TaskStatus.FAILED, message="验证已失效，账单明细导出未完成。",
            publish=True)
        return True

    def _export_trusted(self, row):
        owner = Identity(row["user_id"], row["session_id"], row["demo_round_id"], "user")
        return self.trusted(owner, row["task_id"])

    def _refresh_waiting_export(self, row):
        """Lazy state refresh: a passed challenge generates the file, a terminal one fails."""
        challenge = self.runtime.gateway.get_verification(self._export_trusted(row),
                                                          row["challenge_id"])
        if challenge.challenge_status == "passed":
            self._complete_export(row)
            return
        if challenge.challenge_status == "superseded":
            # A resend replaced the code before this row learned about it (crash
            # gap): follow the newest pending challenge instead of failing (F18).
            pending = [item for item in self.runtime.gateway.list_verifications(
                self._export_trusted(row), row["task_id"])
                if item.challenge_status == "pending"]
            if pending:
                challenge = pending[-1]
                self._bind_export_challenge(row, challenge)
        if challenge.challenge_status != "pending":
            code = ("VERIFICATION_EXPIRED" if challenge.challenge_status == "expired"
                    else "VERIFICATION_REJECTED")
            self._fail_export(row, code=code,
                reason="验证已失效，导出未完成；请重新发起明细导出。",
                task_status=TaskStatus.FAILED, message="验证已失效，账单明细导出未完成。",
                publish=False)

    def _complete_export(self, row):
        rows = self.store.rows("""SELECT report_json FROM api_reports
            WHERE report_id=? AND user_id=? AND demo_round_id=?""",
            (row["report_id"], row["user_id"], row["demo_round_id"]))
        report = BillReport.model_validate(json.loads(rows[0]["report_json"]))
        try:
            content = self._details_csv(self._export_trusted(row), report)
        except Exception:
            # Issue #174: a generator fault closes the export out instead of escaping as
            # an HTTP 500 that leaves it stuck in waiting_verification.
            self._fail_export(row, code="EXPORT_GENERATION_FAILED",
                reason="账单明细生成失败，导出未完成。",
                task_status=TaskStatus.FAILED, message="账单明细生成失败，导出未完成。",
                publish=True)
            return
        if content is None:
            self._fail_export(row, code="DEPENDENCY_UNAVAILABLE",
                reason="暂时无法读取账单明细，导出未完成。",
                task_status=TaskStatus.FAILED, message="账单明细读取失败，导出未完成。",
                publish=True)
            return
        if not self._usable_details_csv(content):
            # Issue #174: an interrupted generator can produce an empty or partial file;
            # a ready download must carry the frozen header, exactly like a real bill.
            self._fail_export(row, code="EXPORT_GENERATION_FAILED",
                reason="账单明细生成结果无效，导出未完成。",
                task_status=TaskStatus.FAILED, message="账单明细生成结果无效，导出未完成。",
                publish=True)
            return
        self.store.finish_export(row["export_id"], "ready",
            file_name=f"bill-details-{row['report_id']}.csv", media_type="text/csv",
            content=content)
        self._update_export_task(row, TaskStatus.SUCCEEDED,
                                 "身份验证完成，账单明细已生成，可以下载。", None)
        self.publish_task(Identity(row["user_id"], row["session_id"], row["demo_round_id"], "user"),
                          row["task_id"])

    @staticmethod
    def _usable_details_csv(content) -> bool:
        """A generated export is the frozen header plus optional rows; nothing less."""

        if not isinstance(content, str) or not content.strip():
            return False
        first_line, *_ = content.splitlines()
        return first_line == ",".join(DETAILS_CSV_HEADER)

    def _fail_export(self, row, *, code, reason, task_status, message, publish):
        self.store.finish_export(row["export_id"], "failed", error_code=code, error_reason=reason)
        self._update_export_task(row, task_status, message,
            ModuleError(code=code, source="platform", field=None, reason=reason,
                        upstream_code=None))
        if publish:
            self.publish_task(Identity(row["user_id"], row["session_id"],
                                       row["demo_round_id"], "user"), row["task_id"])

    def _update_export_task(self, row, status, message, error):
        task = self.runtime.application.get_task(row["user_id"], row["demo_round_id"],
                                                 row["task_id"])
        result = ModuleResult[TransferTaskView].model_validate(task.snapshot["result"]) \
            .model_copy(update={"status": status, "interaction": None, "message": message,
                                "error": error, "allowed_actions": [],
                                "recovery_required": False, "recovery_reason": None})
        self.runtime.application.update_task(row["user_id"], row["demo_round_id"], row["task_id"],
            task.revision, task.run_id, status, task.checkpoint_id,
            {**task.snapshot, "result": result.model_dump(mode="json")})

    def _details_csv(self, trusted, report):
        """CSV straight from bank facts inside the report scope; the exporter owns cell safety."""
        import csv
        import io

        rows = []
        for account_id in report.scope.account_ids:
            result = self.runtime.gateway.list_transactions(
                trusted, account_id, report.scope.start_at, report.scope.end_at)
            if result.kind != "ok":
                return None
            rows.extend(result.data.transactions)
        rows.sort(key=lambda item: (item.occurred_at, item.account_id, item.transaction_id))
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(DETAILS_CSV_HEADER)
        for item in rows:
            writer.writerow([safe_csv_cell(item.occurred_at.isoformat()),
                             safe_csv_cell(item.account_id), safe_csv_cell(item.direction),
                             safe_csv_cell(item.nature), safe_csv_cell(item.category),
                             item.amount_fen, safe_csv_cell(item.counterparty_name),
                             safe_csv_cell(item.counterparty_account_masked or ""),
                             safe_csv_cell(item.channel or ""), safe_csv_cell(item.summary),
                             safe_csv_cell(item.transaction_id)])
        return buffer.getvalue()

    def _card_html(self, report):
        """HTML card export; every dynamic value is escaped by the exporter (§6.7)."""
        from html import escape

        def yuan(fen):
            return f"{fen / 100:.2f}"

        categories = "".join(
            f"<tr><td>{escape(str(item.category))}</td><td>{yuan(item.outflow_fen)}</td>"
            f"<td>{yuan(item.refund_fen)}</td><td>{yuan(item.net_fen)}</td></tr>"
            for item in report.summary.categories)
        average = (f"{yuan(report.monthly_average_fen)} 元" if report.monthly_average_fen is not None
                   else "未提供")
        return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>账单报告 {escape(report.report_id)}</title></head>
<body>
<h1>账单报告</h1>
<p>{escape(report.spoken_summary)}</p>
<p>统计范围：{report.scope.start_at.isoformat()} 至 {report.scope.end_at.isoformat()}（账户 {escape(", ".join(report.scope.account_ids))}）</p>
<p>消费总支出 {yuan(report.summary.consumption_gross_fen)} 元，退款 {yuan(report.summary.consumption_refund_fen)} 元，净支出 {yuan(report.summary.consumption_net_fen)} 元；转入 {yuan(report.summary.transfer_in_fen)} 元，转出 {yuan(report.summary.transfer_out_fen)} 元。</p>
<p>交易笔数 {report.summary.transaction_count}；月均 {average}（{escape(report.average_basis)}，统计 {report.statistical_days} 天）。</p>
<table border="1"><thead><tr><th>分类</th><th>支出（元）</th><th>退款（元）</th><th>净额（元）</th></tr></thead>
<tbody>{categories}</tbody></table>
<p>生成时间：{report.generated_at.isoformat()}</p>
</body></html>"""

    @staticmethod
    def _owner_security_context(trusted):
        # Lookup only needs the trusted owner; execution bindings are resolved
        # by TransferRuntime when answering.
        return ExecutionSecurityContext(**trusted.model_dump(exclude={"parent_task_id"}),
            source_task_id=None, operation_id=None, action_revision=None,
            confirmation_id=None, confirmation_version=None,
            verification_ids=[], release_authorization_id=None)

    @staticmethod
    def _confirmation_view(record):
        return ConfirmationView.model_validate(record.model_dump(include=set(ConfirmationView.model_fields)))

    def confirmation(self, identity, confirmation_id):
        trusted = self.record_context(identity, "confirmation", confirmation_id)
        # Read through the public security service.
        record = self.runtime.confirmations.get(self._owner_security_context(trusted), confirmation_id)
        return trusted, self._confirmation_view(record)

    def task_records(self, identity, task_id):
        """Read-only confirmation and verification replay for the task owner."""
        link = self.link(identity, task_id)
        # Replay under the task's own session: history created before a session
        # recovery must still pass the underlying owner checks. The caller has
        # already proven ownership; this path never mutates task or audit facts.
        owner = Identity(identity.user_id, link["session_id"], identity.demo_round_id, "user")
        trusted = self.trusted(owner, task_id)
        context = self._owner_security_context(trusted)
        confirmations = []
        for row in self.store.rows(
            "SELECT record_id FROM api_records WHERE task_id=? AND kind='confirmation'", (task_id,),
        ):
            record = self.runtime.confirmations.get(context, row["record_id"])
            confirmations.append(((record.created_at, record.confirmation_id), self._confirmation_view(record)))
        confirmations.sort(key=lambda item: item[0])
        # Bank errors surface through the shared dependency mapping; unlike the
        # single-challenge read there is no in-flight verification to fault.
        challenges = self.runtime.gateway.list_verifications(trusted, task_id)
        verifications = sorted(
            [((challenge.created_at, challenge.challenge_id), self.verification_view(challenge))
             for challenge in challenges],
            key=lambda item: item[0])
        return TaskRecordsView(task_id=task_id,
                               confirmations=[view for _, view in confirmations],
                               verifications=[view for _, view in verifications])

    def verification(self, identity, challenge_id):
        trusted = self.record_context(identity, "verification", challenge_id)
        try:
            challenge = self.runtime.gateway.get_verification(trusted, challenge_id)
        except Exception as exc:
            if isinstance(exc, PermissionError) or isinstance(exc, ValueError) and str(exc) == "ACCESS_DENIED":
                raise
            self.verification_fault(identity, trusted, challenge_id, None, "lookup")
            raise ApiProblem(503, "DEPENDENCY_UNAVAILABLE") from None
        return trusted, challenge

    @staticmethod
    def verification_view(challenge):
        return VerificationView.model_validate(challenge.model_dump(include=set(VerificationView.model_fields)))

    @staticmethod
    def verification_response(kind, verification, task, error):
        """F07's envelope stays typed for the module that owns the task (§5.6)."""

        model = task_view_model(task.module)
        response = VerificationResponse[model] if model is not None else VerificationResponse
        return response(kind=kind, verification=verification, task=task, error=error)

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

    def verification_fault(self, identity, trusted, challenge_id, submission_id, method):
        task = self.runtime.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
        if task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return
        # §5.6: the fault envelope is rebuilt from whatever the task's own module wrote,
        # so a subscription task is never re-validated as a transfer task.
        model = task_view_model(self._task_module(task))
        result = (ModuleResult[model] if model is not None else ModuleResult) \
            .model_validate(task.snapshot["result"])
        result = result.model_copy(update={
            "status": TaskStatus.NEEDS_ATTENTION, "interaction": None,
            "message": "验证结果待核实，请使用原提交重试；这不是验证未通过。",
            "error": ModuleError(code="DEPENDENCY_UNAVAILABLE", source="bank", field=None,
                                 reason="暂时无法核对验证结果。", upstream_code=None),
            "allowed_actions": ["resume", "cancel"], "recovery_required": True,
            "recovery_reason": "VERIFICATION_OUTCOME_UNKNOWN",
        })
        pending = {"challenge_id": challenge_id,
                   "submission_id": str(submission_id) if submission_id is not None else None,
                   "method": method}
        if method == "lookup" and task.snapshot.get("pending_verification"):
            pending = task.snapshot["pending_verification"]
        snapshot = {**task.snapshot, "result": result.model_dump(mode="json"),
                    "pending_verification": pending}
        self.runtime.application.update_task(trusted.user_id, trusted.demo_round_id, trusted.task_id,
            task.revision, task.run_id, TaskStatus.NEEDS_ATTENTION, task.checkpoint_id, snapshot)
        self.publish_task(identity, trusted.task_id)

    def check_verification_retry(self, trusted, challenge_id, submission_id, method):
        task = self.runtime.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
        pending = task.snapshot.get("pending_verification")
        if pending and pending["method"] != "lookup" and pending != {"challenge_id": challenge_id, "submission_id": str(submission_id), "method": method}:
            raise ApiProblem(409, "ORIGINAL_VERIFICATION_SUBMISSION_REQUIRED")

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

    def continue_task(self, identity, task_id, response, *, recover_session=False, verification_retry=False, publish=True):
        export = self.export_for_task(identity, task_id)
        if export is not None:
            return self.continue_export_task(identity, export, response)
        link = self.link(
            identity, task_id, mutate=True,
            allow_session_recovery=recover_session,
        )
        trusted = self.trusted(
            identity, task_id, new_run=True,
            allow_session_recovery=recover_session,
        )
        task = self.runtime.application.get_task(identity.user_id, identity.demo_round_id, task_id)
        lookup_retry = bool(task and (task.snapshot.get("pending_verification") or {}).get("method") == "lookup")
        if task and task.snapshot.get("pending_verification") and not (verification_retry or lookup_retry) and response.get("cancel") is not True:
            raise ApiProblem(409, "ORIGINAL_VERIFICATION_SUBMISSION_REQUIRED")
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
        if verification_retry or lookup_retry:
            current = self.runtime.application.get_task(identity.user_id, identity.demo_round_id, task_id)
            if current and "pending_verification" in current.snapshot:
                snapshot = {key: value for key, value in current.snapshot.items() if key != "pending_verification"}
                self.runtime.application.update_task(identity.user_id, identity.demo_round_id, task_id,
                    current.revision, current.run_id, current.status, current.checkpoint_id, snapshot)
        return self.publish_task(identity, task_id) if publish else self.task_view(identity, task_id)

    def continue_export_task(self, identity, export, response):
        """§6.7: a sensitive export pauses and resumes along its own platform task."""
        if export["status"] != "waiting_verification":
            return self.task_view(identity, export["task_id"])
        if response.get("cancel") is True:
            self._fail_export(export, code="EXPORT_CANCELLED", reason="已取消账单明细导出。",
                task_status=TaskStatus.CANCELLED, message="已取消账单明细导出。", publish=True)
            return self.task_view(identity, export["task_id"])
        if export["session_id"] != identity.session_id:
            # The challenge is session-bound; a changed session voids the old authorization.
            self._fail_export(export, code="SESSION_RECONFIRMATION_REQUIRED",
                reason="导出验证已随会话变化失效，请重新发起明细导出。",
                task_status=TaskStatus.CANCELLED,
                message="导出验证已随会话变化失效，请重新发起明细导出。", publish=True)
            return self.task_view(identity, export["task_id"])
        self._refresh_waiting_export(export)
        return self.publish_task(identity, export["task_id"])

    def current_input_task(self, identity, task_id, interaction_id):
        """The task whose live input interaction the caller is answering (§6.5)."""

        self.link(identity, task_id, mutate=True)
        task = self.task_view(identity, task_id)
        if not task.interaction or task.interaction.kind != "input" or task.interaction.interaction_id != interaction_id:
            raise ApiProblem(409, "INTERACTION_STALE")
        return task

    def revise_draft(self, identity, task_id, revision, fields, *, publish=True):
        """Edit only the currently owned, unsubmitted ordinary-transfer draft."""
        self.link(identity, task_id, mutate=True)
        task = self.task_view(identity, task_id)
        if task.task_revision != revision:
            raise ApiProblem(409, "TASK_REVISION_STALE")
        if (task.module != "transfer" or task.recovery_required
                or task.status != TaskStatus.WAITING_APPROVAL
                or not task.interaction
                or task.interaction.kind != "confirmation"
                or not isinstance(task.data, TransferTaskView)
                or task.data.operation is not None):
            raise ApiProblem(409, "DRAFT_NOT_EDITABLE")
        if not fields:
            raise ApiProblem(400, "INVALID_ARGUMENT")
        fields = {
            name: safe_text(value, numeric_field=name == "payer_account_id").strip()
            if isinstance(value, str) else value
            for name, value in fields.items()
        }
        # The module generates a new action revision and confirmation. Cancelling
        # the old confirmation would terminate this task, so never answer it here.
        return self.continue_task(identity, task_id, {"fields": fields}, publish=publish)

    def input_response(self, task, request):
        """F10: turn one answer into the response the task's own module expects (§5.6)."""

        interaction = task.interaction
        if task.module == "subscription":
            # S02: the module disambiguates by subscription id, or by the merchant the
            # user named in their own words.
            if request.selected_option_id is not None:
                if request.text is not None or request.selected_option_id not in {
                    item.id for item in interaction.options
                }:
                    raise ApiProblem(400, "INVALID_OPTION")
                return {"selected_option_id": request.selected_option_id}
            if interaction.required_fields == ["merchant_hint"]:
                return {"text": safe_text(request.text)}
            raise ApiProblem(400, "USE_CURRENT_INPUT_FIELDS")
        if request.selected_option_id is not None:
            searches = self.store.rows("SELECT candidates_json FROM api_payee_searches WHERE task_id=? AND interaction_id=?",
                                       (task.task_id, interaction.interaction_id))
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
        if fields == ["payer_account_id"]:
            if text.strip() not in {item.id for item in interaction.options}:
                raise ApiProblem(400, "INVALID_OPTION")
            return {"fields": {"payer_account_id": text.strip()}}
        raise ApiProblem(400, "USE_CURRENT_INPUT_FIELDS")

    def audit_reader(self, identity):
        if identity.role != "admin":
            raise ApiProblem(403, "ACCESS_DENIED")
        def authorize(viewer, action, target_round, target):
            try:
                current = self.identity(self.cookie(viewer.session_id))
                if current.role != "admin" or target_round != current.demo_round_id:
                    return False
                if action in {"list", "export"}:
                    # A round-wide audit export has no task filter; a task-scoped read or
                    # export still has to name a task of the admin's current round.
                    if target is None:
                        return action == "export"
                    return bool(self.store.rows(
                        "SELECT task_id FROM api_tasks WHERE task_id=? AND demo_round_id=?",
                        (target, target_round)))
                return bool(self.store.rows("""SELECT e.event_id FROM audit_events e JOIN api_tasks t
                    ON e.task_id=t.task_id WHERE e.event_id=? AND e.demo_round_id=?
                    AND t.demo_round_id=?""", (target, target_round, target_round)))
            except ApiProblem:
                return False
        return AuditReader(self.runtime.audit, authorize), AuditViewer(identity.user_id, identity.session_id, identity.demo_round_id)
