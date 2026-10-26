// Ticket v05-cross-frontend/02: the birthday page consumes what the backend
// publishes — interaction options routed through F10, one error tier per public
// code, and the bank facts carried by CrossStep. No option is matched by label
// and no amount is computed by the page.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import type { ConfirmationView, CrossTaskView, VerificationView } from "../contracts";
import { CrossPlanCard } from "./components/CrossPlanCard";
import { DeliveryCard } from "./components/DeliveryCard";
import { TaskBlock } from "./components/TaskBlock";
import { crossSlot } from "./slots/crossSlot";
import { createDemoBackend } from "./stub/demoBackend";
import { useConversation } from "./useConversation";
import { CROSS_ANSWER_LABEL, PLAN_STOPPED } from "./cross";
import type { ShellDataSource, ShellTask, TaskEnvelope } from "./types";

const EDIT_OPTION = { id: "birthday-edit-8f1c", label: "修改尚未提交的部分" };

const birthday: CrossTaskView = {
  scenario: "birthday",
  plan_revision: 4,
  summary: "生日安排进行中。",
  steps: [
    { step_id: "birthday-freeze", action: "bank.freeze_funds", status: "succeeded", amount_fen: 50000 },
    { step_id: "birthday-order-0", action: "bank.create_order", status: "succeeded", amount_fen: 19900, order_id: "ORDER-01", payment_status: "paid" },
    { step_id: "birthday-capture-0", action: "bank.capture_frozen", status: "succeeded", amount_fen: 19900, order_id: "ORDER-01", payment_status: "paid" },
    { step_id: "birthday-order-1", action: "bank.create_order", status: "succeeded", amount_fen: 26800, order_id: "ORDER-02", payment_status: "unpaid" },
    { step_id: "birthday-consumed", action: "bank.get_freeze", status: "succeeded", amount_fen: 46700 },
    { step_id: "birthday-release", action: "bank.release_frozen", status: "succeeded", amount_fen: 3300 },
    { step_id: "birthday-remaining", action: "bank.get_freeze", status: "succeeded", amount_fen: 0 },
  ],
};

const confirmation: ConfirmationView = {
  confirmation_id: "conf-1",
  task_id: "birthday",
  confirmation_version: 2,
  display_fields: [
    { name: "payer", label: "付款账户", value_text: "尾号 8842" },
    { name: "amount", label: "冻结金额", value_text: "¥500.00" },
  ],
  created_at: "2026-10-26T04:00:00Z",
  expires_at: "2026-10-26T04:10:00Z",
  decision: "pending",
};

const verification: VerificationView = {
  challenge_id: "chal-1",
  task_id: "birthday",
  created_at: "2026-10-26T04:00:00Z",
  summary: {
    operation_id: "op-1",
    action_revision: 1,
    source_confirmation_id: "conf-1",
    source_confirmation_version: 2,
    action_name: "bank.freeze_funds",
    amount_fen: 50000,
    payee: null,
    display_fields: confirmation.display_fields,
  },
  required_methods: ["code"],
  code_expires_at: "2026-10-26T04:10:00Z",
  face_started_at: null,
  face_expires_at: null,
  code_result: "pending",
  face_result: "not_required",
  challenge_status: "pending",
  consecutive_code_failures: 0,
};

function task(overrides: Partial<ShellTask>): ShellTask {
  return {
    task_id: "birthday",
    run_id: "run-1",
    status: "waiting_approval",
    data: birthday,
    message: "请核对并确认。",
    interaction: null,
    error: null,
    allowed_actions: [],
    recovery_required: false,
    recovery_reason: null,
    module: "cross",
    thread_id: "thread",
    demo_round_id: "round",
    snapshot_at: "2026-10-26T04:00:00Z",
    task_revision: 5,
    cancel_requested: false,
    ...overrides,
  };
}

const frozenCard = task({
  interaction: {
    interaction_id: "i-freeze", kind: "confirmation", prompt: "请确认：冻结生日安排资金",
    required_fields: [], options: [EDIT_OPTION], record_ref: "conf-1",
  },
  // The published option belongs to the confirmation card; answering it is not
  // an ordinary input, so the page must not require provide_input here.
  allowed_actions: ["confirm", "cancel"],
});

const treatedCard = task({
  interaction: {
    interaction_id: "i-verify", kind: "verification", prompt: "请先完成验证。",
    required_fields: [], options: [EDIT_OPTION], record_ref: "chal-1",
  },
  allowed_actions: ["verify", "cancel"],
});

// The birthday delivery step as the server publishes it (birthday._ask_delivery):
// a controlled form, not a text answer in chat.
const DELIVERY_PROMPT = "请在配送信息专用表单填写收件人、电话和地址，提交后继续选择商品。配送原文不要发到聊天里。";
const RAW = { recipient_name: "李演示", phone: "13800005678", address: "演示市演示区示例路1号" };
const MASKED = [
  { name: "recipient", label: "收件人", value_text: "李*" },
  { name: "phone", label: "联系电话", value_text: "****5678" },
  { name: "address", label: "地址", value_text: "演示****" },
];
const deliveryAsk = task({
  status: "waiting_input",
  data: null,
  message: DELIVERY_PROMPT,
  interaction: {
    interaction_id: "i-delivery", kind: "input", prompt: DELIVERY_PROMPT,
    required_fields: ["delivery"],
    options: [{ id: "o-stop", label: "停止本次安排" }],
    record_ref: null,
  },
  allowed_actions: ["provide_input", "cancel"],
});
const pickAsk = task({
  status: "waiting_input",
  task_revision: 6,
  data: null,
  message: "请选择要买的商品。",
  interaction: {
    interaction_id: "i-pick", kind: "input", prompt: "请选择要买的商品。",
    required_fields: ["cross_selection"],
    options: [{ id: "o-flower", label: "康乃馨花束 · 199.00 元" }],
    record_ref: null,
  },
  allowed_actions: ["provide_input", "cancel"],
});
const REF = "deliver-ref-9f2c1d7a";

function deliveryResponse(card: ShellTask) {
  return { detail_ref: REF, display_fields: MASKED, candidates: null, task: card };
}

function fillDelivery() {
  fireEvent.change(screen.getByLabelText("收件人"), { target: { value: RAW.recipient_name } });
  fireEvent.change(screen.getByLabelText("联系电话"), { target: { value: RAW.phone } });
  fireEvent.change(screen.getByLabelText("详细地址"), { target: { value: RAW.address } });
}

// Everything a reload could read back: both web storages and the address bar.
function storedText(): string {
  const values = [window.location.href];
  for (const area of [localStorage, sessionStorage]) {
    for (let index = 0; index < area.length; index += 1) {
      const key = area.key(index)!;
      values.push(key, area.getItem(key) ?? "");
    }
  }
  return values.join("\n");
}

function envelope(value: ShellTask): TaskEnvelope {
  return { task: value, module: "cross", timelineAt: value.snapshot_at };
}

function Harness({ source, taskId }: { source: ShellDataSource; taskId: string }) {
  const conversation = useConversation(source);
  const current = conversation.tasks.get(taskId);
  if (conversation.booting || !current) return null;
  return <TaskBlock envelope={current} slot={crossSlot} origin="real-api" conversation={conversation} />;
}

// The same page plus the "enter this session again" action, so a test can show
// what survives a session change without reaching into the hook's state.
function SessionHarness({ source, taskId }: { source: ShellDataSource; taskId: string }) {
  const conversation = useConversation(source);
  const current = conversation.tasks.get(taskId);
  if (conversation.booting || !current) return null;
  return (
    <div>
      <button type="button" onClick={() => void conversation.actions.reenter()}>重新进入会话</button>
      <TaskBlock envelope={current} slot={crossSlot} origin="real-api" conversation={conversation} />
    </div>
  );
}

async function mountCard(source: ShellDataSource, card: ShellTask, View = Harness) {
  source.listTasks = async () => [envelope(card)];
  source.getTask = async () => envelope(card);
  source.listTaskRecords = async (taskId: string) => ({
    task_id: taskId,
    confirmations: card.interaction?.kind === "confirmation" ? [confirmation] : [],
    verifications: card.interaction?.kind === "verification" ? [verification] : [],
  });
  source.listChildren = async () => [];
  render(<View source={source} taskId={card.task_id} />);
  // A reloaded unfinished task asks the user to look before continuing; that
  // lookup is not an approval and does not resubmit anything.
  fireEvent.click(await screen.findByRole("button", { name: "查看原任务" }));
}

beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("answers a server-published confirmation option through F10 and swaps in the returned card", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const edited = task({
    status: "waiting_input",
    task_revision: 6,
    message: "原来等待的确认/验证已安全退出，原动作没有提交；只调整尚未成单且没有在途的部分。",
    interaction: {
      interaction_id: "i-edit", kind: "input",
      prompt: "只调整尚未成单且没有在途的部分。\n已选商品：\n· 康乃馨花束 ×1（单价 199 元，小计 199 元）",
      required_fields: ["cross_selection"],
      options: [{ id: "o-qty", label: "改数量：康乃馨花束（当前 1 件）" }, { id: "o-done", label: "就选这些，继续" }],
      record_ref: null,
    },
    allowed_actions: ["provide_input", "cancel"],
  });
  const provideInput = vi.fn().mockResolvedValue(edited);
  backend.user.provideInput = provideInput;
  const send = vi.spyOn(backend.user, "sendMessage");
  await mountCard(backend.user, frozenCard);

  fireEvent.click(await screen.findByRole("button", { name: EDIT_OPTION.label }));
  await waitFor(() => expect(provideInput).toHaveBeenCalledTimes(1));
  const [taskId, body] = provideInput.mock.calls[0];
  expect(taskId).toBe("birthday");
  expect(body).toMatchObject({ interaction_id: "i-freeze", selected_option_id: EDIT_OPTION.id });
  // The card answer carries no free text and starts no chat message.
  expect(body).not.toHaveProperty("text");
  expect(send).not.toHaveBeenCalled();

  // The same task's new revision replaces the card as a normal input menu.
  expect(await screen.findByRole("button", { name: "改数量：康乃馨花束（当前 1 件）" })).toBeTruthy();
  expect(screen.getByText("查看之前的确认内容")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "确认办理" })).toBeNull();
});

it("answers the same published option on a verification card without asking for a code", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const edited = task({ status: "waiting_input", task_revision: 6, interaction: {
    interaction_id: "i-edit", kind: "input", prompt: "只调整尚未成单且没有在途的部分。",
    required_fields: ["cross_selection"], options: [{ id: "o-done", label: "按新方案继续" }], record_ref: null,
  }, allowed_actions: ["provide_input", "cancel"] });
  const provideInput = vi.fn().mockResolvedValue(edited);
  backend.user.provideInput = provideInput;
  await mountCard(backend.user, treatedCard);

  expect(screen.getByText("验证码")).toBeTruthy();
  fireEvent.click(await screen.findByRole("button", { name: EDIT_OPTION.label }));
  await waitFor(() => expect(provideInput).toHaveBeenCalledTimes(1));
  expect(provideInput.mock.calls[0][1]).toMatchObject({ interaction_id: "i-verify", selected_option_id: EDIT_OPTION.id });
  expect(provideInput.mock.calls[0][1]).not.toHaveProperty("text");
  expect(await screen.findByRole("button", { name: "按新方案继续" })).toBeTruthy();
});

it("replays one F10 request after a dependency failure and never turns it into a message", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const edited = task({ status: "waiting_input", task_revision: 6, interaction: {
    interaction_id: "i-edit", kind: "input", prompt: "只调整尚未成单且没有在途的部分。",
    required_fields: ["cross_selection"], options: [{ id: "o-done", label: "按新方案继续" }], record_ref: null,
  }, allowed_actions: ["provide_input", "cancel"] });
  const provideInput = vi.fn()
    .mockRejectedValueOnce(new ApiError(503, "CROSS_UNAVAILABLE", "暂时没有收到修改结果。"))
    .mockResolvedValueOnce(edited);
  backend.user.provideInput = provideInput;
  const send = vi.spyOn(backend.user, "sendMessage");
  await mountCard(backend.user, frozenCard);

  fireEvent.click(await screen.findByRole("button", { name: EDIT_OPTION.label }));
  // The body had no reason, so the page shows its message plus the 503 tier step.
  expect(await screen.findByText("暂时没有收到修改结果。原任务结果待核实，请查询原任务。")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: EDIT_OPTION.label }));
  await waitFor(() => expect(provideInput).toHaveBeenCalledTimes(2));
  expect(provideInput.mock.calls[1]).toEqual(provideInput.mock.calls[0]);
  expect(send).not.toHaveBeenCalled();
});

it("shows the server's own reason verbatim and adds a refresh step only when it is missing", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const provideInput = vi.fn()
    .mockRejectedValueOnce(new ApiError(409, "INTERACTION_STALE", "generic",
      "当前确认或验证卡已更新，本次未进入修改；请刷新任务后按当前卡重新操作。"))
    .mockRejectedValueOnce(new ApiError(409, "TRANSITION_PENDING", "这张卡正在处理另一次修改。"));
  backend.user.provideInput = provideInput;
  await mountCard(backend.user, frozenCard);

  fireEvent.click(await screen.findByRole("button", { name: EDIT_OPTION.label }));
  expect(await screen.findByText("当前确认或验证卡已更新，本次未进入修改；请刷新任务后按当前卡重新操作。")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: EDIT_OPTION.label }));
  // No reason in the body: the page keeps the server message and adds the 409
  // tier's next step instead of inventing a new refusal.
  expect(await screen.findByText("这张卡正在处理另一次修改。请刷新这项任务后重试。")).toBeTruthy();
});

it("reads orders, payment state and bank amounts from the birthday steps only", () => {
  render(<CrossPlanCard view={birthday} task={task({ data: birthday })} childTask={() => undefined} />);
  expect(screen.getByText("冻结资金")).toBeTruthy();
  expect(screen.getByText("¥500.00")).toBeTruthy();
  expect(screen.getAllByText("创建订单")).toHaveLength(2);
  expect(screen.getByText("付款")).toBeTruthy();
  expect(screen.getAllByText("¥199.00")).toHaveLength(2);
  expect(screen.getByText("订单号 ORDER-02")).toBeTruthy();
  expect(screen.getByText("未付款")).toBeTruthy();
  expect(screen.getAllByText("已付款")).toHaveLength(2);
  expect(screen.getByText("已消费")).toBeTruthy();
  expect(screen.getByText("¥467.00")).toBeTruthy();
  expect(screen.getByText("释放冻结资金")).toBeTruthy();
  expect(screen.getByText("¥33.00")).toBeTruthy();
  expect(screen.getByText("冻结余款")).toBeTruthy();
  expect(screen.getByText("¥0.00")).toBeTruthy();
  // The page never says the arrangement is finished just because rows exist.
  expect(screen.queryByText("已完成")).toBeNull();
});

it("keeps unknown birthday facts as 待核实 without filling zero or 已办结", () => {
  const unknown: CrossTaskView = {
    ...birthday,
    steps: [
      { step_id: "birthday-freeze", action: "bank.freeze_funds", status: "needs_attention" },
      { step_id: "birthday-order-0", action: "bank.create_order", status: "needs_attention", order_id: "ORDER-01" },
      { step_id: "birthday-release", action: "bank.release_frozen", status: "needs_attention" },
      { step_id: "birthday-remaining", action: "bank.get_freeze", status: "needs_attention" },
    ],
  };
  const waiting = task({ status: "needs_attention", data: unknown, allowed_actions: ["query"] });
  render(<CrossPlanCard view={unknown} task={waiting} childTask={() => undefined} onQueryChild={() => undefined} />);
  expect(screen.getAllByText("! 结果待核实")).toHaveLength(4);
  expect(screen.getAllByText("金额待核实")).toHaveLength(4);
  expect(screen.getByText("订单号 ORDER-01")).toBeTruthy();
  // Unknown is never zero-filled and never reported as done.
  expect(screen.queryByText("¥0.00")).toBeNull();
  expect(screen.queryByText("已消费")).toBeNull();
  expect(screen.queryByText("已办结")).toBeNull();
});

it("presents a stopped birthday plan as no new work plus the bank receipts", () => {
  const stopped = task({
    status: "partially_succeeded",
    data: { ...birthday, stop_reason: "user_cancelled" },
    message: "部分完成，后续已停止：花束订单已创建并已付款 199 元（交易 9f2c…）。已付款项不退；以上是订单与资金事实，不代表商品已送达。",
    allowed_actions: ["query"],
  });
  render(<CrossPlanCard view={stopped.data as CrossTaskView} task={stopped} childTask={() => undefined} />);
  expect(screen.getByText(/部分完成，后续已停止/)).toBeTruthy();
  expect(screen.getByText(PLAN_STOPPED)).toBeTruthy();
  expect(screen.getByText("订单号 ORDER-02")).toBeTruthy();
  expect(screen.getAllByText("¥199.00")).toHaveLength(2);
  expect(screen.getByText("未付款")).toBeTruthy();
  // Stopping is not a refund, a cancellation or a delivery claim.
  expect(screen.queryByText(/已退款|退款成功/)).toBeNull();
  expect(screen.queryByText(/订单已取消/)).toBeNull();
});

it("shows the adopted personal budget with its version and facts time, and a candidate apart", () => {
  const adopted: CrossTaskView = {
    ...birthday,
    budget: {
      budget_ref: { budget_id: "budget-1", version: 3 },
      purpose: "本月当前账户全部消费",
      scope: { account_ids: ["A1"], start_at: "2026-10-01T00:00:00Z", end_at: "2026-11-01T00:00:00Z" },
      personal_limit_fen: 100000,
      used_fen: 30000,
      remaining_fen: 70000,
      facts_as_of: "2026-10-26T04:00:00Z",
      adopted: true,
    },
  };
  const view = render(<CrossPlanCard view={adopted} task={task({ data: adopted })} childTask={() => undefined} />);
  expect(screen.getByText("已采用")).toBeTruthy();
  expect(screen.getByText("预算限额")).toBeTruthy();
  expect(screen.getByText("账单已用")).toBeTruthy();
  expect(screen.getByText("账单剩余")).toBeTruthy();
  expect(screen.getByText("版本")).toBeTruthy();
  expect(screen.getByText("版本").nextElementSibling?.textContent).toBe("3");
  expect(screen.getByText("截至")).toBeTruthy();

  const candidate: CrossTaskView = { ...adopted, budget: { ...adopted.budget!, adopted: false, budget_ref: null } };
  view.rerender(<CrossPlanCard view={candidate} task={task({ data: candidate })} childTask={() => undefined} />);
  expect(screen.getByText("候选、尚未采用")).toBeTruthy();
  expect(screen.queryByText("已采用")).toBeNull();
  expect(screen.queryByText("版本")).toBeNull();
});

it("takes a typed quantity as a positive integer and leaves the refusal to the server", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const accept = vi.fn();
  backend.user.provideInput = accept;
  const asking = task({
    status: "waiting_input",
    data: null,
    message: "请输入「康乃馨花束」的数量（正整数，如 2）：",
    interaction: {
      interaction_id: "i-qty", kind: "input", prompt: "请输入「康乃馨花束」的数量（正整数，如 2）：",
      required_fields: ["cross_selection"],
      options: [{ id: "o-cancel", label: "取消改数量" }, { id: "o-stop", label: "停止本次安排" }],
      record_ref: null,
    },
    allowed_actions: ["provide_input", "cancel"],
  });
  await mountCard(backend.user, asking);
  const input = screen.getByLabelText(CROSS_ANSWER_LABEL) as HTMLInputElement;
  expect(input.getAttribute("inputmode")).toBe("numeric");

  fireEvent.change(input, { target: { value: "0" } });
  expect(screen.getByRole("button", { name: "填好了，继续" }).hasAttribute("disabled")).toBe(true);
  fireEvent.change(input, { target: { value: "2" } });
  const submit = screen.getByRole("button", { name: "填好了，继续" });
  expect(submit.hasAttribute("disabled")).toBe(false);
  await act(async () => { fireEvent.click(submit); });
  await waitFor(() => expect(accept).toHaveBeenCalledTimes(1));
  expect(accept.mock.calls[0][1]).toMatchObject({ interaction_id: "i-qty", text: "2" });
  expect(accept.mock.calls[0][1]).not.toHaveProperty("selected_option_id");
});

it("renders the parked retired state from the server menu without claiming an outcome", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.provideInput = vi.fn();
  const parked = task({
    status: "waiting_input",
    message: "原动作已由平台安全撤离（该笔未提交），需等待平台接缝就绪后才能继续。本任务与已发生的订单/付款事实保留，未收尾、未释放冻结；可稍后再试，或直接在任务卡片上取消本次安排。",
    interaction: {
      interaction_id: "i-parked", kind: "input", prompt: "原动作已由平台安全撤离（该笔未提交），需等待平台接缝就绪后才能继续。本任务与已发生的订单/付款事实保留，未收尾、未释放冻结；可稍后再试，或直接在任务卡片上取消本次安排。",
      required_fields: ["cross_selection"],
      options: [{ id: "o-retry", label: "稍后再试（保留现状）" }],
      record_ref: null,
    },
    allowed_actions: ["provide_input", "cancel"],
  });
  await mountCard(backend.user, parked);
  expect(screen.getByText(/原动作已由平台安全撤离/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "稍后再试（保留现状）" })).toBeTruthy();
  // The retained bank fact stays visible; the task is not shown as done, failed or cancelled.
  expect(screen.getByText("¥500.00")).toBeTruthy();
  expect(screen.queryByText("已取消")).toBeNull();
  expect(screen.queryByText("没有办成")).toBeNull();
});

it("collects delivery facts in a dedicated form instead of the generic text box", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const submitDetails = vi.fn();
  backend.user.submitDetails = submitDetails;
  backend.user.provideInput = vi.fn();
  await mountCard(backend.user, deliveryAsk);

  expect(screen.getByLabelText("收件人")).toBeTruthy();
  expect(screen.getByLabelText("联系电话")).toBeTruthy();
  expect(screen.getByLabelText("详细地址")).toBeTruthy();
  expect(screen.getByRole("button", { name: "配送资料填好了，继续选商品" })).toBeTruthy();
  // The generic cross text answer and its "补充并继续" form never appear here.
  expect(screen.queryByLabelText(CROSS_ANSWER_LABEL)).toBeNull();
  expect(screen.queryByRole("button", { name: "补充并继续" })).toBeNull();
  // The server's own stop choice stays reachable next to the form.
  expect(screen.getByRole("button", { name: "停止本次安排" })).toBeTruthy();
});

it("continues only the interaction that issued the reference", () => {
  const handoff = { detail_ref: REF, interaction_id: "i-delivery", fields: MASKED };
  const props = {
    id: "delivery",
    active: true,
    busy: false,
    handoff,
    error: "",
    onSelect: () => undefined,
    onSubmit: async () => false,
    onContinue: async () => false,
  };
  const view = render(<DeliveryCard interaction={deliveryAsk.interaction!} {...props} />);
  expect(screen.getByRole("button", { name: "资料不用再填，点下面继续" })).toBeTruthy();

  // A newer interaction on the same task never gets the earlier reference.
  view.rerender(<DeliveryCard interaction={{ ...deliveryAsk.interaction!, interaction_id: "i-delivery-2" }} {...props} />);
  expect(screen.queryByRole("button", { name: "资料不用再填，点下面继续" })).toBeNull();
  expect((screen.getByLabelText("收件人") as HTMLInputElement).value).toBe("");
});

it("stops at the blank field, marks it and writes no sentence of its own", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const submitDetails = vi.fn();
  backend.user.submitDetails = submitDetails;
  await mountCard(backend.user, deliveryAsk);

  fireEvent.change(screen.getByLabelText("收件人"), { target: { value: RAW.recipient_name } });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "配送资料填好了，继续选商品" }));
  });
  const phone = screen.getByLabelText("联系电话");
  const address = screen.getByLabelText("详细地址");
  // The blank fields are reported through their own invalid state; the approved
  // labels and the server's own message carry the rest.
  expect(phone.getAttribute("aria-invalid")).toBe("true");
  expect(address.getAttribute("aria-invalid")).toBe("true");
  expect(phone.getAttribute("aria-required")).toBe("true");
  expect(screen.getByLabelText("收件人").getAttribute("aria-invalid")).toBe("false");
  expect(document.body.textContent).not.toMatch(/请填写/);
  expect(document.activeElement).toBe(phone);
  expect(submitDetails).not.toHaveBeenCalled();
});

it("sends the delivery facts only to F36, then continues F10 with the reference", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const submitDetails = vi.fn().mockResolvedValue(deliveryResponse(deliveryAsk));
  const provideInput = vi.fn().mockResolvedValue(pickAsk);
  backend.user.submitDetails = submitDetails;
  backend.user.provideInput = provideInput;
  const send = vi.spyOn(backend.user, "sendMessage");
  await mountCard(backend.user, deliveryAsk);

  fillDelivery();
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "配送资料填好了，继续选商品" }));
  });
  await waitFor(() => expect(provideInput).toHaveBeenCalledTimes(1));

  const [taskId, body] = submitDetails.mock.calls[0];
  expect(taskId).toBe("birthday");
  expect(body).toMatchObject({ interaction_id: "i-delivery", kind: "delivery", fields: RAW });
  expect(typeof body.request_id).toBe("string");
  expect(body).not.toHaveProperty("text");

  // F10 carries only the reference, never the typed facts and no chat message.
  expect(provideInput).toHaveBeenCalledWith("birthday", expect.objectContaining({
    interaction_id: "i-delivery", text: REF,
  }));
  expect(provideInput.mock.calls[0][1]).not.toHaveProperty("selected_option_id");
  expect(send).not.toHaveBeenCalled();

  expect(await screen.findByRole("button", { name: "康乃馨花束 · 199.00 元" })).toBeTruthy();
  expect(document.body.textContent).not.toContain(RAW.recipient_name);
  expect(storedText()).not.toContain(RAW.recipient_name);
  expect(storedText()).not.toContain(RAW.phone);
  expect(storedText()).not.toContain(RAW.address);
  // Once the next step owns the flow, the reference is no longer kept here either.
  await waitFor(() => expect(storedText()).not.toContain(REF));
});

it("shows the server mask and continues the same F10 reference when the first handoff fails", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.submitDetails = vi.fn().mockResolvedValue(deliveryResponse(deliveryAsk));
  const provideInput = vi.fn()
    .mockRejectedValueOnce(new ApiError(503, "DEPENDENCY_UNAVAILABLE", "暂时没有收到选品结果。"))
    .mockResolvedValueOnce(pickAsk);
  backend.user.provideInput = provideInput;
  await mountCard(backend.user, deliveryAsk);

  fillDelivery();
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "配送资料填好了，继续选商品" }));
  });

  expect(await screen.findByRole("button", { name: "资料不用再填，点下面继续" })).toBeTruthy();
  expect(screen.getByText("李*")).toBeTruthy();
  expect(screen.getByText("****5678")).toBeTruthy();
  // The edited original is gone from the page once F36 took it.
  expect(document.body.textContent).not.toContain(RAW.recipient_name);
  // The failure is shown here, not as a separate page error.
  expect(screen.getByText(/暂时没有收到选品结果/)).toBeTruthy();

  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "资料不用再填，点下面继续" }));
  });
  await waitFor(() => expect(provideInput).toHaveBeenCalledTimes(2));
  // A retry keeps the same request number and still sends only the reference.
  expect(provideInput.mock.calls[1]).toEqual(provideInput.mock.calls[0]);
  expect(await screen.findByRole("button", { name: "康乃馨花束 · 199.00 元" })).toBeTruthy();
});

it("asks for the form again only when the server cannot resolve the reference", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.submitDetails = vi.fn().mockResolvedValue(deliveryResponse(deliveryAsk));
  const refused = task({
    ...deliveryAsk,
    task_revision: 6,
    message: "查不到对应的配送信息，请通过专用表单重新提交，或停止本次安排。",
    interaction: { ...deliveryAsk.interaction!, interaction_id: "i-delivery-2" },
  });
  backend.user.provideInput = vi.fn().mockResolvedValue(refused);
  await mountCard(backend.user, deliveryAsk);

  fillDelivery();
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "配送资料填好了，继续选商品" }));
  });

  expect(await screen.findByLabelText("收件人")).toBeTruthy();
  expect(screen.getByText(/查不到对应的配送信息/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "资料不用再填，点下面继续" })).toBeNull();
  // F36 already owned the original, so the form comes back empty instead of
  // showing the typed recipient, phone and address again.
  expect((screen.getByLabelText("收件人") as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText("联系电话") as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText("详细地址") as HTMLInputElement).value).toBe("");
  // The dead reference is not kept on this device.
  await waitFor(() => expect(storedText()).not.toContain(REF));
});

it("keeps the F36 reference and mask in memory only, never in web storage", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.submitDetails = vi.fn().mockResolvedValue(deliveryResponse(deliveryAsk));
  backend.user.provideInput = vi.fn()
    .mockRejectedValue(new ApiError(503, "DEPENDENCY_UNAVAILABLE", "暂时没有收到选品结果。"));
  await mountCard(backend.user, deliveryAsk);

  fillDelivery();
  const localKeys = Object.keys(localStorage).sort();
  const sessionKeys = Object.keys(sessionStorage).sort();
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "配送资料填好了，继续选商品" }));
  });

  // The handoff stays for the next click in this page session only.
  expect(await screen.findByRole("button", { name: "资料不用再填，点下面继续" })).toBeTruthy();
  expect(screen.getByText("李*")).toBeTruthy();
  expect(Object.keys(localStorage).sort()).toEqual(localKeys);
  expect(Object.keys(sessionStorage).sort()).toEqual(sessionKeys);
  expect(Object.keys(localStorage).some((key) => key.startsWith("fe-delivery:"))).toBe(false);
  expect(Object.keys(sessionStorage).some((key) => key.startsWith("fe-delivery:"))).toBe(false);
  expect(storedText()).not.toContain(REF);
  expect(storedText()).not.toContain("李*");
  expect(storedText()).not.toContain("****5678");
});

it("asks for the delivery facts again after a reload instead of reusing the reference", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.submitDetails = vi.fn().mockResolvedValue(deliveryResponse(deliveryAsk));
  const provideInput = vi.fn()
    .mockRejectedValue(new ApiError(503, "DEPENDENCY_UNAVAILABLE", "暂时没有收到选品结果。"));
  backend.user.provideInput = provideInput;
  await mountCard(backend.user, deliveryAsk);

  fillDelivery();
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "配送资料填好了，继续选商品" }));
  });
  expect(await screen.findByRole("button", { name: "资料不用再填，点下面继续" })).toBeTruthy();

  // A reload is a fresh page session: the in-memory handoff is gone, so the
  // server's own delivery step is shown again with nothing continued on its own.
  cleanup();
  await mountCard(backend.user, deliveryAsk);

  expect(await screen.findByLabelText("收件人")).toBeTruthy();
  expect(screen.getByText(/请在配送信息专用表单填写收件人/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "资料不用再填，点下面继续" })).toBeNull();
  expect(screen.queryByText("李*")).toBeNull();
  expect(provideInput).toHaveBeenCalledTimes(1);
});

it("clears the form when F36 answers, so a dropped reference returns to empty boxes", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.submitDetails = vi.fn().mockResolvedValue(deliveryResponse(deliveryAsk));
  const provideInput = vi.fn().mockRejectedValue(new ApiError(409, "INTERACTION_STALE", "stale",
    "这条配送衔接已经失效，请按当前页面重新填写。"));
  backend.user.provideInput = provideInput;
  await mountCard(backend.user, deliveryAsk);

  fillDelivery();
  // The refresh keeps the same interaction, so the same card instance returns the
  // form: only clearing at F36 success can keep the typed facts out of it.
  backend.user.getTask = async () => envelope(task({
    ...deliveryAsk,
    task_revision: 6,
    message: "配送资料需要按当前页面重新填写。",
  }));
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "配送资料填好了，继续选商品" }));
  });

  expect(await screen.findByLabelText("收件人")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "资料不用再填，点下面继续" })).toBeNull();
  expect((screen.getByLabelText("收件人") as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText("联系电话") as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText("详细地址") as HTMLInputElement).value).toBe("");
  expect(document.body.textContent).not.toContain(RAW.recipient_name);
  expect(document.body.textContent).not.toContain(RAW.phone);
  expect(provideInput).toHaveBeenCalledTimes(1);
  expect(storedText()).not.toContain(REF);
});

it("drops the reference on a stale interaction and follows the replaced snapshot", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.submitDetails = vi.fn().mockResolvedValue(deliveryResponse(deliveryAsk));
  const provideInput = vi.fn().mockRejectedValue(new ApiError(409, "INTERACTION_STALE", "stale",
    "这条配送衔接已经失效，请按当前页面重新填写。"));
  backend.user.provideInput = provideInput;
  const replaced = task({
    ...deliveryAsk,
    task_revision: 6,
    message: "配送资料需要按当前页面重新填写。",
    interaction: {
      ...deliveryAsk.interaction!,
      interaction_id: "i-delivery-2",
      prompt: "请按当前页面重新填写配送资料。",
    },
  });
  await mountCard(backend.user, deliveryAsk);
  // The refresh reads the replaced snapshot, not the card the page started from.
  backend.user.getTask = async () => envelope(replaced);

  fillDelivery();
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "配送资料填好了，继续选商品" }));
  });

  // The refreshed interaction never inherits the old reference, even though the
  // task still asks for delivery: the form is the only way on.
  expect(await screen.findByText("请按当前页面重新填写配送资料。")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "资料不用再填，点下面继续" })).toBeNull();
  expect((screen.getByLabelText("收件人") as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText("联系电话") as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText("详细地址") as HTMLInputElement).value).toBe("");
  expect(screen.getByText("这条配送衔接已经失效，请按当前页面重新填写。")).toBeTruthy();
  // The dropped reference is not replayed on its own.
  expect(provideInput).toHaveBeenCalledTimes(1);
  expect(document.body.textContent).not.toContain(REF);
  expect(storedText()).not.toContain(REF);
});

it("does not carry the reference into another session", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  backend.user.submitDetails = vi.fn().mockResolvedValue(deliveryResponse(deliveryAsk));
  const provideInput = vi.fn()
    .mockRejectedValue(new ApiError(503, "DEPENDENCY_UNAVAILABLE", "暂时没有收到选品结果。"));
  backend.user.provideInput = provideInput;
  await mountCard(backend.user, deliveryAsk, SessionHarness);

  fillDelivery();
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "配送资料填好了，继续选商品" }));
  });
  expect(await screen.findByRole("button", { name: "资料不用再填，点下面继续" })).toBeTruthy();

  // A new session re-checks the recovery gate and starts over: the old reference
  // is neither shown nor continued.
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "重新进入会话" }));
  });
  fireEvent.click(await screen.findByRole("button", { name: "查看原任务" }));
  expect(await screen.findByLabelText("收件人")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "资料不用再填，点下面继续" })).toBeNull();
  expect((screen.getByLabelText("收件人") as HTMLInputElement).value).toBe("");
  expect(screen.queryByText("李*")).toBeNull();
  expect(provideInput).toHaveBeenCalledTimes(1);
});
