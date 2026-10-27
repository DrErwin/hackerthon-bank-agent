"""The already frozen F30-F32 wire contract is separate from task states."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from .api import ManagementOperation, ResetPreviewRequest, ResetRequest


@pytest.mark.parametrize("status,resulting_round,error", [
    ("running", None, None),
    ("succeeded", "D2", None),
    ("failed", None, {"code": "DEPENDENCY_UNAVAILABLE", "source": "bank",
                      "field": None, "reason": "重置未完成。", "upstream_code": None}),
])
def test_management_wire_states_keep_the_source_and_actual_result(
    status, resulting_round, error,
):
    wire = {"management_operation_id": "reset-1", "kind": "reset",
            "status": status, "source_round_id": "D1",
            "resulting_round_id": resulting_round, "phase": "bank",
            "error": error}
    assert ManagementOperation.model_validate(wire).model_dump(mode="json") == wire


def test_task_processing_is_not_a_management_operation_state():
    with pytest.raises(ValidationError):
        ManagementOperation(management_operation_id="reset-1", kind="reset",
                            status="processing", source_round_id="D1",
                            resulting_round_id=None, phase="bank", error=None)


def test_reset_body_requires_the_server_confirmation_not_a_client_round():
    request_id = uuid4()
    preview = ResetPreviewRequest(request_id=request_id, demo_round_id="D1")
    assert preview.demo_round_id == "D1"
    with pytest.raises(ValidationError):
        ResetRequest.model_validate(preview.model_dump())
    confirmed = ResetRequest(request_id=request_id, reset_confirmation_id="reset-check-1")
    assert confirmed.reset_confirmation_id == "reset-check-1"
    with pytest.raises(ValidationError):
        ResetRequest(request_id=request_id, reset_confirmation_id="reset-check-1",
                     user_id="another-user")
