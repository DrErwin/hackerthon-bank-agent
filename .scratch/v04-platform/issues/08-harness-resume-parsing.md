# 08：harness 恢复解析去掉转账视图定型（Issue #122 第 2 项）

Ticket ID: v04-platform/08
Type: 开发
Owner: Erwin
Directory: backend/app/agent_platform/
Status: in_progress
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P01、P02](../spec.md)
Verification: 等待类第二模块任务（`waiting_input` / `waiting_approval`）沿原任务 `resume()` 能继续推进，不再因结果被定型为转账视图而校验失败；转账的恢复与会话转换路径不回归。
Blocked by: 无（与 06 并行，目录不重叠）
Source issue: [Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122) 第 2 项

## 交付

1. `backend/app/agent_platform/harness.py` 的 `_result()` 去掉转账视图定型（通用 `ModuleResult` 解析快照结果），同因的 `_check_result_scope()` 参数标注同步；只改解析与标注，不改任何业务行为。
2. 相关返回标注（`get` / `resume` / `recover_session` 等公开入口）不再声称结果一定属于转账模块——第二模块能力经同一入口返回自己的结果。
3. 断言：注册一个等待类账单能力（返回 `waiting_input` + 账单载荷），`start()` 后 `resume()` 能正常推进到成功；转账恢复路径回归不变。

## 边界与依赖

- 只改 `backend/app/agent_platform/`；契约归 06，API 归 07。
- 证据强度：等待类账单任务用测试替身（登记的账单能力）复现，真实账单能力接入后的复验随 [票 05](05-real-bills-integration.md) 补，本票不声称真实模型或真实账单行为已验证。

## Comments

- 2026-10-14 Erwin（AI 代填）：按 Issue #122 第 2 项建立本票。当前账单桩只返回终态，等待类账单任务在真实模块接入前无自然触发，故断言以登记测试替身复现接缝。
