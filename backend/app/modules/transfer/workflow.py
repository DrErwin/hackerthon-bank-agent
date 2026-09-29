"""A pausable ordinary-transfer LangGraph; the model never submits funds."""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Protocol, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import TypeAdapter

from app.contracts.bank import BankError, OperationResult, PayeeInput, QueryFailure
from app.contracts.common import SecurityDecisionCode, TaskStatus
from app.contracts.platform import StartTransferInput, TrustedContext
from app.contracts.security import ActionDescriptor, ExecutionSecurityContext, SecurityDecision
from app.contracts.tasks import (
    InteractionOption, InteractionRequest, ModuleError, ModuleResult, TransferTaskView,
)
from app.security import ExecutionOutcome

from .tools import TransferAction


_PAYEE = TypeAdapter(PayeeInput)


class TransferPorts(Protocol):
    def read(self, trusted: TrustedContext, action_name: str, parameters: dict) -> ExecutionOutcome: ...
    def prepare_transfer(
        self, trusted: TrustedContext, operation_id: UUID, action_revision: int,
        payer_account_id: str, payee: PayeeInput, amount_fen: int,
    ) -> TransferAction: ...
    def check(self, trusted: TrustedContext, action: TransferAction) -> SecurityDecision: ...
    def execute(self, trusted: TrustedContext, action: TransferAction) -> ExecutionOutcome: ...
    def observe(self, trusted: TrustedContext, action: TransferAction) -> ExecutionOutcome: ...


class TransferState(TypedDict, total=False):
    trusted: dict
    request_id: str
    intent_text: str
    payer_account_id: str | None
    payee_hint: str | None
    payee_input: dict | None
    payee_display: dict | None
    payee_candidates: list[dict]
    amount_fen: int | None
    operation_id: str | None
    action_revision: int
    parameters_ref: str | None
    operation: dict | None
    status: str
    interaction: dict | None
    wait_kind: str | None
    next: str
    message: str
    error: dict | None
    recovery_required: bool
    recovery_reason: str | None
    retry_at: str


class TransferWorkflow:
    """The platform supplies an owned checkpointer and trusted tool ports."""

    def __init__(
        self, ports: TransferPorts, checkpointer, *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.ports = ports
        self.monotonic = monotonic
        self.sleep = sleep
        self._node_action = ContextVar("transfer_node_action", default=None)
        graph = StateGraph(TransferState)
        for name, node in (
            ("collect", self._collect), ("find_payee", self._find_payee),
            ("verify_payee", self._verify_payee), ("precheck", self._precheck),
            ("security", self._security), ("submit", self._submit),
            ("reconcile", self._reconcile), ("manual_reconcile", self._manual_reconcile),
            ("await_query", self._await_query), ("wait", self._wait),
        ):
            graph.add_node(name, node)
            graph.add_conditional_edges(name, lambda state: state["next"])
        graph.add_edge(START, "collect")
        self.graph = graph.compile(checkpointer=checkpointer)

    @staticmethod
    def _trusted(state: TransferState) -> TrustedContext:
        return TrustedContext.model_validate(state["trusted"])

    @staticmethod
    def _config(trusted: TrustedContext, thread_id: str | None) -> dict:
        return {"configurable": {"thread_id": thread_id or trusted.task_id}}

    def _checkpoint_for_run(self, config: dict, trusted: TrustedContext,
                            request_id: str | None = None):
        saved = self.graph.get_state(config)
        if not saved.values:
            return saved
        self._check_owner(saved.values, trusted)
        if request_id is not None and saved.values["request_id"] != request_id:
            raise ValueError("REQUEST_CONFLICT")
        if saved.values["trusted"]["run_id"] != trusted.run_id:
            self.graph.update_state(config, {"trusted": trusted.model_dump(mode="json")})
            saved = self.graph.get_state(config)
        if saved.next in {("wait",), ("await_query",)} and not any(
            task.interrupts for task in saved.tasks
        ):
            self.graph.invoke(None, config)
            saved = self.graph.get_state(config)
        return saved

    @staticmethod
    def _interaction(prompt: str, fields: list[str], options: list[InteractionOption] | None = None) -> dict:
        return InteractionRequest(
            interaction_id=str(uuid4()), kind="input", prompt=prompt,
            required_fields=fields, options=options or [], record_ref=None,
        ).model_dump(mode="json")

    @staticmethod
    def _fail(code: str, source: str, message: str, *, recoverable: bool = False) -> dict:
        return {
            "status": (TaskStatus.NEEDS_ATTENTION if recoverable else TaskStatus.FAILED).value,
            "message": message,
            "error": ModuleError(
                code=code, source=source, field=None, reason=message, upstream_code=None,
            ).model_dump(mode="json"),
            "interaction": None,
            "recovery_required": recoverable,
            "recovery_reason": code if recoverable else None,
            "next": END,
        }

    def _read_failure(self, error: str, message: str, retry_at: str) -> dict:
        if error in {"ACCESS_DENIED", "INVALID_ARGUMENT"}:
            return self._fail(error, "bank", "无法继续这笔转账，请核对访问权限或输入。")
        return {
            "status": TaskStatus.WAITING_INPUT.value,
            "message": message + "稍后可在原任务重试。",
            "error": ModuleError(
                code=error, source="bank", field=None, reason=message, upstream_code=None,
            ).model_dump(mode="json"),
            "interaction": self._interaction(message + "请选择重试或取消。", [], [
                InteractionOption(id="resume", label="重试"),
                InteractionOption(id="cancel", label="取消"),
            ]),
            "wait_kind": "retry_read", "retry_at": retry_at, "next": "wait",
            "recovery_required": True, "recovery_reason": error,
        }

    @staticmethod
    def _bank_reason(failure: BankError) -> str:
        reasons = {
            "INSUFFICIENT_FUNDS": "可用余额不足",
            "LIMIT_EXCEEDED": "超过银行当前允许的转账额度",
            "ACCOUNT_UNAVAILABLE": "转出账户当前不可用",
            "PAYEE_MISMATCH": "收款账户资料未通过核验",
            "RISK_REJECTED": "银行风控未放行",
        }
        reason = reasons.get(failure.code, "银行未批准这笔转账")
        available = failure.details.get("available_fen")
        allowed = failure.details.get("allowed_fen")
        if isinstance(available, int):
            reason += f"，当前可用 {available / 100:.2f} 元"
        elif isinstance(allowed, int):
            reason += f"，当前可用额度 {allowed / 100:.2f} 元"
        return reason

    def _read(self, state: TransferState, name: str, parameters: dict):
        for attempt in range(2):
            try:
                outcome = self.ports.read(self._trusted(state), name, parameters)
            except Exception:
                error = "DEPENDENCY_UNAVAILABLE"
            else:
                if outcome.decision is None or outcome.decision.decision != SecurityDecisionCode.ALLOW:
                    return None, "ACCESS_DENIED"
                response = outcome.result
                if getattr(response, "kind", None) == "ok":
                    return response.data, None
                error = response.error.code if isinstance(response, QueryFailure) else "DEPENDENCY_UNAVAILABLE"
                if error in {"ACCESS_DENIED", "INVALID_ARGUMENT"}:
                    return None, error
            if attempt == 1:
                return None, error

    def _collect(self, state: TransferState) -> dict:
        if not state["intent_text"].strip():
            return self._fail("INVALID_ARGUMENT", "transfer", "请说明要办理的普通转账。")
        if state.get("amount_fen") is None or state.get("amount_fen", 0) <= 0:
            return {
                "status": TaskStatus.WAITING_INPUT.value,
                "interaction": self._interaction("请告诉我转账金额。", ["amount_fen"]),
                "wait_kind": "details", "next": "wait",
                "message": "还需要转账金额。",
            }
        if not state.get("payer_account_id"):
            accounts, error = self._read(state, "bank.list_accounts", {})
            if error:
                return self._read_failure(error, "暂时无法查询转出账户。", "collect")
            return {
                "status": TaskStatus.WAITING_INPUT.value,
                "interaction": self._interaction(
                    "请选择转出账户。", ["payer_account_id"],
                    [InteractionOption(id=a.account_id, label=a.display_name + " " + a.account_masked)
                     for a in accounts.accounts],
                ),
                "wait_kind": "details", "next": "wait",
                "message": "请先选择转出账户。",
            }
        if not state.get("payee_input") and not state.get("payee_hint"):
            return {
                "status": TaskStatus.WAITING_INPUT.value,
                "interaction": self._interaction("请告诉我收款人。", ["payee_hint"]),
                "wait_kind": "details", "next": "wait",
                "message": "还需要收款人信息。",
            }
        return {"status": TaskStatus.RUNNING.value, "interaction": None, "next": "find_payee"}

    def _find_payee(self, state: TransferState) -> dict:
        if state.get("payee_input"):
            return {"next": "verify_payee"}
        hint = state["payee_hint"].strip()
        kind = "phone" if hint.isdigit() and len(hint) == 11 else (
            "account_number" if hint.isdigit() else "remark"
        )
        search_kinds = [kind, "name"] if kind == "remark" else [kind]
        candidates_by_id = {}
        for search_kind in search_kinds:
            payees, error = self._read(
                state, "bank.list_payees", {"kind": search_kind, "value": hint},
            )
            if error:
                return self._read_failure(error, "收款人查询暂不可用。", "find_payee")
            for item in payees.payees:
                candidates_by_id[item.payee_id] = item.model_dump(mode="json")
        candidates = list(candidates_by_id.values())
        if not candidates:
            return {
                "payee_hint": None,
                "status": TaskStatus.WAITING_INPUT.value,
                "interaction": self._interaction("没有找到匹配的收款人，请提供更多线索。", ["payee_hint"]),
                "wait_kind": "details", "next": "wait",
                "message": "请核对收款人信息。",
            }
        if len(candidates) > 1:
            return {
                "payee_candidates": candidates,
                "status": TaskStatus.WAITING_INPUT.value,
                "interaction": self._interaction(
                    "找到多位收款人，请选择。", [],
                    [InteractionOption(id=item["payee_id"], label=(
                        (item.get("remark") or item["name_masked"]) + " "
                        + item["bank_name"] + " " + item["account_masked"]
                    )) for item in candidates],
                ),
                "wait_kind": "choose_payee", "next": "wait",
                "message": "请确认要转给哪位收款人。",
            }
        return {
            "payee_input": {"kind": "saved", "payee_id": candidates[0]["payee_id"]},
            "payee_display": candidates[0], "next": "verify_payee",
        }

    def _verify_payee(self, state: TransferState) -> dict:
        verification, error = self._read(
            state, "bank.verify_payee", {"payee": state["payee_input"]},
        )
        if error:
            return self._read_failure(error, "收款账户暂时无法核验。", "verify_payee")
        if not verification.matched:
            return self._fail("PAYEE_MISMATCH", "bank", "收款账户未通过核验，请核对账户资料。")
        return {"payee_display": verification.payee.model_dump(mode="json"), "next": "precheck"}

    def _precheck(self, state: TransferState) -> dict:
        draft = {
            "payer_account_id": state["payer_account_id"],
            "payee": state["payee_input"], "amount_fen": state["amount_fen"],
        }
        check, error = self._read(state, "bank.precheck_transfer", draft)
        if error:
            return self._read_failure(error, "银行暂时无法检查这笔转账。", "precheck")
        if not check.can_proceed:
            reason = self._bank_reason(check.failure)
            if check.failure.code == "RISK_REJECTED":
                return self._fail("RISK_REJECTED", "bank", reason + "，已停止这笔转账。")
            return {
                "status": TaskStatus.WAITING_INPUT.value,
                "interaction": self._interaction(
                    reason + "。你可以修改金额、账户或取消。",
                    [],
                    [InteractionOption(id="cancel", label="取消")],
                ),
                "wait_kind": "adjust", "next": "wait",
                "message": reason + "；这笔转账尚未提交，请修改或取消。",
                "error": ModuleError(
                    code="BANK_REJECTED", source="bank", field=None,
                    reason=reason, upstream_code=check.failure.code,
                ).model_dump(mode="json"),
            }
        if state.get("operation_id") and state.get("parameters_ref"):
            return {"next": "security"}
        operation_id = uuid4()
        action = self.ports.prepare_transfer(
            self._trusted(state), operation_id, state["action_revision"],
            state["payer_account_id"], _PAYEE.validate_python(state["payee_input"]),
            state["amount_fen"],
        )
        return {
            "operation_id": str(operation_id), "parameters_ref": action.parameters_ref,
            "next": "security", "error": None,
        }

    @staticmethod
    def _action(state: TransferState) -> TransferAction:
        return TransferAction(
            UUID(state["operation_id"]), state["action_revision"], state["parameters_ref"],
        )

    @contextmanager
    def _within_action(self, state: TransferState):
        token = self._node_action.set(state)
        try:
            yield
        finally:
            self._node_action.reset(token)

    def _security(self, state: TransferState) -> dict:
        with self._within_action(state):
            decision = self.ports.check(self._trusted(state), self._action(state))
        return self._security_decision(decision)

    def _security_decision(self, decision: SecurityDecision) -> dict:
        if decision.decision == SecurityDecisionCode.ALLOW:
            return {"status": TaskStatus.RUNNING.value, "interaction": None, "next": "submit"}
        if decision.decision in {
            SecurityDecisionCode.REQUIRE_CONFIRMATION, SecurityDecisionCode.REQUIRE_VERIFICATION,
        }:
            return {
                "status": TaskStatus.WAITING_APPROVAL.value,
                "interaction": decision.interaction.model_dump(mode="json"),
                "wait_kind": "security", "next": "wait",
                "message": ("请核对并点击当前确认单的按钮。" if decision.decision ==
                            SecurityDecisionCode.REQUIRE_CONFIRMATION else "请完成专用身份验证。"),
            }
        if decision.decision == SecurityDecisionCode.REQUIRE_INPUT:
            return {
                "status": TaskStatus.WAITING_INPUT.value,
                "interaction": decision.interaction.model_dump(mode="json"),
                "wait_kind": "details", "next": "wait", "message": "请补充必要信息。",
            }
        return self._fail(
            decision.reason_codes[0], "security",
            "安全检查暂不允许提交这笔转账。",
            recoverable=decision.decision == SecurityDecisionCode.PAUSE,
        )

    def _submit(self, state: TransferState) -> dict:
        with self._within_action(state):
            outcome = self.ports.execute(self._trusted(state), self._action(state))
        if outcome.decision is not None and outcome.decision.decision != SecurityDecisionCode.ALLOW:
            return self._security_decision(outcome.decision)
        if isinstance(outcome.result, OperationResult):
            applied = self._apply_operation(state, outcome.result)
            return applied
        return {"next": "reconcile"}

    @staticmethod
    def _apply_operation(state: TransferState, operation: OperationResult) -> dict:
        if str(operation.operation_id) != state["operation_id"]:
            return TransferWorkflow._fail(
                "OPERATION_CONFLICT", "bank", "银行结果与原操作不一致，已停止办理。",
                recoverable=True,
            )
        if operation.operation_status == "processing":
            return {"operation": operation.model_dump(mode="json"), "next": "reconcile"}
        if operation.operation_status == "succeeded":
            receipt = operation.receipt
            return {
                "operation": operation.model_dump(mode="json"), "status": TaskStatus.SUCCEEDED.value,
                "message": f"银行返回转账成功，金额 {receipt.amount_fen / 100:.2f} 元。交易编号 {receipt.transaction_id}。",
                "interaction": None, "error": None, "next": END,
            }
        reason = operation.failure.code if operation.failure else "BANK_REJECTED"
        description = (TransferWorkflow._bank_reason(operation.failure)
                       if operation.failure else "银行未批准这笔转账")
        return {
            "operation": operation.model_dump(mode="json"), "status": TaskStatus.FAILED.value,
            "message": description + "；银行明确未完成这笔转账。请核对后重新办理。",
            "error": ModuleError(
                code="BANK_REJECTED", source="bank", field=None,
                reason=description, upstream_code=reason,
            ).model_dump(mode="json"),
            "interaction": None, "next": END,
        }

    def _reconcile_once(self, state: TransferState) -> dict | None:
        with self._within_action(state):
            outcome = self.ports.observe(self._trusted(state), self._action(state))
        if outcome.decision is not None and outcome.decision.decision != SecurityDecisionCode.ALLOW:
            reason = outcome.decision.reason_codes[0]
            if outcome.decision.decision == SecurityDecisionCode.PAUSE or reason in {
                "AUTH_REQUIRED", "ACCESS_DENIED", "DEPENDENCY_UNAVAILABLE",
            }:
                pending = self._pending(state.get("operation"))
                pending.update({
                    "message": "暂时无法查询原转账结果。恢复合法访问后，可继续查询这笔原交易。",
                    "error": ModuleError(
                        code=reason, source="security", field=None,
                        reason="当前无法核对原转账结果", upstream_code=None,
                    ).model_dump(mode="json"),
                })
                return pending
            return self._fail(
                reason, "security", "暂时无法查询原转账结果。",
                recoverable=True,
            )
        if isinstance(outcome.result, OperationResult):
            return self._apply_operation(state, outcome.result)
        return None

    @staticmethod
    def _pending(operation: dict | None) -> dict:
        processing = operation is not None and operation["operation_status"] == "processing"
        return {
            "operation": operation,
            "status": TaskStatus.NEEDS_ATTENTION.value,
            "message": (
                "银行已受理这笔转账，目前还在处理中，尚不能视为到账。你可以稍后查询结果。"
                if processing else
                "这笔转账的结果暂时还没核实，我没有再次提交。你可以稍后查询结果。"
            ),
            "interaction": None, "error": None, "recovery_required": True,
            "recovery_reason": "OPERATION_PROCESSING" if processing else "OPERATION_UNKNOWN",
            "next": "await_query",
        }

    def _reconcile(self, state: TransferState) -> dict:
        deadline = self.monotonic() + 10
        last_operation = state.get("operation")
        while (remaining := deadline - self.monotonic()) > 0:
            self.sleep(min(3, remaining))
            result = self._reconcile_once(state)
            if result is not None:
                if result["next"] in {END, "await_query"}:
                    return result
                last_operation = result["operation"]
        return self._pending(last_operation)

    def _manual_reconcile(self, state: TransferState) -> dict:
        result = self._reconcile_once(state)
        if result is not None:
            if result["next"] in {END, "await_query"}:
                return result
            return self._pending(result["operation"])
        return self._pending(state.get("operation"))

    def _await_query(self, state: TransferState) -> dict:
        interrupt({"kind": "query_result", "operation_id": state["operation_id"]})
        return {"next": "manual_reconcile"}

    def _wait(self, state: TransferState) -> dict:
        response = interrupt(state["interaction"])
        if not isinstance(response, dict):
            return {"next": "wait"}
        if response.get("cancel") is True or response.get("choice") == "cancel":
            return {
                "status": TaskStatus.CANCELLED.value, "interaction": None,
                "message": "这笔转账尚未提交，已取消。",
                "recovery_required": False, "recovery_reason": None, "next": END,
            }
        kind = state["wait_kind"]
        if kind == "retry_read":
            if response.get("choice") != "resume":
                return {"next": "wait"}
            return {
                "interaction": None, "status": TaskStatus.RUNNING.value,
                "error": None, "recovery_required": False, "recovery_reason": None,
                "next": state["retry_at"],
            }
        if kind == "choose_payee":
            selected = next(
                (item for item in state["payee_candidates"]
                 if item["payee_id"] == response.get("choice")), None,
            )
            if selected is None:
                return {"next": "wait"}
            return {
                "payee_input": {"kind": "saved", "payee_id": selected["payee_id"]},
                "payee_display": selected, "interaction": None,
                "status": TaskStatus.RUNNING.value, "next": "verify_payee",
            }
        if kind in {"details", "adjust", "security"} and isinstance(response.get("fields"), dict):
            fields = response.get("fields")
            allowed = {"payer_account_id", "amount_fen", "payee_hint", "payee_input"}
            changes = {key: value for key, value in fields.items() if key in allowed}
            if not changes:
                return {"next": "wait"}
            if "payee_input" in changes:
                try:
                    changes["payee_input"] = _PAYEE.validate_python(changes["payee_input"]).model_dump(mode="json")
                except ValueError:
                    return {"next": "wait"}
            if "amount_fen" in changes and (
                not isinstance(changes["amount_fen"], int) or changes["amount_fen"] <= 0
            ):
                return {"next": "wait"}
            if "payee_hint" in changes:
                changes["payee_input"] = None
                changes["payee_display"] = None
            if state.get("operation_id"):
                changes.update({
                    "operation_id": None, "parameters_ref": None, "operation": None,
                    "action_revision": state["action_revision"] + 1,
                })
            changes.update({"interaction": None, "status": TaskStatus.RUNNING.value, "next": "collect"})
            return changes
        if kind in {"details", "adjust"}:
            return {"next": "wait"}
        return {"interaction": None, "status": TaskStatus.RUNNING.value, "next": "security"}

    @staticmethod
    def _result(state: TransferState) -> ModuleResult[TransferTaskView]:
        status = TaskStatus(state["status"])
        if status == TaskStatus.WAITING_INPUT and state.get("wait_kind") == "retry_read":
            allowed = ["resume", "cancel"]
        elif status == TaskStatus.WAITING_INPUT:
            allowed = ["provide_input", "cancel"]
        elif status == TaskStatus.WAITING_APPROVAL:
            allowed = ["confirm" if state["interaction"]["kind"] == "confirmation" else "verify", "cancel"]
        elif status == TaskStatus.NEEDS_ATTENTION and state.get("recovery_reason") in {
            "OPERATION_UNKNOWN", "OPERATION_PROCESSING",
        }:
            allowed = ["query"]
        else:
            allowed = []
        return ModuleResult[TransferTaskView](
            task_id=state["trusted"]["task_id"], run_id=state["trusted"]["run_id"],
            status=status,
            data=TransferTaskView(
                operation_id=state.get("operation_id"),
                payer_account_id=state.get("payer_account_id"),
                payee=state.get("payee_display"), amount_fen=state.get("amount_fen"),
                operation=state.get("operation"),
            ),
            message=state.get("message", ""), interaction=state.get("interaction"),
            error=state.get("error"), allowed_actions=allowed,
            recovery_required=state.get("recovery_required", False),
            recovery_reason=state.get("recovery_reason"),
        )

    def start(
        self, trusted: TrustedContext, request: StartTransferInput, *, thread_id: str | None = None,
    ) -> ModuleResult[TransferTaskView]:
        config = self._config(trusted, thread_id)
        saved = self._checkpoint_for_run(config, trusted, str(request.request_id))
        prior = saved.values
        if prior:
            if saved.next and not any(task.interrupts for task in saved.tasks):
                return self.resume(trusted, {}, thread_id=thread_id)
            return self._result(prior)
        if request.execute_at is not None:
            raise ValueError("CAPABILITY_UNAVAILABLE")
        initial: TransferState = {
            "trusted": trusted.model_dump(mode="json"), "request_id": str(request.request_id),
            "intent_text": request.intent_text, "payer_account_id": request.payer_account_id,
            "payee_hint": request.payee_hint,
            "payee_input": request.payee.model_dump(mode="json") if request.payee else None,
            "amount_fen": request.amount_fen, "operation_id": None,
            "action_revision": 1, "parameters_ref": None, "operation": None,
            "status": TaskStatus.RUNNING.value, "interaction": None,
            "message": "", "error": None, "recovery_required": False,
            "recovery_reason": None,
        }
        result = self.graph.invoke(initial, config)
        return self._result(result)

    @staticmethod
    def _check_owner(state: TransferState, trusted: TrustedContext) -> None:
        old = state["trusted"]
        if (old["user_id"], old["session_id"], old["demo_round_id"], old["task_id"]) != (
            trusted.user_id, trusted.session_id, trusted.demo_round_id, trusted.task_id,
        ):
            raise ValueError("ACCESS_DENIED")

    def is_current_action(
        self, context: ExecutionSecurityContext, action: ActionDescriptor, *,
        thread_id: str | None = None,
    ) -> bool:
        """A scope-authorizer building block for transfer writes and old-confirmation rejection."""
        state = self._node_action.get() if thread_id is None else None
        if state is None:
            state = self.graph.get_state(
                {"configurable": {"thread_id": thread_id or context.task_id}},
            ).values
        if not state:
            return False
        owner = state["trusted"]
        return (
            (owner["user_id"], owner["session_id"], owner["demo_round_id"], owner["task_id"])
            == (context.user_id, context.session_id, context.demo_round_id, context.task_id)
            and state.get("operation_id") == str(context.operation_id)
            and state.get("action_revision") == context.action_revision
            and state.get("parameters_ref") == action.parameters_ref
            and state.get("status") not in {
                TaskStatus.SUCCEEDED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value,
            }
        )

    def resume(
        self, trusted: TrustedContext, response: dict, *, thread_id: str | None = None,
    ) -> ModuleResult[TransferTaskView]:
        config = self._config(trusted, thread_id)
        saved = self._checkpoint_for_run(config, trusted)
        if not saved.values:
            raise ValueError("TASK_NOT_FOUND")
        if not saved.next:
            return self._result(saved.values)
        command = Command(resume=response) if any(task.interrupts for task in saved.tasks) else None
        result = self.graph.invoke(command, config)
        return self._result(result)
