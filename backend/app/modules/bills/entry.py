"""L01 task entry using the platform's scoped checkpointer and F10 option replies.

The current harness supplies StartTransferInput even for a second module. Only
intent_text/request_id are used here; transfer amounts/payees never become facts.
No new API, authentication state, or bank rule is defined in this module.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Callable
from uuid import uuid4

from app.contracts.bills import BillSummarizeInput
from app.contracts.common import Category, TaskStatus
from app.contracts.platform import StartTransferInput, TrustedContext
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult
from ._statistics import BEIJING
from .service import BillsError, BillsService, fail, money

_TERMINAL = {"succeeded", "failed", "cancelled"}
_SECRET = re.compile(r"验证码|短信码|动态码|密码|口令|password|\botp\b", re.I)
_CATEGORIES = {"餐饮": Category.DINING, "交通": Category.TRANSPORT, "医疗": Category.MEDICAL,
               "购物": Category.SHOPPING, "居住": Category.HOUSING, "转账": Category.TRANSFER,
               "其他": Category.OTHER}


def _negative_category(intent: str) -> str | None:
    """Detect category exclusions; never turn 'not transfer' into 'show transfer'."""
    for label, category in _CATEGORIES.items():
        if (re.search(r"(?:不含|不包括|不算|不计|排除|剔除|去掉|不要算)\s*" + label, intent)
                or re.search(label + r"\s*(?:不算|不计入|排除)", intent)):
            return category.value
    return None


def month_range(year: int, month: int) -> tuple[str, str]:
    start = datetime(year, month, 1, tzinfo=BEIJING)
    end = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1, tzinfo=BEIJING)
    return start.isoformat(), end.isoformat()


def parse_month(text: str, now: datetime) -> tuple[str, str] | None:
    """Recognize explicit unambiguous months; ambiguous ranges are clarified."""
    # Do not silently shorten a range/comparison into one matched month.
    if any(word in text for word in ("最近", "对比", "相比", "比上", "比去", "至", "到", "之间")):
        return None
    matches = re.findall(r"(?<!\d)(\d{4})(?:年|-)(\d{1,2})(?:月)?(?!\d|[-/])", text)
    relative = [phrase for phrase in ("本月", "这个月", "上月", "上个月") if phrase in text]
    if len(matches) == 1 and not relative:
        try:
            return month_range(int(matches[0][0]), int(matches[0][1]))
        except ValueError:
            return None
    if matches or len(relative) != 1:
        return None
    date = now.astimezone(BEIJING)
    previous = relative[0] in ("上月", "上个月")
    index = date.year * 12 + date.month - 1 - previous
    return month_range(index // 12, index % 12 + 1)


def _actor(context: TrustedContext) -> tuple[str, str, str]:
    return context.user_id, context.demo_round_id, context.task_id


class BillsEntry:
    """Implements the existing TransferEntry protocol without transfer semantics.

    The harness serializes calls per task. The saver is its scoped durable saver,
    not a module-global memory dictionary. Each read still goes through security.
    """
    def __init__(self, service: BillsService, saver, trace):
        self.service, self.saver, self.trace = service, saver, trace

    def _config(self, context, thread_id):
        return {"configurable": {"thread_id": thread_id or context.task_id, "checkpoint_ns": ""}}

    def _load(self, context, thread_id):
        saved = self.saver.get_tuple(self._config(context, thread_id))
        if saved is None:
            return None, None
        state = deepcopy(saved.checkpoint["channel_values"].get("bills_state"))
        if not isinstance(state, dict) or tuple(state.get("actor", ())) != _actor(context):
            raise PermissionError("ACCESS_DENIED")
        return saved, state

    def _save(self, context, thread_id, state):
        saved, previous = self._load(context, thread_id)
        version = int(saved.checkpoint["channel_versions"].get("bills_state", 0)) + 1 if saved else 1
        checkpoint = {"v": 1, "id": str(uuid4()), "ts": self.service.clock().isoformat(),
            "channel_values": {"bills_state": deepcopy(state)},
            "channel_versions": {"bills_state": version}, "versions_seen": {}, "pending_sends": []}
        config = saved.config if saved else self._config(context, thread_id)
        self.saver.put(config, checkpoint, {"source": "update", "step": version, "parents": {}},
                       {"bills_state": version})

    @staticmethod
    def _result(context, state):
        result = ModuleResult.model_validate(state["result"])
        return result.model_copy(update={"run_id": context.run_id})

    def _wait(self, context, state, prompt, choices, reason):
        interaction_id = str(uuid4())
        state["choices"] = {str(uuid4()): value for label, value in choices}
        labels = [label for label, value in choices]
        options = [InteractionOption(id=key, label=label) for key, label in zip(state["choices"], labels)]
        state["wait_reason"] = reason
        return ModuleResult(task_id=context.task_id, run_id=context.run_id,
            status=TaskStatus.WAITING_INPUT, data=None, message=prompt,
            interaction=InteractionRequest(interaction_id=interaction_id, kind="input", prompt=prompt,
                required_fields=["bills_selection"], options=options, record_ref=None),
            error=None, allowed_actions=["provide_input", "cancel"],
            recovery_required=False, recovery_reason=None)

    def _advance(self, context, state):
        if state["period"] is None:
            now = self.service.clock().astimezone(BEIJING)
            choices = []
            for offset, label in [(0, "本月"), (1, "上月"), (2, "前两个月")]:
                index = now.year * 12 + now.month - 1 - offset
                choices.append((label, {"period": month_range(index // 12, index % 12 + 1)}))
            return self._wait(context, state,
                "请明确查询月份。可选择下列月份；自定义范围和对比请通过结构化 L01 入口提交。",
                choices, "period")
        if state.get("negative_category") not in (None, Category.TRANSFER.value):
            # Frozen L01 offers inclusion/whole-summary, not arbitrary subtraction.
            # Explicitly clarify unsupported exclusions *before* any bank read.
            return self._wait(context, state,
                "目前不支持从统计中排除所选类别。可选择查看全部类别的真实账单。",
                [("查看全部类别", {"negative_category": None, "category": None})],
                "category_exclusion")
        if state["account_ids"] is None:
            try:
                accounts = self.service.accounts(context).accounts
            except BillsError as exc:
                if exc.code in {"DEPENDENCY_UNAVAILABLE", "INCOMPLETE_FACTS"}:
                    return self._wait(context, state, "账户暂时查不到，请稍后重试原范围。",
                        [("重新查询原范围", {"retry": True})], "retry")
                return fail(context, exc)
            except Exception:
                return self._wait(context, state, "账户暂时查不到，请稍后重试原范围。",
                    [("重新查询原范围", {"retry": True})], "retry")
            if not accounts:
                return fail(context, BillsError("ACCESS_DENIED", source="security"))
            if state["all_accounts"]:
                state["account_ids"] = [a.account_id for a in accounts]
            else:
                return self._wait(context, state, "请选择要查询的本人账户，不会替你默认选择。",
                    [(a.display_name + " · " + a.account_masked, {"account_ids": [a.account_id]}) for a in accounts]
                    + [("所有本人账户", {"account_ids": [a.account_id for a in accounts]})], "accounts")
        request = {"scope": {"account_ids": state["account_ids"], "start_at": state["period"][0],
                              "end_at": state["period"][1]}, "mode": state["mode"],
                   "category": state["category"] if state["mode"] == "details" else None}
        result = self.service.summarize(context, request)
        if (result.status == TaskStatus.SUCCEEDED and state["mode"] == "summary"
                and state["category"] and not state.get("negative_category")):
            category = next(c for c in result.data.categories if c.category == state["category"])
            label = next(word for word, code in _CATEGORIES.items() if code.value == state["category"])
            result = result.model_copy(update={"message":
                f"所选本人账户范围内，{label}支出 {money(category.outflow_fen)} 元，"
                f"退款 {money(category.refund_fen)} 元，净额 {money(category.net_fen)} 元。"})
        if result.error and result.error.code in {"DEPENDENCY_UNAVAILABLE", "INCOMPLETE_FACTS"}:
            return self._wait(context, state, result.message + "没有把失败当成零元账单。",
                              [("重新查询原范围", {"retry": True})], "retry")
        return result

    def start(self, trusted: TrustedContext, request: StartTransferInput, *, thread_id=None) -> ModuleResult:
        if not isinstance(request, StartTransferInput) or _SECRET.search(request.intent_text):
            return fail(trusted, BillsError("INVALID_ARGUMENT"))
        saved, state = self._load(trusted, thread_id)
        digest = sha256(request.intent_text.encode("utf-8")).hexdigest()
        if state is not None:
            if state["session_id"] != trusted.session_id:
                raise PermissionError("ACCESS_DENIED")
            if state["request_id"] != str(request.request_id) or state["intent_digest"] != digest:
                raise ValueError("REQUEST_CONFLICT")
            if "result" in state:
                return self._result(trusted, state)
        else:
            # Persist only parsed constraints, not raw user text or model-produced bank facts.
            categories = [code.value for word, code in _CATEGORIES.items() if word in request.intent_text]
            excluded = _negative_category(request.intent_text)
            state = {"actor": list(_actor(trusted)), "session_id": trusted.session_id,
                "request_id": str(request.request_id), "intent_digest": digest,
                "period": parse_month(request.intent_text, self.service.clock()),
                "mode": "details" if "明细" in request.intent_text else "summary",
                "category": categories[0] if len(categories) == 1 and excluded is None else None,
                "negative_category": excluded,
                "all_accounts": any(word in request.intent_text for word in ("所有账户", "全部账户", "所有本人账户")),
                "account_ids": None, "choices": {}, "wait_reason": None}
            self._save(trusted, thread_id, state)
        result = self._advance(trusted, state)
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result

    def resume(self, trusted: TrustedContext, response: dict, *, thread_id=None) -> ModuleResult:
        saved, state = self._load(trusted, thread_id)
        if state is None:
            raise ValueError("TASK_NOT_FOUND")
        if state["session_id"] != trusted.session_id:
            raise PermissionError("ACCESS_DENIED")
        if state.get("result", {}).get("status") in _TERMINAL:
            return self._result(trusted, state)
        if not response:
            if "result" in state:
                return self._result(trusted, state)
            result = self._advance(trusted, state)
        elif response.get("cancel") is True or response.get("choice") == "cancel":
            result = ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
                status=TaskStatus.CANCELLED, data=None, message="已取消账单查询。",
                interaction=None, error=None, allowed_actions=[], recovery_required=False, recovery_reason=None)
        else:
            interaction = state.get("result", {}).get("interaction")
            if not interaction or ("interaction_id" in response and response["interaction_id"] != interaction["interaction_id"]):
                raise ValueError("INTERACTION_STALE")
            if set(response) - {"choice", "selected_option_id", "interaction_id"}:
                raise ValueError("INVALID_ARGUMENT")
            choice = response.get("choice", response.get("selected_option_id"))
            if choice not in state["choices"]:
                raise ValueError("INVALID_OPTION")
            selected = state["choices"][choice]
            state.update({k: v for k, v in selected.items()
                          if k in {"period", "account_ids", "negative_category", "category"}})
            state["choices"] = {}
            state.pop("result", None)
            self._save(trusted, thread_id, state)
            result = self._advance(trusted, state)
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result

    def checkpoint_context(self, trusted: TrustedContext, *, thread_id=None):
        saved, state = self._load(trusted, thread_id)
        if state is None:
            return None
        return trusted.model_copy(update={"session_id": state["session_id"]})

    def recover_session(self, trusted: TrustedContext, *, source_session_id: str, thread_id=None):
        saved, state = self._load(trusted, thread_id)
        if state is None or state["session_id"] not in {source_session_id, trusted.session_id}:
            raise PermissionError("ACCESS_DENIED")
        state["session_id"] = trusted.session_id
        if state.get("result", {}).get("status") in _TERMINAL:
            result = self._result(trusted, state)
        else:
            # Re-authorize every B08 read after the new session. Never reuse a passed flag.
            result = self._wait(trusted, state, "登录会话已更新，请选择是否继续原账单查询。",
                                [("继续原范围", {"retry": True})], "session")
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result


def bills_factory(reads_factory: Callable, clock: Callable[[], datetime]):
    """Platform injects security-checked reads per task; there is no allow-all default."""
    def create(trusted, saver, trace):
        return BillsEntry(BillsService(reads_factory(trusted, trace), clock), saver, trace)
    return create


def register_bills(registry, reads_factory: Callable, clock: Callable[[], datetime]):
    from .manifest import MANIFEST
    registry.register_module(MANIFEST, bills_factory(reads_factory, clock))
