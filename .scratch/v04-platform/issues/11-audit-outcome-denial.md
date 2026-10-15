# 11：拒绝/失败路径审计 outcome 修复（start 与 resume）

Ticket ID: v04-platform/11
Type: 开发
Owner: Erwin
Directory: backend/app/agent_platform/
Status: open
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: P01（任务终态与审计记录一致）；转账 / 账单共用 harness 路径
Verification: 回归断言：安全拒绝（deny-all 策略实测 BLOCK）→ `task.transition` 的 outcome 必须为 failed；成功 / 等待 / 失败 / 拒绝四类状态与 outcome 映射各至少一条用例；`agent_platform` 全量与后端全量回归。命令与输出记入本票 Comments。
Blocked by: None
Source issue: [Issue #135](https://github.com/DrErwin/hackerthon-bank-agent/issues/135)

## 交付

1. `harness.py:484-494`（start）与 `:783-792`（resume）：`task.transition` 的 outcome 由「WAITING_* → waiting，其余 → succeeded」改为按 `result.status` 映射——等待态 → waiting；`SUCCEEDED` → succeeded；`FAILED`（含安全拒绝）→ failed。`:773-782` 的 `recovery.checked` outcome 一并核对。
2. 回归断言：拒绝路径 outcome=failed。现状（[PR #131 审查结论](https://github.com/DrErwin/hackerthon-bank-agent/pull/131#issuecomment-6198615597) 第三节复现）：FAILED 也落 `succeeded`，拒绝路径审计只剩 `model.started / model.finished / task.transition(succeeded)`，无 `tool.*`、无 `security.decided`。

## 边界与依赖

- 只修 outcome 映射与断言；不新增审计事件类型、不改审计写入机制。
- 转账与账单两线都受此缺陷影响；修复合入后两线各自回归用例须全绿。
- 验收口径提示：修复前不得用该 outcome 字段证明读取成功（#131 审查已声明）。

## Comments

- 2026-10-16：按 [PR #131 审查结论](https://github.com/DrErwin/hackerthon-bank-agent/pull/131#issuecomment-6198615597) 第三节建立（[Issue #135](https://github.com/DrErwin/hackerthon-bank-agent/issues/135)）。平台既有缺陷，非 #131 引入。
