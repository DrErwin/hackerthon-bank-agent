import type { MessageView } from "../contracts";
import type { CardSelection, ShellTask, TaskEnvelope } from "./types";

export interface CardLink { parentId: string; childId: string; selection: CardSelection; revision: number }
export const selectionKey = (selection: CardSelection) => selection.action === "subscription_cancel"
  ? selection.action + ":" + selection.subscription_id
  : selection.action === "bill_details" ? selection.action + ":" + selection.category
  : selection.action === "bill_range" ? selection.action + ":" + selection.month
  : selection.action === "bill_check" ? selection.action + ":" + (selection.account_id ?? "") + ":" + (selection.transaction_id ?? "") : selection.action;

export function readCardLinks(threadId: string): CardLink[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem("fe-card-links:" + threadId) ?? "[]");
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is CardLink => typeof item?.parentId === "string"
      && typeof item.childId === "string" && item.parentId !== item.childId
      && Number.isInteger(item.revision) && item.selection && ["bill_details", "bill_check", "bill_range", "subscription_cancel", "refresh_query"].includes(item.selection.action));
  } catch { return []; }
}

export function taskTitle(task: ShellTask): string {
  const data = task.data as Record<string, unknown> | null;
  if (data && Array.isArray(data.accounts)) return "我的银行卡";
  if (data && Array.isArray(data.payees)) return "常用收款人";
  if (data?.action === "list") return "订阅和自动扣费";
  if (task.module === "subscription") return "退订办理";
  if (task.module === "bills") {
    if (Array.isArray(data?.categories) || data?.summary) return "账单汇总";
    if (Array.isArray(data?.findings)) return "陌生扣款核对";
    const categories: Record<string, string> = { dining: "餐饮", transport: "交通", medical: "医疗", shopping: "购物", housing: "居住", transfer: "转账", other: "其他" };
    if (Array.isArray(data?.transactions)) return (categories[String(data.category)] ?? "账单") + "明细";
    return "查看账单";
  }
  if (task.module === "transfer") {
    const payee = data?.payee as { remark?: string; name_masked?: string } | undefined;
    return (payee ? "转给" + (payee.remark || payee.name_masked) : "转账办理")
      + (typeof data?.amount_fen === "number" ? " · " + (data.amount_fen / 100).toFixed(2) + " 元" : "");
  }
  return "办理记录";
}

export function inputPrompt(task: ShellTask): string {
  const input = task.interaction;
  if (!input) return "继续办理";
  const fields = input.required_fields;
  if (fields.includes("amount_fen")) return "您想转多少钱？";
  if (fields.includes("payer_account_id") || fields.includes("account_ids")) return "您想用哪张银行卡？";
  if (fields.includes("payee_hint")) return "您想转给谁？";
  if (fields.includes("subscription_id")) return "您想退订哪一项？";
  if (fields.includes("transaction_id")) return "您想核对哪一笔？";
  return input.prompt;
}

export type TimelineItem = { type: "message"; message: MessageView }
  | { type: "task"; envelope: TaskEnvelope; messages: MessageView[] };

// A record stays at its first assistant response. Later progress belongs inside
// that record, never moves it below unrelated conversation. Legacy unlinked
// tasks use the public snapshot time; no fabricated parent relationship.
export function buildTimeline(messages: MessageView[], tasks: Map<string, TaskEnvelope>, links: CardLink[] = []): TimelineItem[] {
  const nested = new Set(links.filter((link) => tasks.has(link.parentId) && tasks.has(link.childId)
    && !links.some((other) => other.parentId === link.childId)).map((link) => link.childId));
  const anchored = new Set<string>();
  const items: { value: TimelineItem; time: string; order: number }[] = [];
  messages.forEach((message, index) => {
    const ids = message.task_ids.filter((id) => tasks.has(id));
    if (message.role === "assistant" && ids.length === 1) {
      const id = ids[0];
      if (nested.has(id) || anchored.has(id)) return;
      anchored.add(id);
      items.push({ time: message.created_at, order: index, value: { type: "task", envelope: tasks.get(id)!,
        messages: messages.filter((item) => item.role === "assistant" && item.task_ids.length === 1 && item.task_ids[0] === id) } });
    } else items.push({ time: message.created_at, order: index, value: { type: "message", message } });
  });
  for (const envelope of tasks.values()) {
    if (!anchored.has(envelope.task.task_id) && !nested.has(envelope.task.task_id))
      items.push({ time: envelope.timelineAt ?? envelope.task.snapshot_at, order: messages.length, value: { type: "task", envelope, messages: [] } });
  }
  return items.sort((a, b) => a.time.localeCompare(b.time) || a.order - b.order).map((item) => item.value);
}
