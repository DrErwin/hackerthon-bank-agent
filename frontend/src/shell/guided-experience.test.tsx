import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { GuidedTransfer } from "./components/GuidedTransfer";
import { AssistantPage } from "./AssistantPage";
import { createDemoBackend } from "./stub/demoBackend";
import { createSlotRegistry } from "./slots";
import { transferSlot } from "./slots/transferDemoSlot";
import { useConversation } from "./useConversation";
import type { ShellTask } from "./types";
import { ApiError } from "../api";
import { billPeriod } from "./components/BusinessCards";

const task: ShellTask = {
  task_id: "draft", run_id: "run", module: "transfer", status: "waiting_input",
  data: { amount_fen: 50000, payer_account_id: "A1", payee: null, operation: null, operation_id: null },
  message: "请选择收款人", interaction: { interaction_id: "input", kind: "input", required_fields: ["payee_hint"], options: [], prompt: "请选择收款人", record_ref: null },
  error: null, allowed_actions: ["provide_input", "cancel"], recovery_required: false, recovery_reason: null,
  thread_id: "thread", demo_round_id: "round", snapshot_at: "2026-10-23T00:00:00Z", task_revision: 1, cancel_requested: false,
};
beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("shows masked choices and updates the same draft without sending a chat message", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.listTasks = vi.fn().mockResolvedValue([{ task, module: "transfer" }]);
  backend.user.reviseDraft = vi.fn().mockResolvedValue({ ...task, task_revision: 2 });
  const hook = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(hook.result.current.booting).toBe(false));
  const send = vi.spyOn(backend.user, "sendMessage");
  render(<GuidedTransfer task={task} conversation={hook.result.current} busy={false} />);
  const choice = await screen.findByRole("button", { name: /妈妈.*6688/ });
  expect(screen.getByText("¥500.00")).toBeTruthy();
  fireEvent.click(choice);
  await waitFor(() => expect(backend.user.reviseDraft).toHaveBeenCalledWith("draft",
    expect.objectContaining({ task_revision: 1, payee_id: expect.any(String) })));
  expect(send).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("查找已保存的收款人"), { target: { value: "没有这个人" } });
  expect(screen.getByText(/没有匹配的收款人/)).toBeTruthy();
});

it("keeps draft facts visible when discovery fails and lets the user retry", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.readTransferChoices = vi.fn().mockRejectedValue(new Error("offline"));
  const hook = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(hook.result.current.booting).toBe(false));
  render(<GuidedTransfer task={task} conversation={hook.result.current} busy={false} />);
  expect(await screen.findByText(/暂时没有读到账户和收款人/)).toBeTruthy();
  expect(screen.getByText("¥500.00")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
  await waitFor(() => expect(backend.user.readTransferChoices).toHaveBeenCalledTimes(4));
});

it("always sends a question to chat while a transfer is waiting for a recipient", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.listTasks = vi.fn().mockResolvedValue([{ task, module: "transfer" }]);
  const send = vi.spyOn(backend.user, "sendMessage");
  const field = vi.spyOn(backend.user, "provideInput");
  render(<AssistantPage source={backend.user} slots={createSlotRegistry([transferSlot])} />);
  const input = await screen.findByRole("textbox", { name: "输入您想办的事" });
  await waitFor(() => expect(input.hasAttribute("disabled")).toBe(false));
  fireEvent.change(input, { target: { value: "我有什么收款人？" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await waitFor(() => expect(send).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ text: "我有什么收款人？" })));
  expect(field).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: /语音示例/ })).toBeNull();
});

it("reports a failed status refresh rather than silently swallowing it", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const hook = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(hook.result.current.booting).toBe(false));
  backend.user.getTask = vi.fn().mockRejectedValue(new ApiError(0, "NETWORK_ERROR", "暂时连接不上"));
  await act(async () => { await hook.result.current.actions.refreshTask("draft"); });
  expect(hook.result.current.taskErrors.draft).toContain("暂时连接不上");
  expect(hook.result.current.taskNotices.draft).toBe("");
});

it("labels full-month ranges with their inclusive calendar dates", () => {
  expect(billPeriod("2026-09-01T00:00:00+08:00", "2026-10-01T00:00:00+08:00")).toBe("2026/9/1 至 2026/9/30");
});
