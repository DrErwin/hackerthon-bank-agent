# 17：任务选项、草稿选择与查询刷新接口
Ticket ID: bank-e2e-remediation/17
Package: [bank-e2e-remediation/packages/01-demo-remediation：Demo 修复](../packages/01-demo-remediation.md)
Spec: [连续办理体验规格](../experience-spec.md)
Core scenarios: UX02、UX04、UX05、UX07、UX08
Type: 开发
Owner: Erwin（用户授权 Codex 代行）
Directory: `backend/app/api/`
Status: implemented — review/acceptance pending
Blocked by: bank-e2e-remediation/16
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)
Verification: 按规格核对对应用户场景；记录本地回归及真实联调，不能互相替代。相关变更集中一个PR。

- [x] 交付对应用户场景，复用已确认的接口和安全边界。
- [x] 正常、缺资料、失败、恢复与重复操作有可检查的行为证据。
- [x] 更新进度与验证限制；用户最终体验验收另记。


验证：[分层证据](../../../evals/demo-remediation/guided-experience.md)。代码与本地检查完成、真实主路径已验证；用户最终体验及Ringo专业审查未批准。
