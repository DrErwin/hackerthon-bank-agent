# 03：生日核心与关键异常 E2E

Ticket ID: v05-cross-e2e/03

Package: [v05-cross-linkage/packages/05-cross-e2e：三主线 E2E 与全面验收](../../v05-cross-linkage/packages/05-cross-e2e.md)

Spec: [本工作组规格](../spec.md)

Type: 评测

Owner: Erwin（v0.5 阶段承接；包 05 本轮尚未领取）

Directory: `evals/cross/`

Status: planned — PM 已批准拆分；待负责人接包、前置满足和实施授权。

Accepted by: 未记录

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-B01—B07、相关 X；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

真实页面完整预订付款与差额释放；每种未知/失败/停止有银行及订单事实证据，不以接口单测代替页面路径

## Blocked by

- [v05-cross-platform/09：生日工具、权限与演示装配](../../v05-cross-platform/issues/09-birthday-runtime-wiring.md)
- [v05-cross-frontend/02：商品、配送和资金收尾页面](../../v05-cross-frontend/issues/02-birthday-ui.md)

## Start when

- 负责人明确接包并记录实际接受人；本轮尚未授权代码实施或运行评测。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] XL-B01 从真实页面和模型完成花/蛋糕预订付款，实际冻结500、消费467、释放33，订单/核销关联真实。
- [ ] XL-B02—B07 及共性变体覆盖缺信息、替代、部分失败、每阶段未知、取消/安全终止、预算刷新/占用。
- [ ] 逐动作核对银行操作与副作用次数，恢复不重买不重扣；未知/收尾未完成如实阻塞，完整失败批次保留。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。必须执行真实页面 → 真实模型 → HTTP → 隔离模拟银行/生活服务链路；单模块或离线结果不能替代。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：未开始。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 20](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。
