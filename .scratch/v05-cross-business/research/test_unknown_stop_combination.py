"""PR #288 + #289 integration probe; explicitly run on the combined checkout.

Not collected by the ordinary backend suite: #289's execution-claim recovery
is required for the verified release assertions. No business code is patched.
"""

from uuid import UUID

import pytest

from app.agent_platform.test_birthday_runtime_wiring import (
    composition, trusted, run_to_freeze_question, approve_confirmation,
    answer_verification, option_id, _single_freeze,
)
from app.contracts.common import OperationStatus, TaskStatus
from app.modules.cross.entry import CrossEntry


@pytest.mark.parametrize("action,paid_fen,released_fen,order_count,configured", [
    ("bank.freeze_funds", 0, 50000, 0, True),
    ("bank.freeze_funds", 0, 50000, 0, False),
    ("bank.create_order", 0, 50000, 1, False),
    ("bank.capture_frozen", 19900, 30100, 1, False),
])
def test_stop_survives_unknown_original_lookup_on_real_ports(
    tmp_path, action, paid_fen, released_fen, order_count, configured,
):
    runtime, entry = composition(tmp_path, response_loss=True) if configured else composition(tmp_path)
    who = trusted(runtime)
    armed = False
    try:
        current = run_to_freeze_question(entry)
        for _ in range(24):
            interaction = current.interaction
            assert interaction is not None, current.message
            if interaction.kind == "input":
                assert armed and "待核实" in current.message
                break
            if interaction.kind == "confirmation":
                record = runtime.confirmations.get(
                    runtime._context(who, None, None), interaction.record_ref)
                if not armed and record.action_name == action:
                    # Real bank commits, then exceeds the gateway deadline.
                    # This is the same one-shot bank fault PR #289 wires up.
                    if not configured:
                        runtime.gateway._bank.birthday.arm_response_loss(who.user_id)
                    armed = True
                approve_confirmation(runtime, who, interaction.record_ref)
                current = entry.resume(who, {"choice": "approve"})
            else:
                assert interaction.kind == "verification"
                answer_verification(runtime, who, "R1", interaction.record_ref)
                current = entry.resume(who, {"choice": "resume"})
        else:
            pytest.fail("Did not reach the real lost-response wait")

        actions = runtime.application.get_task("U1", "D1", "BIRTHDAY").snapshot["birthday_actions"]
        operation_id = next(row["operation_id"] for row in actions.values()
                            if row.get("parameters", {}).get("__action__") == action)
        before = _single_freeze(runtime)
        assert before["original_amount_fen"] == 50000
        assert before["captured_total_fen"] == paid_fen
        assert before["released_total_fen"] == 0

        entry.resume(who, {"cancel": True})
        # Reconstruct the business entry from its durable checkpoint. The stop
        # must survive a refresh; never reuse the pre-cancellation menu.
        restored = CrossEntry(runtime.harness, entry.saver, None, entry.clock,
                              runtime.birthday.ports_factory)
        waiting = restored.resume(who, {})
        assert waiting.interaction.kind == "input"
        stopped = restored.resume(who, {
            "selected_option_id": option_id(waiting, "核实原操作"),
        })
        assert stopped.status is (TaskStatus.PARTIALLY_SUCCEEDED if paid_fen else TaskStatus.CANCELLED)
        assert stopped.interaction is None  # in particular, no new order card
        assert stopped.data.stop_reason == "user_cancelled"
        after = _single_freeze(runtime)
        assert after["freeze_id"] == before["freeze_id"]
        assert after["captured_total_fen"] == paid_fen
        assert after["released_total_fen"] == released_fen
        assert runtime.gateway.get_freeze(who, after["freeze_id"]).data.remaining_fen == 0
        lookup = runtime.gateway.get_operation(who, UUID(operation_id))
        assert lookup.lookup == "found"
        assert lookup.operation.operation_status is OperationStatus.SUCCEEDED
        after_actions = runtime.application.get_task("U1", "D1", "BIRTHDAY").snapshot["birthday_actions"]
        assert after_actions == actions  # no new freeze, order or capture action
        from app.storage.database import connect
        with connect(runtime.gateway._bank.store.path) as connection:
            assert connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == order_count
        replay = restored.resume(who, {})
        assert replay.status is stopped.status and replay.interaction is None
        assert _single_freeze(runtime) == after
    finally:
        runtime.gateway.close()
