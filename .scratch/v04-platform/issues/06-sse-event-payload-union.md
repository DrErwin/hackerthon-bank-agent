# 06：SSE 事件载荷联合类型收敛为通用 TaskView（Issue #122 第 1 项·契约侧）

Ticket ID: v04-platform/06
Type: 开发
Owner: Erwin
Directory: backend/app/contracts/
Status: in_progress
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P01、P02](../spec.md)（真实数据链路下的端到端验收）
Verification: `EventPayload` 与 `task_updated` 载荷不再按转账视图定型——第二模块（bills）事件可携带自身可展示结果（`BillReport`），转账载荷与既有调用保持有效；契约文档按 §8 登记（轻量确认档）；回归断言：①账单载荷事件带 `data` 且字段可读 ②转账载荷事件不回归 ③非法 `module` 仍拒绝。
Blocked by: 无
Source issue: [Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122) 第 1 项

## 交付

1. `backend/app/contracts/api.py` 的 `EventPayload` 收敛为通用 `TaskView`（去掉 `TaskView[TransferTaskView]` 定型），使 §6.5「`data` 仅为对应模块可展示结果」在 SSE 事件上同样成立。
2. 契约文档登记：《公共契约》修订记录 + §6.6 事件载荷口径；分档=**轻量确认**（旧调用方式与既有行为保持有效）。
3. 回归断言（`backend/app/contracts/test_contracts.py`）：账单载荷 `task_updated` 携带 `data`；转账载荷与既有视图不回归；非法 `module` 值仍拒绝。
4. `frontend/src/api.generated.ts` 需随本票重新生成——生成物归 `frontend/` 工作线（[Issue #89](https://github.com/DrErwin/hackerthon-bank-agent/issues/89) 已登记类型生成），本票合入后发通知。

## 边界与依赖

- 本票只改 `backend/app/contracts/` 与契约文档。API 侧「第二模块事件去 `data`」兜底（`backend/app/api/service.py`）由 [票 07](07-export-task-module-and-event-payload.md) 收；harness 恢复解析（`backend/app/agent_platform/harness.py`）由 [票 08](08-harness-resume-parsing.md) 收——一票一目录，不跨目录改。
- 兼容性：放宽联合类型不改变任何既有事件的运行时行为，`data` 的解释权按 §6.5 交给 `module`（前端据此选插槽）。如实登记的副作用：转账事件的 `data` 不再被公共契约强制校验为 `TransferTaskView`，调用方按 `module` 解释；如后续需要强校验，按 §8 另开协同变更。
- 受影响方：前端（生成类型 + 按 `module` 解释 `data`）；账单侧在票 07 使用。

## Comments

- 2026-10-14 Erwin（AI 代填）：按 Issue #122 第 1 项建立本票；Issue 原文建议「随票 05 一起收」，PM 2026-10-13 决定提前单独收口（票 05 仍 `blocked` 于账单线），故与 07/08 一起拆为三张单目录票。
