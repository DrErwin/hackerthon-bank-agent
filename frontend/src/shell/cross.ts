// Cross-linkage plan helpers. Everything here reads the public CrossTaskView
// payload; the page never invents a step, a status or an amount of its own.
import type { CrossStep, CrossTaskView } from "../contracts";
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
};

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
  const title = STEP_TITLE[step.action] ?? "办理一项";
  return step.action === "transfer.start_transfer" && typeof step.amount_fen === "number"
    ? title + "（" + yuan(step.amount_fen) + "）"
    : title;
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
    fields.push(
      { name: "limit", label: "预算上限", value_text: yuan(budget.personal_limit_fen) },
      { name: "used", label: "已经用掉", value_text: signedYuan(budget.used_fen) },
      { name: "remaining", label: "还能用", value_text: signedYuan(budget.remaining_fen) },
    );
  }
  return fields;
}
