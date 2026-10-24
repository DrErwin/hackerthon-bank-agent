# 09：生日工具、权限与演示装配

Ticket ID: v05-cross-platform/09

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/agent_platform/`

Status: blocked（跨包依赖）— 平台侧前置（票 05、08）中 08 已合入；05 又依赖 v05-cross-business/01，且本票直接前置 v05-cross-business/03（生日编排，Erwin 本阶段承接包）未实施；不能在平台目录代写 cross 业务。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: 待 Erwin 指派

Accepted by: 未记录（具体票的实施执行者）

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-B01、B05—B06、X07—X08；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

将真实网关、生日工具声明/执行门、配送引用和故障配置装配到既有运行环境，取消后只走限定收尾；原 S/P 入口继续可用

## Blocked by

- [v05-cross-platform/05：联动主入口及现有业务装配](05-cross-runtime-wiring.md)
- [v05-cross-business/03：生日编排及预算约束](../../v05-cross-business/issues/03-birthday-orchestration.md)
- [v05-cross-platform/08：配送资料受控 API](08-controlled-delivery-api.md)

## Start when

- 包负责人 Erwin 已于 2026-10-24 接包；本聊天只细化票据，具体执行者由 Erwin 另行指派并记录领取。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] 真实银行网关、执行器、联动工具、受控引用和演示种子在运行环境完整装配，无测试替身代替业务。
- [ ] 能力/工具声明和实际调用一致，每个敏感动作均走安全门；父子/操作/订单/冻结可追溯。
- [ ] 取消和安全终止后的恢复只推进必要收尾，未知不得变成新的购买；旧 S/P 入口不回归。

## 实施交接：把生日服务与安全规则真正接起来

1. 等待已列前置合入，包括 cross 生日模块、配送 API；银行服务和生日安全门通过 cross 生日票的依赖传递，不可跳过。
2. 把真实网关、工具声明、授权执行器、受控配送引用和隔离种子装配到原运行环境；核对每个声明与实际调用一致。
3. 取消/安全终止后只继续核对和限定释放，不恢复购买；执行结果未知时先走 B14 和必要对象查询，不换号重做。
4. 现有 XL-S/XL-P 装配保持可用；本票不以跨目录临时修补完成联动，发现业务/API/安全缺陷回原票。

**本票验证步骤**：在真实装配上核对正常生日链、未知回查与停止后的资金收尾，实际操作编号、冻结/订单和审计可对应；没有安全装配时写动作拒绝。页面与真实模型验收归 cross E2E/03。

**交付物与边界**：生日运行装配、受影响旧路径检查及供 E2E 复现的环境说明；不得宣称本票等同完整业务验收或 Ringo 真人签核。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：未开始。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 16](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（接包后细化）：Erwin 明确接受第一个交付包，授权本聊天完成拆票后交其他执行者实施。本票沿用原编号、目录和依赖；具体执行者尚未领取。总交接见[本包交接说明](../handoff.md)。
