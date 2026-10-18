# 11：拒绝/失败路径审计 outcome 修复（start 与 resume）

Ticket ID: v04-platform/11
Type: 开发
Owner: Erwin
Directory: backend/app/agent_platform/
Status: resolved（[PR #141](https://github.com/DrErwin/hackerthon-bank-agent/pull/141) squash `294e0d4` 合入 main，2026-10-18；双轴子代理审查〔AI 审查、非真人——两员均在收尾阶段失败但关键结论已产出：Spec 确认 #135 复现闭合、Standards 变异 4/4 杀〕+ Lead 复核补全〔124 passed、残留模式零〕；[Issue #135](https://github.com/DrErwin/hackerthon-bank-agent/issues/135) 已关闭）
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
- 2026-10-18 实施与合并（[PR #141](https://github.com/DrErwin/hackerthon-bank-agent/pull/141)，审查版 `35fe79c` / 合入 rebase `2c0c2ee`）：`_task_outcome` 助手 + 两处 `task.transition` 迁移；`AuditEvent.outcome` 为冻结 Literal 枚举（started/succeeded/failed/waiting/unknown/denied），未映射终态兜底 `unknown`（实测原值如 `cancelled` 会被枚举拒绝——枚举边界被测试钉住）。**测试命令与输出**（仓库 venv，固定 SHA worktree）：`pytest app/agent_platform -q` → **124 passed**（含 `test_audit_outcomes` 4 用例）。**审查**：Spec 轴（中途失败，关键结论已产出）确认 #135 复现闭合——拒绝 start 审计为 `model.started / model.finished / task.transition(failed)`；Standards 轴（中途失败，关键结论已产出）变异 4/4 杀；Lead 复核补全两位未竟收尾：全量复跑 + `harness.py` 残留三元 outcome 模式扫描为零 + 审查 worktree 变异还原确认。`recovery.checked` outcome 维持不动（成功路径 succeeded、异常路径 failed）：outcome 表达恢复机制本身完成，业务结局由 `payload.result` 与 `task.transition` 承载。转账与账单两线自此审计 outcome 如实区分成功与拒绝。
