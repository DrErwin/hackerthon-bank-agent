"""Ticket v05-cross-business/03: birthday orchestration (tier one).

The birthday money writes are scripted ports (the real gate + gateway seam is
platform 09's wiring); the storage seams — controlled delivery detail, the
serialized budget occupation, D1 — and the whole plan/interaction machine are
real. Numbers follow XL-B01..B07.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.audit.journal import AuditJournal
from app.contracts.bank import Product, ProductList, QueryOk
from app.contracts.common import SecurityDecisionCode, TaskStatus
from app.contracts.cross import BudgetCommitment, BudgetRef, CrossStartInput
from app.contracts.platform import TrustedContext
from app.contracts.tasks import InteractionOption, InteractionRequest, ModuleResult
from app.memory.adapter import MemoryAdapter, MemoryContext
from app.modules.cross.birthday_ports import GateAnswer, ReleaseOutcome, WriteOutcome
from app.modules.cross.entry import CrossEntry, register_cross
from app.storage.application import ApplicationStore

from app.agent_platform.harness import AgentHarness
from app.agent_platform.registry import CapabilityRegistry
from app.agent_platform.own_bank_queries import manifest as accounts_manifest

from app.modules.cross.test_cross_expense import NOW, PlannerStub, parent_trusted

FLOWER = Product(product_id="P_FLOWER", merchant_id="M_SHOP", merchant_name="邻里花坊",
                 product_name="康乃馨花束", unit_price_fen=19900, category="other",
                 earliest_delivery_at=NOW)
CAKE = Product(product_id="P_CAKE", merchant_id="M_BAKERY", merchant_name="幸福烘焙",
               product_name="六寸蛋糕", unit_price_fen=26800, category="other",
               earliest_delivery_at=NOW)


def gate_confirmation(name: str, prompt: str) -> InteractionRequest:
    return InteractionRequest(interaction_id=str(uuid4()), kind="confirmation",
        prompt=prompt, required_fields=[],
        options=[InteractionOption(id="approve", label="确认"),
                 InteractionOption(id="cancel", label="取消")],
        record_ref=f"conf-{name}")


class ScriptedBirthdayPorts:
    """Implements the ports protocol from a per-action script.

    scripts: dict action -> list of outcomes/answers; writes whose execute
    answer is scripted "unknown" are later resolved by requery()/bind_freeze().
    """

    def __init__(self, *, products=(FLOWER, CAKE), fresh_prices=None,
                 freeze="completed", orders=("completed", "completed"),
                 captures=("completed", "completed"),
                 requery_results=None, release="released"):
        self.products_list = list(products)
        self.fresh_prices = dict(fresh_prices or {})
        self.freeze_script = freeze
        self.orders_script = list(orders)
        self.captures_script = list(captures)
        self.requery_results = requery_results or {}
        self.release_status = release
        self.granted: list[str] = []
        self.bind_calls: list[str] = []
        self.freeze_executes = 0
        self.order_executes: list[str] = []
        self.capture_executes: list[str] = []
        self.finalize_calls: list[str] = []

    # reads ------------------------------------------------------------------
    def products(self, context, request):
        # Fresh prices apply only from the second read onward: the first listing
        # is the quote the user picked from, later reads are the re-check (B03).
        self._reads = getattr(self, "_reads", 0) + 1
        if self._reads > 1 and self.fresh_prices:
            rows = [p.model_copy(update={"unit_price_fen": self.fresh_prices[p.product_id]})
                    if p.product_id in self.fresh_prices else p
                    for p in self.products_list]
        else:
            rows = list(self.products_list)
        return QueryOk(kind="ok", data=ProductList(products=rows))

    # gate answers -----------------------------------------------------------
    def freeze_check(self, context, plan):
        return GateAnswer(decision=SecurityDecisionCode.REQUIRE_CONFIRMATION,
                          operation_id=str(uuid4()),
                          interaction=gate_confirmation(
                              "freeze",
                              f"冻结 {plan.freeze_amount_fen / 100:.2f} 元用于生日安排；"
                              "结束时只退未消费部分。"))

    def order_check(self, context, plan, item):
        return GateAnswer(decision=SecurityDecisionCode.REQUIRE_CONFIRMATION,
                          operation_id=str(uuid4()),
                          interaction=gate_confirmation("order", f"下单 {item['name']}"))

    def capture_check(self, context, plan, item, order_id):
        return GateAnswer(decision=SecurityDecisionCode.REQUIRE_CONFIRMATION,
                          operation_id=str(uuid4()),
                          interaction=gate_confirmation(
                              "capture", f"按订单 {order_id} 付款 {item['name']}"))

    # writes ------------------------------------------------------------------
    class _Ok:
        def __init__(self, receipt):
            self.receipt = receipt

    def freeze_execute(self, context, plan):
        self.freeze_executes += 1
        if self.freeze_script == "unknown":
            return WriteOutcome(executed=True, state="unknown", result=None,
                                operation_id=str(uuid4()))

        class Receipt:
            freeze_id = "fz_001"

        return WriteOutcome(executed=True, state="completed",
                            result=self._Ok(Receipt()), operation_id=str(uuid4()))

    def order_execute(self, context, plan, item):
        self.order_executes.append(item["product_id"])
        state = self.orders_script.pop(0) if self.orders_script else "completed"
        if state == "unknown":
            return WriteOutcome(executed=True, state="unknown", result=None,
                                operation_id=str(uuid4()))

        class OrderView:
            order_id = f"ord_{item['product_id'][-5:]}"

        class Result:
            order = OrderView()

        return WriteOutcome(executed=True, state="completed", result=Result(),
                            operation_id=str(uuid4()))

    def capture_execute(self, context, plan, item, order_id):
        self.capture_executes.append(item["product_id"])
        state = self.captures_script.pop(0) if self.captures_script else "completed"
        if state == "unknown":
            return WriteOutcome(executed=True, state="unknown", result=None,
                                operation_id=str(uuid4()))

        class Receipt:
            transaction_id = f"txn_{item['product_id'][-5:]}"

        return WriteOutcome(executed=True, state="completed",
                            result=self._Ok(Receipt()), operation_id=str(uuid4()))

    # release records -----------------------------------------------------------
    def grant_release(self, context, plan, confirmation_ref):
        self.granted.append(confirmation_ref)
        return "rel_001"

    def bind_freeze(self, context, plan, operation_id):
        self.bind_calls.append(operation_id)
        return "fz_001"

    def requery(self, context, plan, target):
        result = self.requery_results.get(target)
        if result is None:
            return None
        return result

    def finalize(self, context, plan, reason):
        self.finalize_calls.append(reason)
        if self.release_status == "needs_attention":
            return ReleaseOutcome(status="needs_attention")
        consumed = sum(int(item["amount_fen"]) for item in plan.items)
        if self.release_status == "nothing_to_release":
            return ReleaseOutcome(status="nothing_to_release", released_amount_fen=0,
                                  remaining_fen=0, consumed_total_fen=consumed,
                                  release_operation_id=str(uuid4()))
        return ReleaseOutcome(status="released", released_amount_fen=3300,
                              remaining_fen=0, consumed_total_fen=consumed,
                              release_operation_id=str(uuid4()))


def birthday_composition(tmp_path, ports):
    application = ApplicationStore(tmp_path / "app.sqlite")
    memory = MemoryAdapter(application, active_round=lambda: "D1")
    harness = AgentHarness(application, memory, AuditJournal(tmp_path / "app.sqlite"),
                           CapabilityRegistry(), PlannerStub(),
                           authorize_capability=lambda _t, _d: True)

    class AccountsStub:
        def start(self, trusted, request, *, thread_id=None):
            return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
                status=TaskStatus.SUCCEEDED,
                data={"accounts": [{"account_id": "A1", "account_masked": "尾号 0001",
                                     "available_balance_fen": 1_000_000,
                                     "display_name": "主账户"}]},
                message="已查到本人账户。", interaction=None, error=None,
                allowed_actions=[], recovery_required=False, recovery_reason=None)

        def resume(self, trusted, response, *, thread_id=None):
            return self.start(trusted, None)

        def recover_session(self, trusted, *, source_session_id, thread_id=None):
            return self.start(trusted, None)

        def checkpoint_context(self, trusted, *, thread_id=None):
            return None

    harness.registry.register_module(accounts_manifest("list_accounts"),
                                     lambda trusted, saver, trace: AccountsStub())
    register_cross(harness, lambda: NOW, lambda trusted: ports)
    real_now = datetime.now(timezone.utc)
    application.create_session("S1", "U1", "D1", real_now.isoformat(),
                               (real_now + timedelta(days=1)).isoformat())
    application.create_task("PARENT", "U1", "S1", "D1", "PR1", "running", {})
    entry = CrossEntry(harness, memory.checkpointer(MemoryContext("U1", "S1", "D1"),
                                                    "PARENT"),
                       None, lambda: NOW, lambda trusted: ports)
    return harness, entry, application


def option_id(result, needle):
    matches = [item for item in result.interaction.options if needle in item.label]
    assert len(matches) == 1, [item.label for item in result.interaction.options]
    return matches[0].id


def store_delivery(application, ref="deliver-ref-0001"):
    application.store_controlled_detail(
        ref, "U1", "D1", "PARENT", "delivery",
        {"recipient_name": "妈妈", "phone": "13800000000",
         "address": "幸福小区 1 号", "deliver_by": NOW.isoformat()},
        NOW.isoformat())


def run_to_freeze(entry, *, budget="500元", date="2026-10-30", ref="deliver-ref-0001",
                  picks=("康乃馨", "蛋糕")):
    started = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="500 元以内给妈妈安排花和蛋糕"))
    assert started.status is TaskStatus.WAITING_INPUT
    current = entry.resume(parent_trusted(), {"text": budget})
    assert current.status is TaskStatus.WAITING_INPUT
    current = entry.resume(parent_trusted(), {"text": date})
    current = entry.resume(parent_trusted(), {"text": ref})
    for pick in picks:
        current = entry.resume(parent_trusted(),
                               {"selected_option_id": option_id(current, pick)})
    current = entry.resume(parent_trusted(),
                           {"selected_option_id": option_id(current, "就选这些")})
    assert current.status is TaskStatus.WAITING_INPUT
    return entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(current, "采用并开始办理")})


# ------------------------------------------------------------------- XL-B01


def test_b01_freeze_500_pay_199_268_release_33(tmp_path):
    ports = ScriptedBirthdayPorts()
    harness, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    freeze_ask = run_to_freeze(entry)
    assert freeze_ask.status is TaskStatus.WAITING_APPROVAL
    assert "只退未消费部分" in freeze_ask.message  # the §3.5 clause reached the user
    confirmed = entry.resume(parent_trusted(), {"choice": "approve"})
    assert confirmed.status is TaskStatus.WAITING_APPROVAL  # first order confirmation
    assert ports.granted == ["conf-freeze"]

    def confirm_until_done():
        result = confirmed
        for _ in range(10):
            if result.status is not TaskStatus.WAITING_APPROVAL:
                return result
            result = entry.resume(parent_trusted(), {"choice": "approve"})
        return result

    done = confirm_until_done()
    assert done.status is TaskStatus.SUCCEEDED, done.message
    assert "康乃馨花束：订单已创建并已付款 199.00 元" in done.message
    assert "六寸蛋糕：订单已创建并已付款 268.00 元" in done.message
    assert "释放 33.00 元" in done.message
    assert "不代表商品已送达" in done.message
    assert ports.freeze_executes == 1
    assert ports.order_executes == ["P_FLOWER", "P_CAKE"]
    assert ports.capture_executes == ["P_FLOWER", "P_CAKE"]
    # Budget occupation: opened at freeze, consumed by both captures, closed.
    commitments = application.list_budget_commitments("U1", "D1", "bud_PARENT", include_closed=True)
    assert len(commitments) == 1 and commitments[0].state == "closed"
    assert commitments[0].committed_fen == 46700
    assert len(commitments[0].settled_transaction_ids) == 2


# ------------------------------------------------------------------- XL-B02


def test_b02_missing_delivery_reference_is_rejected_honestly(tmp_path):
    ports = ScriptedBirthdayPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
    entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(),
                                                   goal="给妈妈过生日"))
    entry.resume(parent_trusted(), {"text": "500元"})
    entry.resume(parent_trusted(), {"text": "2026-10-30"})
    bad = entry.resume(parent_trusted(), {"text": "no-such-ref-0000"})
    assert bad.status is TaskStatus.WAITING_INPUT
    assert "查不到对应的配送信息" in bad.message


def test_b02_flower_only_skips_the_mechanical_script(tmp_path):
    ports = ScriptedBirthdayPorts()
    harness, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run = run_to_freeze(entry, picks=("康乃馨",))
    confirmed = entry.resume(parent_trusted(), {"choice": "approve"})
    result = confirmed
    while result.status is TaskStatus.WAITING_APPROVAL:
        result = entry.resume(parent_trusted(), {"choice": "approve"})
    assert result.status is TaskStatus.SUCCEEDED
    assert "六寸蛋糕" not in result.message
    assert ports.order_executes == ["P_FLOWER"]


# ------------------------------------------------------------------- XL-B03


def test_b03_price_change_never_rides_the_old_confirmation(tmp_path):
    ports = ScriptedBirthdayPorts(fresh_prices={"P_CAKE": 30000})
    harness, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    freeze_ask = run_to_freeze(entry)  # 199 + 268 quoted at pick time
    confirmed = entry.resume(parent_trusted(), {"choice": "approve"})  # flower order+pay
    result = confirmed
    while result.status is TaskStatus.WAITING_APPROVAL and "六寸蛋糕" not in result.message:
        result = entry.resume(parent_trusted(), {"choice": "approve"})
    # The cake re-quote appears before its order runs.
    assert "价格已从 268.00 元变为 300.00 元" in result.message
    assert "旧确认不批准新金额" in result.message
    # 199 paid + 300 new > 467 frozen: the honest refusal, not a silent charge.
    refusal = entry.resume(parent_trusted(),
                           {"selected_option_id": option_id(result, "按新价")})
    assert "超过已冻结" in refusal.message
    skip = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(refusal, "跳过这件")})
    done = skip
    while done.status is TaskStatus.WAITING_APPROVAL:
        done = entry.resume(parent_trusted(), {"choice": "approve"})
    assert done.status is TaskStatus.SUCCEEDED
    assert "康乃馨花束：订单已创建并已付款 199.00 元" in done.message


# ------------------------------------------------------------------- XL-B05


def test_b05_unknown_freeze_blocks_orders_until_requery(tmp_path):
    ports = ScriptedBirthdayPorts(freeze="unknown")
    harness, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    freeze_ask = run_to_freeze(entry)
    confirmed = entry.resume(parent_trusted(), {"choice": "approve"})
    assert confirmed.status is TaskStatus.WAITING_INPUT
    assert "冻结结果还待核实" in confirmed.message
    assert "不重复冻结" in confirmed.message
    assert entry.resume(parent_trusted(), {}).message == confirmed.message
    resolved = entry.resume(parent_trusted(),
                            {"selected_option_id": option_id(confirmed, "核实原操作")})
    assert ports.freeze_executes == 1 and ports.bind_calls  # original id re-query only
    result = resolved
    while result.status is TaskStatus.WAITING_APPROVAL:
        result = entry.resume(parent_trusted(), {"choice": "approve"})
    assert result.status is TaskStatus.SUCCEEDED


# ------------------------------------------------------------------- XL-B06


def test_b06_cancel_after_freeze_releases_and_records_cancelled(tmp_path):
    ports = ScriptedBirthdayPorts()
    harness, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    freeze_ask = run_to_freeze(entry)
    entry.resume(parent_trusted(), {"choice": "approve"})  # freeze done, order asks
    stopped = entry.resume(parent_trusted(), {"cancel": True})
    assert stopped.status is TaskStatus.CANCELLED
    assert "已停止办理" in stopped.message
    assert "释放 33.00 元" in stopped.message
    assert ports.order_executes == []
    assert ports.finalize_calls == ["user_cancelled"]


def test_b06_release_unknown_stays_pending(tmp_path):
    ports = ScriptedBirthdayPorts(release="needs_attention")
    harness, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    entry.resume(parent_trusted(), {"choice": "approve"})
    stopped = entry.resume(parent_trusted(), {"cancel": True})
    assert stopped.status is TaskStatus.RUNNING  # unsettled release stays open
    assert "释放结果待核实" in stopped.message
    assert "不宣称已解冻" in stopped.message


# ------------------------------------------------------------------- XL-B07


def test_b07_budget_occupation_cap_blocks_an_over_cap_freeze(tmp_path):
    ports = ScriptedBirthdayPorts()
    harness, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    # An adopted 3000 budget already consumed 2600 (closed commitment history).
    consumed = BudgetCommitment(
        budget_ref=BudgetRef(budget_id="bud_PARENT", version=1), task_id="PARENT",
        commitment_id="bc_prior", committed_fen=260000, unconsumed_fen=0,
        freeze_id=None, operation_ids=[], settled_transaction_ids=["txn_prior"],
        state="closed", updated_at=NOW)
    consumed = consumed.model_copy(update={"state": "closed"})
    application.register_budget_commitment("U1", "D1", consumed)
    run_to_freeze(entry)  # 500 requested, only 300 room left
    outcome = entry.resume(parent_trusted(), {"choice": "approve"})
    assert outcome.status is TaskStatus.FAILED
    assert "预算不够" in outcome.message and "原额退回" in outcome.message
    assert ports.order_executes == []
    assert ports.finalize_calls == ["budget_exceeded"]


def test_b06_d1_conflict_stops_before_any_freeze(tmp_path):
    from app.contracts.cross import AdoptedArrangement
    from app.modules.cross.test_cross_expense import composition as expense_composition

    ports = ScriptedBirthdayPorts()
    harness, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    application.create_task("OTHER", "U1", "S1", "D1", "R2", "running", {})
    application.acquire_arrangement(AdoptedArrangement.model_validate({
        "arrangement_id": "arr_OTHER", "user_id": "U1", "demo_round_id": "D1",
        "source_task_id": "OTHER", "plan_revision": 1, "payer_account_id": "A1",
        "funds_basis": "available_balance", "income_transaction_ids": [],
        "base_fen": 1000000, "living_reserve_fen": 0,
        "reserve_includes_known_debits": True,
        "upcoming_debit_scope": {"account_ids": ["A1"],
                                  "start_at": "2026-10-01T00:00:00+08:00",
                                  "end_at": "2026-11-01T00:00:00+08:00"},
        "known_debits_fen": 0, "adopted_at": NOW.isoformat(),
        "adoption_interaction_id": "I1", "status": "active",
    }))
    adopt = run_to_freeze(entry)
    assert adopt.status is TaskStatus.WAITING_INPUT
    assert "已有正在办理的资金安排" in adopt.message
    stop = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(adopt, "停止")})
    assert stop.status is TaskStatus.CANCELLED
    assert ports.freeze_executes == 0
