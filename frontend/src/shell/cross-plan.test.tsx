// Ticket v05-cross-frontend/01: the parent plan card, the child interaction it
// nests, and the receipt. Server payloads only; no invented steps or amounts.
import { cleanup, fireEvent, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { ConfirmationView, CrossTaskView } from "../contracts";
import { CrossPlanCard } from "./components/CrossPlanCard";
import { TaskBlock } from "./components/TaskBlock";
import { crossSlot } from "./slots/crossSlot";
import { genericSlot } from "./slots";
import { buildTimeline } from "./presentation";
import { createDemoBackend } from "./stub/demoBackend";
import { createRealDataSource } from "./api/realDataSource";
import { useConversation } from "./useConversation";
import { CROSS_ANSWER_LABEL, PLAN_PROMISE, PLAN_STOPPED } from "./cross";
import type { ShellDataSource, ShellTask, TaskEnvelope } from "./types";

const CONFIRMATION: ConfirmationView = {
  confirmation_id: "conf-1", task_id: "child", confirmation_version: 1,
  display_fields: [
    { name: "merchant", label: "签约商户", value_text: "视频会员" },
    { name: "amount", label: "每月扣费", value_text: "¥39.00" },
  ],
  created_at: "2026-10-25T00:00:00Z", expires_at: "2026-10-25T00:10:00Z", decision: "pending",
};

const plan: CrossTaskView = {
  scenario: "expense_reduction",
  plan_revision: 1,
  summary: "账单和签约都看过了。",
  steps: [
    { step_id: "accounts", action: "transfer.list_accounts", status: "succeeded" },
    { step_id: "subs", action: "subscription.list_subscriptions", status: "succeeded" },
    { step_id: "cancel_1", action: "subscription.cancel_subscription", status: "waiting_approval", child_task_id: "child" },
    { step_id: "cancel_2", action: "subscription.cancel_subscription" },
  ],
  plan_step_ids: ["accounts", "subs", "cancel_1", "cancel_2"],
  active_step_id: "cancel_1",
  interaction_task_id: "child",
};

const parent: ShellTask = {
  task_id: "plan", run_id: "p1", status: "running", data: plan,
  message: "采用好了，下面按顺序一项项办。", interaction: null, error: null,
  allowed_actions: ["resume", "cancel"], recovery_required: false, recovery_reason: null,
  thread_id: "thread", demo_round_id: "round",
  snapshot_at: "2026-10-25T00:00:00Z", task_revision: 4, cancel_requested: false,
};

const child: ShellTask = {
  task_id: "child", run_id: "c1", status: "waiting_approval", data: null,
  message: "取消后以后不再扣费。", interaction: {
    interaction_id: "i1", kind: "confirmation", prompt: "请确认办理内容",
    required_fields: [], options: [], record_ref: "conf-1",
  },
  error: null, allowed_actions: ["confirm", "cancel"], recovery_required: false, recovery_reason: null,
  thread_id: "thread", demo_round_id: "round",
  snapshot_at: "2026-10-25T00:00:00Z", task_revision: 2, cancel_requested: false,
};

const parentEnvelope: TaskEnvelope = { task: { ...parent, module: "cross" }, module: "cross", timelineAt: parent.snapshot_at };
const childEnvelope: TaskEnvelope = { task: { ...child, module: "subscription" }, module: "subscription", timelineAt: child.snapshot_at };

beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("renders the adopted plan from the server payload and nests the current child card", () => {
  const renderChild = vi.fn((id: string) => <p key={id}>{"当前子卡片 " + id}</p>);
  render(<CrossPlanCard view={plan} task={parent} childTask={() => undefined} renderChild={renderChild} />);
  expect(screen.getByRole("region", { name: "减少用不上的扣费安排" })).toBeTruthy();
  expect(screen.getByText(PLAN_PROMISE)).toBeTruthy();
  expect(screen.getByText("查看您的账户")).toBeTruthy();
  expect(screen.getAllByText("取消不需要的签约")).toHaveLength(2);
  expect(screen.getAllByText("已办结")).toHaveLength(2);
  // The running step is marked for assistive tech and carries the child card.
  const rows = screen.getAllByText("取消不需要的签约").map((element) => element.closest("li")!);
  expect(rows[0].getAttribute("aria-current")).toBe("step");
  expect(rows[1].getAttribute("aria-current")).toBeNull();
  expect(renderChild).toHaveBeenCalledWith("child");
  expect(screen.getByText("当前子卡片 child")).toBeTruthy();
  expect(screen.getByText("已办好 2 项，共 4 项。")).toBeTruthy();
  // The last step has no server status yet, so it reads as "待开始" and invents nothing.
  expect(screen.getByText("待开始")).toBeTruthy();
});

it("uses the server message as the receipt and the stop reason for a stopped plan", () => {
  const done: ShellTask = { ...parent, status: "succeeded", message: "已经取消两项签约。", data: {
    ...plan, active_step_id: null, interaction_task_id: null,
    steps: plan.steps.map((step) => ({ ...step, status: "succeeded" as const })),
  } };
  const view = render(<CrossPlanCard view={done.data as CrossTaskView} task={done} childTask={() => undefined} />);
  expect(screen.getByText("已经取消两项签约。")).toBeTruthy();
  expect(screen.queryByText(PLAN_PROMISE)).toBeNull();

  const stopped: ShellTask = { ...parent, status: "cancelled", message: "", data: { ...plan, stop_reason: "user_cancelled" } };
  view.rerender(<CrossPlanCard view={stopped.data as CrossTaskView} task={stopped} childTask={() => undefined} />);
  expect(screen.getByText(PLAN_STOPPED)).toBeTruthy();
});

it("keeps an already stopped plan's own stop note when the server also sends a receipt", () => {
  const stopped: ShellTask = { ...parent, status: "partially_succeeded", message: "两项办好了，其余已经停下。",
    data: { ...plan, stop_reason: "user_cancelled" } };
  render(<CrossPlanCard view={stopped.data as CrossTaskView} task={stopped} childTask={() => undefined} />);
  expect(screen.getByText("两项办好了，其余已经停下。")).toBeTruthy();
  expect(screen.getByText(PLAN_STOPPED)).toBeTruthy();
});

it("removes cancellation from a stopped plan even when its last action list still includes cancel", async () => {
  const stopped = { ...parentEnvelope, task: { ...parentEnvelope.task, status: "cancelled" as const,
    message: "本次安排已停止。", data: { ...plan, active_step_id: null, interaction_task_id: null, stop_reason: "user_cancelled" } } };
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.listTasks = async () => [stopped];
  backend.user.listChildren = async () => [];
  const { result } = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(result.current.booting).toBe(false));
  render(<TaskBlock envelope={stopped} slot={crossSlot} origin="real-api" conversation={result.current} />);
  expect(screen.getByText("本次安排已停止。")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "取消这次办理" })).toBeNull();
});

it("shows the arrangement facts only when the server sends them", () => {
  const empty = render(<CrossPlanCard view={plan} task={parent} childTask={() => undefined} />);
  expect(screen.queryByText("生活费留存（不转出）")).toBeNull();
  empty.rerender(<CrossPlanCard view={{
    ...plan,
    arrangement: {
      arrangement_id: "arr_1", plan_revision: 1, payer_account_id: "A1", funds_basis: "selected_income",
      income_transaction_ids: ["t1"], base_fen: 500000, living_reserve_fen: 150000,
      reserve_includes_known_debits: true, upcoming_debit_scope: {
        account_ids: ["A1"], start_at: "2026-10-01T00:00:00Z", end_at: "2026-11-01T00:00:00Z",
      },
      known_debits_fen: 3900, protected_fen: 150000, distributable_fen: 350000,
      facts_as_of: "2026-10-25T00:00:00Z", adopted: true,
    },
  }} task={parent} childTask={() => undefined} />);
  expect(screen.getByText("生活费留存（不转出）")).toBeTruthy();
  expect(screen.getAllByText("¥1500.00")).toHaveLength(2);
  expect(screen.getByText("¥3500.00")).toBeTruthy();
  expect(screen.getByText(/已经算在生活费里/)).toBeTruthy();
});

it("does not add a standalone record for a cross parent's child tasks", () => {
  const tasks = new Map<string, TaskEnvelope>([
    [parentEnvelope.task.task_id, parentEnvelope],
    [childEnvelope.task.task_id, childEnvelope],
  ]);
  const items = buildTimeline([], tasks, [], new Set([childEnvelope.task.task_id]));
  expect(items.map((item) => item.type === "task" ? item.envelope.task.task_id : "message")).toEqual(["plan"]);
});

it("loads children from the API and renders the child's confirmation inside the plan", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.listTasks = async () => [parentEnvelope];
  backend.user.listChildren = async (taskId: string) => taskId === parent.task_id ? [childEnvelope] : [];
  backend.user.getConfirmation = async () => CONFIRMATION;
  const answer = vi.fn().mockResolvedValue({ ...child, status: "succeeded", interaction: null });
  backend.user.answerConfirmation = answer;
  const provideInput = vi.fn();
  backend.user.provideInput = provideInput;
  const { result } = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(result.current.booting).toBe(false));
  await waitFor(() => expect(result.current.tasks.get(child.task_id)).toBeTruthy());
  expect(result.current.serverChildIds.has(child.task_id)).toBe(true);

  render(<TaskBlock envelope={result.current.tasks.get(parent.task_id)!} slot={crossSlot}
    origin="real-api" conversation={{ ...result.current, bootRecovery: new Set<string>() }}
    renderChild={(id) => <TaskBlock envelope={result.current.tasks.get(id)!} slot={genericSlot}
      origin="real-api" conversation={{ ...result.current, bootRecovery: new Set<string>() }} />} />);
  expect(await screen.findByText("签约商户")).toBeTruthy();
  expect(screen.getByText("视频会员")).toBeTruthy();
  // The answer belongs to the child task: its confirmation goes out under the
  // child's own record, never as a parent-level approval.
  fireEvent.click(screen.getByRole("button", { name: "确认退订" }));
  await waitFor(() => expect(answer).toHaveBeenCalledExactlyOnceWith("conf-1", expect.objectContaining({
    confirmation_version: 1, choice: "approve",
  })));
  expect(provideInput).not.toHaveBeenCalled();
  // No "approve everything" control is offered next to the plan.
  const region = screen.getByRole("region", { name: "减少用不上的扣费安排" });
  const approveAll = within(region).queryAllByRole("button")
    .map((button) => button.textContent ?? "").filter((text) => /全部|批准/.test(text));
  expect(approveAll).toEqual([]);
});

it("reads a parent's children from the documented endpoint", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: [child] }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  const list = await createRealDataSource().listChildren!("plan/a");
  expect(fetch).toHaveBeenCalledWith("/api/v1/tasks/plan%2Fa/children", expect.objectContaining({ method: "GET" }));
  expect(list.map((envelope) => envelope.task.task_id)).toEqual(["child"]);
});

const asking: ShellTask = {
  ...parent,
  status: "waiting_input",
  message: "这次生活费留多少元？（可输入金额，如“1500元”）",
  interaction: {
    interaction_id: "CX1", kind: "input", prompt: "这次生活费留多少元？（可输入金额，如“1500元”）",
    required_fields: ["cross_selection"], options: [{ id: "stop", label: "停止本次安排" }], record_ref: null,
  },
  allowed_actions: ["provide_input", "cancel"],
  // The real cross menus (`entry._ask`) carry no plan body; only the picker and the
  // running/terminal states attach one. The page must work in both shapes.
  data: null,
};

const askingEnvelope: TaskEnvelope = { task: { ...asking, module: "cross" }, module: "cross", timelineAt: asking.snapshot_at };

function Harness({ source }: { source: ShellDataSource }) {
  const conversation = useConversation(source);
  const envelope = conversation.tasks.get(asking.task_id);
  if (conversation.booting || !envelope) return null;
  return <TaskBlock envelope={envelope} slot={crossSlot} origin="real-api" conversation={conversation} />;
}

it("takes a typed answer on a cross menu and sends it as the module's text answer", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.listTasks = async () => [askingEnvelope];
  const provideInput = vi.fn().mockResolvedValue({ ...asking, status: "running", interaction: null });
  backend.user.provideInput = provideInput;
  render(<Harness source={backend.user} />);
  // A reloaded pending plan asks the user to look before continuing; nothing is resubmitted.
  fireEvent.click(await screen.findByRole("button", { name: "继续办理" }));
  // The promise line shows even when the menu has no plan body (adopt screen).
  expect(await screen.findByText(PLAN_PROMISE)).toBeTruthy();
  const label = await screen.findByText(CROSS_ANSWER_LABEL);
  expect(screen.getByText("停止本次安排")).toBeTruthy();
  // This menu asks for an amount, so the count hint stays on the quantity screen.
  expect(screen.queryByText("请填正整数，例如 2")).toBeNull();
  const input = screen.getByLabelText(CROSS_ANSWER_LABEL);
  fireEvent.change(input, { target: { value: "1500" } });
  fireEvent.click(screen.getByRole("button", { name: "填好了，继续" }));
  await waitFor(() => expect(provideInput).toHaveBeenCalledExactlyOnceWith(asking.task_id, expect.objectContaining({
    interaction_id: "CX1", text: "1500",
  })));
  expect(provideInput.mock.calls[0][1].request_id).toEqual(expect.any(String));
  expect(label).toBeTruthy();
});

it("does not put a text box on a cross menu that already offers enough choices", async () => {
  const many = { ...askingEnvelope, task: { ...asking, interaction: {
    ...asking.interaction!,
    options: [{ id: "a", label: "取消视频会员" }, { id: "b", label: "取消音乐会员" }, { id: "c", label: "都不退" }],
  } } } as TaskEnvelope;
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.listTasks = async () => [many];
  render(<Harness source={backend.user} />);
  fireEvent.click(await screen.findByRole("button", { name: "继续办理" }));
  await screen.findByText("取消视频会员");
  expect(screen.queryByText(CROSS_ANSWER_LABEL)).toBeNull();
});

it("never marks a step as current when the server sends no interaction id", () => {
  // The API serialises nulls, so an absent interaction id must not match the null
  // child_task_id of steps that have not started yet.
  const noTarget = {
    ...plan,
    active_step_id: null,
    interaction_task_id: null,
    steps: plan.steps.map((step) => ({ ...step, child_task_id: null })),
  };
  render(<CrossPlanCard view={noTarget} task={{ ...parent, status: "waiting_input" }}
    childTask={() => undefined} />);
  expect(screen.getAllByRole("listitem").map((item) => item.getAttribute("aria-current")))
    .toEqual(plan.steps.map(() => null));
});
