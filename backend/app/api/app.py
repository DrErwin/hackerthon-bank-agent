"""Run with uvicorn app.api.app:app; see README for trusted runtime configuration."""

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import asyncio
import importlib
import json
import os
import sqlite3
from typing import Literal
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import Field

from app.contracts.api import (
    ConfirmationAnswerRequest, MessageAccepted, PayeeDetailsFields, PayeeSearchFields, ProvideInputRequest, RequestIdOnly,
    SendMessageRequest, SessionExpired, StreamEvent, SubmitDetailsRequest, VerificationCodeRequest,
)
from app.contracts.bank import ManualPayee, QueryFailure
from app.contracts.common import Category, DisplayField, PositiveInt, PositiveMoney, TaskStatus
from app.contracts.security import ConfirmationAnswer
from app.contracts.tasks import ModuleError, TransferTaskView
from app.services.mock_bank.verification import AdminContext

from .service import ApiService, now, safe_text, untrusted_material
from .store import ApiProblem, dump


COOKIE = "bank_session"


@dataclass(frozen=True)
class ApiConfig:
    secret: bytes = field(repr=False)
    demo_user_id: str = "U1"
    user_display: str = "演示用户"
    demo_round_id: str = "D1"
    admin_user_id: str = "demo-admin"
    admin_key: str | None = field(default=None, repr=False)
    origins: tuple[str, ...] = ("http://127.0.0.1:8000", "http://localhost:8000")
    secure_cookie: bool = False

    def __post_init__(self):
        if len(self.secret) < 32:
            raise ValueError("BANK_API_SECRET must contain at least 32 bytes")


class FaceAnswer(RequestIdOnly):
    submission_id: UUID
    demo_round_id: str
    result: Literal["passed", "failed"]


class MessageRequest(SendMessageRequest):
    """F11 compatible extension (contract §8): a pasted external datablock.

    It travels with the user's own question, is sanitized before storage or model
    input, and is always data — never an instruction or an authorization.
    """

    untrusted_content: str | None = Field(default=None, max_length=8000)


class ExportRequest(RequestIdOnly):
    kind: Literal["card", "details"]


class ReviseDraftRequest(RequestIdOnly):
    """Compatible task draft extension; never carries approval or credentials."""

    task_revision: PositiveInt
    amount_fen: PositiveMoney | None = None
    payer_account_id: str | None = Field(default=None, min_length=1, max_length=100)
    payee_hint: str | None = Field(default=None, min_length=1, max_length=100)
    payee_id: str | None = Field(default=None, min_length=1, max_length=200)


class AuditExportRequest(RequestIdOnly):
    demo_round_id: str
    task_id: str | None = None


class CardActionRequest(RequestIdOnly):
    source_revision: PositiveInt
    action: Literal["bill_details", "bill_check", "bill_range", "subscription_cancel", "refresh_query"]
    category: Category | None = None
    subscription_id: str | None = Field(default=None, min_length=1, max_length=200)
    transaction_id: str | None = Field(default=None, min_length=1, max_length=200)
    account_id: str | None = Field(default=None, min_length=1, max_length=200)
    month: str | None = Field(default=None, pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")


class MemoriesDeleteRequest(RequestIdOnly):
    # §7.6 F38; a duplicate id or a non-positive version is rejected by the adapter
    # as INVALID_ARGUMENT, so the local model only names the controlled inputs.
    memory_ids: list[str]
    expected_versions: dict[str, int]


def problem(exc):
    if isinstance(exc, ApiProblem):
        status, code = exc.status, exc.code
    else:
        code = str(exc) if isinstance(exc, (ValueError, PermissionError, TimeoutError)) else "DEPENDENCY_UNAVAILABLE"
        # The bank keeps its own conflict detail; the public contract exposes the
        # frozen 409 code for an operation-record conflict.
        code = {"VERIFICATION_SUBMISSION_CONFLICT": "REQUEST_CONFLICT"}.get(code, code)
        status = {"ACCESS_DENIED": 403, "AUTH_REQUIRED": 401, "TASK_NOT_FOUND": 404,
                  "INVALID_ARGUMENT": 400, "TASK_TERMINATED": 409, "MODEL_CONFIG_CHANGED": 409,
                  "TASK_BUSY": 409, "STALE_ROUND": 409, "MEMORY_VERSION_CONFLICT": 409}.get(
                      code, 409 if code.startswith(("CONFIRMATION_", "CHALLENGE_", "SUBMISSION_", "REQUEST_")) else 503)
        if status == 503:
            code = "DEPENDENCY_UNAVAILABLE"
    reasons = {401: "演示登录已过期，请重新进入。", 403: "没有操作或查看权限。",
               404: "当前用户范围内找不到该记录。", 409: "请求已失效或与当前状态冲突，请刷新任务。",
               400: "请核对输入并使用对应的专用入口。", 503: "服务暂不可用，原任务结果待核实，请查询原任务后再继续。"}
    return status, {"error": ModuleError(code=code, source="platform", field=None,
                                        reason=reasons[status], upstream_code=None).model_dump(mode="json")}


def success(value, status=200):
    return JSONResponse({"data": jsonable_encoder(value)}, status_code=status,
                        headers={"Cache-Control": "no-store"})


def create_app(runtime=None, config=None):
    @asynccontextmanager
    async def lifespan(application):
        if not hasattr(application.state, "api"):
            factory_path = os.environ.get("BANK_RUNTIME_FACTORY")
            if not factory_path:
                raise RuntimeError("Set BANK_RUNTIME_FACTORY=module:function to a trusted TransferRuntime factory")
            module, name = factory_path.split(":", 1)
            configured_runtime = getattr(importlib.import_module(module), name)()
            configured = config or ApiConfig(
                secret=os.environ.get("BANK_API_SECRET", "").encode(),
                demo_round_id=os.environ.get("BANK_DEMO_ROUND", "D1"),
                admin_key=os.environ.get("BANK_ADMIN_KEY"),
                origins=tuple(os.environ.get("BANK_API_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")),
                secure_cookie=os.environ.get("BANK_COOKIE_SECURE") == "1",
            )
            application.state.api = ApiService(configured_runtime, configured)
        try:
            yield
        finally:
            application.state.api.runtime.close()

    application = FastAPI(title="AI Banking Agent", lifespan=lifespan)
    if runtime is not None:
        if config is None:
            raise ValueError("ApiConfig is required with an injected runtime")
        application.state.api = ApiService(runtime, config)

    @application.middleware("http")
    async def same_origin(request, call_next):
        if request.method == "POST" and request.url.path.startswith("/api/v1/"):
            service = request.app.state.api
            if request.headers.get("origin") not in service.config.origins:
                status, body = problem(ApiProblem(403, "ORIGIN_DENIED"))
                return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})
        return await call_next(request)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # FastAPI's default error includes rejected inputs, possibly an OTP.
        return JSONResponse(problem(ApiProblem(400, "INVALID_ARGUMENT"))[1], status_code=400,
                            headers={"Cache-Control": "no-store"})

    async def error_handler(request, exc):
        status, body = problem(exc)
        return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})

    for exception in (ApiProblem, ValueError, PermissionError, TimeoutError, sqlite3.Error, RuntimeError, KeyError, OSError):
        application.add_exception_handler(exception, error_handler)

    def api(request: Request):
        return request.app.state.api

    def identity(request: Request, service=Depends(api)):
        return service.identity(request.cookies.get(COOKIE))

    def mutation(service, who, request, body, action, *, status=200, fingerprint=None,
                 recover_verification=False, retry_interrupted=False, on_replay=None):
        with service.mutation_lock:
            # Recheck after a potentially long wait for another operation.
            service.identity(service.cookie(who.session_id))
            previous = service.store.receipt(who, request.url.path, body.request_id,
                                             body if fingerprint is None else fingerprint,
                                             recover_verification=recover_verification,
                                             retry_interrupted=retry_interrupted)
            if previous is not None:
                if on_replay is not None:
                    on_replay()
                return JSONResponse(previous["body"], status_code=previous["status"], headers={"Cache-Control": "no-store"})
            try:
                value = action()
                response = {"status": status, "body": {"data": jsonable_encoder(value)}}
            except Exception as exc:
                error_status, error_body = problem(exc)
                response = {"status": error_status, "body": error_body}
            service.store.finish(who, request.url.path, body.request_id, response)
            return JSONResponse(response["body"], status_code=response["status"], headers={"Cache-Control": "no-store"})

    @application.post("/api/v1/session/enter")
    def enter(request: Request, body: RequestIdOnly, service=Depends(api)):
        with service.mutation_lock:
            who, view = service.enter(request.cookies.get(COOKIE), body.request_id, request.headers.get("X-Demo-Admin-Key"))
        response = success(view)
        response.set_cookie(COOKIE, service.cookie(who.session_id), httponly=True, samesite="strict",
                            secure=service.config.secure_cookie, max_age=7200, path="/api/v1")
        return response

    @application.get("/api/v1/session")
    def session(who=Depends(identity), service=Depends(api)):
        return success(service.session_view(who))

    @application.post("/api/v1/tasks/{task_id}/actions")
    def card_action(request: Request, task_id: str, body: CardActionRequest,
                    who=Depends(identity), service=Depends(api)):
        # Recheck source ownership/session even when replaying a saved receipt.
        service.card_source(who, task_id, body.source_revision)
        return mutation(service, who, request, body,
            lambda: service.card_action(who, task_id, body), retry_interrupted=True)

    @application.post("/api/v1/threads")
    def new_thread(request: Request, body: RequestIdOnly, who=Depends(identity), service=Depends(api)):
        def action():
            at = now().isoformat()
            view = {"thread_id": str(uuid4()), "title": "新对话", "created_at": at, "updated_at": at,
                    "demo_round_id": who.demo_round_id}
            service.store.write("INSERT INTO api_threads VALUES (?, ?, ?, ?, ?)",
                                (view["thread_id"], who.user_id, who.demo_round_id, at, dump(view)))
            return view
        return mutation(service, who, request, body, action)

    @application.get("/api/v1/threads")
    def threads(cursor: str | None = None, limit: int = Query(50, ge=1, le=100), who=Depends(identity), service=Depends(api)):
        rows = service.store.rows("SELECT * FROM api_threads WHERE user_id=? AND demo_round_id=? ORDER BY created_at, thread_id", (who.user_id, who.demo_round_id))
        return success(service.store.page([((r["created_at"], r["thread_id"]), json.loads(r["view_json"])) for r in rows], who, "threads", cursor, limit))

    @application.post("/api/v1/threads/{thread_id}/messages", status_code=202)
    def send(request: Request, thread_id: str, body: MessageRequest, background: BackgroundTasks,
             who=Depends(identity), service=Depends(api)):
        service.thread(who, thread_id)
        text = safe_text(body.text)
        material = untrusted_material(body.untrusted_content)
        def action():
            job = service.accept_message_job(who, thread_id, body.request_id, text, material)
            service.schedule_message_job(job["job_id"], background, who)
            return MessageAccepted(
                message_id=job["user_message_id"], thread_id=thread_id,
                accepted_at=job["created_at"], task_id=None,
            )
        def replay():
            job = service.store.message_job_for_request(who, thread_id, body.request_id)
            if job:
                service.schedule_message_job(job["job_id"], background, who)
        return mutation(service, who, request, body, action, status=202,
                        retry_interrupted=True, on_replay=replay)

    @application.get("/api/v1/threads/{thread_id}/messages")
    def messages(thread_id: str, cursor: str | None = None, limit: int = Query(50, ge=1, le=100), who=Depends(identity), service=Depends(api)):
        service.thread(who, thread_id)
        rows = service.store.rows("SELECT * FROM api_messages WHERE thread_id=? ORDER BY created_at, message_id", (thread_id,))
        return success(service.store.page([((r["created_at"], r["message_id"]), json.loads(r["view_json"])) for r in rows], who, f"messages:{thread_id}", cursor, limit))

    @application.get("/api/v1/memories")
    def memories(who=Depends(identity), service=Depends(api)):
        return success(service.memories(who))

    @application.post("/api/v1/memories/delete")
    def delete_memories(request: Request, body: MemoriesDeleteRequest,
                        who=Depends(identity), service=Depends(api)):
        def action():
            return service.delete_memories(who, body.request_id, body.memory_ids,
                                           body.expected_versions)
        return mutation(service, who, request, body, action)

    @application.get("/api/v1/tasks")
    def tasks(thread_id: str | None = None, recovery_required: bool | None = None, cursor: str | None = None,
              limit: int = Query(50, ge=1, le=100), who=Depends(identity), service=Depends(api)):
        if thread_id:
            service.thread(who, thread_id)
        rows = service.store.rows("SELECT * FROM api_tasks WHERE user_id=? AND demo_round_id=? ORDER BY created_at, task_id", (who.user_id, who.demo_round_id))
        items = []
        for row in rows:
            task = service.task_view(who, row["task_id"])
            if (thread_id is None or row["thread_id"] == thread_id) and (recovery_required is None or task.recovery_required == recovery_required):
                items.append(((row["created_at"], row["task_id"]), task.model_dump(mode="json")))
        return success(service.store.page(items, who, f"tasks:{thread_id}:{recovery_required}", cursor, limit))

    @application.get("/api/v1/tasks/{task_id}")
    def task(task_id: str, who=Depends(identity), service=Depends(api)):
        return success(service.task_view(who, task_id))

    @application.get("/api/v1/tasks/{task_id}/records")
    def records(task_id: str, who=Depends(identity), service=Depends(api)):
        return success(service.task_records(who, task_id))

    @application.get("/api/v1/reports/{report_id}")
    def report(report_id: str, who=Depends(identity), service=Depends(api)):
        return success(service.report(who, report_id))

    @application.post("/api/v1/reports/{report_id}/exports")
    def create_export(request: Request, report_id: str, body: ExportRequest,
                      who=Depends(identity), service=Depends(api)):
        def action():
            return service.create_export(who, report_id, body.kind)
        return mutation(service, who, request, body, action)

    @application.get("/api/v1/exports/{export_id}")
    def export(export_id: str, who=Depends(identity), service=Depends(api)):
        return success(service.export_status(who, export_id))

    @application.get("/api/v1/exports/{export_id}/download")
    def export_download(export_id: str, who=Depends(identity), service=Depends(api)):
        file_name, media_type, content = service.export_file(who, export_id)
        return Response(content=content, media_type=media_type, headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Cache-Control": "no-store"})

    @application.post("/api/v1/tasks/{task_id}/inputs")
    def inputs(request: Request, task_id: str, body: ProvideInputRequest, who=Depends(identity), service=Depends(api)):
        service.link(who, task_id, mutate=True)
        def action():
            task = service.current_input_task(who, task_id, body.interaction_id)
            return service.continue_task(who, task_id, service.input_response(task, body))
        return mutation(service, who, request, body, action)

    @application.post("/api/v1/tasks/{task_id}/draft")
    def revise_draft(request: Request, task_id: str, body: ReviseDraftRequest,
                     who=Depends(identity), service=Depends(api)):
        service.link(who, task_id, mutate=True)
        def action():
            fields = body.model_dump(exclude={"request_id", "task_revision"}, exclude_none=True)
            return service.revise_draft(who, task_id, body.task_revision, fields)
        return mutation(service, who, request, body, action)

    @application.get("/api/v1/tasks/{task_id}/transfer-choices")
    def transfer_choices(task_id: str, kind: Literal["accounts", "payees"],
                         who=Depends(identity), service=Depends(api)):
        task = service.task_view(who, task_id)
        if task.module != "transfer" or not isinstance(task.data, TransferTaskView):
            raise ApiProblem(400, "INVALID_ARGUMENT")
        return success(service.runtime.read_transfer_choices(service.trusted(who, task_id), kind))

    @application.post("/api/v1/tasks/{task_id}/resume")
    @application.post("/api/v1/tasks/{task_id}/cancel")
    @application.post("/api/v1/tasks/{task_id}/query-result")
    def continue_task(request: Request, task_id: str, body: RequestIdOnly, who=Depends(identity), service=Depends(api)):
        command = request.url.path.rsplit("/", 1)[1]
        service.link(
            who, task_id, mutate=True,
            allow_session_recovery=command == "resume",
        )
        def action():
            task = service.task_view(who, task_id)
            if command == "cancel":
                if "cancel" not in task.allowed_actions:
                    raise ApiProblem(409, "ACTION_UNAVAILABLE")
                service.store.write("UPDATE api_tasks SET cancel_requested=1 WHERE task_id=?", (task_id,))
                if service.runtime.application.get_task(who.user_id, who.demo_round_id, task_id) is None:
                    return service.publish_task(who, task_id)
                return service.continue_task(who, task_id, {"query": True} if "query" in task.allowed_actions else {"cancel": True})
            if command == "query-result":
                if "query" not in task.allowed_actions:
                    raise ApiProblem(409, "ACTION_UNAVAILABLE")
                return service.continue_task(who, task_id, {"query": True})
            return service.continue_task(
                who, task_id, {"choice": "resume"}, recover_session=True,
            )
        return mutation(
            service, who, request, body, action,
            retry_interrupted=command == "resume",
        )

    @application.post("/api/v1/tasks/{task_id}/details")
    def details(request: Request, task_id: str, body: SubmitDetailsRequest, who=Depends(identity), service=Depends(api)):
        service.link(who, task_id, mutate=True)
        def action():
            pending = service.current_input_task(who, task_id, body.interaction_id)
            if pending.interaction.required_fields != ["payee_hint"] or body.kind == "delivery":
                raise ApiProblem(409, "DETAILS_NOT_REQUESTED")
            trusted = service.trusted(who, task_id)
            candidates = None
            response = None
            if isinstance(body.fields, PayeeDetailsFields):
                payee = ManualPayee(kind="manual", **body.fields.model_dump())
                revision = service.task_view(who, task_id).task_revision + 1
                checked = service.runtime.payee_references.register(trusted, payee, revision)
                if isinstance(checked, QueryFailure):
                    raise ApiProblem(503, "DEPENDENCY_UNAVAILABLE")
                if not getattr(checked, "reference", None):
                    raise ApiProblem(400, "PAYEE_MISMATCH")
                display = checked.display
                response = {"fields": {"payee_input": {
                    "kind": "reference", "reference": checked.reference,
                    "payee_revision": revision}}}
                fields = [DisplayField(name="payee", label="收款人", value_text=display.name_masked),
                          DisplayField(name="account", label="收款账户", value_text=display.account_masked),
                          DisplayField(name="bank", label="开户行", value_text=display.bank_name)]
            elif isinstance(body.fields, PayeeSearchFields):
                checked = service.runtime.gateway.list_payees(trusted, body.fields.model_dump())
                if isinstance(checked, QueryFailure):
                    raise ApiProblem(503, "DEPENDENCY_UNAVAILABLE")
                candidates = checked.data.payees
                service.store.write("""INSERT INTO api_payee_searches VALUES (?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET interaction_id=excluded.interaction_id,
                    candidates_json=excluded.candidates_json""", (task_id, body.interaction_id,
                                                                dump([item.model_dump(mode="json") for item in candidates])))
                fields = []
            else:
                raise ApiProblem(409, "DETAILS_NOT_REQUESTED")
            ref = str(uuid4())
            service.store.write("INSERT INTO api_records VALUES (?, ?, ?)", ("detail", ref, task_id))
            task = service.task_view(who, task_id) if response is None else service.continue_task(who, task_id, response)
            from app.contracts.api import DetailsResponse
            return DetailsResponse[TransferTaskView](detail_ref=ref, display_fields=fields, candidates=candidates, task=task)
        return mutation(service, who, request, body, action)

    @application.get("/api/v1/confirmations/{confirmation_id}")
    def confirmation(confirmation_id: str, who=Depends(identity), service=Depends(api)):
        return success(service.confirmation(who, confirmation_id)[1])

    @application.post("/api/v1/confirmations/{confirmation_id}/answer")
    def answer(request: Request, confirmation_id: str, body: ConfirmationAnswerRequest, who=Depends(identity), service=Depends(api)):
        trusted, view = service.confirmation(who, confirmation_id)
        def action():
            task = service.task_view(who, trusted.task_id)
            if not task.interaction or task.interaction.record_ref != confirmation_id or view.decision != "pending":
                raise ApiProblem(409, "CONFIRMATION_STALE")
            service.runtime.answer_confirmation(trusted, ConfirmationAnswer(confirmation_id=confirmation_id,
                                                confirmation_version=body.confirmation_version, choice=body.choice))
            return service.continue_task(who, trusted.task_id, {"choice": body.choice})
        return mutation(service, who, request, body, action)

    @application.get("/api/v1/verifications/{challenge_id}")
    def verification(challenge_id: str, who=Depends(identity), service=Depends(api)):
        return success(service.verification_view(service.verification(who, challenge_id)[1]))

    @application.get("/api/v1/verifications/{challenge_id}/demo-code")
    def demo_code(challenge_id: str, who=Depends(identity), service=Depends(api)):
        trusted, challenge = service.verification(who, challenge_id)
        return success({"challenge_id": challenge_id, "code": service.runtime.gateway.get_demo_code_for_api(trusted, challenge_id),
                        "expires_at": challenge.code_expires_at})

    def verification_guard(service, who, trusted, challenge_id, submission_id, method, action):
        service.check_verification_retry(trusted, challenge_id, submission_id, method)
        try:
            return action()
        except Exception as exc:
            status, _ = problem(exc)
            if status != 503:
                if isinstance(exc, (ValueError, ApiProblem)) and (
                    getattr(exc, "code", None) == "CHALLENGE_STALE" or str(exc) == "TASK_TERMINATED"
                ):
                    current = service.runtime.gateway.get_verification(trusted, challenge_id)
                    if current.challenge_status in {"failed", "expired", "cancelled"}:
                        if not service.fail_export_for_challenge(trusted, current):
                            service.continue_task(who, trusted.task_id, {"choice": "resume"}, verification_retry=True)
                raise
            service.verification_fault(who, trusted, challenge_id, submission_id, method)
            raise ApiProblem(503, "DEPENDENCY_UNAVAILABLE") from None

    def verification_response(service, who, trusted, outcome, actor, method):
        current = service.runtime.gateway.get_verification(trusted, outcome.challenge.challenge_id)
        outcome = outcome.model_copy(update={"challenge": current})
        service.record_verification(actor, trusted, outcome, method)
        export = service.export_for_challenge(trusted, current.challenge_id)
        if export is not None:
            return service.export_verification_result(who, export, current)
        task = service.task_view(who, trusted.task_id)
        if task.status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            if outcome.verification_id:
                service.runtime.bind_verification(trusted, outcome.verification_id)
            task = service.continue_task(who, trusted.task_id, {"choice": "resume"}, verification_retry=True)
        error = None if outcome.kind == "verified" else ModuleError(code=outcome.reason_code or "VERIFICATION_REJECTED",
            source="bank", field=None, reason="验证尚未通过。", upstream_code=None)
        # The envelope follows the module that owns the task (§5.6); transfer keeps its
        # typed view and a subscription task carries its own instead of a transfer one.
        return service.verification_response(
            outcome.kind, service.verification_view(outcome.challenge), task, error,
        )

    @application.post("/api/v1/verifications/{challenge_id}/code")
    def code(request: Request, challenge_id: str, body: VerificationCodeRequest, who=Depends(identity), service=Depends(api)):
        trusted = service.record_context(who, "verification", challenge_id)
        def action():
            challenge = service.runtime.gateway.get_verification(trusted, challenge_id)
            # The bank first finds the original submission_id. This also recovers
            # a passed bank record after an API crash before binding it to the task.
            service.begin_verification(who, trusted, "verification.code", terminal_challenge=challenge.challenge_status != "pending")
            outcome = service.runtime.gateway.verify_code(trusted, challenge_id, body.submission_id, body.code.get_secret_value())
            return verification_response(service, who, trusted, outcome, who, "code")
        # HMAC the actual secret for conflict detection; persist neither the code
        # nor its reversible encoding. SecretStr.model_dump masks every value.
        fingerprint = {**body.model_dump(mode="json"), "code": body.code.get_secret_value()}
        return mutation(service, who, request, body, lambda: verification_guard(
            service, who, trusted, challenge_id, body.submission_id, "code", action),
            fingerprint=fingerprint, recover_verification=True)

    @application.post("/api/v1/verifications/{challenge_id}/resend-code")
    @application.post("/api/v1/verifications/{challenge_id}/face/start")
    def verification_action(request: Request, challenge_id: str, body: RequestIdOnly, who=Depends(identity), service=Depends(api)):
        trusted = service.record_context(who, "verification", challenge_id)
        def action():
            challenge = service.runtime.gateway.get_verification(trusted, challenge_id)
            if request.url.path.endswith("resend-code"):
                service.begin_verification(who, trusted, "verification.resend-code")
                current = service.runtime.gateway.resend_verification_code(trusted, challenge_id, body.request_id)
                service.store.write("INSERT OR IGNORE INTO api_records VALUES (?, ?, ?)", ("verification", current.challenge_id, trusted.task_id))
                # F18 for details exports: the waiting export follows the resent code.
                service.rebind_export_challenge(trusted, challenge_id, current)
            else:
                service.begin_verification(who, trusted, "verification.face.start",
                    terminal_challenge=challenge.challenge_status != "pending")
                current = service.runtime.gateway.start_face(trusted, challenge_id, body.request_id)
            task = service.runtime.application.get_task(trusted.user_id, trusted.demo_round_id, trusted.task_id)
            if request.url.path.endswith("resend-code") or task.snapshot.get("pending_verification"):
                service.continue_task(who, trusted.task_id, {"choice": "resume"}, verification_retry=True)
            current = service.runtime.gateway.get_verification(trusted, current.challenge_id)
            return service.verification_view(current)
        return mutation(service, who, request, body, lambda: verification_guard(
            service, who, trusted, challenge_id, body.request_id,
            "resend" if request.url.path.endswith("resend-code") else "face_start", action), recover_verification=True)

    @application.post("/api/v1/admin/verifications/{challenge_id}/face-result")
    def face_result(request: Request, challenge_id: str, body: FaceAnswer, who=Depends(identity), service=Depends(api)):
        if who.role != "admin" or body.demo_round_id != who.demo_round_id:
            raise ApiProblem(403, "ACCESS_DENIED")
        rows = service.store.rows("""SELECT t.* FROM api_records r JOIN api_tasks t ON r.task_id=t.task_id
            WHERE r.kind='verification' AND r.record_id=? AND t.demo_round_id=?""", (challenge_id, who.demo_round_id))
        if not rows:
            raise ApiProblem(404, "NOT_FOUND")
        link = rows[0]
        target = service.identity(service.cookie(link["session_id"]))
        trusted = service.record_context(target, "verification", challenge_id)
        def action():
            challenge = service.runtime.gateway.get_verification(trusted, challenge_id)
            service.begin_verification(who, trusted, "admin.verification.face-result", terminal_challenge=challenge.challenge_status != "pending")
            admin = AdminContext(who.user_id, True, who.demo_round_id, target.user_id)
            outcome = service.runtime.gateway.verify_face(admin, challenge_id, body.submission_id, body.result)
            return verification_response(service, target, trusted, outcome, who, "mock_face")
        return mutation(service, who, request, body, lambda: verification_guard(
            service, target, trusted, challenge_id, body.submission_id, "mock_face", action), recover_verification=True)

    @application.get("/api/v1/admin/audit/events")
    def timeline(task_id: str, demo_round_id: str | None = None, trace_id: str | None = None,
                 cursor: str | None = None, limit: int = Query(50, ge=1, le=100), who=Depends(identity), service=Depends(api)):
        reader, viewer = service.audit_reader(who)
        selected_round = demo_round_id or who.demo_round_id
        events = reader.timeline(viewer, selected_round, task_id)
        from app.contracts.audit import AuditEventSummary
        summaries = [AuditEventSummary.model_validate(e.model_dump(include=set(AuditEventSummary.model_fields))).model_dump(mode="json")
                     for e in events if trace_id is None or e.trace_id == trace_id]
        items = sorted(((e["timestamp"], e["event_id"]), e) for e in summaries)
        return success(service.store.page(items, who, f"audit:{selected_round}:{task_id}:{trace_id}", cursor, limit))

    @application.get("/api/v1/admin/audit/events/{event_id}")
    def evidence(event_id: str, who=Depends(identity), service=Depends(api)):
        reader, viewer = service.audit_reader(who)
        return success(reader.detail(viewer, who.demo_round_id, event_id))

    @application.post("/api/v1/admin/audit/exports")
    def audit_export(request: Request, body: AuditExportRequest, who=Depends(identity), service=Depends(api)):
        def action():
            return service.create_audit_export(who, body.demo_round_id, body.task_id)
        return mutation(service, who, request, body, action)

    @application.get("/api/v1/threads/{thread_id}/events")
    async def events(request: Request, thread_id: str, who=Depends(identity), service=Depends(api)):
        service.thread(who, thread_id)
        cursor = request.headers.get("Last-Event-ID")
        service.events_for_session(who, thread_id, cursor)  # Reject foreign/stale cursors before headers.
        async def stream():
            nonlocal cursor
            while not await request.is_disconnected():
                try:
                    service.identity(request.cookies.get(COOKIE))
                except ApiProblem:
                    event = StreamEvent(event_id=str(uuid4()), thread_id=thread_id, session_id=who.session_id,
                        task_id=None, run_id=None, module="platform", event_type="session_expired", occurred_at=now(),
                        payload=SessionExpired(session_id=who.session_id, reason="AUTH_REQUIRED"))
                    yield f"id: {event.event_id}\nevent: session_expired\ndata: {dump(event)}\n\n"
                    return
                visible_events, scanned_cursor = service.events_for_session(who, thread_id, cursor)
                for event in visible_events:
                    cursor = event["event_id"]
                    yield f"id: {cursor}\nevent: {event['event_type']}\ndata: {dump(event)}\n\n"
                cursor = scanned_cursor or cursor
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.25)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return application


app = create_app()
