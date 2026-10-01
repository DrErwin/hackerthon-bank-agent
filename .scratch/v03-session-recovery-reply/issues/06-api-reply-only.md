# 06：API 仅回复接入

Type: task\
Status: in_progress (API implementation and validation underway)\
Ticket ID: v03-session-recovery-reply/06\
Package: [transfer-agent-framework/packages/01-vertical-backend：v0.3 纵向后端主链路](../../transfer-agent-framework/packages/01-vertical-backend.md)\
Spec file: [v03-session-recovery-reply/spec.md](../spec.md)\
Owner: Erwin（v0.3 纵向后端工作线；转账目录按临时安排）\
Directory: `backend/app/api/`\
Source issue: [Issue #24](https://github.com/DrErwin/hackerthon-bank-agent/issues/24)\
Spec: [新会话恢复与仅回复补票规格](../spec.md)\
Blocked by: None（05已通过PR #35合入并提供公开仅回复结果）\
Unlocks: 原票 10 的普通消息验收；原票 12 联合验收\
Review: 工程与契约审查；涉及身份、确认、验证、资金、隐私或审计时叠加安全审查\
Claimed by: Erwin（用户在本任务明确授权实施本票）\
Started at: 2026-10-01\
Branch: `codex/v03-session-recovery-reply-06`（PR #35 合入后以 main `54b6e7c8ef9f77a09d4ca4db41b66fea33e42fa8` 为基线）

## 业务目的

普通消息保存并收到助手回复，消息和 SSE 不挂多余转账任务；明确转账仍进入真实任务路径。

## 验收

- [ ] 消费 05 的公开理解结果；HTTP 202 与 MessageAccepted.task_id 可为空，任务稍后产生时按现有 SSE / 历史语义关联。
- [ ] 仅回复保留用户及助手消息，MessageView.task_ids 为空，不出现任务快照、确认、验证或银行调用；历史及断线重连一致。
- [ ] 重复同号同内容复用受理结果；同号异内容拒绝；后台中断 / 重启不能重复创建转账或用闲聊伪造任务。
- [ ] 普通“确认”文本不替代正式确认；消息输入与回复遵守现有秘密保护，错误不回显秘密。
- [ ] 明确转账、等待输入和专用确认 / 验证入口保持兼容；HTTP 用例覆盖闲聊、转账、失败、重复和 SSE。
- [ ] 记录仅回复后端证据，真实模型与 React 证据缺失时保留未验收，不因此将票 10 / v0.3 标为完成。

## 验证入口

HTTP + 消息历史 / 任务列表 / SSE，实际公共底座与可重复模型候选。

## 目录边界与交接

一票、一分支、一 PR 只修改本票 Directory；公开能力调用说明、模块文档和测试随本目录交付。本人规格、票据与项目跟踪对应过程条目可按队员开工规范更新。实施若确需额外契约或其他目录改动，先记录缺口并独立拆票，禁止在本票跨目录绕过。

依赖完成标准是前置票实际实现、公开入口可调用且 PR 合入，不能用写完文档代替。最终联合验收仍由原票 12 承担。

## Comments

- 2026-09-30：按用户“先补正式实施票”及六张单目录票方案确认补建；不是已实现功能，也不代表目录负责人本人领取或真人批准。GitHub #24 仍为开放缺口记录。

- 2026-10-01：前置 [v03-session-recovery-reply/05：Harness 无业务意图仅回复](05-harness-reply-only.md) 已经 [PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35) 合入 main（0613a1a），公开理解及 ReplyOnly 能力已提供，本票解除正式依赖阻塞。
- 2026-10-01：用户明确授权在新 worktree 实施本票。实现与验证现以合入后的 main 为基线；Issue #24 与 v0.3 联合验收保持开放。
- 2026-10-01：本地验证完整后端234 passed（168.83秒）、API单目录41 passed（116.02秒）、MockBank14 passed；三个API源文件Pyright 0 errors，compileall、链接及差异空白检查通过。Draft [PR #37](https://github.com/DrErwin/hackerthon-bank-agent/pull/37)已以main为基线打开（head a34661a），Repository checks已通过（[CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36812809932)）。Standards / Spec双轴独立AI复审均无发现；未记录Ringo真人安全批准。真实模型、React与票10 / 12联合验收未完成。
