// Local stub backend for the shell demo. Transfer-shaped demo data only: nothing here calls a
// bank or the real API, and every fact it returns is labelled as demo data in the UI.
import { ApiError } from "../../api";
import type {
  ConfirmationView,
  DemoCodeView,
  DisplayField,
  MessageAccepted,
  MessageView,
  PayeeDisplay,
  SessionView,
  ThreadView,
  TransferTaskView,
  VerificationView,
} from "../../contracts";
import type { AdminDemoSource, ShellDataSource, ShellEvent, ShellTask, ShellVerificationResponse, TaskEnvelope } from "../types";

const STORAGE_KEY = "fe-shell-stub-v1";
const DEMO_ROUND = "stub-demo-round";
const DEMO_CODE = "123456";
const MODULE = "transfer";
const MINUTE = 60_000;

type Phase = "choose" | "confirm" | "verify" | "submitting" | "bank" | "settled";

interface StubTask {
  task: ShellTask<TransferTaskView>;
  phase: Phase;
  phaseUntil: number | null;
  visibleAt: number;
  createdAt: number;
}

interface StubState {
  userSession: SessionView | null;
  userSessionExpired: boolean;
  adminSession: SessionView | null;
  thread: ThreadView | null;
  messages: MessageView[];
  tasks: Record<string, StubTask>;
  confirmations: Record<string, ConfirmationView>;
  verifications: Record<string, VerificationView>;
  faults: { resultUnknown: boolean };
  replies: Record<string, unknown>;
  sequence: number;
}

const PAYER_LABEL = "主账户（尾号 1234）";
const PAYEES: Record<string, PayeeDisplay> = {
  "demo-payee-mom": { payee_id: "demo-payee-mom", name_masked: "妈妈", account_masked: "尾号 6688", remark: "常用收款人", bank_name: "演示银行" },
  "demo-payee-zhang": { payee_id: "demo-payee-zhang", name_masked: "张阿姨", account_masked: "尾号 3166", remark: "最近转过", bank_name: "演示银行" },
};

function emptyState(): StubState {
  return {
    userSession: null,
    userSessionExpired: false,
    adminSession: null,
    thread: null,
    messages: [],
    tasks: {},
    confirmations: {},
    verifications: {},
    faults: { resultUnknown: false },
    replies: {},
    sequence: 0,
  };
}

export interface StubOptions {
  storage?: Storage;
  now?: () => number;
  replyDelayMs?: number;
  submitMs?: number;
  bankMs?: number;
  tickMs?: number;
}

export interface PendingFaceChallenge {
  challenge_id: string;
  task_id: string;
  demo_round_id: string;
  display_fields: DisplayField[];
  face_expires_at: string | null;
}

export interface StubAdminExtras {
  listPendingFaceChallenges(): PendingFaceChallenge[];
  getFaults(): { resultUnknown: boolean };
  setResultUnknownFault(enabled: boolean): void;
  resetDemo(): void;
}

export function createDemoBackend(options: StubOptions = {}) {
  const storage = options.storage ?? window.localStorage;
  const clock = options.now ?? (() => Date.now());
  const replyDelay = options.replyDelayMs ?? 700;
  const submitMs = options.submitMs ?? 1600;
  const bankMs = options.bankMs ?? 1400;
  const tickMs = options.tickMs ?? 400;

  function clone<T>(value: T): T {
    return value === undefined ? value : JSON.parse(JSON.stringify(value));
  }

  function iso(ms: number = clock()): string {
    return new Date(ms).toISOString();
  }

  function load(): StubState {
    try {
      const raw = storage.getItem(STORAGE_KEY);
      return raw ? { ...emptyState(), ...JSON.parse(raw) } : emptyState();
    } catch {
      return emptyState();
    }
  }

  function save(state: StubState): void {
    try {
      storage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Storage may be blocked; the demo still runs for this page view.
    }
  }

  function nextId(state: StubState, prefix: string): string {
    state.sequence += 1;
    return prefix + "-" + state.sequence + "-" + Math.random().toString(36).slice(2, 8);
  }

  function requireUser(state: StubState): SessionView {
    if (!state.userSession || state.userSessionExpired) {
      throw new ApiError(401, "AUTH_REQUIRED", "演示登录已过期，请点击重新进入。");
    }
    return state.userSession;
  }

  function requireAdmin(state: StubState): SessionView {
    if (!state.adminSession) throw new ApiError(403, "ACCESS_DENIED", "需要先进入管理员演示端。");
    return state.adminSession;
  }

  function getRecord(state: StubState, taskId: string): StubTask {
    const record = state.tasks[taskId];
    if (!record || record.visibleAt > clock()) throw new ApiError(404, "NOT_FOUND", "没有找到这项任务。");
    return record;
  }

  function bump(record: StubTask, patch: Partial<ShellTask<TransferTaskView>>): void {
    record.task = {
      ...record.task,
      ...patch,
      task_revision: record.task.task_revision + 1,
      snapshot_at: iso(),
    };
  }

  function addMessage(state: StubState, role: "user" | "assistant", text: string, taskIds: string[] = [], delay = 0): MessageView {
    const message: MessageView = {
      message_id: nextId(state, "demo-msg"),
      thread_id: state.thread!.thread_id,
      role,
      text,
      created_at: iso(clock() + delay),
      task_ids: taskIds,
      report_ids: [],
    };
    state.messages.push(message);
    return message;
  }

  function once<T>(state: StubState, requestId: string, run: () => T): T {
    if (requestId in state.replies) return state.replies[requestId] as T;
    const result = run();
    state.replies[requestId] = result;
    return result;
  }

  function amountFromText(text: string): number {
    const match = text.match(/(\d+(?:\.\d{1,2})?)\s*(元|块)?/);
    const value = match ? Math.round(Number(match[1]) * 100) : 50_000;
    return Number.isFinite(value) && value > 0 ? value : 50_000;
  }

  function terminate(state: StubState, record: StubTask, code: string, reason: string): void {
    record.phase = "settled";
    record.phaseUntil = null;
    bump(record, {
      status: "failed",
      message: reason,
      interaction: null,
      allowed_actions: [],
      error: { code, source: "security", field: null, reason, upstream_code: null },
    });
    for (const verification of Object.values(state.verifications)) {
      if (verification.task_id === record.task.task_id && verification.challenge_status === "pending") {
        verification.challenge_status = "failed";
      }
    }
  }

  function receipt(record: StubTask) {
    const at = iso();
    const data = record.task.data!;
    return {
      operation_id: data.operation_id!,
      operation_type: "bank.submit_transfer",
      operation_status: "succeeded" as const,
      recorded_at: at,
      updated_at: at,
      failure: null,
      receipt: {
        transaction_id: "DEMO-" + at.slice(0, 10).replaceAll("-", "") + "-" + record.task.task_id.split("-")[2],
        payer_account_id: data.payer_account_id ?? "demo-acct-1234",
        payee: data.payee!,
        amount_fen: data.amount_fen ?? 0,
        fee_fen: 0 as const,
        arrival_mode: "instant" as const,
        completed_at: at,
        balance: {
          account_id: "demo-acct-1234",
          book_balance_fen: 0,
          frozen_balance_fen: 0,
          available_balance_fen: 0,
          as_of: at,
        },
      },
    };
  }

  function settleSucceeded(state: StubState, record: StubTask, message: string): void {
    const operation = receipt(record);
    record.phase = "settled";
    record.phaseUntil = null;
    bump(record, {
      status: "succeeded",
      message,
      interaction: null,
      allowed_actions: [],
      data: { ...record.task.data!, operation },
    });
    addMessage(state, "assistant", "还有什么要我帮忙的吗？", [], 300);
  }

  // Advances timers as a server would; safe to call repeatedly from several tabs.
  function advance(state: StubState): boolean {
    const now = clock();
    let changed = false;
    for (const record of Object.values(state.tasks)) {
      if (record.phase === "verify") {
        const challengeId = record.task.interaction?.record_ref;
        const verification = challengeId ? state.verifications[challengeId] : undefined;
        if (verification && verification.challenge_status === "pending") {
          if (verification.code_result === "pending" && Date.parse(verification.code_expires_at) < now) {
            verification.code_result = "expired";
            verification.challenge_status = "expired";
            terminate(state, record, "VERIFICATION_EXPIRED", "验证码已超时。按安全规则本次办理已终止，没有提交给银行。");
            changed = true;
          } else if (verification.face_expires_at && verification.face_result === "pending" && Date.parse(verification.face_expires_at) < now) {
            verification.face_result = "expired";
            verification.challenge_status = "expired";
            terminate(state, record, "VERIFICATION_EXPIRED", "模拟人脸验证已超时。按安全规则本次办理已终止，没有提交给银行。");
            changed = true;
          }
        }
      }
      while (record.phaseUntil !== null && record.phaseUntil <= now) {
        changed = true;
        if (record.phase === "submitting") {
          record.phase = "bank";
          record.phaseUntil += bankMs;
          bump(record, { message: "银行正在处理，请稍等，完成后会显示结果。" });
        } else if (record.phase === "bank") {
          if (state.faults.resultUnknown) {
            state.faults.resultUnknown = false;
            record.phase = "settled";
            record.phaseUntil = null;
            const at = iso();
            bump(record, {
              status: "needs_attention",
              message: "银行的结果暂时没有返回，请过一会儿再查。",
              allowed_actions: ["query"],
              data: {
                ...record.task.data!,
                operation: {
                  operation_id: record.task.data!.operation_id!,
                  operation_type: "bank.submit_transfer",
                  operation_status: "processing",
                  recorded_at: at,
                  updated_at: at,
                  failure: null,
                  receipt: null,
                },
              },
            });
          } else {
            settleSucceeded(state, record, "银行已返回结果。");
          }
        } else {
          record.phaseUntil = null;
        }
      }
    }
    return changed;
  }

  function read(): StubState {
    const state = load();
    if (advance(state)) save(state);
    return state;
  }

  function mutate<T>(run: (state: StubState) => T): Promise<T> {
    try {
      const state = load();
      advance(state);
      const result = run(state);
      save(state);
      sync();
      return Promise.resolve(clone(result));
    } catch (error) {
      return Promise.reject(error);
    }
  }

  function query<T>(run: (state: StubState) => T): Promise<T> {
    try {
      return Promise.resolve(clone(run(read())));
    } catch (error) {
      return Promise.reject(error);
    }
  }

  function envelope(record: StubTask): TaskEnvelope {
    return { task: record.task as ShellTask, module: MODULE };
  }

  function makeVerificationResponse(verification: VerificationView, record: StubTask, error: ShellTask["error"]): ShellVerificationResponse {
    return {
      kind: error ? "rejected" : "verified",
      verification,
      task: record.task as ShellTask,
      error,
    };
  }

  // ---- event fan-out: one diff routine for local writes, ticks and other tabs ----
  interface Listener {
    threadId: string;
    onEvent: (event: ShellEvent) => void;
    seenTasks: Map<string, number>;
    seenMessages: Set<string>;
    expiredSent: boolean;
  }
  const listeners = new Set<Listener>();
  let ticker: number | null = null;

  function snapshotSeen(listener: Listener, state: StubState): void {
    const now = clock();
    for (const record of Object.values(state.tasks)) {
      if (record.visibleAt <= now) listener.seenTasks.set(record.task.task_id, record.task.task_revision);
    }
    for (const message of state.messages) {
      if (Date.parse(message.created_at) <= now) listener.seenMessages.add(message.message_id);
    }
  }

  function sync(): void {
    if (listeners.size === 0) return;
    const state = read();
    const now = clock();
    for (const listener of listeners) {
      const base = {
        thread_id: listener.threadId,
        session_id: state.userSession?.session_id ?? "stub-session",
        module: MODULE,
        occurred_at: iso(now),
      };
      if (state.userSessionExpired && state.userSession && !listener.expiredSent) {
        listener.expiredSent = true;
        listener.onEvent({ ...base, event_id: "expired-" + state.userSession.session_id, task_id: null, run_id: null, event_type: "session_expired", payload: { session_id: state.userSession.session_id, reason: "demo_expired" } });
      }
      for (const message of state.messages) {
        if (message.thread_id !== listener.threadId || listener.seenMessages.has(message.message_id)) continue;
        if (Date.parse(message.created_at) > now) continue;
        listener.seenMessages.add(message.message_id);
        listener.onEvent({ ...base, event_id: "evt-" + message.message_id, task_id: message.task_ids[0] ?? null, run_id: null, event_type: "message_completed", payload: message });
      }
      for (const record of Object.values(state.tasks)) {
        const task = record.task;
        if (task.thread_id !== listener.threadId || record.visibleAt > now) continue;
        if (listener.seenTasks.get(task.task_id) === task.task_revision) continue;
        listener.seenTasks.set(task.task_id, task.task_revision);
        listener.onEvent({ ...base, event_id: "evt-" + task.task_id + "-" + task.task_revision, task_id: task.task_id, run_id: task.run_id, event_type: "task_updated", payload: clone(task) });
      }
    }
  }

  function onStorage(event: StorageEvent): void {
    if (event.key === STORAGE_KEY) sync();
  }

  function newConfirmation(state: StubState, record: StubTask, version: number): ConfirmationView {
    const data = record.task.data!;
    const payee = data.payee!;
    const confirmation: ConfirmationView = {
      confirmation_id: nextId(state, "demo-confirmation"),
      task_id: record.task.task_id,
      confirmation_version: version,
      display_fields: [
        { name: "payee", label: "收款人", value_text: payee.name_masked + "（" + payee.account_masked + "）" },
        { name: "bank", label: "收款银行", value_text: payee.bank_name },
        { name: "payer", label: "转出账户", value_text: PAYER_LABEL },
        { name: "amount", label: "金额", value_text: "¥" + ((data.amount_fen ?? 0) / 100).toFixed(2) },
        { name: "fee", label: "手续费", value_text: "¥0.00" },
        { name: "arrival", label: "到账方式", value_text: "实时到账" },
      ],
      created_at: iso(),
      expires_at: iso(clock() + 60 * MINUTE),
      decision: "pending",
    };
    state.confirmations[confirmation.confirmation_id] = confirmation;
    record.phase = "confirm";
    bump(record, {
      status: "waiting_approval",
      message: "请核对确认单，确认无误后点「确认办理」。",
      interaction: {
        interaction_id: nextId(state, "demo-interaction"),
        kind: "confirmation",
        prompt: "请核对并决定是否办理。",
        required_fields: [],
        options: [],
        record_ref: confirmation.confirmation_id,
      },
      allowed_actions: ["confirm", "cancel"],
      recovery_required: false,
      recovery_reason: null,
    });
    return confirmation;
  }

  const user: ShellDataSource = {
    origin: "stub",

    enterSession: ({ request_id }) => mutate((state) => once(state, request_id, () => {
      if (state.userSession && !state.userSessionExpired) return state.userSession;
      const relogin = state.userSessionExpired;
      const at = iso();
      state.userSession = {
        session_id: nextId(state, "stub-user-session"),
        user_display: "演示用户",
        role: "user",
        demo_round_id: DEMO_ROUND,
        created_at: at,
        expires_at: iso(clock() + 120 * MINUTE),
      };
      state.userSessionExpired = false;
      if (relogin) {
        for (const record of Object.values(state.tasks)) {
          if (record.phase === "confirm" || record.phase === "verify") {
            bump(record, {
              recovery_required: true,
              recovery_reason: "登录已更换，原来的确认和验证不能继续使用，需要重新确认。",
              allowed_actions: ["resume", "cancel"],
            });
          }
        }
      }
      return state.userSession;
    })),

    getSession: () => query(requireUser),

    ensureThread: () => mutate((state) => {
      const session = requireUser(state);
      if (!state.thread) {
        const at = iso();
        state.thread = { thread_id: nextId(state, "demo-thread"), title: "银行助手", created_at: at, updated_at: at, demo_round_id: session.demo_round_id };
      }
      return state.thread;
    }),

    listMessages: (threadId) => query((state) => {
      requireUser(state);
      const now = clock();
      return state.messages.filter((message) => message.thread_id === threadId && Date.parse(message.created_at) <= now);
    }),

    listTasks: (threadId) => query((state) => {
      requireUser(state);
      const now = clock();
      return Object.values(state.tasks)
        .filter((record) => record.task.thread_id === threadId && record.visibleAt <= now)
        .sort((a, b) => a.createdAt - b.createdAt)
        .map(envelope);
    }),

    getTask: (taskId) => query((state) => {
      requireUser(state);
      return envelope(getRecord(state, taskId));
    }),

    sendMessage: (threadId, { request_id, text }) => mutate((state) => {
      requireUser(state);
      if (!state.thread || state.thread.thread_id !== threadId) throw new ApiError(404, "NOT_FOUND", "没有找到这段对话。");
      if (/^\s*\d{6}\s*$/.test(text)) {
        throw new ApiError(400, "USE_VERIFICATION_ENDPOINT", "验证码请填在专用验证框里，不要发在聊天里。");
      }
      return once(state, request_id, (): MessageAccepted => {
        const userMessage = addMessage(state, "user", text);
        let taskId: string | null = null;
        if (/转|汇/.test(text)) {
          taskId = nextId(state, "demo-task");
          const now = clock();
          state.tasks[taskId] = {
            phase: "choose",
            phaseUntil: null,
            visibleAt: now + replyDelay,
            createdAt: now,
            task: {
              task_id: taskId,
              run_id: nextId(state, "demo-run"),
              status: "waiting_input",
              data: { operation_id: null, payer_account_id: null, payee: null, amount_fen: amountFromText(text), operation: null },
              message: "请选择收款人。",
              interaction: {
                interaction_id: nextId(state, "demo-interaction"),
                kind: "input",
                prompt: "请选择收款人：",
                required_fields: [],
                options: Object.values(PAYEES).map((payee) => ({
                  id: payee.payee_id!,
                  label: payee.name_masked + " · " + payee.account_masked + "（" + payee.remark + "）",
                })),
                record_ref: null,
              },
              error: null,
              allowed_actions: ["provide_input", "cancel"],
              recovery_required: false,
              recovery_reason: null,
              thread_id: threadId,
              demo_round_id: DEMO_ROUND,
              snapshot_at: iso(now + replyDelay),
              task_revision: 0,
              cancel_requested: false,
            },
          };
          addMessage(state, "assistant", "好的，我帮您办一笔转账。", [taskId], replyDelay);
        } else if (/确认/.test(text)) {
          addMessage(state, "assistant", "聊天里说「确认」不会批准任何资金操作。请在确认单上点按钮。", [], replyDelay);
        } else {
          addMessage(state, "assistant", "我听到了。演示环境目前只接了转账形状的演示流程，您可以说「转给妈妈 500 块」。", [], replyDelay);
        }
        return { message_id: userMessage.message_id, thread_id: threadId, accepted_at: userMessage.created_at, task_id: taskId };
      });
    }),

    provideInput: (taskId, { request_id, interaction_id, selected_option_id }) => mutate((state) => {
      requireUser(state);
      return once(state, request_id, () => {
        const record = getRecord(state, taskId);
        if (!record.task.allowed_actions.includes("provide_input") || record.task.interaction?.interaction_id !== interaction_id) {
          throw new ApiError(409, "INTERACTION_STALE", "这一步已经过去了，请看最新的卡片。");
        }
        const payee = selected_option_id ? PAYEES[selected_option_id] : undefined;
        if (!payee) throw new ApiError(400, "INVALID_OPTION", "请从列出的收款人里选择。");
        record.task.data = { ...record.task.data!, payee, payer_account_id: "demo-acct-1234" };
        newConfirmation(state, record, 1);
        addMessage(state, "assistant", "您选择了" + payee.name_masked + "（" + payee.account_masked + "），请再核对完整信息。", [taskId]);
        return record.task as ShellTask;
      });
    }),

    resumeTask: (taskId, { request_id }) => mutate((state) => {
      requireUser(state);
      return once(state, request_id, () => {
        const record = getRecord(state, taskId);
        if (!record.task.recovery_required) throw new ApiError(409, "ACTION_UNAVAILABLE", "这项任务不需要恢复。");
        if (record.phase === "confirm" || record.phase === "verify") {
          for (const item of Object.values(state.confirmations)) {
            if (item.task_id === taskId && item.decision === "pending") item.decision = "superseded";
          }
          for (const item of Object.values(state.verifications)) {
            if (item.task_id === taskId && item.challenge_status === "pending") item.challenge_status = "superseded";
          }
          const versions = Object.values(state.confirmations).filter((item) => item.task_id === taskId).map((item) => item.confirmation_version);
          record.task.run_id = nextId(state, "demo-run");
          newConfirmation(state, record, Math.max(0, ...versions) + 1);
          bump(record, { message: "已恢复原任务。登录更换后需要重新确认一次。" });
        } else {
          bump(record, { recovery_required: false, recovery_reason: null, allowed_actions: record.task.allowed_actions.filter((action) => action !== "resume") });
        }
        return record.task as ShellTask;
      });
    }),

    cancelTask: (taskId, { request_id }) => mutate((state) => {
      requireUser(state);
      return once(state, request_id, () => {
        const record = getRecord(state, taskId);
        if (!record.task.allowed_actions.includes("cancel")) throw new ApiError(409, "ACTION_UNAVAILABLE", "这项任务现在不能取消。");
        for (const item of Object.values(state.confirmations)) {
          if (item.task_id === taskId && item.decision === "pending") item.decision = "cancelled";
        }
        for (const item of Object.values(state.verifications)) {
          if (item.task_id === taskId && item.challenge_status === "pending") item.challenge_status = "cancelled";
        }
        record.phase = "settled";
        bump(record, { status: "cancelled", message: "这笔转账已取消，没有提交给银行。", interaction: null, allowed_actions: [], recovery_required: false, recovery_reason: null });
        return record.task as ShellTask;
      });
    }),

    queryResult: (taskId, { request_id }) => mutate((state) => {
      requireUser(state);
      return once(state, request_id, () => {
        const record = getRecord(state, taskId);
        if (!record.task.allowed_actions.includes("query")) throw new ApiError(409, "ACTION_UNAVAILABLE", "这项任务现在不需要查询。");
        settleSucceeded(state, record, "已查到原操作的结果。这次只是查询，没有重新提交。");
        return record.task as ShellTask;
      });
    }),

    getConfirmation: (confirmationId) => query((state) => {
      requireUser(state);
      const confirmation = state.confirmations[confirmationId];
      if (!confirmation) throw new ApiError(404, "NOT_FOUND", "没有找到这张确认单。");
      return confirmation;
    }),

    answerConfirmation: (confirmationId, { request_id, confirmation_version, choice }) => mutate((state) => {
      requireUser(state);
      return once(state, request_id, () => {
        const confirmation = state.confirmations[confirmationId];
        if (!confirmation || confirmation.decision !== "pending" || confirmation.confirmation_version !== confirmation_version) {
          throw new ApiError(409, "CONFIRMATION_STALE", "这张确认单已经失效，请以最新的确认单为准。");
        }
        const record = getRecord(state, confirmation.task_id);
        if (record.task.recovery_required) throw new ApiError(409, "RECOVERY_REQUIRED", "请先恢复原任务，再重新确认。");
        if (choice === "cancel") {
          if (!record.task.allowed_actions.includes("cancel")) throw new ApiError(409, "ACTION_UNAVAILABLE", "现在不能取消。");
          confirmation.decision = "cancelled";
          record.phase = "settled";
          bump(record, { status: "cancelled", message: "好的，这笔转账已取消，没有提交给银行。", interaction: null, allowed_actions: [] });
          return record.task as ShellTask;
        }
        if (!record.task.allowed_actions.includes("confirm")) throw new ApiError(409, "ACTION_UNAVAILABLE", "现在不能确认。");
        confirmation.decision = "approved";
        const verification: VerificationView = {
          challenge_id: nextId(state, "demo-challenge"),
          task_id: record.task.task_id,
          summary: {
            operation_id: crypto.randomUUID(),
            action_revision: 1,
            source_confirmation_id: confirmation.confirmation_id,
            source_confirmation_version: confirmation.confirmation_version,
            action_name: "bank.submit_transfer",
            amount_fen: record.task.data?.amount_fen ?? null,
            payee: record.task.data?.payee ?? null,
            display_fields: confirmation.display_fields,
          },
          required_methods: ["code", "mock_face"],
          code_expires_at: iso(clock() + 5 * MINUTE),
          face_started_at: null,
          face_expires_at: null,
          code_result: "pending",
          face_result: "pending",
          challenge_status: "pending",
          consecutive_code_failures: 0,
        };
        state.verifications[verification.challenge_id] = verification;
        record.phase = "verify";
        bump(record, {
          status: "waiting_approval",
          message: "为了安全，请先输入验证码，再完成模拟人脸验证。",
          interaction: {
            interaction_id: nextId(state, "demo-interaction"),
            kind: "verification",
            prompt: "请完成验证码和模拟人脸两项验证。",
            required_fields: [],
            options: [],
            record_ref: verification.challenge_id,
          },
          allowed_actions: ["verify", "cancel"],
        });
        return record.task as ShellTask;
      });
    }),

    getVerification: (challengeId) => query((state) => {
      requireUser(state);
      const verification = state.verifications[challengeId];
      if (!verification) throw new ApiError(404, "NOT_FOUND", "没有找到这项验证。");
      return verification;
    }),

    submitCode: (challengeId, { request_id, code }) => mutate((state) => {
      requireUser(state);
      return once(state, request_id, () => {
        const verification = state.verifications[challengeId];
        if (!verification || verification.challenge_status !== "pending" || verification.code_result !== "pending") {
          throw new ApiError(409, "CHALLENGE_STALE", "这项验证已经结束，请看最新状态。");
        }
        const record = getRecord(state, verification.task_id);
        if (!record.task.allowed_actions.includes("verify") || record.task.recovery_required) {
          throw new ApiError(409, "ACTION_UNAVAILABLE", "现在不能提交验证码。");
        }
        if (code === DEMO_CODE) {
          verification.code_result = "passed";
          bump(record, { message: "验证码已通过。请继续完成模拟人脸验证。" });
          return makeVerificationResponse(verification, record, null);
        }
        verification.code_result = "failed";
        verification.consecutive_code_failures += 1;
        terminate(state, record, "VERIFICATION_FAILED", "验证码不正确。按安全规则本次办理已终止，没有提交给银行。");
        return makeVerificationResponse(state.verifications[challengeId], record, record.task.error);
      });
    }),

    resendCode: (challengeId, { request_id }) => mutate((state) => {
      requireUser(state);
      return once(state, request_id, () => {
        const old = state.verifications[challengeId];
        if (!old || old.challenge_status !== "pending" || old.code_result !== "pending") {
          throw new ApiError(409, "CHALLENGE_STALE", "这项验证已经结束，不能重新获取。");
        }
        const record = getRecord(state, old.task_id);
        old.challenge_status = "superseded";
        const fresh: VerificationView = { ...old, challenge_id: nextId(state, "demo-challenge"), challenge_status: "pending" };
        state.verifications[fresh.challenge_id] = fresh;
        bump(record, {
          message: "已重新发送验证码，旧验证码失效。截止时间不变。",
          interaction: { ...record.task.interaction!, interaction_id: nextId(state, "demo-interaction"), record_ref: fresh.challenge_id },
        });
        return fresh;
      });
    }),

    getDemoCode: (challengeId) => query((state): DemoCodeView => {
      requireUser(state);
      const verification = state.verifications[challengeId];
      if (!verification || verification.challenge_status !== "pending") throw new ApiError(409, "CHALLENGE_STALE", "这项验证已经结束。");
      return { challenge_id: challengeId, code: DEMO_CODE, expires_at: verification.code_expires_at };
    }),

    startFace: (challengeId, { request_id }) => mutate((state) => {
      requireUser(state);
      return once(state, request_id, () => {
        const verification = state.verifications[challengeId];
        if (!verification || verification.challenge_status !== "pending" || !verification.required_methods.includes("mock_face")) {
          throw new ApiError(409, "CHALLENGE_STALE", "这项验证已经结束。");
        }
        if (verification.required_methods.includes("code") && verification.code_result !== "passed") {
          throw new ApiError(409, "CODE_REQUIRED", "请先完成验证码。");
        }
        const record = getRecord(state, verification.task_id);
        if (!verification.face_started_at) {
          verification.face_started_at = iso();
          verification.face_expires_at = iso(clock() + 5 * MINUTE);
          bump(record, { message: "正在等待管理员在演示端作答模拟人脸验证。" });
        }
        return verification;
      });
    }),

    subscribe(threadId, onEvent, onConnection) {
      const listener: Listener = { threadId, onEvent, seenTasks: new Map(), seenMessages: new Set(), expiredSent: false };
      snapshotSeen(listener, read());
      listeners.add(listener);
      if (listeners.size === 1) {
        window.addEventListener("storage", onStorage);
        ticker = window.setInterval(sync, tickMs);
      }
      onConnection(true);
      return () => {
        listeners.delete(listener);
        if (listeners.size === 0) {
          window.removeEventListener("storage", onStorage);
          if (ticker !== null) window.clearInterval(ticker);
          ticker = null;
        }
        onConnection(false);
      };
    },
  };

  const admin: AdminDemoSource & StubAdminExtras = {
    origin: "stub",

    enterAdmin: ({ request_id }) => mutate((state) => once(state, request_id, () => {
      if (!state.adminSession) {
        const at = iso();
        state.adminSession = {
          session_id: nextId(state, "stub-admin-session"),
          user_display: "演示管理员",
          role: "admin",
          demo_round_id: DEMO_ROUND,
          created_at: at,
          expires_at: iso(clock() + 120 * MINUTE),
        };
      }
      return state.adminSession;
    })),

    getAdminSession: () => query((state) => {
      const session = state.adminSession;
      if (!session) throw new ApiError(401, "AUTH_REQUIRED", "尚未进入管理员演示端。");
      return session;
    }),

    answerFace: (challengeId, { request_id, demo_round_id, result }) => mutate((state) => {
      requireAdmin(state);
      return once(state, request_id, () => {
        if (demo_round_id !== DEMO_ROUND) throw new ApiError(409, "ROUND_MISMATCH", "演示轮次不一致。");
        const verification = state.verifications[challengeId];
        if (!verification || verification.challenge_status !== "pending" || !verification.face_started_at || verification.face_result !== "pending") {
          throw new ApiError(409, "CHALLENGE_STALE", "这项模拟人脸验证已经结束或尚未开始。");
        }
        const record = state.tasks[verification.task_id];
        if (result === "failed") {
          verification.face_result = "failed";
          verification.challenge_status = "failed";
          terminate(state, record, "VERIFICATION_FAILED", "模拟人脸验证未通过。按安全规则本次办理已终止，没有提交给银行。");
          return makeVerificationResponse(verification, record, record.task.error);
        }
        verification.face_result = "passed";
        verification.challenge_status = "passed";
        record.phase = "submitting";
        record.phaseUntil = clock() + submitMs;
        record.task.data = { ...record.task.data!, operation_id: verification.summary?.operation_id ?? crypto.randomUUID() };
        bump(record, { status: "running", message: "正在安全提交这笔转账，请不要重复操作。", interaction: null, allowed_actions: [] });
        return makeVerificationResponse(verification, record, null);
      });
    }),

    expireUserSession: ({ request_id, demo_round_id }) => mutate((state) => {
      requireAdmin(state);
      return once(state, request_id, () => {
        if (demo_round_id !== DEMO_ROUND) throw new ApiError(409, "ROUND_MISMATCH", "演示轮次不一致。");
        if (!state.userSession) throw new ApiError(404, "NOT_FOUND", "当前没有用户演示会话。");
        state.userSessionExpired = true;
        return { session_id: state.userSession.session_id, expired_at: iso() };
      });
    }),

    listPendingFaceChallenges() {
      const state = read();
      if (!state.adminSession) return [];
      return Object.values(state.verifications)
        .filter((item) => item.challenge_status === "pending" && item.face_started_at && item.face_result === "pending")
        .map((item) => ({
          challenge_id: item.challenge_id,
          task_id: item.task_id,
          demo_round_id: DEMO_ROUND,
          display_fields: item.summary?.display_fields ?? [],
          face_expires_at: item.face_expires_at,
        }));
    },

    getFaults: () => read().faults,

    setResultUnknownFault(enabled) {
      const state = load();
      requireAdmin(state);
      state.faults.resultUnknown = enabled;
      save(state);
    },

    resetDemo() {
      storage.removeItem(STORAGE_KEY);
      for (const key of Object.keys(storage)) {
        if (key.startsWith("fe-shell-history:")) storage.removeItem(key);
      }
    },
  };

  return { user, admin, sync };
}

export type DemoBackend = ReturnType<typeof createDemoBackend>;
