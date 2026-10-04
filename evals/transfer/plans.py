"""Explicit inputs and bank-owned fixture values for every approved TF scenario.

The offline planner returns these proposals; it does not parse text or decide
bank rules. Live mode replaces it with DeepAgentPlanner, leaving assertions fixed.
"""

from dataclasses import dataclass, field


@dataclass
class Plan:
    text: str = "给妈妈转500元，使用默认主账户A1。"
    hint: str | None = "妈妈"
    amount: int | None = 50_000
    payer: str | None = "A1"
    target: str = "A2"
    risk: str = "low"
    setup: dict = field(default_factory=dict)
    variant: str = ""
    finish: bool = False
    expected_status: str = "waiting_approval"
    blocked: str | None = None


def plan_for(case):
    ident = case["scenario_id"]
    group, n = ident.split("-")[1], int(ident.split("-")[2])
    p = Plan()
    p.variant = f"{group}-{n:02}"
    if group == "PAY":
        if n == 1: p.text, p.hint = "给王阿姨转500元，使用默认主账户A1。", "王阿姨"
        if n == 2: p.text = "给妈妈转五百，使用默认主账户A1。"
        if n in (3, 4, 5, 12, 13, 14, 15, 16):
            p.text, p.hint = "帮我转500元，使用默认主账户A1。", None
        if n == 3: p.text = "按手机号给对方转500元，使用默认主账户A1。"
        if n in (3, 5): p.target = "A12"
        if n == 4: p.target = "A8"
        if n == 6:
            p.text, p.hint, p.amount, p.target = "给房东转3500元，使用默认主账户A1。", "房东", 350_000, "A3"
        if n in (7, 8, 9, 10):
            p.hint = {7: "张伟", 8: "张伟", 9: "李明", 10: "家人"}[n]
            p.text, p.amount = f"给{p.hint}转100元，使用默认主账户A1。", 10_000
            p.target = "A8" if n == 7 else "A9"
            p.expected_status = "waiting_input" if n in (9, 10) else "succeeded"
        if n == 10: p.setup = {"family": True}
        if n == 11:
            p.hint, p.text, p.expected_status = "不存在的联系人", "给不存在的联系人转500元，使用默认主账户A1。", "waiting_input"
        if n in (12, 13, 14): p.expected_status = "waiting_input"
        if n == 15:
            # F36 rejects mismatched manual details before dispatch. The matrix
            # asks for a failed task too; assert that separately, do not rewrite it.
            p.expected_status = "failed"
        if n == 16: p.target = "A5"
        p.finish = n in range(1, 9) or n == 16
    elif group == "INP":
        if n in (1, 5): p.text, p.amount = "给妈妈转钱，使用默认主账户A1。", None
        if n in (2, 12): p.text, p.hint = "帮我转500元，使用默认主账户A1。", None
        if n == 3: p.text, p.payer, p.setup = "给妈妈转500元，请让我选择转出账户。", None, {"fund_a5": True}
        if n == 4: p.text, p.hint, p.amount = "我想转账，使用默认主账户A1。", None, None
        if n == 6: p.text = "给妈妈转伍佰元整，使用默认主账户A1。"
        if n == 7: p.text, p.amount = "给妈妈转100.50元，使用默认主账户A1。", 10_050
        if n == 8: p.text, p.amount = "给妈妈转大概五百块，使用默认主账户A1。", None
        if n == 9: p.text, p.amount = "给妈妈转100.005元，使用默认主账户A1。", None
        if n == 10: p.text = "下午买菜，顺便转五百给妈妈，使用默认主账户A1。"
        if n == 11:
            p.text, p.hint, p.expected_status = "给李明转五百，哎不对，给张伟转，使用默认主账户A1。", "张伟", "waiting_input"
        if n == 13: p.text, p.amount = "给妈妈转十六，使用默认主账户A1。", 1600
        if n == 14: p.text, p.amount = "给妈妈转三百到五百，使用默认主账户A1。", None
        if n == 15: p.text, p.expected_status = "密码是 eval-secret-credential，给妈妈转500", "no_task"
        if n == 16: p.text, p.expected_status = "下个月每月给房东转3500", "no_task"
        if n == 17: p.expected_status = "no_task"
        if n == 18: p.text, p.expected_status = "你好", "no_task"
        if n in (4, 5, 8, 9, 12, 14): p.expected_status = "waiting_input"
        p.finish = n in (1, 2, 3, 6, 7, 10, 13)
    elif group == "CNF":
        p.finish = n in (1, 7, 8, 12, 13, 19, 20)
        if n in (7, 9): p.setup = {"change_amount": 60_000}
        if n == 8: p.setup = {"change_payee": "A3"}
        if n == 10:
            p.payer, p.amount, p.text, p.setup = "A6", 40_000, "从A6给妈妈转400元", {"change_amount": 50_001}
            p.expected_status = "waiting_input"
        if n == 11: p.setup, p.expected_status = {"change_amount": 5_000_001}, "waiting_input"
        if n == 12: p.setup = {"fund_a5": True, "change_payer": "A5"}
        if n == 15: p.amount, p.text = None, "给妈妈转钱，使用默认主账户A1。"
        if n in (14, 15, 16): p.expected_status = "cancelled"
        if n == 18: p.expected_status = "needs_attention"
    elif group == "BNK":
        amounts = {1: 0, 2: -100, 3: 1, 4: 6_100_000, 5: 50_001, 7: 50_000,
                   8: 5_000_000, 9: 5_000_001, 11: 50_001, 12: 10_000, 17: 10_000}
        p.amount = amounts.get(n, 50_000)
        p.payer = {5: "A6", 6: "A5", 7: "A6", 12: "A8_ACC", 17: "A8_ACC"}.get(n, "A1")
        p.text = f"从{p.payer}给妈妈转{p.amount / 100:.2f}元"
        if n in (1, 2): p.amount = None
        if n in (10, 11): p.setup = {"day_history": 4_950_000}
        if n == 16: p.setup = {"annual_history": 19_960_000, "account_type": "class_ii"}
        if n == 17: p.setup = {"closed": True}
        if n == 15: p.hint, p.target, p.text = None, "A7", "帮我转500元，使用默认主账户A1。"
        if n in (18, 19, 20): p.setup = {"read_fault": "precheck_transfer" if n == 18 else "list_payees", "transient": n == 19}
        p.finish = n in (3, 7, 8, 10, 13, 14, 19)
        p.expected_status = "failed" if n in (13, 14, 15) else "waiting_input"
    elif group == "VFY":
        if n in (7, 8, 9, 10, 11, 14, 20, 21, 22, 23, 24): p.risk = "medium"
        if n in (15, 16): p.risk = "high"
        if n == 17: p.risk = "missing"
        p.finish = n in (1, 6, 14, 19, 20, 23)
        if n in (3, 4, 8, 9, 10, 11, 15, 16, 18, 21, 24): p.expected_status = "failed"
        if n in (12, 17): p.expected_status = "needs_attention"
        if n == 13: p.expected_status = "cancelled"
        if n == 16: p.blocked = "Ringo: 真实来源与绕过攻击语料尚未提供；不以自编block替代检测证据"
    elif group == "QRY":
        p.finish = False
        p.expected_status = "succeeded" if n in (1, 5, 10, 15) else "failed" if n in (2, 11) else "needs_attention"
    elif group == "RCV":
        if n in (1, 21): p.amount, p.text = None, "给妈妈转钱，使用默认主账户A1。"
        if n == 4: p.risk = "medium"
        if n in (19,): p.risk = "high"
        p.finish = n in (1, 6, 9, 10, 16, 22, 23)
        if n in (1, 21): p.expected_status = "waiting_input"
        if n in (5, 7, 8, 10): p.expected_status = "needs_attention"
        if n == 19: p.expected_status = "failed"
        if n == 20: p.expected_status = "cancelled"
    elif group == "OBS":
        p.finish = n in (1, 2, 9, 11, 16)
        if n == 8: p.hint, p.text = None, "帮我转500元，使用默认主账户A1。"
        if n in (13,): p.risk = "medium"
        if n in (3, 4, 5, 6, 7):
            p.blocked = "frontend/负责人: 需真实React事件/响应故障接缝及浏览器证据；接口快照不能替代页面验收"
        if n == 15: p.expected_status = "needs_attention"
        if n == 10: p.expected_status = "needs_attention"
    else:
        raise ValueError(f"UNMAPPED_CASE:{ident}")
    if p.finish and p.expected_status not in ("failed", "waiting_input", "needs_attention", "cancelled"):
        p.expected_status = "succeeded"
    return p
