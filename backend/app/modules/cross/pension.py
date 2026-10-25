"""Monthly pension arrangement: funds scope, living reserve, per-transfer execution.

Ticket v05-cross-business/02 on the shared plan skeleton. Every money figure is
a bank fact or a user-adopted number the server recorded — the model proposes
nothing effective here. D1 runs through the storage arrangement seam: one
adopted arrangement per payer account, adopted before the first transfer and
closed only when the chosen steps and their closeout are all verified. An
unknown transfer keeps the arrangement active and blocks the rest (never a
silent retry). Cancelling a future debit never adds to this month's funds
(P05): the base is income or balance read before any cancel.
"""

from __future__ import annotations

import re
from uuid import uuid4

from app.contracts.common import TaskStatus
from app.contracts.cross import ArrangementView

from . import plan
from .plan import money, month_range
from app.storage.application import ArrangementConflictError

_AMOUNT = re.compile(r"^\s*(\d+)(?:[.．](\d{1,2}))?\s*(?:元|块钱?|块)?\s*$")


def parse_amount_fen(text) -> int | None:
    """Strict yuan text to fen; anything else asks again instead of guessing."""

    if not isinstance(text, str):
        return None
    found = _AMOUNT.match(text)
    if not found:
        return None
    return int(found.group(1)) * 100 + int((found.group(2) or "").ljust(2, "0"))


class PensionFlow:
    """Owns the monthly_arrangement phases on top of the shared plan skeleton."""

    DEFAULTS = {
        "phase": "facts", "basis": None, "base_fen": None,
        "income_transaction_ids": [], "payer": None,
        "reserve_fen": None, "includes_debits": None,
        "known_debits_fen": None, "allocations": [], "arrangement_id": None,
        "pre_cancel": False, "accounts": [], "payees": [],
    }

    def __init__(self, entry, state: dict):
        self.entry, self.state = entry, state
        pension = state.get("pension")
        if pension is None:
            pension = {}
            state["pension"] = pension
        for key, default in self.DEFAULTS.items():
            pension.setdefault(key, default)
        self.pension = pension

    # ------------------------------------------------------------------ helpers

    def _inventory(self) -> list[dict]:
        return self.state.get("inventory") or []

    def _upcoming_total(self):
        """Live total of still-known future debits (review F5).

        Computed from the inventory minus every cancellation the bank has
        already confirmed, so an adopted arrangement never carries the
        pre-cancellation snapshot.
        """

        settled = ({receipt["subscription_id"] for receipt in self.state.get("receipts", [])}
                   | {entry["subscription_id"] for entry in self.state.get("unknown", [])})
        return sum(item.get("amount_fen", 0) for item in self._inventory()
                   if item.get("status") == "active"
                   and item.get("source_type") == "mandate"
                   and item.get("can_cancel_in_bank")
                   and item.get("subscription_id") not in settled)

    def _income_transactions(self) -> list[dict]:
        record = plan.step_state(self.state, "bills_details")
        result = record.get("result")
        if not isinstance(result, dict):
            return []
        return [row for row in result.get("transactions") or []
                if row.get("direction") == "inflow" and row.get("nature") == "transfer"
                and row.get("account_id") == self.pension["payer"]]

    def _balance(self, account_id: str):
        for account in self.pension["accounts"]:
            if account.get("account_id") == account_id:
                return account.get("available_balance_fen")
        return None

    def _protected(self) -> int:
        reserve = self.pension["reserve_fen"] or 0
        debits = self._upcoming_total() if self.pension["includes_debits"] is False else 0
        if self.pension["includes_debits"] is None:
            debits = 0
        return reserve + debits

    def _transferred(self) -> int:
        total = 0
        for step in self.state["steps"]:
            if not step["step_id"].startswith("transfer:"):
                continue
            record = plan.step_state(self.state, step["step_id"])
            if record.get("status") is TaskStatus.SUCCEEDED:
                total += step["amount_fen"]
        return total

    def _distributable(self) -> int:
        return self.pension["base_fen"] - self._protected()

    def _remaining(self) -> int:
        return self._distributable() - self._transferred()

    def view(self) -> ArrangementView:
        from app.contracts.bills import BillScope as Scope
        now = self.entry.clock()
        start, end = month_range(now, 0)
        return ArrangementView(
            arrangement_id=self.pension["arrangement_id"] or f"arr_{self.state['actor'][2]}",
            plan_revision=self.state["plan_revision"],
            payer_account_id=self.pension["payer"],
            funds_basis=self.pension["basis"] or "available_balance",
            income_transaction_ids=list(self.pension["income_transaction_ids"]),
            base_fen=self.pension["base_fen"],
            living_reserve_fen=self.pension["reserve_fen"] or 0,
            reserve_includes_known_debits=bool(self.pension["includes_debits"]),
            upcoming_debit_scope=Scope(
                account_ids=[self.pension["payer"]], start_at=start, end_at=end),
            known_debits_fen=self._upcoming_total(),
            protected_fen=self._protected(),
            distributable_fen=self._distributable(),
            facts_as_of=now,
            adopted=self.pension["arrangement_id"] is not None,
        )

    # ------------------------------------------------------------------ advance

    def advance(self, trusted) -> object:
        entry, state = self.entry, self.state
        # A pending question stays put on an empty resume: a status query must
        # not dispatch the very spend the user has not answered about.
        held = self.pension.get("hold_question")
        if held is not None:
            return held
        entry._reconcile(state, trusted)
        entry._collect_read_facts(state)
        self._collect_pension_facts()
        holding = plan.holding_step(state)
        if holding is not None:
            return entry._holding_view(trusted, state, holding)
        ready = plan.next_step(state)
        while ready is not None and ready["kind"] == "read":
            entry._dispatch(trusted, state, ready)
            entry._reconcile(state, trusted)
            entry._collect_read_facts(state)
            self._collect_pension_facts()
            holding = plan.holding_step(state)
            if holding is not None:
                return entry._holding_view(trusted, state, holding)
            ready = plan.next_step(state)
        if ready is not None and ready["kind"] == "write":
            if ready["step_id"].startswith("transfer:"):
                # One failed transfer pauses every remaining one; the user
                # decides what to do with the rest (review F3).
                if self._any_transfer_failed():
                    return self._paused_by_failure(trusted)
                problem = self._preflight(trusted, ready)
                if problem is not None:
                    return problem
            entry._dispatch(trusted, state, ready)
            entry._reconcile(state, trusted)
            holding = plan.holding_step(state)
            if holding is not None:
                return entry._holding_view(trusted, state, holding)
        return self._phase_view(trusted)

    def _any_transfer_failed(self) -> bool:
        return any(step["step_id"].startswith("transfer:")
                   and plan.step_state(self.state, step["step_id"]).get("status")
                   is TaskStatus.FAILED
                   for step in self.state["steps"])

    def _paused_by_failure(self, trusted):
        lines = self.entry._pension_summary_lines(self.state)[0]
        return self.entry._view(
            trusted, self.state,
            "有一笔转账没有办成，后续转账已暂停；已成功的保留，不会自动重办。\n"
            + "\n".join(lines))

    def _collect_pension_facts(self) -> None:
        # The latest successful accounts read wins, including per-transfer
        # refreshes: balances are re-verified before every spend (review F1).
        latest_accounts = None
        for step in self.state["steps"]:
            if step.get("action") != "transfer.list_accounts":
                continue
            record = plan.step_state(self.state, step["step_id"])
            if record.get("status") is TaskStatus.SUCCEEDED and isinstance(
                    record.get("result"), dict):
                latest_accounts = record["result"].get("accounts") or []
        if latest_accounts is not None:
            self.pension["accounts"] = latest_accounts
            self.pension["accounts_ok"] = True
        payees = plan.step_state(self.state, "payees")
        if payees.get("status") is TaskStatus.SUCCEEDED and isinstance(
                payees.get("result"), dict):
            self.pension["payees"] = payees["result"].get("payees") or []
            self.pension["payees_ok"] = True
        elif payees.get("status") is TaskStatus.FAILED:
            self.pension["payees_ok"] = False

    # ------------------------------------------------------------------ preflight

    def _preflight(self, trusted, step: dict):
        """Refresh facts before each transfer; never auto-lower a shortfall."""

        entry, state = self.entry, self.state
        record = plan.step_state(state, step["step_id"])
        # Every attempt refreshes anew: a retry must see the current balance,
        # never the snapshot that produced the refusal (review F2).
        attempt = int(record.get("refresh_attempts") or 0) + 1
        record["refresh_attempts"] = attempt
        refresh_id = f"accounts_refresh:{step['step_id']}#{attempt}"
        plan.add_step(state, {"step_id": refresh_id,
                              "action": "transfer.list_accounts", "kind": "read",
                              "depends_on": []})
        refresh_step = next(s for s in state["steps"] if s["step_id"] == refresh_id)
        entry._dispatch(trusted, state, refresh_step)
        entry._reconcile(state, trusted)
        self._collect_pension_facts()
        refresh_record = plan.step_state(state, refresh_id)
        if refresh_record.get("status") is not TaskStatus.SUCCEEDED:
            return self._hold(entry._ask(trusted, state,
                              "转账前核实账户余额时暂时查不到，这笔先不办理；"
                              "已成功的转账保持不变。可稍后重试或停止剩余办理。",
                              [("停止剩余办理", {"kind": "pension_stop"}),
                               ("我已核实，重试这笔", {"kind": "pension_retry",
                                                      "step_id": step["step_id"]})]))
        balance = self._balance(self.pension["payer"])
        if balance is not None and balance < step["amount_fen"]:
            return self._hold(entry._ask(trusted, state,
                              f"账户当前可用余额 {money(balance)} 元，不够支付这笔 "
                              f"{money(step['amount_fen'])} 元转账。留存与已成功转账保持不变，"
                              "不会自动改小金额。您可以先核实账户，或停止剩余办理。",
                              [("停止剩余办理", {"kind": "pension_stop"}),
                               ("我已核实，重试这笔", {"kind": "pension_retry",
                                                      "step_id": step["step_id"]})]))
        if self._remaining() < step["amount_fen"]:
            return self._hold(entry._ask(trusted, state,
                              f"按已采用的范围与留存，本次还可转 {money(self._remaining())} 元，"
                              f"不够支付 {money(step['amount_fen'])} 元；留存不会被自动降低。"
                              "请选择停止剩余办理，或说明要如何调整。",
                              [("停止剩余办理", {"kind": "pension_stop"})]))
        return None

    def _hold(self, question):
        self.pension["hold_question"] = question
        return question

    # ------------------------------------------------------------------ phases

    def _phase_view(self, trusted):
        phase = self.pension["phase"]
        handler = {
            "facts": self._ask_payer, "pre_cancel": self._ask_pre_cancel,
            "basis": self._ask_basis, "reserve": self._ask_reserve,
            "reserve_debits": self._ask_reserve_debits,
            "destination": self._ask_destination, "amount": self._ask_amount,
            "adopt": self._ask_adopt, "running": self._running_view,
            "cancel_pick": lambda trusted: self.entry._ask_pick(
                trusted, self.state, pension_mode=True),
        }[phase]
        return handler(trusted)

    def _ask_payer(self, trusted):
        accounts = self.pension["accounts"]
        if len(accounts) <= 1:
            self.pension["payer"] = accounts[0]["account_id"] if accounts else None
            self.pension["phase"] = "pre_cancel"
            return self._ask_pre_cancel(trusted)
        choices = [(f"{a['display_name']} · {a['account_masked']}（可用 "
                    f"{money(a['available_balance_fen'])} 元）",
                    {"kind": "pension_payer", "account_id": a["account_id"]})
                   for a in accounts]
        return self.entry._ask(trusted, self.state,
                               "这张安排要用哪张本人账户？", choices)

    def _ask_pre_cancel(self, trusted):
        cancellable = self.entry._cancellable(self.state)
        if not cancellable:
            self.pension["phase"] = "basis"
            return self._ask_basis(trusted)
        self.pension["phase"] = "pre_cancel"
        return self.entry._ask(trusted, self.state,
                               "安排资金前，要不要先看看有哪些不用了的自动扣费？"
                               "先退订不影响本次安排的资金范围。",
                               [("先看看可退订的扣费", {"kind": "pension_pre_cancel"}),
                                ("不用，直接安排资金", {"kind": "pension_skip_cancel"})])

    def _ask_basis(self, trusted):
        incomes = self._income_transactions()
        balance = self._balance(self.pension["payer"])
        accounts_ok = bool(self.pension.get("accounts_ok"))
        choices = self._basis_choices(incomes, balance)
        if not choices:
            return self.entry._ask(trusted, self.state,
                                   "账户与入账情况暂时都查不到，本次先不安排；"
                                   "已办事项不受影响。",
                                   [("停止本次安排", {"kind": "pension_stop"})])
        note = "" if accounts_ok else "（账户余额暂时查不到，本次不提供余额范围）"
        return self.entry._ask(trusted, self.state,
                               "本次安排的资金范围以哪个为准？（金额以银行记录为准）" + note,
                               choices)

    def _ask_reserve(self, trusted):
        return self.entry._ask(trusted, self.state,
                               f"本月生活费要留多少？（本次可安排范围 "
                               f"{money(self.pension['base_fen'])} 元；可输入金额，如“1500元”）",
                               [("不留存，全部安排", {"kind": "pension_reserve",
                                                      "fen": 0})])

    def _ask_reserve_debits(self, trusted):
        debits = self._upcoming_total()
        if not debits:
            self.pension["includes_debits"] = True
            self.pension["phase"] = "destination"
            return self._ask_destination(trusted)
        return self.entry._ask(trusted, self.state,
                               f"未来一个月内已知代扣合计 {money(debits)} 元。这部分要算进"
                               "生活费留存里吗？",
                               [("算进留存（不再另加）", {"kind": "pension_debits",
                                                          "includes": True}),
                                ("不算，留存之外另加保护", {"kind": "pension_debits",
                                                            "includes": False})])

    def _ask_destination(self, trusted):
        if "payees" not in plan.step_ids(self.state):
            plan.add_step(self.state, {"step_id": "payees",
                                       "action": "transfer.list_payees", "kind": "read",
                                       "depends_on": []})
            return self.entry._advance_pension(trusted, self.state)
        payees = [p for p in self.pension["payees"]
                  if p.get("payee_id")] or []
        choices = []
        for payee in payees:
            name = payee["name_masked"]
            if payee.get("remark"):
                name += f"·{payee['remark']}"
            choices.append((f"转给 {name}（{payee['account_masked']}）",
                            {"kind": "pension_payee", "payee_id": payee["payee_id"], "name": name}))
        own_accounts = [a for a in self.pension["accounts"]
                        if a["account_id"] != self.pension["payer"]]
        choices = [(f"转到 本人·{a['display_name']}（{a['account_masked']}）",
                    {"kind": "pension_own_account", "target_account_id": a["account_id"],
                     "name": f"本人·{a['display_name']}"}) for a in own_accounts] + choices
        choices.append(("去向已选好，开始办理", {"kind": "pension_adopt"}))
        remaining = self._remaining()
        prompt = (f"本次还可安排 {money(remaining)} 元。请选择本人账户或收款人："
                  "（逐笔选择，每笔转账前还会有确认）")
        if not payees and own_accounts:
            if self.pension.get("payees_ok") is False:
                prompt += "保存的收款人暂时查不到，已查到的本人账户仍可选择。"
                choices.append(("重新查询收款人", {"kind": "pension_retry_payees"}))
        elif not payees:
            if self.pension.get("payees_ok") is False:
                prompt = "收款人暂时查不到（不是没有收款人）。可以重新查询或停止本次安排。"
                choices = [("重新查询收款人", {"kind": "pension_retry_payees"}),
                           ("停止本次安排", {"kind": "pension_stop"})]
            else:
                prompt = "您还没有保存的收款人，暂时无法新增转账去向。可以停止本次安排。"
                choices = [("停止本次安排", {"kind": "pension_stop"})]
            return self.entry._ask(trusted, self.state, prompt, choices)
        return self.entry._ask(trusted, self.state, prompt, choices)

    def _ask_amount(self, trusted):
        target = self.pension["allocations"][-1]
        return self.entry._ask(trusted, self.state,
                               f"转给 {target['name']} 多少元？（还可安排 "
                               f"{money(self._remaining())} 元，可输入金额）",
                               [("不转了，去掉这笔", {"kind": "pension_drop_last"})])

    def _failed_cancels(self) -> list[str]:
        names = []
        for step in self.state["steps"]:
            if not step["step_id"].startswith("cancel:"):
                continue
            record = plan.step_state(self.state, step["step_id"])
            if record.get("status") is TaskStatus.FAILED:
                item = next((row for row in self._inventory()
                             if row.get("subscription_id") == step["subscription_id"]), None)
                names.append((item or {}).get("service_name") or step["subscription_id"])
        return names

    def _ask_adopt(self, trusted):
        view = self.view()
        failed = self._failed_cancels()
        preface = []
        confirm_label = "采用并开始办理"
        if failed:
            preface.append("您要求先退订的 " + "、".join(failed)
                           + " 没有办成（银行或安全侧未通过）；后续转账与之不再绑定，"
                             "请明确选择是否继续。")
            confirm_label = "知道未办成，仍继续办理转账"
        lines = preface + [f"资金范围 {money(view.base_fen)} 元"
                 f"（{'本月实际入账' if view.funds_basis == 'selected_income' else '当前可用余额'}）；",
                 f"生活费留存 {money(view.living_reserve_fen)} 元"
                 + (f"，其中已含未来代扣 {money(view.known_debits_fen)} 元"
                    if view.reserve_includes_known_debits and view.known_debits_fen else ""),
                 f"可安排 {money(view.distributable_fen)} 元，共 "
                 f"{len(self.pension['allocations'])} 笔转账，合计 "
                 f"{money(sum(a['amount_fen'] for a in self.pension['allocations']))} 元。",
                 "采用后开始逐笔办理；每笔转账仍会单独确认。"]
        self.pension["phase"] = "adopt"
        return self.entry._ask(trusted, self.state, "\n".join(lines),
                               [(confirm_label, {"kind": "pension_confirm_adopt"}),
                                ("取消，不办理", {"kind": "pension_stop"})])

    def _running_view(self, trusted):
        state = self.state
        pending = [step for step in state["steps"]
                   if step["step_id"].startswith("transfer:")
                   and plan.step_state(state, step["step_id"]).get("status") is None]
        unknown = any(plan.step_state(state, step["step_id"]).get("status")
                      is TaskStatus.NEEDS_ATTENTION
                      for step in state["steps"] if step["step_id"].startswith("transfer:"))
        failed = any(plan.step_state(state, step["step_id"]).get("status") is TaskStatus.FAILED
                     for step in state["steps"] if step["step_id"].startswith("transfer:"))
        if unknown:
            return self.entry._receipt_pension(trusted, state)
        if failed:
            # A failed transfer pauses the remaining ones; the user decides.
            return self.entry._view(
                trusted, state,
                "有一笔转账没有办成，后续转账已暂停。已成功的保留，不会自动重办。",
                active=None, child_id=None)
        if pending:
            # The previous write settled; continue with the next allocation.
            return self.advance(trusted)
        self.entry._close_arrangement_if_any(state)
        return self.entry._receipt_pension(trusted, state)

    # ------------------------------------------------------------------ choices

    def apply(self, trusted, picked: dict):
        entry, state, pension = self.entry, self.state, self.pension
        pension.pop("hold_question", None)
        kind = picked["kind"]
        if kind in {"cancel_item", "finish"}:
            # The optional pre-transfer cancel loop shares the expense pick
            # handling; "finish" there returns to the pension phases.
            return entry._apply_pick(trusted, state, picked)
        if kind == "pension_payer":
            pension["payer"] = picked["account_id"]
            pension["phase"] = "pre_cancel"
            return entry._advance_pension(trusted, self.state)
        if kind == "pension_pre_cancel":
            pension["pre_cancel"] = True
            pension["phase"] = "cancel_pick"
            return entry._ask_pick(trusted, state, pension_mode=True)
        if kind == "pension_skip_cancel":
            pension["phase"] = "basis"
            return entry._advance_pension(trusted, self.state)
        if kind == "pension_basis":
            pension["basis"] = picked["basis"]
            if picked["basis"] == "selected_income":
                incomes = self._income_transactions()
                selected_ids = picked.get("income_transaction_ids")
                if not selected_ids or not set(selected_ids) <= {row["transaction_id"] for row in incomes}:
                    return self._ask_basis(trusted)
                pension["income_transaction_ids"] = list(selected_ids)
                pension["base_fen"] = sum(row["amount_fen"] for row in incomes
                                           if row["transaction_id"] in selected_ids)
            else:
                pension["base_fen"] = self._balance(pension["payer"])
            pension["phase"] = "reserve"
            return self._ask_reserve(trusted)
        if kind == "pension_reserve":
            pension["reserve_fen"] = picked["fen"]
            pension["phase"] = "reserve_debits"
            return entry._advance_pension(trusted, self.state)
        if kind == "pension_debits":
            pension["includes_debits"] = picked["includes"]
            pension["phase"] = "destination"
            return entry._advance_pension(trusted, self.state)
        if kind == "pension_payee":
            pension["allocations"].append({"payee_id": picked["payee_id"],
                                           "name": picked["name"], "amount_fen": None})
            pension["phase"] = "amount"
            return self._ask_amount(trusted)
        if kind == "pension_own_account":
            pension["allocations"].append({"target_account_id": picked["target_account_id"],
                                           "name": picked["name"], "amount_fen": None})
            pension["phase"] = "amount"
            return self._ask_amount(trusted)
        if kind == "pension_drop_last":
            pension["allocations"].pop()
            pension["phase"] = "destination"
            return entry._advance_pension(trusted, self.state)
        if kind == "pension_adopt":
            # The explicit adoption menu: adopting is a user decision the server
            # records, never implied by finishing the destination list.
            pension["phase"] = "adopt"
            return self._ask_adopt(trusted)
        if kind == "pension_confirm_adopt":
            return self._adopt(trusted)
        if kind == "pension_stop":
            return entry._closeout(trusted, state, stop_reason="user_cancelled")
        if kind == "pension_retry":
            record = plan.step_state(state, picked["step_id"])
            record["status"] = None  # allow the preflight to run again
            return entry._advance_pension(trusted, self.state)
        if kind == "pension_switch_account":
            pension["phase"] = "facts"
            return entry._advance_pension(trusted, state)
        if kind == "pension_recheck":
            return self._adopt(trusted)
        if kind == "pension_retry_payees":
            plan.step_state(state, "payees").clear()  # redispatch the read
            pension["phase"] = "destination"
            return entry._advance_pension(trusted, state)
        raise ValueError("INVALID_OPTION")

    def apply_text(self, trusted, text: str):
        pension = self.pension
        pension.pop("hold_question", None)
        if pension["phase"] == "reserve":
            fen = parse_amount_fen(text)
            if fen is None or fen > pension["base_fen"]:
                return self._ask_reserve(trusted)
            pension["reserve_fen"] = fen
            pension["phase"] = "reserve_debits"
            return self.entry._advance_pension(trusted, self.state)
        if pension["phase"] == "amount" and pension["allocations"]:
            fen = parse_amount_fen(text)
            remaining = self._remaining()
            if fen is None or fen <= 0 or fen > remaining:
                return self._ask_amount(trusted)
            pension["allocations"][-1]["amount_fen"] = fen
            pension["phase"] = "destination"
            return self.entry._advance_pension(trusted, self.state)
        if pension["phase"] == "basis":
            # A spoken range is a candidate; the bank facts decide (XL-P02).
            claimed = parse_amount_fen(text)
            incomes = self._income_transactions()
            income_total = sum(row["amount_fen"] for row in incomes)
            balance = self._balance(self.pension["payer"])
            if claimed is None:
                return self._ask_basis(trusted)
            correction = []
            if claimed not in {row["amount_fen"] for row in incomes} and claimed != income_total and claimed != balance:
                facts = f"本月实际入账 {money(income_total)} 元" if incomes else "本月入账暂无可查"
                if self.pension.get("accounts_ok") and balance is not None:
                    facts += f"，当前可用余额 {money(balance)} 元"
                else:
                    facts += "，账户余额暂时查不到"
                correction.append(f"您说的 {money(claimed)} 元与银行记录不一致：{facts}。以哪个为准？")
            prompt = "\n".join(correction) if correction else "请选择资金范围："
            return self.entry._ask(trusted, self.state, prompt,
                                   self._basis_choices(incomes, balance))
        # Text in other phases never names a money target (bank facts only).
        return self._phase_view(trusted)

    def _basis_choices(self, incomes, balance):
        choices = [(f"本月实际入账 {money(row['amount_fen'])} 元 · "
                    f"{row['occurred_at'][:19].replace('T', ' ')} · "
                    f"{row['counterparty_name']} · {row['summary']}（第{index}笔）",
                    {"kind": "pension_basis", "basis": "selected_income",
                     "income_transaction_ids": [row["transaction_id"]]})
                   for index, row in enumerate(incomes, 1)]
        # A failed accounts read offers no balance basis — zero would be a
        # fabricated fact, and a chosen None base crashes later maths (N1).
        if self.pension.get("accounts_ok") and balance is not None:
            choices.append((f"当前可用余额 {money(balance)} 元",
                            {"kind": "pension_basis", "basis": "available_balance"}))
        return choices

    # ------------------------------------------------------------------ adoption

    def _adopt(self, trusted):
        from app.contracts.cross import AdoptedArrangement

        entry, state, pension = self.entry, self.state, self.pension
        view = self.view()
        now = entry.clock()
        record = AdoptedArrangement(
            arrangement_id=view.arrangement_id, user_id=state["actor"][0],
            demo_round_id=state["actor"][1], source_task_id=state["actor"][2],
            plan_revision=state["plan_revision"], payer_account_id=pension["payer"],
            funds_basis=view.funds_basis,
            income_transaction_ids=list(pension["income_transaction_ids"]),
            base_fen=pension["base_fen"], living_reserve_fen=pension["reserve_fen"] or 0,
            reserve_includes_known_debits=bool(pension["includes_debits"]),
            upcoming_debit_scope=view.upcoming_debit_scope,
            known_debits_fen=view.known_debits_fen, adopted_at=now,
            adoption_interaction_id=state.get("interaction_id") or str(uuid4()),
            status="active",
        )
        try:
            entry.harness.application.acquire_arrangement(record)
        except ArrangementConflictError:
            return self._hold(entry._ask(trusted, state,
                              "这张账户已有正在办理的资金安排。需先完成、调整或结束原安排，"
                              "也可以换一张账户再核对。查询不受影响。",
                              [("换一张账户", {"kind": "pension_switch_account"}),
                               ("重新检查这张账户", {"kind": "pension_recheck"}),
                               ("停止本次安排", {"kind": "pension_stop"})]))
        pension["arrangement_id"] = record.arrangement_id
        for index, allocation in enumerate(pension["allocations"], 1):
            plan.add_step(state, {
                "step_id": f"transfer:{index}", "action": "transfer.start_transfer",
                "kind": "write", "payee_id": allocation.get("payee_id"),
                "target_account_id": allocation.get("target_account_id"),
                "payee_name": allocation["name"], "amount_fen": allocation["amount_fen"],
                "depends_on": []})
        pension["phase"] = "running"
        return entry._advance_pension(trusted, self.state)
