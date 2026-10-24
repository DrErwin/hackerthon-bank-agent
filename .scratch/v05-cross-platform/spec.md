# 公共接缝与模拟银行工作规格

Status: in_progress — 2026-10-24 平台底座七票（01/02/03/04/06/07/08）经子代理审查合入（PR #256—#263，含 #261 修正），票面均已回交；票 05/09 阻塞于 v05-cross-business（未在平台目录代写）。Ringo 安全审查、三主线 E2E 与真人签核按各自流程另行记录。

Owner: Erwin

Accepted by: Erwin

Accepted at: 2026-10-24

Execution assignee: 票 01 的公共约定准备由 Erwin 指派 Codex；其余实施执行者仍待指派。本轮未启动模型编码。

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../v05-cross-linkage/packages/01-platform-bank.md)

## 范围与规则

本工作组以[共享规格](../v05-cross-linkage/spec.md)的用户故事、AI/Harness/确定性业务边界与 E2E 框架为需求，不再复制一套业务规则。公共差异见[公共约定方案](../v05-cross-linkage/contract-proposal.md)，其中未确认项不作为已冻结接口。

涉及目录：`backend/app/agent_platform/`, `backend/app/api/`, `backend/app/contracts/`, `backend/app/services/`, `backend/app/storage/`。每张票仍只修改一个归属目录。工作组将同一负责人工作集中编号，不允许以工作组为单位做跨目录大 PR。

## 独立票与依赖

- [v05-cross-platform/01：公共模型落地](issues/01-public-models.md)。
- [v05-cross-platform/02：任务关系与安排记录持久化](issues/02-durable-task-relations.md)。
- [v05-cross-platform/03：Harness 受控子任务衔接](issues/03-child-task-dispatch.md)。
- [v05-cross-platform/04：联动任务与子交互 API](issues/04-parent-child-api.md)。
- [v05-cross-platform/05：联动主入口及现有业务装配](issues/05-cross-runtime-wiring.md)。
- [v05-cross-platform/06：生日银行数据与原子提交](issues/06-bank-order-freeze-storage.md)。
- [v05-cross-platform/07：生日模拟银行与网关](issues/07-birthday-bank-services.md)。
- [v05-cross-platform/08：配送资料受控 API](issues/08-controlled-delivery-api.md)。
- [v05-cross-platform/09：生日工具、权限与演示装配](issues/09-birthday-runtime-wiring.md)。

依赖、核心场景和可检查的验收写在各票。总顺序及跨组关系见[已批准拆票方案](../v05-cross-linkage/ticket-proposal.md)。

## 验收与完成

本工作组局部检查不替代真实页面、真实模型、HTTP、隔离模拟银行/生活服务 E2E。实际验证按票留证；专业安全审查、PM 体验接受、版本完成分别记录。所有票当前未实施/未运行。

## 接包与下一步

Erwin 本次明确接受第一个包，要求细化票据后交其他人执行。九票沿用现有编号，逐票增加实施交接说明；不重新拆组，不改其他包领取状态。执行顺序、跨包前置及可复制的交接指令见[交接说明](handoff.md)。公共约定与安全审查仍须按真实结果记录。

本机技能检查及来源说明沿用共享规格 Further Notes，实施时再检查 implement/code-review 的可用性。全过程只更新本人工作线和[项目跟踪](../../docs/01-项目跟踪.md)对应条目。
