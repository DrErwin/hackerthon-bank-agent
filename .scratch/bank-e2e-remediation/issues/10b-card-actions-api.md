# 10b：绑定结果条目的卡片动作

Ticket ID: bank-e2e-remediation/10b
Directory: `backend/app/api/`
Owner: Erwin / Codex 按用户授权代行
Status: implemented-merged
Priority: P1
Blocked by: bank-e2e-remediation/10a
Source issue: [#227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

增加明确的结果卡片动作入口。服务器核对来源任务归属、会话、版本、成功状态及所选条目；账单分类只使用来源范围，退订只接受来源清单内可银行取消的有效签约。服务端固定业务，不把隐藏指令填进聊天。动作请求幂等，重试不能新建第二份任务。

验收：伪造条目/跨人/旧会话/版本不匹配拒绝；订阅必须继续通过确认和专用验证；疑似消费及已退订项目不能发起取消。

规格：[修复规格](../spec.md) S03/S06；交付包：[01](../packages/01-demo-remediation.md)。

2026-10-23：实现见 [PR #246](https://github.com/DrErwin/hackerthon-bank-agent/pull/246)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
