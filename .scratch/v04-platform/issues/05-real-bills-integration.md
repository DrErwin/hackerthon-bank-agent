# 05：真实账单模块接入平台与纵向联调（替换契约形状桩）

Ticket ID: v04-platform/05
Type: 开发
Owner: Erwin
Directory: backend/app/api/
Status: blocked
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P01、P02、P03、P04](../spec.md)（真实数据链路下的端到端验收）
Verification: E2E：真实账单任务（L01—L03）→ 报告自动落库 → F21 读取 → F22/F24 明细导出与下载；与前端账单插槽、账单线 BF01—BF07 的纵向联调记录；报告与导出无秘密泄漏。命令与输出、联调记录链接记入本票 Comments；整条路径通过才算 P01—P04 场景通过，局部接线不替代联调证据。
Blocked by: 账单公开能力可运行（周恩宇 [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)，跨线前置，非本组票）；[Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) 记录缺口
Source issue: [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123)

## 交付

1. 按可用性条件注册真实 bills 工厂，替换 `agent_platform/bills_stub.py` 的桩（桩保留为测试替身 / 降级路径，不删除、不作为生产默认）。
2. 真实账单任务：任务视图 `module=bills` + 真实载荷、报告自动落库与 `report_ready` 事件端到端验证（票 04 接线在真数据下的确认）。
3. 纵向联调：与前端账单插槽（frontend-complete/01）和账单线 BF01—BF07 联调，证据并入 [v04-bills/02](../../v04-bills/packages/02-v04-acceptance.md) 联合验收。
4. 同窗口收 [Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122) 的三处接缝（SSE 事件载荷联合类型收敛、harness 恢复解析、导出任务 `module=bills` 一行修复）——真实接入后会真实触发；涉及 `contracts/` 或 `agent_platform/` 时按一票一目录另开票。

## 边界与依赖

- 不在本票：账单业务实现与评测（周恩宇，[v04-bills/01](../../v04-bills/packages/01-bills-backend.md)）；前端页面实现（梁爽/六水）。
- 前置未满足时保持 `blocked`；平台侧接口（F21—F24、模块注册点 `register_module`）已就绪，可先做接线准备与非真数据（测试替身）验证。

## Comments

- 2026-10-13：v0.4 盘点发现"真实账单模块接入"无归属票（票 03/04 只交付注册点与契约形状桩），登记 [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) 并建立本票；前置=账单公开能力可运行。
