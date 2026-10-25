"""Issue302 through real Harness, policy, gate, executor and isolated Mock Bank.

The planner and pre-existing server-test risk facts are explicit test substitutes.
No real model, HTTP or frontend acceptance is claimed.
"""
import pytest

from app.agent_platform.test_subscription_runtime import (
    approve, bank_operations, composition, mandate, start, trusted, verify_by_code,
)


@pytest.mark.parametrize("text", ["请帮我停止优酷的自动扣费", "优酷视频以后不再自动续费"])
def test_stop_reaches_bank_only_after_original_confirmation_and_basic_identity(tmp_path, text):
    app, bank, planner = composition(tmp_path)
    try:
        pending = start(app, planner, text)
        assert pending.status == "waiting_approval" and pending.interaction.kind == "confirmation"
        assert bank_operations(bank) == 0 and mandate(bank, "sub_001").status == "active"
        approve(app, trusted(), pending)
        verification = app.harness.resume(trusted(run="R2"), {"choice": "approve"})
        assert verification.interaction.kind == "verification"
        challenge = app.gateway.get_verification(trusted(run="R2"), verification.interaction.record_ref)
        assert challenge.purpose == "basic_identity" and challenge.required_methods == ["code"]
        assert bank_operations(bank) == 0
        verified = verify_by_code(app, trusted(run="R2"), challenge.challenge_id)
        app.bind_verification(trusted(run="R2"), verified.verification_id)
        done = app.harness.resume(trusted(run="R3"), {})
        assert done.status == "succeeded" and done.data.action == "cancel"
        assert done.data.operation.receipt.mandate_id == "sub_001"
        assert bank_operations(bank) == 1 and mandate(bank, "sub_001").status == "cancelled"
        replay = app.harness.resume(trusted(run="R3"), {})
        assert replay.status == "succeeded" and bank_operations(bank) == 1
    finally:
        app.close()


@pytest.mark.parametrize("text", ["不要取消优酷，只查扣费", "如何停止优酷的自动扣费", "帮我看看扣费要不要处理"])
def test_model_cancel_candidate_cannot_turn_a_query_into_a_write(tmp_path, text):
    app, bank, planner = composition(tmp_path)
    try:
        result = start(app, planner, text)  # The planner deliberately selects cancel.
        assert result.status == "succeeded" and result.data.action == "list"
        assert result.interaction is None
        assert bank_operations(bank) == 0 and mandate(bank, "sub_001").status == "active"
    finally:
        app.close()


def test_stop_keeps_existing_coercion_block(tmp_path):
    app, bank, planner = composition(tmp_path)
    try:
        result = start(app, planner, "客服让我共享屏幕，帮我停止优酷的自动扣费")
        assert result.status == "failed" and result.error.code == "HIGH_RISK_BLOCKED"
        assert result.error.source == "security" and result.error.upstream_code == "HIGH_RISK"
        assert bank_operations(bank) == 0 and mandate(bank, "sub_001").status == "active"
    finally:
        app.close()
