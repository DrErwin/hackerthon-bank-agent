# 05：聊天续办可靠派发与隐私前置过滤

Ticket ID: bank-e2e-remediation/05
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `backend/app/api/`
Priority: P0
Status: implemented-merged
Blocked by: bank-e2e-remediation/04
Core scenarios: S01 S02 S04 S07
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
将续办候选派发原任务，保存原请求与目标，重放不重复推进；讨论验证码不误拒，实际凭据不落库不入模型。

## Acceptance criteria
- [x] HTTP 连续办理；重试/崩溃/重复消息；旧版本拒绝；实际凭据、反诈求助成对回归。
- [x] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。

2026-10-23：[PR #234](https://github.com/DrErwin/hackerthon-bank-agent/pull/234) 依赖 #233；730ed86 API 全目录145通过，新HTTP8项包括最终单笔银行流水及旧会话拒绝。GPT-6.1-sol 双轴代审通过；d597802 仅同步已代审的04选项上下文。真实模型/React组合验收仍待票11。

2026-10-23：实现见 [PR #234](https://github.com/DrErwin/hackerthon-bank-agent/pull/234)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
