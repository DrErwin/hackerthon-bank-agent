import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { ApiError } from "../api";
import { AdminDemoPage } from "./AdminDemoPage";
import { AssistantPage } from "./AssistantPage";
import { createSlotRegistry, genericSlot } from "./slots";
import { billsSlot } from "./slots/billsSlot";
import { transferSlot } from "./slots/transferDemoSlot";
import { createDemoBackend } from "./stub/demoBackend";
import type { DemoBackend } from "./stub/demoBackend";

const slots = createSlotRegistry([transferSlot, billsSlot]);

function makeBackend(): DemoBackend {
  return createDemoBackend({ replyDelayMs: 0, submitMs: 30, bankMs: 30, tickMs: 20 });
}

function renderPage(backend: DemoBackend) {
  return render(<AssistantPage source={backend.user} slots={slots} />);
}

async function sendText(text: string) {
  const input = await screen.findByRole("textbox", { name: "输入您想办的事" });
  await waitFor(() => expect(input.hasAttribute("disabled")).toBe(false));
  fireEvent.change(input, { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
}

async function choosePayeeAndAccount() {
  fireEvent.click(await screen.findByRole("button", { name: /演示账户.*1234/ }));
  fireEvent.click(await screen.findByRole("button", { name: /妈妈.*6688/ }));
  await screen.findByRole("button", { name: "确认办理" });
}

async function reachVerification() {
  await sendText("转给妈妈500块");
  await choosePayeeAndAccount();
  fireEvent.click(await screen.findByRole("button", { name: "确认办理" }));
  return screen.findByRole("heading", { name: "请完成两项身份验证" });
}

async function passCode() {
  fireEvent.change(await screen.findByLabelText("请输入 6 位验证码"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "提交验证码" }));
  fireEvent.click(await screen.findByRole("button", { name: "开始模拟人脸验证" }));
  await screen.findByText("请稍等，工作人员会帮您完成刷脸验证，完成后这里会自动更新。");
}

async function adminAnswer(backend: DemoBackend, result: "passed" | "failed") {
  await backend.admin.enterAdmin({ request_id: crypto.randomUUID() });
  const [challenge] = backend.admin.listPendingFaceChallenges();
  expect(challenge).toBeTruthy();
  await backend.admin.answerFace(challenge.challenge_id, {
    request_id: crypto.randomUUID(),
    submission_id: crypto.randomUUID(),
    demo_round_id: challenge.demo_round_id,
    result,
  });
}

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new Event("close")); };
  localStorage.clear();
  window.history.replaceState({}, "", "/v04");
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("v0.4 shell with stub data", () => {
  it("walks confirm → code → admin face → waiting → result and keeps finished cards read-only", async () => {
    const backend = makeBackend();
    renderPage(backend);
    expect(await screen.findByText("演示数据")).toBeTruthy();

    await reachVerification();
    const confirmation = screen.getByRole("heading", { name: "确认单记录" }).closest("section")!;
    expect(within(confirmation).getByText("已确认办理")).toBeTruthy();
    expect(within(confirmation).queryByRole("button")).toBeNull();
    expect(within(confirmation).getByText("妈妈（尾号 6688）")).toBeTruthy();

    await passCode();
    expect(screen.queryByRole("button", { name: /模拟成功|通过/ })).toBeNull();

    await adminAnswer(backend, "passed");
    expect(await screen.findByRole("heading", { name: "正在办理" })).toBeTruthy();
    expect(await screen.findByText("转账成功")).toBeTruthy();
    expect(screen.getByText(/示例回执/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "办理凭证" }));
    expect(screen.getByText(/^DEMO-/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "关闭详情" }));
    const verification = screen.getByRole("heading", { name: "安全验证记录" }).closest("section")!;
    expect(within(verification).getByText("验证已通过")).toBeTruthy();
    expect(within(verification).queryByLabelText("请输入 6 位验证码")).toBeNull();
  });

  it("sends one confirmation answer even when the button is clicked twice", async () => {
    const backend = makeBackend();
    const answer = vi.spyOn(backend.user, "answerConfirmation");
    renderPage(backend);
    await sendText("转给妈妈500块");
    await choosePayeeAndAccount();
    const confirm = await screen.findByRole("button", { name: "确认办理" });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    await screen.findByRole("heading", { name: "请完成两项身份验证" });
    expect(answer).toHaveBeenCalledTimes(1);
  });

  it("edits the original draft and shows a fresh confirmation without cancelling or sending a prompt", async () => {
    const backend = makeBackend();
    const answer = vi.spyOn(backend.user, "answerConfirmation");
    const send = vi.spyOn(backend.user, "sendMessage");
    const revise = vi.spyOn(backend.user, "reviseDraft");
    renderPage(backend);
    await sendText("转给妈妈500块");
    await choosePayeeAndAccount();

    fireEvent.click(await screen.findByRole("button", { name: "修改转账资料" }));
    fireEvent.click(screen.getByRole("button", { name: "修改金额" }));
    fireEvent.change(screen.getByLabelText("转账金额（元）"), { target: { value: "300" } });
    fireEvent.click(screen.getByRole("button", { name: "用这个金额" }));

    const composer = await screen.findByRole("textbox", { name: "输入您想办的事" }) as HTMLInputElement;
    expect(composer.value).toBe("");
    expect(await screen.findByText("已被新确认单替代")).toBeTruthy();
    await screen.findByRole("button", { name: "确认办理" });
    expect(revise).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ amount_fen: 30000 }));
    expect(answer).not.toHaveBeenCalled();
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("keeps the editable form and original confirmation when the draft update fails", async () => {
    const backend = makeBackend();
    renderPage(backend);
    await sendText("转给妈妈500块");
    await choosePayeeAndAccount();
    vi.spyOn(backend.user, "reviseDraft").mockRejectedValue(
      new ApiError(409, "CONFIRMATION_STALE", "这张确认单已经失效，请以最新状态为准。"),
    );

    fireEvent.click(await screen.findByRole("button", { name: "修改转账资料" }));
    fireEvent.click(screen.getByRole("button", { name: "修改金额" }));
    fireEvent.change(screen.getByLabelText("转账金额（元）"), { target: { value: "300" } });
    fireEvent.click(screen.getByRole("button", { name: "用这个金额" }));

    expect(await screen.findByText("这张确认单已经失效，请以最新状态为准。")).toBeTruthy();
    const composer = screen.getByRole("textbox", { name: "输入您想办的事" }) as HTMLInputElement;
    expect(composer.value).toBe("");
    expect((screen.getByLabelText("转账金额（元）") as HTMLInputElement).value).toBe("300");
  });

  it.each([
    ["expired", "已过期"],
    ["superseded", "已被新确认单替代"],
  ] as const)("refreshes after a 409 and keeps a %s confirmation read-only without resubmitting", async (decision, label) => {
    const backend = makeBackend();
    renderPage(backend);
    await sendText("转给妈妈500块");
    await choosePayeeAndAccount();
    const confirm = await screen.findByRole("button", { name: "确认办理" });
    const thread = await backend.user.ensureThread();
    const [envelope] = await backend.user.listTasks(thread.thread_id);
    const confirmationId = envelope.task.interaction!.record_ref!;
    const previous = await backend.user.getConfirmation(confirmationId);

    // Simulate a server-side change after the card was displayed, without an SSE event.
    // The rejected answer must trigger a read of the newer task and confirmation.
    const refresh = vi.spyOn(backend.user, "getTask").mockResolvedValue({
      ...envelope,
      task: {
        ...envelope.task,
        task_revision: envelope.task.task_revision + 1,
        interaction: null,
        allowed_actions: [],
      },
    });
    const readConfirmation = vi.spyOn(backend.user, "getConfirmation")
      .mockResolvedValue({ ...previous, decision });
    const answer = vi.spyOn(backend.user, "answerConfirmation")
      .mockRejectedValue(new ApiError(409, "confirmation_conflict", "这张确认单已经失效，请以最新的确认单为准。"));
    const submitCode = vi.spyOn(backend.user, "submitCode");
    fireEvent.click(confirm);

    expect(await screen.findByText("这张确认单已经失效，请以最新的确认单为准。")).toBeTruthy();
    expect(await screen.findByText(label)).toBeTruthy();
    const card = screen.getByRole("heading", { name: "确认单记录" }).closest("section")!;
    expect(within(card).queryByRole("button")).toBeNull();
    expect(screen.queryByLabelText("请输入 6 位验证码")).toBeNull();
    expect(answer).toHaveBeenCalledTimes(1);
    expect(answer).toHaveBeenCalledWith(confirmationId, expect.objectContaining({
      confirmation_version: previous.confirmation_version, choice: "approve",
    }));
    expect(refresh).toHaveBeenCalledWith(envelope.task.task_id);
    expect(readConfirmation).toHaveBeenCalledWith(confirmationId);
    expect(submitCode).not.toHaveBeenCalled();
    expect(screen.queryByText("转账成功")).toBeNull();
  });

  it("ends the task without a result when the medium-risk code is wrong", async () => {
    const backend = makeBackend();
    renderPage(backend);
    await reachVerification();
    fireEvent.change(screen.getByLabelText("请输入 6 位验证码"), { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: "提交验证码" }));
    expect(await screen.findByText("验证码不正确。按安全规则本次办理已终止，没有提交给银行。")).toBeTruthy();
    expect(screen.getByText("这笔转账没有完成")).toBeTruthy();
    expect(screen.queryByText("转账成功")).toBeNull();
    expect(screen.queryByRole("button", { name: "开始模拟人脸验证" })).toBeNull();
  });

  it("asks before continuing after a refresh and restores history without a new submission", async () => {
    const backend = makeBackend();
    const first = renderPage(backend);
    await reachVerification();
    first.unmount();

    // F39 is the source of confirmation / verification history. The shell must
    // recover even when browser-local record ids have been cleared.
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith("fe-shell-history:")) localStorage.removeItem(key);
    }

    const reloaded = makeBackend();
    const send = vi.spyOn(reloaded.user, "sendMessage");
    const provide = vi.spyOn(reloaded.user, "provideInput");
    const answer = vi.spyOn(reloaded.user, "answerConfirmation");
    renderPage(reloaded);
    expect(await screen.findByRole("heading", { name: "接着上次的办理" })).toBeTruthy();
    expect(screen.queryByLabelText("请输入 6 位验证码")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "继续办理" }));
    expect(await screen.findByText("已确认办理")).toBeTruthy();
    expect(await screen.findByLabelText("请输入 6 位验证码")).toBeTruthy();
    expect(screen.queryByText("已找回上次的办理资料，请查看当前进度。")).toBeNull();
    expect(send).not.toHaveBeenCalled();
    expect(provide).not.toHaveBeenCalled();
    expect(answer).not.toHaveBeenCalled();
    expect(await reloaded.user.listTasks((await reloaded.user.ensureThread()).thread_id)).toHaveLength(1);
  });

  it("shows needs_attention with a query-only entry and resolves it from the original operation", async () => {
    const backend = makeBackend();
    renderPage(backend);
    await reachVerification();
    await passCode();
    await backend.admin.enterAdmin({ request_id: crypto.randomUUID() });
    backend.admin.setResultUnknownFault(true);
    const query = vi.spyOn(backend.user, "queryResult");
    await adminAnswer(backend, "passed");

    expect(await screen.findByText("结果还没查清，请先查看原来那笔。")).toBeTruthy();
    const button = screen.getByRole("button", { name: "查询原操作" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(await screen.findByText("转账成功")).toBeTruthy();
    expect(query).toHaveBeenCalledTimes(1);
  });

  it("locks old buttons when the demo login expires and re-confirms after re-entering", async () => {
    const backend = makeBackend();
    renderPage(backend);
    await reachVerification();
    await backend.admin.enterAdmin({ request_id: crypto.randomUUID() });
    await backend.admin.expireUserSession({ request_id: crypto.randomUUID(), demo_round_id: "stub-demo-round" });

    expect(await screen.findByText("演示登录已过期")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "提交验证码" })).toBeNull();
    expect(screen.getByText("验证已暂停")).toBeTruthy();
    expect(screen.getByRole("textbox", { name: "输入您想办的事" }).hasAttribute("disabled")).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "点这里重新进入" }));
    expect(await screen.findByText(/登录已更换/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "继续办理" }));
    expect(await screen.findByRole("button", { name: "确认办理" })).toBeTruthy();
    expect(await screen.findByText("已被新验证替代")).toBeTruthy();
    expect(screen.getByText("已确认办理")).toBeTruthy();
  });

  it("refuses a verification code typed into the chat", async () => {
    const backend = makeBackend();
    renderPage(backend);
    await sendText("123456");
    expect(await screen.findByText("验证码请填在专用验证框里，不要发在聊天里。")).toBeTruthy();
    expect((screen.getByRole("textbox", { name: "输入您想办的事" }) as HTMLInputElement).value).toBe("");
    expect(screen.queryByText("123456", { selector: ".sh-bubble" })).toBeNull();
  });

  it("only lets the separate admin entry answer a started face check", async () => {
    const backend = makeBackend();
    const view = renderPage(backend);
    await reachVerification();
    await passCode();
    view.unmount();

    window.history.replaceState({}, "", "/v04/admin");
    render(<AdminDemoPage admin={backend.admin} stubExtras={backend.admin} />);
    fireEvent.click(await screen.findByRole("button", { name: "进入管理员演示端" }));
    fireEvent.click(await screen.findByRole("button", { name: "提交模拟失败" }));
    expect(await screen.findByText(/已提交「模拟失败」/)).toBeTruthy();
    const thread = await backend.user.ensureThread();
    const [{ task }] = await backend.user.listTasks(thread.thread_id);
    expect(task.status).toBe("failed");
    expect(task.data).toMatchObject({ operation: null });
  });

  it("falls back to the generic slot for an unknown module and mounts under /v04 only", async () => {
    expect(slots.resolve("bills")).toBe(billsSlot);
    expect(slots.resolve("transfer")).toBe(transferSlot);
    expect(slots.resolve("payroll")).toBe(genericSlot);
    render(<App />);
    expect(await screen.findByRole("heading", { name: "银行小助手" })).toBeTruthy();
  });
});
