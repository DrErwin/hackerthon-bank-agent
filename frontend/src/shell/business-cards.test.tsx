import { act, cleanup, fireEvent, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import type { SubscriptionTaskView } from "../contracts";
import { BusinessCards, BillCardActions } from "./components/BusinessCards";
import { TaskBlock } from "./components/TaskBlock";
import { genericSlot } from "./slots";
import { cardMessageSummary } from "./AssistantPage";
import { MessageBubble } from "./components/Chrome";
import { createDemoBackend } from "./stub/demoBackend";
import { createRealDataSource } from "./api/realDataSource";
import { useConversation } from "./useConversation";
import type { ShellTask } from "./types";

const task: ShellTask = {
  task_id: "source", run_id: "run", status: "succeeded", data: null, message: "已查询",
  interaction: null, error: null, allowed_actions: [], recovery_required: false, recovery_reason: null,
  module: "subscription", thread_id: "thread", demo_round_id: "round", snapshot_at: "2026-10-22T00:00:00Z",
  task_revision: 3, cancel_requested: false,
};
const item: NonNullable<SubscriptionTaskView["list_result"]>["items"][number] = {
  subscription_id: "first", source_type: "mandate", mandate_id: "sub_first", merchant_id: "merchant",
  merchant_name: "商户", service_name: "视频会员", amount_fen: 2500, cycle: "monthly", account_id: "A1",
  account_masked: "****1234", last_billed_at: null, next_billing_at: null, status: "active",
  can_cancel_in_bank: true, days_until_renewal: null, is_upcoming_renewal: false, external_cancel_guide: null,
};
const subscription: SubscriptionTaskView = { action: "list", list_result: {
  items: [item, { ...item, subscription_id: "second", service_name: "音乐会员", mandate_id: "sub_second" },
    { ...item, subscription_id: "suspected", service_name: "疑似扣款", source_type: "suspected_ledger",
      mandate_id: null, status: "suspected", can_cancel_in_bank: false },
    { ...item, subscription_id: "cancelled", service_name: "旧会员", status: "cancelled", can_cancel_in_bank: false }],
  upcoming_renewals: [], active_count: 2, upcoming_total_fen: 0, as_of: "2026-10-22T00:00:00Z",
  suspected_scan_status: "insufficient_data", suspected_scan_reason: "lookback_incomplete",
} };
beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("keeps the full subscription explanation available without duplicating it above the cards", () => {
  const message = { message_id: "m", thread_id: "thread", role: "assistant" as const,
    text: "完整查询说明", created_at: task.snapshot_at, task_ids: [task.task_id], report_ids: [] };
  const tasks = new Map([[task.task_id, { task: { ...task, data: subscription }, module: "subscription" }]]);
  render(<MessageBubble message={message} cardSummary={cardMessageSummary(message, tasks)} />);
  expect(screen.getByText("完整查询说明").closest("details")?.open).toBe(false);
  expect(cardMessageSummary({ ...message, task_ids: [] }, tasks)).toBeUndefined();
  expect(cardMessageSummary({ ...message, role: "user" }, tasks)).toBeUndefined();
});

it("groups subscriptions and binds the clicked row, with no action on suspected or cancelled rows", async () => {
  const onAction = vi.fn().mockResolvedValue("child");
  render(<BusinessCards task={{ ...task, data: subscription }} enabled busy={false} onAction={onAction} />);
  expect(within(screen.getByRole("region", { name: "疑似周期扣款" })).queryByRole("button")).toBeNull();
  expect(within(screen.getByRole("region", { name: "已退订" })).queryByRole("button")).toBeNull();
  const button = screen.getByRole("button", { name: "取消「音乐会员」" });
  button.focus();
  expect(document.activeElement).toBe(button);
  fireEvent.click(button);
  await screen.findByRole("link", { name: "查看已打开的办理" });
  expect(onAction).toHaveBeenCalledExactlyOnceWith({ action: "subscription_cancel", subscription_id: "second" });
  expect(screen.getByText("流水资料不足，疑似周期扣款尚未完整核对。")).toBeTruthy();
});

it("disables stale-session or busy controls and renders only the bank balance and masked account", () => {
  const onAction = vi.fn();
  const view = render(<BusinessCards task={{ ...task, data: subscription }} enabled busy onAction={onAction} />);
  for (const button of screen.getAllByRole("button")) {
    expect(button.hasAttribute("disabled")).toBe(true);
    fireEvent.click(button);
  }
  expect(onAction).not.toHaveBeenCalled();
  view.rerender(<BusinessCards task={{ ...task, data: { accounts: [{ account_id: "A1", display_name: "工资卡",
    bank_name: "模拟银行", account_masked: "****6789", available_balance_fen: 12345, account_type: "class_i" }] } }}
    enabled busy={false} onAction={onAction} />);
  expect(screen.getByText("¥123.45")).toBeTruthy();
  expect(screen.getByText("****6789")).toBeTruthy();
});

it("passes the chosen bill category without generating a chat prompt", async () => {
  const onAction = vi.fn().mockResolvedValue("detail");
  render(<BillCardActions task={{ ...task, data: { categories: [{ category: "dining" }, { category: "medical" }] } }}
    busy={false} onAction={onAction} />);
  fireEvent.click(screen.getByRole("button", { name: "查看医疗明细" }));
  await waitFor(() => expect(onAction).toHaveBeenCalledExactlyOnceWith({ action: "bill_details", category: "medical" }));
});

it("retries a lost card response with the same id, adds the child module and deduplicates subsequent clicks", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const child = { ...task, task_id: "child", module: "bills", recovery_required: true };
  const cardAction = vi.fn().mockRejectedValueOnce(new ApiError(503, "DEPENDENCY_UNAVAILABLE", "暂未收到结果"))
    .mockResolvedValue(child);
  backend.user.cardAction = cardAction;
  const send = vi.spyOn(backend.user, "sendMessage");
  const { result } = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(result.current.booting).toBe(false));
  const selection = { action: "bill_check" as const };
  await act(async () => { await result.current.actions.cardAction(task, selection); });
  await act(async () => { await result.current.actions.cardAction(task, selection); });
  await act(async () => { await result.current.actions.cardAction(task, selection); });
  expect(cardAction).toHaveBeenCalledTimes(2);
  expect(cardAction.mock.calls[0]).toEqual(cardAction.mock.calls[1]);
  expect(cardAction.mock.calls[0][1].source_revision).toBe(3);
  expect(result.current.tasks.get("child")?.module).toBe("bills");
  render(<TaskBlock envelope={result.current.tasks.get("child")!} slot={genericSlot}
    origin="real-api" conversation={result.current} />);
  expect(document.getElementById("task-child")?.querySelector("button")).toBeTruthy();
  expect(send).not.toHaveBeenCalled();
});

it("uses the card action endpoint with exact source and selection", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: task }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  const body = { request_id: "request", source_revision: 3, action: "subscription_cancel" as const, subscription_id: "second" };
  await createRealDataSource().cardAction!("source/a", body);
  expect(fetch).toHaveBeenCalledWith("/api/v1/tasks/source%2Fa/actions",
    expect.objectContaining({ method: "POST", body: JSON.stringify(body) }));
});
