"""Export public API Pydantic models as a JSON Schema for TypeScript generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.api.app import CardActionRequest, FaceAnswer  # noqa: E402
from app.contracts.api import (  # noqa: E402
    ConfirmationAnswerRequest,
    DemoCodeView,
    DetailsResponse,
    MessageAccepted,
    MessageView,
    Page,
    PayeeDetailsFields,
    PayeeSearchFields,
    ProvideInputRequest,
    RequestIdOnly,
    SendMessageRequest,
    SessionView,
    StreamEvent,
    SubmitDetailsRequest,
    TaskRecordsView,
    ThreadView,
    VerificationCodeRequest,
    VerificationResponse,
)
from app.contracts.audit import AuditEventDetail, AuditEventSummary  # noqa: E402
from app.contracts.bank import AccountList, PayeeList, PayeeCandidate  # noqa: E402
from app.contracts.subscription import SubscriptionTaskView  # noqa: E402
from app.contracts.bills import (  # noqa: E402
    AnomalyResult,
    BillDetails,
    BillReport,
    SpendingSummary,
    TransactionCandidates,
)
from app.contracts.security import ConfirmationView, VerificationView  # noqa: E402
from app.contracts.cross import CrossTaskView  # noqa: E402
from app.contracts.tasks import TaskView, TransferTaskView  # noqa: E402

PUBLIC_MODELS = {
    "CardActionRequest": CardActionRequest,
    "AccountList": AccountList,
    "PayeeList": PayeeList,
    "SubscriptionTaskView": SubscriptionTaskView,
    "CrossTaskView": CrossTaskView,
    "SessionView": SessionView,
    "ThreadView": ThreadView,
    "MessageAccepted": MessageAccepted,
    "MessageView": MessageView,
    "ThreadPage": Page[ThreadView],
    "MessagePage": Page[MessageView],
    "TaskPage": Page[TaskView[TransferTaskView]],
    "TaskView": TaskView[TransferTaskView],
    "TaskRecordsView": TaskRecordsView,
    "ConfirmationView": ConfirmationView,
    "VerificationView": VerificationView,
    "VerificationResponse": VerificationResponse[TransferTaskView],
    "DemoCodeView": DemoCodeView,
    "PayeeCandidate": PayeeCandidate,
    "DetailsResponse": DetailsResponse[TransferTaskView],
    "StreamEvent": StreamEvent,
    "AuditEventSummary": AuditEventSummary,
    "AuditEventDetail": AuditEventDetail,
    "AuditEventPage": Page[AuditEventSummary],
    "RequestIdOnly": RequestIdOnly,
    "SendMessageRequest": SendMessageRequest,
    "ProvideInputRequest": ProvideInputRequest,
    "SubmitDetailsRequest": SubmitDetailsRequest,
    "PayeeDetailsFields": PayeeDetailsFields,
    "PayeeSearchFields": PayeeSearchFields,
    "ConfirmationAnswerRequest": ConfirmationAnswerRequest,
    "VerificationCodeRequest": VerificationCodeRequest,
    "FaceAnswer": FaceAnswer,
    "SpendingSummary": SpendingSummary,
    "BillDetails": BillDetails,
    "AnomalyResult": AnomalyResult,
    "TransactionCandidates": TransactionCandidates,
    "BillReport": BillReport,
}


def main() -> None:
    definitions: dict[str, object] = {}
    properties: dict[str, object] = {}
    for name, model in PUBLIC_MODELS.items():
        model_schema = model.model_json_schema(ref_template="#/definitions/{model}")
        nested = model_schema.pop("$defs", {})
        definitions.update(nested)
        model_schema["title"] = name
        definitions[name] = model_schema
        properties[name] = {"$ref": f"#/definitions/{name}"}

    definitions["PublicContract"] = {
        "type": "object",
        "properties": properties,
        "required": list(properties),
    }
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$ref": "#/definitions/PublicContract",
        "definitions": definitions,
    }
    output = Path(__file__).resolve().parents[1] / ".contract-schema.json"
    output.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
