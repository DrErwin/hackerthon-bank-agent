# v0.5 账单类型化输入入口

Status: in_progress
Owner: Erwin
Accepted by: Erwin 授权执行对话
Accepted at: 2026-10-25

## Problem Statement

联动已按现行契约派发账单输入，公开工厂仍只接收聊天信封，导致减支和养老金取不到账单依据。
来源：[v05-cross-platform/03：受控子任务衔接](../v05-cross-platform/issues/03-child-task-dispatch.md)末尾与[前端盘点 G4](../v05-cross-frontend/research/backend-api-surface.md)。
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../v05-cross-linkage/packages/01-platform-bank.md)。

## Solution

使三个现有公开工厂接收各自声明的 BillSummarizeInput、DetectAnomaliesInput、GenerateReportInput，仍由原服务、安全读取和银行提供真实依据。已批准范围只补接线，不重新设计业务。

## User Stories

1. 用户在减支中能取得指定账户、期间及对照期的真实统计。
2. 用户在养老金中能取得真实流水明细，供联动选择入账。
3. 类型化调用者能按既有 locate/single/scan 模式核对银行记录；locate 返回候选，不擅选一笔。
4. 报告调用保留目的和对比范围，分享目的不授予第三方访问权限。
5. 普通聊天仍可澄清、取消、恢复，读权限不放宽。

## Implementation Decisions

仅账单目录代码、测试、模块文档及本工作组材料。复用冻结公共模型及原服务；类型化约束独立于旧聊天解析保存，任务身份只从 TrustedContext 获取。相同任务重放不重复读取，参数变化拒绝；临时故障在原范围重试。不同能力的输入或裸字典拒绝。

## Testing Decisions

核心场景：BI01 summary + comparison；BI02 details + category；BI03 anomaly locate/single/scan；BI04 report purpose + comparison；BI05 权限拒绝、故障重试、重放冲突和跨会话恢复；BI06 普通聊天回归。
在公开注册工厂和真实 Harness.dispatch_child 接缝测试；使用隔离临时 SQLite、种子银行、真实安全执行器，规划器与风险策略为明确替身。单模块及平台/联动回归独立记录，不等同真实模型、HTTP、页面 E2E 或真人接受。后续联合验收复用联动 E2E 包，本票只解除账单入口依赖。

## Out of Scope

不改平台、安全、银行、联动、前端、共享项目跟踪和版本完成状态。不调用真实模型、不变更共享数据、不合并 PR。

## Further Notes

2026-10-25 已读取本机 to-spec、to-tickets、implement、code-review 文件；前三项未在当前会话注册为可调用技能，按已读流程执行，不宣称已调用。来源沿用团队基线 d81f3a183412e71a5b1e84ca21bc1a35eea03a60，未安装或升级。用户已明确本票目录、单票粒度、公开工厂验证接缝和实施授权。按 code-review 双轴子代理审查并使用 pr 模板交付。
