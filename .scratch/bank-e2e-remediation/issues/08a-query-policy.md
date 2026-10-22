# 08a：本人账户与联系人查询声明准入

Ticket ID: bank-e2e-remediation/08a
Package: [修复包](../packages/01-demo-remediation.md)
Spec: [规格](../spec.md)
Owner: Codex 按用户授权代行
Directory: `backend/app/security/`
Status: implemented-merged
Priority: P1
Parent: bank-e2e-remediation/08
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

安全侧独立保存两条只读公开声明 `transfer.list_accounts` 与 `transfer.list_payees`；只用现有 `transfer.read` 权限、当前本人/轮次及既有私有银行读取。任意声明漂移、越权或未知能力拒绝，不扩大写权限。平台08另票注册及实现，不在本票放业务代码。

验收：两条正常声明通过；身份/轮次与安全属性漂移拒绝；既有转账安全回归通过。新查询经真实银行/HTTP及页面验证由08和11负责。

2026-10-23：实现见 [PR #239](https://github.com/DrErwin/hackerthon-bank-agent/pull/239)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
