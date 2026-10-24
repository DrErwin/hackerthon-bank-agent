# 01：生日动作与限定收尾安全门

Ticket ID: v05-cross-security/01

Package: [v05-cross-linkage/packages/02-security：安全边界与专项核验](../../v05-cross-linkage/packages/02-security.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin（v0.5 本阶段统一负责）

Directory: `backend/app/security/`

Status: planned — PM 已批准拆分；待负责人接包、前置满足和实施授权。

Accepted by: 未记录

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-B05—B07、X05—X08；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

冻结/下单/核销按声明确认与验证；收尾只释放原冻结未消费部分。测试越权、篡改、过期、未知、必要审计失败；复用现有执行器

## Blocked by

- [v05-cross-platform/01：公共模型落地](../../v05-cross-platform/issues/01-public-models.md)

## Start when

- 负责人明确接包并记录实际接受人；本轮尚未授权代码实施或运行评测。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。
- C6/C7 的资金和隐私规则由 Erwin 按本阶段授权本人审阅并记录结论；本次转派本身不算确认通过。

## Acceptance criteria

- [ ] 每种新动作的权限、副作用、确认、验证、审计规则明确，不能由模型填写放行结果。
- [ ] 冻结时限定授权绑定本人/任务/轮次/原冻结；取消或安全终止只能收尾，不批准购买。
- [ ] 存在未知在途先核对，已消费不退，零剩余不提交零金额释放；参数篡改、过期或越权拒绝。
- [ ] 必要审计或授权事实不可用时按原规则阻止敏感执行；确认及验证复用不扩大原授权范围。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：未开始。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 13](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（责任更新）：本票本阶段执行由 Erwin 承担；具体票的开工、实现和验证状态仍按实际结果记录。
