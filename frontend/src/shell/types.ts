import type {
  AccountList,
  PayeeList,
  DetailsResponse,
  CardActionRequest,
  ConfirmationView,
  DemoCodeView,
  DisplayField,
  InteractionRequest,
  MessageAccepted,
  MessageView,
  ModuleError,
  SessionView,
  StreamEvent,
  TaskView,
  TransferTaskView,
  TaskRecordsView,
  ThreadView,
  VerificationResponse,
  VerificationView,
} from "../contracts";

// The generated TaskView is specialised to TransferTaskView; the shell only reads the
// module-independent envelope and leaves `data` to the business slot.
export type ShellTask<D = unknown> = Omit<TaskView, "data"> & { data: D | null };
export type CardSelection = Omit<CardActionRequest, "request_id" | "source_revision">;

export interface TaskEnvelope<D = unknown> {
  /** Client display position only. Never sent as bank or authorization data. */
  timelineAt?: string;
  task: ShellTask<D>;
  // From StreamEvent.module; TaskView itself carries no module name.
  module: string | null;
}

export type ShellVerificationResponse = Omit<VerificationResponse, "task"> & { task: ShellTask };

export type DraftChanges = Partial<Pick<TransferTaskView, "amount_fen" | "payer_account_id">> & { payee_hint?: string; payee_id?: string };

export type DataOrigin = "stub" | "contract-demo" | "real-api";

export type ShellEvent = Omit<StreamEvent, "payload"> & { payload: unknown };

export type HistoryEntry =
  | { kind: "confirmation"; id: string; snapshot?: ConfirmationView }
  | { kind: "verification"; id: string }
  | { kind: "input"; id: string; interaction: InteractionRequest; selectedLabel: string | null };

export interface ShellDataSource {
  readonly origin: DataOrigin;
  enterSession(body: { request_id: string }): Promise<SessionView>;
  getSession(): Promise<SessionView>;
  ensureThread(): Promise<ThreadView>;
  listMessages(threadId: string): Promise<MessageView[]>;
  listTasks(threadId: string): Promise<TaskEnvelope[]>;
  getTask(taskId: string): Promise<TaskEnvelope>;
  // Cross-linkage parents expose durable child tasks; the page answers on the
  // child that owns the current interaction, never on the parent.
  listChildren?(taskId: string): Promise<TaskEnvelope[]>;
  listTaskRecords(taskId: string): Promise<TaskRecordsView>;
  sendMessage(threadId: string, body: { request_id: string; text: string }): Promise<MessageAccepted>;
  provideInput(
    taskId: string,
    body: { request_id: string; interaction_id: string; selected_option_id?: string; text?: string },
  ): Promise<ShellTask>;
  reviseDraft(taskId: string, body: DraftChanges & { request_id: string; task_revision: number }): Promise<ShellTask>;
  readTransferChoices?(taskId: string, kind: "accounts" | "payees"): Promise<AccountList | PayeeList>;
  submitPayeeDetails?(taskId: string, body: { request_id: string; interaction_id: string; kind: "payee"; fields: { account_name: string; account_number: string } }): Promise<DetailsResponse>;
  resumeTask(taskId: string, body: { request_id: string }): Promise<ShellTask>;
  cancelTask(taskId: string, body: { request_id: string }): Promise<ShellTask>;
  queryResult(taskId: string, body: { request_id: string }): Promise<ShellTask>;
  cardAction?(taskId: string, body: CardActionRequest): Promise<ShellTask>;
  getConfirmation(confirmationId: string): Promise<ConfirmationView>;
  answerConfirmation(
    confirmationId: string,
    body: { request_id: string; confirmation_version: number; choice: "approve" | "cancel" },
  ): Promise<ShellTask>;
  getVerification(challengeId: string): Promise<VerificationView>;
  submitCode(
    challengeId: string,
    body: { request_id: string; submission_id: string; code: string },
  ): Promise<ShellVerificationResponse>;
  resendCode(challengeId: string, body: { request_id: string }): Promise<VerificationView>;
  getDemoCode(challengeId: string): Promise<DemoCodeView>;
  startFace(challengeId: string, body: { request_id: string }): Promise<VerificationView>;
  subscribe(threadId: string, onEvent: (event: ShellEvent) => void, onConnection: (connected: boolean) => void): () => void;
}

export interface AdminDemoSource {
  readonly origin: DataOrigin;
  enterAdmin(body: { request_id: string }): Promise<SessionView>;
  getAdminSession(): Promise<SessionView>;
  answerFace(
    challengeId: string,
    body: { request_id: string; submission_id: string; demo_round_id: string; result: "passed" | "failed" },
  ): Promise<ShellVerificationResponse>;
  expireUserSession(body: { request_id: string; demo_round_id: string }): Promise<{ session_id: string; expired_at: string }>;
}

export type Tone = "success" | "danger" | "warning" | "pending" | "neutral";

export interface ResultView {
  tone: Tone;
  title: string;
  headline?: string;
  fields: DisplayField[];
  note?: string;
}

export interface ReportView {
  title: string;
  periodLabel: string;
  headline?: { label: string; value: string };
  fields: DisplayField[];
  note?: string;
}

export type { DisplayField, ModuleError };
