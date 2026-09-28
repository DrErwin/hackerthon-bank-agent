"""Types shared by the frozen v1 public contract."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import re
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, UUID4


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


ID = Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r"^\S+$")]
Money = Annotated[int, Field(strict=True, ge=0)]
PositiveMoney = Annotated[int, Field(strict=True, gt=0)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
def _iso_timestamp(value: object) -> object:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not re.search(r"T.+(?:Z|[+-]\d{2}:\d{2})$", value):
        raise ValueError("timestamp must be an ISO 8601 string with timezone")
    return value


Timestamp = Annotated[AwareDatetime, BeforeValidator(_iso_timestamp)]
OperationId = UUID4
RequestId = UUID
SubmissionId = UUID


class TaskStatus(StrEnum):
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEEDS_ATTENTION = "needs_attention"


class OperationLevel(StrEnum):
    READ = "read"
    MODIFY = "modify"
    SENSITIVE = "sensitive"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SecurityDecisionCode(StrEnum):
    ALLOW = "allow"
    REQUIRE_INPUT = "require_input"
    REQUIRE_CONFIRMATION = "require_confirmation"
    REQUIRE_VERIFICATION = "require_verification"
    BLOCK = "block"
    PAUSE = "pause"


class OperationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PROCESSING = "processing"


class Phase(StrEnum):
    ADMISSION = "admission"
    EXECUTION = "execution"
    RECOVERY = "recovery"


class DisplayField(ContractModel):
    name: ID
    label: str
    value_text: str
