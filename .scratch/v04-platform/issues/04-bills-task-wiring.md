# 04：账单任务接线（module=bills 任务视图、载荷与事件）

Ticket ID: v04-platform/04
Type: 开发
Owner: Erwin
Directory: backend/app/api/
Status: pr_open（[PR #118](https://github.com/DrErwin/hackerthon-bank-agent/pull/118) 待统一审查，2026-10-13 开出；Depends on PR #115 + #117，合并顺序建议 #115→#116→#117→#118）
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P01 账单任务在平台上创建、等待、恢复](../spec.md)、[P02 前端按 module 选插槽](../spec.md)（后端事实部分）
Verification: E2E：账单任务创建 → 等待 → 恢复，任务视图 `module=bills` 与账单载荷正确；`task_updated` / `report_ready` 事件断言；转账链路回归（`module=transfer`、确认 / 验证 / 恢复不回退）。双场景互不串台的前端走查由前端线覆盖，本票只验后端事实。命令与输出记入本票 Comments。
Blocked by: [v04-platform/03：账单能力注册与意图路由](03-bills-registration.md)；[v04-platform/01：受控报告存储与 F21 读取](01-report-storage-read.md)（`report_ready` 与报告载荷引用已落库报告）
Source issue: [Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87)

## 交付

1. `create_app` 支持挂载第二个业务模块（账单）运行时，与转账运行时并存；`SERVED_MODULE` 单常量机制泛化为按任务取模块。
2. 任务视图：账单任务在所有对外任务视图（F08—F13、F15、F36 等）带 `module=bills` 与账单载荷（data 为账单模块可展示结果）；转账任务仍为 `module=transfer`。
3. 事件：`task_updated` 载荷带 module；**`report_ready`（task_id、report_id）在报告就绪时发射**（契约 §6.6 已定义、本票落地；前端按 F21 读卡片，不广播全量交易明细）。
4. 等待 / 恢复口径：账单任务创建、等待、恢复沿平台任务八态与既有恢复机制，不新建第二套。

## 边界与依赖

- 不在本票：账单业务实现（周恩宇）；前端插槽选择逻辑（梁爽/六水，消费 `module` 字段）；银行接缝（按需另开票）。

## Comments

- 2026-10-13：双轴审核通过后建立（原包建议 03 的 api 半张；`report_ready` 事件归属在本票明确）。
- 2026-10-13 实施（分支 `v04-platform-04-bills-wiring` = 03 分支 + merge 01 分支 + 增量，先红后绿）：`ApiService` 装配注册账单桩（槽位已占则跳过）；任务视图 / 事件 `module` 按快照 `capability_name` 前缀取，转账保持定型视图零行为变化；`BillReport` 载荷自动落库 + F21 可读 + 消息 `report_ids` + `report_ready` 事件（仅发射一次）；顺带修复 01 的 `save_report` 未返回行数。已知接缝三处（SSE 载荷联合类型、harness 恢复定型解析、导出任务 module）已在 PR #118 正文与 README 登记，待契约票 / 账单线联调放宽。E2E 一项 + 转账回归；api 66 passed、后端全量 424 passed。Ringo 审批：本票不触及 `security/`，无审批项；导出相关豁免记录见票 02。[PR #118](https://github.com/DrErwin/hackerthon-bank-agent/pull/118) 待统一审查。
