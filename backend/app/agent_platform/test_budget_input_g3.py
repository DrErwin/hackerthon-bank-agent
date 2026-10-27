"""Dedicated budget input over real G3/Cross/adoption; NoopModel, new DBs."""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.contracts.common import TaskStatus

from .test_birthday_harness_publication import harness_env
from .test_birthday_runtime_wiring import NoopModel, option_id


def budget_candidate(env):
    current = env.start()
    current = env.resume({"selected_option_id": option_id(current, "设置本月")})
    return env.resume({"text": "10000元"})


def test_dedicated_budget_completion_follows_its_g3_publication(harness_env, monkeypatch):
    env = harness_env
    candidate = budget_candidate(env)
    request_id = uuid4()
    adopt = Mock(wraps=env.runtime.application.adopt_budget)
    monkeypatch.setattr(env.runtime.application, "adopt_budget", adopt)
    try:
        completion = env.runtime.harness.resume_budget_input(env.who,
            input_request_id=request_id, interaction_id=candidate.interaction.interaction_id,
            selected_option_id=option_id(candidate, "采用个人预算"))
    finally:
        records = env.runtime.application.list_adopted_budgets("U1", "D1")
        assert len(records) == 1
        assert records[0].version == 1 and records[0].personal_limit_fen == 1_000_000
        assert adopt.call_count == 1
    assert completion.result.status is TaskStatus.WAITING_INPUT
    assert any("继续生日" in option.label for option in completion.result.interaction.options)
    record = env.runtime.harness.budget_input_record(env.who, request_id)
    assert record["phase"] == "completed"
    assert record["completion"]["attempt_ref"]
    assert completion.task_revision == env.task().revision
    assert env.runtime.harness.budget_input_origin(env.who) is None
    with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
        env.runtime.harness.resume_budget_input(env.who, input_request_id=request_id,
            interaction_id=candidate.interaction.interaction_id,
            selected_option_id=option_id(candidate, "修改个人限额"))


@pytest.mark.parametrize("advance_current", [False, True])
@pytest.mark.parametrize("restart", [False, True])
def test_published_budget_recovers_original_winner_without_adopting_again(
        harness_env, monkeypatch, advance_current, restart):
    env = harness_env
    candidate = budget_candidate(env)
    request_id = uuid4()
    interaction = candidate.interaction.interaction_id
    option = option_id(candidate, "采用个人预算")
    adopt = Mock(wraps=env.runtime.application.adopt_budget)
    monkeypatch.setattr(env.runtime.application, "adopt_budget", adopt)
    update = env.runtime.application.update_task

    def fail_completion(*args, **kwargs):
        record = args[-1].get("budget_input_origins", {}).get(str(request_id), {})
        if record.get("phase") == "completed":
            raise OSError("completion CAS interrupted")
        return update(*args, **kwargs)

    with monkeypatch.context() as fault:
        fault.setattr(env.runtime.application, "update_task", fail_completion)
        with pytest.raises(OSError, match="completion CAS interrupted"):
            env.runtime.harness.resume_budget_input(env.who, input_request_id=request_id,
                interaction_id=interaction, selected_option_id=option)
    record = env.runtime.harness.budget_input_record(env.who, request_id)
    winner = env.runtime.harness.birthday_handoff.find_input_conversion(env.who, record["origin_id"])
    assert winner is not None and winner != "pending"
    if advance_current:
        env.resume({"selected_option_id": option_id(winner.result, "继续生日")})
    current = env.task().snapshot["result"]
    if restart:
        from .local_demo import build_runtime
        from .test_local_demo import configuration

        directory = env.runtime.application.path.parent
        env.runtime.gateway.close()
        with patch("app.agent_platform.local_demo.ChatOpenAI",
                   return_value=NoopModel(response_mode="none")):
            env.runtime = build_runtime(configuration(directory))
        new_adopt = Mock(wraps=env.runtime.application.adopt_budget)
        monkeypatch.setattr(env.runtime.application, "adopt_budget", new_adopt)
    completion = env.runtime.harness.resume_budget_input(
        env.who.model_copy(update={"run_id": str(uuid4())}), input_request_id=request_id,
        interaction_id=interaction, selected_option_id=option)
    assert completion.result == winner.result
    assert completion.task_revision == winner.task_revision
    assert env.task().snapshot["result"] == current
    assert adopt.call_count == 1
    if restart:
        assert new_adopt.call_count == 0
    assert len(env.runtime.application.list_adopted_budgets("U1", "D1")) == 1
    assert env.runtime.harness.budget_input_origin(env.who) is None


@pytest.mark.parametrize("boundary", ["before_reserve", "after_publish"])
def test_external_cas_never_becomes_the_budget_call_own_publication(
        harness_env, monkeypatch, boundary):
    from .birthday_edit import BirthdayTransition

    env = harness_env
    candidate = budget_candidate(env)
    request_id = uuid4()
    original_publish = BirthdayTransition.publish
    adopt = Mock(wraps=env.runtime.application.adopt_budget)
    monkeypatch.setattr(env.runtime.application, "adopt_budget", adopt)

    def foreign_cas():
        task = env.task()
        env.runtime.application.update_task("U1", "D1", "BIRTHDAY", task.revision,
            task.run_id, task.status, task.checkpoint_id, {**task.snapshot, "foreign_revision": True})

    def drift(transition, result, **kwargs):
        if boundary == "before_reserve":
            foreign_cas()
        publication = original_publish(transition, result, **kwargs)
        if boundary == "after_publish":
            foreign_cas()
        return publication

    monkeypatch.setattr(BirthdayTransition, "publish", drift)
    code = "PUBLISH_CONFLICT" if boundary == "before_reserve" else "BUDGET_INPUT_STALE"
    with pytest.raises(ValueError, match=code):
        env.runtime.harness.resume_budget_input(env.who, input_request_id=request_id,
            interaction_id=candidate.interaction.interaction_id,
            selected_option_id=option_id(candidate, "采用个人预算"))
    assert env.task().snapshot["foreign_revision"] is True
    assert env.runtime.harness.budget_input_record(env.who, request_id)["phase"] == "accepted"
    assert adopt.call_count == 1
    assert env.runtime.harness.budget_input_origin(env.who) is None


@pytest.mark.parametrize("boundary", ["seal", "publish"])
def test_owned_g3_fault_recovers_original_budget_winner_without_dispatch(
        harness_env, monkeypatch, boundary):
    env = harness_env
    candidate = budget_candidate(env)
    request_id = uuid4()
    interaction = candidate.interaction.interaction_id
    option = option_id(candidate, "采用个人预算")
    adopt = Mock(wraps=env.runtime.application.adopt_budget)
    monkeypatch.setattr(env.runtime.application, "adopt_budget", adopt)
    target = "_seal_content" if boundary == "seal" else "_publish_successor"
    with monkeypatch.context() as fault:
        fault.setattr(env.runtime.harness.birthday_handoff, target,
                      Mock(side_effect=OSError("owned G3 fault")))
        with pytest.raises(OSError, match="owned G3 fault"):
            env.runtime.harness.resume_budget_input(env.who, input_request_id=request_id,
                interaction_id=interaction, selected_option_id=option)
    assert env.task().status is TaskStatus.NEEDS_ATTENTION
    completion = env.runtime.harness.resume_budget_input(env.who,
        input_request_id=request_id, interaction_id=interaction, selected_option_id=option)
    assert completion.result.status is TaskStatus.WAITING_INPUT
    assert env.runtime.harness.resume_budget_input(env.who,
        input_request_id=request_id, interaction_id=interaction, selected_option_id=option) == completion
    assert adopt.call_count == 1
    assert len(env.runtime.application.list_adopted_budgets("U1", "D1")) == 1
    assert env.runtime.harness.budget_input_origin(env.who) is None


def test_adopted_fact_without_a_persisted_g3_winner_does_not_reactivate_input(
        harness_env, monkeypatch):
    env = harness_env
    candidate = budget_candidate(env)
    request_id = uuid4()
    interaction = candidate.interaction.interaction_id
    option = option_id(candidate, "采用个人预算")
    adopt = Mock(wraps=env.runtime.application.adopt_budget)
    monkeypatch.setattr(env.runtime.application, "adopt_budget", adopt)
    with monkeypatch.context() as fault:
        fault.setattr(env.runtime.harness.birthday_handoff, "publish_transition",
                      Mock(side_effect=OSError("before G3 reservation")))
        with pytest.raises(OSError, match="before G3 reservation"):
            env.runtime.harness.resume_budget_input(env.who, input_request_id=request_id,
                interaction_id=interaction, selected_option_id=option)
    with pytest.raises(ValueError, match="BUDGET_INPUT_STALE"):
        env.runtime.harness.resume_budget_input(env.who, input_request_id=request_id,
            interaction_id=interaction, selected_option_id=option)
    assert adopt.call_count == 1
    assert len(env.runtime.application.list_adopted_budgets("U1", "D1")) == 1
    assert env.runtime.harness.budget_input_record(env.who, request_id)["phase"] == "invalidated"


def test_old_g3_association_can_only_recover_its_sealed_budget_attempt(harness_env, monkeypatch):
    env = harness_env
    candidate = budget_candidate(env)
    request_id = uuid4()
    interaction = candidate.interaction.interaction_id
    option = option_id(candidate, "采用个人预算")
    resume = env.runtime.harness._resume
    update = env.runtime.application.update_task
    adopt = Mock(wraps=env.runtime.application.adopt_budget)
    monkeypatch.setattr(env.runtime.application, "adopt_budget", adopt)

    def old_association(subject, response, **_kwargs):
        # Previous budget dispatch omitted the explicit G3 request association.
        return resume(subject, response)

    def lost_completion(*args, **kwargs):
        record = args[-1].get("budget_input_origins", {}).get(str(request_id), {})
        if record.get("phase") == "completed":
            raise OSError("old completion missing")
        return update(*args, **kwargs)

    with monkeypatch.context() as fault:
        fault.setattr(env.runtime.harness, "_resume", old_association)
        fault.setattr(env.runtime.application, "update_task", lost_completion)
        with pytest.raises(OSError, match="old completion missing"):
            env.runtime.harness.resume_budget_input(env.who, input_request_id=request_id,
                interaction_id=interaction, selected_option_id=option)
    original = env.task().snapshot["result"]
    recovered = env.runtime.harness.resume_budget_input(env.who, input_request_id=request_id,
        interaction_id=interaction, selected_option_id=option)
    assert recovered.result.model_dump(mode="json") == original
    assert recovered.result.status is TaskStatus.WAITING_INPUT
    assert adopt.call_count == 1
    assert env.runtime.harness.budget_input_origin(env.who) is None


@pytest.mark.parametrize("choice,status", [
    ("修改个人限额", TaskStatus.WAITING_INPUT),
    ("不采用", TaskStatus.CANCELLED),
])
def test_other_dedicated_budget_choices_publish_without_adopting(harness_env, choice, status):
    env = harness_env
    candidate = budget_candidate(env)
    request_id = uuid4()
    option = option_id(candidate, choice)
    completed = env.runtime.harness.resume_budget_input(env.who,
        input_request_id=request_id, interaction_id=candidate.interaction.interaction_id,
        selected_option_id=option)
    assert completed.result.status is status
    assert env.runtime.harness.resume_budget_input(env.who,
        input_request_id=request_id, interaction_id=candidate.interaction.interaction_id,
        selected_option_id=option) == completed
    assert env.runtime.application.list_adopted_budgets("U1", "D1") == []
    assert env.runtime.harness.budget_input_origin(env.who) is None
