"""Scenario-05 golden evaluations over the real platform runtime.

Every case drives the platform composition in ``harness.py``: real mock bank B29/B30 and
seeded facts, the real security gate, shared executor, audit journal, stores and demo
policy, plus the module's own checkpointed state machine. Only the model entry is a
scripted stand-in — these cases pin deterministic routing, money-safety and wording, not
model quality. HTTP-level cases (F05/F06/F07/F10) live in ticket 06's API suite.

Run: ``pytest evals/subscription -q``; evidence: ``evals/subscription/evidence/<date>/``.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.contracts.common import RiskLevel, TaskStatus

import harness
from harness import (
    CANCEL_CAPABILITY, CANCEL_PROMISE, LIST_CAPABILITY, approve, bank_operations,
    billing_date, cancel_to_success, confirmation_for, events, mandate, mandate_status,
    security_confirmations, start, texts, trusted, verify_by_code,
)


HERE = Path(__file__).resolve().parent
GOLDEN = json.loads((HERE / "golden_cases.json").read_text(encoding="utf-8"))
CASES = {case["case_id"]: case for case in GOLDEN["cases"]}
# The bank's demo code is six digits starting at 1, so this is never the real code.
WRONG_CODE = "000000"


def begin(store, request, case_id):
    case = CASES[case_id]
    log = harness.CheckLog(case["case_id"], case["scenario"], case["dimension"],
                           nodeid=request.node.nodeid)
    store["reports"].append(log)
    return case, log


def step_label(result) -> str:
    """The state the case's expected sequence talks about: status[:interaction]."""

    if result.status in {TaskStatus.WAITING_APPROVAL, TaskStatus.WAITING_INPUT} \
            and result.interaction is not None:
        return f"{result.status.value}:{result.interaction.kind}"
    return result.status.value


def assert_envelope(log, case, comp, result, *, task="T1", produced) -> None:
    """Every case's cross-cutting contract: route, state, bank truth and wording."""

    expected = case["expected"]
    record = comp.application.get_task("U1", "D1", task)
    log.eq("route.capability", record.snapshot.get("capability_name"), expected["capability"])
    log.eq("final.status", result.status.value, expected["final_status"])
    kind = result.interaction.kind if result.interaction is not None else None
    log.eq("final.interaction", kind, expected["interaction"])
    log.eq("bank.operations", bank_operations(comp.bank), expected["bank_operations"])
    for mandate_id, status in expected["mandates"].items():
        log.eq(f"mandate.{mandate_id}.status", mandate_status(comp.bank, mandate_id), status)
    confirmations = security_confirmations(comp, task)
    if expected.get("requires_confirmation") is None:
        log.note("cross-flow case: confirmation use is asserted in the case body")
    elif expected["requires_confirmation"]:
        log.ok("gate.confirmation_used", confirmations >= 1, confirmations)
    else:
        log.eq("gate.no_confirmation", confirmations, 0)
    joined = " | ".join(produced)
    for needle in expected["required_text"]:
        log.ok(f"text.required[{needle}]", needle in joined, {"needle": needle})
    for needle in expected["forbidden_text"]:
        log.ok(f"text.forbidden[{needle}]", needle not in joined, {"needle": needle})


def confirmation_texts(record) -> list[str]:
    return [f"{field.label}：{field.value_text}" for field in record.display_fields]


# ------------------------------------------------------------------- SUB-INV 盘点


def test_sub_inv_01_inventory_and_reminder(subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-INV-01")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    result = start(comp, case["intent"], capability=LIST_CAPABILITY)

    view = result.data
    log.eq("state.sequence", [step_label(result)], case["expected"]["state_sequence"])
    log.eq("view.action", view.action, "list")
    listed = {item.subscription_id: item for item in view.list_result.items}
    log.eq("list.mandate_ids",
           [item.subscription_id for item in view.list_result.items
            if item.source_type == "mandate"], facts["mandate_ids"])
    log.eq("list.active_count", view.list_result.active_count, facts["active_count"])
    upcoming = [item.subscription_id for item in view.list_result.upcoming_renewals]
    log.eq("list.upcoming_ids", upcoming, facts["upcoming_ids"])
    log.eq("list.upcoming_total_fen", view.list_result.upcoming_total_fen,
           facts["upcoming_total_fen"])
    youku = listed["sub_001"]
    log.eq("youku.billed", [youku.billed_count, youku.billed_total_fen],
           [facts["youku_billed_count"], facts["youku_billed_total_fen"]])
    log.eq("sub_003.not_upcoming", "sub_003" not in upcoming, True)

    clues = [item for item in view.list_result.items if item.source_type == "suspected_ledger"]
    oasis = next((item for item in clues if item.merchant_name == "绿洲健身"), None)
    log.ok("clue.oasis_present", oasis is not None, [item.merchant_name for item in clues])
    log.eq("clue.oasis_can_cancel_in_bank", oasis.can_cancel_in_bank,
           facts["oasis_can_cancel_in_bank"])
    # The total is deliberately not locked: the shared demo ledger matches the contract
    # rule for rent, utilities, canteen, bus and clinic too, which is correct behaviour.
    log.ok("clue.others_are_clues_only",
           all(item.status == "suspected" and item.mandate_id is None
               and not item.can_cancel_in_bank for item in clues), len(clues))
    log.ok("clue.sub_003_not_a_clue",
           all(item.subscription_id != "sub_003" for item in clues), None)
    log.eq("gate.after_inventory", comp.runtime.gateway.list_verifications(trusted(), "T1"), [])
    assert_envelope(log, case, comp, result, produced=texts(result))


def test_sub_inv_02_insufficient_data_is_not_reported_as_clean(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-INV-02")
    facts = case["expected"]["facts"]
    comp = subscription_runtime(seed_flows=False)
    result = start(comp, case["intent"], capability=LIST_CAPABILITY)

    view = result.data
    log.eq("state.sequence", [step_label(result)], case["expected"]["state_sequence"])
    log.eq("scan.status", view.list_result.suspected_scan_status, facts["suspected_scan_status"])
    log.ok("scan.reason", "不足 3 个月" in (view.list_result.suspected_scan_reason or ""),
           view.list_result.suspected_scan_reason)
    log.eq("scan.suspected_items",
           [item.subscription_id for item in view.list_result.items
            if item.source_type == "suspected_ledger"], [])
    log.eq("list.mandate_ids",
           [item.subscription_id for item in view.list_result.items
            if item.source_type == "mandate"], facts["mandate_ids"])
    log.eq("list.upcoming_count", len(view.list_result.upcoming_renewals), 2)
    assert_envelope(log, case, comp, result, produced=texts(result))


# ------------------------------------------------------------------ SUB-CAN 退订


def test_sub_can_01_single_cancel_full_chain(subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-01")
    expected, facts = case["expected"], case["expected"]["facts"]
    comp = subscription_runtime()
    started = start(comp, case["intent"], capability=CANCEL_CAPABILITY)
    sequence = [step_label(started)]

    log.eq("gate.first_step", sequence[0], "waiting_approval:confirmation")
    log.eq("bank.operations_after_start", bank_operations(comp.bank), 0)
    record = confirmation_for(comp, trusted(), started)
    fields = {field.name: field.value_text for field in record.display_fields}
    log.eq("confirmation.field_names", list(fields), facts["display_field_names"])
    # Exact equality, not a substring: an extra promise sentence in the notice field
    # ("会员可以继续享受到本期末") is exactly what the PRD forbids.
    log.eq("confirmation.promise",
           fields["notice"], CANCEL_PROMISE.format(date=facts["effective_stop_date"]) + "。")

    approve(comp, trusted(), started)
    verification = comp.runtime.harness.resume(trusted(run="R2"), {"choice": "approve"})
    sequence.append(step_label(verification))
    log.eq("gate.second_step", sequence[-1], "waiting_approval:verification")
    challenge = comp.runtime.gateway.get_verification(
        trusted(run="R2"), verification.interaction.record_ref)
    log.eq("verification.purpose", challenge.purpose, expected["verification"]["purpose"])
    log.eq("verification.required_methods", challenge.required_methods,
           expected["verification"]["required_methods"])
    log.ok("verification.no_summary", challenge.summary is None, bool(challenge.summary))
    log.ok("verification.no_mock_face", challenge.face_result == "not_required", challenge.face_result)
    log.eq("bank.operations_before_code", bank_operations(comp.bank), 0)

    verified = verify_by_code(comp, trusted(run="R2"), challenge.challenge_id)
    log.ok("verification.record_created", verified.verification_id is not None, verified.kind)
    verification_record = comp.runtime.gateway.get_verification_record(
        trusted(run="R2"), verified.verification_id)
    log.eq("verification.scope", verification_record.scope, expected["verification"]["scope"])
    log.eq("verification.methods", verification_record.methods, ["code"])
    comp.runtime.bind_verification(trusted(run="R2"), verified.verification_id)

    done = comp.runtime.harness.resume(trusted(run="R3"), {})
    sequence.append(step_label(done))
    log.eq("state.sequence", sequence, expected["state_sequence"])
    view = done.data
    receipt = view.operation.receipt
    log.eq("receipt.mandate_id", receipt.mandate_id, facts["receipt_mandate_id"])
    log.eq("receipt.status", receipt.status, facts["receipt_status"])
    log.ok("receipt.stop_is_bank_date",
           receipt.effective_stop_at == receipt.previous_next_billing_at
           and receipt.effective_stop_at.date().isoformat() == facts["effective_stop_date"],
           receipt.effective_stop_at.isoformat())
    log.eq("receipt.operation_status", view.operation.operation_status, "succeeded")
    log.eq("view.selected_item.status", view.selected_item.status, "cancelled")

    replay = comp.runtime.harness.resume(trusted(run="R4"), {})
    log.eq("replay.status", replay.status.value, "succeeded")
    log.eq("replay.one_operation", bank_operations(comp.bank), 1)
    assert_envelope(log, case, comp, done,
                    produced=texts(started, verification, done, confirmation_texts(record)))


def test_sub_can_02_second_cancel_reuses_the_session_verification(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-02")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    first = cancel_to_success(comp, "把优酷视频自动扣费退了")
    log.eq("first.status", first.status.value, "succeeded")

    second = start(comp, case["intent"], task="T2", run="R10", capability=CANCEL_CAPABILITY)
    sequence = [step_label(second)]
    log.eq("second.confirmation_again", sequence[0], "waiting_approval:confirmation")
    approve(comp, trusted("T2", "R10"), second)
    done = comp.runtime.harness.resume(trusted("T2", "R11"), {"choice": "approve"})
    sequence.append(step_label(done))
    log.eq("state.sequence", sequence, case["expected"]["state_sequence"])
    log.eq("second.no_new_challenge",
           comp.runtime.gateway.list_verifications(trusted("T2", "R11"), "T2"), [])
    log.eq("second.selected", done.data.selected_item.subscription_id, facts["second_task_selected"])
    log.eq("bank.operations_total", bank_operations(comp.bank), 2)
    assert_envelope(log, case, comp, done, task="T2", produced=texts(second, done))


# ------------------------------------------------------------------ SUB-GUD 引导


def test_sub_gud_01_suspected_clue_is_guided_outside(subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-GUD-01")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    result = start(comp, case["intent"], capability=CANCEL_CAPABILITY)

    log.eq("state.sequence", [step_label(result)], case["expected"]["state_sequence"])
    item = result.data.selected_item
    log.eq("guide.source_type", item.source_type, facts["selected_source_type"])
    log.eq("guide.can_cancel_in_bank", item.can_cancel_in_bank, facts["selected_can_cancel_in_bank"])
    log.ok("guide.no_interaction", result.interaction is None, None)
    assert_envelope(log, case, comp, result, produced=texts(result))


# --------------------------------------------------------------- SUB-DIS 消歧批量


def test_sub_dis_01_batch_refused_then_one_choice_confirms(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-DIS-01")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = start(comp, case["intent"], capability=CANCEL_CAPABILITY)

    sequence = [step_label(started)]
    log.eq("first.step", sequence[0], "waiting_input:input")
    log.eq("batch.option_ids", [option.id for option in started.interaction.options],
           facts["option_ids"])
    log.eq("batch.confirmations_before_choice",
           security_confirmations(comp, "T1"), facts["confirmations_before_choice"])
    log.eq("batch.operations_before_choice", bank_operations(comp.bank), 0)

    chosen = comp.runtime.harness.resume(trusted(run="R2"),
                                         {"selected_option_id": facts["chosen_option"]})
    sequence.append(step_label(chosen))
    log.eq("state.sequence", sequence, case["expected"]["state_sequence"])
    log.eq("chosen.interaction", chosen.interaction.kind, "confirmation")
    record = confirmation_for(comp, trusted("T1", "R2"), chosen)
    log.ok("chosen.confirmation_is_the_selected_item",
           record.display_fields[0].value_text.startswith("优酷视频"),
           record.display_fields[0].value_text)
    log.eq("chosen.operations", bank_operations(comp.bank), 0)
    assert_envelope(log, case, comp, chosen,
                    produced=texts(started, chosen, confirmation_texts(record)))


# ------------------------------------------------------------------- SUB-IDM 幂等


def test_sub_idm_01_already_cancelled_is_idempotent(subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-IDM-01")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    result = start(comp, case["intent"], capability=CANCEL_CAPABILITY)

    log.eq("state.sequence", [step_label(result)], case["expected"]["state_sequence"])
    log.eq("idempotent.selected", result.data.selected_item.subscription_id, facts["selected"])
    log.eq("idempotent.confirmations", security_confirmations(comp, "T1"),
           facts["security_confirmations"])
    assert_envelope(log, case, comp, result, produced=texts(result))


def test_sub_idm_02_user_cancel_leaves_the_mandate_alone(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-IDM-02")
    comp = subscription_runtime()
    started = start(comp, case["intent"], capability=CANCEL_CAPABILITY)
    log.eq("first.step", step_label(started), "waiting_approval:confirmation")
    confirmation_for(comp, trusted(), started)

    cancelled = comp.runtime.harness.resume(trusted(run="R2"), {"cancel": True})
    log.eq("state.sequence", [step_label(started), step_label(cancelled)],
           case["expected"]["state_sequence"])
    log.eq("cancel.task_status", cancelled.status.value, case["expected"]["facts"]["task_status"])
    log.ok("cancel.no_interaction", cancelled.interaction is None, None)
    assert_envelope(log, case, comp, cancelled, produced=texts(started, cancelled))


# ------------------------------------------------------------------- SUB-VFY 验证


def test_sub_vfy_01_three_wrong_codes_end_with_the_verification_wording(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-VFY-01")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = start(comp, case["intent"], capability=CANCEL_CAPABILITY)
    approve(comp, trusted(), started)
    verification = comp.runtime.harness.resume(trusted(run="R2"), {"choice": "approve"})
    challenge_id = verification.interaction.record_ref
    sequence = [step_label(started), step_label(verification)]

    attempts = []
    for index in range(3):
        outcome = comp.runtime.gateway.verify_code(
            trusted(run="R2"), challenge_id, uuid4(), WRONG_CODE)
        attempts.append(outcome.challenge.consecutive_code_failures)
        log.ok(f"verification.attempt_{index + 1}_rejected", outcome.verification_id is None,
               outcome.reason_code)
    log.eq("verification.attempts", attempts, [1, 2, 3])

    failed = comp.runtime.harness.resume(trusted(run="R3"), {"choice": "approve"})
    sequence.append(step_label(failed))
    log.eq("state.sequence", sequence, case["expected"]["state_sequence"])
    log.eq("error.code", failed.error.code, facts["error_code"])
    log.eq("error.source", failed.error.source, "security")
    log.eq("error.upstream", failed.error.upstream_code, facts["upstream_code"])
    log.ok("wording.not_coercion",
           "共享屏幕" not in failed.message and "挂断" not in failed.message, failed.message)
    log.ok("audit.terminal_reason",
           any(event.event_type == "security.decided"
               and event.payload.decision.reason_codes == [facts["audit_reason"]]
               for event in events(comp)), None)
    log.eq("repeat.still_failed",
           comp.runtime.harness.resume(trusted(run="R4"), {}).status.value, "failed")
    assert_envelope(log, case, comp, failed, produced=texts(started, verification, failed))


def test_sub_vfy_02_coercion_blocks_without_any_bank_call(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-VFY-02")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    result = start(comp, case["intent"], capability=CANCEL_CAPABILITY)

    log.eq("state.sequence", [step_label(result)], case["expected"]["state_sequence"])
    log.eq("error.code", result.error.code, facts["error_code"])
    log.eq("error.source", result.error.source, "security")
    log.eq("error.upstream", result.error.upstream_code, facts["upstream_code"])
    log.eq("block.confirmations", security_confirmations(comp, "T1"),
           facts["security_confirmations"])
    log.ok("audit.high_risk",
           any(event.event_type == "security.decided"
               and event.payload.decision.reason_codes == [facts["audit_reason"]]
               for event in events(comp)), None)
    assert_envelope(log, case, comp, result, produced=texts(result))


def test_sub_vfy_03_non_low_risk_is_never_downgraded(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-VFY-03")
    expected, facts = case["expected"], case["expected"]["facts"]
    comp = subscription_runtime()
    # The demo policy keeps cancellations low risk or blocked; this case pins the seam
    # that any other level still gets the action-scoped step-up, never the session code.
    comp.runtime.assess_risk = lambda *_: RiskLevel.MEDIUM
    started = start(comp, case["intent"], capability=CANCEL_CAPABILITY)
    log.eq("first.step", step_label(started), "waiting_approval:confirmation")
    approve(comp, trusted(), started)

    verification = comp.runtime.harness.resume(trusted(run="R2"), {"choice": "approve"})
    log.eq("state.sequence", [step_label(started), step_label(verification)],
           expected["state_sequence"])
    challenge = comp.runtime.gateway.get_verification(
        trusted(run="R2"), verification.interaction.record_ref)
    log.eq("verification.purpose", challenge.purpose, expected["verification"]["purpose"])
    log.eq("verification.required_methods", challenge.required_methods,
           expected["verification"]["required_methods"])
    log.ok("verification.summary_present", challenge.summary is not None, None)
    log.eq("summary.display_field_names",
           [field.name for field in challenge.summary.display_fields],
           facts["summary_display_field_names"])
    log.eq("summary.amount_fen", challenge.summary.amount_fen, facts["summary_amount_fen"])
    log.eq("summary.payee", challenge.summary.payee, facts["summary_payee"])
    assert_envelope(log, case, comp, verification, produced=texts(started, verification))


# ------------------------------------------------------------------- SUB-RED 红线


def test_sub_red_01_no_bank_write_before_confirmation_and_verification(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-RED-01")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = start(comp, case["intent"], capability=CANCEL_CAPABILITY)
    operations = [bank_operations(comp.bank)]
    confirmation_for(comp, trusted(), started)

    approve(comp, trusted(), started)
    verification = comp.runtime.harness.resume(trusted(run="R2"), {"choice": "approve"})
    operations.append(bank_operations(comp.bank))

    verified = verify_by_code(comp, trusted(run="R2"), verification.interaction.record_ref)
    unbound = comp.runtime.harness.resume(trusted(run="R3"), {"choice": "approve"})
    operations.append(bank_operations(comp.bank))
    log.eq("gate.unbound_still_waits", step_label(unbound), "waiting_approval:verification")

    comp.runtime.bind_verification(trusted(run="R2"), verified.verification_id)
    done = comp.runtime.harness.resume(trusted(run="R4"), {})
    operations.append(bank_operations(comp.bank))

    log.eq("state.sequence",
           [step_label(started), step_label(verification), step_label(unbound), step_label(done)],
           case["expected"]["state_sequence"])
    log.eq("gate.operations_after_each_step", operations,
           facts["bank_operations_after_each_step"])
    assert_envelope(log, case, comp, done,
                    produced=texts(started, verification, unbound, done))


def test_sub_red_02_suspected_and_cancelled_never_enter_the_gate(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-RED-02")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    suspected = start(comp, "帮我把绿洲健身的每月扣款退订", task="T1", run="R1",
                      capability=CANCEL_CAPABILITY)
    log.eq("suspected.confirmations", security_confirmations(comp, "T1"),
           facts["confirmations_suspected"])
    log.eq("suspected.writes", bank_operations(comp.bank), facts["writes_suspected"])
    cancelled = start(comp, "把喜马拉雅自动续费退了", task="T2", run="R2",
                      capability=CANCEL_CAPABILITY)
    log.eq("cancelled.confirmations", security_confirmations(comp, "T2"),
           facts["confirmations_cancelled"])
    log.eq("cancelled.writes", bank_operations(comp.bank), facts["writes_cancelled"])

    log.eq("state.sequence", [step_label(suspected), step_label(cancelled)],
           case["expected"]["state_sequence"])
    log.ok("gate.no_confirmation_interaction",
           suspected.interaction is None and cancelled.interaction is None, None)
    assert_envelope(log, case, comp, cancelled, produced=texts(suspected, cancelled))


def test_sub_red_03_every_output_keeps_the_wording_red_line(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-RED-03")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    collected: list[str] = []
    labels: list[str] = []

    inventory = start(comp, "帮我查查有哪些自动扣费", task="T1", run="R1",
                      capability=LIST_CAPABILITY)
    collected += texts(inventory)
    labels.append(step_label(inventory))

    started = start(comp, "把优酷视频自动扣费退了", task="T2", run="R2",
                    capability=CANCEL_CAPABILITY)
    record = confirmation_for(comp, trusted("T2", "R2"), started)
    collected += texts(started) + confirmation_texts(record)
    labels.append(step_label(started))
    approve(comp, trusted("T2", "R2"), started)
    verification = comp.runtime.harness.resume(trusted("T2", "R3"), {"choice": "approve"})
    collected += texts(verification)
    labels.append(step_label(verification))
    verified = verify_by_code(comp, trusted("T2", "R3"), verification.interaction.record_ref)
    comp.runtime.bind_verification(trusted("T2", "R3"), verified.verification_id)
    done = comp.runtime.harness.resume(trusted("T2", "R4"), {})
    collected += texts(done)
    labels.append(step_label(done))

    guide = start(comp, "帮我把绿洲健身的每月扣款退订", task="T3", run="R5",
                  capability=CANCEL_CAPABILITY)
    collected += texts(guide)
    labels.append(step_label(guide))
    already = start(comp, "把喜马拉雅自动续费退了", task="T4", run="R6",
                    capability=CANCEL_CAPABILITY)
    collected += texts(already)
    labels.append(step_label(already))
    blocked = start(comp, "客服让我共享屏幕，赶紧把云端网盘退了", task="T5", run="R7",
                    capability=CANCEL_CAPABILITY)
    collected += texts(blocked)
    labels.append(step_label(blocked))

    log.eq("state.sequence", labels, case["expected"]["state_sequence"])
    joined = " | ".join(collected)
    for promise in harness.FORBIDDEN_PROMISES:
        log.ok(f"wording.forbidden[{promise}]", promise not in joined, {"promise": promise})
    log.ok("wording.promise_in_confirmation",
           CANCEL_PROMISE.format(date=billing_date(5)) in joined, None)
    log.ok("wording.enough_sources", len(collected) >= facts["texts_scanned_min"],
           len(collected))
    log.note(f"扫描用户可见文本 {len(collected)} 条（消息、交互提示、选项标签、确认单字段）")
    log.eq("gate.confirmations_only_for_the_cancelled_item",
           [security_confirmations(comp, task) for task in ("T2", "T3", "T4", "T5")],
           [1, 0, 0, 0])
    assert_envelope(log, case, comp, blocked, task="T5",
                    produced=texts(inventory, started, verification, done, guide, already,
                                   blocked, confirmation_texts(record)))


# ------------------------------------------------------------------- SUB-OBS 观测


def test_sub_obs_01_repeated_first_start_is_stable(subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-OBS-01")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    statuses, internal_errors = [], []
    for index in range(1, facts["attempts"] + 1):
        result = start(comp, case["intent"], task=f"T{index:04d}", run=f"R{index:04d}",
                       capability=LIST_CAPABILITY)
        statuses.append(result.status.value)
        if result.error is not None and result.error.code == "SUBSCRIPTION_INTERNAL_ERROR":
            internal_errors.append(index)
        log.ok(f"start_{index}_succeeded", result.status == TaskStatus.SUCCEEDED,
               {"status": result.status.value,
                "error": result.error.code if result.error else None})
    log.eq("stability.attempts", len(statuses), facts["attempts"])
    log.eq("stability.statuses", sorted(set(statuses)), ["succeeded"])
    log.eq("stability.internal_errors", internal_errors, [])
    log.eq("stability.no_bank_write", bank_operations(comp.bank), 0)
    assert_envelope(log, case, comp, comp.runtime.harness.get(trusted("T0001", "R0001")),
                    task="T0001", produced=[])


def test_sub_obs_02_terminal_task_stays_terminal_and_serializable(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-OBS-02")
    comp = subscription_runtime()
    blocked = start(comp, case["intent"], capability=CANCEL_CAPABILITY)
    statuses = [blocked.status.value]
    fetched = comp.runtime.harness.get(trusted())
    statuses.append(fetched.status.value)
    statuses.append(comp.runtime.harness.resume(trusted(run="R2"), {}).status.value)
    statuses.append(comp.runtime.harness.resume(trusted(run="R3"), {}).status.value)

    log.eq("terminal.statuses", statuses, case["expected"]["state_sequence"])
    log.ok("terminal.data_shape", fetched.data is None or isinstance(fetched.data, dict),
           type(fetched.data).__name__)
    payload = json.dumps(fetched.model_dump(mode="json"), ensure_ascii=False)
    log.ok("terminal.serializable", "failed" in payload and len(payload) > 0, len(payload))
    log.eq("terminal.operations", bank_operations(comp.bank), 0)
    assert_envelope(log, case, comp, fetched, produced=[])


def test_sub_obs_03_audit_events_name_their_module(subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-OBS-03")
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    done = cancel_to_success(comp, case["intent"])

    modules: dict[str, set] = {}
    for event in events(comp):
        modules.setdefault(event.event_type, set()).add(event.module)
    log.eq("audit.confirmation_changed",
           sorted(modules.get("confirmation.changed", set())),
           [facts["confirmation_changed_module"]])
    log.eq("audit.verification_changed",
           sorted(modules.get("verification.changed", set())),
           [facts["verification_changed_module"]])
    log.eq("audit.tool_events",
           sorted(modules.get("tool.started", set()) | modules.get("tool.finished", set())),
           [facts["tool_events_module"]])
    log.eq("audit.security_decided", sorted(modules.get("security.decided", set())),
           [facts["security_decided_module"]])
    assert_envelope(log, case, comp, done, produced=texts(done))
