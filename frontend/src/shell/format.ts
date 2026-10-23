import type { ShellTask, Tone } from "./types";

export function newRequestId(): string {
  return crypto.randomUUID();
}

export function clockTime(value: string | null | undefined): string {
  if (!value) return "";
  return new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export function yuan(fen: number | null | undefined): string {
  return typeof fen === "number" ? "¥" + (fen / 100).toFixed(2) : "未返回";
}

export interface StatusLabel {
  tone: Tone;
  icon: string;
  text: string;
}

export function taskStatusLabel(task: ShellTask): StatusLabel {
  switch (task.status) {
    case "running":
      return { tone: "pending", icon: "…", text: "正在办理" };
    case "waiting_input":
      return { tone: "pending", icon: "✎", text: "等您补充" };
    case "waiting_approval":
      return task.interaction?.kind === "verification"
        ? { tone: "pending", icon: "◆", text: "等您验证" }
        : { tone: "pending", icon: "?", text: "等您确认" };
    case "needs_attention":
      return { tone: "warning", icon: "!", text: task.error?.source === "security" ? "安全核对暂停" : "结果待核实" };
    case "succeeded":
      return { tone: "success", icon: "✓", text: "已办结" };
    case "partially_succeeded":
      return { tone: "warning", icon: "!", text: "部分完成" };
    case "failed":
      return { tone: "danger", icon: "✕", text: "没有办成" };
    case "cancelled":
      return { tone: "neutral", icon: "−", text: "已取消" };
  }
}

export function isTerminal(task: ShellTask): boolean {
  return task.status === "succeeded" || task.status === "failed" || task.status === "cancelled" || task.status === "partially_succeeded";
}

export function originLabel(origin: string): string {
  if (origin === "real-api") return "";
  if (origin === "contract-demo") return "契约演示数据";
  return "演示数据（stub）";
}
