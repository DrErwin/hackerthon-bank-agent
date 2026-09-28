"""HTTP and SSE data exchanged by the first transfer journey."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import Field, SecretStr, model_validator

from .common import ContractModel, ID, PositiveInt, RequestId, SubmissionId, Timestamp
from .security import VerificationView
from .tasks import InteractionRequest, ModuleError, TaskView, TransferTaskView


T = TypeVar("T")


class ApiSuccess(ContractModel, Generic[T]):
    data: T


class ApiError(ContractModel):
    error: ModuleError


class SessionView(ContractModel):
    session_id: ID
    user_display: str
    role: Literal["user", "admin"]
    demo_round_id: ID
    created_at: Timestamp
    expires_at: Timestamp


class ThreadView(ContractModel):
    thread_id: ID
    title: str
    created_at: Timestamp
    updated_at: Timestamp
    demo_round_id: ID


class MessageAccepted(ContractModel):
    message_id: ID
    thread_id: ID
    accepted_at: Timestamp
    task_id: ID | None


class MessageView(ContractModel):
    message_id: ID
    thread_id: ID
    role: Literal["user", "assistant"]
    text: str
    created_at: Timestamp
    task_ids: list[ID]
    report_ids: list[ID]


class Page(ContractModel, Generic[T]):
    items: list[T]
    next_cursor: str | None


class RequestIdOnly(ContractModel):
    request_id: RequestId


class SendMessageRequest(RequestIdOnly):
    text: str


class DemoCodeView(ContractModel):
    challenge_id: ID
    code: str = Field(repr=False)
    expires_at: Timestamp


class ProvideInputRequest(ContractModel):
    request_id: RequestId
    interaction_id: ID
    text: str | None = None
    selected_option_id: ID | None = None

    @model_validator(mode="after")
    def require_answer(self) -> "ProvideInputRequest":
        if self.text is None and self.selected_option_id is None:
            raise ValueError("text or selected_option_id is required")
        return self


class ConfirmationAnswerRequest(ContractModel):
    request_id: RequestId
    confirmation_version: PositiveInt
    choice: Literal["approve", "cancel"]



class VerificationCodeRequest(ContractModel):
    request_id: RequestId
    submission_id: SubmissionId
    code: SecretStr


class VerificationResponse(ContractModel, Generic[T]):
    kind: Literal["verified", "rejected", "error"]
    verification: VerificationView
    task: TaskView[T]
    error: ModuleError | None


class MessageDelta(ContractModel):
    message_id: ID
    text_delta: str


class InteractionRequired(ContractModel):
    task_id: ID
    interaction: InteractionRequest


class ReportReady(ContractModel):
    task_id: ID
    report_id: ID


class SessionExpired(ContractModel):
    session_id: ID
    reason: str


EventPayload = (
    MessageDelta | MessageView | TaskView[TransferTaskView] | InteractionRequired
    | ReportReady | SessionExpired | ModuleError
)


class StreamEvent(ContractModel):
    event_id: ID
    thread_id: ID
    session_id: ID
    task_id: ID | None
    run_id: ID | None
    module: ID
    event_type: Literal[
        "message_delta", "message_completed", "task_updated", "interaction_required",
        "report_ready", "session_expired", "stream_error",
    ]
    occurred_at: Timestamp
    payload: EventPayload

    @model_validator(mode="after")
    def payload_matches_event(self) -> "StreamEvent":
        expected = {
            "message_delta": MessageDelta,
            "message_completed": MessageView,
            "task_updated": TaskView,
            "interaction_required": InteractionRequired,
            "report_ready": ReportReady,
            "session_expired": SessionExpired,
            "stream_error": ModuleError,
        }[self.event_type]
        if not isinstance(self.payload, expected):
            raise ValueError("payload does not match event_type")
        return self
