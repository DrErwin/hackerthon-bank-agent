"""Ticket v05-cross-platform/03: controlled child dispatch, recovery and the D1 seam."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.audit.journal import AuditJournal
from app.contracts.bills import BillScope, BillSummarizeInput
from app.contracts.common import OperationLevel, TaskStatus
from app.contracts.platform import (
    CapabilityDefinition, ModuleManifest, StartTransferInput, TrustedContext,
)
from app.contracts.subscription import SubscriptionCancelInput, SubscriptionListInput
from app.contracts.tasks import InteractionRequest, ModuleResult
from app.memory.adapter import MemoryAdapter
from app.services.mock_bank.core import MockBankService
from app.storage.application import ApplicationStore, ArrangementConflictError
from app.storage.mock_bank.repository import MockBankStore

from .harness import AgentHarness
from .registry import CapabilityRegistry
from .test_transfer_runtime import runtime as transfer_runtime
from .test_transfer_runtime import trusted as transfer_trusted


NOW = datetime.now(timezone.utc)


class PlannerStub:
    provider = "scripted"
    model_name = "child-dispatch-test"
    config_version = "test-v3"


class ScriptedEntry:
    """A contract-conformant child business whose outcomes come from a script."""

    def __init__(self, script: list[ModuleResult]):
        self.script = script

    def _next(self, trusted) -> ModuleResult:
        return self.script.pop(0).model_copy(
            update={"task_id": trusted.task_id, "run_id": trusted.run_id},
        )

    def start(self, trusted, request, *, thread_id=None):
        return self._next(trusted)

    def resume(self, trusted, response, *, thread_id=None):
        return self._next(trusted)

    def recover_session(self, trusted, *, source_session_id, thread_id=None):
        return self._next(trusted)

    def checkpoint_context(self, trusted, *, thread_id=None):
        return None


def waiting_input(task_id, run_id):
    return ModuleResult(
        task_id=task_id, run_id=run_id, status=TaskStatus.WAITING_INPUT, data=None,
        message="请补充金额。", interaction=InteractionRequest(
            interaction_id="I1", kind="input", prompt="金额", required_fields=["amount_fen"],
            options=[], record_ref=None,
        ), error=None, allowed_actions=["provide_input", "cancel"],
        recovery_required=False, recovery_reason=None,
    )


def waiting_confirmation(task_id, run_id):
    return ModuleResult(
        task_id=task_id, run_id=run_id, status=TaskStatus.WAITING_APPROVAL, data=None,
        message="请确认。", interaction=InteractionRequest(
            interaction_id="I2", kind="confirmation", prompt="确认办理", required_fields=[],
            options=[], record_ref="CONF1",
        ), error=None, allowed_actions=["confirm", "cancel"],
        recovery_required=False, recovery_reason=None,
    )


def waiting_verification(task_id, run_id):
    return ModuleResult(
        task_id=task_id, run_id=run_id, status=TaskStatus.WAITING_APPROVAL, data=None,
        message="请验证。", interaction=InteractionRequest(
            interaction_id="I3", kind="verification", prompt="身份验证", required_fields=[],
            options=[], record_ref="VERI1",
        ), error=None, allowed_actions=["verify", "cancel"],
        recovery_required=False, recovery_reason=None,
    )


def finished(task_id, run_id, status, *, message="结束"):
    return ModuleResult(
        task_id=task_id, run_id=run_id, status=status, data=None, message=message,
        interaction=None, error=None, allowed_actions=[], recovery_required=False,
        recovery_reason=None,
    )


def scripted_registry(script: list[ModuleResult]) -> CapabilityRegistry:
    manifest = ModuleManifest(
        module_name="scripted", version="v1", owner="test", description="scripted child",
        implementation_kind="workflow", capabilities=[
            CapabilityDefinition(
                name="scripted.write", input_schema_ref="StartTransferInput#1",
                output_schema_ref="ModuleResult#1", required_permissions=[],
                operation_level=OperationLevel.SENSITIVE, side_effect=True,
                confirmation_policy="per_action", timeout_ms=60000, retry_policy="none",
                handler_ref="test",
            ),
            CapabilityDefinition(
                name="scripted.read", input_schema_ref="StartTransferInput#1",
                output_schema_ref="ModuleResult#1", required_permissions=[],
                operation_level=OperationLevel.READ, side_effect=False,
                confirmation_policy="none", timeout_ms=60000, retry_policy="read_only",
                handler_ref="test",
            ),
        ], dependencies=[],
    )

    def factory(_trusted, _saver, _trace):
        return ScriptedEntry(script)

    registry = CapabilityRegistry()
    registry.register_module(manifest, factory)
    return registry


def harness_with_parent(path, script):
    application = ApplicationStore(path)
    harness = AgentHarness(
        application, MemoryAdapter(application, active_round=lambda: "D1"),
        AuditJournal(path), scripted_registry(script), PlannerStub(),
        authorize_capability=lambda _trusted, _definition: True,
    )
    if harness.application.get_session("U1", "D1", "S1") is None:
        harness.application.create_session(
            "S1", "U1", "D1", NOW.isoformat(), (NOW + timedelta(days=1)).isoformat(),
        )
    if harness.application.get_task("U1", "D1", "PARENT") is None:
        harness.application.create_task("PARENT", "U1", "S1", "D1", "PR1", "running", {})
    return harness


def parent() -> TrustedContext:
    return TrustedContext(user_id="U1", session_id="S1", task_id="PARENT",
                          run_id="PR1", parent_task_id=None, demo_round_id="D1")


def write_input(**overrides) -> StartTransferInput:
    payload = {"request_id": uuid4(), "intent_text": "scripted write",
               "payer_account_id": None, "payee_hint": None, "amount_fen": None}
    return StartTransferInput(**(payload | overrides))


def test_dispatch_runs_one_interactive_step_and_reads_interleave(tmp_path):
    script = [waiting_input("pending", "pending")]
    harness = harness_with_parent(tmp_path / "app.sqlite", script)
    first = harness.dispatch_child(
        parent(), "scripted.write", uuid4(), write_input(), step_id="pay_1", plan_revision=1,
    )
    assert first.status is TaskStatus.WAITING_INPUT
    child_id = first.task_id
    assert child_id != "PARENT"
    assert harness.application.parent_of_task("U1", "D1", child_id) == "PARENT"
    summaries = harness.child_task_summaries(parent())
    assert [(s["step_id"], s["status"]) for s in summaries] == [("pay_1", "waiting_input")]

    # A second side-effect step cannot start, repeated request included; reads can.
    with pytest.raises(ValueError, match="CHILD_STEP_ALREADY_ACTIVE"):
        harness.dispatch_child(
            parent(), "scripted.write", uuid4(), write_input(), step_id="pay_2", plan_revision=1,
        )
    script.append(finished("r", "r", TaskStatus.SUCCEEDED))
    read = harness.dispatch_child(
        parent(), "scripted.read", uuid4(), write_input(), step_id="query_1", plan_revision=1,
    )
    assert read.status is TaskStatus.SUCCEEDED
    assert len(harness.child_task_summaries(parent())) == 2

    with pytest.raises(ValueError):
        harness.dispatch_child(parent(), "scripted.missing", uuid4(), write_input(),
                               step_id="x", plan_revision=1)
    with pytest.raises(ValueError, match="INVALID_CAPABILITY_INPUT"):
        harness.dispatch_child(parent(), "scripted.read", uuid4(), {"not": "a contract"},
                               step_id="x", plan_revision=1)


def test_dispatch_validates_input_against_the_declared_contract(tmp_path):
    """G1: bills and subscription children carry their own typed contracts.

    A capability accepts exactly the input its manifest declares; the transfer
    envelope is refused for them, so a parent cannot smuggle bills or
    subscription parameters through StartTransferInput.
    """
    script = [finished("r", "r", TaskStatus.SUCCEEDED)]
    harness = harness_with_parent(tmp_path / "app.sqlite", script)
    manifest = ModuleManifest(
        module_name="typed", version="v1", owner="test", description="typed children",
        implementation_kind="workflow", capabilities=[
            CapabilityDefinition(
                name="typed.bills", input_schema_ref="BillSummarizeInput",
                output_schema_ref="ModuleResult#1", required_permissions=[],
                operation_level=OperationLevel.READ, side_effect=False,
                confirmation_policy="none", timeout_ms=60000, retry_policy="read_only",
                handler_ref="test",
            ),
            CapabilityDefinition(
                name="typed.subscription_cancel", input_schema_ref="SubscriptionCancelInput",
                output_schema_ref="ModuleResult#1", required_permissions=[],
                operation_level=OperationLevel.SENSITIVE, side_effect=True,
                confirmation_policy="per_action", timeout_ms=60000, retry_policy="none",
                handler_ref="test",
            ),
            CapabilityDefinition(
                name="typed.unknown_ref", input_schema_ref="NotAPublicContract",
                output_schema_ref="ModuleResult#1", required_permissions=[],
                operation_level=OperationLevel.READ, side_effect=False,
                confirmation_policy="none", timeout_ms=60000, retry_policy="read_only",
                handler_ref="test",
            ),
        ], dependencies=[],
    )
    harness.registry.register_module(manifest, lambda _trusted, _saver, _trace: ScriptedEntry(script))
    scope = BillScope.model_validate({
        "account_ids": ["A1"],
        "start_at": "2026-09-01T00:00:00+00:00", "end_at": "2026-10-01T00:00:00+00:00",
    })
    legal_bills = BillSummarizeInput(scope=scope)
    assert harness.dispatch_child(
        parent(), "typed.bills", uuid4(), legal_bills, step_id="compare", plan_revision=1,
    ).status is TaskStatus.SUCCEEDED
    script.append(finished("w", "w", TaskStatus.SUCCEEDED))
    legal_cancel = SubscriptionCancelInput(
        request_id=uuid4(), intent_text="退订优酷视频", subscription_id="sub_001",
    )
    assert harness.dispatch_child(
        parent(), "typed.subscription_cancel", uuid4(), legal_cancel,
        step_id="cancel_1", plan_revision=1,
    ).status is TaskStatus.SUCCEEDED

    # Wrong shapes fail before any task exists: another capability's contract,
    # the transfer envelope, plain dicts and undeclared refs alike.
    for capability, payload in (
        ("typed.bills", SubscriptionListInput(request_id=uuid4(), intent_text="看签约")),
        ("typed.bills", write_input()),
        ("typed.subscription_cancel", write_input()),
        ("typed.subscription_cancel", {"subscription_id": "sub_001"}),
        ("typed.unknown_ref", write_input()),
    ):
        with pytest.raises(ValueError, match="INVALID_CAPABILITY_INPUT"):
            harness.dispatch_child(parent(), capability, uuid4(), payload,
                                   step_id="rejected", plan_revision=1)
    extra = [item for item in harness.child_task_summaries(parent())
             if item["step_id"] == "rejected"]
    assert extra == []


def test_child_waiting_input_confirmation_verification_then_success(tmp_path):
    script: list[ModuleResult] = [waiting_input("c", "c")]
    harness = harness_with_parent(tmp_path / "app.sqlite", script)
    first = harness.dispatch_child(
        parent(), "scripted.write", uuid4(), write_input(), step_id="pay_1", plan_revision=2,
    )
    assert first.interaction.kind == "input"
    with pytest.raises(ValueError, match="PLAN_SUPERSEDED"):
        harness.resume_child(parent(), first.task_id, {"text": "100 元"}, plan_revision=1)

    script.extend([waiting_confirmation("c", "c"), waiting_verification("c", "c"),
                   finished("c", "c", TaskStatus.SUCCEEDED)])
    confirmed = harness.resume_child(parent(), first.task_id, {"text": "100 元"}, plan_revision=2)
    assert confirmed.status is TaskStatus.WAITING_APPROVAL
    assert confirmed.interaction.kind == "confirmation"
    verified = harness.resume_child(parent(), first.task_id, {"choice": "approve"}, plan_revision=2)
    assert verified.interaction.kind == "verification"
    done = harness.resume_child(parent(), first.task_id, {"code": "123456"}, plan_revision=2)
    assert done.status is TaskStatus.SUCCEEDED

    # The finished step frees the single-active-step slot for the next write step.
    script.append(finished("c2", "c2", TaskStatus.SUCCEEDED))
    nxt = harness.dispatch_child(
        parent(), "scripted.write", uuid4(), write_input(), step_id="pay_2", plan_revision=2,
    )
    assert nxt.status is TaskStatus.SUCCEEDED
    with pytest.raises(PermissionError):
        stranger = TrustedContext(user_id="U1", session_id="S1", task_id="PARENT",
                                  run_id="PR1", parent_task_id=None, demo_round_id="D2")
        harness.resume_child(stranger, first.task_id, {}, plan_revision=2)


def test_failed_child_frees_slot_but_unknown_blocks_new_steps(tmp_path):
    script = [finished("c", "c", TaskStatus.FAILED, message="银行拒绝")]
    harness = harness_with_parent(tmp_path / "app.sqlite", script)
    failed = harness.dispatch_child(
        parent(), "scripted.write", uuid4(), write_input(), step_id="pay_1", plan_revision=1,
    )
    assert failed.status is TaskStatus.FAILED

    script.append(ModuleResult(
        task_id="c2", run_id="c2", status=TaskStatus.NEEDS_ATTENTION, data=None,
        message="付款未知", interaction=None, error=None, allowed_actions=["query", "cancel"],
        recovery_required=True, recovery_reason="OPERATION_UNKNOWN",
    ))
    harness.dispatch_child(
        parent(), "scripted.write", uuid4(), write_input(), step_id="pay_2", plan_revision=1,
    )
    with pytest.raises(ValueError, match="CHILD_STEP_ALREADY_ACTIVE"):
        harness.dispatch_child(
            parent(), "scripted.write", uuid4(), write_input(), step_id="pay_3", plan_revision=1,
        )


def test_restart_keeps_original_association_and_continues(tmp_path):
    path = tmp_path / "app.sqlite"
    script: list[ModuleResult] = []
    harness = harness_with_parent(path, script)
    script.append(waiting_input("c", "c"))
    first = harness.dispatch_child(
        parent(), "scripted.write", uuid4(), write_input(), step_id="pay_1", plan_revision=1,
    )

    restarted = harness_with_parent(path, script)
    summaries = restarted.child_task_summaries(parent())
    assert [(s["child_task_id"], s["status"]) for s in summaries] == [
        (first.task_id, "waiting_input"),
    ]
    script.append(finished("c", "c", TaskStatus.SUCCEEDED))
    done = restarted.resume_child(parent(), first.task_id, {"text": "100 元"}, plan_revision=1)
    assert done.status is TaskStatus.SUCCEEDED
    assert restarted.child_task_summaries(parent())[0]["status"] == "succeeded"


def _arrangement(task_id: str, payer: str):
    from app.contracts import AdoptedArrangement

    return AdoptedArrangement.model_validate({
        "arrangement_id": f"arr_{task_id}", "user_id": "U1", "demo_round_id": "D1",
        "source_task_id": task_id, "plan_revision": 1, "payer_account_id": payer,
        "funds_basis": "available_balance", "income_transaction_ids": [],
        "base_fen": 500000, "living_reserve_fen": 150000,
        "reserve_includes_known_debits": True,
        "upcoming_debit_scope": {
            "account_ids": [payer], "start_at": "2026-10-01T00:00:00+08:00",
            "end_at": "2026-11-01T00:00:00+08:00",
        },
        "known_debits_fen": 0, "adopted_at": NOW.isoformat(),
        "adoption_interaction_id": "I1", "status": "active",
    })


def test_dispatch_checks_d1_before_creating_the_child(tmp_path):
    script = [waiting_input("c", "c")]
    harness = harness_with_parent(tmp_path / "app.sqlite", script)
    harness.application.create_task("OTHER", "U1", "S1", "D1", "R2", "running", {})
    harness.application.acquire_arrangement(_arrangement("OTHER", "A1"))

    with pytest.raises(ArrangementConflictError):
        harness.dispatch_child(
            parent(), "scripted.write", uuid4(), write_input(payer_account_id="A1"),
            step_id="pay_1", plan_revision=1,
        )
    assert harness.child_task_summaries(parent()) == []

    # Reads never consult the arrangement; the holder's own lineage dispatches freely.
    script[:] = [finished("r", "r", TaskStatus.SUCCEEDED)]
    assert harness.dispatch_child(
        parent(), "scripted.read", uuid4(), write_input(), step_id="query_1", plan_revision=1,
    ).status is TaskStatus.SUCCEEDED

    harness.application.close_arrangement("U1", "D1", "arr_OTHER")
    harness.application.acquire_arrangement(_arrangement("PARENT", "A1"))
    script.append(waiting_input("c2", "c2"))
    assert harness.dispatch_child(
        parent(), "scripted.write", uuid4(), write_input(payer_account_id="A1"),
        step_id="pay_2", plan_revision=1,
    ).status is TaskStatus.WAITING_INPUT


def test_ordinary_transfer_pauses_on_d1_before_any_bank_write(tmp_path):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    app = transfer_runtime(tmp_path / "application.sqlite", bank)
    now = datetime.now(timezone.utc)
    app.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    app.application.create_task("OTHER", "U1", "S1", "D1", "R9", "running", {})
    app.application.acquire_arrangement(_arrangement("OTHER", "A1"))

    from app.contracts.security import ConfirmationAnswer

    pending = app.harness.start(transfer_trusted(), uuid4(), "给妈妈转 500 元")
    assert pending.status is TaskStatus.WAITING_APPROVAL
    context = app._context(transfer_trusted(), pending.data.operation_id, 1)
    confirmation = app.confirmations.get(context, pending.interaction.record_ref)
    app.answer_confirmation(transfer_trusted(), ConfirmationAnswer(
        confirmation_id=confirmation.confirmation_id, confirmation_version=1, choice="approve",
    ))
    verification_identity = transfer_trusted("R3")
    verification = app.harness.resume(verification_identity, {"choice": "approve"})
    code = app.gateway.get_demo_code_for_api(verification_identity, verification.interaction.record_ref)
    verified = app.gateway.verify_code(
        verification_identity, verification.interaction.record_ref, uuid4(), code,
    )
    app.bind_verification(verification_identity, verified.verification_id)
    paused = app.harness.resume(transfer_trusted("R4"), {"choice": "approve"})
    # D1 pauses the conflicting spend for attention; it is not a bank rejection.
    assert paused.status is TaskStatus.NEEDS_ATTENTION
    assert paused.error.code == "ARRANGEMENT_CONFLICT"
    assert paused.recovery_required is True
    assert paused.recovery_reason == "ARRANGEMENT_CONFLICT"
    # The pause happened before submission: no bank movement and no ledger row.
    assert bank.store.list_ledger("U1", "A1") == []
    app.close()


def test_holder_lineage_lets_its_own_child_transfer_proceed(tmp_path):
    bank = MockBankService(MockBankStore(tmp_path / "bank.sqlite"), demo_secret=b"demo-secret" * 4)
    app = transfer_runtime(tmp_path / "application.sqlite", bank)
    now = datetime.now(timezone.utc)
    app.application.create_session(
        "S1", "U1", "D1", now.isoformat(), (now + timedelta(days=1)).isoformat(),
    )
    app.application.create_task("CROSS_PARENT", "U1", "S1", "D1", "PR1", "running", {})
    app.application.acquire_arrangement(_arrangement("CROSS_PARENT", "A1"))

    parent_trusted = TrustedContext(user_id="U1", session_id="S1", task_id="CROSS_PARENT",
                                    run_id="PR1", parent_task_id=None, demo_round_id="D1")
    child = app.harness.dispatch_child(
        parent_trusted, "transfer.start_transfer", uuid4(),
        StartTransferInput(request_id=uuid4(), intent_text="给妈妈转 500 元",
                           payee_hint="妈妈", amount_fen=50000, payer_account_id="A1"),
        step_id="transfer_01", plan_revision=1,
    )
    assert child.status is TaskStatus.WAITING_APPROVAL
    assert app.application.parent_of_task("U1", "D1", child.task_id) == "CROSS_PARENT"
    app.close()
