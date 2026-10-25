"""Explicit #284 + #292 + business07 composition probe; no real model call.

Run explicitly with PYTHONPATH pointing at the combined checkout's backend.
Not collected by the ordinary backend suite before its upstream PRs merge.
"""

import json
from uuid import uuid4

from app.agent_platform.test_birthday_runtime_wiring import composition, trusted
from app.contracts.bills import BillDetails
from app.contracts.cross import CrossStartInput
from app.modules.cross.test_cross_pension import option_id
from app.modules.cross.test_pension_contract_inputs import income


def test_actual_bank_income_and_own_destination_on_combined_inputs(tmp_path):
    runtime, entry = composition(tmp_path)
    who = trusted(runtime)
    try:
        at = runtime.gateway._bank.clock().replace(day=2, hour=10, minute=0, second=0, microsecond=0)
        rows = [income("real-pension", 500000, occurred_at=at),
                income("family-credit", 20000, occurred_at=at, counterparty_name="家人", summary="家人转入"),
                income("other-own-credit", 80000, occurred_at=at, account_id="A5"),
                income("transfer-out", 90000, occurred_at=at, direction="outflow"),
                income("interest-credit", 100, occurred_at=at, nature="interest", category="other")]
        runtime.gateway._bank.store.seed_ledger_rows([
            {**row.model_dump(mode="json"), "user_id": "U1"} for row in rows])
        current = entry.start(who, CrossStartInput(request_id=uuid4(), goal="按本月养老金安排储蓄和家人转账"))
        current = entry.resume(who, {"selected_option_id": option_id(current, "主账户")})
        current = entry.resume(who, {"selected_option_id": option_id(current, "直接安排资金")})
        relations = runtime.application.list_child_tasks("U1", "D1", who.task_id)
        bill_child = next(row for row in relations if row.step_id == "bills_details")
        bill_result = runtime.application.get_task("U1", "D1", bill_child.child_task_id).snapshot["result"]
        assert bill_result["status"] == "succeeded", bill_result
        details = BillDetails.model_validate(bill_result["data"])
        assert any(row.transaction_id == "real-pension" and row.direction == "inflow"
                   and row.nature == "transfer" for row in details.transactions)
        labels = [row.label for row in current.interaction.options]
        assert any("5000.00" in label for label in labels)
        assert not any("5200.00" in label or "800.00" in label for label in labels)
        current = entry.resume(who, {"selected_option_id": option_id(current, "5000.00")})
        current = entry.resume(who, {"text": "1500元"})
        current = entry.resume(who, {"selected_option_id": option_id(current, "算进留存")})
        current = entry.resume(who, {"selected_option_id": option_id(current, "储蓄账户")})
        current = entry.resume(who, {"text": "2500元"})
        current = entry.resume(who, {"selected_option_id": option_id(current, "家庭")})
        current = entry.resume(who, {"text": "1000元"})
        current = entry.resume(who, {"selected_option_id": option_id(current, "去向已选好")})
        assert "2 笔转账，合计 3500.00 元" in current.message
        current = entry.resume(who, {"selected_option_id": option_id(current, "采用并开始办理")})
        active = runtime.application.get_active_arrangement("U1", "D1", "A1").record
        assert active.funds_basis == "selected_income"
        assert active.income_transaction_ids == ["real-pension"]
        assert active.base_fen == 500000 and active.living_reserve_fen == 150000
        transfers = [step for step in current.data.steps if step.action == "transfer.start_transfer"]
        assert len(transfers) == 2 and transfers[0].amount_fen == 250000
        assert transfers[1].amount_fen is None and transfers[1].status is None
        child = runtime.application.get_task("U1", "D1", current.data.interaction_task_id)
        assert child.snapshot["result"]["status"] == "needs_attention"
        assert child.snapshot["result"]["data"]["payee"]["account_masked"] == runtime.gateway.get_account(who, "A5").data.account_masked
        assert all(row["operation_id"].startswith("seed:") for row in runtime.gateway._bank.store.list_ledger("U1", "A1"))
        print(json.dumps({"income_transaction_ids": active.income_transaction_ids,
            "base_fen": active.base_fen, "reserve_fen": active.living_reserve_fen,
            "planned_transfers_fen": [250000, 100000], "first_child_status": "needs_attention",
            "second_transfer_dispatched": False, "non_seed_writes": 0}, ensure_ascii=False))
    finally:
        runtime.gateway.close()
