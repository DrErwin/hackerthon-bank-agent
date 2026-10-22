# 06：对话风险证据的确定性兜底

Ticket ID: bank-e2e-remediation/06
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `backend/app/security/`
Priority: P0
Status: implemented-merged
Blocked by: 无
Core scenarios: S04 S05
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
新增有限 demo 反诈判断结果入口与策略，未知/失败暂停；共享屏幕+催促保密等证据不得被低风险样例覆盖。

## Acceptance criteria
- [x] 正常/诈骗/求助/不确定成对；高风险停止敏感动作；缺证据暂停；不得由模型直接放行。
- [x] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。

2026-10-23：实现见 [PR #235](https://github.com/DrErwin/hackerthon-bank-agent/pull/235)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
