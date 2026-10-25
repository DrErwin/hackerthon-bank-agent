# 03：生日核心与关键异常 E2E

Ticket ID: v05-cross-e2e/03

Package: [v05-cross-linkage/packages/05-cross-e2e：三主线 E2E 与全面验收](../../v05-cross-linkage/packages/05-cross-e2e.md)

Spec: [本工作组规格](../spec.md)

Type: 评测

Owner: Erwin（本执行对话代行本票评测）

Directory: `evals/cross/`

Status: blocked — 2026-10-25 准备已细化；真实运行blocked（业务05、前端02走查/实现及指定动作未知注入前置）。

Accepted by: Erwin（授权本执行对话）

Accepted at: 2026-10-25

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-B01—B07、相关 X；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

真实页面完整预订付款与差额释放；每种未知/失败/停止有银行及订单事实证据，不以接口单测代替页面路径

## Blocked by

- [v05-cross-platform/09：生日工具、权限与演示装配](../../v05-cross-platform/issues/09-birthday-runtime-wiring.md)
- [v05-cross-frontend/02：商品、配送和资金收尾页面](../../v05-cross-frontend/issues/02-birthday-ui.md)

- 顺序前置：[v05-cross-e2e/02：养老金核心与关键异常 E2E](02-monthly-arrangement-e2e.md)核心通过。
- [v05-cross-business/05：生日受控配送入口与结构化收尾视图](../../v05-cross-business/issues/05-birthday-delivery-and-structured-facts.md)。
- 未知变体依赖平台/银行线提供指定动作响应丢失入口（平台09 B28残留；该变体的前置，不额外阻塞已可执行的正常分支）。

## Start when

- 已获2026-10-25本轮执行授权；准备可立即做，真实运行按当前前置单独放行，不把领取当作验收通过。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] XL-B01 从真实页面和模型完成花/蛋糕预订付款，实际冻结500、消费467、释放33，订单/核销关联真实。
- [ ] XL-B02—B07 及共性变体覆盖缺信息、替代、部分失败、每阶段未知、取消/安全终止、预算刷新/占用。
- [ ] 逐动作核对银行操作与副作用次数，恢复不重买不重扣；未知/收尾未完成如实阻塞，完整失败批次保留。

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

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 20](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

## 2026-10-25 接包与执行细化

先按顺序完成01、02核心，再跑XL-B01—B07；业务05提供受控配送/结构化事实，前端02仍须PM走查与交付。平台09的B28故障装配残留独立阻塞B05等未知变体；不能用单测arm_response_loss代替页面全链。

运行入口、数据/故障要求见[runbook](../../../evals/cross/runbook.md)；逐场景可观察断言和独立变体见[覆盖映射](../../../evals/cross/coverage-plan.md)；证据字段和归档见[批次模板](../../../evals/cross/batch-template.md)。[当前准备快照](../../../evals/cross/readiness-2026-10-25.md)只证明准备，不是页面或模型结果。总状态由中控维护。
