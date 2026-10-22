# 09a：固定同一会话的账单来源

Ticket ID: bank-e2e-remediation/09a
Directory: `backend/app/api/`
Owner: Erwin / Codex 按用户授权代行
Status: ready-for-agent
Priority: P1
Blocked by: bank-e2e-remediation/09b
Source issue: [#227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

在消息受理时固定同一用户、轮次、会话、聊天中最近的已完成账单任务，随消息工作项持久化。处理中重新检查归属，不从其他聊天或旧会话继承。来源仅供只读续查，不授权转账或审批。

验收：换聊天、换用户、换会话不能串范围；重试不改来源；没有合格来源时按原流程澄清。

依赖：既有 API 消息工作项。规格：[修复规格](../spec.md) S06；交付包：[01](../packages/01-demo-remediation.md)。
