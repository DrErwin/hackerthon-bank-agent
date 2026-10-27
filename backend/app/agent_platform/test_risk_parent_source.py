"""Platform19: real bound inputs keep parent risk data, never internal markers."""

from uuid import uuid4

import pytest

from app.contracts.common import TaskStatus
from app.security.demo_policy import DemoRiskSignal
from app.security.demo_text_risk import demo_text_risk
from app.security.gate import RiskFactsUnavailable
from app.storage.database import connect
from .risk_inputs import REQUEST_BINDING_REQUIRED, TrustedRiskInputs
from .risk_conversation import RiskConversation
from .test_risk_inputs import (
    LEGAL_TEXT, LOW_SIGNALS, RISK_TEXT, bound_context, flow_control_detector,
    trusted, wired, write_declaration,
)


def linked(tmp_path, parent_text=LEGAL_TEXT):
    runtime, bank, store, holder = wired(tmp_path, flow_control_detector(LOW_SIGNALS))
    pending = runtime.harness.start(trusted(), uuid4(), LEGAL_TEXT)
    parent_request = str(uuid4())
    store.create_task("PARENT", "U1", "S1", "D1", "PR1", TaskStatus.RUNNING,
        {"capability_name": "cross.start_task", "request_id": parent_request,
         "intent_text": parent_text, "trace_id": str(uuid4())})
    child = store.get_task("U1", "D1", "T1")
    store.update_task("U1", "D1", "T1", child.revision, child.run_id, child.status,
        child.checkpoint_id, {**child.snapshot, "intent_text": "transfer.start_transfer:transfer:1",
                             "step_id": "transfer:1", "plan_revision": 6})
    store.link_child_task("U1", "D1", "PARENT", "T1", "transfer:1", 6)
    context, action = bound_context(runtime, store, pending, source_task_id="PARENT")
    return runtime, bank, store, holder["inputs"], context, action, parent_request


def test_parent_request_reaches_the_actual_text_detector_without_marker(tmp_path):
    runtime, bank, store, resolver, context, action, request_id = linked(tmp_path, RISK_TEXT)
    try:
        inputs = resolver.resolve(context, action, write_declaration())
        assert inputs.request_id == request_id
        assert inputs.request_source_task_id == "PARENT"
        assert inputs.request_text == RISK_TEXT
        assert "transfer.start_transfer" not in inputs.request_text
        detected = demo_text_risk(inputs, None)
        assert DemoRiskSignal.IMPERSONATION in detected.signals
        assert DemoRiskSignal.SECRECY_OR_URGENT_PRESSURE in detected.signals
        assert store.get_task("U1", "D1", "T1").status is TaskStatus.WAITING_APPROVAL
        assert bank.store.get_account("U1", "A1").book_balance_fen == 6_000_000
    finally:
        runtime.gateway.close()


def test_parent_and_child_followups_survive_reopen_and_appear_in_the_hash(tmp_path):
    runtime, bank, store, resolver, context, action, request_id = linked(tmp_path)
    try:
        before = resolver.resolve(context, action, write_declaration())
        parent = trusted().model_copy(update={"task_id": "PARENT"})
        resolver.conversation.append(parent, "PARENT", uuid4(), "请共享屏幕")
        resolver.conversation.append(trusted(), "T1", uuid4(), "别告诉家人")
        reopened = TrustedRiskInputs(store, runtime.snapshots, runtime.gateway)
        inputs = reopened.resolve(context, action, write_declaration())
        assert inputs.request_id == request_id
        assert inputs.request_text == LEGAL_TEXT + "\n请共享屏幕\n别告诉家人"
        assert inputs.evidence_ref != before.evidence_ref
        assert "共享屏幕" not in inputs.evidence_ref
        assert DemoRiskSignal.SCREEN_SHARING in demo_text_risk(inputs, None).signals
    finally:
        runtime.gateway.close()


@pytest.mark.parametrize("fault", ["missing_context", "different_context", "relation_missing",
    "step_mismatch", "plan_mismatch", "parent_missing_request", "parent_missing_text", "parent_wrong_capability",
    "relation_user", "relation_round", "missing_parent", "unreadable_parent"])
def test_missing_or_misbound_parent_never_falls_back_to_the_marker(tmp_path, monkeypatch, fault):
    from app.storage.database import transaction

    runtime, bank, store, resolver, context, action, _ = linked(tmp_path)
    try:
        if fault == "missing_context":
            context = context.model_copy(update={"source_task_id": None})
        elif fault == "different_context":
            context = context.model_copy(update={"source_task_id": "OTHER"})
        elif fault == "relation_missing":
            with transaction(store.path) as connection:
                connection.execute("DELETE FROM task_relations WHERE child_task_id='T1'")
        elif fault in {"relation_user", "relation_round"}:
            column, value = ("user_id", "U2") if fault == "relation_user" else ("demo_round_id", "D2")
            with transaction(store.path) as connection:
                connection.execute(f"UPDATE task_relations SET {column}=? WHERE child_task_id='T1'", (value,))
        elif fault in {"missing_parent", "unreadable_parent"}:
            original_get = store.get_task
            def read(user, round_id, task_id):
                if task_id == "PARENT":
                    if fault == "missing_parent": return None
                    raise OSError("source unavailable")
                return original_get(user, round_id, task_id)
            monkeypatch.setattr(store, "get_task", read)
        else:
            task = store.get_task("U1", "D1", "T1" if fault in {"step_mismatch", "plan_mismatch"} else "PARENT")
            snapshot = dict(task.snapshot)
            if fault == "step_mismatch": snapshot["step_id"] = "transfer:2"
            elif fault == "plan_mismatch": snapshot["plan_revision"] = 7
            elif fault == "parent_missing_request": snapshot.pop("request_id")
            elif fault == "parent_missing_text": snapshot.pop("intent_text")
            else: snapshot["capability_name"] = "transfer.start_transfer"
            store.update_task("U1", "D1", task.task_id, task.revision, task.run_id,
                task.status, task.checkpoint_id, snapshot)
        with pytest.raises(RiskFactsUnavailable) as error:
            resolver.resolve(context, action, write_declaration())
        assert error.value.rule_id == REQUEST_BINDING_REQUIRED
        assert bank.store.get_account("U1", "A1").book_balance_fen == 6_000_000
    finally:
        runtime.gateway.close()


def test_real_harness_text_resume_preserves_the_same_request_once(tmp_path):
    runtime, bank, store, holder = wired(tmp_path, flow_control_detector(LOW_SIGNALS))
    try:
        runtime.harness.start(trusted(), uuid4(), LEGAL_TEXT)
        request_id = uuid4()
        # A rejected business input still is a real owned user's risk statement.
        for _ in range(2):
            try:
                runtime.harness.resume(trusted(), {"text": "请共享屏幕"}, request_id=request_id)
            except ValueError:
                pass
        task = store.get_task("U1", "D1", "T1")
        assert RiskConversation(store.path).texts(task) == ["请共享屏幕"]
    finally:
        runtime.gateway.close()


@pytest.mark.parametrize("original,should_block", [(RISK_TEXT, True), (LEGAL_TEXT, False)])
def test_actual_child_dispatch_keeps_parent_text_at_the_real_gate(tmp_path, original, should_block):
    from app.contracts.common import SecurityDecisionCode
    from app.contracts.bank import SavedPayee
    from app.contracts.platform import StartTransferInput
    from .test_birthday_runtime_wiring import composition, trusted as birthday_trusted

    runtime, _ = composition(tmp_path)
    parent = birthday_trusted(runtime)
    try:
        task = runtime.application.get_task("U1", "D1", parent.task_id)
        runtime.application.update_task("U1", "D1", parent.task_id, task.revision,
            task.run_id, task.status, task.checkpoint_id,
            {**task.snapshot, "intent_text": original, "request_id": str(uuid4())})
        request_id = uuid4()
        result = runtime.harness.dispatch_child(parent, "transfer.start_transfer", request_id,
            StartTransferInput(request_id=request_id, intent_text="内部计划转账步骤",
                payer_account_id="A1", payee=SavedPayee(kind="saved", payee_id="A2"), amount_fen=50000),
            step_id="transfer:1", plan_revision=1)
        decisions = [event.payload.decision for event in runtime.audit._events("D1")
            if event.event_type == "security.decided" and event.payload.decision.action_name == "bank.submit_transfer"]
        assert decisions
        if should_block:
            assert decisions[-1].decision is SecurityDecisionCode.BLOCK
            assert result.interaction is None
        else:
            assert result.status is TaskStatus.WAITING_APPROVAL
            assert result.interaction.kind == "confirmation"
        with connect(runtime.bank.store.path) as connection:
            assert connection.execute("SELECT COUNT(*) FROM bank_operations").fetchone()[0] == 0
    finally:
        runtime.gateway.close()
