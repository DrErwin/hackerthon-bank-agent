# 07：导出任务 module=bills 与第二模块事件带载荷（Issue #122 第 3 项 + 第 1 项·API 侧）

Ticket ID: v04-platform/07
Type: 开发
Owner: Erwin
Directory: backend/app/api/
Status: blocked
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P01、P02](../spec.md)
Verification: ①敏感明细导出任务的任务视图 `module=bills`（不再回退 `transfer`）②第二模块 `task_updated` 事件携带模块自身载荷（`data` 不再被 API 去掉），转账事件与导出链路不回归。既有导出生命周期用例（等待、验证、取消、会话变化）继续通过。
Blocked by: [v04-platform/06](06-sse-event-payload-union.md)（契约联合类型不先收敛，去掉 API 兜底会让第二模块事件在 `StreamEvent` 校验处失败）
Source issue: [Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122) 第 3 项 + 第 1 项 API 侧

## 交付

1. 导出任务快照补 `capability_name: "bills.export_details"`（第 3 项，一行修复）：`_task_module()` 按前缀取模块名，导出任务显示 `bills`。
2. 去掉 `stream_event()` 的第二模块去 `data` 兜底（第 1 项 API 侧）：契约 06 合入后，`task_updated` 直接携带模块自身载荷。
3. 断言：导出任务 `module=bills`；账单 `task_updated` 事件带载荷——原「第二模块事件去载荷、前端重新 GET」的断言翻转为「事件已带载荷」。
4. `backend/app/api/README.md` 第二模块接线段与「已知接缝」段按修复后口径改写（接缝清空，不再声明待放宽）。

## 边界与依赖

- 只改 `backend/app/api/`（含本目录文档）；契约归 06，harness 归 08。
- 风险与已核实前提：`capability_name` 会被 harness 的 `resume()` / `recover_session()` 拿去 `registry.get()`；导出任务若进入那两条路径会因能力未注册而失败。已核实 `continue_task()` 对导出任务在进入 harness 前短路（`service.py:904-906`），导出任务永不进入那两条路径；既有导出生命周期用例继续覆盖该前提，不新增防御代码。
- 顺序：06 合入 main 后从最新 main 开分支，不叠层 PR。

## Comments

- 2026-10-14 Erwin（AI 代填）：按 Issue #122 第 3 项与第 1 项 API 侧建立本票。Issue 原文建议第 3 项并入票 05，PM 2026-10-13 决定提前单独收口（票 05 仍 `blocked`）。第 3 项在真实数据链路打通前无对外触发场景（无报告则无导出任务），本票证据为平台链路级。
