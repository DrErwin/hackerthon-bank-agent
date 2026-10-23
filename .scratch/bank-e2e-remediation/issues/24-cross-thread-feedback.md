# bank-e2e-remediation/24 新对话误接旧任务的反馈

Ticket ID: bank-e2e-remediation/24
Package: [Demo修复](../packages/01-demo-remediation.md)
Spec: [本轮规格](../business-e2e-spec.md)
Owner: Erwin（用户授权 Codex 代行）
Directory: `backend/app/api/`
Blocked by: none
Status: developed; verification complete; PR/user acceptance pending
- 目录: backend/app/api/
- 来源: Issue #227；business-e2e-spec.md E06
- 发现: 真实 GLM HTTP 走查 E03，模型提出另一对话中的待确认任务；权限检查正确阻止，但消息一直停在 continuation_ready，重试仍失败。
- 修改: 保持禁止跨对话续办，返回可读的终态回复，提示回原对话；不修改原任务、不重复执行。
- 验收: 回归先红后绿；原任务版本与银行操作不变；消息完成且可继续新请求。

本轮实现、分层验证和边界见[走查记录](../../../evals/demo-remediation/business-e2e.md)。集中新 PR 待审，不自动合并。
