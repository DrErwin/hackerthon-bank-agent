import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { MessageView } from "../contracts";
import { buildTimeline, type CardLink } from "./presentation";
import type { ShellTask, TaskEnvelope } from "./types";
import { BillDetailsCard, BusinessCards } from "./components/BusinessCards";
import { DetailsDrawer } from "./components/DetailsDrawer";
import { TaskRecord } from "./components/TaskRecord";
import { createDemoBackend } from "./stub/demoBackend";
import { useConversation } from "./useConversation";

const task: ShellTask = {
  task_id: "parent", run_id: "run", status: "succeeded", data: null, message: "已查询",
  interaction: null, error: null, allowed_actions: [], recovery_required: false, recovery_reason: null,
  module: "bills", thread_id: "thread", demo_round_id: "round", snapshot_at: "2026-10-22T02:00:00Z",
  task_revision: 3, cancel_requested: false,
};
const envelope = (value: ShellTask): TaskEnvelope => ({ task: value, module: value.module ?? null });
const msg = (id: string, time: string, ids: string[] = [], role: MessageView["role"] = "assistant"): MessageView => ({
  message_id: id, thread_id: "thread", role, text: id, created_at: "2026-10-22T" + time + "Z", task_ids: ids, report_ids: [],
});
beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("keeps a task at its first reply and nests only explicitly linked card results", () => {
  const child = { ...task, task_id: "child", snapshot_at: "2026-10-22T04:00:00Z" };
  const legacy = { ...task, task_id: "legacy", snapshot_at: "2026-10-22T02:30:00Z" };
  const tasks = new Map([task, child, legacy].map((value) => [value.task_id, envelope(value)]));
  const messages = [msg("first", "01:00:00", ["parent"]), msg("unrelated", "03:00:00", [], "user"), msg("later", "05:00:00", ["parent"])];
  const links: CardLink[] = [{ parentId: "parent", childId: "child", revision: 3, selection: { action: "bill_check" } }];
  const timeline = buildTimeline(messages, tasks, links);
  expect(timeline.map((item) => item.type === "task" ? item.envelope.task.task_id : item.message.message_id)).toEqual(["parent", "legacy", "unrelated"]);
  expect(timeline[0].type === "task" && timeline[0].messages.map((item) => item.text)).toEqual(["first", "later"]);
  expect(buildTimeline(messages, tasks).some((item) => item.type === "task" && item.envelope.task.task_id === "child")).toBe(true);
});

it("folds old results but keeps pending and failed child work visible", () => {
  const view = render(<TaskRecord task={task} messages={[]} latest={false}><button>查看明细</button></TaskRecord>);
  expect(screen.queryByRole("button", { name: "查看明细" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /展开/ }));
  expect(screen.getByRole("button", { name: "查看明细" })).toBeTruthy();
  view.rerender(<TaskRecord task={task} messages={[]} latest={false} hasActiveChild><button>确认办理</button></TaskRecord>);
  expect(screen.getByRole("button", { name: "确认办理" })).toBeTruthy();
  expect(screen.getByRole("button", { name: /已办结/ }).hasAttribute("disabled")).toBe(true);
});

it("reuses persisted card relationships after refresh without creating another child", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const child = { ...task, task_id: "child" };
  backend.user.listTasks = vi.fn().mockResolvedValue([envelope(task), envelope(child)]);
  backend.user.listTaskRecords = vi.fn().mockResolvedValue({ task_id: "parent", confirmations: [], verifications: [] });
  backend.user.cardAction = vi.fn().mockResolvedValue(child);
  const first = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(first.result.current.booting).toBe(false));
  await act(async () => { await first.result.current.actions.cardAction(task, { action: "bill_check" }); });
  expect(first.result.current.cardLinks).toHaveLength(1);
  first.unmount();
  const second = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(second.result.current.booting).toBe(false));
  expect(second.result.current.cardLinks[0]?.childId).toBe("child");
  await act(async () => { expect(await second.result.current.actions.cardAction(task, { action: "bill_check" })).toBe("child"); });
  expect(backend.user.cardAction).toHaveBeenCalledTimes(1);
});

it("opens a restored subscription confirmation in the selected row without a new action", () => {
  const onAction = vi.fn();
  render(<BusinessCards task={{ ...task, data: { action: "list", list_result: {
    active_count: 1, upcoming_total_fen: 2500, as_of: task.snapshot_at, items: [{ subscription_id: "music", service_name: "音乐会员", merchant_name: "音乐", amount_fen: 2500,
      cycle: "monthly", account_masked: "****1234", status: "active", source_type: "mandate", can_cancel_in_bank: true }],
  } } }} busy={false} enabled onAction={onAction}
    links={[{ parentId: "parent", childId: "child", revision: 3, selection: { action: "subscription_cancel", subscription_id: "music" } }]}
    activeChildren={["child"]} renderChild={() => <button>确认退订音乐会员</button>} />);
  expect(screen.getByRole("button", { name: "确认退订音乐会员" }).closest(".sh-business-row")?.textContent).toContain("音乐会员");
  expect(onAction).not.toHaveBeenCalled();
});

it("opens long details in a dialog and returns focus to the same trigger after closing", () => {
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new Event("close")); };
  render(<DetailsDrawer title="查看全部明细"><p>第十笔账单</p></DetailsDrawer>);
  expect(screen.queryByText("第十笔账单")).toBeNull();
  const trigger = screen.getByRole("button", { name: "查看全部明细" });
  fireEvent.click(trigger);
  expect(screen.getByRole("dialog", { name: "查看全部明细" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "关闭详情" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(trigger);
});

it("keeps category, direction and bank amount available in an unfiltered transaction list", () => {
  const common = { account_id: "A1", occurred_at: task.snapshot_at, nature: "consumption", direction: "outflow",
    counterparty_account_masked: "****1234", summary: "银行返回的说明" };
  render(<BillDetailsCard demo={false} task={{ ...task, data: { scope: {}, category: null, as_of: task.snapshot_at, transactions: [
    { ...common, transaction_id: "a", counterparty_name: "社区食堂", amount_fen: 3200, category: "dining" },
    { ...common, transaction_id: "b", counterparty_name: "社区药房", amount_fen: 11300, category: "medical" },
  ] } }} />);
  expect(screen.getByText("¥32.00")).toBeTruthy();
  expect(screen.getByText("¥113.00")).toBeTruthy();
  expect(screen.getAllByText("消费 · 支出")).toHaveLength(2);
  const dining = screen.getByText("分类：餐饮").closest("details")!;
  const medical = screen.getByText("分类：医疗").closest("details")!;
  expect(dining.open).toBe(false);
  expect(medical.open).toBe(false);
  fireEvent.click(dining.querySelector("summary")!);
  expect(dining.open).toBe(true);
  expect(dining.textContent).toContain("银行返回的说明");
  expect(dining.textContent).toContain("****1234");
});
