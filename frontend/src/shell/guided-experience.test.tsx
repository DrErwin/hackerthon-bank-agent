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
import { buildTimeline, type CardLink } from "./presentation";
import { TaskBlock } from "./components/TaskBlock";
import { genericSlot } from "./slots";

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

it("follows requested fields while a payee is not yet bank-verified", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const hook = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(hook.result.current.booting).toBe(false));
  const amountTask: ShellTask = { ...task, data: { amount_fen: null, payer_account_id: null, payee: null },
    interaction: { ...task.interaction!, required_fields: ["amount_fen"] } };
  const view = render(<GuidedTransfer task={amountTask} conversation={hook.result.current} busy={false} />);
  expect(screen.getByLabelText("转账金额（元）")).toBeTruthy();
  expect(screen.queryByLabelText("查找已保存的收款人")).toBeNull();
  view.rerender(<GuidedTransfer task={{ ...amountTask, data: { amount_fen: 50000, payer_account_id: null, payee: null },
    interaction: { ...task.interaction!, required_fields: ["payer_account_id"] } }} conversation={hook.result.current} busy={false} />);
  expect(await screen.findByRole("button", { name: /演示账户.*1234/ })).toBeTruthy();
  expect(screen.queryByLabelText("转账金额（元）")).toBeNull();
  expect(screen.getByText("¥500.00")).toBeTruthy();
});

it("retains draft facts and edit actions beside ambiguous payee choices", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const hook = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(hook.result.current.booting).toBe(false));
  const ambiguous: ShellTask = { ...task, interaction: { ...task.interaction!, required_fields: [],
    options: [{ id: "one", label: "张伟 · 尾号1234" }, { id: "two", label: "张伟 · 尾号5678" }] } };
  render(<TaskBlock envelope={{ task: ambiguous, module: "transfer" }} slot={genericSlot} origin="real-api"
    conversation={{ ...hook.result.current, history: { draft: [{ kind: "input", id: "input", interaction: ambiguous.interaction!, selectedLabel: null }] } }} />);
  expect(screen.getByText("¥500.00")).toBeTruthy();
  expect(screen.getByRole("button", { name: "修改金额" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "修改付款卡" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "张伟 · 尾号1234" })).toBeTruthy();
  expect(screen.queryByLabelText("查找已保存的收款人")).toBeNull();
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
  backend.user.getTask = vi.fn().mockResolvedValue({ task, module: "transfer" });
  await act(async () => { await hook.result.current.actions.refreshTask("draft"); });
  expect(hook.result.current.taskErrors.draft).toBe("");
  expect(hook.result.current.taskNotices.draft).toContain("已更新");
});

it("does not report a bank-level draft rejection as a successful edit", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.reviseDraft = vi.fn().mockResolvedValue({ ...task, task_revision: 2,
    error: { code: "PAYEE_MISMATCH", source: "bank", field: "payee_hint", reason: "收款资料未通过核验", upstream_code: null } });
  const hook = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(hook.result.current.booting).toBe(false));
  await act(async () => {
    expect(await hook.result.current.actions.reviseDraft(task, undefined, { payee_id: "stale" })).toBe(false);
  });
  expect(hook.result.current.taskErrors.draft).toBe("收款资料未通过核验");
  expect(hook.result.current.taskNotices.draft).not.toContain("已更新");
});

it("keeps repeated refreshes and their pending children in a single root record", () => {
  const tasks = new Map(["root", "refresh1", "refresh2", "cancel"].map((id) => [id, { task: { ...task, task_id: id }, module: "subscription" }]));
  const links: CardLink[] = [
    { parentId: "root", childId: "refresh1", selection: { action: "refresh_query" }, revision: 1 },
    { parentId: "refresh1", childId: "refresh2", selection: { action: "refresh_query" }, revision: 1 },
    { parentId: "refresh2", childId: "cancel", selection: { action: "subscription_cancel", subscription_id: "s" }, revision: 1 },
  ];
  expect(buildTimeline([], tasks, links).map((item) => item.type === "task" && item.envelope.task.task_id)).toEqual(["root"]);
});

it("queries the new month instead of reopening the previous month's cached category", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const hook = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(hook.result.current.booting).toBe(false));
  function bill(id: string, month: string): ShellTask {
    return { ...task, task_id: id, module: "bills", status: "succeeded", interaction: null, allowed_actions: [],
      data: { scope: { start_at: "2026-" + month + "-01T00:00:00+08:00", end_at: "2026-10-01T00:00:00+08:00", account_ids: ["A1"] },
        categories: [{ category: "dining", net_fen: 3000 }], transaction_count: 1, consumption_net_fen: 3000, as_of: task.snapshot_at } };
  }
  const sept = bill("september", "09"), aug = bill("august", "08");
  const cardAction = vi.fn().mockResolvedValue("september-details");
  const base = { ...hook.result.current, supportsCardActions: true, actions: { ...hook.result.current.actions, cardAction },
    tasks: new Map([[sept.task_id, { task: sept, module: "bills" }], [aug.task_id, { task: aug, module: "bills" }]]) };
  const view = render(<TaskBlock envelope={{ task: sept, module: "bills" }} slot={genericSlot} origin="real-api"
    conversation={base} renderChild={(id) => <p>{id}</p>} />);
  fireEvent.click(screen.getByText("换一个月份"));
  fireEvent.input(screen.getByLabelText("查询月份（沿用这些银行卡）"), { target: { value: "2026-08" } });
  fireEvent.click(screen.getByRole("button", { name: "查询这个月" }));
  expect(cardAction).toHaveBeenCalledWith(sept, { action: "bill_range", month: "2026-08" });
  fireEvent.click(screen.getByRole("button", { name: "查看餐饮明细" }));
  expect(await screen.findByText("september-details")).toBeTruthy();
  view.rerender(<TaskBlock envelope={{ task: sept, module: "bills" }} slot={genericSlot} origin="real-api"
    conversation={{ ...base, cardLinks: [{ parentId: sept.task_id, childId: aug.task_id, revision: 1, selection: { action: "bill_range", month: "2026-08" } }] }}
    renderChild={(id) => <p>{id}</p>} />);
  fireEvent.click(screen.getByRole("button", { name: "查看餐饮明细" }));
  await waitFor(() => expect(cardAction).toHaveBeenLastCalledWith(aug, { action: "bill_details", category: "dining" }));
  const pending = { ...task, task_id: "pending-check", module: "bills" as const };
  view.rerender(<TaskBlock envelope={{ task: sept, module: "bills" }} slot={genericSlot} origin="real-api"
    conversation={{ ...base, tasks: new Map([...base.tasks, [pending.task_id, { task: pending, module: "bills" }]]),
      cardLinks: [
        { parentId: sept.task_id, childId: aug.task_id, revision: 1, selection: { action: "bill_range", month: "2026-08" } },
        { parentId: sept.task_id, childId: pending.task_id, revision: 1, selection: { action: "bill_check" } },
      ] }}
    renderChild={(id) => id === pending.task_id ? <button id={"task-" + id}>继续原来的核对</button> : <p>{id}</p>} />);
  const continueButton = screen.getByRole("button", { name: "继续原来的核对" });
  expect(continueButton.closest("details")?.open).toBe(true);
});

it("labels full-month ranges with their inclusive calendar dates", () => {
  expect(billPeriod("2026-09-01T00:00:00+08:00", "2026-10-01T00:00:00+08:00")).toBe("2026/9/1 至 2026/9/30");
});
