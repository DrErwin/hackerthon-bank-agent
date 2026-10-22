# 09c：提供实际完成的账单查询范围

Ticket ID: bank-e2e-remediation/09c
Directory: `backend/app/modules/bills/`
Owner: Erwin / Codex 按用户授权代行
Status: ready-for-agent
Priority: P1
Blocked by: bank-e2e-remediation/09
Source issue: [#227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

代审发现异常查询结果没有范围字段，创建时的继承范围又可能被用户新要求覆盖。异常入口提供 `completed_scope`：从同用户/轮次/任务/会话检查点读取最终成功查询的日期与账户，返回已有 BillScope；未成功不给范围。平台09b保存实际完成范围，后续才能准确继承。

验收：9月汇总→明确8月异常核对→明细保持8月；账户选择变化也保留。不能用初始继承值冒充最终实际范围。

规格：[修复规格](../spec.md) S06；交付包：[01](../packages/01-demo-remediation.md)。合入顺序09c→09b→09a。
