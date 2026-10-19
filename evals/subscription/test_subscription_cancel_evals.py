"""Scenario-05 cancellation-side evaluations: disambiguation, verification borders,
idempotency, confirmation invalidation, audit and redaction.

Every case drives the platform composition in ``harness.py`` (real mock bank B29/B30 and
seeded facts, real security gate/executor/audit/stores, real demo policy, the module's
own checkpointed state machine); only the model entry is a scripted stand-in. The
machine-readable expectation for each case is the ``golden_cases.json`` entry, and each
test asserts those facts directly — the two must never drift apart.

Covered here: E01/T12 disambiguation (text and menu), E05 cancellation points, E08 batch
refusal, E10 verification borders, T11/E07 repeated confirm, T13 terminal replay,
SOP-3 missing-date refusal, §5.2 confirmation invalidation across sessions, §5.10 audit
chain and §5.6 redaction. Cross-user isolation and inventory/reminder cases live in
``test_subscription_read_evals.py``; the cancel success path, red lines, unknown-result
recovery and observation cases live in ``test_subscription_evals.py``.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.contracts.security import ConfirmationAnswer

import harness
from harness import (
    CANCEL_CAPABILITY, approve, assert_envelope, begin, begin_cancel,
    cancel_operations, confirmation_for, confirmation_texts, events, insert_mandate,
    load_cases, mandate_status, owner, recover_to_new_session, resume,
    security_confirmations, start, step_label, texts, update_mandate, verify_by_code,
)


CASES = load_cases()
WRONG_CODE = "000000"


def _confirmation_answer(record):
    return ConfirmationAnswer(
        confirmation_id=record.confirmation_id,
        confirmation_version=record.confirmation_version, choice="approve")


def _chosen_mandate(comp, task, parameters_ref):
    """The mandate the frozen confirmation actually bound (never inferred from text)."""

    payload = comp.runtime.subscription.binding(task, parameters_ref)
    return payload["mandate_id"] if payload else None


# ------------------------------------------------------------------- 消歧与批量


def test_sub_eval_27_text_disambiguation(subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-03", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = start(comp, case["intent"], capability=CANCEL_CAPABILITY)

    log.eq("first.step", step_label(started), "waiting_input:input")
    log.eq("menu.option_ids", [option.id for option in started.interaction.options],
           facts["option_ids"])
    log.eq("menu.before_choice.confirmations", security_confirmations(comp, "T1"),
           facts["confirmations_before_choice"])
    log.eq("menu.before_choice.bank_operations", cancel_operations(comp.bank), 0)

    typed = harness.typed_answer(comp, "T1", "R2", facts["typed"])
    log.eq("typed.step", step_label(typed), "waiting_approval:confirmation")
    record = confirmation_for(comp, owner(comp, "T1", "R2"), typed)
    log.ok("typed.confirmation_is_the_named_item",
           record.display_fields[0].value_text.startswith("优酷视频"),
           record.display_fields[0].value_text)
    log.eq("typed.chosen", _chosen_mandate(comp, "T1", record.parameters_ref),
           facts["chosen"])
    log.eq("typed.bank_operations", cancel_operations(comp.bank), 0)
    assert_envelope(log, case, comp, typed,
                    produced=texts(started, typed, confirmation_texts(record)))


def test_sub_eval_28_batch_then_typed_merchant(subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-04", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = start(comp, case["intent"], capability=CANCEL_CAPABILITY)
    log.eq("first.step", step_label(started), "waiting_input:input")
    log.eq("batch.refusal.present", "每次只能退订一项" in (started.message or ""), True)

    typed = harness.typed_answer(comp, "T1", "R2", facts["typed"])
    log.eq("typed.step", step_label(typed), "waiting_approval:confirmation")
    record = confirmation_for(comp, owner(comp, "T1", "R2"), typed)
    log.ok("typed.confirmation_is_the_named_item",
           "优酷视频" in record.display_fields[0].value_text,
           record.display_fields[0].value_text)
    log.eq("typed.chosen", _chosen_mandate(comp, "T1", record.parameters_ref),
           facts["chosen"])
    log.eq("typed.confirmations_before_choice", 0, facts["confirmations_before_choice"])
    log.eq("typed.bank_operations", cancel_operations(comp.bank), 0)
    assert_envelope(log, case, comp, typed,
                    produced=texts(started, typed, confirmation_texts(record)))


def test_sub_eval_29_unknown_merchant_falls_back_to_menu(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-05", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = start(comp, case["intent"], capability=CANCEL_CAPABILITY)

    log.eq("first.step", step_label(started), "waiting_input:input")
    log.eq("menu.option_ids", [option.id for option in started.interaction.options],
           facts["option_ids"])
    log.eq("menu.no_default_first", started.status.value == "waiting_input",
           facts["no_default_first"])
    # Not defaulting to the first item is the point: nothing happened yet.
    log.eq("menu.confirmations", security_confirmations(comp, "T1"), 0)
    log.eq("menu.bank_operations", cancel_operations(comp.bank), 0)

    chosen = resume(comp, "T1", "R2", selected_option_id=facts["chosen"])
    log.eq("chosen.step", step_label(chosen), "waiting_approval:confirmation")
    record = confirmation_for(comp, owner(comp, "T1", "R2"), chosen)
    log.ok("chosen.is_the_selected_item",
           chosen.interaction.record_ref == record.confirmation_id, None)
    log.eq("chosen.mandate", _chosen_mandate(comp, "T1", record.parameters_ref),
           facts["chosen"])
    log.eq("chosen.bank_operations", cancel_operations(comp.bank), 0)
    assert_envelope(log, case, comp, chosen,
                    produced=texts(started, chosen, confirmation_texts(record)))


# ----------------------------------------------------------- 重复点击与验证边界


def test_sub_eval_30_repeated_confirm_clicks_execute_once(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-06", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = begin_cancel(comp, case["intent"], task="T1")
    record = confirmation_for(comp, owner(comp, "T1", "R1"), started)
    answer = _confirmation_answer(record)

    comp.runtime.answer_confirmation(owner(comp, "T1", "R1"), answer)
    again = comp.runtime.answer_confirmation(owner(comp, "T1", "R1"), answer)
    log.eq("clicks.same_record", again.confirmation_version,
           record.confirmation_version)
    log.eq("clicks.second_approve_same_record",
           again.confirmation_id == record.confirmation_id,
           facts["second_approve_same_record"])
    log.eq("clicks.one_confirmation_row", security_confirmations(comp, "T1"),
           facts["confirmation_rows"])

    verification = resume(comp, "T1", "R2", choice="approve")
    verified = verify_by_code(comp, owner(comp, "T1", "R2"),
                              verification.interaction.record_ref)
    comp.runtime.bind_verification(owner(comp, "T1", "R2"), verified.verification_id)
    done = resume(comp, "T1", "R3")
    replay = resume(comp, "T1", "R4")

    log.eq("state.sequence",
           [step_label(started), step_label(verification), step_label(done)],
           case["expected"]["state_sequence"])
    log.eq("done.status", done.status.value, "succeeded")
    log.eq("replay.status", replay.status.value, facts["replay_status"])
    log.eq("write.executed_once", cancel_operations(comp.bank), facts["cancel_operations"])
    assert_envelope(log, case, comp, replay,
                    produced=texts(started, verification, done, replay,
                                   confirmation_texts(record)))


def test_sub_eval_31_cancel_at_verification_stage(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-07", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = begin_cancel(comp, case["intent"], task="T1")
    approve(comp, owner(comp, "T1", "R1"), started)
    verification = resume(comp, "T1", "R2", choice="approve")

    cancelled = resume(comp, "T1", "R3", cancel=True)
    log.eq("state.sequence",
           [step_label(started), step_label(verification), step_label(cancelled)],
           case["expected"]["state_sequence"])
    log.eq("cancel.status", cancelled.status.value, "cancelled")
    log.eq("cancel.challenges_issued", len(comp.runtime.gateway.list_verifications(
        owner(comp, "T1", "R2"), "T1")), facts["challenges_issued"])
    log.eq("cancel.bank_operations", cancel_operations(comp.bank),
           facts["cancel_operations"])
    context = comp.runtime._context(owner(comp, "T1", "R3"),
                                    *harness.pending_binding(comp, "T1"))
    log.eq("cancel.verification_bound", bool(context.verification_ids),
           facts["verification_bound"])
    assert_envelope(log, case, comp, cancelled,
                    produced=texts(started, verification, cancelled))


def test_sub_eval_32_fourth_attempt_boundary(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-08", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = begin_cancel(comp, case["intent"], task="T1")
    approve(comp, owner(comp, "T1", "R1"), started)
    verification = resume(comp, "T1", "R2", choice="approve")
    challenge = verification.interaction.record_ref

    attempts = []
    for _ in range(3):
        outcome = comp.runtime.gateway.verify_code(
            owner(comp, "T1", "R2"), challenge, uuid4(), WRONG_CODE)
        attempts.append(outcome)
    log.eq("attempts.failures", [item.challenge.consecutive_code_failures
                                 for item in attempts], [1, 2, 3])
    log.eq("attempts.failures_recorded", attempts[-1].challenge.consecutive_code_failures,
           facts["failures_recorded"])
    log.ok("attempts.no_verification_record",
           all(item.verification_id is None for item in attempts),
           facts["no_verification_record"])
    log.eq("third.stops_the_challenge", attempts[-1].reason_code,
           "VERIFICATION_LIMIT_REACHED")
    with pytest.raises(ValueError) as fourth:
        comp.runtime.gateway.verify_code(owner(comp, "T1", "R2"), challenge,
                                         uuid4(), WRONG_CODE)
    log.ok("fourth.rejected", facts["fourth_attempt_error"] in str(fourth.value),
           str(fourth.value))

    failed = resume(comp, "T1", "R3", choice="approve")
    log.eq("state.sequence",
           [step_label(started), step_label(verification), step_label(failed)],
           case["expected"]["state_sequence"])
    log.eq("error.code", failed.error.code, facts["error_code"])
    log.eq("error.upstream", failed.error.upstream_code, facts["upstream_code"])
    log.eq("terminated.no_bank_call", cancel_operations(comp.bank),
           facts["cancel_operations"])
    assert_envelope(log, case, comp, failed,
                    produced=texts(started, verification, failed))


def test_sub_eval_33_two_wrong_codes_then_correct(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-09", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = begin_cancel(comp, case["intent"], task="T1")
    approve(comp, owner(comp, "T1", "R1"), started)
    verification = resume(comp, "T1", "R2", choice="approve")
    challenge = verification.interaction.record_ref
    for _ in range(facts["wrong_attempts"]):
        wrong = comp.runtime.gateway.verify_code(
            owner(comp, "T1", "R2"), challenge, uuid4(), WRONG_CODE)
        log.ok("wrong.keeps_the_challenge", wrong.challenge.challenge_status == "pending",
               wrong.challenge.challenge_status)
    good = verify_by_code(comp, owner(comp, "T1", "R2"), challenge)
    log.eq("recovered.verification_created", good.verification_id is not None,
           facts["verification_created"])
    comp.runtime.bind_verification(owner(comp, "T1", "R2"), good.verification_id)
    done = resume(comp, "T1", "R3")

    log.eq("state.sequence",
           [step_label(started), step_label(verification), step_label(done)],
           case["expected"]["state_sequence"])
    log.eq("done.status", done.status.value, "succeeded")
    log.eq("done.bank_operations", cancel_operations(comp.bank),
           facts["cancel_operations"])
    assert_envelope(log, case, comp, done,
                    produced=texts(started, verification, done))


# ------------------------------------------------------- 确认失效、幂等与边界


def test_sub_eval_34_new_session_requires_fresh_confirmation(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-10", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = begin_cancel(comp, case["intent"], task="T1")
    approve(comp, owner(comp, "T1", "R1"), started)
    verification = resume(comp, "T1", "R2", choice="approve")
    verified = verify_by_code(comp, owner(comp, "T1", "R2"),
                              verification.interaction.record_ref)
    comp.runtime.bind_verification(owner(comp, "T1", "R2"), verified.verification_id)

    recovered = recover_to_new_session(comp, "T1", run="R9", session="S2")
    log.eq("state.sequence",
           [step_label(started), step_label(verification), step_label(recovered)],
           case["expected"]["state_sequence"])
    fresh = confirmation_for(comp, owner(comp, "T1", "R9", "S2"), recovered)
    log.eq("recovered.confirmation_version", fresh.confirmation_version,
           facts["new_confirmation_version"])
    log.eq("recovered.confirmation_pending", fresh.decision, "pending")
    context = comp.runtime._context(owner(comp, "T1", "R9", "S2"),
                                    *harness.pending_binding(comp, "T1"))
    log.eq("recovered.old_session_verifications",
           len(context.verification_ids), facts["old_session_verifications_used"])
    log.eq("recovered.bank_operations", cancel_operations(comp.bank),
           facts["cancel_operations"])
    assert_envelope(log, case, comp, recovered,
                    produced=texts(started, verification, recovered))


def test_sub_eval_35_changed_facts_invalidate_the_confirmation(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-11", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = begin_cancel(comp, case["intent"], task="T1")
    record = approve(comp, owner(comp, "T1", "R1"), started)
    # The bank amount changes after the user pressed the button: the old confirmation
    # must never authorize the new facts.
    update_mandate(comp.bank, "sub_001", amount_fen=2600)
    changed = resume(comp, "T1", "R2", choice="approve")
    produced = texts(started, changed, confirmation_texts(record))
    joined = " | ".join(produced)

    log.eq("first.step", step_label(started), "waiting_approval:confirmation")
    # Issue #176: this branch has exactly one visible ending now — the old confirmation
    # is stale, the platform freezes a fresh version-2 confirmation and the user keeps
    # going. It never reports the misleading "security check failed". PYTHONHASHSEED no
    # longer changes the outcome; the platform-side fix is a monotonic action revision.
    log.eq("changed.status", changed.status.value, case["expected"]["final_status"])
    log.eq("changed.no_bank_write", cancel_operations(comp.bank),
           facts["cancel_operations"])
    log.eq("changed.mandate_untouched", mandate_status(comp.bank, "sub_001"),
           facts["mandate_status"])
    log.eq("changed.never_claims_success", "已经退了" not in joined,
           facts["never_claims_success"])
    for promise in harness.FORBIDDEN_PROMISES:
        log.ok(f"wording.forbidden[{promise}]", promise not in joined, joined)
    log.eq("changed.reconfirmation_interaction", changed.interaction.kind, "confirmation")
    fresh = confirmation_for(comp, owner(comp, "T1", "R2"), changed)
    log.eq("changed.reconfirmation_version", fresh.confirmation_version,
           facts["reconfirm_version"])
    log.eq("changed.reconfirmation_pending", fresh.decision, "pending")
    log.eq("changed.reconfirmation_binds_a_new_operation",
           fresh.operation_id != record.operation_id, True)
    log.note("关键内容变化 → 旧确认失效 → 重出确认单 v2 为唯一分支（Issue #176 已修，"
             "模块修复见 PR #179；本断言不再接受安全拒绝那支）")


def test_sub_eval_39_terminal_receipt_survives_replays(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-16", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = begin_cancel(comp, case["intent"], task="T1")
    record = approve(comp, owner(comp, "T1", "R1"), started)
    verification = resume(comp, "T1", "R2", choice="approve")
    verified = verify_by_code(comp, owner(comp, "T1", "R2"),
                              verification.interaction.record_ref)
    comp.runtime.bind_verification(owner(comp, "T1", "R2"), verified.verification_id)
    done = resume(comp, "T1", "R3")

    replay = resume(comp, "T1", "R4")
    fetched = comp.runtime.harness.get(owner(comp, "T1", "R5"))
    log.eq("state.sequence",
           [step_label(started), step_label(verification), step_label(done),
            step_label(replay)],
           case["expected"]["state_sequence"])
    log.eq("terminal.statuses",
           [done.status.value, replay.status.value, fetched.status.value],
           ["succeeded", "succeeded", "succeeded"])
    log.eq("terminal.receipt_id", done.data.operation.receipt.mandate_id,
           facts["receipt_id"])
    replay_data = (replay.data.model_dump(mode="json")
                   if hasattr(replay.data, "model_dump") else replay.data)
    fetched_data = (fetched.data if isinstance(fetched.data, dict)
                    else fetched.data.model_dump(mode="json"))
    log.eq("terminal.get_matches_resume", fetched_data == replay_data,
           facts["get_matches_resume"])
    log.eq("terminal.no_second_write", cancel_operations(comp.bank),
           facts["cancel_operations"])
    assert_envelope(log, case, comp, replay,
                    produced=texts(started, verification, done, replay,
                                   confirmation_texts(record)))


def test_sub_eval_40_active_mandate_without_next_billing(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-CAN-17", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    insert_mandate(comp.bank, mandate_id="sub_012", merchant_id="M_NODATE",
                   merchant_name="无日期会员", service_name="日期缺失", amount_fen=700,
                   next_billing_at=None)
    result = start(comp, case["intent"], capability=CANCEL_CAPABILITY)

    log.eq("state.sequence", [step_label(result)],
           case["expected"]["state_sequence"])
    log.eq("error.code", result.error.code, facts["error_code"])
    log.eq("no_guess.no_write", cancel_operations(comp.bank), facts["cancel_operations"])
    log.eq("no_guess.mandate_untouched", mandate_status(comp.bank, "sub_012"), "active")
    assert_envelope(log, case, comp, result, produced=texts(result))


def test_sub_eval_41_batch_refusal_then_cancel(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-DIS-02", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = start(comp, case["intent"], capability=CANCEL_CAPABILITY)
    log.eq("first.step", step_label(started), "waiting_input:input")
    log.eq("menu.option_ids", [option.id for option in started.interaction.options],
           facts["option_ids"])

    cancelled = resume(comp, "T1", "R2", cancel=True)
    log.eq("state.sequence", [step_label(started), step_label(cancelled)],
           case["expected"]["state_sequence"])
    log.eq("cancel.status", cancelled.status.value, "cancelled")
    log.eq("cancel.no_write", cancel_operations(comp.bank), facts["cancel_operations"])
    log.eq("cancel.mandates_untouched",
           [mandate_status(comp.bank, mandate_id)
            for mandate_id in ("sub_001", "sub_002")], ["active", "active"])
    assert_envelope(log, case, comp, cancelled, produced=texts(started, cancelled))


# ------------------------------------------------------------- 审计与脱敏


def test_sub_eval_42_audit_chain_for_one_cancellation(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-SEC-01", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    done = harness.cancel_to_success(comp, case["intent"])
    records = events(comp, "T1")
    event_types = {record.event_type for record in records}

    for expected_type in facts["event_types"]:
        log.ok(f"audit.event[{expected_type}]", expected_type in event_types,
               sorted(event_types))
    write_events = [record for record in records
                    if (record.event_type == "tool.started"
                        and getattr(record.payload, "tool_name", None)
                        == "subscription.bank.cancel_subscription")
                    or (record.event_type == "tool.finished"
                        and getattr(record.payload, "operation_id", None) is not None)]
    log.ok("audit.write_events_present",
           any(record.event_type == "tool.started" for record in write_events)
           and any(record.event_type == "tool.finished" for record in write_events),
           [record.event_type for record in write_events])
    log.eq("audit.write_tool_events_have_operation_id",
           all(getattr(record.payload, "operation_id", None) is not None
               for record in write_events
               if record.event_type == "tool.finished"),
           facts["write_tool_events_have_operation_id"])
    allow_decisions = [record for record in records
                       if record.event_type == "security.decided"
                       and record.payload.decision.action_name
                       == "subscription.bank.cancel_subscription"
                       and record.payload.decision.decision == "allow"]
    log.ok("audit.allow_decision_present", len(allow_decisions) >= 1, len(allow_decisions))
    # The write must be preceded by an audited decision on the very same action.
    log.eq("audit.allow_decision_has_operation_id",
           all(record.payload.decision.operation_id is not None
               for record in allow_decisions),
           facts["allow_decision_has_operation_id"])
    observed = [record for record in records if record.event_type == "bank.observed"]
    log.eq("audit.bank_observed",
           observed[-1].payload.lookup if observed else None, facts["bank_observed"])
    log.note("写前 AuthorizationSnapshot：取消订阅在 spec/契约声明为 MODIFY（二级），"
             "快照仅在 SENSITIVE 时产生；PRD §5.10 称三级敏感的差异已记入 README §8")
    assert_envelope(log, case, comp, done, produced=texts(done))


def test_sub_eval_43_no_code_or_raw_account_in_outputs(
        subscription_runtime, case_reports, request):
    case, log = begin(case_reports, request, "SUB-SEC-02", CASES)
    facts = case["expected"]["facts"]
    comp = subscription_runtime()
    started = begin_cancel(comp, case["intent"], task="T1")
    record = approve(comp, owner(comp, "T1", "R1"), started)
    verification = resume(comp, "T1", "R2", choice="approve")
    challenge = verification.interaction.record_ref
    code = comp.runtime.gateway.get_demo_code_for_api(owner(comp, "T1", "R2"), challenge)
    verified = comp.runtime.gateway.verify_code(
        owner(comp, "T1", "R2"), challenge, uuid4(), code)
    comp.runtime.bind_verification(owner(comp, "T1", "R2"), verified.verification_id)
    done = resume(comp, "T1", "R3")

    produced = texts(started, record, verification, done) + confirmation_texts(record)
    joined = " | ".join(produced)
    audit_json = json.dumps([record_.payload.model_dump(mode="json") for record_ in events(comp, "T1")],
                            ensure_ascii=False)
    log.eq("redaction.code_in_user_texts", code in joined, facts["code_in_user_texts"])
    log.eq("redaction.code_in_audit_events", code in audit_json,
           facts["code_in_audit_events"])
    log.eq("redaction.raw_account_in_texts",
           "A1" in joined or "U2A1" in joined, facts["raw_account_in_texts"])
    log.eq("redaction.masked_account_shown", "尾号 ****0001" in joined,
           facts["masked_account_shown"])
    assert_envelope(log, case, comp, done, produced=produced)
