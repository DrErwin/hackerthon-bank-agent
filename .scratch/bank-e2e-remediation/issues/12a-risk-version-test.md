# 12a：风险规则版本的集成断言

Ticket ID: bank-e2e-remediation/12a
Directory: `backend/app/agent_platform/`
Owner: Erwin / Codex 按用户授权代行
Status: implemented-merged
Priority: P0
Blocked by: 无；在12之前合入
Source issue: [#227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

票12升级安全规则版本，平台现有集成测试硬编码v1。改为从安全模块引用实际版本，继续断言审计来源含实际规则版本，避免在平台复制规则版本常量。仅测试适配，不改运行代码。验收：当前v1及12分支v2集成测试通过。

规格：[S05](../spec.md)；交付包：[01](../packages/01-demo-remediation.md)。

2026-10-23：实现见 [PR #248](https://github.com/DrErwin/hackerthon-bank-agent/pull/248)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
