# 10a：确定的卡片动作直接进入现有业务

Ticket ID: bank-e2e-remediation/10a
Directory: `backend/app/agent_platform/`
Owner: Erwin / Codex 按用户授权代行
Status: ready-for-agent
Priority: P1
Blocked by: bank-e2e-remediation/09b
Source issue: [#227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

给服务端已校验的卡片动作提供确定能力入口，只允许账单明细、异常核对、单项订阅取消；复用现有任务、审计、权限、确认和验证链路，不经过模型再次猜测选择。重试复用原任务，来源只为业务范围，不是审批。

验收：卡片进入准确能力；订阅仍暂停确认，不能通过此入口直接转账或审批；无伪造模型调用证据。

规格：[修复规格](../spec.md) S03/S06；交付包：[01](../packages/01-demo-remediation.md)。
