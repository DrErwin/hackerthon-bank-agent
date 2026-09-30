# 05：Harness 无业务意图仅回复

Type: task\
Status: in_progress\
Owner: Erwin（v0.3 纵向后端工作线；转账目录按临时安排）\
Ticket ID: v03-session-recovery-reply/05\
Package: [transfer-agent-framework/packages/01-vertical-backend：v0.3 纵向后端主链路](../transfer-agent-framework/packages/01-vertical-backend.md)\
Directory: `backend/app/agent_platform/`\
Source issue: [Issue #24](https://github.com/DrErwin/hackerthon-bank-agent/issues/24)\
PR: [PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35)\
Spec: [新会话恢复与仅回复补票规格](../spec.md)\
Blocked by: 无新增依赖；原 Harness 票 09 已合入\
Unlocks: 06\
Review: 工程与契约审查；涉及身份、确认、验证、资金、隐私或审计时叠加安全审查\
Claimed by: Codex（按用户明确指示执行；用户身份未提供）\
Started at: 2026-10-01

## 业务目的

模型和底座能表达仅回复：普通闲聊或无明确业务意图时安全答复，不强造转账任务。

## 验收

- [x] 提供模型无业务候选与受控仅回复公开结果，API 可区分回复与转账；保持原 TransferProposal 与转账调用兼容。
- [x] 仅回复不登记业务任务、不调用转账 / 银行能力、不生成确认 / 验证或资金动作；不以成功转账任务包装普通回复。
- [x] 意图判断由模型 / Harness 完成，API 无关键词分类；模糊业务意图可追问但不编造收款人、金额或授权。
- [x] 聊天“确认”、诱导绕过验证或外部注入不能变成正式资金授权；输出及追踪仍遵守秘密隔离与脱敏规则。
- [x] 模型结果缺失、矛盾或失败时安全停止并返回受控错误，不默认转账；明确转账继续原公共能力路径。
- [x] 公开规划 / 理解入口与 DeepAgentPlanner 的模型接缝覆盖闲聊、模糊请求、确认文本、转账及异常；明确注明可重复模型与实际提供商证据的区别。

## 验证入口

模型适配接缝与 Harness 公共理解入口，断言无业务任务 / 银行调用；现有转账流程回归。

## 目录边界与交接

一票、一分支、一 PR 只修改本票 Directory；公开能力调用说明、模块文档和测试随本目录交付。本人规格、票据与项目跟踪对应过程条目可按队员开工规范更新。实施若确需额外契约或其他目录改动，先记录缺口并独立拆票，禁止在本票跨目录绕过。

依赖完成标准是前置票实际实现、公开入口可调用且 PR 合入，不能用写完文档代替。当前票只完成正式发布，未领取、未开始实现；最终联合验收仍由原票 12 承担。

## Comments

- 2026-09-30：按用户“先补正式实施票”及六张单目录票方案确认补建；不是已实现功能，也不代表目录负责人本人领取或真人批准。GitHub #24 仍为开放缺口记录。
- 2026-10-01：用户明确要求在新 worktree 完成剩余补票；按该指示开始本票实施，worktree 分支 `codex/v03-session-recovery-reply-05`。本地验收用例 33 项与后端全量回归 225 项通过；本地验收勾选不代表合入或 v0.3 联合验收完成。
- 2026-10-01：Harness 提供 `understand()` 和 `handle_message()` 两个公开结果入口，`ReplyOnly` 不创建任务或触发转账；保留 `start()` 和显式转账路径。模型缺失 / 冲突结果安全失败，凭据输入在建 trace 前拒绝；回复在返回前脱敏，`model.finished` 保存脱敏受控输出快照。完整模型请求（系统提示与会话上下文）在 Deep Agents 接缝不可见，`model.started` 如实标为证据缺失并说明原因。真实模型与 React 未验证；Ringo 真人审查及 PR 合入未完成。
- 2026-10-01：实现已推送并建立 [PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35)；提交 `6783212` 的 Repository checks 通过，等待 Ringo 真人审查。PR 未合并，票保持 `in_progress`，06 保持 `blocked`。
