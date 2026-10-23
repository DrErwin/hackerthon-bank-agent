# 01：银行事实和防重专项验收

Ticket ID: v05-cross-bank-eval/01

Package: [v05-cross-linkage/packages/06-bank-eval：银行专项验收](../../v05-cross-linkage/packages/06-bank-eval.md)

Spec: [本工作组规格](../spec.md)

Type: 评测

Owner: Erwin

Directory: `evals/mockbank/`

Status: planned — PM 已批准拆分；待负责人接包、前置满足和实施授权。

Accepted by: 未记录

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-B01、B03—B07；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

固定/变价商品、冻结/核销/释放、订单绑定、各动作同号/异参、未知查询与故障后数据一致性有可重复证据

## Blocked by

- [v05-cross-platform/07：生日模拟银行与网关](../../v05-cross-platform/issues/07-birthday-bank-services.md)

## Start when

- 负责人明确接包并记录实际接受人；本轮尚未授权代码实施或运行评测。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] 银行事实证明冻结500、消费467、释放33；消费199后无在途可释放301。
- [ ] 各写动作的重复、异参、未知回查、订单防重扣、跨用户/轮次和存储故障均有可重复记录。
- [ ] 固定种子重置后结论可复现，实际银行结果及账本计数一致；报告清楚标为银行专项，非页面 E2E。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：未开始。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 18](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。
