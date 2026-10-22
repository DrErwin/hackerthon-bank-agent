# 10b：绑定结果条目的卡片动作

Ticket ID: bank-e2e-remediation/10b
Directory: `backend/app/api/`
Owner: Erwin / Codex 按用户授权代行
Status: ready-for-agent
Priority: P1
Blocked by: bank-e2e-remediation/10a
Source issue: [#227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

增加明确的结果卡片动作入口。服务器核对来源任务归属、会话、版本、成功状态及所选条目；账单分类只使用来源范围，退订只接受来源清单内可银行取消的有效签约。服务端固定业务，不把隐藏指令填进聊天。动作请求幂等，重试不能新建第二份任务。

验收：伪造条目/跨人/旧会话/版本不匹配拒绝；订阅必须继续通过确认和专用验证；疑似消费及已退订项目不能发起取消。

规格：[修复规格](../spec.md) S03/S06；交付包：[01](../packages/01-demo-remediation.md)。
