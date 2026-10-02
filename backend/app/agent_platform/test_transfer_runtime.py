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
from app.contracts.security import ConfirmationAnswer, ExecutionSecurityContext
from app.memory.adapter import MemoryAdapter
from app.security import SecurityError
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


@pytest.mark.parametrize("risk", [RiskLevel.LOW, RiskLevel.MEDIUM])
def test_confirmation_and_verification_show_bank_quote_and_backend_risk(tmp_path, risk):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    app = runtime(tmp_path / "application.sqlite", bank, risk=risk)
    now = datetime.now(timezone.utc)
    app.application.create_session("S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat())
    pending = app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    context = app._context(trusted(), pending.data.operation_id, 1)
    confirmation = app.confirmations.get(context, pending.interaction.record_ref)
    fields = {field.name: field.value_text for field in confirmation.display_fields}
    assert fields["payer_account_id"] == "主账户 尾号 0001"
    assert fields["amount"] == "500.00 元"
    assert fields["bank"] == "模拟合作银行"
    assert fields["fee"] == "0.00 元"
    assert fields["arrival"] == "即时到账"
    assert fields["risk"].startswith("低风险" if risk == RiskLevel.LOW else "中风险")
    assert "6222000000000002" not in str(fields)
    assert len(bank.store.list_ledger("U1", "A1")) == 0
    app.answer_confirmation(trusted(), ConfirmationAnswer(
        confirmation_id=confirmation.confirmation_id, confirmation_version=1, choice="approve",
    ))
    waiting = app.harness.resume(trusted("R2"), {"choice": "approve"})
    challenge = app.gateway.get_verification(trusted("R2"), waiting.interaction.record_ref)
    if risk == RiskLevel.MEDIUM:
        assert challenge.summary.display_fields == confirmation.display_fields
    app.close()


def test_unavailable_confirmation_quote_cannot_create_a_funds_claim(tmp_path):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    app = runtime(tmp_path / "application.sqlite", bank)
    now = datetime.now(timezone.utc)
    app.application.create_session("S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat())
    with patch.object(app.gateway, "quote_transfer", side_effect=RuntimeError("bank unavailable")):
        pending = app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    assert pending.status == TaskStatus.NEEDS_ATTENTION
    assert len(bank.store.list_ledger("U1", "A1")) == 0
    connection = connect(app.application.path)
    assert connection.execute("SELECT COUNT(*) FROM security_executions").fetchone()[0] == 0
    connection.close()
    app.close()


def test_new_session_recovers_before_first_business_checkpoint(tmp_path):
    path = tmp_path / "application.sqlite"
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    app = runtime(path, bank)
    now = datetime.now(timezone.utc)
    for session in ("S1", "S2"):
        app.application.create_session(session, "U1", "D1", now.isoformat(),
                                       (now + timedelta(days=1)).isoformat())
    request_id = uuid4()
    with patch("app.modules.transfer.workflow.TransferWorkflow.start",
               side_effect=RuntimeError("before first checkpoint")):
        with pytest.raises(RuntimeError, match="before first checkpoint"):
            app.harness.start(trusted(), request_id, "给妈妈转 500 元")
    app.close()

    restarted = runtime(path, bank)
    current = trusted("R2").model_copy(update={"session_id": "S2"})
    recovered = restarted.harness.recover_session(current)
    assert recovered.task_id == "T1"
    assert recovered.run_id == "R2"
    assert recovered.status == TaskStatus.WAITING_APPROVAL
    assert restarted.harness.planner.calls == 0
    assert restarted.harness.recover_session(current) == recovered
    assert len(bank.store.list_ledger("U1", "A1")) == 0
    assert len(restarted.application.list_task_operations("U1", "D1", "T1")) == 1
    restarted.answer_confirmation(current, ConfirmationAnswer(
        confirmation_id=recovered.interaction.record_ref,
        confirmation_version=1, choice="approve",
    ))
    verification_identity = current.model_copy(update={"run_id": "R3"})
    verification = restarted.harness.resume(verification_identity, {"choice": "approve"})
    code = restarted.gateway.get_demo_code_for_api(verification_identity, verification.interaction.record_ref)
    verified = restarted.gateway.verify_code(verification_identity, verification.interaction.record_ref, uuid4(), code)
    restarted.bind_verification(verification_identity, verified.verification_id)
    done = restarted.harness.resume(current.model_copy(update={"run_id": "R4"}), {"choice": "approve"})
    assert done.status == TaskStatus.SUCCEEDED
    terminal_identity = current.model_copy(update={"run_id": "R5"})
    terminal = restarted.harness.recover_session(terminal_identity)
    assert terminal.status == TaskStatus.SUCCEEDED
    assert terminal.run_id == "R5"
    assert terminal.data.operation_id == done.data.operation_id
    assert restarted.harness.recover_session(terminal_identity) == terminal
    assert len(bank.store.list_ledger("U1", "A1")) == 1
    restarted.close()


@pytest.mark.parametrize("after_checkpoint_conversion", [False, True])
def test_interrupted_recovery_survives_another_login(tmp_path, after_checkpoint_conversion):
    from app.modules.transfer.workflow import TransferWorkflow
    from app.storage.database import transaction

    path = tmp_path / "application.sqlite"
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    app = runtime(path, bank)
    now = datetime.now(timezone.utc)
    for session in ("S1", "S2", "S3"):
        app.application.create_session(session, "U1", "D1", now.isoformat(),
                                       (now + timedelta(days=1)).isoformat())
    pending = app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    recover = TransferWorkflow.recover_session

    def interrupt(workflow, *args, **kwargs):
        if after_checkpoint_conversion:
            recover(workflow, *args, **kwargs)
        raise RuntimeError("recovery interrupted")

    with patch.object(TransferWorkflow, "recover_session", interrupt):
        with pytest.raises(RuntimeError, match="recovery interrupted"):
            app.harness.recover_session(trusted("R2").model_copy(update={"session_id": "S2"}))
    with transaction(path) as connection:
        connection.execute("UPDATE sessions SET expires_at=? WHERE session_id='S2'",
                           ((now - timedelta(seconds=1)).isoformat(),))
    app.close()

    restarted = runtime(path, bank)
    current = trusted("R3").model_copy(update={"session_id": "S3"})
    recovered = restarted.harness.recover_session(current)
    assert recovered.status == TaskStatus.WAITING_APPROVAL
    assert recovered.task_id == pending.task_id
    assert recovered.data.operation_id == pending.data.operation_id
    assert recovered.run_id == "R3"
    assert restarted.harness.recover_session(current) == recovered
    assert restarted.application.get_task("U1", "D1", "T1").session_id == "S3"
    assert restarted.harness.planner.calls == 0
    assert len(bank.store.list_ledger("U1", "A1")) == 0
    assert len(restarted.application.list_task_operations("U1", "D1", "T1")) == 1
    with pytest.raises(SecurityError):
        restarted.answer_confirmation(current, ConfirmationAnswer(
            confirmation_id=pending.interaction.record_ref, confirmation_version=1,
            choice="approve",
        ))
    restarted.close()


def test_interrupted_new_checkpoint_initialization_retries_after_restart(tmp_path):
    from app.modules.transfer.workflow import TransferWorkflow

    path = tmp_path / "application.sqlite"
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    app = runtime(path, bank)
    now = datetime.now(timezone.utc)
    for session in ("S1", "S2"):
        app.application.create_session(session, "U1", "D1", now.isoformat(),
                                       (now + timedelta(days=1)).isoformat())
    with patch.object(TransferWorkflow, "start", side_effect=RuntimeError("before graph")):
        with pytest.raises(RuntimeError, match="before graph"):
            app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
    current = trusted("R2").model_copy(update={"session_id": "S2"})
    with patch.object(TransferWorkflow, "_collect", side_effect=RuntimeError("graph initialized")):
        with pytest.raises(RuntimeError, match="graph initialized"):
            app.harness.recover_session(current)
    app.close()

    restarted = runtime(path, bank)
    current = current.model_copy(update={"run_id": "R3"})
    recovered = restarted.harness.recover_session(current)
    assert recovered.status == TaskStatus.WAITING_APPROVAL
    assert recovered.run_id == "R3"
    assert restarted.harness.recover_session(current) == recovered
    assert restarted.harness.planner.calls == 0
    assert len(bank.store.list_ledger("U1", "A1")) == 0
    assert len(restarted.application.list_task_operations("U1", "D1", "T1")) == 1
    restarted.close()


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


def test_reserved_operation_is_reused_after_snapshot_interruption(tmp_path):
    path = tmp_path / "application.sqlite"
    bank_path = tmp_path / "bank.sqlite"
    bank = MockBankService(
        MockBankStore(bank_path), demo_secret=b"demo-secret" * 4,
    )
    app = runtime(path, bank)
    now = datetime.now(timezone.utc)
    app.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    request_id = uuid4()
    save = app.snapshots.save
    interrupted = False

    def save_after_reservation(current, action_name, parameters, operation_id=None,
                               action_revision=None):
        nonlocal interrupted
        if action_name == "bank.submit_transfer" and not interrupted:
            interrupted = True
            raise RuntimeError("snapshot interrupted after operation reservation")
        return save(current, action_name, parameters, operation_id, action_revision)

    with patch.object(app.snapshots, "save", side_effect=save_after_reservation):
        with pytest.raises(RuntimeError, match="after operation reservation"):
            app.harness.start(trusted(), request_id, "给妈妈转 500 元")

    operations = app.application.list_task_operations("U1", "D1", "T1")
    assert len(operations) == 1
    operation_id = UUID(operations[0].operation_id)
    assert operations[0].state == "reserved"
    assert app.gateway.get_operation(trusted(), operation_id).lookup == "not_found"
    app.close()

    restarted_bank = MockBankService(
        MockBankStore(bank_path), demo_secret=b"demo-secret" * 4,
    )
    restarted = runtime(path, restarted_bank)
    retried = restarted.harness.start(trusted(), request_id, "给妈妈转 500 元")
    assert retried.status == TaskStatus.WAITING_APPROVAL
    assert retried.data.operation_id == operation_id
    assert [item.operation_id for item in restarted.application.list_task_operations("U1", "D1", "T1")] == [
        str(operation_id),
    ]
    assert restarted.gateway.get_operation(trusted(), operation_id).lookup == "not_found"
    assert len(restarted_bank.store.list_ledger("U1", "A1")) == 0
    restarted.close()


def test_new_session_recovery_queries_original_operation_when_task_summary_lags(tmp_path):
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
    operation_id = pending.data.operation_id
    app.answer_confirmation(trusted(), ConfirmationAnswer(
        confirmation_id=pending.interaction.record_ref,
        confirmation_version=1, choice="approve",
    ))
    verification = app.harness.resume(trusted("R2"), {"choice": "approve"})
    challenge_id = verification.interaction.record_ref
    code = app.gateway.get_demo_code_for_api(trusted("R2"), challenge_id)
    verified = app.gateway.verify_code(trusted("R2"), challenge_id, uuid4(), code)
    app.bind_verification(trusted("R2"), verified.verification_id)

    original_submit = bank.submit_transfer
    submissions = []

    def submit_once(*args, **kwargs):
        submissions.append(operation_id)
        return original_submit(*args, **kwargs)

    with patch.object(bank, "submit_transfer", side_effect=submit_once), \
         patch.object(app, "_record_result", side_effect=RuntimeError("crash after bank")):
        with pytest.raises(RuntimeError, match="crash after bank"):
            app.harness.resume(trusted("R3"), {"choice": "approve"})

    assert submissions == [operation_id]
    assert app.gateway.get_operation(trusted(), operation_id).lookup == "found"
    assert app.application.get_operation("U1", "D1", str(operation_id)).state == "reserved"
    assert len(bank.store.list_ledger("U1", "A1")) == 1

    # The durable graph and operation record are ahead of the API task summary.
    task = app.application.get_task("U1", "D1", "T1")
    app.application.update_task(
        "U1", "D1", "T1", task.revision, task.run_id, TaskStatus.RUNNING,
        task.checkpoint_id,
        {key: value for key, value in task.snapshot.items() if key != "result"},
    )
    app.application.create_session(
        "S2", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    app.close()

    restarted = runtime(path, bank)
    current = trusted("R4").model_copy(update={"session_id": "S2"})
    with patch.object(bank, "submit_transfer", side_effect=AssertionError("must not resubmit")):
        recovered = restarted.harness.recover_session(current)

    assert recovered.status == TaskStatus.SUCCEEDED
    assert recovered.data.operation_id == operation_id
    assert bank.store.get_operation("U1", str(operation_id)).status == "succeeded"
    assert len(bank.store.list_ledger("U1", "A1")) == 1
    recovery_events = [event for event in restarted.audit._events("D1", "T1")
                       if event.event_type == "recovery.checked"]
    started = next(event for event in recovery_events
                   if event.payload.reason_code == "SESSION_RECOVERY_STARTED")
    completed = next(event for event in reversed(recovery_events)
                     if event.payload.reason_code == "SESSION_RECOVERY_COMPLETED")
    assert started.outcome == "started"
    assert started.payload.operation_ids == [operation_id]
    assert completed.payload.operation_ids == [operation_id]
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


def test_new_session_recovery_requires_new_confirmation_and_verification(tmp_path):
    path = tmp_path / "application.sqlite"
    bank = MockBankService(
        MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4,
    )
    app = runtime(
        path, bank, risk=RiskLevel.MEDIUM,
        authorize_face=lambda admin, *_: admin.authorized,
    )
    now = datetime.now(timezone.utc)
    app.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    try:
        pending = app.harness.start(trusted(), uuid4(), "给妈妈转 500 元")
        old_confirmation_id = pending.interaction.record_ref
        app.answer_confirmation(trusted(), ConfirmationAnswer(
            confirmation_id=old_confirmation_id, confirmation_version=1, choice="approve",
        ))
        old_session_verification = app.harness.resume(
            trusted("R2"), {"choice": "approve"},
        )
        assert old_session_verification.interaction.kind == "verification"
        old_challenge_id = old_session_verification.interaction.record_ref
        old_code = app.gateway.get_demo_code_for_api(trusted("R2"), old_challenge_id)
        code_result = app.gateway.verify_code(
            trusted("R2"), old_challenge_id, uuid4(), old_code,
        )
        assert code_result.verification_id is None
        app.gateway.start_face(trusted("R2"), old_challenge_id, uuid4())
        old_verification = app.gateway.verify_face(
            AdminContext(actor_id="admin", authorized=True, demo_round_id="D1",
                         target_user_id="U1"),
            old_challenge_id, uuid4(), "passed",
        )
        app.bind_verification(trusted("R2"), old_verification.verification_id)

        app.application.create_session(
            "S2", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
        )
        current = trusted("R3").model_copy(update={"session_id": "S2"})
        recovered = app.harness.recover_session(current)
        assert recovered.status == TaskStatus.WAITING_APPROVAL, recovered.error
        assert recovered.interaction.kind == "confirmation"
        assert recovered.data.operation_id == pending.data.operation_id
        assert app.gateway.get_operation(current, pending.data.operation_id).lookup == "not_found"

        current_context = ExecutionSecurityContext(
            user_id=current.user_id, session_id=current.session_id,
            demo_round_id=current.demo_round_id, task_id=current.task_id,
            run_id=current.run_id, source_task_id=current.parent_task_id,
            operation_id=None, action_revision=None, confirmation_id=None,
            confirmation_version=None, verification_ids=[],
            release_authorization_id=None,
        )
        confirmation = app.confirmations.get(
            current_context, recovered.interaction.record_ref,
        )
        assert confirmation.confirmation_version == 2

        with pytest.raises(SecurityError, match="CONFIRMATION_STALE"):
            app.answer_confirmation(current, ConfirmationAnswer(
                confirmation_id=old_confirmation_id, confirmation_version=1, choice="approve",
            ))
        app.answer_confirmation(current, ConfirmationAnswer(
            confirmation_id=recovered.interaction.record_ref,
            confirmation_version=confirmation.confirmation_version, choice="approve",
        ))
        new_verification = app.harness.resume(current, {"choice": "approve"})
        assert new_verification.status == TaskStatus.WAITING_APPROVAL
        assert new_verification.interaction.kind == "verification"
        assert new_verification.interaction.record_ref != old_challenge_id
        assert app.gateway.get_operation(current, pending.data.operation_id).lookup == "not_found"
        assert len(bank.store.list_ledger("U1", "A1")) == 0
    finally:
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
