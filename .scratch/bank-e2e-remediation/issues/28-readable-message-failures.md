# bank-e2e-remediation/28 实时错误丢失后仍能读到失败原因

Ticket ID: bank-e2e-remediation/28
Package: [Demo修复](../packages/01-demo-remediation.md)
Spec: [本轮规格](../business-e2e-spec.md) E06
Owner: Erwin（用户授权 Codex 代行）
Directory: `backend/app/api/`
Status: developed; verification complete; PR/user acceptance pending
Blocked by: none
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

票27审查发现失败路径只保存stream_error，不在消息列表展示。错误通知丢失时只读补查无法结束等待。将已有脱敏失败说明也持久化为助手消息；沿用错误事件和原任务状态，重试同一请求不重复添加失败消息，不重执行业务。

本轮实现、分层验证和边界见[走查记录](../../../evals/demo-remediation/business-e2e.md)。集中新 PR 待审，不自动合并。
