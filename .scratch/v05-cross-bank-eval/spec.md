# 银行专项验收工作规格

Status: blocked — 2026-10-26 只读核查与责任判断完成；跨轮次旧对象边界拆出存储/服务候选票（待 Owner 确认防御纵深决策），本组新增评测收口票 02，待提供方合入后执行。

Owner: Erwin

Accepted by: Erwin（2026-10-25委派授权）

Accepted at: 2026-10-25

Package: [v05-cross-linkage/packages/06-bank-eval：银行专项验收](../v05-cross-linkage/packages/06-bank-eval.md)

## 范围与规则

本工作组以[共享规格](../v05-cross-linkage/spec.md)的用户故事、AI/Harness/确定性业务边界与 E2E 框架为需求，不再复制一套业务规则。公共差异见[公共约定方案](../v05-cross-linkage/contract-proposal.md)，其中未确认项不作为已冻结接口。

涉及目录：`evals/mockbank/`。每张票仍只修改一个归属目录。工作组将同一负责人工作集中编号，不允许以工作组为单位做跨目录大 PR。

## 独立票与依赖

- [v05-cross-bank-eval/01：银行事实和防重专项验收](issues/01-birthday-bank-evidence.md)。
- [v05-cross-bank-eval/02：跨轮次旧对象边界回归收口](issues/02-round-object-regression.md) — 依赖 [v05-bank-round-objects/01](../v05-bank-round-objects/issues/01-object-round-storage.md)、[02](../v05-bank-round-objects/issues/02-object-round-services.md)。

依赖、核心场景和可检查的验收写在各票。总顺序及跨组关系见[已批准拆票方案](../v05-cross-linkage/ticket-proposal.md)。

## 验收与完成

本工作组局部检查不替代真实页面、真实模型、HTTP、隔离模拟银行/生活服务 E2E。实际验证按票留证；专业安全审查、PM 体验接受、版本完成分别记录。本轮实际运行与缺口见[银行专项证据](../../evals/mockbank/birthday-evidence.md)。

## 接包与下一步

2026-10-25 中控在 Erwin 授权下正式委派 v05-cross-bank-eval/01，允许银行专项实施、运行及子代理审查。仅更新本工作组和 evals/mockbank/；包领取、共享项目跟踪和版本进度由中控统一维护。不得跳过公共约定和必要的安全审查。

本机技能检查：2026-10-25 四项通用技能文件均存在；本轮读取并遵循 implement（用户显式要求，disable-model-invocation，无专用 slash 调用工具）和 code-review 工作流，不冒称已执行 slash 工具。沿用共享规格 Further Notes 记录的团队来源基线 `d81f3a183412e71a5b1e84ca21bc1a35eea03a60`，本轮未安装或升级技能，未重新验证本机副本与来源逐字相同。原 spec/票复用，不重跑拆票。

当前执行对话、回交要求和依赖触发见[中控调度表](../v05-control/dispatch-2026-10-25.md)。共享进度由中控维护。
