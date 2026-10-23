# bank-e2e-remediation/25 账单刷新保留已选择范围

- Ticket ID: bank-e2e-remediation/25
- Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
- Spec: [business-e2e-spec.md](../business-e2e-spec.md) E04
- Owner: Erwin（用户授权 Codex 本轮修复）
- Directory: backend/app/api/
- Status: developed; verification complete; PR/user acceptance pending
- Blocked by: none
- Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

真实 HTTP 走查发现：账单首次查询后，用户已选择账户；点击刷新却重播最初缺账户的请求，再次追问。刷新应按已完成结果的实际账户、日期、查询类型和分类重新读取银行。回归覆盖选择后的范围及明细分类，不靠原始话语猜测范围。

本轮实现、分层验证和边界见[走查记录](../../../evals/demo-remediation/business-e2e.md)。集中新 PR 待审，不自动合并。
