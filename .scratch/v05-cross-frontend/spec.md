# 联动页面体验工作规格

Status: planning-approved — 2026-10-24 PM 已确认业务顺序、交付包与拆分；公共契约细节、实际接包及实施尚待完成。

Owner: 梁爽（六水协助）

Accepted by: 未记录

Package: [v05-cross-linkage/packages/04-frontend：联动页面体验](../v05-cross-linkage/packages/04-frontend.md)

## 范围与规则

本工作组以[共享规格](../v05-cross-linkage/spec.md)的用户故事、AI/Harness/确定性业务边界与 E2E 框架为需求，不再复制一套业务规则。公共差异见[公共约定方案](../v05-cross-linkage/contract-proposal.md)，其中未确认项不作为已冻结接口。

涉及目录：`frontend/`。每张票仍只修改一个归属目录。工作组将同一负责人工作集中编号，不允许以工作组为单位做跨目录大 PR。

## 独立票与依赖

- [v05-cross-frontend/01：总方案、子确认和结果页面](issues/01-plan-and-child-interactions.md)。
- [v05-cross-frontend/02：商品、配送和资金收尾页面](issues/02-birthday-ui.md)。

依赖、核心场景和可检查的验收写在各票。总顺序及跨组关系见[已批准拆票方案](../v05-cross-linkage/ticket-proposal.md)。

## 验收与完成

本工作组局部检查不替代真实页面、真实模型、HTTP、隔离模拟银行/生活服务 E2E。实际验证按票留证；专业安全审查、PM 体验接受、版本完成分别记录。所有票当前未实施/未运行。

## 接包与下一步

PM 本次批准的是规划和拆票，未替本工作组负责人领取，也未指派代码实施。正式接包后记录 Accepted by/at，按当前依赖选择票推进；不得跳过公共约定和必要的安全审查。

本机技能检查及来源说明沿用共享规格 Further Notes，实施时再检查 implement/code-review 的可用性。全过程只更新本人工作线和[项目跟踪](../../docs/01-项目跟踪.md)对应条目。
