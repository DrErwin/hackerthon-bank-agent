import type { PublicContract } from "./api.generated";

// Contract types are generated from backend/app/contracts with npm run generate:contracts.
export type SessionView = PublicContract["SessionView"];
export type ThreadView = PublicContract["ThreadView"];
export type MessageAccepted = PublicContract["MessageAccepted"];
export type MessageView = PublicContract["MessageView"];
// Stream events intentionally carry a module-neutral TaskView whose data is unknown.
// The task list endpoint remains the typed transfer surface used by the current UI.
export type TaskView = PublicContract["TaskPage"]["items"][number];
export type TaskRecordsView = PublicContract["TaskRecordsView"];
export type ConfirmationView = PublicContract["ConfirmationView"];
export type VerificationView = PublicContract["VerificationView"];
export type VerificationResponse = PublicContract["VerificationResponse"];
export type DemoCodeView = PublicContract["DemoCodeView"];
export type PayeeCandidate = PublicContract["PayeeCandidate"];
export type DetailsResponse = PublicContract["DetailsResponse"];
export type StreamEvent = PublicContract["StreamEvent"];
export type AuditEventSummary = PublicContract["AuditEventSummary"];
export type AuditEventDetail = PublicContract["AuditEventDetail"];
export type SpendingSummary = PublicContract["SpendingSummary"];
export type BillDetails = PublicContract["BillDetails"];
export type AnomalyResult = PublicContract["AnomalyResult"];
export type TransactionCandidates = PublicContract["TransactionCandidates"];
export type BillReport = PublicContract["BillReport"];

export type TaskStatus = TaskView["status"];
export type AllowedAction = TaskView["allowed_actions"][number];
export type DisplayField = ConfirmationView["display_fields"][number];
export type InteractionRequest = NonNullable<TaskView["interaction"]>;
export type InteractionOption = InteractionRequest["options"][number];
export type ModuleError = NonNullable<TaskView["error"]>;
export type PayeeDisplay = NonNullable<NonNullable<TaskView["data"]>["payee"]>;
export type TransferTaskView = NonNullable<TaskView["data"]>;
export type VerificationSummary = NonNullable<VerificationView["summary"]>;
export type TransferReceipt = NonNullable<NonNullable<NonNullable<TaskView["data"]>["operation"]>["receipt"]>;
export type OperationResult<T> = Omit<NonNullable<NonNullable<TaskView["data"]>["operation"]>, "receipt"> & { receipt: T | null };

export type Page<T> = Omit<PublicContract["ThreadPage"], "items"> & { items: T[] };
