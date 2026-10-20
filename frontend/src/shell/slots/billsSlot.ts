// Maps a bills task onto the shell cards. Amounts, categories, clues and status
// come only from the public bills payload; this file does not invent a second schema.
import type {
  AnomalyResult,
  BillDetails,
  BillReport,
  SpendingSummary,
  TransactionCandidates,
} from "../../contracts";

type BillScope = SpendingSummary["scope"];
type Category = SpendingSummary["categories"][number]["category"];
type Transaction = BillDetails["transactions"][number];
import { yuan } from "../format";
import type { BusinessSlot } from "../slots";
import type { DisplayField, ReportView, ResultView, ShellTask } from "../types";

const CATEGORY_LABEL: Record<Category, string> = {
  dining: "餐饮",
  transport: "交通",
  medical: "医疗",
  shopping: "购物",
  housing: "居住",
  transfer: "转账",
  other: "其他",
};

const NATURE_LABEL: Record<Transaction["nature"], string> = {
  consumption: "消费",
  transfer: "转账",
  refund: "退款",
  interest: "利息",
};

const ATTENTION_LABEL: Record<AnomalyResult["findings"][number]["attention"], string> = {
  notice: "提示",
  high_attention: "重点提示",
};

// The contract exposes machine codes for insufficient checks; the card maps the
// known codes and never attributes the gap to the bank.
const REASON_LABEL: Record<string, string> = {
  insufficient_facts: "缺少判断依据",
  lookback_incomplete: "缺少三个月历史流水",
  trusted_family_status_required: "本人转账关系未确认",
  counterparty_or_lookback_missing: "缺少对手方或历史流水",
  amount_baseline_missing: "缺少金额参照",
  timezone_missing: "缺少交易时间",
  periodic_history_incomplete: "缺少连续扣款历史",
  merchant_identity_missing: "缺少商户信息",
};

function reasonLabel(reason: string | null): string {
  return reason && REASON_LABEL[reason] ? REASON_LABEL[reason] : "这次没能核对";
}

function signedYuan(fen: number): string {
  return fen < 0 ? "-¥" + (-fen / 100).toFixed(2) : "¥" + (fen / 100).toFixed(2);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isScope(value: unknown): value is BillScope {
  return isRecord(value)
    && Array.isArray(value.account_ids)
    && typeof value.start_at === "string"
    && typeof value.end_at === "string";
}

function isBillReport(value: unknown): value is BillReport {
  return isRecord(value)
    && typeof value.report_id === "string"
    && typeof value.spoken_summary === "string"
    && isRecord(value.summary)
    && isScope(value.scope);
}

function isBillDetails(value: unknown): value is BillDetails {
  return isRecord(value) && Array.isArray(value.transactions) && isScope(value.scope) && !("report_id" in value);
}

function isCandidates(value: unknown): value is TransactionCandidates {
  return isRecord(value) && Array.isArray(value.candidates) && isScope(value.scope) && !("transactions" in value);
}

function isAnomaly(value: unknown): value is AnomalyResult {
  return isRecord(value) && Array.isArray(value.findings) && Array.isArray(value.checks);
}

function isSummary(value: unknown): value is SpendingSummary {
  return isRecord(value)
    && Array.isArray(value.categories)
    && typeof value.consumption_net_fen === "number"
    && !("report_id" in value);
}

function categoryLabel(value: string): string {
  return value in CATEGORY_LABEL ? CATEGORY_LABEL[value as Category] : value;
}

function timeLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function rangeLabel(scope: BillScope): string {
  return timeLabel(scope.start_at) + " 起，" + timeLabel(scope.end_at) + " 止（不含结束时刻）";
}

function shareText(bps: number): string {
  return (bps / 100).toFixed(2) + "%";
}

function scopeOf(value: unknown): BillScope | null {
  return isRecord(value) && isScope(value.scope) ? value.scope : null;
}

function summarize(task: ShellTask): DisplayField[] {
  const data = task.data;
  const scope = scopeOf(data);
  if (!scope) return [];
  const fields: DisplayField[] = [{ name: "scope", label: "统计范围", value_text: rangeLabel(scope) }];
  if (isRecord(data) && typeof data.category === "string") {
    fields.push({ name: "category", label: "分类", value_text: categoryLabel(data.category) });
  }
  return fields;
}

function categoryFields(summary: SpendingSummary): DisplayField[] {
  return summary.categories.map((item) => ({
    name: "category-" + item.category,
    label: "第 " + item.rank + " 类 · " + categoryLabel(item.category),
    value_text: yuan(item.net_fen) + (typeof item.share_bps === "number" ? " · 占比 " + shareText(item.share_bps) : ""),
  }));
}

function comparisonFields(summary: SpendingSummary): DisplayField[] {
  const comparison = summary.comparison;
  if (!comparison) return [];
  const fields: DisplayField[] = [
    { name: "comparison-scope", label: "对比范围", value_text: rangeLabel(comparison.scope) },
    { name: "comparison-net", label: "对比净额", value_text: signedYuan(comparison.consumption_net_fen) },
    { name: "comparison-delta", label: "净额变化", value_text: signedYuan(comparison.delta_fen) },
  ];
  if (typeof comparison.change_bps === "number") {
    fields.push({ name: "comparison-change", label: "变化幅度", value_text: shareText(comparison.change_bps) });
  }
  if (comparison.largest_change_category) {
    fields.push({
      name: "comparison-category",
      label: "变化最大分类",
      value_text: categoryLabel(comparison.largest_change_category),
    });
  }
  return fields;
}

function overviewFields(summary: SpendingSummary): DisplayField[] {
  return [
    { name: "gross", label: "消费支出", value_text: yuan(summary.consumption_gross_fen) },
    { name: "refund", label: "退款", value_text: yuan(summary.consumption_refund_fen) },
    { name: "transfer-out", label: "转出", value_text: yuan(summary.transfer_out_fen) },
    { name: "transfer-in", label: "转入", value_text: yuan(summary.transfer_in_fen) },
    { name: "count", label: "笔数", value_text: String(summary.transaction_count) },
    { name: "accounts", label: "覆盖账户", value_text: summary.scope.account_ids.length + " 个" },
    ...categoryFields(summary),
    ...comparisonFields(summary),
    { name: "as-of", label: "数据时间", value_text: timeLabel(summary.as_of) },
  ];
}

function transactionField(item: Transaction): DisplayField {
  const nature = NATURE_LABEL[item.nature] ?? item.nature;
  const category = categoryLabel(item.category);
  // Transfer rows carry category "transfer" too; keep the row readable without
  // repeating the same word twice.
  const parts = [yuan(item.amount_fen), nature];
  if (nature !== category) parts.push(category);
  parts.push(timeLabel(item.occurred_at));
  if (item.counterparty_account_masked) parts.push(item.counterparty_account_masked);
  if (item.summary) parts.push(item.summary);
  return { name: item.transaction_id, label: item.counterparty_name, value_text: parts.join(" · ") };
}

function summaryView(data: SpendingSummary): ResultView {
  return {
    tone: "success",
    title: "消费汇总",
    headline: signedYuan(data.consumption_net_fen),
    fields: overviewFields(data),
  };
}

function detailsView(data: BillDetails): ResultView {
  return {
    tone: "success",
    title: data.category ? categoryLabel(data.category) + "明细" : "账单明细",
    headline: data.transactions.length + " 笔",
    fields: data.transactions.map(transactionField),
    note: "数据时间：" + timeLabel(data.as_of),
  };
}

function anomalyView(data: AnomalyResult): ResultView {
  const high = data.findings.some((finding) => finding.attention === "high_attention");
  const title = data.findings.length === 0
    ? "没有发现需要留意的交易"
    : high ? "有需要留意的账单" : "有账单提示";
  const fields: DisplayField[] = [];
  if (data.transaction) fields.push(transactionField(data.transaction));
  data.findings.forEach((finding, index) => {
    fields.push({
      name: "finding-" + index + "-evidence",
      label: ATTENTION_LABEL[finding.attention] + " · 规则 " + finding.rule_id,
      value_text: finding.evidence,
    });
    fields.push({
      name: "finding-" + index + "-suggestion",
      label: "建议",
      value_text: finding.suggestion,
    });
    if (finding.transaction_ids.length > 0) {
      fields.push({
        name: "finding-" + index + "-ids",
        label: "相关交易",
        value_text: finding.transaction_ids.join("、"),
      });
    }
  });
  for (const check of data.checks) {
    if (check.status !== "insufficient_data") continue;
    fields.push({
      name: "check-" + check.rule_id,
      label: "规则 " + check.rule_id + " 数据不足",
      value_text: reasonLabel(check.reason),
    });
  }
  return {
    tone: data.findings.length > 0 ? "warning" : "success",
    title,
    fields,
    note: "数据时间：" + timeLabel(data.as_of),
  };
}

function candidatesView(data: TransactionCandidates): ResultView {
  return {
    tone: "success",
    title: data.candidates.length > 0 ? "找到这些相关交易" : "没有找到相符的交易",
    headline: data.candidates.length + " 笔",
    fields: data.candidates.map(transactionField),
    note: "数据时间：" + timeLabel(data.as_of),
  };
}

function closedView(task: ShellTask, title: string, tone: ResultView["tone"]): ResultView {
  return { tone, title, fields: summarize(task), note: task.message || undefined };
}

function result(task: ShellTask): ResultView | null {
  if (task.status === "cancelled") return closedView(task, "已取消，没有继续查询", "neutral");
  if (task.status === "failed") return closedView(task, "这次没有查成", "danger");
  const data = task.data;
  if (isBillDetails(data)) return detailsView(data);
  if (isCandidates(data)) return candidatesView(data);
  if (isAnomaly(data)) return anomalyView(data);
  if (isSummary(data)) return summaryView(data);
  return null;
}

function report(task: ShellTask): ReportView | null {
  if (task.status !== "succeeded" && task.status !== "partially_succeeded") return null;
  if (!isBillReport(task.data)) return null;
  const data = task.data;
  const fields = overviewFields(data.summary);
  if (typeof data.monthly_average_fen === "number") {
    fields.push({ name: "monthly-average", label: "月均消费", value_text: yuan(data.monthly_average_fen) });
  }
  fields.push(
    { name: "statistical-days", label: "统计天数", value_text: String(data.statistical_days) },
    { name: "average-basis", label: "月均口径", value_text: data.average_basis },
    { name: "generated-at", label: "报告生成时间", value_text: timeLabel(data.generated_at) },
  );
  return {
    title: "账单报告",
    periodLabel: rangeLabel(data.scope),
    headline: { label: "消费净额", value: signedYuan(data.summary.consumption_net_fen) },
    fields,
    note: data.spoken_summary,
  };
}

export const billsSlot: BusinessSlot = {
  module: "bills",
  label: "账单",
  exampleHints: ["这个月花了多少", "看看这个月的餐饮明细", "这笔钱我不认识，是不是扣错了", "给我出一份这个月的账单"],
  summarize,
  result,
  report,
};
