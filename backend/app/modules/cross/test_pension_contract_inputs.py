"""PI01—PI05: bank contract income and public own-account discovery."""

from uuid import uuid4
from datetime import timedelta
from contextlib import nullcontext
from unittest.mock import patch

import pytest

from app.contracts.bank import Transaction
from app.contracts.cross import CrossStartInput
from app.contracts.common import TaskStatus
from app.modules.cross.test_cross_pension import pension_composition, option_id
from app.modules.cross.test_cross_expense import NOW, parent_trusted


def income(txid, amount, **changes):
    data = dict(transaction_id=txid, account_id="A1", occurred_at=NOW, amount_fen=amount,
        direction="inflow", nature="transfer", category="transfer", counterparty_id=None,
        counterparty_name="养老金发放", counterparty_account_masked=None, channel="bank",
        summary="养老金到账", original_transaction_id=None, original_occurred_at=None)
    return Transaction(**{**data, **changes})


def test_contract_income_candidates_are_selected_not_summed(tmp_path):
    rows = [income("pension", 500000), income("family", 20000, summary="家人转入"),
            income("out", 90000, direction="outflow"),
            income("interest", 100, nature="interest", category="other"),
            income("refund", 900, nature="refund", category="shopping",
                   original_transaction_id="previous", original_occurred_at=NOW)]
    inputs = []
    harness, entry, _, _ = pension_composition(tmp_path, transactions=rows, transfer_inputs=inputs)
    started = entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(), goal="安排本月养老金"))
    basis = entry.resume(parent_trusted(), {
        "selected_option_id": option_id(started, "直接安排资金")})
    labels = [row.label for row in basis.interaction.options]
    assert any("5000.00" in label for label in labels), labels
    assert any("200.00" in label for label in labels), labels
    assert not any("5200.00" in label or "900.00" in label or "9.00" in label for label in labels)
    reserve = entry.resume(parent_trusted(), {
        "selected_option_id": option_id(basis, "5000.00")})
    assert "本次可安排范围 5000.00" in reserve.message
    debits = entry.resume(parent_trusted(), {"text": "1500元"})
    choices = entry.resume(parent_trusted(), {"selected_option_id": option_id(debits, "算进留存")})
    selected = entry.resume(parent_trusted(), {"selected_option_id": option_id(choices, "妈妈")})
    choices = entry.resume(parent_trusted(), {"text": "2500元"})
    adopt = entry.resume(parent_trusted(), {"selected_option_id": option_id(choices, "去向已选好")})
    entry.resume(parent_trusted(), {"selected_option_id": option_id(adopt, "采用并开始办理")})
    record = harness.application.get_active_arrangement("U1", "D1", "A1").record
    assert record.income_transaction_ids == ["pension"] and record.base_fen == 500000
    assert inputs[0].payee.kind == "saved" and inputs[0].payee.payee_id == "P_MOM"


def test_same_day_same_amount_income_has_distinct_labels_and_stale_choices_fail(tmp_path):
    later = NOW + timedelta(hours=1)
    _, entry, _, _ = pension_composition(tmp_path, transactions=[
        income("morning", 500000), income("later", 500000, occurred_at=later)])
    started = entry.start(parent_trusted(), CrossStartInput(request_id=uuid4(), goal="安排本月养老金"))
    basis = entry.resume(parent_trusted(), {"selected_option_id": option_id(started, "直接安排资金")})
    options = [row for row in basis.interaction.options if "本月实际入账" in row.label]
    assert len(options) == len({row.label for row in options}) == 2
    assert later.strftime("%H:%M:%S") in options[1].label
    refreshed = entry.resume(parent_trusted(), {"text": "5000元"})
    with pytest.raises(ValueError, match="INVALID_OPTION"):
        entry.resume(parent_trusted(), {"selected_option_id": options[1].id})
    entry.resume(parent_trusted(), {"selected_option_id": option_id(refreshed, "第2笔")})
    # The adopted source is externally visible after the ordinary plan adoption.
    debits = entry.resume(parent_trusted(), {"text": "1500元"})
    dest = entry.resume(parent_trusted(), {"selected_option_id": option_id(debits, "算进留存")})
    entry.resume(parent_trusted(), {"selected_option_id": option_id(dest, "妈妈")})
    dest = entry.resume(parent_trusted(), {"text": "2500元"})
    adopt = entry.resume(parent_trusted(), {"selected_option_id": option_id(dest, "去向已选好")})
    entry.resume(parent_trusted(), {"selected_option_id": option_id(adopt, "采用并开始办理")})
    record = entry.harness.application.get_active_arrangement("U1", "D1", "A1").record
    assert record.income_transaction_ids == ["later"]


@pytest.mark.parametrize("payees_unavailable", [False, True])
def test_real_own_account_is_available_without_saved_contact(tmp_path, payees_unavailable):
    from app.agent_platform.test_birthday_runtime_wiring import composition, trusted
    runtime, entry = composition(tmp_path)
    who = trusted(runtime)
    try:
        started = entry.start(who, CrossStartInput(request_id=uuid4(), goal="安排本月养老金"))
        main = entry.resume(who, {"selected_option_id": option_id(started, "主账户")})
        basis = entry.resume(who, {"selected_option_id": option_id(main, "直接安排资金")})
        reserve = entry.resume(who, {"selected_option_id": option_id(basis, "当前可用余额")})
        debit = entry.resume(who, {"text": "1500元"})
        from app.contracts.bank import QueryFailure, BankError
        failure = QueryFailure(kind="error", error=BankError(code="BANK_UNAVAILABLE", details={}))
        failing = patch.object(runtime.gateway, "list_payees", return_value=failure) if payees_unavailable else nullcontext()
        with failing:
            destinations = entry.resume(who, {"selected_option_id": option_id(debit, "算进留存")})
        assert not any("本人·主账户" in row.label for row in destinations.interaction.options)
        if not payees_unavailable:
            assert any(row.label.startswith("转给 ") for row in destinations.interaction.options)
        else:
            assert "收款人暂时查不到" in destinations.message
        # A5 is a real own account; the saved-contact list contains no such id.
        assert runtime.gateway.get_account(who, "A5").data.account_id == "A5"
        assert all(p.payee_id != "A5" for p in runtime.gateway.list_payees(who).data.payees)
        picked = entry.resume(who, {"selected_option_id": option_id(destinations, "储蓄账户")})
        assert "储蓄账户" in picked.message
        amounts = entry.resume(who, {"text": "2500元"})
        adopted = entry.resume(who, {"selected_option_id": option_id(amounts, "去向已选好")})
        first = entry.resume(who, {"selected_option_id": option_id(adopted, "采用并开始办理")})
        children = runtime.application.list_child_tasks("U1", "D1", who.task_id)
        transfer = next(row for row in children if row.step_id == "transfer:1")
        child = runtime.application.get_task("U1", "D1", transfer.child_task_id)
        assert child.snapshot["capability_name"] == "transfer.start_transfer"
        # Check the public child draft: OwnPayee survives the original transfer entry.
        data = child.snapshot["result"]["data"]
        assert data["payee"]["account_masked"] == runtime.gateway.get_account(who, "A5").data.account_masked
        assert first.status is not TaskStatus.SUCCEEDED  # no confirmation or verification was answered
        assert child.snapshot["result"]["status"] == "needs_attention", child.snapshot["result"]
        assert "已暂停" in first.message
        assert child.snapshot["result"]["message"] in first.message
        assert "办理结果未知" not in first.message
        rows = runtime.gateway._bank.store.list_ledger("U1", "A1")
        assert all(row["operation_id"].startswith("seed:") for row in rows)
    finally:
        runtime.gateway.close()
