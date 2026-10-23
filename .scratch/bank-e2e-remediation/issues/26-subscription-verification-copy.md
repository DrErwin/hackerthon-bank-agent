# bank-e2e-remediation/26 退订提示兼容同会话验证复用

Ticket ID: bank-e2e-remediation/26
Package: [Demo修复](../packages/01-demo-remediation.md)
Spec: [本轮规格](../business-e2e-spec.md) E01、E05
Owner: Erwin（用户授权 Codex 代行）
Directory: `backend/app/modules/subscription/`
Status: developed; verification complete; PR/user acceptance pending
Blocked by: bank-e2e-remediation/22
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

浏览器走查发现：确认说明总承诺“还要填一次短信验证码”，与允许复用本会话验证的实际流程不符。改为按页面提示完成所需验证，保留逐项确认和退订后果。只改文案，不改安全门或业务规则。

本轮实现、分层验证和边界见[走查记录](../../../evals/demo-remediation/business-e2e.md)。集中新 PR 待审，不自动合并。
