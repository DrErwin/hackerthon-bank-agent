# 三主线 E2E 与全面验收工作规格

Status: in_progress — 2026-10-25 Erwin授权中控委派执行；沿用批准规划，实际运行按依赖启动。

Owner: Erwin（v0.5阶段；委派AI执行）

Accepted by: Erwin（2026-10-25委派授权）

Accepted at: 2026-10-25

Package: [v05-cross-linkage/packages/05-cross-e2e：三主线 E2E 与全面验收](../v05-cross-linkage/packages/05-cross-e2e.md)

## 范围与规则

本工作组以[共享规格](../v05-cross-linkage/spec.md)的用户故事、AI/Harness/确定性业务边界与 E2E 框架为需求，不再复制一套业务规则。公共差异见[公共约定方案](../v05-cross-linkage/contract-proposal.md)，其中未确认项不作为已冻结接口。

涉及目录：`evals/cross/`。每张票仍只修改一个归属目录。工作组将同一负责人工作集中编号，不允许以工作组为单位做跨目录大 PR。

## 独立票与依赖

- [v05-cross-e2e/01：减支核心与关键异常 E2E](issues/01-expense-reduction-e2e.md)。
- [v05-cross-e2e/02：养老金核心与关键异常 E2E](issues/02-monthly-arrangement-e2e.md)。
- [v05-cross-e2e/03：生日核心与关键异常 E2E](issues/03-birthday-e2e.md)。
- [v05-cross-e2e/04：三目标完整覆盖与体验收口](issues/04-full-coverage-and-ux.md)。

依赖、核心场景和可检查的验收写在各票。总顺序及跨组关系见[已批准拆票方案](../v05-cross-linkage/ticket-proposal.md)。

## 验收与完成

本工作组局部检查不替代真实页面、真实模型、HTTP、隔离模拟银行/生活服务 E2E。实际验证按票留证；专业安全审查、PM 体验接受、版本完成分别记录。2026-10-25已委派准备与执行；实际结果待回交，不提前判通过。

## 接包与下一步

2026-10-24责任转派后，2026-10-25 Erwin进一步授权中控分发剩余工作，包05据此委派启动。先准备，按实际页面与运行依赖逐条验收；不得跳过公共约定和必要安全审查。

本轮技能文件检查与能力限制见[准备快照](../../evals/cross/readiness-2026-10-25.md)。未重新生成规格/票据；沿用已批准26条设计，按[运行准备](../../evals/cross/runbook.md)、[覆盖映射](../../evals/cross/coverage-plan.md)及[证据模板](../../evals/cross/batch-template.md)执行。子代理独立规范/规格审查见[审查记录](review.md)。

当前执行对话、回交要求和依赖触发见[中控调度表](../v05-control/dispatch-2026-10-25.md)。共享进度由中控维护。
