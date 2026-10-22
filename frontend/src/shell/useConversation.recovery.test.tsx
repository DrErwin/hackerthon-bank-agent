import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ApiError } from "../api";
import type { ConfirmationView, MessageView, SessionView, TaskRecordsView, ThreadView } from "../contracts";
import { AssistantPage } from "./AssistantPage";
import { verificationAdminHref, verificationAdminLabel } from "./components/TaskBlock";
import { shellUsesContractDemo } from "./ShellApp";
import { createSlotRegistry } from "./slots";
import { transferSlot } from "./slots/transferDemoSlot";
import type { ShellDataSource, ShellEvent, ShellTask, TaskEnvelope } from "./types";

const slots = createSlotRegistry([transferSlot]);
const session: SessionView = {
  session_id: "session-1",
  user_display: "演示用户",
  role: "user",
  demo_round_id: "round-1",
  created_at: "2026-10-18T00:00:00Z",
  expires_at: "2026-10-18T02:00:00Z",
};
const thread: ThreadView = {
  thread_id: "thread-1",
  title: "银行助手",
  created_at: "2026-10-18T00:00:00Z",
  updated_at: "2026-10-18T00:00:00Z",
  demo_round_id: "round-1",
};

function task(id: string, status: ShellTask["status"], revision = 1): ShellTask {
  return {
    task_id: id,
    run_id: "run-" + id,
    status,
    data: null,
    message: status === "succeeded" ? "转账已完成" : "正在办理",
    interaction: null,
    error: null,
    allowed_actions: [],
    recovery_required: false,
    recovery_reason: null,
    thread_id: thread.thread_id,
    demo_round_id: "round-1",
    snapshot_at: "2026-10-18T00:00:0" + revision + "Z",
    task_revision: revision,
    cancel_requested: false,
  };
}

function confirmation(taskId: string): ConfirmationView {
  return {
    confirmation_id: "confirmation-" + taskId,
    task_id: taskId,
    confirmation_version: 1,
    display_fields: [{ name: "amount", label: "金额", value_text: "¥500.00" }],
    created_at: "2026-10-18T00:00:01Z",
    expires_at: "2026-10-18T01:00:00Z",
    decision: "approved",
  };
}

function message(text: string, taskIds: string[] = []): MessageView {
  return {
    message_id: "message-" + text,
    thread_id: thread.thread_id,
    role: "user",
    text,
    created_at: "2026-10-18T00:00:00Z",
    task_ids: taskIds,
    report_ids: [],
  };
}

function sourceHarness() {
  const messages: MessageView[] = [];
  const tasks: TaskEnvelope[] = [];
  const records = new Map<string, TaskRecordsView>();
  const recordFailures = new Map<string, ApiError>();
  let recordCalls = 0;
  let holdRecords = false;
  let releaseHold: () => void = () => undefined;
  let onConnection: ((connected: boolean) => void) | null = null;

  const source: ShellDataSource = {
    origin: "real-api",
    enterSession: async () => session,
    getSession: async () => session,
    ensureThread: async () => thread,
    listMessages: async () => messages.slice(),
    listTasks: async () => tasks.slice(),
    getTask: async (taskId) => tasks.find((item) => item.task.task_id === taskId) ?? Promise.reject(new ApiError(404, "NOT_FOUND", "没有这项任务")),
    listTaskRecords: async (taskId) => {
      recordCalls += 1;
      if (holdRecords) {
        holdRecords = false;
        await new Promise<void>((resolve) => {
          releaseHold = resolve;
        });
      }
      const failure = recordFailures.get(taskId);
      if (failure) throw failure;
      return records.get(taskId) ?? { task_id: taskId, confirmations: [], verifications: [] };
    },
    sendMessage: async () => Promise.reject(new ApiError(500, "UNUSED", "unused")),
    provideInput: async () => Promise.reject(new ApiError(500, "UNUSED", "unused")),
    reviseDraft: async () => Promise.reject(new ApiError(500, "UNUSED", "unused")),
    resumeTask: async () => Promise.reject(new ApiError(500, "UNUSED", "unused")),
    cancelTask: async () => Promise.reject(new ApiError(500, "UNUSED", "unused")),
    queryResult: async () => Promise.reject(new ApiError(500, "UNUSED", "unused")),
    getConfirmation: async () => Promise.reject(new ApiError(404, "NOT_FOUND", "没有确认单")),
    answerConfirmation: async () => Promise.reject(new ApiError(500, "UNUSED", "unused")),
    getVerification: async () => Promise.reject(new ApiError(404, "NOT_FOUND", "没有验证")),
    submitCode: async () => Promise.reject(new ApiError(500, "UNUSED", "unused")),
    resendCode: async () => Promise.reject(new ApiError(500, "UNUSED", "unused")),
    getDemoCode: async () => Promise.reject(new ApiError(500, "UNUSED", "unused")),
    startFace: async () => Promise.reject(new ApiError(500, "UNUSED", "unused")),
    subscribe(_threadId, _onEvent: (event: ShellEvent) => void, connection: (connected: boolean) => void) {
      onConnection = connection;
      connection(true);
      return () => connection(false);
    },
  };

  return {
    source,
    messages,
    tasks,
    records,
    recordFailures,
    reconnect() {
      onConnection?.(false);
      onConnection?.(true);
    },
    holdNextRecords() {
      holdRecords = true;
    },
    releaseRecords() {
      releaseHold();
    },
    recordCalls: () => recordCalls,
  };
}

afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe("shell recovery from server records", () => {
  it("keeps the page usable when one task history request fails", async () => {
    const harness = sourceHarness();
    harness.messages.push(message("给妈妈转五百", ["task-ok"]));
    harness.tasks.push({ task: task("task-ok", "succeeded"), module: "transfer" }, { task: task("task-down", "succeeded", 2), module: "transfer" });
    harness.records.set("task-ok", { task_id: "task-ok", confirmations: [confirmation("task-ok")], verifications: [] });
    harness.recordFailures.set("task-down", new ApiError(503, "UPSTREAM_UNAVAILABLE", "银行暂时不可用"));

    render(<AssistantPage source={harness.source} slots={slots} />);

    expect(await screen.findByText("给妈妈转五百")).toBeTruthy();
    expect(await screen.findByText("已确认办理 · 只读")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /已办结/ })).toHaveLength(2);
    const input = screen.getByRole("textbox", { name: "输入您想办的事" }) as HTMLInputElement;
    expect(input.disabled).toBe(false);
    expect(screen.queryByText(/银行暂时不可用/)).toBeNull();
  });

  it("merges confirmation history when the thread reconnects", async () => {
    const harness = sourceHarness();
    harness.messages.push(message("给妈妈转五百"));
    render(<AssistantPage source={harness.source} slots={slots} />);
    await screen.findByText("已连接");

    harness.messages.push(message("转账已完成", ["task-done"]));
    harness.tasks.push({ task: task("task-done", "succeeded"), module: "transfer" });
    harness.records.set("task-done", { task_id: "task-done", confirmations: [confirmation("task-done")], verifications: [] });
    harness.reconnect();

    expect(await screen.findByText("已确认办理 · 只读")).toBeTruthy();
    expect(screen.getByRole("button", { name: /已办结/ })).toBeTruthy();
  });

  it("does not stack another history reload while one reconnect is still reading records", async () => {
    const harness = sourceHarness();
    harness.tasks.push({ task: task("task-1", "succeeded"), module: "transfer" });
    render(<AssistantPage source={harness.source} slots={slots} />);
    await screen.findByRole("button", { name: /已办结/ });
    const afterBoot = harness.recordCalls();

    harness.holdNextRecords();
    harness.reconnect();
    await waitFor(() => expect(harness.recordCalls()).toBe(afterBoot + 1));
    harness.reconnect();
    await Promise.resolve();
    expect(harness.recordCalls()).toBe(afterBoot + 1);

    harness.releaseRecords();
    await waitFor(() => expect(harness.recordCalls()).toBe(afterBoot + 2));
  });

  it("shows the backend's Chinese explanation instead of raw recovery codes", async () => {
    const harness = sourceHarness();
    harness.messages.push(message("给妈妈转五百", ["task-paused"]));
    harness.tasks.push({
      task: {
        ...task("task-paused", "needs_attention"),
        message: "验证结果待核实，请使用原提交重试；这不是验证未通过。",
        error: {
          code: "DEPENDENCY_UNAVAILABLE",
          source: "bank",
          field: null,
          reason: "暂时无法核对验证结果。",
          upstream_code: null,
        },
        allowed_actions: ["resume", "cancel"],
        recovery_required: true,
        recovery_reason: "DEPENDENCY_UNAVAILABLE",
      },
      module: "transfer",
    });
    harness.tasks.push({
      task: {
        ...task("task-failed", "failed", 2),
        message: "这笔转账没有办成。",
        error: {
          code: "HIGH_RISK",
          source: "security",
          field: null,
          reason: "这笔转账已被安全规则终止，没有提交给银行。",
          upstream_code: null,
        },
      },
      module: "transfer",
    });

    render(<AssistantPage source={harness.source} slots={slots} />);

    expect(await screen.findByText("验证结果待核实，请使用原提交重试；这不是验证未通过。")).toBeTruthy();
    expect(await screen.findByText("这笔转账已被安全规则终止，没有提交给银行。")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "这项还没办完" })).toBeTruthy();
    expect(document.body.textContent).not.toContain("DEPENDENCY_UNAVAILABLE");
    expect(document.body.textContent).not.toContain("HIGH_RISK");
  });

  it("falls back to the error reason when a recovery task has no message copy", async () => {
    const harness = sourceHarness();
    harness.tasks.push({
      task: {
        ...task("task-no-message", "needs_attention"),
        message: "",
        error: {
          code: "OPERATION_UNKNOWN",
          source: "bank",
          field: null,
          reason: "暂时无法核对原转账结果。",
          upstream_code: null,
        },
        recovery_required: true,
        recovery_reason: "OPERATION_UNKNOWN",
      },
      module: "transfer",
    });

    render(<AssistantPage source={harness.source} slots={slots} />);

    expect(await screen.findByText("暂时无法核对原转账结果。")).toBeTruthy();
    expect(document.body.textContent).not.toContain("OPERATION_UNKNOWN");
  });
});

describe("real-api admin entry", () => {
  it("switches the administrator host and reuses the shared API mode", () => {
    expect(shellUsesContractDemo("contract-demo")).toBe(true);
    expect(shellUsesContractDemo("real-api")).toBe(false);
    expect(verificationAdminLabel("real-api")).toBe("打开独立管理员会话处理模拟人脸");
    expect(verificationAdminHref("task-1", "challenge-1", "round-1", "stub")).toBe(
      "/v04/admin?task_id=task-1&challenge_id=challenge-1&demo_round_id=round-1",
    );

    const href = verificationAdminHref("task-1", "challenge-1", "round-1", "real-api");
    const switched = window.location.hostname === "localhost" ? "127.0.0.1" : "localhost";
    expect(href.startsWith(window.location.protocol + "//" + switched)).toBe(true);
    expect(href).toContain("/admin?task_id=task-1&challenge_id=challenge-1&demo_round_id=round-1");
    expect(href.startsWith("/admin")).toBe(false);
  });
});
