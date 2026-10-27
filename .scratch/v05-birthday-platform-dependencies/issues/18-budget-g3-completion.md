# v05-birthday-platform-dependencies/18：预算输入的G3封存完成证明

Ticket ID: v05-birthday-platform-dependencies/18
Package: [v05-cross-linkage/packages/01-platform-bank：底座与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [平台18最小规格](../budget-g3-18.md)
Type: 开发
Owner: Erwin（v0.5统一负责）
Directory: `backend/app/agent_platform/`
Status: in_progress — 真实G3红转绿，13项G3与原35来源测试通过；16已合，准备准确完整平台组合
Blocked by: None（335已合入）
Accepted by: 本对话AI，用户全部非比赛资料授权与中控明确分派
Accepted at: 2026-10-27
Core scenarios: P18-01—P18-05
Verification: NoopModel/新隔离库的真实预算采用与G3封存、原号恢复、外部CAS/异参拒绝及适度平台回归；不动Cross/B/C历史。

## Comments

- 2026-10-27：Cross09原`test_pending_personal_budget_moves_only_after_fresh_proof`在进入会话恢复前已失败，原controls.xml由原工作树保留。平台18独立分支`codex/v05-budget-input-g3-18`基于main f4a98724，不混337与16/17。
- 2026-10-27：平台正常红例1 failed/8.90s，另已发布但completion CAS中断的两种当前计划状态2 failed/1 passed；修后原35预算来源+9真实G3共44 passed/56.24s，随后最终11真实G3 passed/58.20s（不与44重复加总）。无原winner时仅保持失效，旧关联只读恢复、外部CAS与异参保持拒绝；待17+16主线一起做一次完整平台。
- 2026-10-27：修改限额/不采用两种非adopt专用选择另2 passed/11.29s，真实预算写入为0；本文件G3节点共13。平台16已合至main c760f0d0，将在此准确组合冻结源代码运行一次完整平台。
