"""L02 task seam: deterministic choices and durable state, no live-model claim."""
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.agent_platform.registry import CapabilityRegistry
from app.contracts.bills import AnomalyResult, TransactionCandidates
from app.contracts.platform import StartTransferInput
from app.modules.bills.anomaly_entry import BillsAnomalyEntry, register_bills_anomalies
from app.modules.bills.anomaly_manifest import ANOMALY_MANIFEST
from app.modules.bills.anomaly_service import BillsAnomalyService
from app.modules.bills.entry import register_bills
from app.modules.bills.manifest import MANIFEST
from app.modules.bills.test_public import CTX, END, NOW, START, Reads, Saver, transaction


def entry(reads, saver):
    return BillsAnomalyEntry(BillsAnomalyService(reads, lambda: NOW), saver, None)


def start(reads, saver, text="核对交易，2026年9月所有账户", **fields):
    request = StartTransferInput(request_id=uuid4(), intent_text=text, **fields)
    return entry(reads, saver).start(CTX, request, thread_id="thread1")


def choose(reads, saver, result, label=None, *, index=0, context=CTX):
    option = next(item for item in result.interaction.options if item.label == label) if label else result.interaction.options[index]
    return entry(reads, saver).resume(context, {"selected_option_id": option.id,
        "interaction_id": result.interaction.interaction_id}, thread_id="thread1")


def payload(result, model=AnomalyResult):
    return model.model_validate(result.data.model_dump() if hasattr(result.data, "model_dump") else result.data)


def test_unknown_charge_followup_reuses_scope_and_existing_locate_flow():
    from app.contracts.bills import BillScope
    reads, saver = Reads([transaction()], accounts=("a1",)), Saver()
    result = entry(reads, saver).start(CTX,
        StartTransferInput(request_id=uuid4(), intent_text="核对陌生扣款"), thread_id="thread1",
        inherited_scope=BillScope(account_ids=["a1"], start_at=START, end_at=END))
    assert result.status == "succeeded"
    assert payload(result).transaction.transaction_id == "p"
    assert any(call[0] == "transactions" for call in reads.calls)


def test_separate_registered_l02_keeps_the_frozen_l01_definition():
    before = MANIFEST.model_dump(mode="json")
    registry = CapabilityRegistry()
    register_bills(registry, lambda *_: Reads(), lambda: NOW)
    register_bills_anomalies(registry, lambda *_: Reads(), lambda: NOW)
    assert [item["name"] for item in registry.public_catalog()] == ["bills.summarize", "bills.detect_anomalies"]
    assert MANIFEST.model_dump(mode="json") == before
    assert ANOMALY_MANIFEST.dependencies == ["bank_gateway", "security"]
    definition = registry.get("bills.detect_anomalies").definition
    assert definition.input_schema_ref == "DetectAnomaliesInput"
    assert definition.output_schema_ref == "AnomalyResult"
    assert definition.required_permissions == ["bills.read"]
    assert definition.operation_level == "read" and not definition.side_effect
    assert definition.confirmation_policy == "none" and definition.retry_policy == "read_only"
    assert registry.get("bills.detect_anomalies").factory != registry.get("bills.summarize").factory


def test_missing_mode_month_and_even_single_account_are_explicit_choices():
    reads, saver = Reads([transaction()], accounts=("a1",)), Saver()
    result = start(reads, saver, "看看账单")
    assert result.status == "waiting_input" and reads.calls == []
    result = choose(reads, saver, result, "核对一笔交易")
    assert result.status == "waiting_input" and reads.calls == []
    result = choose(reads, saver, result, "上月")
    assert result.status == "waiting_input" and {call[0] for call in reads.calls} == {"accounts"}
    result = choose(reads, saver, result, "账户0 · ****0000")
    assert result.status == "succeeded" and payload(result).transaction.transaction_id == "p"


def test_multi_candidate_waits_and_maps_saved_option_ids_after_entry_recreation():
    rows = [transaction("first"), transaction("second", at=START + timedelta(days=1))]
    reads, saver = Reads(rows, accounts=("a1",)), Saver()
    result = start(reads, saver, "核对这笔500元，2026年9月所有账户")
    assert result.status == "waiting_input" and isinstance(result.data, TransactionCandidates)
    assert [row.transaction_id for row in result.data.candidates] == ["first", "second"]
    assert len(result.interaction.options) == 2
    for option in result.interaction.options:
        assert str(UUID(option.id)) == option.id and option.id not in {"first", "second"}
    assert len([call for call in reads.calls if call[0] == "transactions"]) == 1
    result = choose(reads, saver, result, index=1, context=CTX.model_copy(update={"run_id": "r2"}))
    assert result.task_id == CTX.task_id and result.run_id == "r2" and result.status == "succeeded"
    assert payload(result).transaction.transaction_id == "second"
    assert "500.00" in result.message and "正常商户" in result.message and "渠道：未知" in result.message
    assert "2026-09-02 00:00:00" in result.message


def test_selection_reloads_bank_facts_instead_of_using_stored_display_values():
    first, second = transaction("first"), transaction("second", at=START + timedelta(days=1))
    reads, saver = Reads([first, second], accounts=("a1",)), Saver()
    result = start(reads, saver)
    changed = second.model_copy(update={"amount_fen": 60000, "counterparty_name": "更新后的银行商户", "channel": "银行卡"})
    reads.rows = [first, changed]
    result = choose(reads, saver, result, index=1)
    assert result.status == "succeeded" and payload(result).transaction == changed
    assert "600.00" in result.message and "更新后的银行商户" in result.message and "渠道：银行卡" in result.message


@pytest.mark.parametrize("response", [
    {"selected_option_id": "forged"}, {"account_id": "a1", "transaction_id": "first"},
    {"verified": True}, {"choice": "current", "amount_fen": 1},
    {"choice": "current", "selected_option_id": "another"},
    {"choice": "current", "interaction_id": "expired"},
])
def test_forged_or_stale_f10_answers_never_change_selection_or_read_bank(response):
    reads, saver = Reads([transaction("first"), transaction("second")], accounts=("a1",)), Saver()
    result = start(reads, saver)
    response = {key: result.interaction.options[0].id if value == "current" else value for key, value in response.items()}
    before = len(reads.calls), saver.writes
    with pytest.raises(ValueError):
        entry(reads, saver).resume(CTX, response, thread_id="thread1")
    assert (len(reads.calls), saver.writes) == before


def test_empty_candidates_keep_same_task_and_clear_clues_only_after_explicit_choice():
    reads, saver = Reads([transaction()], accounts=("a1",)), Saver()
    result = start(reads, saver, "这笔1元，2026年9月所有账户")
    assert result.status == "waiting_input" and result.data.candidates == []
    assert "不代表没有异常" in result.message
    result = choose(reads, saver, result, "去掉线索，列出原范围流水")
    assert result.status == "succeeded" and result.task_id == CTX.task_id
    assert payload(result).transaction.amount_fen == 50000
    assert all(call[2:4] == (START, END) for call in reads.calls if call[0] == "transactions" and call[2] == START)


def test_model_transfer_fields_cannot_supply_account_or_amount_facts():
    reads, saver = Reads([transaction()], accounts=("a1",)), Saver()
    result = start(reads, saver, "核对交易，2026年9月", payer_account_id="foreign", amount_fen=1,
                   payee_hint="untrusted-model-merchant")
    assert result.status == "waiting_input" and {call[0] for call in reads.calls} == {"accounts"}
    result = choose(reads, saver, result, "账户0 · ****0000")
    assert payload(result).transaction.amount_fen == 50000
    assert payload(result).transaction.account_id == "a1"
    assert "untrusted-model-merchant" not in str(saver.saved.checkpoint)


def test_partial_account_failure_waits_without_returning_partial_candidates():
    reads, saver = Reads([transaction()], accounts=("a1", "a2")), Saver()
    reads.failure = lambda account, *_: account == "a2"
    result = start(reads, saver)
    assert result.status == "waiting_input" and result.data is None
    assert "完整银行流水" in result.message
    reads.failure = None
    result = choose(reads, saver, result, "重新读取原范围")
    assert result.status == "succeeded" and result.task_id == CTX.task_id


def test_request_replay_conflict_cancellation_and_terminal_state():
    reads, saver = Reads(), Saver()
    request = StartTransferInput(request_id=uuid4(), intent_text="看看账单")
    first = entry(reads, saver).start(CTX, request, thread_id="thread1")
    second = entry(reads, saver).start(CTX, request, thread_id="thread1")
    assert first == second and reads.calls == []
    with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
        entry(reads, saver).start(CTX, request.model_copy(update={"intent_text": "另一笔"}), thread_id="thread1")
    cancelled = entry(reads, saver).resume(CTX, {"cancel": True}, thread_id="thread1")
    assert cancelled.status == "cancelled"
    replay = choose(reads, saver, first)
    assert replay.status == "cancelled" and reads.calls == []


def test_cross_session_requires_recovery_and_invalidates_candidate_options():
    reads, saver = Reads([transaction("first"), transaction("second")], accounts=("a1",)), Saver()
    original = start(reads, saver)
    current = CTX.model_copy(update={"session_id": "s2", "run_id": "r2"})
    with pytest.raises(PermissionError):
        choose(reads, saver, original, context=current)
    moved = entry(reads, saver).recover_session(current, source_session_id="s1", thread_id="thread1")
    assert moved.task_id == CTX.task_id and moved.status == "waiting_input"
    with pytest.raises(ValueError):
        choose(reads, saver, original, context=current)
    result = choose(reads, saver, moved, "继续原范围", context=current)
    assert result.status == "waiting_input" and isinstance(result.data, TransactionCandidates)
    assert not {option.id for option in original.interaction.options} & {option.id for option in result.interaction.options}


@pytest.mark.parametrize("changed", [{"user_id": "other"}, {"demo_round_id": "old"}, {"task_id": "other-task"}])
def test_checkpoint_actor_is_not_an_id_only_access_token(changed):
    reads, saver = Reads(), Saver()
    result = start(reads, saver, "看看账单")
    with pytest.raises(PermissionError):
        choose(reads, saver, result, context=CTX.model_copy(update=changed))
    assert reads.calls == []


def test_multiple_or_excluded_amounts_require_a_choice_before_bank_reads():
    for text in ["这笔100元或200元", "这笔不是100元", "这笔-100元", "这笔1,000元",
                 "这笔1e3元", "这笔10.001元", "这笔大于100元", "这笔100-200元",
                 "这笔1，000元", "这笔100元50分"]:
        reads, saver = Reads(), Saver()
        result = start(reads, saver, text + "，2026年9月所有账户")
        assert result.status == "waiting_input" and reads.calls == []
        assert "歧义" in result.message


def test_quoted_merchant_content_is_only_a_hint_not_an_amount_or_category():
    target = transaction().model_copy(update={"counterparty_name": "100元购物商店"})
    reads, saver = Reads([target], accounts=("a1",)), Saver()
    result = start(reads, saver, "商户是“100元购物商店”，2026年9月所有账户")
    assert result.status == "succeeded", result
    assert payload(result).transaction == target


def test_merchant_literal_cannot_select_all_accounts_month_or_scan_mode():
    target = transaction().model_copy(update={"counterparty_name": "所有账户2026年9月周期扣款商店"})
    reads, saver = Reads([target], accounts=("a1",)), Saver()
    result = start(reads, saver, "商户是“所有账户2026年9月周期扣款商店”")
    assert result.status == "waiting_input" and reads.calls == []
    assert "查询范围" in result.message
    result = choose(reads, saver, result, "上月")
    assert result.status == "waiting_input" and {call[0] for call in reads.calls} == {"accounts"}
    result = choose(reads, saver, result, "账户0 · ****0000")
    assert result.status == "succeeded" and payload(result).transaction == target


def test_future_month_uses_bank_cutoff_and_requires_a_new_scope():
    reads, saver = Reads(), Saver()
    result = start(reads, saver, "核对交易，2026年11月所有账户")
    assert result.status == "waiting_input" and result.data is None
    assert [option.label for option in result.interaction.options] == ["重新选择月份"]


def test_conflicting_explicit_and_relative_periods_are_clarified_without_reads():
    reads, saver = Reads(), Saver()
    result = start(reads, saver, "所有账户2026年8月最近三个完整月份检查周期扣款")
    assert result.status == "waiting_input" and reads.calls == []
    assert "查询范围" in result.message


@pytest.mark.parametrize("period", [
    "2026年9月上半月", "2026年9月和10月", "本月和9月", "2026年9月12日",
    "2026-09-12", "2026年9月下旬", "2026年9月月底", "上个月和2026年8月",
])
def test_partial_days_and_second_month_are_not_silently_replaced_by_one_full_month(period):
    reads, saver = Reads(), Saver()
    result = start(reads, saver, period + "所有账户核对交易")
    assert result.status == "waiting_input" and reads.calls == []
    assert "完整月份" in result.message


@pytest.mark.parametrize("count, status, model", [
    (1, "succeeded", AnomalyResult), (2, "waiting_input", TransactionCandidates),
    (0, "waiting_input", TransactionCandidates),
])
def test_direct_replay_keeps_public_data_type_ids_and_does_not_read_or_checkpoint(count, status, model):
    reads = Reads([transaction(str(index)) for index in range(count)], accounts=("a1",))
    saver = Saver()
    request = StartTransferInput(request_id=uuid4(), intent_text="核对交易，2026年9月所有账户")
    first = entry(reads, saver).start(CTX, request, thread_id="thread1")
    assert first.status == status and isinstance(first.data, model)
    before = list(reads.calls), saver.writes
    current = CTX.model_copy(update={"run_id": "r2"})
    replay = entry(reads, saver).start(current, request, thread_id="thread1")
    resumed = entry(reads, saver).resume(current, {}, thread_id="thread1")
    for result in (replay, resumed):
        assert isinstance(result.data, model) and result.data == first.data
        assert result.task_id == first.task_id and result.run_id == "r2"
        assert result.interaction == first.interaction
    assert (reads.calls, saver.writes) == before


def test_replayed_checkpoint_with_a_drifted_result_fails_with_controlled_error():
    reads, saver = Reads([transaction()], accounts=("a1",)), Saver()
    request = StartTransferInput(request_id=uuid4(), intent_text="核对交易，2026年9月所有账户")
    assert entry(reads, saver).start(CTX, request, thread_id="thread1").status == "succeeded"
    # An older checkpoint shape must not raise pydantic errors into the harness.
    drifted = deepcopy(saver.saved)
    drifted.checkpoint["channel_values"]["bills_anomaly_state"]["result"]["data"] = {"unexpected": True}
    saver.saved = drifted
    replay = entry(reads, saver).start(CTX, request, thread_id="thread1")
    assert replay.status == "failed" and replay.data is None
    assert replay.error.code == "BILLS_RESULT_INVALID"


def test_secret_input_is_rejected_without_saving_raw_text():
    reads, saver = Reads(), Saver()
    result = start(reads, saver, "验证码123456，核对交易")
    assert result.error.code == "INVALID_ARGUMENT" and saver.saved is None and reads.calls == []


def test_scan_runs_only_rule4_in_explicit_three_complete_month_scope():
    rows = [transaction(str(month), amount=3900,
              at=datetime(2026, month, 10, 12, tzinfo=START.tzinfo)) for month in (7, 8, 9)]
    reads, saver = Reads(rows, accounts=("a1",)), Saver()
    result = start(reads, saver, "所有账户最近三个完整月份检查周期扣款")
    assert result.status == "succeeded" and payload(result).transaction is None
    assert [check.rule_id for check in payload(result).checks] == [4]
    assert len(payload(result).findings) == 1
    assert result.allowed_actions == []
    assert {call[0] for call in reads.calls} == {"accounts", "transactions"}
