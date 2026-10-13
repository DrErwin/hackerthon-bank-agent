# 07：导出任务 module=bills 与第二模块事件带载荷（Issue #122 第 3 项 + 第 1 项·API 侧）

Ticket ID: v04-platform/07
Type: 开发
Owner: Erwin
Directory: backend/app/api/
Status: resolved（[PR #128](https://github.com/DrErwin/hackerthon-bank-agent/pull/128) squash `77726a9` 合入 main，2026-10-14；Spec 轴无 P0/P1、Standards 轴无 P0/P1/P2，P3 全部处置〔AI 审查、非真人，意见与处置见 PR 评论〕；合入后 api 63 passed、主线后端全量 533 passed + 模拟银行 14 passed）
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
- 2026-10-14 实现与验证：交付 1—4 全部落地（`service.py` 导出任务快照补 `capability_name`、`stream_event()` 去掉去载荷兜底、两条断言、README 口径改写）。**先红后绿**（PR #128 正文与评论有命令与输出）：PR 测试 + 旧 `service.py` 时两条断言分别红在 `assert 'transfer' == 'bills'` 与 `data` 为 `None`；改动后 API 用例全绿。后端全量 530 passed、模拟银行 14 passed，CI 绿。
- 2026-10-14 双轴 AI 审查（非真人）结论：**Spec 轴无 P0/P1、可合入**；Standards 轴结论见 PR 评论。采纳的加固：①事件载荷断言先断 `data is not None`（旧实现下红为 `AssertionError` 而非 `TypeError`）；②导出任务 `module=bills` 补完成态断言（快照在绑定挑战与更新结果时会 `{**task.snapshot}` 重建）；③README 写明导出任务对外为 `bills` 域、结果信封仍按 `ModuleResult[TransferTaskView]` 构造（`data` 恒空，承接契约 06 的接受项），并写明「将来导出任务携带自身 `data` 或进入 harness 恢复入口时必须同步放宽校验」的触发条件。
- 2026-10-14 审查提出的对账责任（转 [票 05](05-real-bills-integration.md)）：`bills.export_details` 是硬编码的能力名，契约与任何 manifest 都没有它，注册表里查不到；本票只在任务视图取模块名前缀时使用它，导出任务在 `continue_task()` 处被 `export_for_task()` 短路、不进 harness 的能力解析，因此今天无需注册。真实账单模块接入时须在票 05 明确：真实模块登记同名能力，或与 API 侧对账改名——任何把导出任务引入 harness 恢复路径的改动都必须先解决这一条。
