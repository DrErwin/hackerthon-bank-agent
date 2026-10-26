import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AssistantPage } from "./AssistantPage";
import { createDemoBackend } from "./stub/demoBackend";
import { createSlotRegistry } from "./slots";
import { transferSlot } from "./slots/transferDemoSlot";

beforeEach(() => { localStorage.clear(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

async function say(text: string) {
  const input = screen.getByRole("textbox", { name: "输入您想办的事" });
  await waitFor(() => expect(input.hasAttribute("disabled")).toBe(false));
  fireEvent.change(input, { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
}

it("mixes clicks, a side question and a spoken edit in one demo draft, requiring a fresh confirmation", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  const confirm = vi.spyOn(backend.user, "answerConfirmation");
  render(<AssistantPage source={backend.user} slots={createSlotRegistry([transferSlot])} />);
  const starter = await screen.findByRole("button", { name: "给家人转一笔钱" });
  await waitFor(() => expect(starter.hasAttribute("disabled")).toBe(false));
  fireEvent.click(starter);
  fireEvent.click(await screen.findByRole("button", { name: /妈妈.*6688/ }));
  expect(screen.queryByLabelText("查找已保存的收款人")).toBeNull();
  fireEvent.change(await screen.findByLabelText("转账金额（元）"), { target: { value: "500" } });
  fireEvent.click(screen.getByRole("button", { name: "用这个金额" }));
  fireEvent.click(await screen.findByRole("button", { name: /演示账户.*1234/ }));
  await screen.findByRole("button", { name: "确认办理" });
  const thread = await backend.user.ensureThread();
  const [original] = await backend.user.listTasks(thread.thread_id);
  const oldId = original.task.interaction!.record_ref!;

  await say("我还有多少余额？");
  expect(await screen.findByText(/您的演示账户尾号 1234，可用余额 1,000 元/)).toBeTruthy();
  await say("改成300元");
  await screen.findByText("金额改好了，请核对当前转账单。");
  const current = await backend.user.listTasks(thread.thread_id);
  expect(current).toHaveLength(1);
  expect(current[0].task.task_id).toBe(original.task.task_id);
  expect(current[0].task.data).toMatchObject({ amount_fen: 30000 });
  expect((await backend.user.getConfirmation(oldId)).decision).toBe("superseded");
  expect(screen.getAllByRole("button", { name: "确认办理" })).toHaveLength(1);
  expect(confirm).not.toHaveBeenCalled();
  expect(document.querySelectorAll(".sh-record")).toHaveLength(1);
  expect(screen.getByRole("textbox", { name: "输入您想办的事" })).toBeTruthy();
});

it("keeps an unfinished task reachable through history and returns focus to it", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0 });
  Element.prototype.scrollIntoView = vi.fn();
  render(<AssistantPage source={backend.user} slots={createSlotRegistry([transferSlot])} />);
  await say("转账500元");
  await screen.findByRole("button", { name: /妈妈.*6688/ });
  fireEvent.click(screen.getByRole("button", { name: "记录" }));
  const dialog = await screen.findByRole("dialog", { name: "办理记录" });
  fireEvent.click(within(dialog).getByRole("button", { name: "继续这项办理" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await waitFor(() => expect(document.activeElement?.getAttribute("data-task-id")).toBeTruthy());
});
