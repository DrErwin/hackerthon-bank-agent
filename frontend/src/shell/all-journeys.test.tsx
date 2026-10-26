import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { BusinessCards, BillCardActions } from "./components/BusinessCards";
import { Composer } from "./components/Chrome";
import { ResultCard } from "./components/StatusCards";
import { ConfirmationCard } from "./components/ConfirmationCard";
import { AssistantPage } from "./AssistantPage";
import { createSlotRegistry } from "./slots";
import { transferSlot } from "./slots/transferDemoSlot";
import { createDemoBackend } from "./stub/demoBackend";
import type { ShellTask } from "./types";

const task: ShellTask = {
  task_id: "lookup", run_id: "run", status: "succeeded", data: null, message: "已查询",
  interaction: null, error: null, allowed_actions: [], recovery_required: false, recovery_reason: null,
  module: "transfer", thread_id: "thread", demo_round_id: "round", snapshot_at: "2026-10-26T00:00:00Z",
  task_revision: 3, cancel_requested: false,
};
beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("renders one confirmation action per decision and routes extra options separately", () => {
  const onAnswer = vi.fn();
  const onSelectOption = vi.fn();
  render(<ConfirmationCard id="confirm" title="请核对" active canConfirm canCancel busy={false}
    extraActions={[]} onAnswer={onAnswer} onSelectOption={onSelectOption}
    options={[{ id: "approve", label: "确认办理" }, { id: "cancel", label: "取消" }, { id: "edit-opaque", label: "修改商品" }]}
    view={{ confirmation_id: "c", task_id: "t", confirmation_version: 1, display_fields: [], created_at: task.snapshot_at, expires_at: task.snapshot_at, decision: "pending" }} />);
  expect(screen.getAllByRole("button", { name: "确认办理" })).toHaveLength(1);
  expect(screen.getAllByRole("button", { name: "取消", exact: true })).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "确认办理" }));
  expect(onAnswer).toHaveBeenCalledExactlyOnceWith("approve");
  fireEvent.click(screen.getByRole("button", { name: "修改商品" }));
  expect(onSelectOption).toHaveBeenCalledExactlyOnceWith("edit-opaque", "修改商品");
});

it("searches masked payees locally and applies the selected identity to the existing transfer", async () => {
  const onAction = vi.fn();
  const onChoose = vi.fn().mockResolvedValue(undefined);
  const target = { ...task, task_id: "transfer", status: "waiting_input" as const };
  render(<BusinessCards task={{ ...task, data: { payees: [
    { payee_id: "p1", remark: "妈妈", name_masked: "张*", bank_name: "示例银行", account_masked: "****0011" },
    { payee_id: "p2", remark: "房东", name_masked: "李*", bank_name: "示例银行", account_masked: "****0022" },
  ] } }} busy={false} enabled onAction={onAction} onChoose={onChoose} transferTargets={[target]} />);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "0022" } });
  expect(screen.queryByText("妈妈")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /选择房东/ }));
  expect(onChoose).toHaveBeenCalledExactlyOnceWith(target, { payee_id: "p2" });
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "不存在" } });
  expect(screen.getByRole("status").textContent).toContain("没有找到这位收款人");
  expect(onAction).not.toHaveBeenCalled();
});

it("keeps every substantive receipt fact visible while putting only references in the drawer", () => {
  render(<ResultCard id="receipt" origin="real-api" view={{ tone: "success", title: "转账成功", fields: [
    { name: "payee", label: "收款人", value_text: "妈妈" },
    { name: "bank", label: "银行", value_text: "示例银行" },
    { name: "fee", label: "手续费", value_text: "¥0.00" },
    { name: "completed", label: "完成时间", value_text: "2026年10月26日 12:00" },
    { name: "balance", label: "付款卡余额", value_text: "¥800.00" },
    { name: "transaction", label: "交易号", value_text: "TEST-123" },
  ] }} />);
  expect(screen.getByText("¥800.00")).toBeTruthy();
  expect(screen.getByText("2026年10月26日 12:00")).toBeTruthy();
  expect(screen.queryByText("TEST-123")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "办理凭证" }));
  expect(screen.getByText("TEST-123")).toBeTruthy();
});

it("changes a bill month with the public action while preserving the source task", async () => {
  const onAction = vi.fn().mockResolvedValue("next");
  render(<BillCardActions task={{ ...task, data: {
    scope: { start_at: "2026-10-01T00:00:00+08:00", end_at: "2026-11-01T00:00:00+08:00", account_ids: ["A1"] },
    categories: [], transaction_count: 0, consumption_net_fen: 0, as_of: task.snapshot_at,
  } }} busy={false} onAction={onAction} />);
  expect(screen.getByText(/这段时间没有账单记录/)).toBeTruthy();
  fireEvent.click(screen.getByText("换一个月份"));
  fireEvent.input(screen.getByLabelText("查询月份（沿用这些银行卡）"), { target: { value: "2026-09" } });
  fireEvent.click(screen.getByRole("button", { name: "查询这个月" }));
  expect(onAction).toHaveBeenCalledExactlyOnceWith({ action: "bill_range", month: "2026-09" });
});

it("preserves multiline drafts and sends Enter only after Chinese composition ends", async () => {
  const onSend = vi.fn().mockResolvedValue(true);
  render(<Composer disabled={false} sending={false} pendingText={null} onSend={onSend} />);
  const input = screen.getByRole("textbox");
  fireEvent.change(input, { target: { value: "金额改成300元\n用工资卡" } });
  fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
  fireEvent.keyDown(input, { key: "Enter", isComposing: true });
  expect(onSend).not.toHaveBeenCalled();
  fireEvent.keyDown(input, { key: "Enter" });
  await waitFor(() => expect(onSend).toHaveBeenCalledExactlyOnceWith("金额改成300元\n用工资卡"));
});

it("keeps the user's large text choice on the next page visit", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const slots = createSlotRegistry([transferSlot]);
  const view = render(<AssistantPage source={backend.user} slots={slots} />);
  await waitFor(() => expect(screen.queryByText("正在读取对话记录…")).toBeNull());
  fireEvent.click(screen.getByRole("button", { name: "大字" }));
  view.unmount();
  render(<AssistantPage source={backend.user} slots={slots} />);
  expect(screen.getByRole("button", { name: "标准字" }).getAttribute("aria-pressed")).toBe("true");
});
