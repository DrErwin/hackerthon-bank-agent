"""Business reset time stays separate from real confirmation/verification expiry."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from app.api.test_app import approve, start
from app.audit.journal import AuditReader, AuditViewer
from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from app.memory.adapter import MemoryContext
from app.services.mock_bank.verification import AdminContext

from .birthday_edit import EDIT_OPTION_LABEL
from .local_demo import build_runtime
from .test_birthday_harness_publication import harness_env
from .test_birthday_runtime_wiring import DELIVERY_REF, approve_confirmation, option_id
from .test_local_demo import ConnectorTestModel, app_for, configuration


INITIAL = datetime(2031, 6, 12, 9, tzinfo=timezone(timedelta(hours=8)))


def runtime_for(config):
    with patch("app.agent_platform.local_demo.ChatOpenAI", return_value=ConnectorTestModel()):
        return build_runtime(config)


def trusted(round_id="D1"):
    return TrustedContext(user_id="U1", session_id="S1", task_id="T1", run_id="R1",
                          parent_task_id=None, demo_round_id=round_id)


def test_registered_business_clocks_observe_later_setter(tmp_path):
    runtime = runtime_for(configuration(tmp_path))
    try:
        clocks = [runtime.bank.clock, runtime.bank.birthday.clock, runtime.bank.demo.clock]
        for name in ("bills.summarize", "bills.detect_anomalies", "bills.generate_report",
                     "subscription.list_subscriptions", "cross.start_task"):
            entry = runtime.harness.registry.get(name).factory(trusted(), None, None)
            clocks.append(entry.clock if name.startswith("cross.") else entry.service.clock)
        runtime.set_demo_clock(INITIAL)
        assert all(clock() == INITIAL for clock in clocks)
        later = INITIAL + timedelta(days=40)
        runtime.set_demo_clock(later)
        assert all(clock() == later for clock in clocks)
        with pytest.raises(ValueError, match="INVALID_ARGUMENT"):
            runtime.set_demo_clock(datetime(2031, 1, 1))
        assert all(clock() == later for clock in clocks)
        runtime.set_demo_clock(datetime(2031, 6, 30, 16, tzinfo=timezone.utc))
        assert all((clock().month, clock().day, clock().hour) == (7, 1, 0)
                   for clock in clocks)
    finally:
        runtime.close()


def test_bank_reset_round_and_start_survive_runtime_restart(tmp_path):
    config = configuration(tmp_path)
    runtime = runtime_for(config)
    declaration = runtime.harness.registry.get("cross.start_task").definition
    try:
        assert runtime.memory.active_round() == config.demo_round_id
        assert runtime.harness.authorize_capability(trusted(), declaration)
        result = runtime.bank.reset_demo(
            AdminContext(config.admin_actor_id, True, "D1", "U1"),
            "reset-clock-1", "D1", "D2", INITIAL)
        assert result.status == "succeeded"
        runtime.set_demo_clock(result.logical_at)
        assert runtime.memory.active_round() == "D2"
        assert runtime.birthday.current_demo_round() == "D2"
        assert not runtime.harness.authorize_capability(trusted(), declaration)
        assert runtime.harness.authorize_capability(trusted("D2"), declaration)
        with pytest.raises(ValueError, match="STALE_ROUND"):
            runtime.memory.agent_backend(MemoryContext("U1", "S1", "D1"))
    finally:
        runtime.close()
    restarted = runtime_for(config)
    try:
        assert restarted.bank.current_demo_round_id == "D2"
        assert restarted.memory.active_round() == "D2"
        assert restarted.birthday.current_demo_round() == "D2"
        assert restarted.bank.clock() == INITIAL
        assert restarted.harness.authorize_capability(trusted("D2"), declaration)
        assert not restarted.harness.authorize_capability(trusted(), declaration)
    finally:
        restarted.close()


def test_business_time_does_not_expire_or_extend_security_waits(tmp_path, monkeypatch):
    app = app_for(configuration(tmp_path))
    runtime = app.state.api.runtime
    with TestClient(app) as client:
        _, task = start(client)
        ref = task["interaction"]["record_ref"]
        before = client.get(f"/api/v1/confirmations/{ref}").json()["data"]
        runtime.set_demo_clock(INITIAL)
        after = client.get(f"/api/v1/confirmations/{ref}").json()["data"]
        assert after == before
        waiting = approve(client, task)
        owner = runtime.application.get_task("U1", "D1", task["task_id"])
        who = trusted().model_copy(update={"session_id": owner.session_id,
                                          "task_id": owner.task_id, "run_id": owner.run_id})
        challenge_ref = waiting["interaction"]["record_ref"]
        challenge = runtime.bank.verification.get_verification(who, challenge_ref)
        assert abs((challenge.code_created_at - datetime.now(timezone.utc)).total_seconds()) < 30
        assert challenge.code_expires_at - challenge.code_created_at == timedelta(minutes=5)
        runtime.set_demo_clock(INITIAL - timedelta(days=4000))
        assert runtime.bank.verification.get_verification(who, challenge_ref) == challenge
        monkeypatch.setattr(runtime.bank.verification, "clock",
                            lambda: challenge.code_expires_at + timedelta(seconds=1))
        assert runtime.bank.verification.get_verification(who, challenge_ref).code_result == "expired"


@pytest.mark.parametrize("business_at", [INITIAL, INITIAL - timedelta(days=8000)],
                         ids=["forward", "backward"])
def test_controlled_edit_retirement_and_audit_use_real_time(harness_env, business_at):
    env = harness_env
    env.runtime.set_demo_clock(business_at)
    current = env.start()
    for text in ("500元", (business_at + timedelta(days=3)).date().isoformat(), DELIVERY_REF):
        current = env.resume({"text": text})
    for choice in ("鲜花", "蛋糕", "就选这些", "采用并开始办理"):
        current = env.resume({"selected_option_id": option_id(current, choice)})
    assert current.interaction.kind == "confirmation"
    approve_confirmation(env.runtime, env.who, current.interaction.record_ref)
    current = env.resume({"choice": "approve"})
    assert current.interaction.kind == "verification"
    original = env.snapshot()["birthday_actions"]["freeze"]
    edit_option = next(option.id for option in current.interaction.options
                       if option.label == EDIT_OPTION_LABEL)

    before = datetime.now(timezone.utc)
    outcome = env.runtime.birthday.handoff.begin_birthday_edit(
        env.who, request_id=uuid4(),
        interaction_id=current.interaction.interaction_id, option_id=edit_option)
    after = datetime.now(timezone.utc)

    assert outcome.result.status is TaskStatus.WAITING_INPUT
    operation_id = UUID(original["operation_id"])
    context = env.runtime._context(env.who, operation_id, original["action_revision"])
    retirement = env.runtime.confirmations.state.get_retirement(
        context, env.who.task_id, operation_id, original["action_revision"])
    assert retirement.state == "sealed"
    bank_retired_at = datetime.fromisoformat(retirement.bank_evidence["retired_at"])
    assert before <= retirement.created_at <= bank_retired_at <= retirement.sealed_at <= after
    reader = AuditReader(env.runtime.audit, authorize=lambda *_: True)
    event = reader.detail(AuditViewer("U1", "S1", "D1"), "D1", retirement.audit_ref)
    assert event.event_type == "security.decided"
    assert event.timestamp == retirement.sealed_at
    assert event.payload.decision.checked_at == retirement.sealed_at
    assert datetime.fromisoformat(env.snapshot()["birthday_edit"]["accepted_at"]) == business_at
