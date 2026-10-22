# 12：正常转账的标点与付款账户补充

Ticket ID: bank-e2e-remediation/12
Directory: `backend/app/security/`
Owner: Erwin / Codex 按用户授权代行
Status: implemented-merged
Priority: P0
Blocked by: bank-e2e-remediation/06
Source issue: [#227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

真实 HTTP 复验发现：给妈妈转300元，主账户A1，虽然参数有演示事实，仍因有限正常文本规则未覆盖标点/账户补充而 needs_attention。只扩展有限、明确的正常字段语法；危险文本先判，未知文本和未绑定参数仍暂停。不得把普通正文截断后当安全。

验收：正常语句可进入确认；同样前缀追加共享屏幕、保密、未知指令不得变成低风险；缺事实不放行。复用安全门测试及真实HTTP成对重跑。原失败保留在票11证据。

规格：[S05](../spec.md)；交付包：[01](../packages/01-demo-remediation.md)。

2026-10-23：实现见 [PR #249](https://github.com/DrErwin/hackerthon-bank-agent/pull/249)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
