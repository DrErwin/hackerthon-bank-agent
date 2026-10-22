# 08b：账单集成测试识别新版查询准入策略

Ticket ID: bank-e2e-remediation/08b
Package: [修复包](../packages/01-demo-remediation.md)
Spec: [规格](../spec.md)
Owner: Codex 按用户授权代行
Directory: `backend/app/modules/bills/`
Status: implemented-merged
Priority: P1
Parent: bank-e2e-remediation/08a
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

账单现有测试按策略版本枚举检查 L02 声明。08a 新增本人查询需提升策略版本至 v04-local-demo-read-6；本票先将该版本加入现有已知版本断言，保留 L02 准入、字段漂移及未知版本拒绝语义。只改该测试；运行行为不变。08a 生效后的组合验证另行记录。

2026-10-23：实现见 [PR #237](https://github.com/DrErwin/hackerthon-bank-agent/pull/237)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
