// Maps a cross-linkage parent task onto the shell. The plan body is rendered by
// CrossPlanCard; this slot only contributes the fields shown by the generic
// waiting / recovery cards and the entry hints on the welcome card.
import { crossPlan, planCounts } from "../cross";
import type { BusinessSlot } from "../slots";
import type { DisplayField, ShellTask } from "../types";

function summarize(task: ShellTask): DisplayField[] {
  const view = crossPlan(task);
  if (!view) return [];
  const counts = planCounts(view);
  return [{
    name: "progress",
    label: "办理进度",
    value_text: "已办好 " + counts.done + " 项，共 " + counts.total + " 项",
  }];
}

export const crossSlot: BusinessSlot = {
  module: "cross",
  label: "联动安排",
  exampleHints: ["养老金到了，帮我安排本月的钱", "最近钱怎么花得快，帮我处理不用的扣费"],
  summarize,
};
