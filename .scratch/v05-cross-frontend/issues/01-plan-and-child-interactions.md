# 01：总方案、子确认和结果页面

Ticket ID: v05-cross-frontend/01

Package: [v05-cross-linkage/packages/04-frontend：联动页面体验](../../v05-cross-linkage/packages/04-frontend.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin（v0.5 本阶段统一负责）

Directory: `frontend/`

Status: planned — PM 已批准拆分；待负责人接包、前置满足和实施授权。

Accepted by: 未记录

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-S01、XL-P01、X02—X05、X08；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

先提交版式/文案供 PM 走查，再实现父总览、原子确认卡、逐步结果/等待/恢复；采用方案不等于批准全部办理。复用原转账/退订卡片

## Blocked by

- [v05-cross-platform/04：联动任务与子交互 API](../../v05-cross-platform/issues/04-parent-child-api.md)

## Start when

- 负责人明确接包并记录实际接受人；本轮尚未授权代码实施或运行评测。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。
- 具体页面/文案在本票编码前提交 PM 走查；粒度批准不等于 UI 定稿。

## Acceptance criteria

- [ ] 实施前提交方案总览、子卡片及结果状态的具体版式/文案并记录 PM 走查结论。
- [ ] 采用方案与确认具体业务不同；调用后端真实 allowed_actions，不靠聊天肯定词自动放行。
- [ ] 多个任务、插入查询、等待、失败、未知、断线/刷新时不丢目标和已办项，旧确认不可用。
- [ ] 复用原转账/退订验证卡；检查键盘、200% 缩放及读屏标签，本票页面结果留证。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：未开始。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 7](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（责任更新）：本票本阶段执行由 Erwin 承担；具体票的开工、实现和验证状态仍按实际结果记录。
