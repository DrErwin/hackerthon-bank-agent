"""Issue302: behavior through the registered public entry, isolated ports only."""
import pytest

from app.agent_platform.registry import CapabilityRegistry
from app.modules.subscription.entry import register_subscription
from app.modules.subscription.test_subscription import (
    FakeBank, FakeGate, MemorySaver, NOW, Ports, context, start_request,
)


def registered_entry():
    bank, gate = FakeBank(), FakeGate(verify_required=True)
    registry = CapabilityRegistry()
    register_subscription(registry, lambda *_: Ports(bank, gate), lambda: NOW)
    return registry.get("subscription.cancel_subscription").factory(context(), MemorySaver(), None), bank, gate


def test_explicit_stop_reaches_confirmation_without_executing():
    task, bank, gate = registered_entry()
    result = task.start(context(), start_request("请帮我停止优酷的自动扣费"))
    assert result.status == "waiting_approval"
    assert result.interaction.kind == "confirmation"
    assert gate.plans[-1].mandate_id == "sub_001"
    assert bank.cancel_calls == 0


def test_negated_cancellation_stays_read_only_even_under_cancel_candidate():
    task, bank, gate = registered_entry()
    result = task.start(context(), start_request("不要取消优酷，只查询扣费"))
    assert result.status == "succeeded"
    assert result.data.action == "list"
    assert result.interaction is None and gate.plans == []
    assert bank.cancel_calls == 0


@pytest.mark.parametrize("text,mandate_id", [
    ("请停止优酷视频的自动扣费", "sub_001"),
    ("帮我终止云端网盘的代扣", "sub_002"),
    ("优酷视频以后不再续费", "sub_001"),
    ("云端网盘不要再自动续费", "sub_002"),
    ("优酷视频不想继续续订", "sub_001"),
    ("云端网盘不续费了", "sub_002"),
    ("别再扣优酷视频的钱了", "sub_001"),
    ("请把不需要的优酷自动扣费停止", "sub_001"),
    ("先查一下账单，帮我停止优酷的自动扣费", "sub_001"),
    ("先查一下优酷的退订记录，然后帮我停止优酷的自动扣费", "sub_001"),
    ("先查一下退订记录，帮我停止优酷的自动扣费", "sub_001"),
    ("先了解一下取消的后果，然后帮我停止优酷的自动扣费", "sub_001"),
    ("不要再扣费了请帮我取消优酷自动续费", "sub_001"),
    ("优酷以后不要再自动扣费了请取消它", "sub_001"),
    ("请停止优酷自动扣费并保留退订记录", "sub_001"),
])
def test_stop_and_future_renewal_requests_match_the_actual_mandate(text, mandate_id):
    task, bank, gate = registered_entry()
    result = task.start(context(), start_request(text))
    assert result.status == "waiting_approval" and result.interaction.kind == "confirmation"
    assert gate.plans[-1].mandate_id == mandate_id
    assert bank.cancel_calls == 0


@pytest.mark.parametrize("text", [
    "别帮我停止优酷自动扣费", "我不想退订优酷", "先不关闭云端网盘，看看下期扣款",
    "我不是要取消，只查优酷扣费", "怎么取消优酷的自动扣费", "如何停止优酷的自动扣费",
    "优酷的自动扣费取消了吗", "查一下优酷是否已经取消自动续费",
    "我只想了解不再续费的影响", "帮我看看优酷的退订记录", "我能取消优酷吗",
    "帮我查查有哪些自动扣费", "帮我看看这些扣费要不要处理", "别再问我这些扣费了",
    "我不想让你停止优酷的自动扣费", "不要把优酷的自动扣费停止",
    "不要把优酷的自动扣费取消了", "别把优酷的自动续费关掉",
    "帮我查一下优酷停止自动扣费的日期", "请问优酷自动扣费能停止吗",
    "优酷已经停止自动扣费了，帮我查一下", "优酷已经停止自动扣费了",
    "优酷的自动扣费可以停止吗", "看看云端网盘的解约结果",
    "我不需要把优酷的代扣停止", "不用把云端网盘的续费关闭", "我只是看优酷的取消信息",
])
def test_denial_query_and_unclear_request_never_enter_confirmation(text):
    task, bank, gate = registered_entry()
    result = task.start(context(), start_request(text))
    assert result.status == "succeeded" and result.data.action == "list"
    assert result.interaction is None and gate.plans == []
    assert bank.cancel_calls == 0


@pytest.mark.parametrize("text", ["停止自动扣费", "以后不再续费", "全部停止自动扣费", "把自动扣费都关"])
def test_stop_without_one_target_requires_selection(text):
    task, bank, gate = registered_entry()
    result = task.start(context(), start_request(text))
    assert result.status == "waiting_input"
    assert {o.id for o in result.interaction.options} == {"sub_001", "sub_002"}
    assert gate.plans == [] and bank.cancel_calls == 0
    selected = task.resume(context(), {"selected_option_id": "sub_002"})
    assert selected.status == "waiting_approval" and selected.interaction.kind == "confirmation"
    assert gate.plans[-1].mandate_id == "sub_002" and bank.cancel_calls == 0


def test_stop_still_requires_confirmation_then_verification_before_execution():
    task, bank, gate = registered_entry()
    first = task.start(context(), start_request("优酷视频不再自动续费"))
    assert first.interaction.kind == "confirmation" and bank.cancel_calls == 0
    gate.confirmed = True  # The fake gate models the dedicated answer, not chat authorization.
    verification = task.resume(context(), {"choice": "approve"})
    assert verification.interaction.kind == "verification" and bank.cancel_calls == 0
    gate.verified = True
    done = task.resume(context(), {"choice": "resume"})
    assert done.status == "succeeded" and done.data.action == "cancel"
    assert done.data.operation.receipt.mandate_id == "sub_001" and bank.cancel_calls == 1
    assert task.resume(context(), {"choice": "resume"}).status == "succeeded"
    assert bank.cancel_calls == 1
