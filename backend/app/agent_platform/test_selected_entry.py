"""A card action chooses a capability; it never supplies execution approval."""
from unittest.mock import patch
from uuid import uuid4

import pytest

from .test_subscription_runtime import composition, confirmation_for, trusted, LIST_CAPABILITY, CANCEL_CAPABILITY


def test_selected_cancel_never_calls_model_and_still_requires_confirmation(tmp_path):
    runtime, bank, planner = composition(tmp_path)
    planner.capability = LIST_CAPABILITY
    inventory = runtime.harness.start(trusted("list"), uuid4(), "查看我的订阅")
    item = next(row for row in inventory.data.list_result.items if row.can_cancel_in_bank)
    request_id = uuid4()
    context = trusted("cancel")
    with patch.object(planner, "select", side_effect=AssertionError("card must not replan")):
        result = runtime.harness.start_selected(context, request_id, "取消 " + item.mandate_id, CANCEL_CAPABILITY)
        assert result.status == "waiting_approval" and result.interaction.kind == "confirmation"
        record = confirmation_for(runtime, context, result)
        assert item.service_name in " ".join(field.value_text for field in record.display_fields)
        replay = runtime.harness.start_selected(context, request_id, "取消 " + item.mandate_id, CANCEL_CAPABILITY)
        assert replay.interaction == result.interaction
        events = runtime.audit._events("D1", "cancel")
        assert not any(event.event_type.startswith("model.") for event in events)
    runtime.close()


def test_selected_entry_rejects_transfer_or_changed_capability(tmp_path):
    runtime, bank, planner = composition(tmp_path)
    with pytest.raises(ValueError, match="INVALID_ARGUMENT"):
        runtime.harness.start_selected(trusted(), uuid4(), "给妈妈转500元", "transfer.start_transfer")
    request_id = uuid4()
    runtime.harness.start_selected(trusted(), request_id, "取消订阅", CANCEL_CAPABILITY)
    with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
        runtime.harness.start_selected(trusted(), request_id, "取消订阅", "bills.summarize")
    runtime.close()


def test_interrupted_selection_recovers_without_model(tmp_path):
    runtime, bank, planner = composition(tmp_path)
    request_id = uuid4()
    with patch.object(runtime.application, "update_task", side_effect=OSError("receipt interrupted")):
        with pytest.raises(OSError):
            runtime.harness.start_selected(trusted(), request_id, "取消订阅", CANCEL_CAPABILITY)
    with patch.object(planner, "select", side_effect=AssertionError("selection must remain saved")):
        result = runtime.harness.start_selected(trusted(), request_id, "取消订阅", CANCEL_CAPABILITY)
        assert result.status == "waiting_input"
    runtime.close()
