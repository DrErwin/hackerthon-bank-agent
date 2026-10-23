# 02：养老金安排与留存核算

Ticket ID: v05-cross-business/02

Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: 周恩宇

Directory: `backend/app/modules/cross/`

Status: planned — PM 已批准拆分；待负责人接包、前置满足和实施授权。

Accepted by: 未记录

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-P01—P06、X02—X05；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

加入实际入账范围、生活费口径、退订依赖、刷新及逐笔转账；处理部分成功、并发安排和未知，不造留存交易

## Blocked by

- [v05-cross-business/01：减支编排和共用计划骨架](01-expense-reduction.md)

## Start when

- 负责人明确接包并记录实际接受人；本轮尚未授权代码实施或运行评测。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] 实际入账、当前余额和用户选择的资金范围分开；留存额及是否包括未来已知代扣须明确采用。
- [ ] 整数分核算和比例尾差符合契约；历史支出不双减，取消未来 39 不增加当前收入。
- [ ] 退订依赖失败/未知时暂停相关转账；每笔执行前刷新事实并检查留存及同应用并发安排。
- [ ] 成功转账保留不重做；待办变化重新确认，留存不足不能自动降低；只查/取消后的新写入为零。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：未开始。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 9](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。
