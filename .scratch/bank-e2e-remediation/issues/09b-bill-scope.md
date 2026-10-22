# 09b：传递已核实账单范围

Ticket ID: bank-e2e-remediation/09b
Directory: `backend/app/agent_platform/`
Owner: Erwin / Codex 按用户授权代行
Status: implemented-merged
Priority: P1
Blocked by: bank-e2e-remediation/09, bank-e2e-remediation/09c
Source issue: [#227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

只对账单汇总、报告和异常核对，将服务器已保存的成功账单范围传给新查询。重新核对来源用户、轮次、会话和公共结果类型，保存来源引用；不接受模型生成的范围。原报告保持不变，新查询仍过银行读取权限门。

验收：餐饮明细/陌生扣款沿用原日期账户，显式新范围可重新选择；旧任务、其他用户或异常结果不能作为范围事实。

规格：[修复规格](../spec.md) S06；交付包：[01](../packages/01-demo-remediation.md)。

2026-10-23：联合测试发现本地演示账单读口未传递 parent_task_id，API提前启用会导致第二次账单读取被正确拒绝。调整合入顺序为09→09b→09a；09b先修正可信上下文一致性并通过直接Harness测试，09a再启用HTTP来源绑定。

2026-10-23：实现见 [PR #243](https://github.com/DrErwin/hackerthon-bank-agent/pull/243)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
