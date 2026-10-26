"""Birthday orchestration: candidates → adoption → freeze → order → capture → release.

Ticket v05-cross-business/03 on the shared plan skeleton. The money writes run
through the birthday ports (the security-declared private tools behind the
gate, never the model registry and never ordinary transfers): each sensitive
action carries its own confirmation, the freeze confirmation displays the §3.5
limited-release clause, and the ending releases only the bank-verified
remainder under the original authorization. Order creation and payment are
reported separately — an unpaid order is never "bought", a paid one is never
"cancelled", and nothing claims real-world delivery. The personal budget is a
constraint sub-goal enforced through the serialized occupation seam: same
consumption never counts twice, competing tasks cannot double-spend one cap.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime
from uuid import uuid4

from app.contracts.bank import ListProductsInput
from app.contracts.common import SecurityDecisionCode, TaskStatus
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult

from . import plan
from .birthday_ports import BirthdayPlan, WriteOutcome
from .plan import money
from .personal_budget import PersonalBudget, BudgetPending

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REF = re.compile(r"^[A-Za-z0-9-]{8,64}$")
# The edit-wait menu never other than these controlled choices; a client cannot
# name an item id, quantity or amount from chat (server options only).
_EDIT_KINDS = frozenset({
    "b_edit_qty", "b_edit_remove", "b_edit_replace",
    "b_edit_add", "b_edit_choose", "b_edit_cancel", "b_edit_done",
})

_PRODUCT_FACTS = ("merchant_id", "merchant_name", "category", "unit_price_fen")


def yuan(fen) -> str:
    return money(int(fen or 0))


def item_key(item: dict) -> str:
    """A plan row's stable execution identity, separate from the product id.

    The legacy shape (an old checkpoint whose rows carry no ``item_id``) keeps
    the product key; a new row is always addressed by its own item id, so a
    same-product replacement is a different execution item.
    """
    return item.get("item_id") or item["product_id"]


def positive_quantity(text) -> int | None:
    """Only an explicit positive integer is a quantity; nothing is inferred."""
    value = (text or "").strip()
    if not value.isdigit() or int(value) < 1:
        return None
    return int(value)


class BirthdayFlow:
    """Owns the birthday phases on top of the shared plan skeleton."""

    DEFAULTS = {
        "phase": "facts", "payer": None,
        "budget_limit_fen": None, "budget_id": None, "budget_version": None,
        "deliver_by": None, "delivery_ref": None, "products": [],
        "chosen": [], "freeze": None, "orders": [],
        "pending": None, "holding": None, "commitment_id": None,
        "stop_reason": None, "released": None,
        # v05-cross-business/08: one controlled edit in flight, its facts and the
        # verified "failed, no order" evidence that may justify a replacement.
        "edit": None, "edit_text_target": None, "edit_replace_target": None,
        "edit_add": False, "edit_history": [], "verified_failures": {},
        "write_facts": {},
    }

    def __init__(self, entry, state: dict, ports):
        self.entry, self.state, self.ports = entry, state, ports
        data = state.get("birthday")
        if data is None:
            given = state.get("constraints") or {}
            data = {"budget_limit_fen": given.get("budget_fen"),
                    "payer": given.get("payer_account_id"), "delivery_ref": given.get("delivery_ref"),
                    "deliver_by": given.get("deliver_by")}
            state["birthday"] = data
        for key, default in self.DEFAULTS.items():
            data.setdefault(key, default)
        self.b = data

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _fact(item: dict, *, field: str | None = None) -> dict:
        """The service facts one plan row froze; amounts are always rebuilt."""
        facts = {name: item[name] for name in _PRODUCT_FACTS if item.get(name) is not None}
        facts["product_id"] = item["product_id"]
        if item.get("item_id") is not None:
            facts["item_id"] = item["item_id"]
        facts["name"] = item.get("name")
        facts["quantity"] = int(item.get("quantity") or 1)
        if field is not None:
            facts[field] = item.get(field)
        return facts

    def _plan_items(self) -> list[dict]:
        by_id = {p["product_id"]: p for p in self.b["products"]}
        rows = self.b["orders"] or self._chosen_items()
        items = []
        for row in rows:
            source = by_id.get(row["product_id"], {})
            quantity = int(row.get("quantity") or 1)
            unit_price_fen = row.get("unit_price_fen") or source.get("unit_price_fen")
            item = {**source, **self._fact(row)}
            item["quantity"] = quantity
            item["unit_price_fen"] = unit_price_fen
            item["amount_fen"] = row["amount_fen"]
            item["name"] = row.get("name") or source.get("product_name")
            items.append(item)
        return items

    def _plan(self) -> BirthdayPlan:
        items = tuple(self._plan_items())
        # The freeze covers the adopted budget cap, not the current basket:
        # purchases may shrink, the remainder returns at the ending (XL-B01).
        return BirthdayPlan(
            payer_account_id=self.b["payer"],
            budget_id=self.b["budget_id"], budget_version=self.b["budget_version"],
            budget_limit_fen=self.b["budget_limit_fen"],
            freeze_amount_fen=self.b["budget_limit_fen"],
            deliver_by=self.b["deliver_by"],
            delivery_ref=self.b["delivery_ref"], items=items)

    def _chosen_items(self) -> list[dict]:
        """The selected basket before the freeze: full facts, stable item ids.

        A legacy checkpoint stores only product ids; those stay one-unit rows
        without an item id so the old platform binding keeps its exact shape.
        """
        by_id = {p["product_id"]: p for p in self.b["products"]}
        items = []
        for chosen in self.b["chosen"]:
            if isinstance(chosen, dict):
                item = dict(chosen)
                item["quantity"] = int(item.get("quantity") or 1)
                item["unit_price_fen"] = int(item["unit_price_fen"])
                item["amount_fen"] = item["unit_price_fen"] * item["quantity"]
                items.append(item)
                continue
            source = by_id.get(chosen)
            if not source:
                continue
            item = dict(source)
            item["quantity"] = 1
            item["amount_fen"] = source["unit_price_fen"]
            item["name"] = source["product_name"]
            items.append(item)
        return items

    @staticmethod
    def _total(items) -> int:
        return sum(item["unit_price_fen"] * item.get("quantity", 1) for item in items)

    @staticmethod
    def _plan_total(rows) -> int:
        """The current plan total: a failed/skipped row committed no money."""
        return sum(int(row["amount_fen"]) for row in rows
                   if row.get("order") not in ("failed", "skipped"))

    @staticmethod
    def _new_item(product: dict, *, quantity: int = 1) -> dict:
        """One new execution item: the product id can repeat, the item id cannot."""
        unit_price_fen = int(product["unit_price_fen"])
        return {
            "item_id": f"bi-{uuid4().hex}",
            "product_id": product["product_id"],
            **{name: product[name] for name in _PRODUCT_FACTS
               if product.get(name) is not None},
            "name": product.get("product_name"),
            "quantity": quantity,
            "unit_price_fen": unit_price_fen,
            "amount_fen": unit_price_fen * quantity,
        }

    def _post_freeze(self) -> bool:
        """After the freeze the plan rows are the facts; nothing may be re-frozen."""
        return bool(self.b.get("freeze"))

    def _bump_revision(self) -> None:
        self.state["plan_revision"] = int(self.state.get("plan_revision") or 0) + 1

    def _row(self, key: str) -> dict | None:
        """The mutable plan row behind one stable item key, if it is in the plan."""
        rows = self.b["orders"] if self._post_freeze() else self.b["chosen"]
        for row in rows:
            if isinstance(row, str):
                if row == key:
                    return None  # a legacy product id is not an execution item
                continue
            if item_key(row) == key:
                return row
        return None

    def _display_rows(self) -> list[dict]:
        if self._post_freeze():
            return list(self.b["orders"])
        return self._chosen_items()

    def _editable_rows(self) -> list[dict]:
        """Rows still fully unsubmitted and without any attempt in flight."""
        if self._post_freeze():
            return [row for row in self.b["orders"]
                    if row.get("order") is None and row.get("capture") is None]
        return self._chosen_items()

    def _order(self, key: str) -> dict:
        return next(o for o in self.b["orders"] if item_key(o) == key)

    @staticmethod
    def _same_product(chosen, product_id: str) -> bool:
        if isinstance(chosen, str):
            return chosen == product_id
        return chosen.get("product_id") == product_id

    def _facts(self, item: dict) -> str:
        if item.get("capture") == "completed":
            return f"{item['name']} ×{item['quantity']}：已创建订单并已付款 {yuan(item['amount_fen'])} 元（不可修改）"
        if item.get("capture") == "unknown":
            return f"{item['name']} ×{item['quantity']}：付款结果待核实（不可修改）"
        if item.get("capture") == "failed":
            return f"{item['name']} ×{item['quantity']}：付款没有办成，订单未付款（不可修改）"
        if item.get("order") == "completed":
            return f"{item['name']} ×{item['quantity']}：已创建订单，未付款（{yuan(item['amount_fen'])} 元未扣，不可修改）"
        if item.get("order") == "unknown":
            return f"{item['name']} ×{item['quantity']}：下单结果待核实（不可修改）"
        if item.get("order") == "failed":
            return f"{item['name']} ×{item['quantity']}：下单未办成，未付款（不可修改）"
        return ""

    def _ask(self, trusted, prompt, choices):
        return self.entry._ask(trusted, self.state, prompt, choices)

    def _remember_write(self, kind, item_id, outcome):
        """Keep only displayable bank facts; never checkpoint delivery payloads."""
        key = kind if item_id is None else f"{kind}:{item_id}"
        record = self.b.setdefault("write_facts", {}).setdefault(key, {})
        record.update(status=outcome.state, operation_id=outcome.operation_id)
        if outcome.state != "completed" or outcome.result is None:
            return
        receipt = getattr(outcome.result, "receipt", None)
        if kind == "freeze" and receipt is not None:
            record.update(amount_fen=getattr(receipt, "frozen_amount_fen", None),
                          result_ref=getattr(receipt, "freeze_id", None),
                          remaining_fen=getattr(receipt, "remaining_fen", None))
        elif kind == "order":
            order = getattr(outcome.result, "order", None) or getattr(receipt, "order", None)
            if order is not None:
                record.update(order_id=getattr(order, "order_id", None),
                              amount_fen=getattr(order, "total_fen", None),
                              payment_status=getattr(order, "payment_status", None))
                record["result_ref"] = record["order_id"]
        elif kind == "capture" and receipt is not None:
            record.update(amount_fen=getattr(receipt, "captured_amount_fen", None),
                          result_ref=getattr(receipt, "transaction_id", None),
                          remaining_fen=getattr(receipt, "remaining_fen", None))

    # ------------------------------------------------------------------ advance

    def advance(self, trusted) -> ModuleResult:
        entry, state = self.entry, self.state
        if self.b.get("pending") and not self.b.get("holding"):
            PersonalBudget(entry, state).refresh(trusted)
            return self._pending_view(trusted)
        if self.b.get("holding"):
            # Replay the saved ask: an empty resume must not rotate the option
            # ids out from under the card the user is looking at.
            saved = state.get("result") or {}
            if saved.get("status") in ("waiting_input", "waiting_approval") and saved.get("interaction"):
                return ModuleResult.model_validate(saved).model_copy(
                    update={"run_id": trusted.run_id})
            return self._holding_view(trusted)
        entry._reconcile(state, trusted)
        entry._collect_read_facts(state)
        # Run the planned read children (accounts) to completion first: the
        # payer fact and the D1 check depend on them (same lesson as F1).
        ready = plan.next_step(state)
        while ready is not None and ready["kind"] == "read":
            entry._dispatch(trusted, state, ready)
            entry._reconcile(state, trusted)
            entry._collect_read_facts(state)
            ready = plan.next_step(state)
        accounts = plan.step_state(state, "accounts")
        if accounts.get("status") is TaskStatus.FAILED:
            return self._ask(trusted, "本人账户暂时查不到，本次生日办理先不开始。",
                             [("停止本次安排", {"kind": "b_stop"})])
        if accounts.get("status") is TaskStatus.SUCCEEDED and isinstance(
                accounts.get("result"), dict):
            rows = accounts["result"].get("accounts") or []
            if rows and not self.b["payer"]:
                self.b["payer"] = rows[0]["account_id"]
            if self.b["payer"] not in {row["account_id"] for row in rows}:
                raise BudgetPending("付款账户不在本人已查询账户中。")
        if not self.b["products"] and self.b["phase"] == "facts":
            found = self.ports.products(trusted, ListProductsInput(purpose="birthday"))
            data = getattr(found, "data", None)
            if data is None or getattr(found, "kind", "ok") != "ok":
                return self._ask(trusted, "商品清单暂时查不到（不是没有商品）。可稍后重试或停止。",
                                 [("重新查询商品", {"kind": "b_retry_products"}),
                                  ("停止本次安排", {"kind": "b_stop"})])
            self.b["products"] = [p.model_dump(mode="json") if hasattr(p, "model_dump") else p
                                  for p in data.products]
            self.b["phase"] = "budget"
        personal = PersonalBudget(entry, state)
        restored = personal.restore_adoption(trusted)
        if restored is not None:
            return restored
        if not personal.p.get("prepared"):
            if personal.p.get("mode") in ("candidate", "limit") and state.get("result"):
                return ModuleResult.model_validate(state["result"])
            candidate = personal.prepare(trusted)
            if candidate is not None:
                return candidate
            personal.p["prepared"] = True
        return self._phase_view(trusted)

    def _phase_view(self, trusted):
        if self.b["phase"] == "budget" and self.b["budget_limit_fen"] is not None:
            if self.b["budget_limit_fen"] <= 0:
                raise BudgetPending("本次生日上限为0，不冻结或购买；请明确调整后再办理。")
            self.b["phase"] = "date"
        if self.b["phase"] == "date" and self.b["deliver_by"]:
            self.b["phase"] = "delivery"
        if self.b["phase"] == "delivery" and self.b["delivery_ref"]:
            detail = self.entry.harness.application.get_controlled_detail(
                *self.state["actor"][:2], self.b["delivery_ref"], task_id=self.state["actor"][2])
            if detail is None or detail.kind != "delivery":
                raise BudgetPending("配送引用不属于本任务，请通过原受控表单重新提交。")
            self.b["phase"] = "pick"
        handler = {
            "facts": self.advance,
            "budget": self._ask_budget, "date": self._ask_date,
            "delivery": self._ask_delivery, "pick": self._ask_pick,
            "adopt": self._ask_adopt, "freeze": self._run_freeze,
            "orders": self._run_next_order, "finalize": self._finalize,
            "edit": self._ask_edit,
        }[self.b["phase"]]
        return handler(trusted)

    # ------------------------------------------------------------------ asks

    def _ask_budget(self, trusted):
        return self._ask(trusted, "这次生日安排的预算上限是多少元？（可输入金额，如“500元”）",
                         [("设置本月当前账户全部消费的个人预算", {"kind": "personal_begin"}),
                          ("停止本次安排", {"kind": "b_stop"})])

    def _ask_date(self, trusted):
        return self._ask(trusted, "希望在哪一天前送到？（可输入日期，如 2026-10-30）",
                         [("停止本次安排", {"kind": "b_stop"})])

    def _ask_delivery(self, trusted):
        result = self._ask(
            trusted,
            "请在配送信息专用表单填写收件人、电话和地址，提交后继续选择商品。"
            "配送原文不要发到聊天里。",
            [("停止本次安排", {"kind": "b_stop"})])
        return result.model_copy(update={"interaction": result.interaction.model_copy(
            update={"required_fields": ["delivery"]}), "data": None})

    def _ask_pick(self, trusted, note=None):
        prompt, choices = self.pick_menu(note)
        return self._ask(trusted, prompt, choices)

    def pick_menu(self, note=None):
        """The server-built selection menu: products, quantities and removal.

        Only these option ids answer the menu; a typed positive integer adjusts
        the most recently picked item's quantity (Q01).
        """
        chosen = self.b["chosen"]
        items = self._chosen_items()
        choices = []
        for product in self.b["products"]:
            pid = product["product_id"]
            if any(self._same_product(entry, pid) for entry in chosen):
                continue
            label = (f"{product['merchant_name']}·{product['product_name']} "
                     f"{yuan(product['unit_price_fen'])} 元")
            choices.append((label, {"kind": "b_pick", "product_id": pid}))
        for item in items:
            key = item_key(item)
            choices.append((f"改数量：{item['name']}（当前 {item['quantity']} 件）",
                            {"kind": "b_qty", "key": key}))
            choices.append((f"移除：{item['name']}",
                            {"kind": "b_remove", "key": key}))
        if chosen:
            choices.append(("就选这些，继续", {"kind": "b_pick_done"}))
        else:
            choices.append(("都不选，停止", {"kind": "b_stop"}))
        lines = []
        if note:
            lines.append(note)
        if self.b.get("edit"):
            lines.append("原来等待的确认/验证已安全退出，原动作没有提交；"
                         "可以继续修改尚未采用的方案。")
        if items:
            lines.append("已选商品：")
            for item in items:
                lines.append(f"· {item['name']} ×{item['quantity']}（单价 "
                             f"{yuan(item['unit_price_fen'])} 元，小计 "
                             f"{yuan(item['amount_fen'])} 元）")
            lines.append(f"合计 {yuan(self._total(items))} 元。")
        else:
            lines.append("已选：（还没有）")
        lines.append("还要添加商品吗？输入数量可调整刚选的商品（如 2），也可选"
                     "“改数量/移除”；蛋糕已自己买好这类说明，选"
                     "“就选这些”跳过即可。")
        return "\n".join(lines), choices

    def _ask_adopt(self, trusted):
        PersonalBudget(self.entry, self.state).check_freeze_room(trusted)
        items = self._chosen_items()
        total = self._total(items)
        delivery = (f"受控配送引用 {self.b['delivery_ref'][:8]}…（原文只走专用入口）"
                    if self.b["delivery_ref"] else "无配送（到店/自取类）")
        lines = [f"预算上限 {yuan(self.b['budget_limit_fen'])} 元；",
                 f"送达到 {self.b['deliver_by']} 前；{delivery}；",
                 "商品方案："]
        for item in items:
            lines.append(f"· {item['name']} ×{item['quantity']}：单价 "
                         f"{yuan(item['unit_price_fen'])} 元，小计 "
                         f"{yuan(item['amount_fen'])} 元")
        lines.append(f"付款账户：{self.b['payer'] or '待定'}。")
        lines.append(f"商品合计 {yuan(total)} 元，将按预算上限一次性冻结 "
                     f"{yuan(self.b['budget_limit_fen'])} 元，未消费部分结束时退回。")
        personal = self.state.get("personal_budget", {})
        if personal.get("view"):
            view = personal["view"]
            lines.append(f"个人预算限额 {yuan(view['personal_limit_fen'])} 元，账单已用 {yuan(view['used_fen'])} 元，"
                f"个人剩余 {money(view['remaining_fen'])} 元；另有未结占用 {yuan(personal.get('occupied_fen', 0))} 元、"
                f"尚未反映到本次账单的已核实消费 {yuan(personal.get('gap_fen', 0))} 元。")
        lines.append("商品方案采用不等于个人预算采用或资金授权；每一步仍会单独确认，"
                     "冻结确认里会写明结束时只退未消费部分。")
        return self._ask(trusted, "\n".join(lines),
                         [("调整数量或移除商品", {"kind": "b_edit_basket"}),
                          ("采用并开始办理", {"kind": "b_adopt"}),
                          ("取消，不办理", {"kind": "b_stop"})])

    # ------------------------------------------------------- edit input (08)

    def _ask_edit(self, trusted, note=None):
        prompt, choices = self.edit_menu(note)
        return self._ask(trusted, prompt, choices)

    def edit_menu(self, note=None):
        """The controlled edit input: recomputed plan plus unsubmitted targets."""
        rows = self._display_rows()
        editable = self._editable_rows()
        lines = []
        if note:
            lines.append(note)
        lines.append("原来等待的确认/验证已安全退出，原动作没有提交；"
                     "只调整尚未成单且没有在途的部分。")
        if rows:
            lines.append("当前方案：")
            for item in rows:
                lines.append(f"· {item['name']} ×{item['quantity']}：单价 "
                             f"{yuan(item['unit_price_fen'])} 元，小计 "
                             f"{yuan(item['amount_fen'])} 元")
            cap = ((self.b.get("freeze") or {}).get("amount_fen")
                   or self.b["budget_limit_fen"])
            lines.append(f"合计 {yuan(self._plan_total(rows))} 元（原上限 {yuan(cap)} 元）；"
                         f"付款账户 {self.b['payer'] or '待定'}。")
        else:
            lines.append("当前方案中没有商品。")
        facts = [self._facts(item) for item in rows]
        facts = [line for line in facts if line]
        if facts:
            lines.append("已办事实（不可改写）：")
            lines.extend(facts)
        choices = []
        for item in editable:
            key = item_key(item)
            choices.append((f"改数量：{item['name']}（当前 {item['quantity']} 件）",
                            {"kind": "b_edit_qty", "key": key}))
            choices.append((f"移除：{item['name']}",
                            {"kind": "b_edit_remove", "key": key}))
            choices.append((f"替换：{item['name']}",
                            {"kind": "b_edit_replace", "key": key}))
        choices.append(("再加一件商品", {"kind": "b_edit_add"}))
        choices.append(("按新方案继续", {"kind": "b_edit_done"}))
        choices.append(("停止办理", {"kind": "b_stop"}))
        return "\n".join(lines), choices

    def edit_begin(self, after: str, origin: dict) -> None:
        """Enter the controlled edit of the current birthday card (no writes).

        Before the freeze the chosen basket is the plan (the adopted rows were a
        projection and are rebuilt on re-adoption). After it, the plan rows are
        the facts: only rows with no order/capture attempt are editable.
        """
        if after == "freeze":
            self.b["orders"] = []
            self.b["phase"] = "pick"
            self._normalize_chosen()
        else:
            self.b["phase"] = "edit"
        self.b["pending"] = None
        self.b["holding"] = None
        self.b["edit"] = {"after": after, "origin": origin}
        self.b["edit_text_target"] = None
        self.b["edit_replace_target"] = None
        self.b["edit_add"] = False
        self._bump_revision()

    def _normalize_chosen(self) -> None:
        """Give every selected product a stable item id before the first attempt."""
        by_id = {p["product_id"]: p for p in self.b["products"]}
        converted = []
        for chosen in self.b["chosen"]:
            if not isinstance(chosen, str):
                converted.append(chosen)
                continue
            source = by_id.get(chosen)
            if source is not None:
                converted.append(self._new_item(source))
        self.b["chosen"] = converted

    def _ask_quantity(self, trusted, key, note=None):
        rows = self._editable_rows() if self.b.get("edit") else self._chosen_items()
        item = next((row for row in rows if item_key(row) == key), None)
        if item is None:
            raise ValueError("ITEM_NOT_EDITABLE")
        self.b["edit_text_target"] = key
        lines = [f"请输入「{item['name']}」的数量（正整数，如 2）："]
        if note:
            lines.append(note)
        return self._ask(trusted, "\n".join(lines),
                         [("取消改数量", {"kind": "b_edit_cancel"}),
                          ("停止本次安排", {"kind": "b_stop"})])

    def _set_quantity(self, key: str, quantity: int) -> None:
        row = self._row(key)
        if row is None:
            # A legacy checkpoint's bare product id becomes one stable item on
            # the first explicit quantity change; nothing else is rebuilt.
            chosen = self.b["chosen"]
            index = next((index for index, entry in enumerate(chosen)
                          if isinstance(entry, str) and entry == key), None)
            source = next((product for product in self.b["products"]
                           if product["product_id"] == key), None)
            if index is None or source is None:
                raise ValueError("ITEM_NOT_EDITABLE")
            chosen[index] = self._new_item(source, quantity=quantity)
            self._bump_revision()
            return
        row["quantity"] = quantity
        if self._post_freeze():
            row["amount_fen"] = int(row["unit_price_fen"]) * quantity
        self._bump_revision()

    def _menu_after_change(self, trusted, note=None):
        if self.b.get("edit") and self.b["phase"] == "edit":
            return self._ask_edit(trusted, note)
        return self._ask_pick(trusted, note)

    def _remove_row(self, trusted, key):
        if self._post_freeze():
            row = self._row(key)
            if row is None or row not in self._editable_rows():
                raise ValueError("ITEM_NOT_EDITABLE")
            self.b["edit_history"].append({
                "removed_item": {name: row.get(name) for name in (
                    "item_id", "product_id", "name", "quantity",
                    "unit_price_fen", "amount_fen")},
                "at_revision": self.state["plan_revision"]})
            self.b["orders"].remove(row)
        else:
            chosen = self.b["chosen"]
            index = next((index for index, entry in enumerate(chosen)
                          if (entry == key if isinstance(entry, str)
                              else item_key(entry) == key)), None)
            if index is None:
                raise ValueError("ITEM_NOT_EDITABLE")
            entry = chosen.pop(index)
            self.b["edit_history"].append({
                "removed_item": dict(entry) if isinstance(entry, dict)
                else {"product_id": entry},
                "at_revision": self.state["plan_revision"]})
        self._bump_revision()
        return self._menu_after_change(trusted)

    def _ask_products(self, trusted, replace_key=None, *,
                      choice_kind="b_edit_choose", failed_key=None):
        target = self._row(replace_key or failed_key)
        choices = []
        for product in self.b["products"]:
            label = (f"{product['merchant_name']}·{product['product_name']} "
                     f"{yuan(product['unit_price_fen'])} 元")
            choices.append((label, {"kind": choice_kind,
                                    "product_id": product["product_id"],
                                    "key": replace_key or failed_key}))
        choices.append(("取消", {"kind": "b_edit_cancel"}))
        if failed_key is not None:
            choices[-1] = ("取消", {"kind": "b_failed_cancel", "key": failed_key})
            prompt = (f"请选择用来替代「{target['name']}」的商品"
                      "（新执行项、新确认；不会复用原失败尝试）：")
        elif target is not None:
            prompt = (f"请选择用来替换「{target['name']}」的商品"
                      "（新商品会生成新的执行项，不复用旧订单或付款）：")
        else:
            prompt = "请选择要加入方案的商品（会生成新的执行项）："
        return self._ask(trusted, prompt, choices)

    def _failed_choose(self, trusted, picked):
        """The second basis: one new item after a verified no-order failure."""
        if not self._post_freeze() or not self.b.get("verified_failures"):
            raise ValueError("INVALID_OPTION")
        product = next((row for row in self.b["products"]
                        if row["product_id"] == picked["product_id"]), None)
        if product is None:
            raise ValueError("INVALID_OPTION")
        committed = self._plan_total(self.b["orders"])
        cap = int((self.b.get("freeze") or {}).get("amount_fen") or 0)
        if cap and committed + product["unit_price_fen"] > cap:
            return self._ask(
                trusted,
                f"剩余冻结不足以加入「{product['product_name']}」；"
                "不能自动追加冻结、换账户或提高上限。",
                [("跳过这件", {"kind": "b_skip_item", "key": picked["key"]}),
                 ("停止剩余办理", {"kind": "b_stop"})])
        self.b["orders"].append(self._new_plan_row(product))
        self._bump_revision()
        return self._run_next_order(trusted)

    def _new_plan_row(self, product: dict) -> dict:
        return {**self._new_item(product), "order": None, "capture": None,
                "order_id": None, "transaction_id": None}

    def _edit_choose(self, trusted, picked):
        product = next((row for row in self.b["products"]
                        if row["product_id"] == picked["product_id"]), None)
        if product is None:
            raise ValueError("INVALID_OPTION")
        replace_key = picked.get("key")
        new_item = self._new_item(product)
        if replace_key:
            if self._post_freeze():
                old = self._row(replace_key)
                if old is None or old not in self._editable_rows():
                    raise ValueError("ITEM_NOT_EDITABLE")
                index = self.b["orders"].index(old)
                self.b["edit_history"].append({
                    "replaced_item": {name: old.get(name) for name in (
                        "item_id", "product_id", "name", "quantity",
                        "unit_price_fen", "amount_fen")},
                    "by_item_id": new_item["item_id"],
                    "at_revision": self.state["plan_revision"]})
                self.b["orders"][index] = self._new_plan_row(product)
            else:
                chosen = self.b["chosen"]
                index = next((index for index, entry in enumerate(chosen)
                              if not isinstance(entry, str)
                              and item_key(entry) == replace_key), None)
                if index is None:
                    raise ValueError("ITEM_NOT_EDITABLE")
                self.b["edit_history"].append({
                    "replaced_item": dict(chosen[index]),
                    "by_item_id": new_item["item_id"],
                    "at_revision": self.state["plan_revision"]})
                chosen[index] = new_item
        elif self._post_freeze():
            committed = self._plan_total(self.b["orders"])
            cap = int((self.b.get("freeze") or {}).get("amount_fen") or 0)
            if cap and committed + new_item["amount_fen"] > cap:
                return self._ask_edit(
                    trusted,
                    f"剩余冻结不足以加入「{product['product_name']}」；"
                    "不能自动追加冻结、换账户或提高上限。请调整方案。")
            self.b["orders"].append(self._new_plan_row(product))
        else:
            self.b["chosen"].append(new_item)
        self.b["edit_replace_target"] = None
        self.b["edit_add"] = False
        self._bump_revision()
        return self._menu_after_change(trusted)

    def _apply_edit(self, trusted, picked):
        kind = picked.get("kind")
        if kind == "b_edit_cancel":
            # Cancel a quantity/product sub-question without changing anything.
            self.b["edit_text_target"] = None
            self.b["edit_replace_target"] = None
            self.b["edit_add"] = False
            if self.b.get("edit") and self.b["phase"] == "edit":
                return self._ask_edit(trusted)
            return self._ask_pick(trusted)
        if not self.b.get("edit"):
            # Old cards and old option ids never name an edit action.
            raise ValueError("INVALID_OPTION")
        if kind == "b_edit_qty":
            return self._ask_quantity(trusted, picked["key"])
        if kind == "b_edit_remove":
            return self._remove_row(trusted, picked["key"])
        if kind == "b_edit_replace":
            self.b["edit_replace_target"] = picked["key"]
            return self._ask_products(trusted, replace_key=picked["key"])
        if kind == "b_edit_add":
            self.b["edit_replace_target"] = None
            self.b["edit_add"] = True
            return self._ask_products(trusted, replace_key=None)
        if kind == "b_edit_choose":
            return self._edit_choose(trusted, picked)
        if kind == "b_edit_done":
            return self._finish_edit(trusted)
        raise ValueError("INVALID_OPTION")

    def _finish_edit(self, trusted):
        edit = self.b.get("edit") or {}
        rows = self._display_rows()
        facts = [self._facts(row) for row in rows if self._facts(row)]
        if not rows and not facts:
            return self._ask_edit(
                trusted, "方案中没有可办理的商品；不能冻结或下单。"
                         "请加回商品或停止办理。")
        total = self._plan_total(rows)
        cap = ((self.b.get("freeze") or {}).get("amount_fen")
               or self.b["budget_limit_fen"])
        if cap is not None and total > cap:
            return self._ask_edit(
                trusted,
                f"新方案合计 {yuan(total)} 元，超过原上限 {yuan(cap)} 元；"
                "不能自动追加预算或重置上限。请调整后再继续。")
        after = edit.get("after") or "orders"
        self.b["edit"] = None
        self.b["edit_text_target"] = None
        self.b["edit_replace_target"] = None
        self.b["edit_add"] = False
        self._bump_revision()
        if after == "freeze":
            self.b["phase"] = "adopt"
            return self._ask_adopt(trusted)
        self.b["phase"] = "orders"
        return self._resume_orders(trusted)

    def _resume_orders(self, trusted):
        """Continue the ordered part: an unpaid created order first, then new ones."""
        pending = next((row for row in self.b["orders"]
                        if row.get("order") == "completed" and row.get("order_id")
                        and row.get("capture") is None), None)
        if pending is not None:
            return self._run_capture(trusted, pending)
        return self._run_next_order(trusted)

    def _plan_rows_from_chosen(self) -> list[dict]:
        rows = []
        for item in self._chosen_items():
            row = {**self._fact(item), "quantity": item["quantity"],
                   "unit_price_fen": item["unit_price_fen"],
                   "amount_fen": item["amount_fen"],
                   "order": None, "capture": None, "order_id": None,
                   "transaction_id": None}
            if item.get("item_id") is None:
                row.pop("item_id", None)
            rows.append(row)
        return rows

    # ------------------------------------------------------------------ choices

    def _held_or_allowed(self, kind: str) -> bool:
        return self.b.get("holding") in (None, False) or kind in {
            "b_retry_query", "b_stop"}

    def _replay_holding(self, trusted):
        saved = self.state.get("result") or {}
        if saved.get("status") in ("waiting_input", "waiting_approval"):
            return ModuleResult.model_validate(saved).model_copy(
                update={"run_id": trusted.run_id})
        return self._holding_view(trusted)

    def apply(self, trusted, picked: dict):
        kind = picked["kind"]
        entry, state = self.entry, self.state
        if not self._held_or_allowed(kind):
            # An unknown write holds the flow; only verify-the-original or a
            # full stop may move it (B1).
            return self._replay_holding(trusted)
        if kind == "b_stop":
            return self.stop(trusted, "user_cancelled")
        if kind in _EDIT_KINDS:
            return self._apply_edit(trusted, picked)
        if kind == "b_failed_replace":
            return self._ask_products(trusted, failed_key=picked["key"],
                                      choice_kind="b_failed_choose")
        if kind == "b_failed_choose":
            return self._failed_choose(trusted, picked)
        if kind == "b_failed_cancel":
            item = self._order(picked["key"])
            return self._order_failed(trusted, item,
                                      item.get("order_operation_id") or "")
        if kind == "b_retry_products":
            self.b["products"] = []
            return self.advance(trusted)
        if kind == "b_pick":
            product = next((row for row in self.b["products"]
                            if row["product_id"] == picked["product_id"]), None)
            if product is None:
                raise ValueError("INVALID_OPTION")
            self.b["chosen"].append(self._new_item(product))
            self._bump_revision()
            return self._ask_pick(trusted)
        if kind == "b_qty":
            return self._ask_quantity(trusted, picked["key"])
        if kind == "b_remove":
            return self._remove_row(trusted, picked["key"])
        if kind == "b_pick_done":
            if not self.b["chosen"]:
                return self._ask_pick(trusted)
            total = self._total(self._chosen_items())
            if total > self.b["budget_limit_fen"]:
                # Over budget stops before any bank write (XL-B03 / M2).
                return self._ask(trusted,
                                 f"所选商品合计 {yuan(total)} 元，超过预算上限 "
                                 f"{yuan(self.b['budget_limit_fen'])} 元。"
                                 "请去掉部分商品或停止。",
                                 [("去掉些商品重新选", {"kind": "b_repick"}),
                                  ("停止本次安排", {"kind": "b_stop"})])
            self.b["phase"] = "adopt"
            return self._ask_adopt(trusted)
        if kind == "b_edit_basket":
            if self._post_freeze():
                raise ValueError("INVALID_OPTION")
            self.b["phase"] = "pick"
            return self._ask_pick(trusted)
        if kind == "b_repick":
            self.b["chosen"] = []
            self.b["phase"] = "pick"
            return self._ask_pick(trusted)
        if kind == "b_adopt":
            # Adopting the edited plan ends the edit input; the new plan is the
            # ordinary flow again (nothing was frozen by editing itself).
            self.b["edit"] = None
            self.b["edit_text_target"] = None
            self.b["edit_replace_target"] = None
            self.b["edit_add"] = False
            self.b["orders"] = self._plan_rows_from_chosen()
            return self._d1_check_then_freeze(trusted)
        if kind == "b_price_ok":
            item = self._order(picked["key"])
            unit_price_fen = int(picked["unit_price_fen"])
            fresh_total = unit_price_fen * int(item["quantity"])
            frozen = self.b["freeze"]
            spent = sum(o.get("amount_fen", 0) for o in self.b["orders"]
                        if o.get("capture") == "completed")
            if spent + fresh_total > frozen["amount_fen"]:
                return self._ask(trusted,
                                 f"新价 {yuan(fresh_total)} 元会超过已冻结的 "
                                 f"{yuan(frozen['amount_fen'])} 元"
                                 "（已付款部分保持不变），不能继续办理这件。",
                                 [("跳过这件，继续其他", {"kind": "b_skip_item",
                                                        "key": item_key(item)}),
                                  ("停止剩余办理", {"kind": "b_stop"})])
            item["unit_price_fen"] = unit_price_fen
            item["amount_fen"] = fresh_total
            return self._submit(trusted, ("order", item_key(item)))
        if kind == "b_skip_item":
            key = picked.get("key") or picked.get("product_id")
            item = self._order(key)
            item["order"] = "skipped"
            return self._run_next_order(trusted, skip=key)
        if kind == "b_retry_query":
            return self._requery(trusted)
        raise ValueError("INVALID_OPTION")

    def apply_text(self, trusted, text: str):
        from .pension import parse_amount_fen
        personal = PersonalBudget(self.entry, self.state).text(trusted, text)
        if personal is not None:
            return personal
        if self.b.get("holding"):
            return self._replay_holding(trusted)  # B1: text never bypasses
        target = self.b.get("edit_text_target")
        if target is not None:
            # A server-named item is waiting for one explicit integer; an
            # illegal value re-asks and changes nothing (Q01).
            quantity = positive_quantity(text)
            if quantity is None:
                return self._ask_quantity(
                    trusted, target, note="数量需为正整数（至少 1 件）。")
            self.b["edit_text_target"] = None
            self._set_quantity(target, quantity)
            return self._menu_after_change(trusted)
        phase = self.b["phase"]
        if phase == "pick":
            quantity = positive_quantity(text)
            items = self._chosen_items()
            if quantity is None:
                return self._ask_pick(trusted, note="数量需为正整数（至少 1 件）。")
            if not items:
                return self._ask_pick(trusted, note="还没有选商品，先选一件再输入数量。")
            self._set_quantity(item_key(items[-1]), quantity)
            return self._ask_pick(trusted)
        if phase == "budget":
            fen = parse_amount_fen(text)
            if fen is None or fen <= 0:
                return self._ask_budget(trusted)
            self.b["budget_limit_fen"] = fen
            self.b["phase"] = "date"
            return self._phase_view(trusted)
        if phase == "date":
            candidate = text.strip()
            if not _DATE.match(candidate):
                return self._ask_date(trusted)
            try:
                datetime.fromisoformat(candidate)
            except ValueError:
                return self._ask_date(trusted)
            self.b["deliver_by"] = candidate
            self.b["phase"] = "delivery"
            return self._ask_delivery(trusted)
        if phase == "delivery":
            ref = text.strip()
            if not _REF.match(ref):
                return self._ask_delivery(trusted)
            detail = self.entry.harness.application.get_controlled_detail(
                self.state["actor"][0], self.state["actor"][1], ref,
                task_id=self.state["actor"][2])
            if detail is None or detail.kind != "delivery":
                result = self._ask_delivery(trusted)
                return result.model_copy(update={"message":
                    "查不到对应的配送信息，请通过专用表单重新提交，或停止本次安排。"})
            self.b["delivery_ref"] = ref
            self.b["phase"] = "pick"
            return self._ask_pick(trusted)
        return self._phase_view(trusted)

    # ------------------------------------------------------------------ freeze

    def _d1_check_then_freeze(self, trusted):
        entry = self.entry
        active = entry.harness.application.get_active_arrangement(
            self.state["actor"][0], self.state["actor"][1], self.b["payer"])
        if active is not None and active.record.source_task_id not in (
                entry.harness.application.task_lineage(
                    self.state["actor"][0], self.state["actor"][1],
                    self.state["actor"][2])):
            return self._ask(trusted,
                             "这张账户已有正在办理的资金安排（养老金等）。生日办理需先完成、"
                             "调整或结束原安排；查询不受影响。",
                             [("停止本次安排", {"kind": "b_stop"})])
        self.b["phase"] = "freeze"
        return self._run_freeze(trusted)

    def _run_freeze(self, trusted):
        PersonalBudget(self.entry, self.state).check_freeze_room(trusted)
        answer = self.ports.freeze_check(trusted, self._plan())
        return self._gate(trusted, answer, ("freeze", None))

    def _gate(self, trusted, answer, target):
        entry = self.entry
        if answer.decision in (SecurityDecisionCode.REQUIRE_CONFIRMATION,
                               SecurityDecisionCode.REQUIRE_VERIFICATION):
            self.b["pending"] = {"target": target, "operation_id": answer.operation_id,
                                 "interaction": answer.interaction.model_dump(mode="json")
                                 if answer.interaction else None}
            self.b["holding"] = "gate"
            state = self.state
            state["waiting"] = "gate"
            return ModuleResult(
                task_id=trusted.task_id, run_id=trusted.run_id,
                status=TaskStatus.WAITING_APPROVAL,
                data=entry._view_data(self.state, answer.interaction.prompt
                                      if answer.interaction else "请确认。"),
                message=answer.interaction.prompt if answer.interaction else "请确认。",
                interaction=answer.interaction,
                error=None, allowed_actions=["confirm", "cancel"],
                recovery_required=False, recovery_reason=None)
        if answer.decision == SecurityDecisionCode.ALLOW:
            if target[0] == "freeze":
                # The §3.5 authorization only exists through an approved
                # clause-bearing confirmation; an ALLOW shortcut would strand
                # the frozen funds (m3), so it is refused fail-closed.
                return self._blocked_stop(trusted, "FREEZE_WITHOUT_CLAUSE")
            return self._submit(trusted, target)
        return self._blocked_stop(trusted, answer.reason_code)

    def answer_gate(self, trusted, response: dict):
        if response.get("choice") == "cancel" or response.get("cancel") is True:
            return self.stop(trusted, "user_cancelled")
        pending = self.b.get("pending")
        if not pending:
            return self.advance(trusted)
        # The pending target stays until the write settles: a step-up
        # verification (verify_wait) sits between the approval and the bank.
        self.b["holding"] = None
        target = pending["target"]
        if target[0] == "freeze" and pending.get("interaction"):
            ref = pending["interaction"].get("record_ref")
            if ref:
                # An approved clause-bearing freeze confirmation grants the
                # limited-release authorization before the write runs.
                self.ports.grant_release(trusted, self._plan(), ref)
        return self._submit(trusted, target)

    def resume_gate(self, trusted):
        """Continue one write after its step-up verification passed.

        The verification service answers on the generic code endpoint; the
        platform then resumes this task and the same ports resubmit under the
        now-complete gate (confirmation approved plus challenge passed).
        """
        pending = self.b.get("pending")
        if not pending or self.b.get("holding") != "verify":
            return self.advance(trusted)
        self.b["holding"] = None
        return self._submit(trusted, pending["target"])

    def _pending_view(self, trusted):
        pending = self.b["pending"]
        if pending.get("verify"):
            return self._verify_wait(trusted, WriteOutcome(executed=False, state="verify_wait",
                verify=InteractionRequest.model_validate(pending["verify"])))
        self.b["holding"] = "gate"
        return self._holding_view(trusted)

    def _verify_wait(self, trusted, outcome) -> ModuleResult:
        """Hold one approved write at its step-up challenge; nothing moved."""
        self.b["holding"] = "verify"
        self.b["pending"] = {**(self.b.get("pending") or {}),
                             "verify": outcome.verify.model_dump(mode="json")}
        return ModuleResult(
            task_id=trusted.task_id, run_id=trusted.run_id,
            status=TaskStatus.WAITING_APPROVAL,
            data=self.entry._view_data(self.state, outcome.verify.prompt),
            message=outcome.verify.prompt,
            interaction=outcome.verify, error=None,
            allowed_actions=["verify", "cancel"], recovery_required=False,
            recovery_reason=None)

    def _submit(self, trusted, target):
        kind, item_id = target
        budget = PersonalBudget(self.entry, self.state)
        budget.refresh(trusted)
        if kind == "freeze":
            budget.reserve(trusted)
        plan_data = self._plan()
        if kind == "freeze":
            outcome = self.ports.freeze_execute(trusted, plan_data)
            if outcome.state == "verify_wait":
                self.b["freeze_submission"] = "not_submitted_verification"
                self.entry._save(trusted, None, self.state)
                return self._verify_wait(trusted, outcome)
            self._remember_write(kind, item_id, outcome)
            self.b["pending"] = None
            record = {"operation_id": outcome.operation_id, "amount_fen":
                      plan_data.freeze_amount_fen, "status": outcome.state,
                      "freeze_id": None, "authorization": "granted"}
            self.b["freeze"] = record
            if outcome.state == "unknown":
                budget.frozen(record)
            elif outcome.state == "failed" and not outcome.executed:
                budget.close()
            if outcome.state == "completed" and outcome.result is not None:
                record["freeze_id"] = getattr(outcome.result.receipt, "freeze_id", None) \
                    if hasattr(outcome.result, "receipt") else None
                if not record["freeze_id"]:
                    record["freeze_id"] = self.ports.bind_freeze(
                        trusted, plan_data, record["operation_id"])
                self._register_commitment(record)
                self.b["phase"] = "orders"
                return self._run_next_order(trusted)
            if outcome.state == "unknown":
                self.b["holding"] = "unknown_freeze"
                return self._holding_view(trusted)
            return self._failed_stop(trusted)
        if kind == "order":
            item = self._order(item_id)
            outcome = self.ports.order_execute(trusted, plan_data, item)
            if outcome.state == "verify_wait":
                return self._verify_wait(trusted, outcome)
            self._remember_write(kind, item_key(item), outcome)
            self.b["pending"] = None
            item["order_operation_id"] = outcome.operation_id
            if outcome.state == "completed" and outcome.result is not None:
                order_view = getattr(outcome.result, "order", None) or getattr(
                    getattr(outcome.result, "receipt", None), "order", None)
                item["order_id"] = getattr(order_view, "order_id", None)
                if not item["order_id"] and isinstance(order_view, dict):
                    item["order_id"] = order_view.get("order_id")
                item["order"] = "completed"
                return self._run_capture(trusted, item)
            if outcome.state == "unknown":
                item["order"] = "unknown"
                budget.unknown(outcome.operation_id)
                self.b["holding"] = "unknown_order"
                return self._holding_view(trusted)
            item["order"] = "failed"
            return self._order_failed(trusted, item, outcome.operation_id)
        if kind == "capture":
            item = self._order(item_id)
            outcome = self.ports.capture_execute(trusted, plan_data, item,
                                                 item.get("order_id"))
            if outcome.state == "verify_wait":
                return self._verify_wait(trusted, outcome)
            self._remember_write(kind, item_key(item), outcome)
            self.b["pending"] = None
            item["capture_operation_id"] = outcome.operation_id
            if outcome.state == "completed" and outcome.result is not None:
                receipt = getattr(outcome.result, "receipt", None)
                item["capture"] = "completed"
                item["transaction_id"] = getattr(receipt, "transaction_id", None)
                self._consume_commitment(item)
                return self._run_next_order(trusted, skip=item_key(item))
            if outcome.state == "unknown":
                item["capture"] = "unknown"
                budget.unknown(outcome.operation_id)
                self.b["holding"] = "unknown_capture"
                return self._holding_view(trusted)
            item["capture"] = "failed"
            return self._run_next_order(trusted, skip=item_key(item))
        raise ValueError("INVALID_TARGET")

    # ------------------------------------------------------------------ orders

    def _run_next_order(self, trusted, skip=None):
        pending = [o for o in self.b["orders"]
                   if o.get("order") is None and item_key(o) != skip]
        if not pending:
            paid_any = any(o.get("capture") == "completed" for o in self.b["orders"])
            if paid_any or any(o.get("order") == "completed" for o in self.b["orders"]):
                # settled purchases → finalize under the limited authorization
                self.b["phase"] = "finalize"
                return self._finalize(trusted)
            return self._failed_stop(trusted)
        item = pending[0]
        PersonalBudget(self.entry, self.state).refresh(trusted)
        # A changed or unavailable quote surfaces BEFORE its confirmation is
        # asked for; an old confirmation never approves new money (B03).
        fresh = self._refresh_price(trusted, item)
        if fresh is not None:
            return fresh
        answer = self.ports.order_check(trusted, self._plan(), item)
        return self._gate(trusted, answer, ("order", item_key(item)))

    def _run_capture(self, trusted, item):
        PersonalBudget(self.entry, self.state).refresh(trusted)
        answer = self.ports.capture_check(trusted, self._plan(), item,
                                          item.get("order_id"))
        return self._gate(trusted, answer, ("capture", item_key(item)))

    def _refresh_price(self, trusted, item):
        found = self.ports.products(trusted, ListProductsInput(purpose="birthday"))
        data = getattr(found, "data", None)
        if data is None:
            # Fail closed: without a fresh quote the order does not run (m1).
            return self._ask(trusted,
                             f"下单前核实 {item['name']} 的最新报价时暂时查不到，"
                             "这件先不办理。可稍后重试或停止。",
                             [("稍后再试这件", {"kind": "b_retry_products"}),
                              ("停止剩余办理", {"kind": "b_stop"})])
        quantity = int(item.get("quantity") or 1)
        unit_price_fen = int(item.get("unit_price_fen") or item["amount_fen"])
        for product in data.products:
            if product.product_id == item["product_id"]:
                fresh = product.unit_price_fen
                if fresh * quantity != item["amount_fen"]:
                    # A changed quote never rides an old confirmation; the line
                    # subtotal is rebuilt from the new unit price x quantity.
                    fresh_total = fresh * quantity
                    return self._ask(
                        trusted,
                        f"{item['name']} 的价格已从 {yuan(unit_price_fen)} 元变为 "
                        f"{yuan(fresh)} 元。旧确认不批准新金额；请重新选择。",
                        [(f"按新价 {yuan(fresh_total)} 元继续", {"kind": "b_price_ok",
                                                               "key": item_key(item),
                                                               "unit_price_fen": fresh}),
                         ("停止剩余办理", {"kind": "b_stop"})])
                return None
        return self._ask(trusted, f"{item['name']} 目前不可购买。可停止或跳过。",
                         [("跳过这件，继续其他", {"kind": "b_skip_item",
                                                "key": item_key(item)}),
                          ("停止剩余办理", {"kind": "b_stop"})])

    def _verified_no_order(self, trusted, operation_id) -> bool:
        """Re-read the original operation: only an explicit failure with no
        order receipt is a defensible basis for a replacement (Q10)."""
        if not operation_id:
            return False
        try:
            outcome = self.ports.requery(trusted, self._plan(), "order",
                                         operation_id)
        except Exception:  # noqa: BLE001 - an unprovable failure is not editable
            return False
        return outcome is not None and outcome.state == "failed"

    def _order_failed(self, trusted, item, operation_id):
        """One explicit create-order failure: keep the fact, offer the second basis.

        Only an operation query that re-verifies "failed with no order" supports
        a replacement; without that proof the flow keeps its old behaviour (the
        failed row stays unsubmitted and the remaining items continue), never
        inventing a replacement from an unverified outcome.
        """
        key = item_key(item)
        if not self._verified_no_order(trusted, operation_id):
            return self._run_next_order(trusted, skip=key)
        self.b["verified_failures"][operation_id] = {
            "action": "bank.create_order", "operation_id": operation_id,
            "item_id": key, "state": "failed", "no_order": True,
        }
        return self._ask(
            trusted,
            f"{item['name']} 下单没有办成：银行已明确失败，且已核实没有生成订单、"
            "也没有在途提交。原失败记录保留；可以换一件（新的执行项、新的确认），"
            "或跳过/停止。",
            [("换一件继续", {"kind": "b_failed_replace", "key": key}),
             ("跳过这件", {"kind": "b_skip_item", "key": key}),
             ("停止剩余办理", {"kind": "b_stop"})])

    # ------------------------------------------------------------------ unknown

    def _holding_view(self, trusted):
        kind = self.b.get("holding")
        prompts = {
            "gate": None,  # handled by answer_gate
            "unknown_freeze": ("冻结结果还待核实（原编号保留，不重复冻结）；"
                               "核实前不会下单。"),
            "unknown_order": ("下单结果还待核实（原编号保留，不重复下单）；"
                              "核实前不付款。"),
            "unknown_capture": ("付款结果还待核实（原编号保留，不重复扣款）；"
                                "核实前不继续、也不抢先释放。"),
        }
        if kind == "gate":
            pending = self.b.get("pending") or {}
            interaction = pending.get("interaction") or {}
            return ModuleResult(
                task_id=trusted.task_id, run_id=trusted.run_id,
                status=TaskStatus.WAITING_APPROVAL,
                data=self.entry._view_data(self.state, interaction.get("prompt", "请确认。")),
                message=interaction.get("prompt", "请确认。"),
                interaction=InteractionRequest.model_validate(interaction)
                if interaction else None,
                error=None, allowed_actions=["confirm", "cancel"],
                recovery_required=False, recovery_reason=None)
        prompt = prompts.get(kind) or "结果待核实。"
        choices = [("核实原操作后再试", {"kind": "b_retry_query"}),
                   ("停止新增办理，按原授权收尾", {"kind": "b_stop"})]
        return self._ask(trusted, prompt, choices)

    def _requery(self, trusted):
        kind = self.b.get("holding")
        if kind == "unknown_freeze":
            freeze = self.b["freeze"]
            freeze_id = self.ports.bind_freeze(trusted, self._plan(),
                                               freeze["operation_id"])
            if freeze_id:
                # The binding itself verifies this original freeze exists.
                # A second receipt read may be unavailable; that cannot leave
                # its identity unknown forever or invent an unreturned amount.
                self.b.setdefault("write_facts", {}).setdefault("freeze", {}).update(
                    status="completed", operation_id=freeze["operation_id"],
                    result_ref=freeze_id)
                outcome = self.ports.requery(trusted, self._plan(), "freeze",
                                              freeze["operation_id"])
                if outcome is not None and outcome.state == "completed":
                    self._remember_write("freeze", None, outcome)
                freeze["freeze_id"] = freeze_id
                freeze["status"] = "completed"
                self._register_commitment(freeze)
                self.b["holding"] = None
                if self.b.get("stop_reason"):
                    return self._finalize(trusted)
                self.b["phase"] = "orders"
                return self._run_next_order(trusted)
            return self._holding_view(trusted)
        if self.b["holding"] in ("unknown_order", "unknown_capture"):
            holding_kind = self.b["holding"].split("_")[1]
            # The item that holds the unknown, never a positional guess; the
            # re-query carries its original operation id (B2).
            if holding_kind == "order":
                item = next((o for o in self.b["orders"] if o.get("order") == "unknown"),
                            None)
                operation_id = (item or {}).get("order_operation_id")
            else:
                item = next((o for o in self.b["orders"] if o.get("capture") == "unknown"),
                            None)
                operation_id = (item or {}).get("capture_operation_id")
            if item is None or not operation_id:
                return self._holding_view(trusted)
            outcome = self.ports.requery(trusted, self._plan(), holding_kind,
                                          operation_id)
            if outcome is not None and outcome.state == "completed":
                self._remember_write(holding_kind, item_key(item), outcome)
                if holding_kind == "order":
                    item["order"] = "completed"
                    item["order_id"] = self.b["write_facts"][
                        f"order:{item_key(item)}"].get("order_id")
                    self.b["holding"] = None
                    if self.b.get("stop_reason"):
                        return self._finalize(trusted)
                    return self._run_capture(trusted, item)
                item["capture"] = "completed"
                receipt = getattr(outcome.result, "receipt", None)
                item["transaction_id"] = getattr(receipt, "transaction_id", None)
                self._consume_commitment(item)
                self.b["holding"] = None
                if self.b.get("stop_reason"):
                    return self._finalize(trusted)
                return self._run_next_order(trusted, skip=item_key(item))
            return self._holding_view(trusted)
        return self._holding_view(trusted)

    # ------------------------------------------------------------------ budget seam

    def _register_commitment(self, freeze: dict) -> None:
        PersonalBudget(self.entry, self.state).frozen(freeze)

    def _own_commitment(self):
        return PersonalBudget(self.entry, self.state).own()

    def _consume_commitment(self, item: dict) -> None:
        PersonalBudget(self.entry, self.state).consume(item)

    def _close_commitment(self) -> None:
        PersonalBudget(self.entry, self.state).close()

    # ------------------------------------------------------------------ ending

    def _blocked_stop(self, trusted, reason_code):
        self.b["stop_reason"] = "security_blocked"
        self.b["blocked_reason"] = reason_code
        return self._finalize(trusted)

    def _failed_stop(self, trusted):
        self.b["stop_reason"] = "business_failure"
        return self._finalize(trusted)

    def stop(self, trusted, reason):
        self.b["stop_reason"] = reason
        return self._finalize(trusted)

    def _finalize(self, trusted):
        self.b["phase"] = "finalize"
        if self.b.get("stop_reason"):
            self.state["stop_reason"] = self.b["stop_reason"]
        if self.b.get("holding") in ("gate", "verify"):
            self.b["holding"] = None
            self.b["pending"] = None
        freeze = self.b.get("freeze")
        if not freeze:
            budget = PersonalBudget(self.entry, self.state)
            hold = budget.own()
            if hold and self.b.get("freeze_submission") == "intent":
                self.b["freeze"] = {"operation_id": str(hold.operation_ids[0]),
                    "amount_fen": hold.committed_fen, "status": "unknown", "freeze_id": None}
                self.b["holding"] = "unknown_freeze"
                return self._finalize(trusted)
            if hold:
                budget.close()  # acknowledged verify_wait: the write was not submitted
            return self.entry._done(trusted, self.state, TaskStatus.CANCELLED,
                                    "已停止办理。本次没有冻结资金，也没有下单或付款。")
        unknown = self.b.get("holding") in (
            "unknown_freeze", "unknown_order", "unknown_capture", "unknown_release")
        if unknown:
            return self._ask(
                trusted,
                "已停止新增办理，资金仍待核实：原操作编号保留，核实后才能按限定授权收尾；"
                "不抢先释放、不换号重办。",
                [("核实原操作后收尾", {"kind": "b_retry_query"})])
        outcome = self.ports.finalize(trusted, self._plan(),
                                      self.b.get("stop_reason") or "completed")
        self.b["released"] = asdict(outcome)
        if outcome.status in ("released", "nothing_to_release") and outcome.remaining_fen != 0:
            return self.entry._view(trusted, self.state,
                "释放已有回复，但尚不能核实剩余冻结为零；占用保留，只继续原收尾核实。")
        if outcome.status in ("released", "nothing_to_release"):
            self._close_commitment()
        budget = PersonalBudget(self.entry, self.state)
        if budget.own() is not None:
            try:
                budget.refresh(trusted, for_write=False)  # never gates original closure
            except BudgetPending:
                budget.p["view"] = None
        lines = []
        for item in self.b["orders"]:
            quantity = int(item.get("quantity") or 1)
            name = item["name"] if quantity == 1 else f"{item['name']} ×{quantity}"
            amount = item["amount_fen"]
            if item.get("capture") == "completed":
                lines.append(f"{name}：订单已创建并已付款 {yuan(amount)} 元"
                             f"（交易 {str(item.get('transaction_id'))[:8]}…）。")
            elif item.get("order") == "completed":
                lines.append(f"{name}：订单已创建，未付款（{yuan(amount)} 元未扣）。")
            elif item.get("order") == "unknown":
                lines.append(f"{name}：下单结果此前未知，本次未重复下单。")
            elif item.get("order") == "failed":
                lines.append(f"{name}：下单未办成，未付款。")
        if outcome.status == "released":
            lines.append(f"冻结未消费部分已按限定授权释放 {yuan(outcome.released_amount_fen)} 元"
                         f"（原操作 {str(outcome.release_operation_id)[:8]}…）。")
        elif outcome.status == "nothing_to_release":
            lines.append("冻结已全部消费，无可释放余额。")
        elif outcome.status == "needs_attention":
            lines.append("释放结果待核实（原编号保留），暂不宣称已解冻。")
        else:
            reason = self.b.get("blocked_reason") or outcome.message or "blocked"
            lines.append(f"办理被安全侧阻止（{reason}），冻结保持原状。")
        lines.append("已付款项不退；以上是订单与资金事实，不代表商品已送达。")
        paid = any(o.get("capture") == "completed" for o in self.b["orders"])
        reason = self.b.get("stop_reason")
        if outcome.status in ("needs_attention", "blocked"):
            return self.entry._view(trusted, self.state, "\n".join(lines))
        if reason and reason != "completed":
            status = TaskStatus.PARTIALLY_SUCCEEDED if paid else TaskStatus.CANCELLED
            head = "部分完成，后续已停止：" if paid else "已停止办理。"
            return self.entry._done(trusted, self.state, status,
                                    head + "\n".join(lines))
        return self.entry._done(trusted, self.state, TaskStatus.SUCCEEDED,
                                "\n".join(lines))
