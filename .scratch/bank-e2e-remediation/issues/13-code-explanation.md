# 13：验证码解释被误当凭据

Ticket ID: bank-e2e-remediation/13
Directory: `backend/app/audit/`
Owner: Erwin / Codex 按用户授权代行；安全规则AI代审
Status: implemented-merged
Priority: P0
Blocked by: 无
Source issue: [#227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

真实安全求助连续两次HTTP接受后失败。临时只读诊断确认 reply_only 已成功，输出过滤 SECRET_LABEL 将“验证码是保护您资金安全的最后一道防线”匹配为凭据，最终记 MODEL_UNDERSTANDING_FAILED。不是模型未理解，也不是输入过滤再次拒绝。

修复：验证码/短信码标签仅在后接实际代码形状时匹配凭据；密码、口令和其他凭据规则不放宽。代码值、裸六码语境、英文口令、审计脱敏继续拦截。解释文本不改写、不靠特例话术白名单。

验收：解释句可输出并保留完整含义；验证码值不可落盘或泄漏；安全求助真实模型+HTTP+React重跑，保留原两次失败。输出过滤检测、审计与平台回归分层记录。

规格：[S04](../spec.md)；交付包：[01](../packages/01-demo-remediation.md)。

2026-10-23：实现见 [PR #250](https://github.com/DrErwin/hackerthon-bank-agent/pull/250)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
