import type {
  AuditEventDetail,
  AuditEventSummary,
  ConfirmationView,
  MessageAccepted,
  MessageView,
  ModuleError,
  Page,
  PayeeCandidate,
  SessionView,
  StreamEvent,
  TaskView,
  ThreadView,
  VerificationView,
} from "./contracts";

export type ApiMode = "real-api" | "contract-demo";

export const API_MODE: ApiMode =
  import.meta.env.VITE_API_MODE === "contract-demo" ? "contract-demo" : "real-api";

const API_ROOT = "/api/v1";
const DEMO_STORAGE_KEY = "v03-local-demo-contract-state";
const USER_ENTERED_KEY = "v03-local-demo-user-entered";

/** The API failure body (§6.7): a code plus the backend's user-facing reason. */
export type ApiProblem = Pick<ModuleError, "code"> & { reason?: ModuleError["reason"] | null };

export class ApiError extends Error {
  status: number;
  code: string;
  /** The server's own Chinese reason, shown verbatim; null when the body had none. */
  reason: string | null;

  constructor(status: number, code: string, message: string, reason: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.reason = reason;
  }
}

interface DemoState {
  userSession: SessionView | null;
  adminSession: SessionView | null;
  threads: ThreadView[];
  tasks: Record<string, TaskView>;
  confirmations: Record<string, ConfirmationView>;
  verifications: Record<string, VerificationView>;
  audit: Record<string, AuditEventSummary[]>;
  auditDetails: Record<string, AuditEventDetail>;
}

const defaultDemoState = (): DemoState => ({
  userSession: null,
  adminSession: null,
  threads: [],
  tasks: {},
  confirmations: {},
  verifications: {},
  audit: {},
  auditDetails: {},
});

const demoMessages = new Map<string, MessageView[]>();
const demoListeners = new Map<string, Set<(event: StreamEvent) => void>>();

function readDemoState(): DemoState {
  try {
    const raw = localStorage.getItem(DEMO_STORAGE_KEY);
    return raw ? { ...defaultDemoState(), ...JSON.parse(raw) } : defaultDemoState();
  } catch {
    return defaultDemoState();
  }
}

function saveDemoState(state: DemoState): void {
  try {
    localStorage.setItem(DEMO_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // The test-only page still works in a browser that blocks local storage.
  }
}

function id(): string {
  return crypto.randomUUID();
}

function now(): string {
  return new Date().toISOString();
}

function addMinutes(value: string, minutes: number): string {
  return new Date(new Date(value).getTime() + minutes * 60_000).toISOString();
}

function page<T>(items: T[]): Page<T> {
  return { items, next_cursor: null };
}

function unwrap<T>(value: unknown): T {
  return (value as { data: T }).data;
}

function getCurrentDemoSession(state: DemoState): SessionView | null {
  return window.location.pathname === "/admin" ? state.adminSession : state.userSession;
}

function setCurrentDemoSession(state: DemoState, session: SessionView): void {
  if (window.location.pathname === "/admin") state.adminSession = session;
  else state.userSession = session;
}

function requireDemoSession(state: DemoState, role?: "user" | "admin"): SessionView {
  const session = getCurrentDemoSession(state);
  if (!session) throw new ApiError(401, "AUTH_REQUIRED", "演示登录已过期，请重新进入。");
  if (role && session.role !== role) throw new ApiError(403, "ACCESS_DENIED", "当前演示会话没有此权限。");
  return session;
}

function makeThread(session: SessionView): ThreadView {
  const at = now();
  return {
    thread_id: id(),
    title: "测试对话",
    created_at: at,
    updated_at: at,
    demo_round_id: session.demo_round_id,
  };
}

function makeMessage(threadId: string, role: "user" | "assistant", text: string, taskIds: string[] = []): MessageView {
  return {
    message_id: id(),
    thread_id: threadId,
    role,
    text,
    created_at: now(),
    task_ids: taskIds,
    report_ids: [],
  };
}

function emitDemo(threadId: string, type: StreamEvent["event_type"], payload: StreamEvent["payload"], taskId: string | null = null): void {
  const event: StreamEvent = {
    event_id: id(),
    thread_id: threadId,
    session_id: "contract-session",
    task_id: taskId,
    run_id: null,
    module: "contract-demo",
    event_type: type,
    occurred_at: now(),
    payload,
  };
  for (const listener of demoListeners.get(threadId) ?? []) listener(event);
}

function publishTask(state: DemoState, task: TaskView): void {
  state.tasks[task.task_id] = task;
  saveDemoState(state);
  emitDemo(task.thread_id, "task_updated", task, task.task_id);
}

function auditEvent(
  state: DemoState,
  task: TaskView,
  eventType: "task.transition" | "confirmation.changed" | "verification.changed",
  outcome: AuditEventSummary["outcome"],
): void {
  const sequence = (state.audit[task.task_id]?.length ?? 0) + 1;
  const confirmation = Object.values(state.confirmations).find((item) => item.task_id === task.task_id);
  const verification = Object.values(state.verifications).find((item) => item.task_id === task.task_id);
  const payload: AuditEventDetail["payload"] = eventType === "task.transition"
    ? {
        previous_status: null,
        status: task.status,
        plan_revision: null,
        step_id: null,
        reason_code: "CONTRACT_DEMO",
        checkpoint_ref: null,
      }
    : eventType === "confirmation.changed"
      ? {
          confirmation_id: confirmation?.confirmation_id ?? "test-confirmation",
          confirmation_version: confirmation?.confirmation_version ?? 1,
          action_revision: 1,
          decision: confirmation?.decision ?? "pending",
          display_ref: "contract-demo-display",
          operation_id: task.data?.operation_id ?? null,
        }
      : {
          challenge_id: verification?.challenge_id ?? "test-verification",
          method: verification?.face_result === "passed" || verification?.face_result === "failed" ? "mock_face" : "code",
          result: verification?.face_result === "passed" || verification?.face_result === "failed"
            ? verification.face_result
            : verification?.code_result ?? "pending",
          purpose: "action_step_up",
          operation_id: verification?.summary?.operation_id ?? null,
          verification_id: verification?.challenge_id ?? null,
          consecutive_code_failures: verification?.consecutive_code_failures ?? 0,
          expires_at: verification?.face_expires_at ?? verification?.code_expires_at ?? now(),
          reason_code: "CONTRACT_DEMO",
        };
  const event: AuditEventSummary = {
    event_id: id(),
    sequence,
    trace_id: "contract-demo-trace",
    parent_span_id: null,
    span_id: "contract-demo-span-" + sequence,
    thread_id: task.thread_id,
    task_id: task.task_id,
    run_id: task.run_id,
    module: "contract-demo",
    event_type: eventType,
    timestamp: now(),
    outcome,
    evidence_ref: null,
    demo_round_id: task.demo_round_id,
    actor_id: "contract-demo-user",
    target_user_id: "contract-demo-user",
    session_id: "contract-session",
    target_session_id: null,
  };
  state.audit[task.task_id] = [...(state.audit[task.task_id] ?? []), event];
  state.auditDetails[event.event_id] = {
    ...event,
    payload,
    evidence: null,
    evidence_status: "missing",
    missing_reason: "契约测试响应不包含真实运行证据。",
  };
}

function taskSnapshot(task: TaskView, patch: Partial<TaskView>): TaskView {
  return {
    ...task,
    ...patch,
    task_revision: task.task_revision + 1,
    snapshot_at: now(),
  };
}

function getTask(state: DemoState, taskId: string): TaskView {
  const task = state.tasks[taskId];
  if (!task) throw new ApiError(404, "NOT_FOUND", "当前演示任务不存在。");
  return task;
}

function candidateList(): PayeeCandidate[] {
  return [
    {
      payee_id: "test-payee-mom",
      name_masked: "妈妈",
      account_masked: "尾号 1234",
      remark: "常用收款人（虚构）",
      bank_name: "演示银行",
      last_transfer_at: null,
    },
    {
      payee_id: "test-payee-li",
      name_masked: "李女士",
      account_masked: "尾号 5678",
      remark: "测试候选（虚构）",
      bank_name: "演示银行",
      last_transfer_at: null,
    },
  ];
}

function amountFromDemoText(text: string): number {
  const match = text.match(/(\d+(?:\.\d{1,2})?)\s*元?/);
  if (!match) return 50_000;
  const amount = Math.round(Number(match[1]) * 100);
  return Number.isFinite(amount) && amount > 0 ? amount : 50_000;
}

function openConfirmation(state: DemoState, task: TaskView, payee: PayeeCandidate): TaskView {
  const confirmationId = "test-confirmation-" + id();
  const amountFen = task.data?.amount_fen ?? 50_000;
  const fields: ConfirmationView["display_fields"] = [
    { name: "payer", label: "转出账户", value_text: "演示账户 ··8888" },
    { name: "payee", label: "收款人", value_text: payee.name_masked },
    { name: "account", label: "收款账户", value_text: payee.account_masked },
    { name: "bank", label: "开户行", value_text: payee.bank_name },
    { name: "amount", label: "转账金额", value_text: "¥" + (amountFen / 100).toFixed(2) },
    { name: "fee", label: "手续费", value_text: "¥0.00（测试数据）" },
  ];
  state.confirmations[confirmationId] = {
    confirmation_id: confirmationId,
    task_id: task.task_id,
    confirmation_version: 1,
    display_fields: fields,
    created_at: now(),
    expires_at: addMinutes(now(), 5),
    decision: "pending",
  };
  const next = taskSnapshot(task, {
    status: "waiting_approval",
    message: "测试响应：请核对下方确认单。",
    interaction: {
      interaction_id: "test-confirmation-interaction-" + id(),
      kind: "confirmation",
      prompt: "请核对并决定是否办理。",
      required_fields: [],
      options: [],
      record_ref: confirmationId,
    },
    allowed_actions: ["confirm", "cancel"],
    data: {
      operation_id: null,
      payer_account_id: "test-account",
      payee,
      amount_fen: amountFen,
      operation: null,
    },
  });
  publishTask(state, next);
  auditEvent(state, next, "confirmation.changed", "succeeded");
  saveDemoState(state);
  return next;
}

function createDemoTask(state: DemoState, thread: ThreadView, text: string): TaskView {
  const taskId = "test-task-" + id();
  const at = now();
  const task: TaskView = {
    task_id: taskId,
    run_id: "test-run-" + id(),
    status: "waiting_input",
    data: {
      operation_id: null,
      payer_account_id: null,
      payee: null,
      amount_fen: amountFromDemoText(text),
      operation: null,
    },
    message: "测试响应：请选择或查找收款人。",
    interaction: {
      interaction_id: "test-input-" + id(),
      kind: "input",
      prompt: "请选择收款人，或使用专用资料入口查找。",
      required_fields: ["payee_hint"],
      options: [],
      record_ref: null,
    },
    error: null,
    allowed_actions: ["provide_input", "cancel"],
    recovery_required: false,
    recovery_reason: null,
    thread_id: thread.thread_id,
    demo_round_id: thread.demo_round_id,
    snapshot_at: at,
    task_revision: 0,
    cancel_requested: false,
  };
  state.tasks[taskId] = task;
  state.audit[taskId] = [];
  auditEvent(state, task, "task.transition", "started");
  saveDemoState(state);
  emitDemo(thread.thread_id, "task_updated", task, taskId);
  return task;
}

function makeVerification(state: DemoState, task: TaskView, confirmation: ConfirmationView): VerificationView {
  const challengeId = "test-verification-" + id();
  const view: VerificationView = {
    challenge_id: challengeId,
    task_id: task.task_id,
    created_at: now(),
    summary: {
      operation_id: "00000000-0000-4000-8000-000000000001",
      action_revision: 1,
      source_confirmation_id: confirmation.confirmation_id,
      source_confirmation_version: confirmation.confirmation_version,
      action_name: "bank.submit_transfer",
      amount_fen: task.data?.amount_fen ?? 50_000,
      payee: task.data?.payee ?? null,
      display_fields: confirmation.display_fields,
    },
    required_methods: ["code", "mock_face"],
    code_expires_at: addMinutes(now(), 5),
    face_started_at: null,
    face_expires_at: null,
    code_result: "pending",
    face_result: "pending",
    challenge_status: "pending",
    consecutive_code_failures: 0,
  };
  state.verifications[challengeId] = view;
  return view;
}

function makeReceipt(task: TaskView): NonNullable<NonNullable<TaskView["data"]>["operation"]> {
  const at = now();
  const amount = task.data?.amount_fen ?? 50_000;
  const payee = task.data?.payee ?? candidateList()[0];
  return {
    operation_id: "00000000-0000-4000-8000-000000000001",
    operation_type: "bank.submit_transfer",
    operation_status: "succeeded",
    recorded_at: at,
    updated_at: at,
    failure: null,
    receipt: {
      transaction_id: "test-transaction-" + id(),
      payer_account_id: "test-account",
      payee,
      amount_fen: amount,
      fee_fen: 0,
      arrival_mode: "instant",
      completed_at: at,
      balance: {
        account_id: "test-account",
        book_balance_fen: 100_000,
        frozen_balance_fen: 0,
        available_balance_fen: 100_000,
        as_of: at,
      },
    },
  };
}

function mockGet<T>(path: string): T {
  const state = readDemoState();
  const url = new URL(path, window.location.origin);
  const route = url.pathname.replace(API_ROOT, "");

  if (route === "/session") return requireDemoSession(state) as T;
  if (route === "/threads") {
    const session = requireDemoSession(state, "user");
    const items = state.threads.filter((thread) => thread.demo_round_id === session.demo_round_id);
    return page(items) as T;
  }
  if (route === "/tasks") {
    const session = requireDemoSession(state, "user");
    const threadId = url.searchParams.get("thread_id");
    const recovery = url.searchParams.get("recovery_required");
    const items = Object.values(state.tasks).filter((task) =>
      task.demo_round_id === session.demo_round_id
      && (!threadId || task.thread_id === threadId)
      && (recovery === null || String(task.recovery_required) === recovery));
    return page(items) as T;
  }
  const messagesMatch = route.match(/^\/threads\/([^/]+)\/messages$/);
  if (messagesMatch) {
    requireDemoSession(state, "user");
    return page(demoMessages.get(messagesMatch[1]) ?? []) as T;
  }
  const taskMatch = route.match(/^\/tasks\/([^/]+)$/);
  if (taskMatch) {
    requireDemoSession(state, "user");
    return getTask(state, taskMatch[1]) as T;
  }
  const confirmationMatch = route.match(/^\/confirmations\/([^/]+)$/);
  if (confirmationMatch) {
    requireDemoSession(state, "user");
    const confirmation = state.confirmations[confirmationMatch[1]];
    if (!confirmation) throw new ApiError(404, "NOT_FOUND", "当前测试确认单不存在。");
    return confirmation as T;
  }
  const verificationMatch = route.match(/^\/verifications\/([^/]+)$/);
  if (verificationMatch) {
    requireDemoSession(state, "user");
    const verification = state.verifications[verificationMatch[1]];
    if (!verification) throw new ApiError(404, "NOT_FOUND", "当前测试验证记录不存在。");
    return verification as T;
  }
  const codeMatch = route.match(/^\/verifications\/([^/]+)\/demo-code$/);
  if (codeMatch) {
    requireDemoSession(state, "user");
    const verification = state.verifications[codeMatch[1]];
    if (!verification) throw new ApiError(404, "NOT_FOUND", "当前测试验证记录不存在。");
    return {
      challenge_id: verification.challenge_id,
      code: "123456",
      expires_at: verification.code_expires_at,
    } as T;
  }
  const auditDetailMatch = route.match(/^\/admin\/audit\/events\/([^/]+)$/);
  if (auditDetailMatch) {
    requireDemoSession(state, "admin");
    const detail = state.auditDetails[auditDetailMatch[1]];
    if (!detail) throw new ApiError(404, "NOT_FOUND", "没有这条测试时间线记录。");
    return detail as T;
  }
  if (route === "/admin/audit/events") {
    requireDemoSession(state, "admin");
    const taskId = url.searchParams.get("task_id");
    if (!taskId) throw new ApiError(400, "INVALID_ARGUMENT", "请提供任务编号。");
    getTask(state, taskId);
    return page(state.audit[taskId] ?? []) as T;
  }
  throw new ApiError(404, "NOT_FOUND", "契约测试响应没有此接口。");
}

function mockPost<T>(path: string, body: Record<string, unknown>, headers: Record<string, string> = {}): T {
  const state = readDemoState();
  const url = new URL(path, window.location.origin);
  const route = url.pathname.replace(API_ROOT, "");

  if (route === "/session/enter") {
    const isAdmin = window.location.pathname === "/admin";
    if (isAdmin && !headers["X-Demo-Admin-Key"]) {
      throw new ApiError(400, "INVALID_ARGUMENT", "请输入测试管理员口令。此口令仅用于契约测试，不会保存。");
    }
    const at = now();
    const session: SessionView = {
      session_id: "contract-" + (isAdmin ? "admin" : "user") + "-session",
      user_display: isAdmin ? "测试管理员" : "演示用户",
      role: isAdmin ? "admin" : "user",
      demo_round_id: "contract-demo-round",
      created_at: at,
      expires_at: addMinutes(at, 120),
    };
    setCurrentDemoSession(state, session);
    saveDemoState(state);
    return session as T;
  }
  if (route === "/threads") {
    const session = requireDemoSession(state, "user");
    const thread = makeThread(session);
    state.threads = [...state.threads, thread];
    demoMessages.set(thread.thread_id, []);
    saveDemoState(state);
    return thread as T;
  }
  const sendMatch = route.match(/^\/threads\/([^/]+)\/messages$/);
  if (sendMatch) {
    requireDemoSession(state, "user");
    const threadId = sendMatch[1];
    const thread = state.threads.find((item) => item.thread_id === threadId);
    if (!thread) throw new ApiError(404, "NOT_FOUND", "当前测试对话不存在。");
    const text = typeof body.text === "string" ? body.text : "";
    const messages = demoMessages.get(threadId) ?? [];
    const userMessage = makeMessage(threadId, "user", text);
    const nextMessages = [...messages, userMessage];
    demoMessages.set(threadId, nextMessages);
    emitDemo(threadId, "message_completed", userMessage);
    const accepted: MessageAccepted = {
      message_id: userMessage.message_id,
      thread_id: threadId,
      accepted_at: userMessage.created_at,
      task_id: null,
    };
    if (text.includes("测试转账")) {
      const task = createDemoTask(state, thread, text);
      const assistant = makeMessage(threadId, "assistant", "测试响应：请选择或查找收款人。", [task.task_id]);
      demoMessages.set(threadId, [...nextMessages, assistant]);
      emitDemo(threadId, "message_completed", assistant, task.task_id);
      accepted.task_id = task.task_id;
    } else {
      const assistant = makeMessage(threadId, "assistant", "测试响应：我听到了。普通聊天不会创建转账动作，也不会批准资金操作。");
      demoMessages.set(threadId, [...nextMessages, assistant]);
      emitDemo(threadId, "message_completed", assistant);
    }
    return accepted as T;
  }
  const inputMatch = route.match(/^\/tasks\/([^/]+)\/inputs$/);
  if (inputMatch) {
    requireDemoSession(state, "user");
    const task = getTask(state, inputMatch[1]);
    if (!task.allowed_actions.includes("provide_input") || !task.interaction) {
      throw new ApiError(409, "ACTION_UNAVAILABLE", "当前测试任务不接受补充信息。");
    }
    const selected = String(body.selected_option_id ?? "");
    const candidate = candidateList().find((item) => item.payee_id === selected);
    if (!candidate) throw new ApiError(400, "INVALID_OPTION", "请选择测试候选，或使用专用资料入口。");
    return openConfirmation(state, task, candidate) as T;
  }
  const detailsMatch = route.match(/^\/tasks\/([^/]+)\/details$/);
  if (detailsMatch) {
    requireDemoSession(state, "user");
    const task = getTask(state, detailsMatch[1]);
    if (!task.allowed_actions.includes("provide_input") || task.interaction?.required_fields[0] !== "payee_hint") {
      throw new ApiError(409, "DETAILS_NOT_REQUESTED", "当前测试任务没有收款人资料入口。");
    }
    const kind = body.kind;
    if (kind === "payee_search") {
      return {
        detail_ref: "test-search-" + id(),
        display_fields: [],
        candidates: candidateList(),
        task,
      } as T;
    }
    if (kind === "payee") {
      const fields = body.fields as { account_number?: string; account_name?: string };
      if (!fields?.account_number || !fields.account_name) {
        throw new ApiError(400, "INVALID_ARGUMENT", "请填写账号和收款人姓名。");
      }
      const account = fields.account_number;
      const payee: PayeeCandidate = {
        payee_id: null,
        name_masked: fields.account_name.slice(0, 1) + "*",
        account_masked: "尾号 " + account.slice(-4),
        remark: "手工资料（测试数据）",
        bank_name: "演示银行",
        last_transfer_at: null,
      };
      const next = openConfirmation(state, task, payee);
      return { detail_ref: "test-manual-" + id(), display_fields: [], candidates: null, task: next } as T;
    }
    throw new ApiError(400, "INVALID_ARGUMENT", "测试入口只支持收款人查找或录入。");
  }
  const confirmationMatch = route.match(/^\/confirmations\/([^/]+)\/answer$/);
  if (confirmationMatch) {
    requireDemoSession(state, "user");
    const confirmation = state.confirmations[confirmationMatch[1]];
    if (!confirmation || confirmation.decision !== "pending") {
      throw new ApiError(409, "CONFIRMATION_STALE", "这份测试确认单已失效，请刷新任务。");
    }
    const task = getTask(state, confirmation.task_id);
    const choice = body.choice;
    if (choice === "cancel") {
      state.confirmations[confirmation.confirmation_id] = { ...confirmation, decision: "cancelled" };
      const next = taskSnapshot(task, {
        status: "cancelled",
        message: "测试响应：确认单已取消，没有提交银行操作。",
        interaction: null,
        allowed_actions: [],
      });
      publishTask(state, next);
      auditEvent(state, next, "confirmation.changed", "succeeded");
      saveDemoState(state);
      return next as T;
    }
    if (choice !== "approve" || !task.allowed_actions.includes("confirm")) {
      throw new ApiError(409, "ACTION_UNAVAILABLE", "当前测试任务不能确认。");
    }
    state.confirmations[confirmation.confirmation_id] = { ...confirmation, decision: "approved" };
    const verification = makeVerification(state, task, confirmation);
    state.verifications[verification.challenge_id] = verification;
    const next = taskSnapshot(task, {
      status: "waiting_approval",
      message: "测试响应：需要在专用区域完成验证码，并等待管理员模拟人脸核验。",
      interaction: {
        interaction_id: "test-verification-interaction-" + id(),
        kind: "verification",
        prompt: "请在专用区域完成验证。",
        required_fields: [],
        options: [],
        record_ref: verification.challenge_id,
      },
      allowed_actions: ["verify", "cancel"],
    });
    publishTask(state, next);
    auditEvent(state, next, "verification.changed", "waiting");
    saveDemoState(state);
    return next as T;
  }
  const taskActionMatch = route.match(/^\/tasks\/([^/]+)\/(resume|cancel|query-result)$/);
  if (taskActionMatch) {
    requireDemoSession(state, "user");
    const task = getTask(state, taskActionMatch[1]);
    const command = taskActionMatch[2];
    if (command === "cancel" && task.allowed_actions.includes("cancel")) {
      const next = taskSnapshot(task, { status: "cancelled", message: "测试响应：任务已取消，没有提交银行操作。", interaction: null, allowed_actions: [] });
      publishTask(state, next);
      auditEvent(state, next, "task.transition", "succeeded");
      return next as T;
    }
    if (command === "query-result" && task.allowed_actions.includes("query")) {
      const next = taskSnapshot(task, { status: "needs_attention", message: "测试响应：未提交新操作；查询的仍是原操作，结果暂待核实。", interaction: null, allowed_actions: ["query", "resume"] });
      publishTask(state, next);
      auditEvent(state, next, "task.transition", "unknown");
      return next as T;
    }
    if (command === "resume" && task.allowed_actions.includes("resume")) return task as T;
    throw new ApiError(409, "ACTION_UNAVAILABLE", "当前测试任务不允许此操作。");
  }
  const codeMatch = route.match(/^\/verifications\/([^/]+)\/code$/);
  if (codeMatch) {
    requireDemoSession(state, "user");
    const verification = state.verifications[codeMatch[1]];
    if (!verification || verification.challenge_status !== "pending") {
      throw new ApiError(409, "CHALLENGE_STALE", "测试验证已结束，请刷新任务。");
    }
    const submittedCode = typeof body.code === "string" ? body.code : "";
    const passed = submittedCode === "123456";
    const nextVerification: VerificationView = {
      ...verification,
      code_result: passed ? "passed" : "failed",
      consecutive_code_failures: verification.consecutive_code_failures + (passed ? 0 : 1),
    };
    state.verifications[verification.challenge_id] = nextVerification;
    const task = getTask(state, verification.task_id);
    saveDemoState(state);
    return {
      kind: passed ? "verified" : "rejected",
      verification: nextVerification,
      task,
      error: passed ? null : { code: "VERIFICATION_REJECTED", source: "bank", field: null, reason: "测试验证码不匹配。", upstream_code: null },
    } as T;
  }
  const verificationActionMatch = route.match(/^\/verifications\/([^/]+)\/(resend-code|face\/start)$/);
  if (verificationActionMatch) {
    requireDemoSession(state, "user");
    const verification = state.verifications[verificationActionMatch[1]];
    if (!verification || verification.challenge_status !== "pending") {
      throw new ApiError(409, "CHALLENGE_STALE", "测试验证已结束。");
    }
    const command = verificationActionMatch[2];
    const next = command === "resend-code"
      ? { ...verification, code_result: "pending" as const }
      : { ...verification, face_started_at: now(), face_expires_at: addMinutes(now(), 5) };
    state.verifications[verification.challenge_id] = next;
    saveDemoState(state);
    return next as T;
  }
  const faceMatch = route.match(/^\/admin\/verifications\/([^/]+)\/face-result$/);
  if (faceMatch) {
    requireDemoSession(state, "admin");
    const verification = state.verifications[faceMatch[1]];
    if (!verification || !verification.face_started_at || verification.challenge_status !== "pending") {
      throw new ApiError(409, "CHALLENGE_STALE", "没有等待处理的测试人脸核验。");
    }
    if (body.demo_round_id !== "contract-demo-round") throw new ApiError(403, "ACCESS_DENIED", "测试轮次不匹配。");
    const passed = body.result === "passed";
    const nextVerification: VerificationView = {
      ...verification,
      face_result: passed ? "passed" : "failed",
      challenge_status: passed ? "passed" : "failed",
    };
    state.verifications[verification.challenge_id] = nextVerification;
    const task = getTask(state, verification.task_id);
    const nextTask = passed
      ? taskSnapshot(task, {
          status: "succeeded",
          message: "测试响应：模拟银行返回成功。此结果不是银行交易。",
          interaction: null,
          allowed_actions: [],
          data: task.data ? (() => {
            const operation = makeReceipt(task);
            return { ...task.data, operation_id: operation.operation_id, operation };
          })() : null,
        })
      : taskSnapshot(task, {
          status: "failed",
          message: "测试响应：模拟验证未通过，没有提交银行操作。",
          interaction: null,
          allowed_actions: [],
        });
    publishTask(state, nextTask);
    auditEvent(state, nextTask, "verification.changed", passed ? "succeeded" : "denied");
    saveDemoState(state);
    return {
      kind: passed ? "verified" : "rejected",
      verification: nextVerification,
      task: nextTask,
      error: passed ? null : { code: "VERIFICATION_REJECTED", source: "bank", field: null, reason: "测试人脸核验未通过。", upstream_code: null },
    } as T;
  }
  throw new ApiError(404, "NOT_FOUND", "契约测试响应没有此接口。");
}

export async function get<T>(path: string): Promise<T> {
  if (API_MODE === "contract-demo") return mockGet<T>(API_ROOT + path);
  let response: Response;
  try {
    response = await fetch(API_ROOT + path, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "服务暂不可达。请检查后端连接，再查询当前任务状态。");
  }
  return readResponse<T>(response);
}

export async function post<T>(path: string, body: Record<string, unknown>, extraHeaders: Record<string, string> = {}): Promise<T> {
  if (API_MODE === "contract-demo") return mockPost<T>(API_ROOT + path, body, extraHeaders);
  let response: Response;
  try {
    response = await fetch(API_ROOT + path, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...extraHeaders,
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "服务暂不可达。请先查询当前状态；验证码不会自动重传。");
  }
  return readResponse<T>(response);
}

async function readResponse<T>(response: Response): Promise<T> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(response.status, "INVALID_RESPONSE", "服务返回了无法读取的响应。请刷新任务状态。");
  }
  if (!response.ok) {
    const error = (payload as { error?: ApiProblem }).error;
    throw new ApiError(
      response.status,
      error?.code ?? "REQUEST_FAILED",
      error?.reason ?? "请求未完成。请刷新任务状态后再继续。",
      error?.reason ?? null,
    );
  }
  return unwrap<T>(payload);
}

export function connectToThread(
  threadId: string,
  onEvent: (event: StreamEvent) => void,
  onConnection: (connected: boolean) => void,
): () => void {
  if (API_MODE === "contract-demo") {
    const listeners = demoListeners.get(threadId) ?? new Set<(event: StreamEvent) => void>();
    listeners.add(onEvent);
    demoListeners.set(threadId, listeners);
    onConnection(true);
    return () => {
      listeners.delete(onEvent);
      onConnection(false);
    };
  }

  const stream = new EventSource(API_ROOT + "/threads/" + encodeURIComponent(threadId) + "/events", { withCredentials: true });
  const eventNames: StreamEvent["event_type"][] = [
    "message_delta",
    "message_completed",
    "task_updated",
    "interaction_required",
    "report_ready",
    "session_expired",
    "stream_error",
  ];
  const handlers = eventNames.map((eventName) => {
    const handler = (event: Event) => {
      try {
        const messageEvent = event as MessageEvent<string>;
        const parsed = JSON.parse(messageEvent.data) as StreamEvent;
        onEvent(parsed);
      } catch {
        // The next HTTP snapshot is the reliable source if an event is malformed.
      }
    };
    stream.addEventListener(eventName, handler as EventListener);
    return [eventName, handler] as const;
  });
  stream.onopen = () => onConnection(true);
  stream.onerror = () => onConnection(false);
  return () => {
    for (const [eventName, handler] of handlers) stream.removeEventListener(eventName, handler as EventListener);
    stream.close();
    onConnection(false);
  };
}

export function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "请求未完成。请刷新任务状态后再继续。";
}

export function hasEnteredDemo(): boolean {
  try {
    return localStorage.getItem(USER_ENTERED_KEY) === "yes";
  } catch {
    return false;
  }
}

export function markEnteredDemo(): void {
  try {
    localStorage.setItem(USER_ENTERED_KEY, "yes");
  } catch {
    // This marker contains no login credential or personal data.
  }
}

export function administratorUrl(values: { taskId?: string; challengeId?: string; demoRoundId?: string }): string {
  let host = window.location.host;
  if (API_MODE === "real-api" && ["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    const otherHost = window.location.hostname === "localhost" ? "127.0.0.1" : "localhost";
    host = otherHost + (window.location.port ? ":" + window.location.port : "");
  }
  const params = new URLSearchParams();
  if (values.taskId) params.set("task_id", values.taskId);
  if (values.challengeId) params.set("challenge_id", values.challengeId);
  if (values.demoRoundId) params.set("demo_round_id", values.demoRoundId);
  return window.location.protocol + "//" + host + "/admin" + (params.size ? "?" + params.toString() : "");
}

export function userPageUrl(): string {
  let host = window.location.host;
  if (API_MODE === "real-api" && ["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    const otherHost = window.location.hostname === "localhost" ? "127.0.0.1" : "localhost";
    host = otherHost + (window.location.port ? ":" + window.location.port : "");
  }
  return window.location.protocol + "//" + host + "/";
}
