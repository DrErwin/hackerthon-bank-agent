"""Birthday's adopted-budget constraint, over public bills and durable records.

The lock is deliberately process-local: the supported demo has one worker.
Neither input provenance nor a budget adoption authorizes a bank action.
"""

from collections import defaultdict
from functools import wraps
from hashlib import sha256
import json
from threading import Lock, RLock
from uuid import UUID, uuid4

from app.contracts.bills import BillDetails, BillScope, BillSummarizeInput, SpendingSummary
from app.contracts.common import TaskStatus
from app.contracts.cross import AdoptedBudget, BudgetCommitment, BudgetRef, BudgetView
from app.contracts.tasks import ModuleResult
from app.agent_platform.budget_inputs import BudgetInputRecovery
from app.storage.application import BudgetOccupationExceededError
from .plan import money, month_range


_LOCKS = defaultdict(RLock)
_LOCK_GUARD = Lock()


def serialized(method):
    @wraps(method)
    def call(self, trusted, *args, **kwargs):
        key = (str(self.harness.application.path), trusted.user_id, trusted.demo_round_id)
        with _LOCK_GUARD:
            lock = _LOCKS[key]
        with lock:
            return method(self, trusted, *args, **kwargs)
    return call


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def origin_binding(origin):
    # Phase/completion describe platform bookkeeping, not the immutable input.
    # A cancelled task may still need read-only recovery of an earlier adoption.
    return {k: v for k, v in origin.facts.items() if k not in {"phase", "completion"}}


class BudgetPending(ValueError):
    """A missing or changed business fact: wait, never replace it with zero."""


class PersonalBudget:
    def __init__(self, entry, state):
        self.entry, self.state = entry, state
        self.store = entry.harness.application
        self.b = state["birthday"]
        self.p = state.setdefault("personal_budget", {})
        self.user, self.round, self.task = state["actor"]

    def _read(self, trusted, scope, mode):
        result = self.entry.harness.dispatch_child(
            trusted, "bills.summarize", uuid4(), BillSummarizeInput(scope=scope, mode=mode),
            step_id=f"budget-facts-{uuid4()}", plan_revision=self.state["plan_revision"])
        if result.status != TaskStatus.SUCCEEDED:
            raise BudgetPending("账单事实暂时查不到，请稍后重新核对。")
        model = SpendingSummary if mode == "summary" else BillDetails
        data = model.model_validate(result.data)
        if (set(data.scope.account_ids) != set(scope.account_ids)
                or data.scope.start_at != scope.start_at or data.scope.end_at != scope.end_at
                or (mode == "details" and data.category is not None)):
            raise BudgetPending("账单范围不一致，尚不能办理。")
        return data

    def _window(self, trusted, scope):
        a = self._read(trusted, scope, "summary")
        details = self._read(trusted, scope, "details")
        b = self._read(trusted, scope, "summary")
        fields = ("transaction_count", "consumption_gross_fen", "consumption_refund_fen",
                  "consumption_net_fen", "transfer_out_fen", "transfer_in_fen", "categories")
        if (any(getattr(a, k) != getattr(b, k) for k in fields)
                or len(details.transactions) != b.transaction_count
                or len({t.transaction_id for t in details.transactions}) != len(details.transactions)):
            raise BudgetPending("账单读取期间发生变化，请重新核对。")
        sources = [{s.account_id: s.as_of for s in row.source_as_of} for row in (a, details, b)]
        if any(not sources[0][account] <= sources[1][account] <= sources[2][account]
               for account in scope.account_ids):
            raise BudgetPending("账单来源时间不一致，请重新核对。")
        if any(t.account_id not in scope.account_ids or not scope.start_at <= t.occurred_at < scope.end_at
               for t in details.transactions):
            raise BudgetPending("账单交易归属不一致。")
        self.p["last_window"] = {"scope": scope.model_dump(mode="json"),
            "source_as_of": [r.model_dump(mode="json") for r in b.source_as_of],
            "as_of": b.as_of.isoformat()}
        return b, {t.transaction_id: t for t in details.transactions}

    @staticmethod
    def _purpose(purpose):
        return purpose.strip() in {"生日", "生日安排", "家人生日安排", "全部消费", "本月总消费", "日常消费", "个人消费"}

    def _applicable(self, record):
        now = self.entry.clock()
        return (self.b["payer"] in record.scope.account_ids
                and record.scope.start_at <= now < record.scope.end_at)

    def _view(self, record, summary):
        ref = BudgetRef(budget_id=record.budget_id, version=record.version)
        view = BudgetView(budget_ref=ref, purpose=record.purpose, scope=record.scope,
            personal_limit_fen=record.personal_limit_fen, used_fen=summary.consumption_net_fen,
            remaining_fen=record.personal_limit_fen-summary.consumption_net_fen,
            facts_as_of=summary.as_of, adopted=True)
        self.p["view"] = view.model_dump(mode="json")
        return view

    def discover(self):
        records = [r for r in self.store.list_adopted_budgets(self.user, self.round)
                   if self._applicable(r)]
        explicit = (self.state.get("constraints") or {}).get("budget_ref")
        bound = self.p.get("bound") or explicit
        if bound:
            record = self.store.get_adopted_budget(self.user, self.round, BudgetRef.model_validate(bound))
            if record is None or record.status != "active" or not self._applicable(record):
                raise BudgetPending("原预算版本、付款账户或期间已变化；请先核对原预算，不能自动换到最新版。")
            if not self._purpose(record.purpose):
                raise BudgetPending("预算用途尚不明确；请先在原预算澄清它是否适用于本次生日。")
            if len(records) != 1 or records[0].budget_id != record.budget_id:
                raise BudgetPending("存在重叠预算，请先核对各自范围和用途，不能挑较宽松限额。")
            return record
        if len(records) > 1:
            shown = "；".join(f"{r.purpose} / {r.scope.account_ids} / {r.scope.start_at}至{r.scope.end_at} / {money(r.personal_limit_fen)}元" for r in records)
            raise BudgetPending("存在多份可能适用的预算，请澄清范围和用途：" + shown)
        if records and not self._purpose(records[0].purpose):
            raise BudgetPending("已有预算用途尚不明确，请先核对原预算；省略引用也不能跳过。")
        return records[0] if records else None

    def prepare(self, trusted):
        """Before the birthday basket: honor a supplied personal constraint."""
        constraints = self.state.get("constraints") or {}
        if constraints.get("personal_limit_fen") is not None and not self.p.get("candidate_done"):
            scope = constraints.get("scope")
            purpose = constraints.get("purpose")
            if not scope or not purpose or not self._purpose(purpose):
                return self.entry._ask(trusted, self.state,
                    "个人预算的范围或用途需明确。是否按当前付款账户、本月全部消费核对，并用于本次生日？不是仅统计生日商品。",
                    [("按上述范围形成候选", {"kind": "personal_scope"}), ("停止", {"kind": "b_stop"})])
            self.p["candidate"] = {"scope": scope, "purpose": purpose,
                                   "personal_limit_fen": constraints["personal_limit_fen"]}
            return self.candidate(trusted)
        record = self.discover()
        if record:
            summary, _ = self._window(trusted, record.scope)
            self.p["bound"] = {"budget_id": record.budget_id, "version": record.version}
            self.b.update(budget_id=record.budget_id, budget_version=record.version)
            self._view(record, summary)
        return None

    def candidate(self, trusted):
        candidate = self.p["candidate"]
        prior = self.candidate_previous()
        self.p["candidate_previous"] = prior.model_dump(mode="json") if prior else None
        scope = BillScope.model_validate(candidate["scope"])
        owned = self.state["step_state"]["accounts"]["result"]["accounts"]
        if not set(scope.account_ids) <= {a["account_id"] for a in owned}:
            raise BudgetPending("预算账户必须来自本人的已查询账户。")
        summary, _ = self._window(trusted, scope)
        view = BudgetView(budget_ref=None, purpose=candidate["purpose"], scope=scope,
            personal_limit_fen=candidate["personal_limit_fen"], used_fen=summary.consumption_net_fen,
            remaining_fen=candidate["personal_limit_fen"]-summary.consumption_net_fen,
            facts_as_of=summary.as_of, adopted=False)
        self.p["view"] = view.model_dump(mode="json")
        self.p["mode"] = "candidate"
        previous = f"将修改预算{prior.budget_id}的v{prior.version}，旧版未结占用保留。" if prior else "这是新个人预算候选。"
        result = self.entry._ask(trusted, self.state,
            previous + f"个人预算候选：{scope.account_ids}，{scope.start_at}至{scope.end_at}；用途{view.purpose}。"
            f"统计范围内全部消费；限额{money(view.personal_limit_fen)}元，已用{money(view.used_fen)}元，剩余{money(view.remaining_fen)}元。"
            "采用仅保存约束，不代表动钱授权。",
            [("采用个人预算", {"kind": "personal_adopt"}),
             ("修改个人限额", {"kind": "personal_modify"}), ("不采用，停止新约束", {"kind": "personal_decline"})])
        self.p["candidate_binding"] = {"plan_revision": self.state["plan_revision"], **candidate}
        return result

    def candidate_previous(self):
        hint = self.p.get("change_from") or self.p.get("bound") or (self.state.get("constraints") or {}).get("budget_ref")
        if hint:
            prior = self.store.get_adopted_budget(self.user, self.round, BudgetRef.model_validate(hint))
            if prior is None or prior.status != "active":
                raise BudgetPending("候选的原预算版本已变化，请重新核对。")
            return prior
        matches = [r for r in self.store.list_adopted_budgets(self.user, self.round) if self._applicable(r)]
        if len(matches) > 1:
            raise BudgetPending("存在重叠预算，不能以新编号绕过，请先澄清。")
        return matches[0] if matches else None

    def choice(self, trusted, option):
        picked = self.state.get("choices", {}).get(option, {})
        kind = picked.get("kind", "")
        if not kind.startswith("personal_"):
            return None
        if kind == "personal_scope":
            start, end = month_range(self.entry.clock(), 0)
            self.state["constraints"].update(scope=BillScope(account_ids=[self.b["payer"]],
                start_at=start, end_at=end).model_dump(mode="json"), purpose="生日安排")
            return self.prepare(trusted)
        if kind == "personal_begin":
            start, end = month_range(self.entry.clock(), 0)
            self.p["candidate"] = {"scope": BillScope(account_ids=[self.b["payer"]],
                start_at=start, end_at=end).model_dump(mode="json"), "purpose": "生日安排",
                "personal_limit_fen": 0}
            self.p["mode"] = "limit"
            return self.entry._ask(trusted, self.state,
                "本月当前付款账户全部消费的个人预算限额是多少元？输入后展示完整候选，仍须专用选项采用。",
                [("停止", {"kind": "b_stop"})])
        if kind == "personal_birthday_limit" and self.can_edit_cap():
            self.b.update(phase="budget", budget_limit_fen=None)
            return self.entry._birthday_flow(self.state)._ask_budget(trusted)
        if kind == "personal_review":
            if self.b.get("pending") and not self.b.get("freeze"):
                raise BudgetPending("原确认或验证尚未结束，先按原操作核实或停止，不替换预算候选。")
            records = [r for r in self.store.list_adopted_budgets(self.user, self.round) if self._applicable(r)]
            if len(records) != 1:
                raise BudgetPending("当前预算范围或用途仍未澄清，不能选择较宽松的一份。")
            record = records[0]
            self.p["change_from"] = {"budget_id": record.budget_id, "version": record.version}
            if not self._purpose(record.purpose):
                self.p["view"] = None
                return self.entry._ask(trusted, self.state,
                    f"原预算v{record.version}用途“{record.purpose}”尚未明确。是否提出改版候选："
                    f"仍按{record.scope.account_ids}、{record.scope.start_at}至{record.scope.end_at}统计全部消费，"
                    "用于本次生日？不是仅统计某类商品；下步仍需真实采用。",
                    [("按上述全部消费范围形成候选", {"kind": "personal_clarify"}), ("停止", {"kind": "b_stop"})])
            self.p["candidate"] = {"scope": record.scope.model_dump(mode="json"),
                "purpose": record.purpose, "personal_limit_fen": record.personal_limit_fen}
            self.state["plan_revision"] += 1
            return self.candidate(trusted)
        if kind == "personal_clarify":
            record = self.candidate_previous()
            self.p["candidate"] = {"scope": record.scope.model_dump(mode="json"),
                "purpose": "生日安排", "personal_limit_fen": record.personal_limit_fen}
            self.state["plan_revision"] += 1
            return self.candidate(trusted)
        if kind == "personal_retry":
            if self.p.get("mode") in {"candidate", "limit"}:
                return self.candidate(trusted)
            flow = self.entry._birthday_flow(self.state)
            pending = self.b.get("pending")
            if pending:
                self.refresh(trusted)
                return flow._pending_view(trusted)
            return flow.advance(trusted)
        if kind == "personal_continue":
            self.p["prepared"] = False
            return self.entry._birthday_flow(self.state).advance(trusted)
        if kind in {"personal_adopt", "personal_modify", "personal_decline"}:
            origin = self.entry.harness.budget_input_origin(trusted)
            task = self.store.get_task(self.user, self.round, self.task)
            facts = origin.facts if origin else {}
            if (origin is None or facts.get("interaction_id") != self.state.get("interaction_id")
                    or facts.get("selected_option_id") != option
                    or facts.get("candidate_snapshot") != self.p.get("candidate_binding")
                    or facts.get("binding_digest") != digest(task.snapshot.get("result"))
                    or facts.get("binding_digest") != digest(self.state.get("result"))):
                return ModuleResult.model_validate(self.state["result"]).model_copy(
                    update={"message": "请通过原任务的个人预算专用选项提交；模型回答不能采用预算。"})
            if kind == "personal_modify":
                self.p["mode"] = "limit"
                return self.entry._ask(trusted, self.state, "新的个人预算限额是多少元？范围和用途保持上面所示，输入后仍需重新采用。",
                                       [("停止", {"kind": "b_stop"})])
            if kind == "personal_decline":
                # Declining never removes an existing constraint. The requested
                # new constraint is unresolved: stop instead of silently buying.
                return self.entry._birthday_flow(self.state).stop(trusted, "user_cancelled")
            return self.adopt(trusted, origin)
        return None

    def adopt(self, trusted, origin):
        candidate = self.p["candidate"]
        attempts = self.p.setdefault("attempts", {})
        attempt = attempts.get(origin.origin_id)
        if attempt is None:
            expected = self.p.get("candidate_previous")
            existing = self.candidate_previous()
            if (existing.model_dump(mode="json") if existing else None) != expected:
                raise BudgetPending("候选展示后已有预算发生变化，须展示新版本后重新采用。")
            # Exact supplied ref or unique applicable adoption determines a
            # continuous version. Never create a new id to evade its old holds.
            record = AdoptedBudget(budget_id=existing.budget_id if existing else str(uuid4()),
                version=existing.version+1 if existing else 1, user_id=self.user, demo_round_id=self.round,
                source_task_id=self.task, scope=BillScope.model_validate(candidate["scope"]),
                purpose=candidate["purpose"], personal_limit_fen=candidate["personal_limit_fen"],
                adopted_at=origin.accepted_at, adoption_interaction_id=origin.facts["interaction_id"], status="active")
            attempt = {"origin_id": origin.origin_id, "facts": origin_binding(origin),
                "record": record.model_dump(mode="json"), "previous_version": existing.version if existing else None,
                "expected_revision": origin.dispatch_task_revision, "attempt_ref": str(uuid4()),
                "fact_result": ModuleResult(task_id=self.task, run_id=origin.facts["run_id"],
                    status=TaskStatus.NEEDS_ATTENTION, data=None,
                    message=f"原个人预算v{record.version}已采用，请返回当前任务核对或继续；未办理资金动作。",
                    interaction=None, error=None, allowed_actions=["query"],
                    recovery_required=False, recovery_reason=None).model_dump(mode="json")}
            attempts[origin.origin_id] = attempt
            self.entry._save(trusted, None, self.state)
        record = self.store.adopt_budget(self.user, self.round, AdoptedBudget.model_validate(attempt["record"]),
            expected_task_revision=attempt["expected_revision"], previous_version=attempt["previous_version"])
        if record.status != "active":
            raise BudgetPending("原采用已成为历史版本，不重新激活。请核对当前预算。")
        self.p.update(bound={"budget_id": record.budget_id, "version": record.version}, candidate_done=True, mode=None)
        self.b.update(budget_id=record.budget_id, budget_version=record.version)
        summary, _ = self._window(trusted, record.scope)
        self._view(record, summary)
        # Persist the original adoption result before returning to the platform's
        # result CAS; reconciliation only reads this frozen fact, never resumes.
        result = self.entry._ask(trusted, self.state, "个人预算已采用，尚未办理资金动作。继续核对本次生日上限。",
                                 [("继续生日安排", {"kind": "personal_continue"}), ("停止", {"kind": "b_stop"})])
        attempt["result"] = result.model_dump(mode="json")
        self.state["result"] = attempt["result"]
        self.entry._save(trusted, None, self.state)
        return result

    def recover(self, origin):
        attempt = self.p.get("attempts", {}).get(origin.origin_id)
        if not attempt or attempt["facts"] != origin_binding(origin):
            return None
        original = AdoptedBudget.model_validate(attempt["record"])
        record = self.store.get_adopted_budget(self.user, self.round,
            BudgetRef(budget_id=original.budget_id, version=original.version))
        if record is None or record.model_copy(update={"status": "active"}) != original:
            return None
        if "result" not in attempt:
            # Adoption committed but the result checkpoint did not: return only
            # the original fact, without adopting or advancing a newer plan.
            result = ModuleResult.model_validate(attempt["fact_result"])
        else:
            result = ModuleResult.model_validate(attempt["result"])
        return BudgetInputRecovery(attempt["attempt_ref"], result)

    def restore_adoption(self, trusted):
        """Ordinary current-task recovery; the historical hook remains read-only."""
        if self.p.get("candidate_done"):
            return None
        for attempt in self.p.get("attempts", {}).values():
            if attempt["facts"]["candidate_snapshot"] != self.p.get("candidate_binding"):
                continue
            original = AdoptedBudget.model_validate(attempt["record"])
            record = self.store.get_adopted_budget(self.user, self.round,
                BudgetRef(budget_id=original.budget_id, version=original.version))
            if record is None:
                # The old accepted input cannot authorize a new write. Display a
                # new candidate; its new F10 source must be accepted separately.
                return self.candidate(trusted)
            if record.model_copy(update={"status": "active"}) != original or record.status != "active":
                raise BudgetPending("原采用已变化，请核对当前预算；不重放为新采用。")
            self.p.update(bound={"budget_id": record.budget_id, "version": record.version},
                          candidate_done=True, mode=None)
            self.b.update(budget_id=record.budget_id, budget_version=record.version)
            summary, _ = self._window(trusted, record.scope)
            self._view(record, summary)
            return self.entry._ask(trusted, self.state,
                "已核实原个人预算采用记录；尚未办理资金动作。请明确是否继续生日安排。",
                [("继续生日安排", {"kind": "personal_continue"}), ("停止", {"kind": "b_stop"})])
        return None

    def can_edit_cap(self):
        return not self.b.get("freeze") and not self.b.get("pending") and self.own() is None

    def text(self, trusted, text):
        if self.p.get("mode") == "candidate":
            return ModuleResult.model_validate(self.state["result"])
        if self.p.get("mode") != "limit":
            if self.b.get("pending"):
                return ModuleResult.model_validate(self.state["result"])
            if not self.p.get("prepared"):
                return self.entry._birthday_flow(self.state).advance(trusted)
            return None
        from .pension import parse_amount_fen
        amount = parse_amount_fen(text)
        if amount is None:
            return self.entry._ask(trusted, self.state, "请输入可核对的个人预算限额金额。", [("停止", {"kind": "b_stop"})])
        self.p["candidate"]["personal_limit_fen"] = amount
        self.state["constraints"]["personal_limit_fen"] = amount
        self.state["plan_revision"] += 1
        return self.candidate(trusted)

    def pause(self, trusted, reason):
        choices = [("重新核对预算", {"kind": "personal_retry"})]
        if not self.b.get("pending") or self.b.get("freeze"):
            choices.append(("查看当前个人预算候选", {"kind": "personal_review"}))
        if self.can_edit_cap():
            choices.append(("调整本次生日上限", {"kind": "personal_birthday_limit"}))
        choices.append(("停止并核实收尾", {"kind": "b_stop"}))
        # A paused funding action is not an unadopted candidate. Its retry/stop
        # options must not masquerade as another dedicated budget adoption.
        if not (self.p.get("view") or {}).get("adopted"):
            self.p["view"] = None
        return self.entry._ask(trusted, self.state, str(reason) + " 已暂停新增办理，原事实和占用保留。", choices)

    def _settlement_gap(self, trusted, record, transactions, commitments):
        gap = 0
        seen = set()
        for hold in commitments:
            original = self.store.get_adopted_budget(self.user, self.round, hold.budget_ref)
            if original is None:
                raise BudgetPending("原预算范围缺失，不能推定消费归属。")
            outside = (not set(original.scope.account_ids) & set(record.scope.account_ids)
                or original.scope.end_at <= record.scope.start_at or original.scope.start_at >= record.scope.end_at)
            if outside:
                continue  # only G is excluded; O still counts all non-closed versions
            if not hold.settled_transaction_ids:
                if hold.committed_fen > hold.unconsumed_fen:
                    raise BudgetPending("历史占用缺少真实结算编号，请先核对原任务。")
                continue
            owner = self.store.get_task(self.user, self.round, hold.task_id)
            data = (owner.snapshot.get("result") or {}).get("data") if owner else None
            rows = (data or {}).get("steps", [])
            if hold.task_id == self.task:
                rows = [r.model_dump(mode="json") for r in self.entry._view_data(self.state, "").steps]
            receipts = {row.get("result_ref"): row for row in rows
                if row.get("action") == "bank.capture_frozen" and row.get("status") == "succeeded"
                and row.get("operation_id") in {str(op) for op in hold.operation_ids}}
            historic = None
            for tid in hold.settled_transaction_ids:
                if tid in seen:
                    raise BudgetPending("结算引用重复，需核对原任务。")
                seen.add(tid)
                receipt = receipts.get(tid)
                if receipt is None or receipt.get("amount_fen") is None:
                    raise BudgetPending("原任务未发布完整结算事实，请先在原任务查询后刷新。")
                transaction = transactions.get(tid)
                if transaction is not None:
                    if (transaction.amount_fen != receipt["amount_fen"] or transaction.nature != "consumption"
                            or transaction.direction != "outflow"):
                        raise BudgetPending("账单与结算事实不一致。")
                    continue
                if historic is None:
                    _, historic = self._window(trusted, original.scope)
                transaction = historic.get(tid)
                if (transaction is None or transaction.amount_fen != receipt["amount_fen"]
                        or transaction.nature != "consumption" or transaction.direction != "outflow"):
                    raise BudgetPending("缺少交易的实际账户/时间归属，不能将未知当作零消费。")
                if (transaction.account_id in record.scope.account_ids
                        and record.scope.start_at <= transaction.occurred_at < record.scope.end_at):
                    gap += receipt["amount_fen"]
        return gap

    def refresh(self, trusted, *, for_write=True):
        if for_write and (self.p.get("mode") in {"candidate", "limit"}
                or ((self.state.get("constraints") or {}).get("personal_limit_fen") is not None
                    and not self.p.get("candidate_done"))):
            raise BudgetPending("个人预算候选尚未采用，须先通过原任务专用选项处理。")
        record = self.discover()
        if record is None:
            if self.p.get("bound"):
                raise BudgetPending("原预算失效，停止新办理。")
            return None, None
        ref = {"budget_id": record.budget_id, "version": record.version}
        own = self.own()
        if for_write and own is not None and own.state == "closed":
            raise BudgetPending("原占用已结清，不能恢复新的购买；仅保留原事实查询。")
        if self.b.get("freeze") and self.p.get("bound") is None:
            raise BudgetPending("冻结后发现新的适用个人预算，须先明确绑定并核验真实未消费占用，当前仅允许原号核实/收尾。")
        self.p["bound"] = ref
        self.b.update(budget_id=record.budget_id, budget_version=record.version)
        summary, transactions = self._window(trusted, record.scope)
        view = self._view(record, summary)
        holds = self.store.list_budget_commitments(self.user, self.round, record.budget_id, include_closed=True)
        gap = self._settlement_gap(trusted, record, transactions, holds)
        occupied = sum(h.unconsumed_fen for h in holds if h.state != "closed")
        available = view.remaining_fen - gap
        if self.b.get("freeze") and self.own() is None:
            # A budget adopted after a verified freeze only binds the bank's
            # actual unconsumed remainder, never cap-minus-basket arithmetic.
            steps = self.entry._view_data(self.state, "").steps
            remainder = next((r.amount_fen for r in steps if r.step_id == "birthday-remaining"
                              and r.status == TaskStatus.SUCCEEDED), None)
            if remainder is None or self.b["freeze"].get("status") != "completed":
                raise BudgetPending("原冻结未消费金额尚待银行核实，不能绑定新增预算占用。")
            for row in steps:
                if row.action == "bank.capture_frozen" and row.status == TaskStatus.SUCCEEDED:
                    if row.result_ref not in transactions:
                        raise BudgetPending("绑定前的原消费尚无完整账单归属，需先核对。")
            cid = f"bc_{self.task}"
            hold = BudgetCommitment(budget_ref=BudgetRef.model_validate(ref), task_id=self.task,
                commitment_id=cid, committed_fen=remainder, unconsumed_fen=remainder,
                freeze_id=self.b["freeze"]["freeze_id"], operation_ids=[self.b["freeze"]["operation_id"]],
                settled_transaction_ids=[], state="active", updated_at=self.entry.clock())
            try:
                self.store.register_budget_commitment(self.user, self.round, hold, max_in_flight_fen=available)
            except BudgetOccupationExceededError:
                raise BudgetPending("原冻结未消费占用超过新个人剩余额度，当前只能核实/收尾。") from None
            self.b["commitment_id"] = cid
            self.entry._save(trusted, None, self.state)
            occupied += remainder
        self.p.update(gap_fen=gap, occupied_fen=occupied, max_in_flight_fen=available)
        if occupied > available:
            raise BudgetPending("当前个人剩余额度不足以覆盖已有未结占用，先核对或收尾。")
        return record, available

    def reserve(self, trusted):
        record, room = self.refresh(trusted)
        if record is None:
            return
        cid = self.b.get("commitment_id") or f"bc_{self.task}"
        existing = self.own()
        op = (self.b.get("pending") or {}).get("operation_id")
        if not op:
            raise BudgetPending("缺少原冻结操作编号，不能预留或提交。")
        if existing is not None and (existing.state != "pending"
                or existing.committed_fen != self.b["budget_limit_fen"]
                or existing.unconsumed_fen != self.b["budget_limit_fen"]
                or existing.operation_ids != [UUID(str(op))]):
            raise BudgetPending("原预留金额或操作已变化，不能沿用旧占用执行；请核实原操作或收尾。")
        if existing is None:
            hold = BudgetCommitment(budget_ref=BudgetRef(budget_id=record.budget_id, version=record.version),
                task_id=self.task, commitment_id=cid, committed_fen=self.b["budget_limit_fen"],
                unconsumed_fen=self.b["budget_limit_fen"], freeze_id=None, operation_ids=[op],
                settled_transaction_ids=[], state="pending", updated_at=self.entry.clock())
            try:
                self.store.register_budget_commitment(self.user, self.round, hold, max_in_flight_fen=room)
            except BudgetOccupationExceededError:
                raise BudgetPending("本次上限超过个人预算可新增额度，请先调整本次上限或核对原占用。") from None
            self.b["commitment_id"] = cid
        self.b["freeze_submission"] = "intent"
        self.entry._save(trusted, None, self.state)

    def check_freeze_room(self, trusted):
        record, room = self.refresh(trusted)
        if record is not None and self.own() is None:
            if self.b["budget_limit_fen"] > room-self.p["occupied_fen"]:
                raise BudgetPending(f"本次生日上限超过个人预算可新增额度{money(room-self.p['occupied_fen'])}元"
                    f"（账单未反映的已核实消费{money(self.p['gap_fen'])}元，未结占用{money(self.p['occupied_fen'])}元），请调整本次上限或核对原占用。")

    def own(self):
        ref = self.p.get("bound")
        if not ref:
            return None
        cid = self.b.get("commitment_id") or f"bc_{self.task}"
        return next((r for r in self.store.list_budget_commitments(self.user, self.round,
            ref["budget_id"], include_closed=True) if r.commitment_id == cid), None)

    def frozen(self, freeze):
        hold = self.own()
        if hold and hold.state != "closed":
            operation = UUID(str(freeze["operation_id"]))
            self._update(hold.model_copy(update={"freeze_id": freeze.get("freeze_id"),
                "state": "unknown" if freeze["status"] == "unknown" else "active",
                "operation_ids": list(dict.fromkeys([*hold.operation_ids, operation]))}))

    def unknown(self, operation_id):
        hold = self.own()
        if hold:
            self._update(hold.model_copy(update={"state": "unknown",
                "operation_ids": list(dict.fromkeys([*hold.operation_ids, UUID(str(operation_id))]))}))

    def consume(self, item):
        hold = self.own()
        if hold is None:
            return
        fact = self.b.get("write_facts", {}).get(f"capture:{item['product_id']}", {})
        tid, amount, op = fact.get("result_ref"), fact.get("amount_fen"), fact.get("operation_id")
        if tid in hold.settled_transaction_ids:
            return
        if not tid or amount is None or op is None or amount > hold.unconsumed_fen:
            raise BudgetPending("核销回执不完整，占用保持原状，请核对原操作。")
        self._update(hold.model_copy(update={"unconsumed_fen": hold.unconsumed_fen-amount,
            "operation_ids": list(dict.fromkeys([*hold.operation_ids, UUID(str(op))])),
            "settled_transaction_ids": [*hold.settled_transaction_ids, tid], "state": "active"}))

    def close(self):
        hold = self.own()
        if hold:
            self._update(hold.model_copy(update={"unconsumed_fen": 0,
                "committed_fen": hold.committed_fen-hold.unconsumed_fen, "state": "closed"}))

    def _update(self, hold):
        self.store.update_budget_commitment(self.user, self.round, hold.commitment_id,
            hold.model_copy(update={"updated_at": self.entry.clock()}))
