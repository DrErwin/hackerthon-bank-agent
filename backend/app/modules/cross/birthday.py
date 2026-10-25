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
from app.storage.application import BudgetOccupationExceededError
from app.contracts.common import SecurityDecisionCode, TaskStatus
from app.contracts.cross import BudgetRef
from app.contracts.cross import CrossScenario
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult

from . import plan
from .birthday_ports import BirthdayPlan
from .plan import money

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REF = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def yuan(fen) -> str:
    return money(int(fen or 0))


class BirthdayFlow:
    """Owns the birthday phases on top of the shared plan skeleton."""

    DEFAULTS = {
        "phase": "facts", "payer": None,
        "budget_limit_fen": None, "budget_id": None, "budget_version": 1,
        "deliver_by": None, "delivery_ref": None, "products": [],
        "chosen": [], "freeze": None, "orders": [],
        "pending": None, "holding": None, "commitment_id": None,
        "stop_reason": None, "released": None,
    }

    def __init__(self, entry, state: dict, ports):
        self.entry, self.state, self.ports = entry, state, ports
        data = state.get("birthday")
        if data is None:
            data = {}
            state["birthday"] = data
        for key, default in self.DEFAULTS.items():
            data.setdefault(key, default)
        self.b = data

    # ------------------------------------------------------------------ helpers

    def _plan_items(self) -> list[dict]:
        by_id = {p["product_id"]: p for p in self.b["products"]}
        rows = self.b["orders"] or [
            {"product_id": i["product_id"], "amount_fen": i["amount_fen"],
             "quantity": i.get("quantity", 1)} for i in self._chosen_items()]
        items = []
        for row in rows:
            source = by_id.get(row["product_id"], {})
            items.append({**source,
                          "product_id": row["product_id"],
                          "quantity": row.get("quantity", 1),
                          "amount_fen": row["amount_fen"],
                          "name": source.get("product_name", row.get("name"))})
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
        by_id = {p["product_id"]: p for p in self.b["products"]}
        items = []
        for pid in self.b["chosen"]:
            source = by_id.get(pid)
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

    def _order(self, product_id: str) -> dict:
        return next(o for o in self.b["orders"] if o["product_id"] == product_id)

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
        return self._phase_view(trusted)

    def _phase_view(self, trusted):
        handler = {
            "facts": self.advance,
            "budget": self._ask_budget, "date": self._ask_date,
            "delivery": self._ask_delivery, "pick": self._ask_pick,
            "adopt": self._ask_adopt, "freeze": self._run_freeze,
            "orders": self._run_next_order, "finalize": self._finalize,
        }[self.b["phase"]]
        return handler(trusted)

    # ------------------------------------------------------------------ asks

    def _ask_budget(self, trusted):
        return self._ask(trusted, "这次生日安排的预算上限是多少元？（可输入金额，如“500元”）",
                         [("停止本次安排", {"kind": "b_stop"})])

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
            update={"required_fields": ["delivery"]})})

    def _ask_pick(self, trusted):
        products = self.b["products"]
        choices = []
        for product in products:
            pid = product["product_id"]
            if pid in self.b["chosen"]:
                continue
            label = (f"{product['merchant_name']}·{product['product_name']} "
                     f"{yuan(product['unit_price_fen'])} 元")
            choices.append((label, {"kind": "b_pick", "product_id": pid}))
        if self.b["chosen"]:
            choices.append(("就选这些，继续", {"kind": "b_pick_done"}))
        else:
            choices.append(("都不选，停止", {"kind": "b_stop"}))
        chosen_names = "、".join(
            f"{p['product_name']}（{yuan(p['unit_price_fen'])}元）" for p in self._chosen_items())
        prompt = (f"已选：{chosen_names or '（还没有）'}；合计 "
                  f"{yuan(self._total(self._chosen_items()))} 元。"
                  "还要添加商品吗？蛋糕已自己买好这类说明，选“就选这些”跳过即可。")
        return self._ask(trusted, prompt, choices)

    def _ask_adopt(self, trusted):
        items = self._chosen_items()
        total = self._total(items)
        delivery = (f"受控配送引用 {self.b['delivery_ref'][:8]}…（原文只走专用入口）"
                    if self.b["delivery_ref"] else "无配送（到店/自取类）")
        lines = [f"预算上限 {yuan(self.b['budget_limit_fen'])} 元；",
                 f"送达到 {self.b['deliver_by']} 前；{delivery}；",
                 f"商品合计 {yuan(total)} 元，将按预算上限一次性冻结 "
                 f"{yuan(self.b['budget_limit_fen'])} 元，未消费部分结束时退回。"]
        lines.append("采用后开始办理：冻结→下单→按订单核销付款；每一步仍会单独确认，"
                     "冻结确认里会写明结束时只退未消费部分。")
        return self._ask(trusted, "\n".join(lines),
                         [("采用并开始办理", {"kind": "b_adopt"}),
                          ("取消，不办理", {"kind": "b_stop"})])

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
        if kind == "b_retry_products":
            self.b["products"] = []
            return self.advance(trusted)
        if kind == "b_pick":
            if picked["product_id"] not in self.b["chosen"]:
                self.b["chosen"].append(picked["product_id"])
            return self._ask_pick(trusted)
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
        if kind == "b_repick":
            self.b["chosen"] = []
            self.b["phase"] = "pick"
            return self._ask_pick(trusted)
        if kind == "b_adopt":
            self.b["orders"] = [
                {"product_id": item["product_id"], "name": item["product_name"],
                 "amount_fen": item["unit_price_fen"] * item.get("quantity", 1),
                 "quantity": item.get("quantity", 1),
                 "order": None, "capture": None, "order_id": None,
                 "transaction_id": None}
                for item in self._chosen_items()]
            return self._d1_check_then_freeze(trusted)
        if kind == "b_price_ok":
            item = self._order(picked["product_id"])
            fresh = picked["amount_fen"]
            frozen = self.b["freeze"]
            spent = sum(o.get("amount_fen", 0) for o in self.b["orders"]
                        if o.get("capture") == "completed")
            if spent + fresh > frozen["amount_fen"]:
                return self._ask(trusted,
                                 f"新价 {yuan(fresh)} 元会超过已冻结的 "
                                 f"{yuan(frozen['amount_fen'])} 元"
                                 "（已付款部分保持不变），不能继续办理这件。",
                                 [("跳过这件，继续其他", {"kind": "b_skip_item",
                                                        "product_id": item["product_id"]}),
                                  ("停止剩余办理", {"kind": "b_stop"})])
            item["amount_fen"] = fresh
            return self._submit(trusted, ("order", item["product_id"]))
        if kind == "b_skip_item":
            item = self._order(picked["product_id"])
            item["order"] = "skipped"
            return self._run_next_order(trusted, skip=item["product_id"])
        if kind == "b_retry_query":
            return self._requery(trusted)
        raise ValueError("INVALID_OPTION")

    def apply_text(self, trusted, text: str):
        from .pension import parse_amount_fen
        if self.b.get("holding"):
            return self._replay_holding(trusted)  # B1: text never bypasses
        phase = self.b["phase"]
        if phase == "budget":
            fen = parse_amount_fen(text)
            if fen is None or fen <= 0:
                return self._ask_budget(trusted)
            self.b["budget_limit_fen"] = fen
            # One personal budget per user and month: competing tasks share the
            # id, so the serialized occupation seam guards them against each
            # other (B07 / M3).
            month = self.entry.clock().strftime("%Y-%m")
            self.b["budget_id"] = f"bud_{self.state['actor'][0]}_{month}"
            self.b["budget_version"] = 1
            self.b["phase"] = "date"
            return self._ask_date(trusted)
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
        plan_data = self._plan()
        application = self.entry.harness.application
        if kind == "freeze":
            outcome = self.ports.freeze_execute(trusted, plan_data)
            if outcome.state == "verify_wait":
                return self._verify_wait(trusted, outcome)
            self._remember_write(kind, item_id, outcome)
            self.b["pending"] = None
            record = {"operation_id": outcome.operation_id, "amount_fen":
                      plan_data.freeze_amount_fen, "status": outcome.state,
                      "freeze_id": None, "authorization": "granted"}
            self.b["freeze"] = record
            if outcome.state == "completed" and outcome.result is not None:
                record["freeze_id"] = getattr(outcome.result.receipt, "freeze_id", None) \
                    if hasattr(outcome.result, "receipt") else None
                if not record["freeze_id"]:
                    record["freeze_id"] = self.ports.bind_freeze(
                        trusted, plan_data, record["operation_id"])
                try:
                    self._register_commitment(record)
                except BudgetOccupationExceededError as exceeded:
                    # The freeze succeeded but the serialized cap refused the
                    # occupation (e.g. a competing task won the room first):
                    # reverse it immediately under the limited authorization and
                    # report the honest numbers — no purchase may start.
                    self.b["stop_reason"] = "business_failure"
                    release = self.ports.finalize(trusted, plan_data, "budget_exceeded")
                    self.b["released"] = asdict(release)
                    self.b["phase"] = "finalize"
                    if release.status not in ("released", "nothing_to_release"):
                        return self.entry._view(trusted, self.state,
                            "预算不够，已停止购买；刚冻结资金的释放结果仍待核实，不宣称已退回。")
                    user, round_id, task_id = self.state["actor"]
                    others = application.list_budget_commitments(
                        user, round_id, self.b["budget_id"], include_closed=True)
                    consumed_before = sum(
                        c.committed_fen - c.unconsumed_fen for c in others
                        if c.task_id != task_id)
                    return self.entry._done(
                        trusted, self.state, TaskStatus.FAILED,
                        f"预算不够：该预算当前已占用/消费 {yuan(consumed_before)} 元，"
                        f"再冻结 {yuan(record['amount_fen'])} 元会超过上限 "
                        f"{yuan(self.b['budget_limit_fen'])} 元"
                        f"（合计需 {yuan(consumed_before + record['amount_fen'])} 元）。"
                        f"已按限定授权把刚冻结的 "
                        f"{yuan(release.released_amount_fen)} 元"
                        "原额退回，本次不购买。")
                self.b["phase"] = "orders"
                return self._run_next_order(trusted)
            if outcome.state == "unknown":
                self.b["holding"] = "unknown_freeze"
                return self._holding_view(trusted)
            return self._failed_stop(trusted)
        if kind == "order":
            item = next(i for i in self.b["orders"] if i["product_id"] == item_id)
            outcome = self.ports.order_execute(trusted, plan_data, item)
            if outcome.state == "verify_wait":
                return self._verify_wait(trusted, outcome)
            self._remember_write(kind, item_id, outcome)
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
                self.b["holding"] = "unknown_order"
                return self._holding_view(trusted)
            item["order"] = "failed"
            return self._run_next_order(trusted, skip=item["product_id"])
        if kind == "capture":
            item = next(i for i in self.b["orders"] if i["product_id"] == item_id)
            outcome = self.ports.capture_execute(trusted, plan_data, item,
                                                 item.get("order_id"))
            if outcome.state == "verify_wait":
                return self._verify_wait(trusted, outcome)
            self._remember_write(kind, item_id, outcome)
            self.b["pending"] = None
            item["capture_operation_id"] = outcome.operation_id
            if outcome.state == "completed" and outcome.result is not None:
                receipt = getattr(outcome.result, "receipt", None)
                item["capture"] = "completed"
                item["transaction_id"] = getattr(receipt, "transaction_id", None)
                self._consume_commitment(item)
                return self._run_next_order(trusted, skip=item["product_id"])
            if outcome.state == "unknown":
                item["capture"] = "unknown"
                self.b["holding"] = "unknown_capture"
                return self._holding_view(trusted)
            item["capture"] = "failed"
            return self._run_next_order(trusted, skip=item["product_id"])
        raise ValueError("INVALID_TARGET")

    # ------------------------------------------------------------------ orders

    def _run_next_order(self, trusted, skip=None):
        pending = [o for o in self.b["orders"]
                   if o.get("order") is None and o["product_id"] != skip]
        if not pending:
            paid_any = any(o.get("capture") == "completed" for o in self.b["orders"])
            if paid_any or any(o.get("order") == "completed" for o in self.b["orders"]):
                # settled purchases → finalize under the limited authorization
                self.b["phase"] = "finalize"
                return self._finalize(trusted)
            return self._failed_stop(trusted)
        item = pending[0]
        # A changed or unavailable quote surfaces BEFORE its confirmation is
        # asked for; an old confirmation never approves new money (B03).
        fresh = self._refresh_price(trusted, item)
        if fresh is not None:
            return fresh
        answer = self.ports.order_check(trusted, self._plan(), item)
        return self._gate(trusted, answer, ("order", item["product_id"]))

    def _run_capture(self, trusted, item):
        answer = self.ports.capture_check(trusted, self._plan(), item,
                                          item.get("order_id"))
        return self._gate(trusted, answer, ("capture", item["product_id"]))

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
        for product in data.products:
            if product.product_id == item["product_id"]:
                fresh = product.unit_price_fen
                if fresh != item["amount_fen"]:
                    # A changed quote never rides an old confirmation.
                    return self._ask(
                        trusted,
                        f"{item['name']} 的价格已从 {yuan(item['amount_fen'])} 元变为 "
                        f"{yuan(fresh)} 元。旧确认不批准新金额；请重新选择。",
                        [(f"按新价 {yuan(fresh)} 元继续", {"kind": "b_price_ok",
                                                        "product_id": item["product_id"],
                                                        "amount_fen": fresh}),
                         ("停止剩余办理", {"kind": "b_stop"})])
                return None
        return self._ask(trusted, f"{item['name']} 目前不可购买。可停止或跳过。",
                         [("跳过这件，继续其他", {"kind": "b_skip_item",
                                                "product_id": item["product_id"]}),
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
                outcome = self.ports.requery(trusted, self._plan(), "freeze",
                                              freeze["operation_id"])
                if outcome is not None and outcome.state == "completed":
                    self._remember_write("freeze", None, outcome)
                freeze["freeze_id"] = freeze_id
                freeze["status"] = "completed"
                try:
                    self._register_commitment(freeze)
                except BudgetOccupationExceededError:
                    # The room vanished while the freeze was unknown: reverse
                    # the verified freeze and fail honestly (review N2).
                    self.b["stop_reason"] = "business_failure"
                    release = self.ports.finalize(trusted, self._plan(),
                                                  "budget_exceeded")
                    self.b["released"] = asdict(release)
                    self.b["holding"] = None
                    self.b["phase"] = "finalize"
                    if release.status not in ("released", "nothing_to_release"):
                        return self.entry._view(trusted, self.state,
                            "预算不够，已停止购买；刚核实冻结的释放结果仍待核实，不宣称已退回。")
                    return self.entry._done(
                        trusted, self.state, TaskStatus.FAILED,
                        f"预算不够：核实后这笔冻结已无额度可用。已按限定授权把刚核实的 "
                        f"{yuan(release.released_amount_fen)} 元"
                        "原额退回，本次不购买。")
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
                self._remember_write(holding_kind, item["product_id"], outcome)
                if holding_kind == "order":
                    item["order"] = "completed"
                    item["order_id"] = self.b["write_facts"][
                        f"order:{item['product_id']}"].get("order_id")
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
                return self._run_next_order(trusted, skip=item["product_id"])
            return self._holding_view(trusted)
        return self._holding_view(trusted)

    # ------------------------------------------------------------------ budget seam

    def _register_commitment(self, freeze: dict) -> None:
        from app.contracts.cross import BudgetCommitment

        application = self.entry.harness.application
        user, round_id, task_id = self.state["actor"]
        budget = BudgetRef(budget_id=self.b["budget_id"],
                           version=self.b["budget_version"])
        commitment_id = f"bc_{task_id[:12]}"
        commitments = application.list_budget_commitments(
            user, round_id, budget.budget_id, include_closed=True)
        consumed = sum(c.committed_fen - c.unconsumed_fen for c in commitments
                       if c.commitment_id != commitment_id)
        record = BudgetCommitment(
            budget_ref=budget, task_id=task_id, commitment_id=commitment_id,
            committed_fen=freeze["amount_fen"], unconsumed_fen=freeze["amount_fen"],
            freeze_id=freeze.get("freeze_id"),
            operation_ids=[freeze["operation_id"]], settled_transaction_ids=[],
            state="active", updated_at=self.entry.clock())
        application.register_budget_commitment(
            user, round_id, record,
            max_in_flight_fen=self.b["budget_limit_fen"] - consumed)
        self.b["commitment_id"] = record.commitment_id

    def _own_commitment(self):
        application = self.entry.harness.application
        user, round_id, _ = self.state["actor"]
        for record in application.list_budget_commitments(user, round_id,
                                                          self.b["budget_id"],
                                                          include_closed=True):
            if record.commitment_id == self.b["commitment_id"]:
                return record
        return None

    def _consume_commitment(self, item: dict) -> None:
        application = self.entry.harness.application
        user, round_id, _ = self.state["actor"]
        record = self._own_commitment()
        if record is None:
            return
        updated = record.model_copy(update={
            "unconsumed_fen": record.unconsumed_fen - item["amount_fen"],
            "settled_transaction_ids": [*record.settled_transaction_ids,
                                        item.get("transaction_id") or ""],
            "updated_at": self.entry.clock()})
        application.update_budget_commitment(user, round_id, record.commitment_id, updated)

    def _close_commitment(self) -> None:
        application = self.entry.harness.application
        user, round_id, _ = self.state["actor"]
        record = self._own_commitment()
        if record is None:
            return
        # Closing means the occupation ends: committed shrinks to what was
        # really consumed, so history never counts released money as spending.
        application.update_budget_commitment(
            user, round_id, record.commitment_id,
            record.model_copy(update={
                "committed_fen": record.committed_fen - record.unconsumed_fen,
                "unconsumed_fen": 0, "state": "closed",
                "updated_at": self.entry.clock()}))

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
        if outcome.status in ("released", "nothing_to_release"):
            self._close_commitment()
        lines = []
        for item in self.b["orders"]:
            name, amount = item["name"], item["amount_fen"]
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
