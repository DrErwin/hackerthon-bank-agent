# 04：三目标完整覆盖与体验收口

Ticket ID: v05-cross-e2e/04

Package: [v05-cross-linkage/packages/05-cross-e2e：三主线 E2E 与全面验收](../../v05-cross-linkage/packages/05-cross-e2e.md)

Spec: [本工作组规格](../spec.md)

Type: 评测

Owner: Erwin（本执行对话代行本票评测）

Directory: `evals/cross/`

Status: in_progress — 10-27 本人新授权后已有自动验证、真实接口及部分页面证据；26 变体完整页面、200%/读屏/真机、本人安全/体验接受未齐。模型超时及后续限流分别阻塞新增走查，见[v0.5 完成情况](../../../docs/versions/v0.5.0/completion.md)。2026-10-29 核对。

Accepted by: Erwin（授权本执行对话）

Accepted at: 2026-10-25

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: 全部；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

核心失败先修复，补齐全部 26 条设计及其关键变体，真实自然表达与页面体验走查，汇总证据/限制供 PM 验收；不代签安全、不自行豁免

## Blocked by

- [v05-cross-e2e/01：减支核心与关键异常 E2E](01-expense-reduction-e2e.md)
- [v05-cross-e2e/02：养老金核心与关键异常 E2E](02-monthly-arrangement-e2e.md)
- [v05-cross-bank-eval/01：银行事实和防重专项验收](../../v05-cross-bank-eval/issues/01-birthday-bank-evidence.md)
- [v05-cross-security/02：联动专项安全验证](../../v05-cross-security/issues/02-cross-security-evidence.md)
- [v05-cross-e2e/03：生日核心与关键异常 E2E](03-birthday-e2e.md)

## Start when

- 最新停止线撤回自动续跑授权。本轮只静态交设计；未来由Erwin自行执行，或经用户明确要求和中控另派后再委派AI。依赖就绪不自动启动。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

当前只交[手工执行设计与缺口](../manual-execution-handoff.md)，下列真实验收及完整安全专项未执行。26条变体、设备体验与各层结果分别登记，设计审查通过不代替本票验收。

- [ ] 三核心路径先通过或有 PM 明确接受的具体例外；核心失败未处理时不将全量统计包装成完成。
- [ ] 26条设计的全部关键变体及自然表达页面走查有结论，覆盖映射无遗漏；旧23条仅历史，不计新通过。
- [ ] 关联银行专项与安全专项，分别标明缺口、专业签核和用户体验验收状态，AI 执行不冒充真人。
- [ ] 输出可供更新 v0.5 completion 的事实/证据/遗留/下一步；本票不自行接受例外或宣布版本收口。

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

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 21](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

## 2026-10-25 接包与执行细化

保留全部26条与关键变体；X随前三票逐步验证，04核对完整映射、重跑失败及缺口。200%、键盘、读屏、真机软键盘各自留证或blocked。PM体验接受、例外、Ringo本人签核独立记录，由中控维护版本事实。

运行入口、数据/故障要求见[runbook](../../../evals/cross/runbook.md)；逐场景可观察断言和独立变体见[覆盖映射](../../../evals/cross/coverage-plan.md)；证据字段和归档见[批次模板](../../../evals/cross/batch-template.md)。[当前准备快照](../../../evals/cross/readiness-2026-10-25.md)只证明准备，不是页面或模型结果。总状态由中控维护。
