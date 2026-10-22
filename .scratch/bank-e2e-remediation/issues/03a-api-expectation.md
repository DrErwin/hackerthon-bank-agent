# 03a：订阅 API 断言对齐

Ticket ID: bank-e2e-remediation/03a
Package: [修复包](../packages/01-demo-remediation.md)
Spec: [规格](../spec.md)
Owner: Codex 按用户授权代行
Directory: `backend/app/api/`
Status: implemented-merged
Priority: P0
Parent: bank-e2e-remediation/03

取消对未经核实的外部平台名断言，改核对“在本行退不了”；保留疑似、不可取消及银行未改变。新文案禁止编造渠道的断言保留在票03订阅模块内。定向HTTP测试通过；GPT-6.1-sol双轴代审通过后合入，供票03重跑。

2026-10-23：实现见 [PR #231](https://github.com/DrErwin/hackerthon-bank-agent/pull/231)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
