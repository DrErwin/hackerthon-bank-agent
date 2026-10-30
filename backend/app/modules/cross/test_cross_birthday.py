"""Ticket v05-cross-business/03: birthday orchestration (tier one).

The birthday money writes are scripted ports (the real gate + gateway seam is
platform 09's wiring); the storage seams — controlled delivery detail, the
serialized budget occupation, D1 — and the whole plan/interaction machine are
real. Numbers follow XL-B01..B07: freeze = the adopted budget cap (500),
consumption 199 + 268, remainder 33 released.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

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

BUDGET_ID = "bud_U1_2026-10"  # user + month of the fixed test clock
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


def completed_order(item_pid: str) -> WriteOutcome:
    class OrderView:
        order_id = f"ord_{item_pid[-5:]}"

    class Result:
        order = OrderView()

    return WriteOutcome(executed=True, state="completed", result=Result(),
                        operation_id=str(uuid4()))


def completed_capture(item_pid: str) -> WriteOutcome:
    class Receipt:
        transaction_id = f"txn_{item_pid[-5:]}"

    class Ok:
        receipt = Receipt()

    return WriteOutcome(executed=True, state="completed", result=Ok(),
                        operation_id=str(uuid4()))


class ScriptedBirthdayPorts:
    """Ports from per-action scripts; release amounts are given per test."""

    verify_challenge = None  # a step-up challenge to hold at, once

    def __init__(self, *, products=(FLOWER, CAKE), fresh_prices=None,
                 fresh_missing=(), freeze="completed",
                 orders=("completed", "completed"),
                 captures=("completed", "completed"),
                 requery_results=None, requery_auto=False,
                 release_status="released", released_amount_fen=3300):
        self.products_list = list(products)
        self.fresh_prices = dict(fresh_prices or {})
        self.fresh_missing = set(fresh_missing)
        self.freeze_script = freeze
        self.orders_script = list(orders)
        self.captures_script = list(captures)
        self.requery_results = requery_results or {}
        self.requery_auto = requery_auto
        self.last_order_op = None
        self.last_capture_op = None
        self.release_status = release_status
        self.released_amount_fen = released_amount_fen
        self.granted: list[str] = []
        self.bind_calls: list[str] = []
        self.requery_ids: list[str] = []
        self.freeze_executes = 0
        self.order_executes: list[str] = []
        self.capture_executes: list[str] = []
        self.finalize_calls: list[str] = []
        self._reads = 0

    def products(self, context, request):
        # Fresh state applies from the second read onward (the re-check).
        self._reads += 1
        rows = []
        for product in self.products_list:
            if self._reads > 1 and product.product_id in self.fresh_missing:
                continue  # no longer offered: unavailable / undeliverable
            if self._reads > 1 and product.product_id in self.fresh_prices:
                product = product.model_copy(
                    update={"unit_price_fen": self.fresh_prices[product.product_id]})
            rows.append(product)
        return QueryOk(kind="ok", data=ProductList(products=rows))

    def freeze_check(self, context, plan):
        if self.freeze_script == "block":
            return GateAnswer(decision=SecurityDecisionCode.BLOCK,
                              operation_id=str(uuid4()), reason_code="HIGH_RISK")
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

    def freeze_execute(self, context, plan):
        self.freeze_executes += 1
        if self.freeze_script == "verify_once":
            self.freeze_script = "completed"
            return WriteOutcome(executed=False, state="verify_wait", result=None,
                                operation_id=None, verify=self.verify_challenge)
        if self.freeze_script == "unknown":
            return WriteOutcome(executed=True, state="unknown", result=None,
                                operation_id=str(uuid4()))

        class Receipt:
            freeze_id = "fz_001"

        class Ok:
            receipt = Receipt()

        return WriteOutcome(executed=True, state="completed", result=Ok(),
                            operation_id=str(uuid4()))

    def order_execute(self, context, plan, item):
        self.order_executes.append(item["product_id"])
        state = self.orders_script.pop(0) if self.orders_script else "completed"
        if state == "unknown":
            unknown = WriteOutcome(executed=True, state="unknown", result=None,
                                   operation_id=str(uuid4()))
            self.last_order_op = unknown.operation_id
            return unknown
        if state == "failed":
            return WriteOutcome(executed=True, state="failed", result=None,
                                operation_id=str(uuid4()))
        return completed_order(item["product_id"])

    def capture_execute(self, context, plan, item, order_id):
        self.capture_executes.append(item["product_id"])
        state = self.captures_script.pop(0) if self.captures_script else "completed"
        if state == "unknown":
            unknown = WriteOutcome(executed=True, state="unknown", result=None,
                                   operation_id=str(uuid4()))
            self.last_capture_op = unknown.operation_id
            return unknown
        return completed_capture(item["product_id"])

    def grant_release(self, context, plan, confirmation_ref):
        self.granted.append(confirmation_ref)
        return "rel_001"

    def bind_freeze(self, context, plan, operation_id):
        self.bind_calls.append(operation_id)
        return "fz_001"

    def requery(self, context, plan, target, operation_id):
        self.requery_ids.append(operation_id)
        if operation_id in self.requery_results:
            return self.requery_results[operation_id]
        if self.requery_auto:
            return (completed_capture(context.task_id[-5:]) if target == "capture"
                    else completed_order(context.task_id[-5:]))
        return None

    def finalize(self, context, plan, reason):
        self.finalize_calls.append(reason)
        if self.release_status == "needs_attention":
            return ReleaseOutcome(status="needs_attention")
        if self.release_status == "nothing_to_release":
            return ReleaseOutcome(status="nothing_to_release", released_amount_fen=0,
                                  remaining_fen=0, consumed_total_fen=0,
                                  release_operation_id=str(uuid4()))
        return ReleaseOutcome(status="released",
                              released_amount_fen=self.released_amount_fen,
                              remaining_fen=0, consumed_total_fen=0,
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


def run_to_freeze(entry, *, date="2026-10-30", ref="deliver-ref-0001",
                  picks=("康乃馨", "蛋糕")):
    started = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="500 元以内给妈妈安排花和蛋糕"))
    assert started.status is TaskStatus.WAITING_INPUT
    # The goal already names the budget, so the first question is the date.
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


def confirm_until_settled(entry, guard_word=None):
    result = entry.resume(parent_trusted(), {"choice": "approve"})
    for _ in range(12):
        if result.status is not TaskStatus.WAITING_APPROVAL:
            return result
        if guard_word and guard_word in result.message:
            return result
        result = entry.resume(parent_trusted(), {"choice": "approve"})
    return result


# ------------------------------------------------------------------- XL-B01


def test_b01_freeze_500_pay_199_268_release_33(tmp_path):
    ports = ScriptedBirthdayPorts(released_amount_fen=3300)
    harness, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    freeze_ask = run_to_freeze(entry)
    assert freeze_ask.status is TaskStatus.WAITING_APPROVAL
    assert "冻结 500.00 元" in freeze_ask.message  # the cap, per XL-B01
    assert "只退未消费部分" in freeze_ask.message
    entry.resume(parent_trusted(), {"choice": "approve"})  # freeze confirmation
    assert ports.granted == ["conf-freeze"]  # §3.5 authorization from that approval

    done = confirm_until_settled(entry)
    assert done.status is TaskStatus.SUCCEEDED, done.message
    assert "康乃馨花束：订单已创建并已付款 199.00 元" in done.message
    assert "六寸蛋糕：订单已创建并已付款 268.00 元" in done.message
    assert "没花完的 33.00 元已退回原卡" in done.message
    assert "送达情况请留意商家通知" in done.message
    assert ports.freeze_executes == 1
    assert ports.order_executes == ["P_FLOWER", "P_CAKE"]
    assert ports.capture_executes == ["P_FLOWER", "P_CAKE"]
    commitments = application.list_budget_commitments(
        "U1", "D1", BUDGET_ID, include_closed=True)
    assert commitments == []  # no adopted personal budget: no synthetic month record


def test_b01_step_up_verification_holds_then_resumes_the_write(tmp_path):
    """The real gate asks a step-up code between the approval and the bank
    (v05 security policy); the flow holds at the challenge and the platform's
    resume signal continues the same write (G-series seam for platform 09)."""
    ports = ScriptedBirthdayPorts(released_amount_fen=50000)
    harness, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    freeze_ask = run_to_freeze(entry)
    assert freeze_ask.status is TaskStatus.WAITING_APPROVAL

    challenge = InteractionRequest(
        interaction_id="verify-1", kind="verification", prompt="请输入验证码",
        required_fields=["code"], options=[], record_ref="challenge-1")
    ports.freeze_script = "verify_once"
    ports.verify_challenge = challenge
    held = entry.resume(parent_trusted(), {"choice": "approve"})
    assert held.status is TaskStatus.WAITING_APPROVAL
    assert held.interaction.kind == "verification"
    assert held.interaction.record_ref == "challenge-1"
    assert ports.freeze_executes == 1  # the first submit reached the gate only
    assert application.get_task("U1", "D1", "PARENT").status != TaskStatus.SUCCEEDED
    # An empty nudge replays the challenge, never submits a second time.
    replayed = entry.resume(parent_trusted(), {})
    assert replayed.interaction is not None
    assert replayed.interaction.kind == "verification"
    assert ports.freeze_executes == 1

    # The verification service reports passed; the platform resumes the task.
    settled = entry.resume(parent_trusted(), {"choice": "resume"})
    assert settled.status is not TaskStatus.WAITING_APPROVAL or "验证" not in settled.message
    assert ports.freeze_executes == 2  # same write, resubmitted, now executed
    assert ports.granted == ["conf-freeze"]


# ------------------------------------------------------------------- XL-B02


def test_b02_missing_delivery_reference_is_rejected_honestly(tmp_path):
    ports = ScriptedBirthdayPorts()
    _, entry, _ = birthday_composition(tmp_path, ports)
    entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(),
                                                   goal="给妈妈过生日，安排花和蛋糕"))
    entry.resume(parent_trusted(), {"text": "500元"})
    entry.resume(parent_trusted(), {"text": "2026-10-30"})
    bad = entry.resume(parent_trusted(), {"text": "no-such-ref-0000"})
    assert bad.status is TaskStatus.WAITING_INPUT
    assert "查不到对应的配送信息" in bad.message


def test_b02_over_budget_selection_stops_before_any_write(tmp_path):
    ports = ScriptedBirthdayPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    started = entry.start(parent_trusted(), CrossStartInput(
        request_id=uuid4(), goal="300 元以内给妈妈安排花和蛋糕"))
    entry.resume(parent_trusted(), {"text": "2026-10-30"})
    current = entry.resume(parent_trusted(), {"text": "deliver-ref-0001"})
    current = entry.resume(parent_trusted(),
                           {"selected_option_id": option_id(current, "康乃馨")})
    current = entry.resume(parent_trusted(),
                           {"selected_option_id": option_id(current, "蛋糕")})
    over = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(current, "就选这些")})
    assert over.status is TaskStatus.WAITING_INPUT
    assert "超过预算上限 300.00 元" in over.message
    stop = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(over, "停止")})
    assert stop.status is TaskStatus.CANCELLED
    assert ports.freeze_executes == 0


def test_b02_flower_only_skips_the_mechanical_script(tmp_path):
    ports = ScriptedBirthdayPorts(released_amount_fen=30100)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry, picks=("康乃馨",))
    done = confirm_until_settled(entry)
    assert done.status is TaskStatus.SUCCEEDED
    assert "六寸蛋糕" not in done.message
    assert "没花完的 301.00 元已退回原卡" in done.message
    assert ports.order_executes == ["P_FLOWER"]


# ------------------------------------------------------------------- XL-B03


def test_b03_price_change_requotes_and_over_freeze_refuses(tmp_path):
    # 199 + 350 = 549 > the 500 freeze: the honest refusal, not a silent charge.
    ports = ScriptedBirthdayPorts(fresh_prices={"P_CAKE": 35000})
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    confirm_until_settled(entry, guard_word="康乃馨")  # flower paid at 199
    result = entry.resume(parent_trusted(), {"choice": "approve"})
    while not ("价格已从" in result.message and "350.00" in result.message):
        result = entry.resume(parent_trusted(), {"choice": "approve"})
    assert "旧确认不批准新金额" in result.message
    refusal = entry.resume(parent_trusted(),
                           {"selected_option_id": option_id(result, "按新价")})
    assert "超过已冻结" in refusal.message
    skip = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(refusal, "跳过这件")})
    assert skip.status is TaskStatus.SUCCEEDED
    assert "康乃馨花束：订单已创建并已付款 199.00 元" in skip.message


def test_b03_unavailable_product_is_skipped_not_bought(tmp_path):
    ports = ScriptedBirthdayPorts(fresh_missing={"P_CAKE"})
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    confirm_until_settled(entry, guard_word="康乃馨")
    result = entry.resume(parent_trusted(), {"choice": "approve"})
    while "目前不可购买" not in result.message:
        result = entry.resume(parent_trusted(), {"choice": "approve"})
    skip = entry.resume(parent_trusted(),
                        {"selected_option_id": option_id(result, "跳过这件")})
    assert skip.status is TaskStatus.SUCCEEDED
    assert ports.order_executes == ["P_FLOWER"]


# ------------------------------------------------------------------- XL-B04


def test_b04_flower_paid_cake_order_failed_releases_301(tmp_path):
    ports = ScriptedBirthdayPorts(orders=("completed", "failed"),
                                  captures=("completed",),
                                  released_amount_fen=30100)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    done = confirm_until_settled(entry)
    assert done.status is TaskStatus.SUCCEEDED
    assert "康乃馨花束：订单已创建并已付款 199.00 元" in done.message
    assert "六寸蛋糕：下单未办成，未付款。" in done.message
    assert "共花 199.00 元；没花完的 301.00 元已退回原卡" in done.message


# ------------------------------------------------------------------- XL-B05


def test_b05_unknown_freeze_blocks_orders_until_requery(tmp_path):
    ports = ScriptedBirthdayPorts(freeze="unknown", released_amount_fen=3300)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    held = entry.resume(parent_trusted(), {"choice": "approve"})
    assert held.status is TaskStatus.WAITING_INPUT
    assert "冻结结果还待核实" in held.message and "不重复冻结" in held.message
    # Free text must not bypass the hold (review B1).
    assert entry.resume(parent_trusted(), {"text": "继续下单"}).message == held.message
    resolved = entry.resume(parent_trusted(),
                            {"selected_option_id": option_id(held, "核实原操作")})
    assert ports.freeze_executes == 1 and ports.bind_calls
    done = confirm_until_settled(entry)
    assert done.status is TaskStatus.SUCCEEDED


def test_b05_unknown_order_requeries_by_original_id_and_pays_once(tmp_path):
    ports = ScriptedBirthdayPorts(orders=("unknown",), captures=("completed",),
                                  requery_auto=True, released_amount_fen=30100)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry, picks=("康乃馨",))
    result = entry.resume(parent_trusted(), {"choice": "approve"})  # freeze confirm
    assert result.status is TaskStatus.WAITING_APPROVAL  # the order confirmation
    held = entry.resume(parent_trusted(), {"choice": "approve"})  # order → unknown
    assert held.status is TaskStatus.WAITING_INPUT
    assert "下单结果还待核实" in held.message
    # Free text never restarts the purchase while the order is unsettled (B1).
    assert entry.resume(parent_trusted(), {"text": "继续"}).message == held.message
    resolved = entry.resume(parent_trusted(),
                            {"selected_option_id": option_id(held, "核实原操作")})
    assert ports.requery_ids == [str(ports.last_order_op)]  # the original id
    done = confirm_until_settled(entry)
    assert done.status is TaskStatus.SUCCEEDED
    assert "已付款 199.00 元" in done.message
    assert ports.order_executes == ["P_FLOWER"]  # submitted exactly once


def test_b05_unknown_capture_requeries_and_does_not_double_pay(tmp_path):
    # Two items; the SECOND capture goes unknown: the re-query must resolve the
    # cake's payment, never re-bind onto the already-paid flower (review B2).
    ports = ScriptedBirthdayPorts(captures=("completed", "unknown"),
                                  requery_auto=True, released_amount_fen=3300)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    result = entry.resume(parent_trusted(), {"choice": "approve"})  # freeze confirm
    while "付款结果还待核实" not in result.message:
        result = entry.resume(parent_trusted(), {"choice": "approve"})
    resolved = entry.resume(parent_trusted(),
                            {"selected_option_id": option_id(result, "核实原操作")})
    assert ports.requery_ids == [str(ports.last_capture_op)]
    assert resolved.status is TaskStatus.SUCCEEDED
    assert "康乃馨花束：订单已创建并已付款 199.00 元" in resolved.message
    assert "六寸蛋糕：订单已创建并已付款 268.00 元" in resolved.message
    assert ports.capture_executes == ["P_FLOWER", "P_CAKE"]  # each paid once


# ------------------------------------------------------------------- XL-B06


def test_b06_cancel_after_freeze_releases_whole_remainder(tmp_path):
    ports = ScriptedBirthdayPorts(released_amount_fen=50000)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    entry.resume(parent_trusted(), {"choice": "approve"})  # freeze done
    stopped = entry.resume(parent_trusted(), {"cancel": True})
    assert stopped.status is TaskStatus.CANCELLED
    assert "已停止办理" in stopped.message
    assert "留出的 500.00 元专款已全部退回原卡" in stopped.message
    assert "没有下单，也没有付款" in stopped.message
    assert ports.order_executes == []
    assert ports.finalize_calls == ["user_cancelled"]


def test_b06_cancel_after_flower_paid_is_partial(tmp_path):
    ports = ScriptedBirthdayPorts(released_amount_fen=30100)
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    # Approve until the CAKE's order confirmation: by then the flower is paid.
    result = entry.resume(parent_trusted(), {"choice": "approve"})
    while "六寸蛋糕" not in result.message or result.status is TaskStatus.WAITING_APPROVAL and "下单 六寸蛋糕" not in result.message:
        result = entry.resume(parent_trusted(), {"choice": "approve"})
    stopped = entry.resume(parent_trusted(), {"cancel": True})
    assert stopped.status is TaskStatus.PARTIALLY_SUCCEEDED
    assert stopped.message.startswith("部分完成，后续已停止")
    assert "已付款 199.00 元" in stopped.message
    assert "没花完的 301.00 元已退回原卡" in stopped.message


def test_b06_release_unknown_stays_pending(tmp_path):
    ports = ScriptedBirthdayPorts(release_status="needs_attention")
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    entry.resume(parent_trusted(), {"choice": "approve"})
    stopped = entry.resume(parent_trusted(), {"cancel": True})
    assert stopped.status is TaskStatus.RUNNING
    assert "是否已退回原卡还在核实" in stopped.message
    assert "核实前不能说已经退回" in stopped.message


def test_b06_gate_block_writes_nothing(tmp_path):
    ports = ScriptedBirthdayPorts(freeze="block")
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    blocked = entry.resume(parent_trusted(), {"choice": "approve"})
    # The gate refused before any submission: no authorization, no money moved.
    assert ports.granted == []
    assert ports.freeze_executes == 0
    assert ports.finalize_calls == []  # nothing was frozen, nothing to release


def test_b06_d1_conflict_stops_before_any_freeze(tmp_path):
    from app.contracts.cross import AdoptedArrangement

    ports = ScriptedBirthdayPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
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


def test_b06_own_arrangement_lineage_does_not_block(tmp_path):
    from app.contracts.cross import AdoptedArrangement

    ports = ScriptedBirthdayPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    # The parent task itself holds the arrangement: its own lineage proceeds.
    application.acquire_arrangement(AdoptedArrangement.model_validate({
        "arrangement_id": "arr_PARENT", "user_id": "U1", "demo_round_id": "D1",
        "source_task_id": "PARENT", "plan_revision": 1, "payer_account_id": "A1",
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
    assert adopt.status is TaskStatus.WAITING_APPROVAL  # freeze proceeds


# ------------------------------------------------------------------- XL-B07


def test_b07_unadopted_monthly_fixture_does_not_become_a_personal_budget(tmp_path):
    ports = ScriptedBirthdayPorts()
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    # The old user-month id was fabricated by the flow. It is not an adoption.
    result = run_to_freeze(entry)
    assert result.data.budget is None
    assert application.list_adopted_budgets("U1", "D1") == []
    assert application.list_budget_commitments("U1", "D1", BUDGET_ID) == []
    assert ports.freeze_executes == 0


def test_b05_original_freeze_query_without_personal_adoption_keeps_its_reference(tmp_path):
    ports = ScriptedBirthdayPorts(freeze="unknown")
    _, entry, application = birthday_composition(tmp_path, ports)
    store_delivery(application)
    run_to_freeze(entry)
    held = entry.resume(parent_trusted(), {"choice": "approve"})
    resolved = entry.resume(parent_trusted(), {"selected_option_id": option_id(held, "核实原操作")})
    assert resolved.status is TaskStatus.WAITING_APPROVAL
    assert ports.freeze_executes == 1 and len(ports.bind_calls) == 1
    assert ports.finalize_calls == [] and ports.order_executes == []
    assert application.list_adopted_budgets("U1", "D1") == []
