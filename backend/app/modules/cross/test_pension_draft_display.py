"""Cross13 public prompts; child capabilities use the existing explicit test substitutes."""

from uuid import uuid4

from app.contracts.common import TaskStatus
from app.contracts.cross import CrossStartInput
from app.modules.cross.test_cross_expense import parent_trusted
from app.modules.cross.test_cross_pension import option_id, pension_composition


def destinations(entry):
    who = parent_trusted()
    started = entry.start(who, CrossStartInput(
        request_id=uuid4(), goal="帮我安排本月养老金"))
    basis = entry.resume(who, {
        "selected_option_id": option_id(started, "直接安排资金")})
    entry.resume(who, {
        "selected_option_id": option_id(basis, "本月实际入账")})
    debits = entry.resume(who, {"text": "1500元"})
    return entry.resume(who, {
        "selected_option_id": option_id(debits, "算进留存")})


def test_selected_drafts_reduce_both_prompts_without_changing_adoption(tmp_path):
    _, entry, _, _ = pension_composition(tmp_path)
    who = parent_trusted()
    current = destinations(entry)
    assert "还可安排 3500.00 元" in current.interaction.prompt
    entry.resume(who, {"selected_option_id": option_id(current, "妈妈")})
    after_first = entry.resume(who, {"text": "2500元"})
    assert "还可安排 1000.00 元" in after_first.interaction.prompt
    second_amount = entry.resume(who, {
        "selected_option_id": option_id(after_first, "儿子")})
    assert "还可安排 1000.00 元" in second_amount.interaction.prompt
    after_second = entry.resume(who, {"text": "1000元"})
    assert "还可安排 0.00 元" in after_second.interaction.prompt
    adoption = entry.resume(who, {
        "selected_option_id": option_id(after_second, "去向已选好")})
    assert adoption.status is TaskStatus.WAITING_INPUT
    assert "共 2 笔转账，合计 3500.00 元" in adoption.message
