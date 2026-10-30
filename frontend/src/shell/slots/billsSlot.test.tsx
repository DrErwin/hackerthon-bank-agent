import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { AnomalyResult, BillDetails, BillReport, SpendingSummary } from "../../contracts";
import { TaskBlock } from "../components/TaskBlock";
import type { ShellTask } from "../types";
import type { Conversation } from "../useConversation";
import { billsSlot } from "./billsSlot";

const scope: SpendingSummary["scope"] = {
  account_ids: ["acc-1"],
  start_at: "2026-10-01T00:00:00+08:00",
  end_at: "2026-11-01T00:00:00+08:00",
};

const summary: SpendingSummary = {
  scope,
  as_of: "2026-10-19T08:00:00+08:00",
  source_as_of: [{ account_id: "acc-1", as_of: "2026-10-19T08:00:00+08:00" }],
  transaction_count: 2,
  consumption_gross_fen: 50000,
  consumption_refund_fen: 0,
  consumption_net_fen: 50000,
  transfer_out_fen: 0,
  transfer_in_fen: 0,
  categories: [{
    category: "dining",
    outflow_fen: 50000,
    refund_fen: 0,
    net_fen: 50000,
    share_bps: 10000,
    rank: 1,
  }],
  comparison: {
    scope,
    as_of: "2026-09-19T08:00:00+08:00",
    consumption_net_fen: 20000,
    delta_fen: 30000,
    change_bps: 15000,
    largest_change_category: "dining",
  },
};

const transaction: BillDetails["transactions"][number] = {
  transaction_id: "txn-9",
  account_id: "acc-1",
  occurred_at: "2026-10-03T12:30:00+08:00",
  amount_fen: 3200,
  nature: "consumption",
  category: "dining",
  direction: "outflow",
  counterparty_id: null,
  counterparty_name: "社区食堂",
  counterparty_account_masked: "****1234",
  channel: null,
  summary: "午餐",
  original_transaction_id: null,
  original_occurred_at: null,
};

function task(status: ShellTask["status"], data: unknown, message = ""): ShellTask {
  return {
    task_id: "task-bills",
    run_id: "run-1",
    status,
    data,
    message,
    interaction: null,
    error: null,
    allowed_actions: [],
    recovery_required: false,
    recovery_reason: null,
    thread_id: "thread-1",
    demo_round_id: "round-1",
    snapshot_at: "2026-10-19T09:00:00+08:00",
    task_revision: 1,
    cancel_requested: false,
  };
}

const conversation = {
  tasks: new Map(),
  history: {},
  confirmations: {},
  verifications: {},
  bootRecovery: new Set<string>(),
  expired: false,
  busy: {},
  taskErrors: {},
  actions: {},
} as Conversation;

beforeEach(() => { HTMLDialogElement.prototype.showModal = function () { this.open = true; }; });
afterEach(cleanup);

describe("bills slot", () => {
  it("shows a report from the returned summary and spoken text, without a transaction list", () => {
    const payload: BillReport = {
      report_id: "report-1",
      scope,
      summary,
      spoken_summary: "这个月餐饮花了五百元。",
      monthly_average_fen: null,
      statistical_days: 19,
      average_basis: "不足一个自然月，不计算月均",
      generated_at: "2026-10-19T09:00:00+08:00",
    };
    const view = billsSlot.report?.(task("succeeded", payload));
    expect(view?.note).toBe("这个月餐饮花了五百元。");
    expect(view?.headline).toEqual({ label: "消费净额", value: "¥500.00" });
    expect(view?.fields.some((field) => field.label.includes("餐饮") && field.value_text.includes("¥500.00"))).toBe(true);
    expect(view?.fields.some((field) => field.label === "月均消费")).toBe(false);
    expect(view?.fields.some((field) => field.value_text === "不足一个自然月，不计算月均")).toBe(true);
    expect(view?.fields.some((field) => field.value_text.includes("txn-9"))).toBe(false);
    expect(billsSlot.result?.(task("succeeded", payload))).toBeNull();

    render(
      <TaskBlock
        envelope={{ task: task("succeeded", payload), module: "bills" }}
        slot={billsSlot}
        origin="real-api"
        conversation={conversation}
      />,
    );
    expect(screen.queryByText("这个月餐饮花了五百元。")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "查看完整账单说明" }));
    expect(screen.getByText("这个月餐饮花了五百元。")).toBeTruthy();
    expect(screen.getByText("账单报告")).toBeTruthy();
    expect(screen.queryByText(/演示数据/)).toBeNull();
    expect(screen.queryByText("办理结果")).toBeNull();
  });

  it("keeps the demo banner when the same report is not from the real API", () => {
    const payload: BillReport = {
      report_id: "report-1",
      scope,
      summary,
      spoken_summary: "这个月餐饮花了五百元。",
      monthly_average_fen: 10000,
      statistical_days: 19,
      average_basis: "按已过天数折算",
      generated_at: "2026-10-19T09:00:00+08:00",
    };
    render(
      <TaskBlock
        envelope={{ task: task("succeeded", payload), module: "bills" }}
        slot={billsSlot}
        origin="contract-demo"
        conversation={conversation}
      />,
    );
    expect(screen.getByText(/演示数据，不代表真实账单/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "查看完整账单说明" }));
    expect(screen.getByText("¥100.00")).toBeTruthy();
  });

  it("shows summary, detail and anomaly text returned by the server", () => {
    const summaryView = billsSlot.result?.(task("succeeded", summary));
    expect(summaryView?.title).toBe("消费汇总");
    expect(summaryView?.fields.some((field) => field.label === "净额变化" && field.value_text === "¥300.00")).toBe(true);
    expect(summaryView?.fields.some((field) => field.value_text === "150.00%")).toBe(true);

    const details: BillDetails = {
      scope,
      category: "dining",
      transactions: [transaction],
      source_as_of: [{ account_id: "acc-1", as_of: "2026-10-19T08:00:00+08:00" }],
      as_of: "2026-10-19T08:00:00+08:00",
    };
    const detailView = billsSlot.result?.(task("succeeded", details));
    expect(detailView?.title).toBe("餐饮明细");
    expect(detailView?.fields[0]).toMatchObject({
      label: "社区食堂",
      value_text: expect.stringContaining("¥32.00"),
    });
    expect(detailView?.fields[0]?.value_text).toContain("****1234");
    expect(detailView?.fields[0]?.value_text).toContain("餐饮");

    const anomaly: AnomalyResult = {
      transaction: null,
      findings: [{
        transaction_ids: ["txn-9"],
        rule_id: 2,
        attention: "high_attention",
        evidence: "同一商户当天出现两笔相同金额",
        suggestion: "请对照银行卡账单再看一眼",
      }],
      checks: [
        { rule_id: 2, status: "evaluated", reason: null },
        { rule_id: 4, status: "insufficient_data", reason: "merchant_identity_missing" },
      ],
      as_of: "2026-10-19T08:00:00+08:00",
    };
    const anomalyView = billsSlot.result?.(task("succeeded", anomaly));
    expect(anomalyView?.title).toBe("有需要留意的账单");
    expect(anomalyView?.fields.some((field) => field.value_text === "同一商户当天出现两笔相同金额")).toBe(true);
    expect(anomalyView?.fields.some((field) => field.value_text === "请对照银行卡账单再看一眼")).toBe(true);
    expect(anomalyView?.fields.some((field) => field.value_text === "缺少商户信息")).toBe(true);

    const clear: AnomalyResult = { ...anomaly, findings: [], checks: [{ rule_id: 1, status: "evaluated", reason: null }] };
    expect(billsSlot.result?.(task("succeeded", clear))?.title).toBe("没有发现需要留意的交易");
  });

  it("does not invent an amount when the query fails", () => {
    const view = billsSlot.result?.(task("failed", null, "账单范围超出可查询区间"));
    expect(view?.title).toBe("这次没有查成");
    expect(view?.note).toBe("账单范围超出可查询区间");
    expect(view?.fields).toEqual([]);
    expect(billsSlot.report?.(task("failed", null))).toBeNull();
  });
});
