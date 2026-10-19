"""L02 task continuation over the existing entry protocol and F10 options.

The platform currently supplies StartTransferInput to every module. Only the
original intent and request ID are used; proposal amount/payee fields are never
bank facts. Candidate option IDs map to account/transaction IDs in the scoped
durable checkpoint, and selecting one always re-reads the original bank range.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import re
from typing import Callable
from uuid import uuid4

from app.contracts.bills import (
    AnomalyResult, BillScope, DetectAnomaliesInput, TransactionCandidates, TransactionClues,
)
from app.contracts.common import Category, TaskStatus
from app.contracts.platform import StartTransferInput, TrustedContext
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult
from ._anomalies import BEIJING
from .anomaly_service import BillsAnomalyService, minus_months
from .entry import _SECRET, _actor, month_range, parse_month
from .service import BillsError, fail, money

_CHANNEL = "bills_anomaly_state"
_TERMINAL = {"succeeded", "failed", "cancelled"}
_CATEGORIES = {"餐饮": Category.DINING, "交通": Category.TRANSPORT, "医疗": Category.MEDICAL,
               "购物": Category.SHOPPING, "居住": Category.HOUSING, "转账": Category.TRANSFER,
               "其他": Category.OTHER}
_MERCHANT_HINT = r"(?:商户|收款方|对方)(?:是|为|[:：])?\s*[“\"「『]([^”\"」』]+)[”\"」』]"
_CHANNEL_HINT = r"渠道(?:是|为|[:：])?\s*[“\"「『]([^”\"」』]+)[”\"」』]"


def _intent_constraints(text):
    """Quoted hint values cannot supply instructions for other query fields."""
    return re.sub(_CHANNEL_HINT, "", re.sub(_MERCHANT_HINT, "", text))


def _clues(text: str) -> tuple[dict, bool]:
    """Parse only exact hints; ambiguous/exclusion requests need an explicit choice."""
    merchants = re.findall(_MERCHANT_HINT, text)
    channels = re.findall(_CHANNEL_HINT, text)
    # Merchant/channel literals are values, not numeric or category instructions.
    constraints = _intent_constraints(text)
    # Chinese prose can touch the number; the exclusion below only protects
    # Latin/scientific tokens, not Chinese characters before a normal amount.
    amounts = re.findall(r"(?<![A-Za-z\d_.+-])([+-]?\d[\d,.，]*(?:[eE][+-]?\d+)?)\s*(?:元|块(?:钱)?)(?!\d)", constraints)
    categories = [value.value for label, value in _CATEGORIES.items() if label in constraints]
    ambiguous = any(len(items) > 1 for items in (amounts, merchants, channels, categories))
    if any(not re.fullmatch(r"\d+(?:\.\d{1,2})?", value) for value in amounts):
        ambiguous = True
    if (not amounts and re.search(r"\d\s*(?:元|块)", constraints)) or re.search(r"\d+\s*分", constraints):
        ambiguous = True
    if any(word in constraints for word in ("不是", "不含", "不包括", "排除", "不要算", "大约", "大概", "左右",
                                     "多于", "少于", "超过", "大于", "小于", "至少", "至多", "以上", "以下")):
        ambiguous = True
    if ambiguous:
        return {}, True
    values = {}
    if amounts:
        whole, _, decimal = amounts[0].partition(".")
        values["amount_fen"] = int(whole) * 100 + int(decimal.ljust(2, "0") or "0")
    for name, items in (("counterparty_hint", merchants), ("channel", channels), ("category", categories)):
        if items:
            values[name] = items[0]
    return values, False


def _period(text, now):
    text = _intent_constraints(text)
    # The current F10 adapter handles full-month choices. A recognized month
    # must not erase an unsupported day/half-month or a second requested month.
    if any(word in text for word in ("上半月", "下半月", "前半月", "后半月", "上旬", "中旬", "下旬",
                                     "月初", "月中", "月末", "月底", "今天", "昨天", "前天", "周末",
                                     "工作日", "本周", "上周", "截至", "截止", "之前", "之后")):
        return None
    if re.search(r"\d{1,2}\s*[日号]|\d{1,4}[-/]\d{1,2}[-/]\d{1,2}", text):
        return None
    months = re.findall(r"(?:\d{4}年)?\d{1,2}月|(?<!\d)\d{4}-\d{1,2}(?!\d)", text)
    relatives = sum(text.count(word) for word in ("本月", "这个月", "上月", "上个月"))
    if len(months) + relatives > 1:
        return None
    if "最近三个完整月份" in text:
        if re.search(r"\d{4}(?:年|-)\d{1,2}|本月|上月|上个月|这个月|对比|至|到", text):
            return None
        end = now.astimezone(BEIJING).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return minus_months(end, 3).isoformat(), end.isoformat()
    return parse_month(text, now)


class BillsAnomalyEntry:
    """The scoped saver owns state; there is no process-global candidate cache."""

    def __init__(self, service: BillsAnomalyService, saver, trace):
        self.service, self.saver, self.trace = service, saver, trace

    @staticmethod
    def _config(context, thread_id):
        return {"configurable": {"thread_id": thread_id or context.task_id, "checkpoint_ns": ""}}

    def _load(self, context, thread_id):
        saved = self.saver.get_tuple(self._config(context, thread_id))
        if saved is None:
            return None, None
        state = deepcopy(saved.checkpoint["channel_values"].get(_CHANNEL))
        if not isinstance(state, dict) or tuple(state.get("actor", ())) != _actor(context):
            raise PermissionError("ACCESS_DENIED")
        return saved, state

    def _save(self, context, thread_id, state):
        saved, _ = self._load(context, thread_id)
        version = int(saved.checkpoint["channel_versions"].get(_CHANNEL, 0)) + 1 if saved else 1
        checkpoint = {"v": 1, "id": str(uuid4()), "ts": self.service.clock().isoformat(),
            "channel_values": {_CHANNEL: deepcopy(state)}, "channel_versions": {_CHANNEL: version},
            "versions_seen": {}, "pending_sends": []}
        self.saver.put(saved.config if saved else self._config(context, thread_id), checkpoint,
            {"source": "update", "step": version, "parents": {}}, {_CHANNEL: version})

    @staticmethod
    def _result(context, state):
        result = ModuleResult.model_validate(state["result"])
        data = result.data
        if isinstance(data, dict):
            model = TransactionCandidates if "candidates" in data else AnomalyResult
            data = model.model_validate(data)
        return result.model_copy(update={"run_id": context.run_id, "data": data})

    def _wait(self, context, state, prompt, choices, reason, *, data=None):
        state["choices"] = {str(uuid4()): value for _, value in choices}
        options = [InteractionOption(id=key, label=label)
                   for key, (label, _) in zip(state["choices"], choices)]
        state["wait_reason"] = reason
        return ModuleResult(task_id=context.task_id, run_id=context.run_id,
            status=TaskStatus.WAITING_INPUT, data=data, message=prompt,
            interaction=InteractionRequest(interaction_id=str(uuid4()), kind="input", prompt=prompt,
                required_fields=["bills_anomaly_selection"], options=options, record_ref=None),
            error=None, allowed_actions=["provide_input", "cancel"],
            recovery_required=False, recovery_reason=None)

    def _period_choices(self, state):
        now = self.service.clock().astimezone(BEIJING)
        choices = []
        if state["mode"] == "scan":
            choices.append(("最近三个完整月份", {"period": _period("最近三个完整月份", now)}))
        for offset, label in [(0, "本月"), (1, "上月"), (2, "前两个月")]:
            index = now.year * 12 + now.month - 1 - offset
            choices.append((label, {"period": month_range(index // 12, index % 12 + 1)}))
        return choices

    def _failure(self, context, state, result):
        if not result.error:
            return result
        code = result.error.code
        if code in {"DEPENDENCY_UNAVAILABLE", "INCOMPLETE_FACTS"}:
            return self._wait(context, state, "没有取得完整银行流水，暂时不能核对异常。请重试原范围。",
                              [("重新读取原范围", {"retry": True})], "retry")
        if code in {"RECORD_NOT_FOUND", "BILLS_LOCATE_REQUIRED"}:
            return self._wait(context, state, "当前银行记录已无法核对原候选，请重新定位。",
                              [("重新定位原范围", {"selected": None})], "retry")
        if code == "RANGE_UNSUPPORTED":
            return self._wait(context, state, result.message,
                              [("重新选择月份", {"period": None, "selected": None})], "period")
        return result

    def _select(self, context, state, scope):
        selected = state["selected"]
        result = self.service.detect(context, DetectAnomaliesInput(mode="single",
            account_id=selected["account_id"], transaction_id=selected["transaction_id"]),
            located_scope=scope)
        if result.status == TaskStatus.SUCCEEDED:
            row = result.data.transaction
            local = row.occurred_at.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
            result = result.model_copy(update={"message":
                f"银行记录：{local}（北京时间），{money(row.amount_fen)} 元，"
                f"商户或收款方：{row.counterparty_name}，渠道：{row.channel or '未知'}。" + result.message})
        return self._failure(context, state, result)

    def _advance(self, context, state):
        if state["mode"] is None:
            return self._wait(context, state, "你想核对哪类账单问题？",
                [("核对一笔交易", {"mode": "locate"}), ("检查周期扣款", {"mode": "scan"})], "mode")
        if state["period"] is None:
            return self._wait(context, state, "请明确银行查询范围。当前对话支持完整月份，请选择下列范围，或在新请求中注明具体年月。",
                              self._period_choices(state), "period")
        if state["mode"] == "locate" and state["clues_need_confirmation"]:
            return self._wait(context, state, "金额、类别或商户线索有歧义，可以先列出原范围流水再选择。",
                [("列出原范围流水", {"clues": {}, "clues_need_confirmation": False})], "clues")
        if state["account_ids"] is None:
            try:
                accounts = self.service.accounts(context).accounts
            except BillsError as error:
                return self._failure(context, state, fail(context, error))
            except Exception:
                return self._failure(context, state, fail(context, BillsError("DEPENDENCY_UNAVAILABLE")))
            if not accounts:
                return fail(context, BillsError("ACCESS_DENIED", source="security"))
            if state["all_accounts"]:
                state["account_ids"] = [a.account_id for a in accounts]
            else:
                choices = [(a.display_name + " · " + a.account_masked,
                            {"account_ids": [a.account_id]}) for a in accounts]
                choices.append(("所有本人账户", {"account_ids": [a.account_id for a in accounts]}))
                return self._wait(context, state, "请选择查询的本人账户。", choices, "accounts")
        scope = BillScope(account_ids=state["account_ids"], start_at=state["period"][0], end_at=state["period"][1])
        if state["mode"] == "scan":
            return self._failure(context, state,
                self.service.detect(context, DetectAnomaliesInput(mode="scan", scope=scope)))
        if state["selected"] is not None:
            return self._select(context, state, scope)
        if state["clues"]:
            result = self.service.detect(context, DetectAnomaliesInput(mode="locate", scope=scope,
                                         clues=TransactionClues.model_validate(state["clues"])))
        else:
            result = self.service.candidates(context, scope)
        if result.status != TaskStatus.SUCCEEDED:
            return self._failure(context, state, result)
        candidates = result.data.candidates
        if len(candidates) == 1:
            state["selected"] = {"account_id": candidates[0].account_id,
                                 "transaction_id": candidates[0].transaction_id}
            return self._select(context, state, scope)
        if not candidates:
            choices = [("重新选择月份", {"period": None}),
                       ("重新选择本人账户", {"account_ids": None, "all_accounts": False}),
                       ("重新读取原范围", {"retry": True})]
            if state["clues"]:
                choices.insert(0, ("去掉线索，列出原范围流水", {"clues": {}}))
            return self._wait(context, state, "完整查询后没有符合线索的流水。请调整查询条件；这不代表没有异常。",
                              choices, "no_candidates", data=result.data)
        choices = []
        for number, row in enumerate(candidates, 1):
            when = row.occurred_at.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
            label = (f"{number} · {when} · {money(row.amount_fen)}元 · {row.counterparty_name}"
                     f" · {row.counterparty_account_masked or '账号未知'} · 渠道：{row.channel or '未知'}")
            choices.append((label, {"selected": {"account_id": row.account_id,
                                                 "transaction_id": row.transaction_id}}))
        return self._wait(context, state, "找到多笔候选流水，请选择要核对的一笔（时间为北京时间）。",
                          choices, "candidates", data=result.data)

    def start(self, trusted: TrustedContext, request: StartTransferInput, *, thread_id=None):
        if not isinstance(request, StartTransferInput) or _SECRET.search(request.intent_text):
            return fail(trusted, BillsError("INVALID_ARGUMENT"))
        _, state = self._load(trusted, thread_id)
        digest = sha256(request.intent_text.encode("utf-8")).hexdigest()
        if state is not None:
            if state["session_id"] != trusted.session_id:
                raise PermissionError("ACCESS_DENIED")
            if state["request_id"] != str(request.request_id) or state["intent_digest"] != digest:
                raise ValueError("REQUEST_CONFLICT")
            if "result" in state:
                return self._result(trusted, state)
        else:
            text = request.intent_text
            clues, ambiguous = _clues(text)
            constraints = _intent_constraints(text)
            scan = any(word in constraints for word in ("周期扣款", "重复扣款", "每月扣款"))
            single = bool(clues) or any(word in constraints for word in ("这笔", "那笔", "单笔", "核对交易", "异常交易"))
            state = {"actor": list(_actor(trusted)), "session_id": trusted.session_id,
                "request_id": str(request.request_id), "intent_digest": digest,
                "mode": None if scan and single else "scan" if scan else "locate" if single else None,
                "period": _period(text, self.service.clock()), "clues": clues,
                "clues_need_confirmation": ambiguous,
                "all_accounts": any(word in constraints for word in ("所有账户", "全部账户", "所有本人账户")),
                "account_ids": None, "selected": None, "choices": {}, "wait_reason": None}
            self._save(trusted, thread_id, state)
        result = self._advance(trusted, state)
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result

    def resume(self, trusted: TrustedContext, response: dict, *, thread_id=None):
        _, state = self._load(trusted, thread_id)
        if state is None:
            raise ValueError("TASK_NOT_FOUND")
        if state["session_id"] != trusted.session_id:
            raise PermissionError("ACCESS_DENIED")
        if state.get("result", {}).get("status") in _TERMINAL:
            return self._result(trusted, state)
        if not isinstance(response, dict):
            raise ValueError("INVALID_ARGUMENT")
        if not response and "result" in state:
            return self._result(trusted, state)
        if not response:
            result = self._advance(trusted, state)
        elif response in ({"cancel": True}, {"choice": "cancel"}):
            result = ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
                status=TaskStatus.CANCELLED, data=None, message="已取消本次异常核对。",
                interaction=None, error=None, allowed_actions=[], recovery_required=False, recovery_reason=None)
        else:
            if set(response) - {"choice", "selected_option_id", "interaction_id"}:
                raise ValueError("INVALID_ARGUMENT")
            interaction = state.get("result", {}).get("interaction")
            if not interaction or ("interaction_id" in response
                    and response["interaction_id"] != interaction["interaction_id"]):
                raise ValueError("INTERACTION_STALE")
            choice = response.get("choice", response.get("selected_option_id"))
            if "choice" in response and "selected_option_id" in response and response["choice"] != response["selected_option_id"]:
                raise ValueError("INVALID_OPTION")
            if not isinstance(choice, str) or choice not in state["choices"]:
                raise ValueError("INVALID_OPTION")
            # This mapping is server state. Client IDs, amounts and flags never update it.
            selected = state["choices"][choice]
            state.update({key: deepcopy(value) for key, value in selected.items() if key != "retry"})
            state["choices"] = {}
            state.pop("result", None)
            self._save(trusted, thread_id, state)
            result = self._advance(trusted, state)
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result

    def checkpoint_context(self, trusted: TrustedContext, *, thread_id=None):
        _, state = self._load(trusted, thread_id)
        return None if state is None else trusted.model_copy(update={"session_id": state["session_id"]})

    def recover_session(self, trusted: TrustedContext, *, source_session_id: str, thread_id=None):
        _, state = self._load(trusted, thread_id)
        if state is None or state["session_id"] not in {source_session_id, trusted.session_id}:
            raise PermissionError("ACCESS_DENIED")
        state["session_id"] = trusted.session_id
        if state.get("result", {}).get("status") in _TERMINAL:
            result = self._result(trusted, state)
        else:
            state["selected"] = None
            result = self._wait(trusted, state, "登录会话已更新，请继续原范围并重新核对银行候选。",
                                [("继续原范围", {"retry": True})], "session")
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result


def register_bills_anomalies(registry, reads_factory: Callable, clock: Callable[[], datetime]):
    """Register L02 separately; platform injects real task-scoped security reads."""
    from .anomaly_manifest import ANOMALY_MANIFEST

    def create(trusted, saver, trace):
        return BillsAnomalyEntry(BillsAnomalyService(reads_factory(trusted, trace), clock), saver, trace)

    registry.register_module(ANOMALY_MANIFEST, create)
