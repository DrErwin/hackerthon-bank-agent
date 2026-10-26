import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AssistantPage } from "./AssistantPage";
import { createDemoBackend } from "./stub/demoBackend";
import { createSlotRegistry } from "./slots";
import { transferSlot } from "./slots/transferDemoSlot";
import type { ShellTask } from "./types";

beforeEach(() => { localStorage.clear(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

async function say(text: string) {
  const input = screen.getByRole("textbox", { name: "输入您想办的事" });
  await waitFor(() => expect(input.hasAttribute("disabled")).toBe(false));
  fireEvent.change(input, { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
}

it("mixes clicks, a side question and a spoken edit in one demo draft, requiring a fresh confirmation", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const confirm = vi.spyOn(backend.user, "answerConfirmation");
  render(<AssistantPage source={backend.user} slots={createSlotRegistry([transferSlot])} />);
  const starter = await screen.findByRole("button", { name: "给家人转一笔钱" });
  await waitFor(() => expect(starter.hasAttribute("disabled")).toBe(false));
  fireEvent.click(starter);
  fireEvent.change(await screen.findByLabelText("转账金额（元）"), { target: { value: "500" } });
  fireEvent.click(screen.getByRole("button", { name: "用这个金额" }));
  fireEvent.click(await screen.findByRole("button", { name: /演示账户.*1234/ }));
  fireEvent.click(await screen.findByRole("button", { name: /妈妈.*6688/ }));
  await screen.findByRole("button", { name: "确认办理" });
  const thread = await backend.user.ensureThread();
  const [original] = await backend.user.listTasks(thread.thread_id);
  const oldId = original.task.interaction!.record_ref!;

  await say("我还有多少余额？");
  expect(await screen.findByText(/您的演示账户尾号 1234，可用余额 1,000 元/)).toBeTruthy();
  await say("改成300元");
  await screen.findByText("金额改好了，请核对当前转账单。");
  const current = await backend.user.listTasks(thread.thread_id);
  expect(current).toHaveLength(1);
  expect(current[0].task.task_id).toBe(original.task.task_id);
  expect(current[0].task.data).toMatchObject({ amount_fen: 30000 });
  expect((await backend.user.getConfirmation(oldId)).decision).toBe("superseded");
  expect(screen.getAllByRole("button", { name: "确认办理" })).toHaveLength(1);
  expect(confirm).not.toHaveBeenCalled();
  expect(document.querySelectorAll(".sh-record")).toHaveLength(1);
  expect(screen.getByRole("textbox", { name: "输入您想办的事" })).toBeTruthy();
});

it("keeps an unfinished task reachable through history and returns focus to it", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  Element.prototype.scrollIntoView = vi.fn();
  render(<AssistantPage source={backend.user} slots={createSlotRegistry([transferSlot])} />);
  await say("转账500元");
  await screen.findByRole("button", { name: /演示账户.*1234/ });
  fireEvent.click(screen.getByRole("button", { name: "记录" }));
  const dialog = await screen.findByRole("dialog", { name: "办理记录" });
  fireEvent.click(within(dialog).getByRole("button", { name: "继续这项办理" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await waitFor(() => expect(document.activeElement?.getAttribute("data-task-id")).toBeTruthy());
});

it("opens folded groups when continuing a nested task, and opens finished records from history", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  Element.prototype.scrollIntoView = vi.fn();
  await backend.user.enterSession({ request_id: "enter" });
  const thread = await backend.user.ensureThread();
  const base: ShellTask = { task_id: "list", run_id: "run", module: "subscription", status: "succeeded",
    data: null, message: "已查询", interaction: null, error: null, allowed_actions: [], recovery_required: false,
    recovery_reason: null, thread_id: thread.thread_id, demo_round_id: "round", snapshot_at: "2026-10-26T01:00:00Z", task_revision: 1, cancel_requested: false };
  const parent: ShellTask = { ...base, data: { action: "list", list_result: { active_count: 1, upcoming_total_fen: 2500,
    as_of: base.snapshot_at, items: [{ subscription_id: "music", service_name: "音乐会员", merchant_name: "音乐", amount_fen: 2500,
      cycle: "monthly", account_masked: "****1234", status: "active", source_type: "mandate", can_cancel_in_bank: true }] } } };
  const child: ShellTask = { ...base, task_id: "stop", status: "waiting_input", allowed_actions: ["provide_input"],
    interaction: { interaction_id: "choice", kind: "input", prompt: "请选择", required_fields: [], options: [{ id: "continue", label: "继续退订" }], record_ref: null } };
  const finished: ShellTask = { ...base, task_id: "old", module: "transfer", status: "cancelled", data: { amount_fen: 80000 }, snapshot_at: "2026-10-25T01:00:00Z" };
  const source = { ...backend.user, listTasks: vi.fn().mockResolvedValue([finished, parent, child].map((task) => ({ task, module: task.module }))),
    listTaskRecords: vi.fn().mockImplementation(async (task_id: string) => ({ task_id, confirmations: [], verifications: [] })),
    cardAction: vi.fn() };
  localStorage.setItem("fe-card-links:" + thread.thread_id, JSON.stringify([{ parentId: "list", childId: "stop", revision: 1, selection: { action: "subscription_cancel", subscription_id: "music" } }]));
  const page = render(<AssistantPage source={source} slots={createSlotRegistry([transferSlot])} />);
  const group = (await screen.findByText("正在扣费（1）")).closest("details")!;
  fireEvent.click(group.querySelector("summary")!);
  expect(group.open).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: /待查看.*查看进度/ }));
  await waitFor(() => expect(group.open).toBe(true));
  expect(document.activeElement?.id).toBe("task-stop");

  expect(document.getElementById("record-old")?.hidden).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "记录" }));
  const dialog = await screen.findByRole("dialog", { name: "办理记录" });
  const item = within(dialog).getByRole("heading", { name: "转账办理 · 800.00 元" }).closest("li")!;
  fireEvent.click(within(item).getByRole("button", { name: "查看这项记录" }));
  await waitFor(() => expect(document.getElementById("record-old")?.hidden).toBe(false));
  await waitFor(() => expect(document.activeElement?.id).toBe("task-old"));
  expect(screen.getByText("¥800.00")).toBeTruthy();
  page.unmount();
  // A reload after the nested action finishes keeps one root history entry.
  // Opening the cached child from that entry must not make a new business call.
  source.listTasks.mockResolvedValue([finished, parent, { ...child, status: "cancelled", interaction: null, allowed_actions: [] }].map((task) => ({ task, module: task.module })));
  render(<AssistantPage source={source} slots={createSlotRegistry([transferSlot])} />);
  await screen.findByText("正在扣费（1）");
  fireEvent.click(screen.getByRole("button", { name: "记录" }));
  const refreshedHistory = await screen.findByRole("dialog", { name: "办理记录" });
  expect(within(refreshedHistory).queryByRole("heading", { name: "退订办理" })).toBeNull();
  const parentItem = within(refreshedHistory).getByRole("heading", { name: "订阅和自动扣费" }).closest("li")!;
  fireEvent.click(within(parentItem).getByRole("button", { name: "查看这项记录" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  fireEvent.click(screen.getByRole("button", { name: "取消「音乐会员」" }));
  await waitFor(() => expect(document.getElementById("task-stop")).toBeTruthy());
  expect(source.cardAction).not.toHaveBeenCalled();
});
