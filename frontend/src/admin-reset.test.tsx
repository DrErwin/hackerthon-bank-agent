import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import AdminPage from "./AdminPage";
import type { ManagementOperation, ResetPreview, SessionView } from "./contracts";

const mode = vi.hoisted(() => ({ value: "real-api" }));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, get API_MODE() { return mode.value; }, get: vi.fn(), post: vi.fn() };
});

const session: SessionView = {
  session_id: "admin-session", user_display: "演示管理员", role: "admin", demo_round_id: "D1",
  created_at: "2026-10-27T00:00:00Z", expires_at: "2026-10-27T02:00:00Z",
};
const preview: ResetPreview = {
  reset_confirmation_id: "reset-confirmation-1", demo_round_id: "D1",
  effects: ["后端实际影响甲：停止新业务。", "后端实际影响乙：恢复种子数据。"],
};
const operation: ManagementOperation = {
  management_operation_id: "management-1", kind: "reset", status: "running",
  source_round_id: "D1", resulting_round_id: null, phase: "waiting_inflight", error: null,
};

beforeEach(() => {
  mode.value = "real-api";
  localStorage.clear();
  vi.mocked(api.get).mockReset().mockResolvedValue(session);
  vi.mocked(api.post).mockReset();
  let sequence = 0;
  vi.stubGlobal("crypto", { randomUUID: () => "00000000-0000-4000-8000-" + String(++sequence).padStart(12, "0") });
  window.history.replaceState({}, "", "/admin");
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

async function openPreview() {
  vi.mocked(api.post).mockResolvedValueOnce(preview);
  fireEvent.click(await screen.findByRole("button", { name: "查看重置影响" }));
  await screen.findByText(preview.effects[0]);
}

function confirmReset() {
  fireEvent.click(screen.getByRole("checkbox", { name: "我已核对以上影响，确认重置本轮演示" }));
  fireEvent.click(screen.getByRole("button", { name: "确认并重置本轮演示" }));
}

describe("administrator demo reset", () => {
  it("shows the server's effects and sends no reset before a second confirmation", async () => {
    render(<AdminPage />);
    await openPreview();
    expect(screen.getByText(preview.effects[1])).toBeTruthy();
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(api.post).toHaveBeenCalledWith("/admin/demo/reset-preview", {
      request_id: "00000000-0000-4000-8000-000000000001", demo_round_id: "D1",
    });
    expect(screen.getByRole("checkbox", { name: "我已核对以上影响，确认重置本轮演示" })).toBeTruthy();
    expect(screen.queryByText(/新轮次/)).toBeNull();
  });

  it("requires the explicit checkbox even if a form is submitted directly", async () => {
    render(<AdminPage />);
    await openPreview();
    const checkbox = screen.getByRole("checkbox", { name: "我已核对以上影响，确认重置本轮演示" });
    fireEvent.submit(checkbox.closest("form")!);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(document.activeElement).toBe(checkbox);
    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it("prevents duplicate submissions and queries running progress without another POST", async () => {
    render(<AdminPage />);
    await openPreview();
    let finish!: (value: ManagementOperation) => void;
    vi.mocked(api.post).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    confirmReset();
    fireEvent.click(screen.getByRole("button", { name: "按原请求找回并继续重置" }));
    expect(api.post).toHaveBeenCalledTimes(2);
    expect(api.post).toHaveBeenLastCalledWith("/admin/demo/reset", {
      request_id: "00000000-0000-4000-8000-000000000002", reset_confirmation_id: preview.reset_confirmation_id,
    });
    finish(operation);
    await screen.findByText("重置进行中，尚未完成");
    expect(screen.queryByRole("button", { name: "查看重置影响" })).toBeNull();
    expect(screen.queryByText(/新轮次/)).toBeNull();
    vi.mocked(api.get).mockResolvedValueOnce(operation);
    fireEvent.click(screen.getByRole("button", { name: "只读查询重置进度" }));
    await waitFor(() => expect(api.get).toHaveBeenLastCalledWith("/admin/operations/management-1"));
    await waitFor(() => expect(screen.getByRole("button", { name: "继续同一次重置" }).hasAttribute("disabled")).toBe(false));
    expect(api.post).toHaveBeenCalledTimes(2);
  });

  it("keeps partial failure and its stage, then continues the exact original reset request", async () => {
    render(<AdminPage />);
    await openPreview();
    vi.mocked(api.post).mockResolvedValueOnce({
      ...operation, status: "failed", phase: "resetting_memory", resulting_round_id: "not-yet-published",
      error: { code: "RESET_INCOMPLETE", source: "platform", field: null, reason: "记忆恢复未完成，请沿原请求继续。", upstream_code: null },
    });
    confirmReset();
    await screen.findByText("重置未完成");
    expect(screen.getByText(/记忆恢复未完成/)).toBeTruthy();
    expect(screen.getByText(/恢复预置记忆/)).toBeTruthy();
    expect(screen.queryByText(/新轮次/)).toBeNull();
    expect(screen.queryByRole("link", { name: "重新进入用户页" })).toBeNull();
    const originalRequest = vi.mocked(api.post).mock.calls[1][1];
    vi.mocked(api.post).mockResolvedValueOnce({ ...operation, status: "succeeded", phase: "completed", resulting_round_id: "D2" });
    fireEvent.click(screen.getByRole("button", { name: "继续同一次重置" }));
    await screen.findByText("重置已全部完成");
    expect(api.post).toHaveBeenLastCalledWith("/admin/demo/reset", originalRequest);
    expect(screen.getByText(/新轮次/).textContent).toContain("D2");
    expect(screen.getByRole("link", { name: "重新进入用户页" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "查看当前轮次的重置影响" })).toBeNull();
  });

  it("restores a lost-response request after reload and never submits automatically", async () => {
    const view = render(<AdminPage />);
    await openPreview();
    vi.mocked(api.post).mockRejectedValueOnce(new api.ApiError(0, "NETWORK_ERROR", "响应丢失"));
    confirmReset();
    await screen.findByText("响应丢失");
    const originalRequest = vi.mocked(api.post).mock.calls[1][1];
    view.unmount();
    render(<AdminPage />);
    const recover = await screen.findByRole("button", { name: "按原请求找回并继续重置" });
    expect(api.post).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("button", { name: "查看重置影响" })).toBeNull();
    vi.mocked(api.post).mockResolvedValueOnce(operation);
    fireEvent.click(recover);
    await screen.findByText("重置进行中，尚未完成");
    expect(api.post).toHaveBeenLastCalledWith("/admin/demo/reset", originalRequest);
  });

  it("restores the original management number for read-only queries across a reload", async () => {
    const view = render(<AdminPage />);
    await openPreview();
    vi.mocked(api.post).mockResolvedValueOnce(operation);
    confirmReset();
    await screen.findByText("重置进行中，尚未完成");
    view.unmount();
    render(<AdminPage />);
    await screen.findByText("management-1");
    expect(api.post).toHaveBeenCalledTimes(2);
    vi.mocked(api.get).mockResolvedValueOnce(operation);
    fireEvent.click(screen.getByRole("button", { name: "只读查询重置进度" }));
    await waitFor(() => expect(api.get).toHaveBeenLastCalledWith("/admin/operations/management-1"));
    expect(api.post).toHaveBeenCalledTimes(2);
  });

  it("reuses the preview request after a read failure and allows cancelling before reset", async () => {
    render(<AdminPage />);
    vi.mocked(api.post).mockRejectedValueOnce(new api.ApiError(503, "UNAVAILABLE", "预览暂不可用"));
    fireEvent.click(await screen.findByRole("button", { name: "查看重置影响" }));
    await screen.findByText("预览暂不可用");
    const originalRequest = vi.mocked(api.post).mock.calls[0][1];
    vi.mocked(api.post).mockResolvedValueOnce(preview);
    fireEvent.click(screen.getByRole("button", { name: "重试读取重置影响" }));
    await screen.findByText(preview.effects[0]);
    expect(api.post).toHaveBeenLastCalledWith("/admin/demo/reset-preview", originalRequest);
    fireEvent.click(screen.getByRole("button", { name: "暂不重置" }));
    expect(screen.getByRole("button", { name: "查看重置影响" })).toBeTruthy();
    expect(api.post).toHaveBeenCalledTimes(2);
  });

  it("does not send a reset when its original request cannot be saved", async () => {
    render(<AdminPage />);
    await openPreview();
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("storage unavailable"); });
    confirmReset();
    expect(await screen.findByText(/无法保存原管理请求，本次没有提交/)).toBeTruthy();
    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it("retains a request rejected by the server rather than starting a second reset", async () => {
    render(<AdminPage />);
    await openPreview();
    vi.mocked(api.post).mockRejectedValueOnce(new api.ApiError(409, "RESET_CONFLICT", "已有冲突管理操作"));
    confirmReset();
    await screen.findByText("已有冲突管理操作");
    expect(screen.getByRole("button", { name: "按原请求找回并继续重置" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "查看重置影响" })).toBeNull();
  });

  it("keeps the original request through administrator reauthentication", async () => {
    render(<AdminPage />);
    await openPreview();
    vi.mocked(api.post).mockRejectedValueOnce(new api.ApiError(401, "AUTH_REQUIRED", "会话已过期"));
    confirmReset();
    await screen.findByRole("heading", { name: "验证管理员身份" });
    vi.mocked(api.post).mockResolvedValueOnce({ ...session, session_id: "new-admin-session" });
    fireEvent.change(screen.getByLabelText("管理密钥"), { target: { value: "local-test-key" } });
    fireEvent.click(screen.getByRole("button", { name: "建立管理员会话" }));
    await screen.findByRole("button", { name: "按原请求找回并继续重置" });
    expect(screen.queryByRole("button", { name: "查看重置影响" })).toBeNull();
    expect(localStorage.getItem("bank-admin-demo-reset-v1")).not.toContain("local-test-key");
  });

  it("offers another preview only after entering the resulting round with a fresh admin session", async () => {
    const view = render(<AdminPage />);
    await openPreview();
    vi.mocked(api.post).mockResolvedValueOnce({ ...operation, status: "succeeded", phase: "completed", resulting_round_id: "D2" });
    confirmReset();
    await screen.findByText("重置已全部完成");
    view.unmount();
    vi.mocked(api.get).mockResolvedValueOnce({ ...session, demo_round_id: "D2", session_id: "admin-D2" });
    render(<AdminPage />);
    const nextPreview = await screen.findByRole("button", { name: "查看当前轮次的重置影响" });
    vi.mocked(api.post).mockResolvedValueOnce({ ...preview, demo_round_id: "D2", reset_confirmation_id: "confirmation-D2" });
    fireEvent.click(nextPreview);
    await screen.findByRole("checkbox");
    expect(api.post).toHaveBeenLastCalledWith("/admin/demo/reset-preview", {
      request_id: "00000000-0000-4000-8000-000000000003", demo_round_id: "D2",
    });
  });

  it("blocks a fresh reset if a saved record cannot be read", async () => {
    localStorage.setItem("bank-admin-demo-reset-v1", "broken record");
    render(<AdminPage />);
    await screen.findByText(/本机重置记录无法读取/);
    expect(screen.queryByRole("button", { name: "查看重置影响" })).toBeNull();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("does not expose the reset entry to a user session", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ...session, role: "user" });
    render(<AdminPage />);
    await screen.findByRole("heading", { name: "当前会话没有管理权限" });
    expect(screen.queryByRole("heading", { name: "演示整体重置" })).toBeNull();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("labels contract-demo as unavailable without simulating a real reset", async () => {
    mode.value = "contract-demo";
    render(<AdminPage />);
    await screen.findByText(/整体重置仅在真实 API 模式提供/);
    expect(screen.queryByRole("button", { name: "查看重置影响" })).toBeNull();
    expect(api.post).not.toHaveBeenCalled();
  });
});
