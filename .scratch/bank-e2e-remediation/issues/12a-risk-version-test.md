# 12a：风险规则版本的集成断言

Ticket ID: bank-e2e-remediation/12a
Directory: `backend/app/agent_platform/`
Owner: Erwin / Codex 按用户授权代行
Status: in_progress
Priority: P0
Blocked by: 无；在12之前合入
Source issue: [#227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

票12升级安全规则版本，平台现有集成测试硬编码v1。改为从安全模块引用实际版本，继续断言审计来源含实际规则版本，避免在平台复制规则版本常量。仅测试适配，不改运行代码。验收：当前v1及12分支v2集成测试通过。

规格：[S05](../spec.md)；交付包：[01](../packages/01-demo-remediation.md)。
