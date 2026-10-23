# 05：联动主入口及现有业务装配

Ticket ID: v05-cross-platform/05

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/agent_platform/`

Status: planned — PM 已批准拆分；待负责人接包、前置满足和实施授权。

Accepted by: 未记录

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-S01、XL-P01、X01、X07；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

自然目标进入 cross，账单/订阅/转账的公开调用具备真实工厂及配置；显式声明与安全上下文正确，原单项业务仍可用

## Blocked by

- [v05-cross-business/01：减支编排和共用计划骨架](../../v05-cross-business/issues/01-expense-reduction.md)

## Start when

- 负责人明确接包并记录实际接受人；本轮尚未授权代码实施或运行评测。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] 自然表达三个生活目标时进入已注册 cross；尚未实现目标明确受阻，不伪装成功。
- [ ] 真实账单/订阅/转账工厂及上下文在同一运行环境可调用，父子事件可追溯。
- [ ] 未注册能力、伪造范围或绕过安全门零业务写入；原单业务入口仍能办理。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：未开始。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 6](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。
