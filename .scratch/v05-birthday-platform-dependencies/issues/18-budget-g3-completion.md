# v05-birthday-platform-dependencies/18：预算输入的G3封存完成证明

Ticket ID: v05-birthday-platform-dependencies/18
Package: [v05-cross-linkage/packages/01-platform-bank：底座与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [平台18最小规格](../budget-g3-18.md)
Type: 开发
Owner: Erwin（v0.5统一负责）
Directory: `backend/app/agent_platform/`
Status: ready_for_merge — 精确a45407e3完整平台445 passed/13 skipped，Standards/Spec独立0必须项；最终CI/合入交中控
Blocked by: None（335已合入）
Accepted by: 本对话AI，用户全部非比赛资料授权与中控明确分派
Accepted at: 2026-10-27
Core scenarios: P18-01—P18-05
Verification: NoopModel/新隔离库的真实预算采用与G3封存、原号恢复、外部CAS/异参拒绝及适度平台回归；不动Cross/B/C历史。

## Comments

- 2026-10-27：Cross09原`test_pending_personal_budget_moves_only_after_fresh_proof`在进入会话恢复前已失败，原controls.xml由原工作树保留。平台18独立分支`codex/v05-budget-input-g3-18`基于main f4a98724，不混337与16/17。
- 2026-10-27：平台正常红例1 failed/8.90s，另已发布但completion CAS中断的两种当前计划状态2 failed/1 passed；修后原35预算来源+9真实G3共44 passed/56.24s，随后最终11真实G3 passed/58.20s（不与44重复加总）。无原winner时仅保持失效，旧关联只读恢复、外部CAS与异参保持拒绝；待17+16主线一起做一次完整平台。
- 2026-10-27：修改限额/不采用两种非adopt专用选择另2 passed/11.29s，真实预算写入为0；本文件G3节点共13。平台16已合至main c760f0d0，将在此准确组合冻结源代码运行一次完整平台。
- 2026-10-27：首轮完整平台在6f5f7ba5运行时，自查发现外部CAS使origin invalidated/移除可跳过accepted循环并覆盖新result；该轮到78%后由本代理按精确pytest子进程主动中止（exit1，无完整XML），不计通过或产品测试失败。新增红例真实2 failed/8.80s；将active原调用完整性校验前置到空记录/相位分支之前，修后15真实G3+原35来源 **50 passed/49.66s**。原XML另存，最终完整批次改用新文件，待冻结补修代码后执行。
- 2026-10-27：最终冻结a45407e3在main c760f0d0（17+16均合入）组合上，**445 passed/13 skipped/0 failed/error，421.87s，exit0**；458节点且唯一458，15新G3和35既有来源包含其中，不重复加总。两轴在该源码增量均0必须项；[完整原始XML与范围](../budget-g3-18-verification.md)。Cross09及19/20/21由中控后继组合另验，不跨树冒称通过。
