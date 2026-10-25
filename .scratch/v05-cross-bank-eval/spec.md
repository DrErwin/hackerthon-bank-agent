# 银行专项验收工作规格

Status: in_progress — 2026-10-25 Erwin授权中控委派执行；沿用批准规划，实际运行按依赖启动。

Owner: Erwin

Accepted by: Erwin（2026-10-25委派授权）

Accepted at: 2026-10-25

Package: [v05-cross-linkage/packages/06-bank-eval：银行专项验收](../v05-cross-linkage/packages/06-bank-eval.md)

## 范围与规则

本工作组以[共享规格](../v05-cross-linkage/spec.md)的用户故事、AI/Harness/确定性业务边界与 E2E 框架为需求，不再复制一套业务规则。公共差异见[公共约定方案](../v05-cross-linkage/contract-proposal.md)，其中未确认项不作为已冻结接口。

涉及目录：`evals/mockbank/`。每张票仍只修改一个归属目录。工作组将同一负责人工作集中编号，不允许以工作组为单位做跨目录大 PR。

## 独立票与依赖

- [v05-cross-bank-eval/01：银行事实和防重专项验收](issues/01-birthday-bank-evidence.md)。

依赖、核心场景和可检查的验收写在各票。总顺序及跨组关系见[已批准拆票方案](../v05-cross-linkage/ticket-proposal.md)。

## 验收与完成

本工作组局部检查不替代真实页面、真实模型、HTTP、隔离模拟银行/生活服务 E2E。实际验证按票留证；专业安全审查、PM 体验接受、版本完成分别记录。2026-10-25已委派准备与执行；实际结果待回交，不提前判通过。

## 接包与下一步

2026-10-25 Erwin授权中控分发剩余工作，本包据此委派执行。银行能力已合入，先核对隔离数据和实际接缝，再按票运行并留证；不得跳过公共约定和必要安全审查。

本机技能检查及来源说明沿用共享规格 Further Notes，实施时再检查 implement/code-review 的可用性。全过程只更新本人工作线和[项目跟踪](../../docs/01-项目跟踪.md)对应条目。

当前执行对话、回交要求和依赖触发见[中控调度表](../v05-control/dispatch-2026-10-25.md)。共享进度由中控维护。
