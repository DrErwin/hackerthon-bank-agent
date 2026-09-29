"""The real bank and security path through the platform-owned composition."""

from datetime import datetime, timedelta, timezone
from multiprocessing import get_context
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from app.audit.journal import AuditJournal
from app.contracts.bank import SavedPayee
from app.contracts.common import Phase, RiskLevel, SecurityDecisionCode, TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.security import ConfirmationAnswer
from app.memory.adapter import MemoryAdapter
from app.services.mock_bank.core import MockBankService
from app.services.mock_bank.verification import AdminContext
from app.storage.application import ApplicationStore
from app.storage.database import connect
from app.storage.mock_bank.repository import MockBankStore

from .test_harness import ProposalModel
from .transfer_runtime import TransferRuntime


def trusted(run="R1"):
    return TrustedContext(user_id="U1", session_id="S1", task_id="T1", run_id=run,
                          parent_task_id=None, demo_round_id="D1")


def runtime(path, bank, *, risk=RiskLevel.LOW, authorize_tool=lambda *_: True,
            authorize_face=None):
    application = ApplicationStore(path)
    return TransferRuntime(
        application, MemoryAdapter(application, active_round=lambda: "D1"),
        AuditJournal(path), bank, ProposalModel(),
        authorize_capability=lambda *_: True,
        authorize_tool=authorize_tool,
        assess_risk=risk if callable(risk) else lambda *_: risk,
        authorize_face=authorize_face,
    )


def _resume_in_process(path, bank_path, ready, release, results):
    bank = MockBankService(MockBankStore(bank_path), demo_secret=b"demo-secret" * 4)
    app = runtime(path, bank)
    ready.put(True)
    release.wait()
    try:
        result = app.harness.resume(trusted("R4"), {"choice": "approve"})
        results.put(result.status.value)
    except Exception as exc:
        results.put(type(exc).__name__)
    finally:
        app.close()


def _start_in_process(path, bank_path, request_id, ready, release, results):
    bank = MockBankService(MockBankStore(bank_path), demo_secret=b"demo-secret" * 4)
    app = runtime(path, bank)
    ready.put(True)
    release.wait()
    try:
        result = app.harness.start(trusted(), request_id, "给妈妈转 500 元")
        results.put(str(result.data.operation_id))
    except Exception as exc:
        results.put(type(exc).__name__)
    finally:
        app.close()


def test_real_confirmation_verification_and_crash_recovery(tmp_path):
    path = tmp_path / "application.sqlite"
    bank = MockBankService(
        MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4,
    )
    app = runtime(path, bank)
    now = datetime.now(timezone.utc)
    app.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    request_id = uuid4()
    pending = app.harness.start(trusted(), request_id, "给妈妈转 500 元")
    assert pending.status == TaskStatus.WAITING_APPROVAL
    assert pending.interaction.kind == "confirmation"
    operation_id = pending.data.operation_id
    assert app.gateway.get_operation(trusted(), operation_id).lookup == "not_found"
    assert app.gateway.submit_transfer(
        trusted(), operation_id, "A1", SavedPayee(kind="saved", payee_id="A2"), 50_000,
    ).error.code == "ACCESS_DENIED"

    # Chat text and a resume command do not approve a transfer.
    still_waiting = app.harness.resume(trusted("R2"), {"choice": "approve"})
    assert still_waiting.status == TaskStatus.WAITING_APPROVAL
    assert still_waiting.interaction.kind == "confirmation"
    assert app.gateway.get_operation(trusted(), operation_id).lookup == "not_found"

    record = app.answer_confirmation(trusted("R2"), ConfirmationAnswer(
        confirmation_id=pending.interaction.record_ref,
        confirmation_version=1, choice="approve",
    ))
    assert record.decision == "approved"
    verification = app.harness.resume(trusted("R3"), {"choice": "approve"})
    assert verification.status == TaskStatus.WAITING_APPROVAL
    assert verification.interaction.kind == "verification"
    assert app.gateway.get_operation(trusted(), operation_id).lookup == "not_found"

    challenge_id = verification.interaction.record_ref
    code = app.gateway.get_demo_code_for_api(trusted("R3"), challenge_id)
    verified = app.gateway.verify_code(trusted("R3"), challenge_id, uuid4(), code)
    assert verified.verification_id
    unbound = app.harness.resume(trusted("R3"), {"choice": "approve"})
    assert unbound.status == TaskStatus.WAITING_APPROVAL
    assert app.gateway.get_operation(trusted(), operation_id).lookup == "not_found"
    app.bind_verification(trusted("R3"), verified.verification_id)

    original_submit = bank.submit_transfer
    observations = []

    def guarded_submit(*args, **kwargs):
        events = app.audit._events("D1", "T1")
        assert any(event.event_type == "security.decided"
                   and event.payload.decision.phase == Phase.EXECUTION
                   and event.payload.decision.decision == SecurityDecisionCode.ALLOW
                   for event in events)
        assert any(event.event_type == "tool.started"
                   and event.payload.operation_id == operation_id for event in events)
        observations.append(operation_id)
        return original_submit(*args, **kwargs)

    # The bank completes, then application result/audit persistence fails.
    with patch.object(bank, "submit_transfer", side_effect=guarded_submit), \
         patch.object(app, "_record_result", side_effect=RuntimeError("crash")):
        with pytest.raises(RuntimeError, match="crash"):
            app.harness.resume(trusted("R4"), {"choice": "approve"})
    assert observations == [operation_id]
    assert app.gateway.get_operation(trusted(), operation_id).lookup == "found"
    assert not any(event.event_type == "bank.observed"
                   and event.payload.lookup == "found"
                   for event in app.audit._events("D1", "T1"))
    app.close()

    restarted = runtime(path, bank)
    done = restarted.harness.resume(trusted("R5"), {})
    assert done.status == TaskStatus.SUCCEEDED
    assert done.data.operation_id == operation_id
    assert done.run_id == "R5"
    assert len(bank.store.list_ledger("U1", "A1")) == 1
    assert restarted.harness.resume(trusted("R5"), {}) == done
    events = restarted.audit._events("D1", "T1")
    assert len({event.trace_id for event in events}) == 1
    assert {"model.started", "model.finished", "security.decided", "tool.started",
            "tool.finished", "bank.observed", "recovery.checked"} <= {
                event.event_type for event in events
            }
    connection = connect(path)
    try:
        rows = connection.execute("SELECT event_id, operation_id FROM agent_transfer_results").fetchall()
    finally:
        connection.close()
    assert {row["event_id"] for row in rows} == {
        event.event_id for event in events
        if event.event_type == "bank.observed" and event.payload.lookup == "found"
    }
    assert {row["operation_id"] for row in rows} == {str(operation_id)}
    starts = {event.span_id: event for event in events
              if event.event_type == "task.transition"
              and event.payload.reason_code == "NODE_STARTED"}
    assert {"collect", "find_payee", "verify_payee", "precheck",
            "security", "submit", "wait"} <= {
                event.payload.step_id for event in starts.values()
            }
    assert any(event.event_type == "task.transition"
               and event.payload.reason_code == "NODE_FINISHED"
               and event.parent_span_id in starts for event in events)
    assert any(event.event_type == "task.transition"
               and event.payload.reason_code == "NODE_WAITING"
               and event.parent_span_id in starts for event in events)
    assert any(event.event_type == "security.decided"
               and event.parent_span_id in starts for event in events)
    decisions = {event.span_id for event in events
                 if event.event_type == "security.decided"}
    assert any(event.event_type == "tool.started"
               and event.parent_span_id in decisions for event in events)
    restarted.close()


def test_real_policy_denial_stops_before_confirmation_or_bank(tmp_path):
    path = tmp_path / "application.sqlite"
    bank = MockBankService(
        MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4,
    )
    app = runtime(
        path, bank,
        risk=lambda _context, _action, declaration: (
            RiskLevel.HIGH if declaration.side_effect else RiskLevel.LOW
        ),
    )
    now = datetime.now(timezone.utc)
    app.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    denied = app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    assert denied.status == TaskStatus.FAILED
    assert denied.data.operation_id is not None
    assert app.gateway.get_operation(trusted(), denied.data.operation_id).lookup == "not_found"
    assert len(bank.store.list_ledger("U1", "A1")) == 0
    assert any(event.event_type == "security.decided"
               and event.payload.decision.reason_codes == ["HIGH_RISK"]
               for event in app.audit._events("D1", "T1"))
    app.close()


def test_audit_start_failure_prevents_bank_submission(tmp_path):
    path = tmp_path / "application.sqlite"
    bank = MockBankService(
        MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4,
    )
    app = runtime(path, bank)
    now = datetime.now(timezone.utc)
    app.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    pending = app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    app.answer_confirmation(trusted(), ConfirmationAnswer(
        confirmation_id=pending.interaction.record_ref,
        confirmation_version=1, choice="approve",
    ))
    verification = app.harness.resume(trusted("R2"), {"choice": "approve"})
    challenge_id = verification.interaction.record_ref
    code = app.gateway.get_demo_code_for_api(trusted("R2"), challenge_id)
    verified = app.gateway.verify_code(trusted("R2"), challenge_id, uuid4(), code)
    app.bind_verification(trusted("R2"), verified.verification_id)

    append = app.audit.append_in_transaction

    def unavailable(connection, event, **kwargs):
        if event.event_type == "tool.started" and event.payload.operation_id is not None:
            raise RuntimeError("audit unavailable")
        return append(connection, event, **kwargs)

    with patch.object(app.audit, "append_in_transaction", side_effect=unavailable):
        try:
            unexpected = app.harness.resume(trusted("R3"), {"choice": "approve"})
        except RuntimeError as exc:
            assert str(exc) == "audit unavailable"
        else:
            pytest.fail(f"funds path did not reach the audit gate: {unexpected}")
    assert app.gateway.get_operation(trusted(), pending.data.operation_id).lookup == "not_found"
    assert len(bank.store.list_ledger("U1", "A1")) == 0

    done = app.harness.resume(trusted("R4"), {"choice": "approve"})
    assert done.status == TaskStatus.SUCCEEDED
    assert len(bank.store.list_ledger("U1", "A1")) == 1
    app.close()


def test_medium_risk_requires_bound_code_and_face_record(tmp_path):
    path = tmp_path / "application.sqlite"
    bank = MockBankService(
        MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4,
    )
    app = runtime(path, bank, risk=RiskLevel.MEDIUM,
                  authorize_face=lambda admin, *_: admin.authorized)
    now = datetime.now(timezone.utc)
    app.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    pending = app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    operation_id = pending.data.operation_id
    app.answer_confirmation(trusted(), ConfirmationAnswer(
        confirmation_id=pending.interaction.record_ref,
        confirmation_version=1, choice="approve",
    ))
    verification = app.harness.resume(trusted("R2"), {"choice": "approve"})
    assert verification.data.operation_id == operation_id
    assert verification.interaction.kind == "verification"
    challenge_id = verification.interaction.record_ref
    challenge = app.gateway.get_verification(trusted("R2"), challenge_id)
    assert challenge.summary.operation_id == operation_id
    assert challenge.summary.amount_fen == 50_000
    assert challenge.summary.source_confirmation_id == pending.interaction.record_ref

    code = app.gateway.get_demo_code_for_api(trusted("R2"), challenge_id)
    code_result = app.gateway.verify_code(trusted("R2"), challenge_id, uuid4(), code)
    assert code_result.verification_id is None
    assert app.harness.resume(trusted("R3"), {"choice": "approve"}).status == TaskStatus.WAITING_APPROVAL
    assert app.gateway.get_operation(trusted(), operation_id).lookup == "not_found"

    app.gateway.start_face(trusted("R3"), challenge_id, uuid4())
    face_result = app.gateway.verify_face(
        AdminContext(actor_id="admin", authorized=True, demo_round_id="D1",
                     target_user_id="U1"),
        challenge_id, uuid4(), "passed",
    )
    app.bind_verification(trusted("R3"), face_result.verification_id)
    done = app.harness.resume(trusted("R4"), {"choice": "approve"})
    assert done.status == TaskStatus.SUCCEEDED
    assert done.data.operation_id == operation_id
    assert len(bank.store.list_ledger("U1", "A1")) == 1
    app.close()


def test_two_processes_cannot_submit_same_approved_operation_twice(tmp_path):
    path, bank_path = tmp_path / "application.sqlite", tmp_path / "bank.sqlite"
    bank = MockBankService(MockBankStore(bank_path), demo_secret=b"demo-secret" * 4)
    app = runtime(path, bank)
    now = datetime.now(timezone.utc)
    app.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    pending = app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    app.answer_confirmation(trusted(), ConfirmationAnswer(
        confirmation_id=pending.interaction.record_ref,
        confirmation_version=1, choice="approve",
    ))
    verification = app.harness.resume(trusted("R2"), {"choice": "approve"})
    challenge_id = verification.interaction.record_ref
    code = app.gateway.get_demo_code_for_api(trusted("R2"), challenge_id)
    verified = app.gateway.verify_code(trusted("R2"), challenge_id, uuid4(), code)
    app.bind_verification(trusted("R2"), verified.verification_id)
    app.close()

    ctx = get_context("spawn")
    ready, results, release = ctx.Queue(), ctx.Queue(), ctx.Event()
    workers = [ctx.Process(target=_resume_in_process,
                           args=(path, bank_path, ready, release, results))
               for _ in range(2)]
    for worker in workers:
        worker.start()
    for _ in workers:
        assert ready.get(timeout=25)
    release.set()
    for worker in workers:
        worker.join(timeout=30)
        if worker.is_alive():
            worker.terminate()
            worker.join()
        assert worker.exitcode == 0
    assert len(bank.store.list_ledger("U1", "A1")) == 1
    assert len([results.get(timeout=2) for _ in workers]) == 2


def test_two_processes_starting_same_request_keep_one_current_operation(tmp_path):
    path, bank_path = tmp_path / "application.sqlite", tmp_path / "bank.sqlite"
    bank = MockBankService(MockBankStore(bank_path), demo_secret=b"demo-secret" * 4)
    app = runtime(path, bank)
    now = datetime.now(timezone.utc)
    app.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    ctx = get_context("spawn")
    ready, results, release = ctx.Queue(), ctx.Queue(), ctx.Event()
    request_id = uuid4()
    workers = [ctx.Process(target=_start_in_process,
                           args=(path, bank_path, request_id, ready, release, results))
               for _ in range(2)]
    for worker in workers:
        worker.start()
    for _ in workers:
        assert ready.get(timeout=25)
    release.set()
    for worker in workers:
        worker.join(timeout=30)
        if worker.is_alive():
            worker.terminate()
            worker.join()
        assert worker.exitcode == 0
    outcomes = [results.get(timeout=2) for _ in workers]
    current = app.harness.get(trusted())
    assert current.status == TaskStatus.WAITING_APPROVAL, (outcomes, current)
    assert str(current.data.operation_id) in outcomes
    successful = []
    for outcome in outcomes:
        try:
            successful.append(UUID(outcome))
        except ValueError:
            pass
    assert set(successful) == {current.data.operation_id}
    assert len(bank.store.list_ledger("U1", "A1")) == 0
    app.close()
