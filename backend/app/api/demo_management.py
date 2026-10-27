"""Durable F30—F32 coordination; each subsystem resets through its public seam."""

from datetime import datetime, timezone
import json
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import Depends, Request

from app.contracts.api import ManagementOperation, ResetPreview, ResetPreviewRequest, ResetRequest
from app.contracts.audit import AdminChangedPayload, AuditEvent
from app.contracts.tasks import ModuleError
from app.services.mock_bank.verification import AdminContext
from app.storage.database import transaction

from .store import ApiProblem


EFFECTS = [
    "停止接收新业务，等待正在执行的操作结束。",
    "银行账户、流水、签约及故障恢复演示初始状态。",
    "旧会话、任务按钮和身份验证失效，进入新的演示轮次。",
    "恢复演示预置记忆和逻辑起点；历史审计记录保留。",
]


class DemoManagement:
    def __init__(self, service):
        self.service = service
        self.path = service.store.path
        bank = service.runtime.bank
        bank_round = bank.current_demo_round_id
        at = (bank.current_demo_logical_at or bank.clock()).isoformat()
        with transaction(self.path) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS api_demo_state (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                demo_round_id TEXT NOT NULL, initial_logical_at TEXT NOT NULL,
                logical_at TEXT NOT NULL, reset_state TEXT NOT NULL,
                management_operation_id TEXT)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS api_reset_confirmations (
                confirmation_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL,
                demo_round_id TEXT NOT NULL, request_id TEXT NOT NULL,
                management_operation_id TEXT,
                UNIQUE(actor_id, demo_round_id, request_id))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS api_management_operations (
                operation_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL,
                confirmation_id TEXT NOT NULL, source_round_id TEXT NOT NULL,
                target_round_id TEXT NOT NULL, request_id TEXT NOT NULL,
                users_json TEXT NOT NULL, result_json TEXT NOT NULL,
                UNIQUE(actor_id, source_round_id, request_id))""")
            connection.execute("INSERT OR IGNORE INTO api_demo_state VALUES (1, ?, ?, ?, 'idle', NULL)",
                (bank_round or service.config.demo_round_id, at, at))
        state = self.state()
        if bank_round is not None or state["management_operation_id"] is not None:
            service.runtime.set_demo_clock(datetime.fromisoformat(state["logical_at"]))

    def state(self):
        return self.service.store.rows("SELECT * FROM api_demo_state WHERE singleton = 1")[0]

    @property
    def current_round_id(self):
        return self.state()["demo_round_id"]

    def require_open(self):
        if self.state()["reset_state"] != "idle":
            raise ApiProblem(409, "DEMO_RESET_IN_PROGRESS",
                "演示环境正在重置，暂不接受新的办理；请由管理员查询原重置操作。")

    @staticmethod
    def require_admin(who):
        if who.role != "admin":
            raise ApiProblem(403, "ACCESS_DENIED")

    def preview(self, who, body: ResetPreviewRequest):
        self.require_admin(who)
        self.require_open()
        if body.demo_round_id != self.current_round_id or who.demo_round_id != self.current_round_id:
            raise ApiProblem(409, "STALE_ROUND")
        with transaction(self.path) as connection:
            connection.execute("INSERT OR IGNORE INTO api_reset_confirmations VALUES (?, ?, ?, ?, NULL)",
                (str(uuid4()), who.user_id, body.demo_round_id, str(body.request_id)))
            row = connection.execute("""SELECT confirmation_id FROM api_reset_confirmations
                WHERE actor_id = ? AND demo_round_id = ? AND request_id = ?""",
                (who.user_id, body.demo_round_id, str(body.request_id))).fetchone()
        return ResetPreview(reset_confirmation_id=row["confirmation_id"],
                            demo_round_id=body.demo_round_id, effects=EFFECTS)

    def _row(self, operation_id):
        rows = self.service.store.rows("SELECT * FROM api_management_operations WHERE operation_id = ?",
                                       (operation_id,))
        return rows[0] if rows else None

    def get_operation(self, who, operation_id):
        self.require_admin(who)
        row = self._row(operation_id)
        if row is None:
            raise ApiProblem(404, "NOT_FOUND")
        if row["actor_id"] != who.user_id:
            raise ApiProblem(403, "ACCESS_DENIED")
        return ManagementOperation.model_validate_json(row["result_json"])

    def reset(self, who, body: ResetRequest):
        self.require_admin(who)
        with transaction(self.path) as connection:
            confirmation = connection.execute("SELECT * FROM api_reset_confirmations WHERE confirmation_id = ?",
                                              (body.reset_confirmation_id,)).fetchone()
            if confirmation is None:
                raise ApiProblem(404, "NOT_FOUND")
            if confirmation["actor_id"] != who.user_id:
                raise ApiProblem(403, "ACCESS_DENIED")
            source = confirmation["demo_round_id"]
            operation_id = str(uuid5(NAMESPACE_URL,
                "demo-reset:" + json.dumps([who.user_id, source, str(body.request_id)])))
            previous = connection.execute("SELECT * FROM api_management_operations WHERE operation_id = ?",
                                          (operation_id,)).fetchone()
            if previous:
                if previous["confirmation_id"] != body.reset_confirmation_id:
                    raise ApiProblem(409, "REQUEST_CONFLICT")
                result = ManagementOperation.model_validate_json(previous["result_json"])
                if result.status == "succeeded":
                    return result
            else:
                state = connection.execute("SELECT * FROM api_demo_state WHERE singleton = 1").fetchone()
                if (state["reset_state"] != "idle" or source != state["demo_round_id"]
                        or who.demo_round_id != source or confirmation["management_operation_id"]):
                    raise ApiProblem(409, "RESET_CONFLICT")
                users = {self.service.config.demo_user_id}
                users.update(row["user_id"] for row in connection.execute(
                    "SELECT DISTINCT user_id FROM api_tasks WHERE demo_round_id = ?", (source,)))
                users.update(row["user_id"] for row in connection.execute(
                    "SELECT DISTINCT s.user_id FROM sessions s JOIN api_sessions a "
                    "ON s.session_id = a.session_id WHERE s.demo_round_id = ? AND a.role = 'user'", (source,)))
                result = ManagementOperation(management_operation_id=operation_id, kind="reset",
                    status="running", source_round_id=source, resulting_round_id=None,
                    phase="waiting_inflight", error=None)
                connection.execute("INSERT INTO api_management_operations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (operation_id, who.user_id, body.reset_confirmation_id, source,
                     str(uuid4()), str(body.request_id), json.dumps(sorted(users)), result.model_dump_json()))
                connection.execute("UPDATE api_reset_confirmations SET management_operation_id = ? "
                                   "WHERE confirmation_id = ?", (operation_id, body.reset_confirmation_id))
                connection.execute("UPDATE api_demo_state SET reset_state = 'waiting_inflight', "
                                   "management_operation_id = ? WHERE singleton = 1", (operation_id,))
        # Stop admission durably before trying the API lock. An already running
        # worker needs that lock to finish publishing and leave its active set.
        # Returning the original running operation lets it finish safely.
        if not self.service.mutation_lock.acquire(blocking=False):
            return self.get_operation(who, operation_id)
        try:
            who = self.service.identity(self.service.cookie(who.session_id), management=True)
            self.require_admin(who)
            return self._advance(operation_id, who)
        finally:
            self.service.mutation_lock.release()

    def owns_historical_round(self, actor_id, demo_round_id):
        return bool(self.service.store.rows("SELECT 1 FROM api_management_operations "
            "WHERE actor_id = ? AND source_round_id = ? LIMIT 1", (actor_id, demo_round_id)))

    def _audit(self, row, who, outcome, resulting_round_id=None):
        self.service.runtime.audit.append(AuditEvent(
            event_id=str(uuid4()), trace_id=row["operation_id"], span_id=str(uuid4()), sequence=0,
            parent_span_id=None, demo_round_id=row["source_round_id"], actor_id=who.user_id,
            session_id=who.session_id, target_session_id=None,
            target_user_id=self.service.config.demo_user_id, thread_id=None, task_id=None,
            run_id=str(uuid4()), module="api", event_type="admin.changed",
            timestamp=datetime.now(timezone.utc), logical_at=None, outcome=outcome,
            evidence_ref=None, evidence_status="missing",
            missing_reason="Management operation contains no secret content snapshot",
            payload=AdminChangedPayload(management_operation_id=row["operation_id"],
                action="reset", target_ref=row["confirmation_id"], source_round_id=row["source_round_id"],
                resulting_round_id=resulting_round_id, before_ref=None, after_ref=None, error=None)))

    def _save(self, result, *, reset_state):
        with transaction(self.path) as connection:
            connection.execute("UPDATE api_management_operations SET result_json = ? WHERE operation_id = ?",
                               (result.model_dump_json(), result.management_operation_id))
            connection.execute("UPDATE api_demo_state SET reset_state = ? WHERE singleton = 1", (reset_state,))

    def _phase(self, result, phase):
        result = result.model_copy(update={"status": "running", "phase": phase, "error": None})
        self._save(result, reset_state="waiting_inflight" if phase == "waiting_inflight" else "resetting")
        return result

    def _advance(self, operation_id, who):
        row = self._row(operation_id)
        result = ManagementOperation.model_validate_json(row["result_json"])
        service = self.service
        runtime = service.runtime
        initial = datetime.fromisoformat(self.state()["initial_logical_at"])
        try:
            result = self._phase(result, result.phase)
            if result.phase == "waiting_inflight":
                if (service.active_tasks or service.active_message_jobs
                        or not runtime.gateway.wait_for_inflight(timeout=0.0)):
                    return result
                result = self._phase(result, "resetting_bank")
            if result.phase == "resetting_bank":
                admin = AdminContext(row["actor_id"], True, row["source_round_id"], service.config.demo_user_id)
                bank_result = runtime.bank.get_demo_management_operation(admin, operation_id)
                if bank_result is None or bank_result.status != "succeeded":
                    self._audit(row, who, "started")
                    bank_result = runtime.bank.reset_demo(admin, operation_id,
                        row["source_round_id"], row["target_round_id"], initial)
                if bank_result.status == "running":
                    return self._phase(result, "waiting_inflight")
                if bank_result.status != "succeeded" or bank_result.demo_round_id != row["target_round_id"]:
                    raise RuntimeError("BANK_RESET_INCOMPLETE")
                result = self._phase(result, "resetting_application")
            if result.phase == "resetting_application":
                # Invalidate API-owned user grants, keeping application history and
                # the independent administrator grant for original-id queries.
                service.store.write("DELETE FROM api_sessions WHERE role = 'user' AND session_id IN "
                    "(SELECT session_id FROM sessions WHERE demo_round_id = ?)", (row["source_round_id"],))
                result = self._phase(result, "resetting_memory")
            if result.phase == "resetting_memory":
                for user_id in json.loads(row["users_json"]):
                    runtime.memory.reset_user(user_id, row["target_round_id"], initial.strftime("%Y-%m"))
                result = self._phase(result, "resetting_clock")
            if result.phase == "resetting_clock":
                runtime.set_demo_clock(initial)
                self._audit(row, who, "succeeded", row["target_round_id"])
                result = result.model_copy(update={"status": "succeeded", "phase": "completed",
                    "resulting_round_id": row["target_round_id"], "error": None})
                with transaction(self.path) as connection:
                    connection.execute("UPDATE api_management_operations SET result_json = ? WHERE operation_id = ?",
                                       (result.model_dump_json(), operation_id))
                    connection.execute("UPDATE api_demo_state SET demo_round_id = ?, logical_at = ?, "
                        "reset_state = 'idle', management_operation_id = NULL WHERE singleton = 1",
                        (row["target_round_id"], initial.isoformat()))
            return result
        except Exception:
            result = result.model_copy(update={"status": "failed", "error": ModuleError(
                code="RESET_INCOMPLETE", source="platform", field=None,
                reason="重置未完成，新的办理仍已暂停。请查询原管理操作，并使用原请求继续。",
                upstream_code=None)})
            self._save(result, reset_state="incomplete")
            return result


def install_demo_routes(application, api, success):
    def admin_identity(request: Request, service=Depends(api)):
        who = service.identity(request.cookies.get("bank_session"), management=True)
        service.demo.require_admin(who)
        return who

    @application.post("/api/v1/admin/demo/reset-preview")
    def preview(body: ResetPreviewRequest, who=Depends(admin_identity), service=Depends(api)):
        with service.mutation_lock:
            who = service.identity(service.cookie(who.session_id), management=True)
            return success(service.demo.preview(who, body))

    @application.post("/api/v1/admin/demo/reset")
    def reset(body: ResetRequest, who=Depends(admin_identity), service=Depends(api)):
        return success(service.demo.reset(who, body))

    @application.get("/api/v1/admin/operations/{management_operation_id}")
    def operation(management_operation_id: str, who=Depends(admin_identity), service=Depends(api)):
        return success(service.demo.get_operation(who, management_operation_id))
