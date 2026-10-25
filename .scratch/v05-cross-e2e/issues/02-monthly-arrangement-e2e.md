# 02：养老金核心与关键异常 E2E

Ticket ID: v05-cross-e2e/02

Package: [v05-cross-linkage/packages/05-cross-e2e：三主线 E2E 与全面验收](../../v05-cross-linkage/packages/05-cross-e2e.md)

Spec: [本工作组规格](../spec.md)

Type: 评测

Owner: Erwin（本执行对话代行本票评测）

Directory: `evals/cross/`

Status: blocked — 2026-10-25 准备已细化；真实运行blocked（先完成01核心、账单入口、养老金种子及适用风险事实）。

Accepted by: Erwin（授权本执行对话）

Accepted at: 2026-10-25

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-P01—P06、相关 X；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

从自然目标实际完成 2500/1000 转账、保留 1500；核对数据变化、取消、重启、失败及留存不被绕过

## Blocked by

- [v05-cross-business/02：养老金安排与留存核算](../../v05-cross-business/issues/02-monthly-arrangement.md)
- [v05-cross-platform/05：联动主入口及现有业务装配](../../v05-cross-platform/issues/05-cross-runtime-wiring.md)
- [v05-cross-frontend/01：总方案、子确认和结果页面](../../v05-cross-frontend/issues/01-plan-and-child-interactions.md)

- 顺序前置：[v05-cross-e2e/01：减支核心与关键异常 E2E](01-expense-reduction-e2e.md)核心通过；账单输入修复、养老金种子和转账可信事实须另核实。

## Start when

- 已获2026-10-25本轮执行授权；准备可立即做，真实运行按当前前置单独放行，不把领取当作验收通过。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] XL-P01 实际完成所选退订和 2500/1000 两笔转账，1500 为本次未转出部分，不造第三笔交易。
- [ ] XL-P02—P06 及相关 X 变体核对范围、留存口径、退订依赖、部分失败/未知、外部变化和取消。
- [ ] 真实页面/模型/HTTP 与银行事实能串联；刷新恢复的实际副作用次数无重复，失败批次保留。

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

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 10](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

## 2026-10-25 接包与执行细化

沿用XL-P01—P06，不新增业务规则。01减支核心先贯通；核对实际5000入账、1500含代扣口径、2500/1000两笔去向与可信风险配置，缺配置不得自行设低风险。转账首笔成功/次笔未知的恢复保留原operation_id及次数。

运行入口、数据/故障要求见[runbook](../../../evals/cross/runbook.md)；逐场景可观察断言和独立变体见[覆盖映射](../../../evals/cross/coverage-plan.md)；证据字段和归档见[批次模板](../../../evals/cross/batch-template.md)。[当前准备快照](../../../evals/cross/readiness-2026-10-25.md)只证明准备，不是页面或模型结果。总状态由中控维护。
