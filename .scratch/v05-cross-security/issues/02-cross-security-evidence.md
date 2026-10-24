# 02：联动专项安全验证

Ticket ID: v05-cross-security/02

Package: [v05-cross-linkage/packages/02-security：安全边界与专项核验](../../v05-cross-linkage/packages/02-security.md)

Spec: [本工作组规格](../spec.md)

Type: 评测

Owner: Erwin（v0.5 本阶段统一负责）

Directory: `evals/security/`

Status: planned — PM 已批准拆分；待负责人接包、前置满足和实施授权。

Accepted by: 未记录

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-X02—X08、B05—B07；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

针对父子越权、旧确认、跨会话/轮次、外部文字注入、配送隐私及限定释放跑实测；AI 执行与 Ringo 真人签核分别记录

## Blocked by

- [v05-cross-platform/09：生日工具、权限与演示装配](../../v05-cross-platform/issues/09-birthday-runtime-wiring.md)
- [v05-cross-frontend/02：商品、配送和资金收尾页面](../../v05-cross-frontend/issues/02-birthday-ui.md)

## Start when

- 负责人明确接包并记录实际接受人；本轮尚未授权代码实施或运行评测。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] 对真实联动运行路径测试越权、旧确认、版本变化、跨会话/轮次和外部文字注入。
- [ ] 验证配送/账号/验证码的受控边界及必要审计失败，记录敏感原文不泄露的证据。
- [ ] 生日取消/安全终止的限定释放有实测，未知在途不能抢占释放或重新购买。
- [ ] 报告区分离线/真实模型/HTTP/页面证据与 Ringo 真人签核；不以 #160/#215 或历史通过记录替代新动作验证。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：未开始。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 19](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（责任更新）：本票本阶段执行由 Erwin 承担；具体票的开工、实现和验证状态仍按实际结果记录。
