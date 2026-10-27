import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Progress } from "@/components/ui/progress";
import { DetailsDrawer } from "./components/DetailsDrawer";
import { ServiceNav } from "./components/ServiceNav";
import DesignSystemPage from "./DesignSystemPage";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it.each([390, 1280])("closes details with Escape and returns focus at %i px", async (width) => {
  vi.stubGlobal("innerWidth", width);
  const onOpenChange = vi.fn();
  render(<DetailsDrawer title="查看明细" onOpenChange={onOpenChange}><button>查看一笔账单</button></DetailsDrawer>);
  const trigger = screen.getByRole("button", { name: "查看明细" });
  trigger.focus();
  fireEvent.click(trigger);
  const dialog = await screen.findByRole("dialog", { name: "查看明细" });
  expect(dialog.getAttribute("data-slot")).toBe(width < 960 ? "drawer-content" : "sheet-content");
  expect(dialog.contains(document.activeElement)).toBe(true);
  fireEvent.keyDown(document.activeElement ?? document, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await waitFor(() => expect(document.activeElement).toBe(trigger));
  expect(onOpenChange.mock.calls).toEqual([[true], [false]]);
});

it("announces only a known percentage and leaves unknown progress indeterminate", () => {
  const view = render(<Progress value={null} aria-label="办理进度" />);
  expect(screen.getByRole("progressbar").hasAttribute("aria-valuenow")).toBe(false);
  view.rerender(<Progress value={42} aria-label="办理进度" />);
  expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("42");
});

it("keeps services reachable and blocks new requests while a message is pending", () => {
  vi.stubGlobal("innerWidth", 390);
  const choose = vi.fn();
  const view = render(<ServiceNav disabled onChoose={choose} />);
  const menu = screen.getByRole("button", { name: "常用服务" });
  fireEvent.click(menu);
  fireEvent.click(screen.getByRole("button", { name: "我的收款人" }));
  expect(choose).not.toHaveBeenCalled();
  view.rerender(<ServiceNav disabled={false} onChoose={choose} />);
  fireEvent.click(screen.getByRole("button", { name: "我的收款人" }));
  expect(choose).toHaveBeenCalledExactlyOnceWith("我有哪些收款人");
  expect(menu.getAttribute("aria-expanded")).toBe("false");
  expect(document.activeElement).toBe(menu);
});

it("retains amount when the example payee changes and leaves a readable review", async () => {
  render(<DesignSystemPage />);
  fireEvent.change(screen.getByLabelText("转账金额（元）"), { target: { value: "520" } });
  fireEvent.click(screen.getByRole("button", { name: "换一位收款人" }));
  const dialog = await screen.findByRole("dialog");
  fireEvent.click(within(dialog).getByRole("button", { name: /老伴/ }));
  fireEvent.click(within(dialog).getByRole("button", { name: "关闭详情" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect((screen.getByLabelText("转账金额（元）") as HTMLInputElement).value).toBe("520");
  fireEvent.click(screen.getByRole("button", { name: "核对这笔转账" }));
  expect(screen.getByText("¥520.00")).toBeTruthy();
  expect(screen.getByText("老伴")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "返回修改" }));
  expect((screen.getByLabelText("转账金额（元）") as HTMLInputElement).value).toBe("520");
  fireEvent.click(screen.getByRole("button", { name: "大字" }));
  expect(screen.getByRole("button", { name: "标准字" }).getAttribute("aria-pressed")).toBe("true");
  expect(await screen.findByText("文字已放大")).toBeTruthy();
});
