"""Cross task entry: life-goal plans over the platform's controlled children.

The chat path hands this entry the platform envelope (``StartTransferInput``,
whose intent text is the user's goal); a parent caller may dispatch it with the
declared ``CrossStartInput``. The entry turns the goal into one deterministic
plan, runs every bank touch through dispatched child capabilities, and reports
what is done, waiting, failed or unknown — never a bank success the children
did not return. Sensitive actions keep their own confirmation and verification
inside the child task: adopting a plan approves nothing by itself.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from app.contracts.bank import SavedPayee
from app.contracts.bills import BillScope, BillSummarizeInput
from app.contracts.common import TaskStatus
from app.contracts.cross import CrossScenario, CrossStartInput
from app.contracts.platform import StartTransferInput, TrustedContext
from app.contracts.subscription import SubscriptionCancelInput, SubscriptionListInput
from app.contracts.tasks import (
    InteractionOption, InteractionRequest, ModuleError, ModuleResult,
)

from . import plan
from .plan import money, month_range
from .pension import PensionFlow

_CHANNEL = "cross_state"
_TERMINAL = {"succeeded", "failed", "cancelled", "partially_succeeded"}

_EXPENSE_WORDS = ("减支", "减少", "省钱", "省一点", "不用的", "不用了", "不必要的", "开销",
                  "扣费", "自动扣费", "退订", "订阅", "会员")
_PENSION_WORDS = ("养老金", "退休金", "生活费安排", "每月安排", "工资安排")
_BIRTHDAY_WORDS = ("生日", "过生", "祝寿", "寿宴")

SUPPORTED = (
    ("减少不用的开销（查签约、逐项退订）", CrossScenario.EXPENSE_REDUCTION),
    ("安排本月养老金（明确资金范围与留存，逐笔转账）", CrossScenario.MONTHLY_ARRANGEMENT),
)

_CATEGORY_LABELS = {"dining": "餐饮", "transport": "交通", "medical": "医疗",
                    "shopping": "购物", "housing": "居住", "transfer": "转账",
                    "other": "其他"}


def _actor(context: TrustedContext) -> tuple[str, str, str]:
    return context.user_id, context.demo_round_id, context.task_id


def infer_scenario(goal: str) -> CrossScenario | None:
    """One life goal per goal text, or None: ambiguity is clarified, not guessed."""

    words = {
        CrossScenario.EXPENSE_REDUCTION: _EXPENSE_WORDS,
        CrossScenario.MONTHLY_ARRANGEMENT: _PENSION_WORDS,
        CrossScenario.BIRTHDAY: _BIRTHDAY_WORDS,
    }
    matched = [scenario for scenario, hints in words.items()
               if any(word in goal for word in hints)]
    return matched[0] if len(matched) == 1 else None


def _unsupported_note(scenario: CrossScenario | None) -> str:
    if scenario is CrossScenario.BIRTHDAY:
        return "生日办理需要先接通安全执行能力（安全组票 01），暂时不能办理。"
    return ""


class CrossEntry:
    """Implements the registry's task-entry protocol for the cross module."""

    def __init__(self, harness, saver, trace, clock):
        self.harness, self.saver, self.trace = harness, saver, trace
        self.clock = clock

    # ---------------------------------------------------------------- checkpoint

    def _config(self, context, thread_id):
        # The platform passes the task's checkpoint thread; a direct caller's
        # saver already carries its own scope, which is the safe fallback.
        thread = thread_id or getattr(self.saver, "thread_id", None) or context.task_id
        return {"configurable": {"thread_id": thread, "checkpoint_ns": ""}}

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
        checkpoint = {"v": 1, "id": str(uuid4()), "ts": self.clock().isoformat(),
                      "channel_values": {_CHANNEL: deepcopy(state)},
                      "channel_versions": {_CHANNEL: version}, "versions_seen": {},
                      "pending_sends": []}
        config = saved.config if saved else self._config(context, thread_id)
        self.saver.put(config, checkpoint, {"source": "update", "step": version, "parents": {}},
                       {_CHANNEL: version})

    def _result(self, context, state) -> ModuleResult:
        return ModuleResult.model_validate(state["result"]).model_copy(
            update={"run_id": context.run_id})

    # -------------------------------------------------------------- interactions

    def _ask(self, context, state, prompt: str, choices: list[tuple[str, dict]]) -> ModuleResult:
        """One parent-owned menu; only these server-built option ids answer it."""

        interaction_id = str(uuid4())
        state["choices"] = {str(uuid4()): value for _, value in choices}
        state["waiting"] = "ask"
        state["interaction_id"] = interaction_id
        options = [InteractionOption(id=key, label=label)
                   for key, (label, _) in zip(state["choices"], choices)]
        return ModuleResult(task_id=context.task_id, run_id=context.run_id,
            status=TaskStatus.WAITING_INPUT, data=None, message=prompt,
            interaction=InteractionRequest(interaction_id=interaction_id, kind="input",
                prompt=prompt, required_fields=["cross_selection"], options=options,
                record_ref=None),
            error=None, allowed_actions=["provide_input", "cancel"],
            recovery_required=False, recovery_reason=None)

    def _done(self, context, state, status: TaskStatus, message: str) -> ModuleResult:
        state["waiting"] = None
        state["choices"] = {}
        return ModuleResult(task_id=context.task_id, run_id=context.run_id,
            status=status, data=self._view_data(state, message), message=message,
            interaction=None, error=None,
            allowed_actions=["query"] if status.value in _TERMINAL else ["resume", "cancel"],
            recovery_required=False, recovery_reason=None)

    @staticmethod
    def _view_data(state: dict, message: str):
        if "steps" not in state:
            return None  # a goal-clarify state owns no plan yet
        return plan.build_view(state, message)

    @classmethod
    def _view_data_full(cls, state: dict, message: str, active, child_id):
        if "steps" not in state:
            return None
        return plan.build_view(state, message,
                               active_step_id=active and active["step_id"],
                               interaction_task_id=child_id)

    def _view(self, context, state, message: str, *, active: dict | None = None,
              child_id: str | None = None) -> ModuleResult:
        """A running parent: the child owns the pending user response, if any."""

        state["waiting"] = None
        state["choices"] = {}
        return ModuleResult(task_id=context.task_id, run_id=context.run_id,
            status=TaskStatus.RUNNING,
            data=self._view_data_full(state, message, active, child_id),
            message=message, interaction=None, error=None,
            allowed_actions=["resume", "cancel"], recovery_required=False,
            recovery_reason=None)

    def _failed(self, context, code: str) -> ModuleResult:
        return ModuleResult(task_id=context.task_id, run_id=context.run_id,
            status=TaskStatus.FAILED, data=None,
            message="暂时无法处理这个目标，请稍后重新发起。",
            interaction=None, error=ModuleError(code=code, source="cross", field=None,
                reason="跨场景任务未能开始。", upstream_code=None),
            allowed_actions=[], recovery_required=False, recovery_reason=None)

    # -------------------------------------------------------------------- start

    def start(self, trusted: TrustedContext, request, *, thread_id=None) -> ModuleResult:
        if not isinstance(request, (CrossStartInput, StartTransferInput)):
            return self._failed(trusted, "INVALID_ARGUMENT")
        if isinstance(request, CrossStartInput):
            goal, scenario = request.goal, request.scenario
        else:
            goal, scenario = request.intent_text, None
        saved, state = self._load(trusted, thread_id)
        digest = sha256(goal.encode("utf-8")).hexdigest()
        if state is not None:
            if state["session_id"] != trusted.session_id:
                raise PermissionError("ACCESS_DENIED")
            if state["request_id"] != str(request.request_id) or state["goal_digest"] != digest:
                raise ValueError("REQUEST_CONFLICT")
            if "result" in state:
                return self._result(trusted, state)
        else:
            state = self._new_state(trusted, str(request.request_id), goal, digest, scenario)
        result = self._advance(trusted, state)
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result

    def _new_state(self, trusted, request_id: str, goal: str, digest: str,
                   scenario: CrossScenario | None) -> dict:
        inferred = scenario or infer_scenario(goal)
        if inferred is None or inferred not in (
                CrossScenario.EXPENSE_REDUCTION, CrossScenario.MONTHLY_ARRANGEMENT):
            # Nothing is decided for an unsupported or ambiguous goal; the user
            # picks from what this module can really run today.
            return {"actor": list(_actor(trusted)), "session_id": trusted.session_id,
                    "request_id": request_id, "goal_digest": digest, "goal": goal,
                    "scenario": None, "unsupported": inferred,
                    "choices": {}, "interaction_id": None, "result": None}
        if inferred is CrossScenario.MONTHLY_ARRANGEMENT:
            steps = [
                {"step_id": "accounts", "action": "transfer.list_accounts", "kind": "read",
                 "depends_on": []},
                {"step_id": "subscriptions", "action": "subscription.list_subscriptions",
                 "kind": "read", "depends_on": []},
                {"step_id": "bills_details", "action": "bills.summarize", "kind": "read",
                 "mode": "details", "depends_on": ["accounts"]},
            ]
            state = plan.new_state(trusted, request_id, inferred.value, digest, steps)
            state["goal"] = goal
            state["inventory"] = None
            state["bills"] = None
            state["pension"] = None
            return state
        steps = [
            {"step_id": "accounts", "action": "transfer.list_accounts", "kind": "read",
             "depends_on": []},
            {"step_id": "subscriptions", "action": "subscription.list_subscriptions",
             "kind": "read", "depends_on": []},
            {"step_id": "bills_compare", "action": "bills.summarize", "kind": "read",
             "depends_on": ["accounts"]},
        ]
        state = plan.new_state(trusted, request_id, inferred.value, digest, steps)
        state["goal"] = goal
        state["inventory"] = None
        state["bills"] = None
        return state

    # ------------------------------------------------------------------- resume

    def resume(self, trusted: TrustedContext, response: dict, *, thread_id=None) -> ModuleResult:
        saved, state = self._load(trusted, thread_id)
        if state is None:
            raise ValueError("TASK_NOT_FOUND")
        if state["session_id"] != trusted.session_id:
            raise PermissionError("ACCESS_DENIED")
        if state.get("result", {}).get("status") in _TERMINAL:
            return self._result(trusted, state)
        result = self._respond(trusted, state, response)
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result

    def _respond(self, trusted, state, response: dict) -> ModuleResult:
        if not response:
            return self._advance(trusted, state)
        if response.get("cancel") is True or response.get("choice") == "cancel":
            return self._closeout(trusted, state, stop_reason="user_cancelled")
        if set(response) - {"choice", "selected_option_id", "interaction_id", "text"}:
            raise ValueError("INVALID_ARGUMENT")
        if "interaction_id" in response and response["interaction_id"] != state.get("interaction_id"):
            raise ValueError("INTERACTION_STALE")
        choice = response.get("selected_option_id") or response.get("choice")
        if choice not in state.get("choices", {}):
            if response.get("text"):
                # Free text names no target: menus are built from bank facts only.
                # In the pension flow, typed numbers answer the current amount
                # or funds-scope question; the program still verifies facts.
                if state.get("scenario") == CrossScenario.MONTHLY_ARRANGEMENT.value:
                    return PensionFlow(self, state).apply_text(trusted, response["text"])
                return self._reask(trusted, state)
            raise ValueError("INVALID_OPTION")
        picked = state["choices"][choice]
        state["choices"] = {}
        state["interaction_id"] = None
        if state.get("scenario") is None:
            return self._choose_goal(trusted, state, picked)
        if state.get("scenario") == CrossScenario.MONTHLY_ARRANGEMENT.value:
            return PensionFlow(self, state).apply(trusted, picked)
        return self._apply_pick(trusted, state, picked)

    def _reask(self, trusted, state) -> ModuleResult:
        if "steps" in state:
            # A child still holding the plan's single response slot wins over a
            # fresh menu: re-offering choices here could bump the plan revision
            # and strand the in-flight confirmation (review note 1).
            self._reconcile(state, trusted)
            holding = plan.holding_step(state)
            if holding is not None:
                return self._holding_view(trusted, state, holding)
        if state.get("scenario") is None:
            return self._ask_goal(trusted, state)
        return self._ask_pick(trusted, state)

    # --------------------------------------------------------------- goal choice

    def _ask_goal(self, trusted, state) -> ModuleResult:
        note = _unsupported_note(state.get("unsupported"))
        choices = [(label, {"kind": "goal", "scenario": scenario.value})
                   for label, scenario in SUPPORTED]
        choices.append(("先不办理", {"kind": "cancel"}))
        prompt = (note + "请问这次要办哪件事？" if note
                  else "还没听清要办哪件事。当前可以办理的生活目标如下，请选择：")
        return self._ask(trusted, state, prompt, choices)

    def _choose_goal(self, trusted, state, picked: dict) -> ModuleResult:
        if picked["kind"] == "cancel":
            return self._done(trusted, state, TaskStatus.CANCELLED, "好的，先不办理。")
        rebuilt = self._new_state(trusted, state["request_id"], state["goal"],
                                  state["goal_digest"], CrossScenario(picked["scenario"]))
        rebuilt["actor"], rebuilt["session_id"] = state["actor"], state["session_id"]
        state.clear()
        state.update(rebuilt)
        return self._advance(trusted, state)

    # ------------------------------------------------------------------ advancing

    def _reconcile(self, state: dict, trusted) -> None:
        """Refresh children, then book finished cancellations (D2 facts)."""

        plan.reconcile(state, self.harness, trusted)
        self._record_outcomes(state)

    def _advance_pension(self, trusted, state) -> ModuleResult:
        return PensionFlow(self, state).advance(trusted)

    def _advance(self, trusted, state) -> ModuleResult:
        """Reconcile durable children, run what is ready, then ask or report."""

        if "steps" not in state:
            return self._ask_goal(trusted, state)  # no plan yet: clarify first
        if state.get("scenario") == CrossScenario.MONTHLY_ARRANGEMENT.value:
            return self._advance_pension(trusted, state)
        self._reconcile(state, trusted)
        self._collect_read_facts(state)
        holding = plan.holding_step(state)
        if holding is not None:
            return self._holding_view(trusted, state, holding)
        ready = plan.next_step(state)
        while ready is not None and ready["kind"] == "read":
            self._dispatch(trusted, state, ready)
            self._reconcile(state, trusted)
            self._collect_read_facts(state)
            holding = plan.holding_step(state)
            if holding is not None:
                return self._holding_view(trusted, state, holding)
            ready = plan.next_step(state)
        if ready is not None and ready["kind"] == "write":
            self._dispatch(trusted, state, ready)
            self._reconcile(state, trusted)
            holding = plan.holding_step(state)
            if holding is not None:
                return self._holding_view(trusted, state, holding)
        if state.get("inventory") is None:
            # The subscription inventory is the selection's source; without it
            # there is nothing true to offer or cancel.
            if self._step_failed(state, "subscriptions"):
                return self._done(trusted, state, TaskStatus.FAILED,
                                  "签约盘点暂时查不到（来源：订阅模块），这次先不办理退订；"
                                  "稍后可以重新发起。")
            return self._view(trusted, state, "正在查询您的账户、账单对比和当前签约，请稍候。")
        return self._ask_pick(trusted, state)

    def _holding_view(self, trusted, state, holding: dict) -> ModuleResult:
        record = plan.step_state(state, holding["step_id"])
        status = record["status"]
        child_id = record.get("child_task_id")
        if status is TaskStatus.NEEDS_ATTENTION:
            return self._view(trusted, state,
                              f"「{record.get('label') or holding['step_id']}」的办理结果未知，"
                              "已保留原操作编号，需要先核实原操作；核实前不会继续办理其他项目。",
                              active=holding, child_id=child_id)
        verb = "需要您在对应卡片上补充信息" if status is TaskStatus.WAITING_INPUT \
            else "需要您在确认单上确认或验证"
        return self._view(trusted, state,
                          f"「{record.get('label') or holding['step_id']}」{verb}"
                          "（在对应任务卡片上操作）。",
                          active=holding, child_id=child_id)

    @staticmethod
    def _step_failed(state: dict, step_id: str) -> bool:
        return plan.step_state(state, step_id).get("status") is TaskStatus.FAILED

    def _dispatch(self, trusted, state, step: dict) -> None:
        request_id = uuid4()
        record = plan.step_state(state, step["step_id"])
        action = step["action"]
        if action == "transfer.list_accounts":
            child_input = StartTransferInput(request_id=request_id, intent_text="查询本人账户")
        elif action == "transfer.list_payees":
            child_input = StartTransferInput(request_id=request_id, intent_text="查询保存的收款人")
        elif action == "transfer.start_transfer":
            child_input = StartTransferInput(
                request_id=request_id,
                intent_text=f"转给{step['payee_name']}（养老金安排第{step['step_id'].split(':')[1]}笔）",
                payee=SavedPayee(kind="saved", payee_id=step["payee_id"]),
                amount_fen=step["amount_fen"],
                payer_account_id=(state.get("pension") or {}).get("payer"))
            record["label"] = f"转给{step['payee_name']}"
            record["amount_fen"] = step["amount_fen"]
        elif action == "subscription.list_subscriptions":
            child_input = SubscriptionListInput(request_id=request_id,
                                                intent_text="盘点当前签约代扣")
        elif action == "bills.summarize":
            account_ids = plan.step_state(state, "accounts")["result"]["accounts"]
            ids = [item["account_id"] for item in account_ids]
            now = self.clock()
            scope_start, scope_end = month_range(now, 1)
            if step.get("mode") == "details":
                scope_start, scope_end = month_range(now, 0)
                child_input = BillSummarizeInput(
                    scope=BillScope(account_ids=ids, start_at=scope_start, end_at=scope_end),
                    mode="details")
            else:
                compare_start, compare_end = month_range(now, 2)
                child_input = BillSummarizeInput(
                    scope=BillScope(account_ids=ids, start_at=scope_start, end_at=scope_end),
                    comparison_scope=BillScope(account_ids=ids, start_at=compare_start,
                                               end_at=compare_end),
                    mode="summary")
        elif action == "subscription.cancel_subscription":
            item = self._inventory_item(state, step["subscription_id"])
            child_input = SubscriptionCancelInput(
                request_id=request_id, intent_text=f"退订{item['service_name']}",
                subscription_id=step["subscription_id"])
            record["label"] = item["service_name"]
            record["amount_fen"] = item["amount_fen"]
        else:
            raise ValueError("STEP_ACTION_UNKNOWN")
        result = self.harness.dispatch_child(
            trusted, action, request_id, child_input, step_id=step["step_id"],
            plan_revision=state["plan_revision"])
        record["child_task_id"] = result.task_id
        record["status"] = result.status

    # ------------------------------------------------------------------- facts

    def _collect_read_facts(self, state: dict) -> None:
        bills_record = plan.step_state(state, "bills_compare")
        if state.get("bills") is None and bills_record.get("status") in (
                TaskStatus.SUCCEEDED, TaskStatus.FAILED):
            self._collect_bills(state)
        subscriptions = plan.step_state(state, "subscriptions")
        if state.get("inventory") is None and subscriptions.get("status") in (
                TaskStatus.SUCCEEDED, TaskStatus.FAILED):
            self._collect_inventory(state)

    def _collect_bills(self, state: dict) -> None:
        record = plan.step_state(state, "bills_compare")
        if record.get("status") is TaskStatus.SUCCEEDED and isinstance(record.get("result"), dict):
            data = record["result"]
            comparison = data.get("comparison") or {}
            top = [
                (_CATEGORY_LABELS.get(item.get("category"), item.get("category")),
                 item.get("net_fen"))
                for item in (data.get("categories") or [])[:3]
            ]
            state["bills"] = {"ok": True,
                              "net_fen": data.get("consumption_net_fen"),
                              "delta_fen": comparison.get("delta_fen"),
                              "top": top}
        else:
            state["bills"] = {"ok": False, "reason": record.get("message") or "账单模块未返回对比结果"}

    def _collect_inventory(self, state: dict) -> None:
        record = plan.step_state(state, "subscriptions")
        if record.get("status") is TaskStatus.SUCCEEDED and isinstance(record.get("result"), dict):
            list_result = (record["result"] or {}).get("list_result") or {}
            state["inventory"] = list_result.get("items") or []
        else:
            state["inventory"] = []

    @staticmethod
    def _inventory_item(state: dict, subscription_id: str) -> dict:
        for item in state["inventory"]:
            if item.get("subscription_id") == subscription_id:
                return item
        raise ValueError("SUBSCRIPTION_NOT_IN_INVENTORY")

    @staticmethod
    def _cancellable(state: dict) -> list[dict]:
        """Only an active bank mandate can be cancelled online (XL-S03)."""

        return [item for item in state["inventory"]
                if item.get("can_cancel_in_bank") and item.get("status") == "active"]

    @staticmethod
    def _suspected(state: dict) -> list[dict]:
        return [item for item in state["inventory"]
                if item.get("source_type") == "suspected_ledger"]

    def _already_cancelled(self, state: dict) -> list[str]:
        done = {receipt["subscription_id"] for receipt in state["receipts"]}
        done |= {entry["subscription_id"] for entry in state["unknown"]}
        failed = {step["subscription_id"] for step in state["steps"]
                  if step["step_id"].startswith("cancel:")
                  and plan.step_state(state, step["step_id"]).get("status")
                  in (TaskStatus.FAILED, TaskStatus.CANCELLED)}
        return sorted(done | failed)

    # ------------------------------------------------------------------ picking

    def _ask_pick(self, trusted, state, *, pension_mode: bool = False) -> ModuleResult:
        done = set(self._already_cancelled(state))
        remaining = [item for item in self._cancellable(state)
                     if item["subscription_id"] not in done]
        suspected = self._suspected(state)
        lines = [self._evidence_line(state)]
        if remaining:
            names = "、".join(f"{item['merchant_name']}·{item['service_name']}"
                             f"（{money(item['amount_fen'])}元/"
                             f"{'每月' if item['cycle'] == 'monthly' else '每年'}）"
                             for item in remaining)
            lines.append(f"当前可在线退订的签约：{names}。")
        choices = []
        for item in remaining:
            # Merchant plus service keeps same-name merchants distinguishable.
            label = (f"退订 {item['merchant_name']}·{item['service_name']}"
                     f"（{money(item['amount_fen'])}元/"
                     f"{'每月' if item['cycle'] == 'monthly' else '每年'}，"
                     f"{item['account_masked']}）")
            choices.append((label, {"kind": "cancel_item",
                                    "subscription_id": item["subscription_id"]}))
        if state["receipts"] or state["unknown"]:
            choices.append(("保留其余项目，出总回执" if not pension_mode else
                            "退订到这里，继续安排资金", {"kind": "finish"}))
        else:
            choices.append(("都不退，直接安排资金" if pension_mode else "都不退，保留全部",
                            {"kind": "finish"}))
        if remaining:
            if not state["receipts"] and not pension_mode:
                lines.append("想退订的项目请逐项选择；每项退订前还会有一次确认。")
            prompt = "\n".join(lines)
            asked = self._ask(trusted, state, prompt, choices)
            return asked.model_copy(update={"data": plan.build_view(state, prompt)})
        if state["receipts"] or state["unknown"]:
            if pension_mode:
                return self._advance_pension(trusted, state)
            return self._receipt(trusted, state)
        extra = []
        if suspected:
            names = "、".join(f"{item['merchant_name']}（疑似，银行无签约记录）"
                             for item in suspected)
            extra.append(f"另有疑似周期扣费线索：{names}。这些没有银行签约记录，"
                         "不能在线退订，如需处理请到对应商户渠道。")
        return self._done(trusted, state, TaskStatus.SUCCEEDED,
                          "\n".join(lines + extra + ["当前没有可在线退订的签约。"]))

    def _evidence_line(self, state: dict) -> str:
        accounts_record = plan.step_state(state, "accounts")
        if accounts_record.get("status") is TaskStatus.FAILED:
            # bills depends on accounts: with accounts failed it never runs, and
            # saying "still querying" would be untrue (review note 3).
            return ("本人账户暂时查不到，账单对比本次不可用；"
                    "以下结论只基于签约盘点。")
        bills = state.get("bills")
        if bills is None:
            return "账单对比还在查询中。"
        if not bills.get("ok"):
            return f"账单对比暂时不可用（{bills.get('reason')}），本次结论只基于签约盘点。"
        delta = bills.get("delta_fen")
        top = "、".join(f"{name} {money(net)}元" for name, net in bills.get("top", []) if net)
        delta_text = ("与上月基本持平" if delta == 0 else
                      f"比上月多花 {money(delta)}元" if delta > 0 else
                      f"比上月少花 {money(-delta)}元")
        return (f"最近一个完整月消费净额 {money(bills['net_fen'])}元，{delta_text}。"
                f"支出最多的类别：{top or '无'}。以下签约是银行记录的自动扣费。")

    def _apply_pick(self, trusted, state, picked: dict) -> ModuleResult:
        if picked["kind"] == "finish":
            if state.get("scenario") == CrossScenario.MONTHLY_ARRANGEMENT.value:
                if isinstance(state.get("pension"), dict):
                    state["pension"]["phase"] = "basis"
                return self._advance_pension(trusted, state)
            return self._receipt(trusted, state)
        if picked["kind"] != "cancel_item":
            raise ValueError("INVALID_OPTION")
        cancellable = {item["subscription_id"] for item in self._cancellable(state)}
        if picked["subscription_id"] not in cancellable:
            raise ValueError("SUBSCRIPTION_NOT_CANCELLABLE")
        item = self._inventory_item(state, picked["subscription_id"])
        plan.add_step(state, {
            "step_id": f"cancel:{item['subscription_id']}",
            "action": "subscription.cancel_subscription", "kind": "write",
            "subscription_id": item["subscription_id"], "depends_on": []})
        return self._advance(trusted, state)

    # ----------------------------------------------------------------- closeout

    def _pension_summary_lines(self, state: dict) -> tuple[list[str], int, bool]:
        """Shared receipt facts: per-transfer truth, cancels, retained amount."""

        pension = state.get("pension") or {}
        lines, transferred, unknown = [], 0, False
        for step in state["steps"]:
            if not step["step_id"].startswith("transfer:"):
                continue
            record = plan.step_state(state, step["step_id"])
            amount, name = step.get("amount_fen", 0), step.get("payee_name", "")
            status = record.get("status")
            if status is TaskStatus.SUCCEEDED:
                transferred += amount
                lines.append(f"已转给 {name} {money(amount)} 元。")
            elif status is TaskStatus.NEEDS_ATTENTION:
                unknown = True
                lines.append(f"转给 {name} {money(amount)} 元的结果待核实"
                             f"（原任务 {(record.get('child_task_id') or '')[:8]}…），"
                             "核实前不继续其他转账。")
            elif status is TaskStatus.FAILED:
                lines.append(f"转给 {name} {money(amount)} 元没有办成"
                             f"（{record.get('message') or '转账模块返回失败'}），"
                             "后续转账已暂停。")
        for receipt in state["receipts"]:
            cycle = "每月" if receipt["cycle"] == "monthly" else "每年"
            lines.append(f"已退订 {receipt['service_name']}：{money(receipt['amount_fen'])}元/{cycle}，"
                         f"自 {receipt['effective_stop_at']} 起不再自动扣费。")
        if pension.get("base_fen") is not None:
            protected = (pension.get("reserve_fen") or 0) + (
                pension.get("known_debits_fen") or 0
                if pension.get("includes_debits") is False else 0)
            retained = pension["base_fen"] - protected - transferred
            note = ""
            if pension.get("includes_debits") is False and pension.get("known_debits_fen"):
                note = f"（留存之外已保护未来代扣 {money(pension['known_debits_fen'])} 元）"
            lines.append(f"资金范围 {money(pension['base_fen'])} 元；留存 "
                         f"{money(pension.get('reserve_fen') or 0)} 元{note}；"
                         f"已转出 {money(transferred)} 元；未转出留在账户 "
                         f"{money(retained)} 元。")
        return lines, transferred, unknown

    def _receipt_pension(self, trusted, state, *, stopped: bool = False) -> ModuleResult:
        lines, transferred, unknown = self._pension_summary_lines(state)
        pension = state.get("pension") or {}
        if unknown:
            # D2: an unsettled write keeps the whole arrangement open.
            return self._view(trusted, state,
                              "已停止新增办理，资金仍待核实：\n" + "\n".join(lines) +
                              "\n未知笔核实前，本账户的资金安排不解除。")
        succeeded_any = bool(transferred) or bool(state["receipts"])
        if stopped:
            status = TaskStatus.PARTIALLY_SUCCEEDED if succeeded_any else TaskStatus.CANCELLED
            head = "部分完成，后续已停止：" if succeeded_any else "已停止办理。"
            if succeeded_any:
                lines.append("您叫停后，未办理的转账都没有提交。")
            return self._done(trusted, state, status, head + "\n".join(lines))
        lines.append("本次安排的转账已全部办完，资金安排已解除。")
        return self._done(trusted, state, TaskStatus.SUCCEEDED, "\n".join(lines))

    def _close_arrangement_if_any(self, state: dict) -> None:
        pension = state.get("pension") or {}
        if pension.get("arrangement_id"):
            try:
                self.harness.application.close_arrangement(
                    state["actor"][0], state["actor"][1], pension["arrangement_id"])
            except ValueError:
                pass  # already closed or superseded; the bank facts remain the truth
            pension["arrangement_id"] = None

    def _closeout(self, trusted, state, *, stop_reason: str) -> ModuleResult:
        """Stop everything not executed; keep real outcomes (D2)."""

        state["stop_reason"] = stop_reason
        for step in state["steps"]:
            record = plan.step_state(state, step["step_id"])
            status = record.get("status")
            if status in (TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL,
                          TaskStatus.RUNNING, None) and record.get("child_task_id"):
                if step["kind"] == "write":
                    # The child's own cancel path stops it before any bank write
                    # it has not confirmed; an unknown child is left to verify.
                    try:
                        self.harness.resume_child(
                            trusted, record["child_task_id"], {"cancel": True},
                            plan_revision=state["plan_revision"])
                    except ValueError:
                        pass
                self._reconcile(state, trusted)
        self._reconcile(state, trusted)
        self._collect_read_facts(state)
        if state.get("scenario") == CrossScenario.MONTHLY_ARRANGEMENT.value:
            lines, _transferred, unknown = self._pension_summary_lines(state)
            if unknown:
                return self._view(trusted, state,
                                  "已停止新增办理，资金仍待核实：\n" + "\n".join(lines) +
                                  "\n未知笔核实前，本账户的资金安排不解除。")
            self._close_arrangement_if_any(state)
            return self._receipt_pension(trusted, state, stopped=True)
        if state["receipts"]:
            return self._receipt(trusted, state, stopped=True)
        return self._done(trusted, state, TaskStatus.CANCELLED,
                          "已停止办理。这次没有完成任何退订；已经扣过的费用不因此退回。")

    # ------------------------------------------------------------------ receipt

    def _receipt(self, trusted, state, *, stopped: bool = False) -> ModuleResult:
        """Only bank-verified stops count; unknown stays pending (XL-S05)."""

        lines = []
        monthly_total = 0
        for receipt in state["receipts"]:
            cycle = "每月" if receipt["cycle"] == "monthly" else "每年"
            lines.append(
                f"已退订 {receipt['service_name']}：{money(receipt['amount_fen'])}元/{cycle}，"
                f"自 {receipt['effective_stop_at']} 起不再自动扣费。")
            if receipt["cycle"] == "monthly":
                monthly_total += receipt["amount_fen"]
        for entry in state["unknown"]:
            lines.append(f"{entry['merchant_name']}·{entry['service_name']} 的退订结果还待核实"
                         f"（原任务 {entry['child_task_id'][:8]}…），"
                         "核实前不计入已确定的少扣金额。")
        suspected = self._suspected(state)
        if suspected:
            names = "、".join(f"{item['merchant_name']}（疑似，银行无签约记录）" for item in suspected)
            lines.append(f"另有疑似周期扣费线索：{names}。这些没有银行签约，不能在线退订，"
                         "如需处理请到对应商户渠道。")
        if monthly_total:
            lines.append(f"从下期起每月合计少扣 {money(monthly_total)}元。已扣过的费用不退。")
        if stopped:
            head = "部分完成，后续已停止：" if state["receipts"] else ""
            status = TaskStatus.PARTIALLY_SUCCEEDED if state["receipts"] else TaskStatus.CANCELLED
            lines.append("您叫停后，未办理的项目都没有提交。")
            return self._done(trusted, state, status, head + "\n".join(lines))
        return self._done(trusted, state, TaskStatus.SUCCEEDED, "\n".join(lines))

    # ------------------------------------------------------------------ unknown

    def _record_outcomes(self, state: dict) -> None:
        """Move finished cancel children into receipts / unknown bookkeeping."""

        self._reclassify_unknown(state)
        for step in state["steps"]:
            if not step["step_id"].startswith("cancel:"):
                continue
            record = plan.step_state(state, step["step_id"])
            subscription_id = step["subscription_id"]
            known = ({receipt["subscription_id"] for receipt in state["receipts"]}
                     | {entry["subscription_id"] for entry in state["unknown"]})
            if subscription_id in known:
                continue
            if record.get("status") is TaskStatus.SUCCEEDED and isinstance(record.get("result"), dict):
                operation = (record["result"].get("operation") or {})
                receipt = operation.get("receipt") or {}
                item = record["result"].get("selected_item") or {}
                if receipt and item:
                    stop = receipt.get("effective_stop_at")
                    state["receipts"].append({
                        "subscription_id": subscription_id,
                        "service_name": item.get("service_name") or receipt.get("service_name"),
                        "merchant_name": item.get("merchant_name") or receipt.get("merchant_name"),
                        "amount_fen": receipt.get("amount_fen"),
                        "cycle": receipt.get("cycle"),
                        "effective_stop_at": (stop[:10] if isinstance(stop, str) else stop),
                        "child_task_id": record.get("child_task_id"),
                    })
            elif record.get("status") is TaskStatus.NEEDS_ATTENTION:
                item = self._inventory_item(state, subscription_id)
                state["unknown"].append({
                    "subscription_id": subscription_id,
                    "merchant_name": item["merchant_name"],
                    "service_name": item["service_name"],
                    "child_task_id": record.get("child_task_id"),
                })

    @staticmethod
    def _reclassify_unknown(state: dict) -> None:
        """An unknown cancel that later resolved keeps its verified truth (review note 2).

        A re-verified success becomes a receipt; a settled failure or cancellation
        stops being reported as pending. Conservatism is for unsettled facts only.
        """

        still_unknown = []
        for entry in state["unknown"]:
            step = next((s for s in state["steps"]
                         if s.get("subscription_id") == entry["subscription_id"]), None)
            record = plan.step_state(state, step["step_id"]) if step else {}
            status = record.get("status")
            if status is TaskStatus.SUCCEEDED and isinstance(record.get("result"), dict):
                operation = (record["result"].get("operation") or {})
                receipt = operation.get("receipt") or {}
                item = record["result"].get("selected_item") or {}
                if receipt and item and entry["subscription_id"] not in {
                        r["subscription_id"] for r in state["receipts"]}:
                    stop = receipt.get("effective_stop_at")
                    state["receipts"].append({
                        "subscription_id": entry["subscription_id"],
                        "service_name": item.get("service_name") or receipt.get("service_name"),
                        "merchant_name": item.get("merchant_name") or receipt.get("merchant_name"),
                        "amount_fen": receipt.get("amount_fen"),
                        "cycle": receipt.get("cycle"),
                        "effective_stop_at": (stop[:10] if isinstance(stop, str) else stop),
                        "child_task_id": record.get("child_task_id"),
                    })
                continue
            if status in (TaskStatus.NEEDS_ATTENTION, None):
                still_unknown.append(entry)
            # FAILED / CANCELLED: dropped from unknown — already refused, never pending.
        state["unknown"] = still_unknown

    # --------------------------------------------------------------- entry seams

    def checkpoint_context(self, trusted: TrustedContext, *, thread_id=None):
        saved, state = self._load(trusted, thread_id)
        if state is None:
            return None
        return trusted.model_copy(update={"session_id": state["session_id"]})

    def recover_session(self, trusted: TrustedContext, *, source_session_id: str,
                        thread_id=None) -> ModuleResult:
        saved, state = self._load(trusted, thread_id)
        if state is None or state["session_id"] not in {source_session_id, trusted.session_id}:
            raise PermissionError("ACCESS_DENIED")
        state["session_id"] = trusted.session_id
        if state.get("result", {}).get("status") not in _TERMINAL:
            result = self._advance(trusted, state)
        else:
            result = self._result(trusted, state)
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result


def register_cross(harness, clock):
    """Platform assembly (v05-cross-platform/05) calls this to mount the module."""

    from .manifest import CROSS_MANIFEST

    def factory(trusted, saver, trace):
        return CrossEntry(harness, saver, trace, clock)

    harness.registry.register_module(CROSS_MANIFEST, factory)
