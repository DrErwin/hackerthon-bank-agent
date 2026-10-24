# 04：三目标完整覆盖与体验收口

Ticket ID: v05-cross-e2e/04

Package: [v05-cross-linkage/packages/05-cross-e2e：三主线 E2E 与全面验收](../../v05-cross-linkage/packages/05-cross-e2e.md)

Spec: [本工作组规格](../spec.md)

Type: 评测

Owner: Erwin（v0.5 阶段承接；包 05 本轮尚未领取）

Directory: `evals/cross/`

Status: planned — PM 已批准拆分；待负责人接包、前置满足和实施授权。

Accepted by: 未记录

Accepted at: 未记录

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

- 负责人明确接包并记录实际接受人；本轮尚未授权代码实施或运行评测。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] 三核心路径先通过或有 PM 明确接受的具体例外；核心失败未处理时不将全量统计包装成完成。
- [ ] 26条设计的全部关键变体及自然表达页面走查有结论，覆盖映射无遗漏；旧23条仅历史，不计新通过。
- [ ] 关联银行专项与安全专项，分别标明缺口、专业签核和用户体验验收状态，AI 执行不冒充真人。
- [ ] 输出可供更新 v0.5 completion 的事实/证据/遗留/下一步；本票不自行接受例外或宣布版本收口。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。必须执行真实页面 → 真实模型 → HTTP → 隔离模拟银行/生活服务链路；单模块或离线结果不能替代。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：未开始。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 21](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。
