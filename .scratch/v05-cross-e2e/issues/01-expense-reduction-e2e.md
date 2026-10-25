# 01：减支核心与关键异常 E2E

Ticket ID: v05-cross-e2e/01

Package: [v05-cross-linkage/packages/05-cross-e2e：三主线 E2E 与全面验收](../../v05-cross-linkage/packages/05-cross-e2e.md)

Spec: [本工作组规格](../spec.md)

Type: 评测

Owner: Erwin（本执行对话代行本票评测）

Directory: `evals/cross/`

Status: blocked — 2026-10-25 运行准备完成；真实运行blocked（账单类型化输入及正式案例数据待就绪）。

Accepted by: Erwin（授权本执行对话）

Accepted at: 2026-10-25

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-S01—S05、相关 X；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

真实页面/模型/HTTP/模拟银行实跑 XL-S，核对签约变化和副作用次数；报告失败、阻塞和相关 X 分支，缺陷回原目录

## Blocked by

- [v05-cross-platform/05：联动主入口及现有业务装配](../../v05-cross-platform/issues/05-cross-runtime-wiring.md)
- [v05-cross-frontend/01：总方案、子确认和结果页面](../../v05-cross-frontend/issues/01-plan-and-child-interactions.md)

- [v05-cross-business/01：减支盘点与退订编排](../../v05-cross-business/issues/01-expense-reduction.md)（已合PR #269；账单类型化输入缺口仍由账单线提供修复）
- [v05-cross-platform/11：子任务交互登记与联动文本输入](../../v05-cross-platform/issues/11-child-interaction-and-text-input.md)（PR #281已合）；前端01以PR #283为合入证据，原#282关闭。
- 正式比较数据与签约种子尚未完成本轮适配；账单输入修复由中控另派，具体票/commit待提供，不把缺口记录当实现。

## Start when

- 已获2026-10-25本轮执行授权；准备可立即做，真实运行按当前前置单独放行，不把领取当作验收通过。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] XL-S01 从真实页面自然表达贯通真实模型、HTTP 和模拟银行，选定协议实际取消，保留项不变。
- [ ] XL-S02—S05 以及相关共性变体留独立证据：多协议、无签约、反悔、部分成功、未知和恢复。
- [ ] 银行写入次数、任务与回执一致；实际失败/阻塞保留，跨目录缺陷回原票。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。必须执行真实页面 → 真实模型 → HTTP → 隔离模拟银行/生活服务链路；单模块或离线结果不能替代。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 准备交付：本工作组及evals/cross的Markdown准备增量，分支`codex/v05-cross-e2e-01-prep`，未合入；非代码，不创建PR、不运行CI。
- 实际运行 / 本票完成：blocked，未关闭。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 8](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

## 2026-10-25 接包与执行细化

01为本分支准备增量，覆盖XL-S01—S05及X适用分支；依赖就绪先跑S01，失败回归属线修复并保留批次。平台11 #281与前端01替代交付#283已合，不再以这两项未合为阻塞。账单入口仍只接受StartTransferInput而cross派发BillSummarizeInput，交账单线（中控已另派；具体新票号待提供）。

运行入口、数据/故障要求见[runbook](../../../evals/cross/runbook.md)；逐场景可观察断言和独立变体见[覆盖映射](../../../evals/cross/coverage-plan.md)；证据字段和归档见[批次模板](../../../evals/cross/batch-template.md)。[当前准备快照](../../../evals/cross/readiness-2026-10-25.md)只证明准备，不是页面或模型结果。总状态由中控维护。
