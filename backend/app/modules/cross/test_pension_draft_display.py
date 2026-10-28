"""Cross13 public prompts; child capabilities use the existing explicit test substitutes."""

from copy import deepcopy
from uuid import uuid4

import pytest

from app.contracts.common import TaskStatus
from app.contracts.cross import CrossStartInput
from app.modules.cross import plan
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


@pytest.mark.parametrize("earlier_status", [None, TaskStatus.FAILED, TaskStatus.SUCCEEDED])
def test_restored_amount_omits_its_old_draft_and_counts_earlier_success_once(
        tmp_path, earlier_status):
    _, entry, _, _ = pension_composition(tmp_path)
    who = parent_trusted()
    current = destinations(entry)
    entry.resume(who, {"selected_option_id": option_id(current, "妈妈")})
    current = entry.resume(who, {"text": "2500元"})
    entry.resume(who, {"selected_option_id": option_id(current, "儿子")})
    entry.resume(who, {"text": "1000元"})

    # A synthetic local checkpoint represents an old amount question reopening.
    # It adds no editing option or bank result to the actual product.
    saved = entry.saver.get_tuple({"configurable": {
        "thread_id": "PARENT", "checkpoint_ns": ""}})
    checkpoint = deepcopy(saved.checkpoint)
    checkpoint["id"] = str(uuid4())
    version = checkpoint["channel_versions"][plan.CHANNEL] + 1
    checkpoint["channel_versions"][plan.CHANNEL] = version
    state = checkpoint["channel_values"][plan.CHANNEL]
    state["pension"]["phase"] = "amount"
    if earlier_status is not None:
        plan.add_step(state, {"step_id": "transfer:1", "action": "transfer.start_transfer",
                             "kind": "write", "amount_fen": 250000, "depends_on": []})
        state["step_state"]["transfer:1"] = {"status": earlier_status}
    entry.saver.put(saved.config, checkpoint, saved.metadata, {plan.CHANNEL: version})

    amount = entry.resume(who, {})
    assert "还可安排 1000.00 元" in amount.interaction.prompt
    changed = entry.resume(who, {"text": "900元"})
    assert changed.status is TaskStatus.WAITING_INPUT
    assert "还可安排 100.00 元" in changed.interaction.prompt
