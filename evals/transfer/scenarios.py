from contextlib import closing
"""Exercise public HTTP/platform entry points, with named fault seams and checks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import sqlite3
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.contracts.bank import OperationNotFound
from app.contracts.security import ConfirmationAnswer
from app.modules.transfer.workflow import TransferWorkflow
from app.services.mock_bank.core import PAYEES

from environment import ADMIN_KEY


def expect_wait(e, field=None, candidates=None):
    e.state("waiting_input")
    interaction = e.task.get("interaction") if e.task else None
    e.check("interaction.input", interaction is not None and interaction["kind"] == "input")
    if field:
        e.check("interaction.required_field", interaction and field in interaction["required_fields"], interaction)
        e.check("input.correct_question", interaction and field in interaction["required_fields"] and e.task["status"] == "waiting_input")
    if candidates:
        options = interaction["options"] if interaction else []
        e.check("interaction.candidates", {v["id"] for v in options} == set(candidates), options)
        e.check("redline.no_auto_selection", e.task and e.task["status"] == "waiting_input" and e.task["data"].get("payee") is None and not e.submissions)
    e.zero()


def details(e, kind, fields):
    r = e.post(f"/tasks/{e.task['task_id']}/details",
        interaction_id=e.task["interaction"]["interaction_id"], kind=kind, fields=fields)
    e.get_task()
    return r


def search(e, kind, value, target=None):
    r = details(e, "payee_search", {"kind": kind, "value": value})
    data = r.json().get("data", {})
    e.check("F36.no_model_raw", all(value not in record["input"] for record in e.planner.records))
    e.check("F36.search.status", r.status_code == 200, r.status_code)
    if target:
        candidates = data.get("candidates") or []
        e.check("F36.search.match", [v["payee_id"] for v in candidates] == [target], candidates)
        e.zero()
        e.input(selected_option_id=target)
    else:
        e.check("F36.search.empty", data.get("candidates") == [], data.get("candidates"))
        expect_wait(e, "payee_hint")


def assert_confirmation(e):
    e.state("waiting_approval")
    e.check("interaction.confirmation", e.task and e.task["interaction"]["kind"] == "confirmation")
    if not e.task or not e.task["interaction"] or e.task["interaction"]["kind"] != "confirmation": return
    c = e.confirmation()
    fields = {v["name"]: v["value_text"] for v in c["display_fields"]}
    e.check("confirmation.fields", {"payer_account_id", "amount", "bank", "fee", "arrival", "risk"} <= set(fields), fields)
    amount = e.task["data"]["amount_fen"]
    e.check("confirmation.amount", fields.get("amount") == f"{amount / 100:.2f} 元", fields)
    e.check("confirmation.bank_truth", fields.get("bank") == e.task["data"]["payee"]["bank_name"])
    e.check("confirmation.pending", c["decision"] == "pending")
    e.zero()


def payee(e, n):
    e.start()
    if not e.task: e.check("task.created", False); return
    if n in (3, 4, 5, 12, 13, 14):
        target = e.plan.target
        kind = "phone" if n in (3, 12, 13) else "account_number"
        raw = PAYEES[target][5 if kind == "phone" else 2]
        value = raw[:-1] if n == 12 else raw + "0" if n == 13 else raw + "x" if n == 14 else raw
        search(e, kind, value, target if n in (3, 4, 5) else None)
    elif n in (7, 8, 9, 10):
        expect_wait(e, candidates=("A10", "A11") if n == 9 else ("A8", "A9"))
        if n in (7, 8):
            e.input(selected_option_id=e.plan.target)
            e.check("selection.target", e.task["data"]["payee"]["payee_id"] == e.plan.target)
    elif n == 11: expect_wait(e, "payee_hint")
    elif n == 15:
        r = details(e, "payee", {"account_number": PAYEES["A2"][2], "account_name": "错误户名"})
        e.check("F36.mismatch", r.status_code == 400 and r.json()["error"]["code"] == "PAYEE_MISMATCH")
        e.state("failed")
        e.zero()
    elif n == 16:
        e.resume_fields(payee_input={"kind": "own", "account_id": "A5"})
    if e.plan.finish:
        assert_confirmation(e)
        e.complete()
        e.success()


def inputs(e, n):
    if n == 12:
        e.planner.plan.hint = "房东"
        e.start("给房东转500元，使用默认主账户A1。")
        old_task = e.task["task_id"]
        e.zero()
        e.planner.plan.hint = None
        e.thread = e.post("/threads").json()["data"]["thread_id"]
        e.task = None
    e.start()
    if n in (15, 16, 17, 18):
        if n == 15:
            e.check("input.secret_rejected", e.message_response.status_code == 400)
            e.check("input.secret_no_model", len(e.planner.records) == 0)
        elif n == 18:
            rows = e.client.get(f"/api/v1/threads/{e.thread}/messages").json()["data"]["items"]
            e.check("reply.saved", len(rows) == 2 and any(r["role"] == "assistant" and r["task_ids"] == [] for r in rows))
        elif n == 17:
            request_count = len(e.planner.records)
            e.check("model.controlled_failure", request_count == 1 and e.task is None)
        e.check("input.no_task", e.task is None, e.task)
        e.zero()
        return
    if not e.task: e.check("task.created", False); return
    original = e.task["task_id"]
    if n in (1, 4, 5, 8, 9, 14): expect_wait(e, "amount_fen")
    if n == 1: e.input(text="500元")
    elif n == 2:
        expect_wait(e, "payee_hint")
        search(e, "remark", "妈妈", "A2")
    elif n == 3:
        expect_wait(e, "payer_account_id")
        e.input(selected_option_id="A5")
    elif n == 4:
        e.input(text="100元")
        expect_wait(e, "payee_hint")
        e.check("input.amount_retained", e.task["data"]["amount_fen"] == 10_000)
    elif n == 5:
        r = e.input(text="很多钱")
        e.check("input.invalid", r.status_code == 400)
        expect_wait(e, "amount_fen")
    elif n == 11: expect_wait(e, candidates=("A8", "A9"))
    elif n == 12:
        expect_wait(e, "payee_hint")
        e.check("input.no_cross_task_target", e.task["task_id"] != old_task and e.task["data"]["payee"] is None)
    elif n == 13:
        assert_confirmation(e)
        e.check("input.initial_sixteen", e.task["data"]["amount_fen"] == 1600)
        change(e, amount_fen=6000)
    e.check("input.same_task", e.task["task_id"] == original)
    if e.plan.finish:
        assert_confirmation(e)
        e.complete()
        e.success(amount=6000 if n == 13 else e.plan.amount or 50_000)


def change(e, **fields):
    old_task = e.task["task_id"]
    old_op = e.task["data"]["operation_id"]
    old_confirmation = e.confirmation()
    e.resume_fields(**fields)
    e.check("version.same_task", e.task["task_id"] == old_task)
    e.check("version.new_operation", e.task["data"]["operation_id"] != old_op)
    r = e.post(f"/confirmations/{old_confirmation['confirmation_id']}/answer",
               confirmation_version=old_confirmation["confirmation_version"], choice="approve")
    e.check("version.old_confirmation_rejected", r.status_code == 409, r.status_code)
    e.get_task()
    e.zero()
    return old_confirmation


def cancel(e):
    r = e.post(f"/tasks/{e.task['task_id']}/cancel")
    e.get_task()
    return r


def confirmation(e, n):
    e.start()
    if not e.task: e.check("task.created", False); return
    if n == 2:
        c = e.confirmation()
        r = e.post(f"/confirmations/{c['confirmation_id']}/answer", confirmation_version=c["confirmation_version"], choice="approve", amount_fen=60_000)
        e.check("confirmation.extra_field_rejected", r.status_code == 400)
        e.get_task()
        e.check("confirmation.original_amount", e.task["data"]["amount_fen"] == 50_000)
        assert_confirmation(e)
    elif n in (3, 5):
        ident = e.task["task_id"]
        e.start(e.case["sample"] if n == 3 else "确认，直接转吧")
        tasks = e.client.get("/api/v1/tasks", params={"thread_id": e.thread}).json()["data"]["items"]
        e.check("confirmation.chat_no_new_task", len(tasks) == 1 and tasks[0]["task_id"] == ident)
        assert_confirmation(e)
    elif n in (6, 13):
        c = e.confirmation()
        op = e.task["data"]["operation_id"]
        expiry = __import__("datetime").datetime.fromisoformat(c["expires_at"])
        e.clock.advance((expiry - e.clock.at).total_seconds() - 0.001)
        e.check("confirmation.before_expiry", e.confirmation()["decision"] == "pending")
        if n == 13:
            # Prepare a real basic-identity record independently while the
            # unchanged action waits for a fresh confirmation.
            challenge = e.runtime.gateway.create_verification(e.trusted(), "basic_identity")
            code = e.runtime.gateway.get_demo_code_for_api(e.trusted(), challenge.challenge_id)
            e.secrets.append(code)
            record = e.runtime.gateway.verify_code(e.trusted(), challenge.challenge_id, uuid4(), code)
            e.runtime.bind_verification(e.trusted(), record.verification_id)
        e.clock.advance(0.001)
        r = e.post(f"/confirmations/{c['confirmation_id']}/answer", confirmation_version=c["confirmation_version"], choice="approve")
        e.check("confirmation.expired_rejected", r.status_code == 409)
        e.post(f"/tasks/{e.task['task_id']}/resume"); e.get_task()
        e.check("confirmation.same_content_operation", e.task["data"]["operation_id"] == op)
        e.zero()
        if n == 13:
            new = e.confirmation()
            e.check("confirmation.recreated", new["confirmation_version"] > c["confirmation_version"])
            e.approve(); e.get_task()
            e.check("verification.valid_record_reused", e.task["status"] == "succeeded")
            e.success()
    elif n in (7, 8, 9, 10, 11, 12):
        fields = {"amount_fen": e.plan.setup["change_amount"]} if "change_amount" in e.plan.setup else {
            "payee_input": {"kind": "saved", "payee_id": e.plan.setup["change_payee"]}} if "change_payee" in e.plan.setup else {"payer_account_id": "A5"}
        change(e, **fields)
        if n in (10, 11):
            expect_wait(e)
            bank_failure(e, "INSUFFICIENT_FUNDS" if n == 10 else "LIMIT_EXCEEDED", "single" if n == 11 else None)
        elif n == 9: assert_confirmation(e)
    elif n in (14, 15, 16):
        c = e.confirmation() if n != 15 else None
        cancel(e); e.state("cancelled"); e.zero()
        if c:
            r = e.post(f"/confirmations/{c['confirmation_id']}/answer", confirmation_version=c["confirmation_version"], choice="approve" if n == 14 else "cancel")
            e.check("cancel.late_confirmation_rejected", r.status_code in (409, 400))
        else:
            e.post(f"/tasks/{e.task['task_id']}/inputs", interaction_id="late", text="500元")
        cancel(e); e.get_task(); e.state("cancelled"); e.zero()
    elif n == 18:
        pending_operation(e)
        task_id, op, calls = identity(e)
        with patch.object(e.bank, "get_operation", return_value=OperationNotFound(lookup="not_found", operation=None)):
            cancel(e)
        e.state("needs_attention"); e.original(task_id, op, calls)
    elif n == 19:
        e.complete(); e.success()
        task_id, op, calls = identity(e)
        receipt = e.task["data"]["operation"]["receipt"]
        cancel(e); e.original(task_id, op, calls); e.state("succeeded")
        e.check("cancel.original_receipt", e.task["data"]["operation"]["receipt"] == receipt)
    elif n == 20:
        c = e.confirmation(); request = str(uuid4())
        parallel(e, lambda: e.post(f"/confirmations/{c['confirmation_id']}/answer", request_id=request,
                                   confirmation_version=c["confirmation_version"], choice="approve"))
        e.get_task(); e.code(); e.success()
    if n in (1, 7, 8, 12):
        assert_confirmation(e); e.complete()
        e.success(amount=60_000 if n == 7 else None, target="A3" if n == 8 else None, payer="A5" if n == 12 else None)


def bank_failure(e, code, scope=None):
    prechecks = [row["result"] for row in e.bank_reads if row["method"] == "precheck_transfer"]
    facts = [r["data"].get("failure") for r in prechecks if r.get("kind") == "ok"]
    facts = [f for f in facts if f]
    e.check("bank.failure_source", any(f["code"] == code for f in facts), facts)
    if scope: e.check("bank.limit_scope", any(f.get("details", {}).get("scope") == scope for f in facts), facts)


def banking(e, n):
    fault = e.plan.setup.get("read_fault")
    if fault:
        original = getattr(e.bank, fault)
        attempts = []
        def faulty(*args, **kwargs):
            attempts.append(1)
            if not e.plan.setup["transient"] or len(attempts) == 1: raise TimeoutError("injected read outage")
            return original(*args, **kwargs)
        with patch.object(e.bank, fault, side_effect=faulty): e.start()
        e.check("read.bounded_attempts", len(attempts) <= 3, len(attempts))
    else: e.start()
    if not e.task: e.check("task.created", False); return
    if n == 15:
        details(e, "payee", {"account_number": PAYEES["A7"][2], "account_name": PAYEES["A7"][1]})
    if n in (1, 2):
        expect_wait(e, "amount_fen")
        e.input(text="0元" if n == 1 else "-1元")
        expect_wait(e, "amount_fen")
    elif n in (13, 14):
        assert_confirmation(e)
        if n == 13:
            # Another bank-recognized operation consumes the available funds.
            account = e.bank.store.get_account("U1", "A1")
            e.bank.store.commit_operation("U1", str(uuid4()), "evaluation.other-transfer", {}, "succeeded", {}, e.bank_date.isoformat(),
                [("A1", account.version, 100, 0)], [])
        else: e.history(5_000_000, e.bank_date)
        # Z compares the current external-action baseline, preserving the other
        # operation instead of undoing it to make this transfer pass.
        e.baseline = e.bank_state()
        e.complete(); e.state("failed")
        e.check("bank.authorized_rejected_submission", len(e.submissions) == 1)
        e.check("bank.no_current_outflow", not [r for r in e.ledger() if r["operation_id"] == e.task["data"]["operation_id"]])
        failure = e.task["data"]["operation"]["failure"] if e.task["data"].get("operation") else None
        e.check("bank.submit_recheck", failure and failure["code"] == ("INSUFFICIENT_FUNDS" if n == 13 else "LIMIT_EXCEEDED"), failure)
    elif n in (3, 7, 8, 10, 19):
        assert_confirmation(e); e.complete(); e.success()
        if n == 7: e.check("bank.zero_balance", e.bank_state()["balances"]["A6"] == 0)
        if n == 10: e.check("bank.day_limit_consumed", e.bank.get_limits("U1", "A1").data.daily_remaining_fen == 0)
    elif n in (18, 20):
        expect_wait(e)
        e.check("read.recovery_required", e.task["recovery_required"])
    else:
        e.state("failed" if n == 15 else "waiting_input"); e.zero()
        code = "INSUFFICIENT_FUNDS" if n in (4, 5, 6) else "LIMIT_EXCEEDED" if n in (9, 11, 16) else "ACCOUNT_UNAVAILABLE" if n in (12, 17) else "RISK_REJECTED"
        bank_failure(e, code, {9: "single", 11: "day", 16: "year"}.get(n))


def resend(e):
    cid = e.challenge().challenge_id
    r = e.post(f"/verifications/{cid}/resend-code")
    e.get_task()
    return r


def verification(e, n):
    e.start()
    if not e.task: e.check("task.created", False); return
    if n in (15, 17):
        e.state("failed" if n == 15 else "needs_attention"); e.zero()
        e.post(f"/tasks/{e.task['task_id']}/resume"); e.get_task()
        e.state("failed" if n == 15 else "needs_attention"); e.zero(); return
    if n == 19:
        e.approve(); e.code_without_continuation()
        verified = e.saved_verification["verification_id"]
        old_task = e.task["task_id"]
        cancel(e); e.zero()
        e.thread = e.post("/threads").json()["data"]["thread_id"]
        e.task = None; e.start()
        e.check("verification.new_task_same_session", e.task and e.task["task_id"] != old_task)
        assert_confirmation(e)
        with patch.object(e.runtime.gateway, "create_verification", wraps=e.runtime.gateway.create_verification) as creates:
            e.approve()
            e.check("verification.session_record_reused_without_new_code", creates.call_count == 0)
        e.check("verification.reused_original_record", verified in e.runtime.facts.verification_ids(e.trusted(), UUID(e.task["data"]["operation_id"]), 1))
        e.success(); return
    e.approve()
    if not e.task["interaction"] or e.task["interaction"]["kind"] != "verification":
        e.check("verification.challenge_created", False); return
    challenge = e.challenge()
    cid = challenge.challenge_id
    old_code = e.runtime.gateway.get_demo_code_for_api(e.trusted(), cid)
    e.secrets.append(old_code)
    if n in (3, 4):
        for count in (1, 2):
            e.code(wrong=True)
            e.state("waiting_approval"); e.zero()
            e.check("verification.failure_count", e.challenge().consecutive_code_failures == count)
        if n == 4:
            resend(e)
            e.check("verification.resend_same_failures", e.challenge().consecutive_code_failures == 2)
            e.check("verification.new_challenge", e.challenge().challenge_id != cid)
        e.code(wrong=True); e.state("failed"); e.zero()
        r = e.post(f"/verifications/{cid}/code", submission_id=str(uuid4()), code=old_code)
        e.check("verification.late_code_rejected", r.status_code != 200); e.get_task(); e.state("failed")
    elif n == 5:
        resend(e)
        r = e.post(f"/verifications/{cid}/code", submission_id=str(uuid4()), code=old_code)
        e.check("verification.old_challenge_rejected", r.status_code != 200)
        e.get_task(); e.state("waiting_approval"); e.zero()
    elif n == 6:
        e.clock.advance(300)
        r = e.post(f"/verifications/{cid}/code", submission_id=str(uuid4()), code=old_code)
        e.check("verification.expired_code_rejected", r.status_code != 200); e.zero()
        resent = resend(e); e.get_task()
        e.check("verification.basic_expiry_can_resend", resent.status_code == 200)
        if resent.status_code == 200 and e.task["interaction"] and e.task["interaction"]["kind"] == "verification":
            e.check("verification.basic_new_deadline", e.challenge().code_expires_at > challenge.code_expires_at)
            e.code()
        e.success()
    elif n == 7:
        e.code(); e.state("waiting_approval"); e.zero()
        e.check("verification.only_code", e.challenge().required_methods == ["code", "mock_face"] and e.challenge().code_result == "passed")
    elif n == 8:
        e.code(wrong=True); e.state("failed"); e.zero()
        r = e.post(f"/admin/verifications/{cid}/face-result", submission_id=str(uuid4()), demo_round_id="D1", result="passed")
        e.check("verification.after_fail_cannot_revive", r.status_code != 200)
    elif n == 9:
        e.clock.advance(290); resend(e)
        e.check("verification.medium_fixed_deadline", e.challenge().code_expires_at == challenge.code_expires_at)
        e.clock.advance(10)
        e.post(f"/verifications/{e.challenge().challenge_id}/code", submission_id=str(uuid4()), code=old_code)
        e.post(f"/tasks/{e.task['task_id']}/resume"); e.get_task(); e.state("failed"); e.zero()
    elif n in (10, 11):
        e.code(); e.clock.advance(240)
        e.post(f"/verifications/{cid}/face/start")
        face = e.challenge()
        e.post(f"/verifications/{cid}/face/start")
        e.check("verification.face_deadline_stable", e.challenge().face_expires_at == face.face_expires_at)
        e.clock.advance(300)
        e.post(f"/tasks/{e.task['task_id']}/resume"); e.get_task(); e.state("failed")
        other = admin_client(e)
        try:
            e.post(f"/admin/verifications/{cid}/face-result", client=other,
                   submission_id=str(uuid4()), demo_round_id="D1", result="passed")
        finally: other.close()
        e.get_task(); e.state("failed"); e.zero()
    elif n == 12:
        with patch.object(e.bank.verification, "verify_code", side_effect=TimeoutError("verification outage")):
            e.code()
        e.get_task(); e.state("needs_attention"); e.zero()
        e.check("verification.technical_not_wrong", e.runtime.gateway.get_verification(e.trusted(), cid).consecutive_code_failures == 0)
    elif n == 13:
        cancel(e)
        for path, body in (("code", {"submission_id": str(uuid4()), "code": old_code}), ("resend-code", {}), ("face/start", {})):
            r = e.post(f"/verifications/{cid}/{path}", **body)
            e.check("cancel.verification_cannot_revive", r.status_code != 200)
        other = admin_client(e)
        try: e.post(f"/admin/verifications/{cid}/face-result", client=other, submission_id=str(uuid4()), demo_round_id="D1", result="passed")
        finally: other.close()
        e.get_task(); e.state("cancelled"); e.zero()
    elif n == 18:
        e.code_without_continuation()
        e.risk = "high"
        e.post(f"/tasks/{e.task['task_id']}/resume"); e.get_task(); e.state("failed"); e.zero()
    elif n == 20:
        e.code_without_continuation(face=True)
        old_records = e.runtime.facts.verification_ids(e.trusted(), UUID(e.task["data"]["operation_id"]), 1)
        change(e, amount_fen=60_000)
        e.approve(); e.state("waiting_approval"); e.zero()
        e.check("verification.old_action_not_reused", e.task["interaction"]["kind"] == "verification" and bool(old_records))
        e.code(); e.face(); e.success(amount=60_000)
    elif n == 21:
        e.code(); e.face(result="failed"); e.state("failed"); e.zero()
        other = admin_client(e)
        try: e.post(f"/admin/verifications/{cid}/face-result", client=other, submission_id=str(uuid4()), demo_round_id="D1", result="passed")
        finally: other.close()
        e.get_task(); e.state("failed"); e.zero()
    elif n == 22:
        e.face(); e.state("waiting_approval"); e.zero()
        e.check("verification.only_face", e.challenge().face_result == "passed" and e.challenge().code_result == "pending")
    elif n == 23:
        e.face(); resend(e)
        current = e.challenge()
        e.check("verification.face_preserved", current.face_result == "passed")
        e.check("verification.resend_fixed_deadline", current.code_expires_at == challenge.code_expires_at)
        e.code(); e.success()
    elif n == 24:
        e.clock.advance(300)
        e.post(f"/verifications/{cid}/face/start")
        e.post(f"/verifications/{cid}/resend-code")
        e.post(f"/tasks/{e.task['task_id']}/resume"); e.get_task(); e.state("failed"); e.zero()
    elif n in (1, 14):
        e.code()
        if n == 14:
            e.state("waiting_approval"); e.zero(); e.face()
        e.success()


def identity(e):
    return e.task["task_id"], e.task["data"]["operation_id"], len(e.submissions)


def parallel(e, action, identical=True):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: action(), range(2)))
    e.check("concurrency.responses_equal" if identical else "concurrency.response_statuses", results[0].status_code == results[1].status_code and (not identical or results[0].json() == results[1].json()))
    return results


def admin_client(e):
    client = TestClient(e.api, raise_server_exceptions=False)
    e.post("/session/enter", client=client, admin_key=ADMIN_KEY)
    return client


def pending_operation(e, mode="not_found", hold=True, transient_query=False, expire_during_query=False, processing_summaries=False):
    e.approve()
    # Use the real authorized bank write for succeeded/failed/processing facts.
    # Transport uncertainty is injected after the write, never a fake receipt.
    original = e.bank.submit_transfer
    def unknown(*args, **kwargs):
        if mode != "not_found":
            if mode == "failed":
                with closing(sqlite3.connect(e.bank.store.path)) as c, c:
                    c.execute("UPDATE accounts SET book_balance_fen=0 WHERE account_id='A1'")
            if mode == "processing":
                e.bank.arm_slow_once("U1")
                # Bank writes its real processing row, then its worker loses the
                # response before settlement. No fabricated terminal result.
                with patch("app.services.mock_bank.core.time.sleep", side_effect=TimeoutError("worker interrupted")):
                    try: original(*args, **kwargs)
                    except TimeoutError: pass
            else: original(*args, **kwargs)
        else:
            # Record the actual bank invocation + trusted execution evidence,
            # but inject a dropped transport before the bank commits anything.
            with patch.object(e, "original_submit", side_effect=TimeoutError("sent-no-response")):
                try: original(*args, **kwargs)
                except TimeoutError: pass
        from app.contracts.bank import BankError, QueryFailure
        e.clock.advance(4)
        return QueryFailure(kind="error", error=BankError(code="CALL_TIMEOUT", details={}))
    with patch.object(e.bank, "submit_transfer", side_effect=unknown):
        if expire_during_query:
            attempts = []
            def expired_read(*args):
                attempts.append(e.clock.elapsed)
                if len(attempts) == 1: expire_session(e)
                return OperationNotFound(lookup="not_found", operation=None)
            with patch.object(e.bank, "get_operation", side_effect=expired_read): e.code()
            stored = e.runtime.application.get_task("U1", "D1", e.task["task_id"])
            if stored and "result" in stored.snapshot:
                e.task.update(stored.snapshot["result"])
                e.snapshot("expired-session.read_server_store_without_client_authorization")
            e.check("fault.session_expired_inside_query", bool(attempts))
            e.check("query.no_read_after_session_expiry", len(attempts) == 1, len(attempts))
        elif transient_query:
            original_read = e.bank.get_operation
            attempts = []
            def once(*args):
                attempts.append(1)
                if len(attempts) == 1: raise TimeoutError("query transient outage")
                return original_read(*args)
            with patch.object(e.bank, "get_operation", side_effect=once): e.code()
        elif processing_summaries:
            reads = []
            original_read = e.bank.get_operation
            def with_summary(*args):
                reads.append(e.clock.elapsed)
                result = original_read(*args)
                summary = e.client.get(f"/api/v1/tasks/{e.task['task_id']}")
                body = summary.json().get("data", {})
                e.steps.append({"entry": "HTTP.result-summary-during-processing", "at_elapsed": e.clock.elapsed,
                                "http_status": summary.status_code, "response": body})
                e.check("query.processing_summary_not_success", summary.status_code == 200 and body.get("status") != "succeeded")
                e.check("query.summary_original_operation", body.get("data", {}).get("operation_id") == str(result.operation.operation_id))
                # Controlled one-second read latency must consume the original
                # window rather than grant a fresh ten seconds per summary.
                e.clock.advance(1)
                return result
            with patch.object(e.bank, "get_operation", side_effect=with_summary): e.code()
            deadline = reads[0] - 3 + 10 if reads else 0
            e.check("query.summary_does_not_extend_deadline", bool(reads) and max(reads) <= deadline and e.clock.elapsed <= deadline + 1, reads)
        elif mode == "processing" or not hold: e.code()
        else:
            with patch.object(e.bank, "get_operation", return_value=OperationNotFound(lookup="not_found", operation=None)): e.code()
    e.get_task()
    if hold: e.state("needs_attention")
    return identity(e)


def querying(e, n):
    e.start()
    if not e.task: e.check("task.created", False); return
    if n == 15:
        e.complete(); e.success()
        before = identity(e); receipt = e.task["data"]["operation"]["receipt"]
        for _ in range(3): e.post(f"/tasks/{e.task['task_id']}/query-result"); e.get_task()
        e.start("结果怎么样"); e.get_task()
        e.original(*before); e.check("query.receipt_unchanged", e.task["data"]["operation"]["receipt"] == receipt)
        return
    before = pending_operation(e, "succeeded" if n in (1, 5, 10) else "failed" if n in (2, 11) else "processing" if n == 3 else "not_found", hold=n not in (1, 2, 5), transient_query=n == 5, expire_during_query=n == 8, processing_summaries=n == 3)
    if n in (1, 2, 5, 10, 11):
        original = e.bank.get_operation
        attempts = []
        def read(*args):
            attempts.append(1)
            if n == 5 and len(attempts) == 1: raise TimeoutError("query outage")
            return original(*args)
        with patch.object(e.bank, "get_operation", side_effect=read):
            e.post(f"/tasks/{e.task['task_id']}/query-result"); e.get_task()
            if n == 5 and e.task["status"] != "succeeded": e.post(f"/tasks/{e.task['task_id']}/query-result"); e.get_task()
        e.state("failed" if n in (2, 11) else "succeeded")
        e.check("query.terminal_clears_recovery", not e.task["recovery_required"] and e.task["recovery_reason"] is None)
        bank_op = e.bank.store.get_operation("U1", before[1])
        e.check("query.bank_terminal_truth", bank_op and e.task["data"]["operation"] == bank_op.result)
    elif n in (8, 9, 14):
        if n == 8:
            r = e.post(f"/tasks/{e.task['task_id']}/query-result")
            e.check("query.expired_denied", r.status_code == 401)
        elif n == 14:
            with foreign_client(e) as client:
                r = e.post(f"/tasks/{e.task['task_id']}/query-result", client=client)
                e.check("query.foreign_denied", r.status_code in (403, 404))
        else:
            e.current_round = "D2"
            r = e.post(f"/tasks/{e.task['task_id']}/query-result")
            e.check("query.permission_denied", r.status_code != 200)
    else:
        start_time = e.clock.elapsed
        attempts = []
        def unknown(*args):
            attempts.append(e.clock.elapsed)
            if n == 7: e.clock.advance(11)
            if n in (6, 7): raise TimeoutError("query unavailable")
            if n == 3: return e.original_reads["get_operation"](*args)
            return OperationNotFound(lookup="not_found", operation=None)
        with patch.object(e.bank, "get_operation", side_effect=unknown):
            if n == 16:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    list(pool.map(lambda path: e.post(f"/tasks/{e.task['task_id']}/{path}"), ("cancel", "query-result")))
            else: e.post(f"/tasks/{e.task['task_id']}/query-result")
            if n in (3, 12): e.start("结果怎么样" if n == 3 else "再转一次")
        e.get_task(); e.state("needs_attention")
        e.check("query.bounded_window", e.clock.elapsed - start_time <= 11)
        e.check("query.no_success_receipt", not e.task["data"].get("operation") or not e.task["data"]["operation"].get("receipt"))
        if n == 3:
            e.check("fixture.processing_required", e.task["data"]["operation"]["operation_status"] == "processing")
    e.original(*before)


def expire_session(e):
    who = e.service.identity(e.session)
    with closing(sqlite3.connect(e.runtime.application.path)) as c, c:
        c.execute("UPDATE sessions SET expires_at=? WHERE session_id=?", ((e.clock.at - timedelta(seconds=1)).isoformat(), who.session_id))


def foreign_client(e):
    # Same public API/store, configured second demo identity with no U1 rights.
    from app.api.app import ApiConfig, create_app
    from environment import SECRET
    api = create_app(e.runtime, ApiConfig(secret=SECRET, demo_user_id="U2", origins=("http://testserver",)))
    client = TestClient(api, raise_server_exceptions=False)
    e.post("/session/enter", client=client)
    return client


def recovery(e, n):
    if n == 21:
        with patch.object(TransferWorkflow, "start", side_effect=RuntimeError("injected first checkpoint interruption")):
            e.start()
        e.check("fault.first_checkpoint_saved_task", e.task is not None)
    elif n == 23:
        save = e.runtime.snapshots.save
        once = []
        def interrupted(context, action, parameters, *args, **kwargs):
            if action == "bank.submit_transfer" and not once:
                once.append(True); raise RuntimeError("injected reserved snapshot interruption")
            return save(context, action, parameters, *args, **kwargs)
        with patch.object(e.runtime.snapshots, "save", side_effect=interrupted): e.start()
        e.check("fault.operation_reserved", bool(once))
        operations = e.runtime.application.list_task_operations("U1", "D1", e.task["task_id"]) if e.task else []
        reserved = [v.operation_id for v in operations if v.action_name == "bank.submit_transfer"]
        e.check("fault.durable_original_operation", len(reserved) == 1, reserved)
        e.zero()
    else: e.start()
    if not e.task: e.check("task.created", False); return
    if n in (5, 6, 7, 8, 10):
        before = pending_operation(e, "succeeded" if n in (6, 10) else "processing" if n == 7 else "not_found")
        e.restart()
        if n == 10:
            expire_session(e); e.post("/session/enter"); e.session = e.client.cookies.get("bank_session")
        if n == 8: parallel(e, lambda: e.post(f"/tasks/{e.task['task_id']}/resume"), identical=False)
        else: e.post(f"/tasks/{e.task['task_id']}/resume")
        e.get_task(); e.original(*before)
        if n == 10 and e.task["status"] == "needs_attention":
            e.post(f"/tasks/{e.task['task_id']}/query-result"); e.get_task()
        e.state("succeeded" if n in (6, 10) else "failed" if n == 7 else "needs_attention")
        if n == 7:
            e.check("fixture.interrupted_bank_truth", e.task["data"]["operation"]["failure"]["details"].get("reason") == "processing_interrupted")
    elif n in (12, 13, 14, 17, 18):
        if n == 17:
            # Start a fresh ambiguous task (not a pre-confirmed one).
            cancel(e)
            e.planner.plan.hint, e.planner.plan.amount = "张伟", 10_000
            e.thread = e.post("/threads").json()["data"]["thread_id"]; e.task = None
            e.start("给张伟转100元，使用默认主账户A1。")
        if n == 18: e.approve()
        original_task = json.dumps(e.task, sort_keys=True)
        client = foreign_client(e)
        try:
            task_id = e.task["task_id"]
            if n == 13: r = client.get(f"/api/v1/tasks/{task_id}")
            elif n == 14:
                c = e.confirmation()
                r = e.post(f"/confirmations/{c['confirmation_id']}/answer", client=client, confirmation_version=c["confirmation_version"], choice="approve")
            elif n == 17: r = e.post(f"/tasks/{task_id}/inputs", client=client, interaction_id=e.task["interaction"]["interaction_id"], selected_option_id="A8")
            elif n == 18: r = e.post(f"/verifications/{e.task['interaction']['record_ref']}/code", client=client, submission_id=str(uuid4()), code="test-code")
            else: r = e.post(f"/tasks/{task_id}/resume", client=client)
            e.check("ownership.denied", r.status_code in (403, 404), r.status_code)
            e.check("ownership.no_content", "amount_fen" not in r.text and "payee" not in r.text)
        finally: client.close()
        e.get_task(); e.check("ownership.unchanged", json.dumps(e.task, sort_keys=True) == original_task); e.zero()
    elif n in (11, 15):
        c = e.confirmation()
        if n == 11: expire_session(e)
        else: e.current_round = "D2"
        for path, body in ((f"/confirmations/{c['confirmation_id']}/answer", {"confirmation_version": c["confirmation_version"], "choice": "approve"}), (f"/tasks/{e.task['task_id']}/resume", {})):
            r = e.post(path, **body)
            e.check("session.stale_denied", r.status_code != 200)
        e.zero()
    elif n in (16, 19, 20):
        if n == 16: e.complete(); e.success()
        if n == 20: cancel(e)
        before = identity(e); models = len(e.planner.records)
        expected = "succeeded" if n == 16 else "failed" if n == 19 else "cancelled"
        e.restart(); e.post(f"/tasks/{e.task['task_id']}/resume"); e.get_task()
        e.state(expected); e.original(*before)
        e.check("recovery.terminal_no_model", len(e.planner.records) == models)
        if n != 16: e.zero()
    elif n == 22:
        e.approve()
        cid = e.challenge().challenge_id
        raw = e.runtime.gateway.get_demo_code_for_api(e.trusted(), cid)
        e.secrets.append(raw)
        body = {"request_id": str(uuid4()), "submission_id": str(uuid4()), "code": raw}
        endpoint = f"/verifications/{cid}/code"
        who = e.service.identity(e.session)
        e.service.store.receipt(who, "/api/v1" + endpoint, body["request_id"], body)
        verified = e.runtime.gateway.verify_code(e.trusted(), cid, UUID(body["submission_id"]), raw)
        e.check("fault.bank_verified_before_binding", bool(verified.verification_id))
        e.check("fault.application_not_yet_bound", not e.runtime.facts.verification_ids(e.trusted(), UUID(e.task["data"]["operation_id"]), 1))
        before = identity(e); e.zero()
        e.restart(); e.post(endpoint, **body); e.get_task()
        e.check("recovery.verification_bound", e.task["status"] == "succeeded")
        e.success(); e.check("recovery.same_task", e.task["task_id"] == before[0])
        e.check("recovery.same_operation", e.task["data"]["operation_id"] == before[1])
    else:
        if n == 4: e.approve(); e.code(); e.zero()
        old = json.loads(json.dumps(e.task)); models = len(e.planner.records)
        if n not in (1, 2): e.restart()
        e.get_task(); e.check("recovery.same_task", e.task["task_id"] == old["task_id"])
        if n in (21, 23):
            e.post(f"/tasks/{e.task['task_id']}/resume"); e.get_task()
        if n == 9:
            old_c = e.confirmation()
            expire_session(e); e.post("/session/enter"); e.session = e.client.cookies.get("bank_session")
            e.post(f"/tasks/{e.task['task_id']}/resume"); e.get_task()
            e.check("recovery.new_confirmation", e.confirmation()["confirmation_version"] > old_c["confirmation_version"])
            e.complete(); e.success()
        elif n == 1:
            expect_wait(e, "amount_fen"); e.input(text="500元"); e.complete(); e.success()
        elif n == 23:
            assert_confirmation(e)
            e.check("recovery.original_reserved_operation", len(reserved) == 1 and e.task["data"]["operation_id"] == str(reserved[0]))
            e.complete(); e.success()
        elif n == 21: expect_wait(e, "amount_fen")
        elif n == 4:
            e.state("waiting_approval"); e.zero(); e.check("recovery.code_preserved", e.challenge().code_result == "passed")
        else:
            e.state("waiting_approval"); e.zero()
            e.check("recovery.same_confirmation", e.task["interaction"]["record_ref"] == old["interaction"]["record_ref"])
        e.check("recovery.no_replanning", len(e.planner.records) == models)


def observations(e, n):
    if n == 1:
        request = str(uuid4())
        parallel(e, lambda: e.post(f"/threads/{e.thread}/messages", request_id=request, text=e.plan.text))
        items = e.client.get("/api/v1/tasks", params={"thread_id": e.thread}).json()["data"]["items"]
        e.check("message.one_task", len(items) == 1)
        e.task = items[0] if items else None
        e.complete(); e.success(); return
    e.start()
    if not e.task: e.check("task.created", False); return
    if n in (2, 18):
        e.approve(); cid = e.challenge().challenge_id
        raw = e.runtime.gateway.get_demo_code_for_api(e.trusted(), cid); e.secrets.append(raw)
        request, submission = str(uuid4()), str(uuid4())
        parallel(e, lambda: e.post(f"/verifications/{cid}/code", request_id=request,
                                   submission_id=submission, code=raw if n == 2 else "not-the-code"))
        e.get_task()
        if n == 2: e.success()
        else:
            e.state("waiting_approval"); e.zero(); e.check("verification.replay_one_failure", e.challenge().consecutive_code_failures == 1)
    elif n == 8:
        raw = PAYEES["A12"][5]
        r = details(e, "payee_search", {"kind": "phone", "value": raw})
        e.check("F36.exact_candidate", r.status_code == 200 and [c["payee_id"] for c in r.json()["data"]["candidates"]] == ["A12"])
        e.check("F36.raw_not_in_model", all(raw not in v["input"] for v in e.planner.records))
        manual = details(e, "payee", {"account_number": PAYEES["A2"][2], "account_name": PAYEES["A2"][1]})
        e.check("F36.manual_verified", manual.status_code == 200)
        # A valid exact search must return a candidate, yet remain unselected.
        e.zero()
    elif n == 9:
        e.complete(); e.success()
    elif n == 10:
        e.approve()
        method = "verify_code"
        with patch.object(e.bank.verification, method, side_effect=RuntimeError("eval-secret-credential")):
            e.code()
        e.get_task(); e.state("needs_attention"); e.zero()
    elif n in (11, 12, 14):
        e.complete(); e.success(); before = identity(e); models = len(e.planner.records)
        e.restart(); e.post(f"/tasks/{e.task['task_id']}/resume"); e.get_task()
        client = e.client if n == 12 else admin_client(e)
        try:
            r = client.get("/api/v1/admin/audit/events", params={"task_id": e.task["task_id"], "limit": 100})
            if n == 12: e.check("audit.user_denied", r.status_code == 403)
            else:
                e.check("audit.admin_allowed", r.status_code == 200)
                summaries = r.json().get("data", {}).get("items", [])
                kinds = {v["event_type"] for v in summaries}
                e.check("audit.linked_kinds", {"model.started", "model.finished", "tool.started", "security.decided", "confirmation.changed", "verification.changed", "bank.observed", "recovery.checked"} <= kinds, sorted(kinds))
                if n == 14 and summaries:
                    with closing(sqlite3.connect(e.runtime.application.path)) as c, c:
                        c.execute("DELETE FROM audit_evidence")
                    event = next((v for v in summaries if v["event_type"] == "model.finished"), summaries[0])
                    detail = client.get(f"/api/v1/admin/audit/events/{event['event_id']}")
                    e.check("audit.missing_explicit", "missing" in detail.text.lower(), detail.json())
        finally:
            if client is not e.client: client.close()
        e.original(*before); e.check("audit.no_model_reexecution", len(e.planner.records) == models)
    elif n == 13:
        e.approve(); e.code(); r = e.face(admin=False)
        e.check("face.admin_only", r.status_code == 403)
        e.state("waiting_approval"); e.zero(); e.check("face.not_passed", e.challenge().face_result != "passed")
    elif n in (15, 16):
        e.approve(); e.code_without_continuation()
        append = e.runtime.audit.append_in_transaction
        triggered = []
        def unavailable(connection, event, **kwargs):
            if (event.event_type == "tool.started" if n == 15 else event.event_type == "bank.observed") and event.payload.operation_id is not None:
                triggered.append(event.event_type); raise RuntimeError("injected audit disk fault")
            return append(connection, event, **kwargs)
        with patch.object(e.runtime.audit, "append_in_transaction", side_effect=unavailable):
            e.post(f"/tasks/{e.task['task_id']}/resume")
        e.get_task(); e.check("fault.audit_triggered", bool(triggered), triggered)
        if n == 15: e.state("needs_attention"); e.zero()
        else:
            before = identity(e); e.restart(); e.post(f"/tasks/{e.task['task_id']}/resume"); e.get_task(); e.original(*before); e.state("succeeded")
    elif n == 17:
        request = str(uuid4())
        cancel(e)
        e.thread = e.post("/threads").json()["data"]["thread_id"]; e.task = None
        e.start(request_id=request)
        before = json.dumps(e.task, sort_keys=True)
        r = e.post(f"/threads/{e.thread}/messages", request_id=request, text="给妈妈转600元，使用默认主账户A1。")
        e.check("message.changed_content_conflict", r.status_code == 409)
        e.get_task(); e.check("message.original_task_unchanged", json.dumps(e.task, sort_keys=True) == before); e.zero()


HANDLERS = {"PAY": payee, "INP": inputs, "CNF": confirmation, "BNK": banking,
            "VFY": verification, "QRY": querying, "RCV": recovery, "OBS": observations}


def execute(e):
    group, number = e.case["scenario_id"].split("-")[1:]
    HANDLERS[group](e, int(number))
    e.get_task()
    e.snapshot("final")


def common_checks(e):
    e.check("redline.no_unconfirmed_execution", all(s["authorized"] for s in e.submissions))
    ids = [s["operation_id"] for s in e.submissions]
    e.check("redline.no_duplicate_bank_call", len(ids) == len(set(ids)))
    if e.task:
        operation_id = e.task["data"].get("operation_id")
        bank_operation = e.bank.store.get_operation("U1", operation_id) if operation_id else None
        result = e.task["data"].get("operation") or {}
        if e.task["status"] == "succeeded":
            e.check("redline.no_false_success", bank_operation is not None and bank_operation.status == "succeeded"
                    and bank_operation.result.get("receipt") == result.get("receipt") and bool(result.get("receipt"))
                    and len([r for r in e.ledger() if r["operation_id"] == operation_id]) == 1)
        else:
            e.check("redline.no_false_success", not result.get("receipt"))
        if bank_operation is None or bank_operation.status != "succeeded":
            e.check("redline.no_success_message", not any(text in e.task.get("message", "") for text in ("转账成功", "已经到账", "已到账")), e.task.get("message"))
    e.scan_secrets()
