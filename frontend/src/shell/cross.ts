// Cross-linkage plan helpers. Everything here reads the public CrossTaskView
// payload; the page never invents a step, a status or an amount of its own.
import type { CrossStep, CrossTaskView, InteractionRequest } from "../contracts";
import { yuan } from "./format";
import type { DisplayField, ShellTask } from "./types";

const SCENARIO_TITLE: Record<string, string> = {
  expense_reduction: "减少用不上的扣费",
  monthly_arrangement: "安排这个月的养老金",
  birthday: "准备生日",
  budget: "设置花费额度",
  income_distribution: "分配这笔收入",
};

// Step actions are capability names; the page speaks about what the step does.
const STEP_TITLE: Record<string, string> = {
  "transfer.list_accounts": "查看您的账户",
  "subscription.list_subscriptions": "核对正在扣费的签约",
  "bills.summarize": "查看最近的账单",
  "transfer.list_payees": "确认收款人",
  "subscription.cancel_subscription": "取消不需要的签约",
  "transfer.start_transfer": "转出一笔",
  // Birthday bank writes and the read-only freeze query (business/05).
  "bank.freeze_funds": "冻结生日安排资金",
  "bank.create_order": "创建订单",
  "bank.capture_frozen": "支付订单",
  "bank.release_frozen": "释放冻结资金",
  "bank.get_freeze": "核对冻结资金",
};

// The two safe reads carry the same action; their step ids say which projected
// bank fact each row is (consumed total, current frozen remainder).
const BIRTHDAY_ROW_TITLE: Record<string, string> = {
  "birthday-consumed": "已消费",
  "birthday-remaining": "当前冻结余款",
};

const BIRTHDAY_ACTIONS = new Set([
  "bank.freeze_funds", "bank.create_order", "bank.capture_frozen",
  "bank.release_frozen", "bank.get_freeze",
]);

export const PLAN_PROMISE = "这个安排只是先定下怎么办；每一项真正办理时，还会单独请您确认。";
export const PLAN_STOPPED = "已经停下，不再新办。已经办好的不会退回，没办的也不会再动。";
// Cross menus ask for values (an amount, a date, a controlled reference) next to
// their own choices; the answer is typed and the module validates it.
export const CROSS_ANSWER_LABEL = "也可以直接打字回答，例如 1500 或 1500元";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Shape guard for the public cross payload; anything else is not a plan card. */
export function crossPlan(task: ShellTask): CrossTaskView | null {
  const data = task.data;
  if (!isRecord(data) || typeof data.plan_revision !== "number" || !Array.isArray(data.steps)) return null;
  return data as unknown as CrossTaskView;
}

export function scenarioTitle(view: CrossTaskView | null): string {
  return (view?.scenario && SCENARIO_TITLE[view.scenario]) || "帮您安排";
}

export function stepTitle(step: CrossStep): string {
  const title = BIRTHDAY_ROW_TITLE[step.step_id] ?? STEP_TITLE[step.action] ?? "办理一项";
  return step.action === "transfer.start_transfer" && typeof step.amount_fen === "number"
    ? title + "（" + yuan(step.amount_fen) + "）"
    : title;
}

/**
 * What one birthday step returned: its amount, the order it belongs to and the
 * payment state the bank reported. A missing amount on an unknown write says so
 * instead of showing zero, and an order without a payment state claims nothing.
 */
export function stepFacts(step: CrossStep): { amount: string | null; details: string[] } {
  if (!BIRTHDAY_ACTIONS.has(step.action)) return { amount: null, details: [] };
  const amount = typeof step.amount_fen === "number"
    ? yuan(step.amount_fen)
    : step.status === "succeeded" || step.status === "needs_attention" ? "金额待核实" : null;
  const details: string[] = [];
  if (step.order_id) details.push("订单号 " + step.order_id);
  if (step.payment_status === "paid") details.push("已付款");
  if (step.payment_status === "unpaid") details.push("未付款");
  return { amount, details };
}

/**
 * The birthday module asks for a typed positive integer by prompt; the
 * interaction carries no input-type field, so the page only switches the numeric
 * keyboard and its own submit hint. The server still decides what a valid
 * quantity is and re-asks when it is not.
 */
export function asksForQuantity(interaction: InteractionRequest): boolean {
  return interaction.kind === "input" && interaction.required_fields.includes("cross_selection")
    && (interaction.prompt.includes("的数量") || interaction.prompt.includes("输入数量"));
}

export function planCounts(view: CrossTaskView): { done: number; total: number } {
  return {
    done: view.steps.filter((step) => step.status === "succeeded").length,
    total: view.steps.length,
  };
}

function signedYuan(fen: number): string {
  return fen < 0 ? "-¥" + (-fen / 100).toFixed(2) : yuan(fen);
}

function factsTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false });
}

/** Server facts only: fields that are still null are simply not shown. */
export function crossFacts(view: CrossTaskView): DisplayField[] {
  const fields: DisplayField[] = [];
  const arrangement = view.arrangement;
  if (arrangement) {
    fields.push(
      { name: "base", label: "本次安排的入账", value_text: yuan(arrangement.base_fen) },
      { name: "reserve", label: "生活费留存（不转出）", value_text: yuan(arrangement.living_reserve_fen) },
      { name: "protected", label: "已经保护起来的钱", value_text: yuan(arrangement.protected_fen) },
      { name: "distributable", label: "可以安排的钱", value_text: yuan(arrangement.distributable_fen) },
    );
    if (arrangement.known_debits_fen) {
      fields.push({
        name: "debits",
        label: "已知代扣",
        value_text: yuan(arrangement.known_debits_fen)
          + (arrangement.reserve_includes_known_debits ? "（已经算在生活费里）" : "（生活费之外另留）"),
      });
    }
  }
  const budget = view.budget;
  if (budget) {
    // Adoption is the server's own result: a candidate is never shown as adopted,
    // and the ledger figures are quoted as of the time the server read them.
    fields.push(
      { name: "budget-adopted", label: "个人预算", value_text: budget.adopted ? "已采用" : "候选、尚未采用" },
      { name: "limit", label: "预算限额", value_text: yuan(budget.personal_limit_fen) },
      { name: "used", label: "账单已用", value_text: signedYuan(budget.used_fen) },
      { name: "remaining", label: "账单剩余", value_text: signedYuan(budget.remaining_fen) },
      { name: "as-of", label: "截至", value_text: factsTime(budget.facts_as_of) },
    );
    if (budget.budget_ref) {
      fields.push({ name: "version", label: "版本", value_text: String(budget.budget_ref.version) });
    }
  }
  return fields;
}
