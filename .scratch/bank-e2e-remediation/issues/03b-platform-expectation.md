# 03b：订阅底座断言对齐

Ticket ID: bank-e2e-remediation/03b
Package: [修复包](../packages/01-demo-remediation.md)
Spec: [规格](../spec.md)
Owner: Codex 按用户授权代行
Directory: `backend/app/agent_platform/`
Status: ready-for-agent
Priority: P0
Parent: bank-e2e-remediation/03

取消对未经核实的外部平台名断言，改核对“在本行退不了”；保留疑似、不可取消、无安全门/银行执行。新文案禁止编造渠道的断言保留在票03订阅模块内。定向底座测试通过、GPT-6.1-sol双轴代审通过后合入，供票03重跑。
