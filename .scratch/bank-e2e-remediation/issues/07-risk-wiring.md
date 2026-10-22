# 07：风险输入接线与可办理 Demo 参数范围

Ticket ID: bank-e2e-remediation/07
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `backend/app/agent_platform/`
Priority: P0
Status: implemented-merged
Blocked by: bank-e2e-remediation/06
Core scenarios: S05
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
对话及后续补充进入风险判断；保留策略/证据来源；明确 demo 正常参数事实范围，不能所有输入默认低风险。

## Acceptance criteria
- [x] 正常 300/500/600 和风险配对；当前输入证据可回放；模型/检测器失败不冒充检出成功。
- [x] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。

2026-10-23：实现见 [PR #236](https://github.com/DrErwin/hackerthon-bank-agent/pull/236)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
