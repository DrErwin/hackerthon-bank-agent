# 08b：账单集成测试识别新版查询准入策略

Ticket ID: bank-e2e-remediation/08b
Package: [修复包](../packages/01-demo-remediation.md)
Spec: [规格](../spec.md)
Owner: Codex 按用户授权代行
Directory: `backend/app/modules/bills/`
Status: ready-for-agent
Priority: P1
Parent: bank-e2e-remediation/08a
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

账单现有测试按策略版本枚举检查 L02 声明。08a 新增本人查询需提升策略版本至 v04-local-demo-read-6；本票先将该版本加入现有已知版本断言，保留 L02 准入、字段漂移及未知版本拒绝语义。只改该测试；运行行为不变。08a 生效后的组合验证另行记录。
