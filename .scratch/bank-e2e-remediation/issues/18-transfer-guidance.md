# 18：转账步骤选择与补充中修改
Ticket ID: bank-e2e-remediation/18
Package: [bank-e2e-remediation/packages/01-demo-remediation：Demo 修复](../packages/01-demo-remediation.md)
Spec: [连续办理体验规格](../experience-spec.md)
Core scenarios: UX02、UX04、UX05
Type: 开发
Owner: Erwin（用户授权 Codex 代行）
Directory: `backend/app/modules/transfer/`
Status: ready-for-agent
Blocked by: None
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)
Verification: 按规格核对对应用户场景；记录本地回归及真实联调，不能互相替代。相关变更集中一个PR。

- [ ] 交付对应用户场景，复用已确认的接口和安全边界。
- [ ] 正常、缺资料、失败、恢复与重复操作有可检查的行为证据。
- [ ] 更新进度与验证限制；用户最终体验验收另记。

