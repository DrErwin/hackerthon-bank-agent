"""L01 task entry using the platform's scoped checkpointer and F10 option replies.

Chat starts use StartTransferInput; registered callers may use the declared
bills input model. Transfer amounts/payees never become bill facts.
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

from app.contracts.bills import (
    BillDetails, BillReport, BillScope, BillSummarizeInput, GenerateReportInput, SpendingSummary,
)
from pydantic import ValidationError
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


def parse_report_period(text: str, now: datetime) -> tuple[str, str] | None:
    """L03 report time scope: explicit month, this year, last year, or YYYY year.

    Use Beijing calendar boundaries; incomplete current year ends at the trusted
    clock, not at a model-guessed future date. Any comparison remains unresolved.
    """
    if any(word in text for word in ("相比", "对比", "比较", "比上", "比去", "同比", "环比",
                                     "多了", "少了", "增长", "下降", "到", "至", "之间",
                                     "季度", "半年", "半月", "半个月", "上旬", "中旬", "下旬",
                                     "月初", "月中", "月底", "月末")):
        return None
    # Colloquial comparisons are not a single-period report request.
    # Fail closed before asking the bank to read a one-sided time range.
    if re.search(r"(?:跟|和|与|同)[^，。；;]{0,12}比", text):
        return None
    if re.search(r"[\d一二三四五六七八九十两]+\s*(?:日|号|天|周)", text):
        return None
    relative = [x for x in ("今年", "去年") if x in text]
    month = parse_month(text, now)
    if month is not None:
        # parse_month handles one year-qualified month. A second bare month or
        # year must not disappear (e.g. "2026年9月和10月" or "本月和9月").
        remainder = re.sub(r"(?<!\d)\d{4}(?:年|-)\d{1,2}(?:月)?(?!\d|[-/])|本月|这个月|上月|上个月",
                           "", text, count=1)
        more_time = re.search(r"[\d一二三四五六七八九十两]+\s*(?:月|年)|本月|这个月|上月|上个月", remainder)
        if relative or more_time:
            return None
        # Year-qualified months and relative months use the same trusted date
        # bounds; otherwise future/9999 month requests could succeed empty.
        local = now.astimezone(BEIJING)
        start_at = datetime.fromisoformat(month[0])
        return None if start_at > local or start_at.year >= 9999 else month
    # A failed or unsupported month expression must never become a whole year.
    if re.search(r"(?:[\d一二三四五六七八九十两]+\s*月|本月|上月|个月)", text):
        return None
    years = re.findall(r"(?<!\d)(\d{4})年(?:度|全年)?", text)
    if len(relative) + len(years) != 1:
        return None
    local = now.astimezone(BEIJING)
    year = local.year if relative == ["今年"] else local.year - 1 if relative == ["去年"] else int(years[0])
    if not 1 <= year < 9999 or year > local.year:
        return None
    start = datetime(year, 1, 1, tzinfo=BEIJING)
    end = datetime(year + 1, 1, 1, tzinfo=BEIJING)
    if start > local:
        return None
    return start.isoformat(), (min(end, local) if year == local.year else end).isoformat()


def _actor(context: TrustedContext) -> tuple[str, str, str]:
    return context.user_id, context.demo_round_id, context.task_id


def inherit_scope(state, text: str, scope: BillScope | None):
    """A server-checked prior query is context, never a replacement for new intent."""
    if scope is None:
        return
    scope = BillScope.model_validate(scope)
    if not any(word in text for word in (*_CATEGORIES, "明细", "这笔", "那笔", "陌生", "核对", "扣款", "继续")):
        return
    # Unsupported new dates must be clarified instead of silently reusing old dates.
    if state["period"] is None and not re.search(r"年|月|日|号|天|周|星期|礼拜|旬|期|最近|至|到|之前|之后|之间|截至|截止|\d{4}[-/]", text):
        state["period"] = (scope.start_at.isoformat(), scope.end_at.isoformat())
    # Account changes always use the existing own-account chooser.
    if not re.search(r"账户|账号|帐号|卡|存折|A\d+", text, re.I):
        state["account_ids"] = list(scope.account_ids)


class BillsEntry:
    """Implements the existing TransferEntry protocol without transfer semantics.

    The harness serializes calls per task. The saver is its scoped durable saver,
    not a module-global memory dictionary. Each read still goes through security.
    """
    def __init__(self, service: BillsService, saver, trace, *,
                 capability_name: str = "bills.summarize"):
        if capability_name not in {"bills.summarize", "bills.generate_report"}:
            raise ValueError("UNSUPPORTED_BILLS_CAPABILITY")
        self.service, self.saver, self.trace = service, saver, trace
        self.capability_name = capability_name

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

    def _result(self, context, state):
        result = ModuleResult.model_validate(state["result"])
        if self.capability_name == "bills.generate_report" and result.status == TaskStatus.SUCCEEDED:
            try:
                result = result.model_copy(update={"data": BillReport.model_validate(result.data)})
            except (ValidationError, ValueError, TypeError):
                return fail(context, BillsError("BILLS_RESULT_INVALID"))
        if state.get("typed_request") is not None and result.status == TaskStatus.SUCCEEDED:
            model = (BillReport if self.capability_name == "bills.generate_report" else
                     BillDetails if state["typed_request"]["mode"] == "details" else SpendingSummary)
            result = result.model_copy(update={"data": model.model_validate(result.data)})
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
        if state.get("typed_request") is not None:
            request = state["typed_request"]
            result = (self.service.generate_report(context, request)
                      if self.capability_name == "bills.generate_report"
                      else self.service.summarize(context, request))
            if result.error and result.error.code in {"DEPENDENCY_UNAVAILABLE", "INCOMPLETE_FACTS"}:
                return self._wait(context, state, result.message + "没有把失败当成零元账单。",
                                  [("重新查询原范围", {"retry": True})], "retry")
            return result
        if state["period"] is None:
            now = self.service.clock().astimezone(BEIJING)
            choices = []
            for offset, label in [(0, "本月"), (1, "上月"), (2, "前两个月")]:
                index = now.year * 12 + now.month - 1 - offset
                choices.append((label, {"period": month_range(index // 12, index % 12 + 1)}))
            return self._wait(context, state,
                "当前支持按完整月份查询。请选择下列月份，或重新输入具体年月，例如2026年9月。",
                choices, "period")
        if self.capability_name == "bills.generate_report" and state.get("report_filter_unresolved"):
            return self._wait(context, state,
                "当前报告包含全部类别的总览、分类和对比，不提供单类筛选或逐笔明细。是否查看全部类别报告？",
                [("查看全部类别报告", {"report_filter_unresolved": False,
                    "negative_category": None, "category": None})], "report_filter")
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
        scope = {"account_ids": state["account_ids"], "start_at": state["period"][0],
                 "end_at": state["period"][1]}
        if self.capability_name == "bills.generate_report":
            # L03 carries only trusted scope and the restricted purpose value.
            # The platform persists the typed BillReport before F21/F22 may read it.
            result = self.service.generate_report(context, {
                "scope": scope, "purpose": state.get("report_purpose", "self_view")})
        else:
            request = {"scope": scope, "mode": state["mode"],
                       "category": state["category"] if state["mode"] == "details" else None}
            result = self.service.summarize(context, request)
        if (self.capability_name == "bills.summarize"
                and result.status == TaskStatus.SUCCEEDED and state["mode"] == "summary"
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

    def start(self, trusted: TrustedContext, request: StartTransferInput | BillSummarizeInput | GenerateReportInput, *, thread_id=None,
              inherited_scope: BillScope | None = None) -> ModuleResult:
        typed_model = (GenerateReportInput if self.capability_name == "bills.generate_report"
                       else BillSummarizeInput)
        if not isinstance(request, (StartTransferInput, typed_model)):
            return fail(trusted, BillsError("INVALID_ARGUMENT"))
        typed = isinstance(request, typed_model)
        if not typed and _SECRET.search(request.intent_text):
            return fail(trusted, BillsError("INVALID_ARGUMENT"))
        saved, state = self._load(trusted, thread_id)
        content = (typed_model.__name__ + request.model_dump_json() if typed else request.intent_text)
        digest = sha256(content.encode("utf-8")).hexdigest()
        request_id = None if typed else str(request.request_id)
        if state is not None:
            if state["session_id"] != trusted.session_id:
                raise PermissionError("ACCESS_DENIED")
            if state["request_id"] != request_id or state["intent_digest"] != digest:
                raise ValueError("REQUEST_CONFLICT")
            if "result" in state:
                return self._result(trusted, state)
        elif typed:
            state = {"actor": list(_actor(trusted)), "session_id": trusted.session_id,
                "request_id": request_id, "intent_digest": digest,
                "typed_request": request.model_dump(mode="json"),
                "period": (request.scope.start_at.isoformat(), request.scope.end_at.isoformat()),
                "account_ids": list(request.scope.account_ids), "choices": {}, "wait_reason": None}
            self._save(trusted, thread_id, state)
        else:
            # Persist only parsed constraints, not raw user text or model-produced bank facts.
            categories = [code.value for word, code in _CATEGORIES.items() if word in request.intent_text]
            excluded = _negative_category(request.intent_text)
            state = {"actor": list(_actor(trusted)), "session_id": trusted.session_id,
                "request_id": str(request.request_id), "intent_digest": digest,
                "period": (parse_report_period(request.intent_text, self.service.clock())
                           if self.capability_name == "bills.generate_report"
                           else parse_month(request.intent_text, self.service.clock())),
                "mode": "details" if "明细" in request.intent_text else "summary",
                "category": categories[0] if len(categories) == 1 and excluded is None else None,
                "negative_category": excluded,
                "report_filter_unresolved": (self.capability_name == "bills.generate_report"
                                              and bool(categories or "明细" in request.intent_text)),
                "report_purpose": ("print" if any(w in request.intent_text for w in ("打印", "纸质"))
                                   else "share_request" if any(w in request.intent_text
                                       for w in ("分享", "给孩子看", "给子女看"))
                                   else "self_view"),
                "all_accounts": any(word in request.intent_text for word in ("所有账户", "全部账户", "所有本人账户")),
                "account_ids": None, "choices": {}, "wait_reason": None}
            inherit_scope(state, request.intent_text, inherited_scope)
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
                          if k in {"period", "account_ids", "negative_category", "category",
                                   "report_filter_unresolved"}})
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


def bills_report_factory(reads_factory: Callable, clock: Callable[[], datetime]):
    """A separate entry factory is essential: registry dispatches by capability."""
    from .report_service import BillsReportService

    def create(trusted, saver, trace):
        return BillsEntry(BillsReportService(reads_factory(trusted, trace), clock),
                          saver, trace, capability_name="bills.generate_report")
    return create


def register_bills_report(registry, reads_factory: Callable, clock: Callable[[], datetime]):
    """Augment the existing real bills registry; never impersonate export grants."""
    from .manifest import REPORT_MANIFEST
    registry.register_module(REPORT_MANIFEST, bills_report_factory(reads_factory, clock))
