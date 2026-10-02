import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import App from "./App";
import TaskCard from "./TaskCard";
import { getPageItems } from "./pagination";
import type { SessionView, StreamEvent, TaskView, ThreadView, VerificationView } from "./contracts";

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    API_MODE: "real-api",
    get: vi.fn(actual.get),
    post: vi.fn(actual.post),
    connectToThread: vi.fn((
      _threadId: string,
      _onEvent: (event: StreamEvent) => void,
      onConnection: (connected: boolean) => void,
    ) => {
      onConnection(true);
      return () => undefined;
    }),
    hasEnteredDemo: vi.fn(() => true),
    markEnteredDemo: vi.fn(),
  };
});

const timestamp = "2026-10-01T00:00:00.000Z";
const session: SessionView = {
  session_id: "session-1",
  user_display: "演示用户",
  role: "user",
  demo_round_id: "round-1",
  created_at: timestamp,
  expires_at: "2026-10-01T02:00:00.000Z",
};
const threads: ThreadView[] = [
  { thread_id: "thread-a", title: "对话 A", created_at: timestamp, updated_at: timestamp, demo_round_id: "round-1" },
  { thread_id: "thread-b", title: "对话 B", created_at: timestamp, updated_at: timestamp, demo_round_id: "round-1" },
];

function makeTask(overrides: Partial<TaskView>): TaskView {
  return {
    task_id: "task-1",
    run_id: "run-1",
    status: "running",
    data: null,
    message: "测试任务",
    interaction: null,
    error: null,
    allowed_actions: [],
    recovery_required: false,
    recovery_reason: null,
    thread_id: "thread-a",
    demo_round_id: "round-1",
    snapshot_at: timestamp,
    task_revision: 1,
    cancel_requested: false,
    ...overrides,
  } as TaskView;
}

function makeTaskCardProps(task: TaskView) {
  return {
    task,
    onTask: vi.fn(),
    onRefresh: vi.fn(async () => undefined),
    onError: vi.fn(),
    onSessionExpired: vi.fn(),
    onModifyDraft: vi.fn(),
  };
}

beforeEach(() => {
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
  vi.mocked(api.connectToThread).mockClear();
  vi.mocked(api.get).mockImplementation(async (path) => {
    if (path === "/session") return session as never;
    if (path === "/threads?limit=100") return { items: threads, next_cursor: null } as never;
    if (path.includes("/messages?limit=100")) return { items: [], next_cursor: null } as never;
    if (path.startsWith("/tasks?thread_id=")) return { items: [], next_cursor: null } as never;
    throw new Error("Unexpected GET " + path);
  });
  let requestSequence = 0;
  vi.stubGlobal("crypto", { randomUUID: () => "request-id-" + ++requestSequence });
  window.history.replaceState({}, "", "/");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("recovery and retry controls", () => {
  function codeTask(challengeId = "challenge-1") {
    return makeTask({ status: "waiting_approval", allowed_actions: ["verify"], interaction: {
      interaction_id: challengeId, kind: "verification", prompt: "完成专用验证",
      required_fields: [], options: [], record_ref: challengeId,
    } });
  }

  const codeVerification = {
    challenge_id: "challenge-1", task_id: "task-1", summary: null,
    required_methods: ["code"], code_result: "pending", face_result: "pending",
    challenge_status: "pending", code_expires_at: timestamp, face_started_at: null,
    face_expires_at: null, consecutive_code_failures: 0,
  } as VerificationView;

  it("submits a code once while waiting and queries after a lost response without replaying it", async () => {
    vi.mocked(api.get).mockImplementation(async (path) =>
      path.startsWith("/verifications/") ? codeVerification as never : codeTask() as never);
    let rejectSubmission!: (error: unknown) => void;
    vi.mocked(api.post).mockImplementation(() => new Promise((_resolve, reject) => { rejectSubmission = reject; }));
    render(<TaskCard {...makeTaskCardProps(codeTask())} />);
    const input = await screen.findByLabelText("验证码（专用输入）");
    fireEvent.change(input, { target: { value: "123456" } });
    const form = input.closest("form")!;
    fireEvent.submit(form);
    fireEvent.change(input, { target: { value: "654321" } });
    fireEvent.submit(form);
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "提交中…" }).hasAttribute("disabled")).toBe(true);
    rejectSubmission(new api.ApiError(0, "NETWORK_ERROR", "响应丢失"));
    await screen.findByText(/验证码不会自动重传/);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/tasks/task-1"));
    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it("clears entered codes and demo hints when a new challenge replaces the old one", async () => {
    vi.mocked(api.get).mockImplementation(async (path) => path.endsWith("/demo-code")
      ? { code: "123456", expires_at: timestamp } as never : codeVerification as never);
    const props = makeTaskCardProps(codeTask());
    const view = render(<TaskCard {...props} />);
    fireEvent.change(await screen.findByLabelText("验证码（专用输入）"), { target: { value: "654321" } });
    fireEvent.click(screen.getByRole("button", { name: "打开模拟验证码提示区" }));
    await screen.findByText("123456");
    view.rerender(<TaskCard {...props} task={codeTask("challenge-2")} />);
    const input = await screen.findByLabelText("验证码（专用输入）");
    expect((input as HTMLInputElement).value).toBe("");
    expect(screen.queryByText("123456")).toBeNull();
  });

  it("ignores a delayed demo code from a previous challenge", async () => {
    let finishHint!: (value: never) => void;
    vi.mocked(api.get).mockImplementation(async (path) => path.endsWith("/demo-code")
      ? await new Promise<never>((resolve) => { finishHint = resolve; }) : codeVerification as never);
    const props = makeTaskCardProps(codeTask());
    const view = render(<TaskCard {...props} />);
    fireEvent.click(await screen.findByRole("button", { name: "打开模拟验证码提示区" }));
    view.rerender(<TaskCard {...props} task={codeTask("challenge-2")} />);
    await screen.findByLabelText("验证码（专用输入）");
    finishHint({ code: "123456", expires_at: timestamp } as never);
    await waitFor(() => expect(screen.queryByText("123456")).toBeNull());
  });

  it("keeps delayed history from a previous thread out of the selected conversation", async () => {
    let finishOldHistory!: (value: never) => void;
    const defaultGet = vi.mocked(api.get).getMockImplementation()!;
    vi.mocked(api.get).mockImplementation(async (path) => {
      if (path === "/threads/thread-b/messages?limit=100") {
        return await new Promise<never>((resolve) => { finishOldHistory = resolve; });
      }
      return defaultGet(path);
    });
    render(<App />);
    await screen.findByRole("textbox", { name: "输入聊天内容" });
    await waitFor(() => expect(finishOldHistory).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /对话 A/ }));
    finishOldHistory({ items: [{ message_id: "old-message", thread_id: "thread-b", role: "assistant", text: "旧对话内容", created_at: timestamp }], next_cursor: null } as never);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/threads/thread-a/messages?limit=100"));
    expect(screen.queryByText("旧对话内容")).toBeNull();
  });

  it("allows editing a definitively rejected chat message", async () => {
    vi.mocked(api.post).mockRejectedValue(new api.ApiError(400, "USE_VERIFICATION_ENDPOINT", "请使用专用验证入口"));
    render(<App />);
    const input = await screen.findByRole("textbox", { name: "输入聊天内容" });
    fireEvent.change(input, { target: { value: "123456" } });
    fireEvent.submit(screen.getByRole("button", { name: "发送" }).closest("form")!);
    await screen.findByText("请使用专用验证入口");
    expect(input.hasAttribute("disabled")).toBe(false);
    fireEvent.change(input, { target: { value: "你好" } });
    expect((input as HTMLTextAreaElement).value).toBe("你好");
  });

  it("loads remaining pages with the server cursor", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ items: ["first"], next_cursor: "next/page" } as never)
      .mockResolvedValueOnce({ items: ["latest"], next_cursor: null } as never);
    expect(await getPageItems<string>("/threads?limit=100")).toEqual(["first", "latest"]);
    expect(api.get).toHaveBeenLastCalledWith("/threads?limit=100&cursor=next%2Fpage");
  });

  it("refreshes the same verification challenge when the task snapshot changes", async () => {
    const task = makeTask({ status: "waiting_approval", allowed_actions: ["verify"], interaction: {
      interaction_id: "interaction-1", kind: "verification", prompt: "完成专用验证",
      required_fields: [], options: [], record_ref: "challenge-1",
    } });
    const verification = {
      challenge_id: "challenge-1", required_methods: ["mock_face"],
      face_started_at: timestamp, face_result: "pending", challenge_status: "pending",
    } as VerificationView;
    vi.mocked(api.get).mockResolvedValueOnce(verification as never)
      .mockResolvedValueOnce({ ...verification, face_result: "passed" } as never);
    const props = makeTaskCardProps(task);
    const view = render(<TaskCard {...props} />);
    await screen.findByText("等待管理员处理");
    view.rerender(<TaskCard {...props} task={{ ...task, task_revision: 2 }} />);
    await screen.findByText("已通过");
    expect(screen.queryByText("等待管理员处理")).toBeNull();
  });

  it("retries an unknown chat send only in its original thread with the same request id", async () => {
    const requests: Array<{ path: string; body: Record<string, unknown> }> = [];
    vi.mocked(api.post).mockImplementation(async (path, body) => {
      if (path.endsWith("/messages")) {
        requests.push({ path, body });
        if (requests.length === 1) throw new api.ApiError(0, "NETWORK_ERROR", "模拟网络中断");
        return { message_id: "message-1", thread_id: "thread-b", accepted_at: timestamp, task_id: null } as never;
      }
      throw new Error("Unexpected POST " + path);
    });

    render(<App />);
    const input = await screen.findByRole("textbox", { name: "输入聊天内容" });
    fireEvent.change(input, { target: { value: "你好" } });
    fireEvent.submit(screen.getByRole("button", { name: "发送" }).closest("form")!);
    await screen.findByRole("button", { name: "重试同一请求" });

    fireEvent.click(screen.getByRole("button", { name: /对话 A/ }));
    const blockedRetry = await screen.findByRole("button", { name: "切回原对话重试" });
    expect(blockedRetry.hasAttribute("disabled")).toBe(true);
    expect(await screen.findByText(/上一条消息结果尚未确定，属于“对话 B”/)).toBeTruthy();
    expect(requests).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: /对话 B/ }));
    fireEvent.click(await screen.findByRole("button", { name: "重试同一请求" }));
    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests.map((request) => request.path)).toEqual([
      "/threads/thread-b/messages",
      "/threads/thread-b/messages",
    ]);
    expect(requests[0].body.request_id).toBe(requests[1].body.request_id);
  });

  it("offers explicit resume for a server-marked recovery task and keeps old verification actions disabled", async () => {
    const task = makeTask({
      status: "waiting_approval",
      interaction: {
        interaction_id: "interaction-1",
        kind: "verification",
        prompt: "完成专用验证",
        required_fields: [],
        options: [],
        record_ref: "challenge-1",
      },
      recovery_required: true,
      recovery_reason: "SESSION_RECONFIRMATION_REQUIRED",
    });
    const verification: VerificationView = {
      challenge_id: "challenge-1",
      task_id: task.task_id,
      summary: null,
      required_methods: ["code", "mock_face"],
      code_expires_at: "2026-10-01T00:05:00.000Z",
      face_started_at: null,
      face_expires_at: null,
      code_result: "pending",
      face_result: "pending",
      challenge_status: "pending",
      consecutive_code_failures: 0,
    } as VerificationView;
    const props = makeTaskCardProps(task);
    vi.mocked(api.get).mockResolvedValue(verification as never);
    vi.mocked(api.post).mockResolvedValue(makeTask({ task_revision: 2 }) as never);

    render(<TaskCard {...props} />);
    expect(await screen.findByRole("heading", { name: "专用验证" })).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: "验证码（专用输入）" })).toBeNull();
    expect(screen.queryByRole("button", { name: "开始模拟人脸等待" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "恢复原任务" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/tasks/task-1/resume", expect.objectContaining({ request_id: expect.any(String) })));
  });

  it("does not offer modify when the server permits confirmation but not cancellation", async () => {
    const task = makeTask({
      status: "waiting_approval",
      allowed_actions: ["confirm"],
      interaction: {
        interaction_id: "interaction-1",
        kind: "confirmation",
        prompt: "核对确认单",
        required_fields: [],
        options: [],
        record_ref: "confirmation-1",
      },
    });
    vi.mocked(api.get).mockResolvedValue({
      confirmation_id: "confirmation-1",
      task_id: task.task_id,
      confirmation_version: 1,
      display_fields: [],
      created_at: timestamp,
      expires_at: "2026-10-01T00:05:00.000Z",
      decision: "pending",
    } as never);

    render(<TaskCard {...makeTaskCardProps(task)} />);
    expect(await screen.findByRole("button", { name: "确认办理" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "修改" })).toBeNull();
  });
});
