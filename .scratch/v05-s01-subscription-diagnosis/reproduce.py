"""Read-only diagnostic probe: actual entry + existing in-memory test doubles only."""
import json
from uuid import uuid4
from app.agent_platform.registry import CapabilityRegistry
from app.contracts.platform import StartTransferInput
from app.contracts.subscription import SubscriptionCancelInput, SubscriptionListInput
from app.modules.subscription.entry import register_subscription, wants_cancel
from app.modules.subscription.test_subscription import FakeBank, FakeGate, Ports, MemorySaver, NOW, context

LIVE = "最近钱怎么花得快，帮我处理不用的扣费"

def run(label, capability, request):
    bank, gate, saver = FakeBank(), FakeGate(verify_required=True), MemorySaver()
    registry = CapabilityRegistry()
    register_subscription(registry, lambda *_: Ports(bank, gate), lambda: NOW)
    task = registry.get(capability).factory(context(), saver, None)
    result = task.start(context(), request)
    state = saver.get_tuple({"configurable": {"thread_id": context().task_id}}).checkpoint["channel_values"]["subscription_state"]
    return {"label": label, "capability": capability, "request_type": type(request).__name__,
        "wants_cancel": wants_cancel(request.intent_text), "mode": state["mode"],
        "status": result.status.value, "action": result.data.action if result.data else None,
        "interaction": result.interaction.kind if result.interaction else None,
        "options": len(result.interaction.options) if result.interaction else 0,
        "fake_gate_checks": len(gate.plans), "fake_cancel_calls": bank.cancel_calls}

rows = [
 run("live_cancel", "subscription.cancel_subscription", StartTransferInput(request_id=uuid4(), intent_text=LIVE)),
 run("live_list", "subscription.list_subscriptions", StartTransferInput(request_id=uuid4(), intent_text=LIVE)),
 run("explicit_single", "subscription.cancel_subscription", StartTransferInput(request_id=uuid4(), intent_text="把优酷视频的自动扣费退了")),
 run("missing_target", "subscription.cancel_subscription", StartTransferInput(request_id=uuid4(), intent_text="帮我退订一项自动扣费")),
 run("explicit_stop_single", "subscription.cancel_subscription", StartTransferInput(request_id=uuid4(), intent_text="请帮我停止优酷的自动扣费")),
 run("typed_stop_single", "subscription.cancel_subscription", SubscriptionCancelInput(request_id=uuid4(), intent_text="请帮我停止优酷的自动扣费")),
 run("read_only", "subscription.list_subscriptions", StartTransferInput(request_id=uuid4(), intent_text="帮我查查有哪些自动扣费")),
 run("typed_cancel_unspecified", "subscription.cancel_subscription", SubscriptionCancelInput(request_id=uuid4(), intent_text=LIVE)),
 run("typed_cancel_selected", "subscription.cancel_subscription", SubscriptionCancelInput(request_id=uuid4(), intent_text=LIVE, subscription_id="sub_001")),
 run("typed_list_authority", "subscription.list_subscriptions", SubscriptionListInput(request_id=uuid4(), intent_text="退订")),
]
assert rows[0]["mode"] == "list" and rows[0]["status"] == "succeeded" and rows[0]["action"] == "list"
assert rows[0]["interaction"] is None and rows[0]["fake_gate_checks"] == 0
assert all(row["fake_cancel_calls"] == 0 for row in rows)
print(json.dumps({"probe": "offline-entry-only", "rows": rows}, ensure_ascii=False, indent=2))
