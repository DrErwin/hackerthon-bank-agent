# bank-e2e-remediation/27 等待回复时补读丢失的实时通知

Ticket ID: bank-e2e-remediation/27
Package: [Demo修复](../packages/01-demo-remediation.md)
Spec: [本轮规格](../business-e2e-spec.md) E06
Owner: 梁爽目录，用户授权 Codex 本轮代行
Directory: `frontend/`
Status: developed; verification complete; PR/user acceptance pending
Blocked by: none
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

浏览器断线/服务重启走查：后台任务 1ef672e1 已完成并持久化回复，但页面实时连接未收到消息、停在正在回复且禁用输入。等待期间每 15 秒串行读取原对话结果；提供主动查询入口。只读恢复，不能重发消息/转账/退订。正常收到回复、会话过期或组件卸载后停止补读。

本轮实现、分层验证和边界见[走查记录](../../../evals/demo-remediation/business-e2e.md)。集中新 PR 待审，不自动合并。
