import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import { InputCard } from "./components/StatusCards";
import { Composer } from "./components/Chrome";
import { createDemoBackend } from "./stub/demoBackend";
import { useConversation } from "./useConversation";
import type { ShellEvent } from "./types";

beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); });

it("offers a labelled amount form, preserves a rejected value and then continues the same step", async () => {
  const submit = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  render(<InputCard id="amount" active busy={false} selectedLabel={null}
    interaction={{ interaction_id: "i1", kind: "input", prompt: "请告诉我金额",
      required_fields: ["amount_fen"], options: [], record_ref: null }}
    onSelect={vi.fn()} onSubmitText={submit} />);
  const input = screen.getByLabelText("转账金额（元）") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "500" } });
  fireEvent.click(screen.getByRole("button", { name: "补充并继续" }));
  await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
  expect(input.value).toBe("500");
  fireEvent.click(screen.getByRole("button", { name: "补充并继续" }));
  await waitFor(() => expect(input.value).toBe(""));
  expect(submit).toHaveBeenLastCalledWith("500");
});

it("keeps ordinary rejected message text available to correct", async () => {
  render(<Composer disabled={false} sending={false} pendingText={null} onSend={async () => false} />);
  const input = screen.getByLabelText("输入您想办的事") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "我想继续办理" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await waitFor(() => expect(input.value).toBe("我想继续办理"));
});

it("keeps waiting beyond fifteen seconds and exposes a real processing error", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0, tickMs: 10 });
  let receive!: (event: ShellEvent) => void;
  vi.spyOn(backend.user, "subscribe").mockImplementation((_id, onEvent) => { receive = onEvent; return () => undefined; });
  const { result } = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(result.current.booting).toBe(false));
  await act(async () => { await result.current.actions.send("你好"); });
  expect(result.current.awaitingReply).toBe(true);
  vi.useFakeTimers();
  await act(async () => { await vi.advanceTimersByTimeAsync(16000); });
  expect(result.current.awaitingReply).toBe(true);
  act(() => receive({ event_type: "stream_error", payload: { reason: "理解失败，尚未提交银行。" } } as ShellEvent));
  expect(result.current.awaitingReply).toBe(false);
  expect(result.current.pageError).toBe("理解失败，尚未提交银行。");
});

it("retries a failed input with its original request id and never sends it as a new message", async () => {
  const backend = createDemoBackend({ replyDelayMs: 0, tickMs: 10 });
  const { result } = renderHook(() => useConversation(backend.user));
  await waitFor(() => expect(result.current.booting).toBe(false));
  await act(async () => { await result.current.actions.send("转给妈妈500元"); });
  await waitFor(() => expect(result.current.tasks.size).toBe(1));
  const task = [...result.current.tasks.values()][0].task;
  const send = vi.spyOn(backend.user, "sendMessage");
  const provide = vi.spyOn(backend.user, "provideInput")
    .mockRejectedValueOnce(new ApiError(503, "DEPENDENCY_UNAVAILABLE", "暂未收到结果"))
    .mockResolvedValueOnce(task);
  await act(async () => { await result.current.actions.provideText(task, "补充信息"); });
  await act(async () => { await result.current.actions.provideText(task, "补充信息"); });
  expect(provide).toHaveBeenCalledTimes(2);
  expect(provide.mock.calls[0][0]).toBe(task.task_id);
  expect(provide.mock.calls[0][1]).toEqual(provide.mock.calls[1][1]);
  expect(send).not.toHaveBeenCalled();
});
