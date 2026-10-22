# 05：聊天续办可靠派发与隐私前置过滤

Ticket ID: bank-e2e-remediation/05
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `backend/app/api/`
Priority: P0
Status: ready-for-agent
Blocked by: bank-e2e-remediation/04
Core scenarios: S01 S02 S04 S07
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
将续办候选派发原任务，保存原请求与目标，重放不重复推进；讨论验证码不误拒，实际凭据不落库不入模型。

## Acceptance criteria
- [ ] HTTP 连续办理；重试/崩溃/重复消息；旧版本拒绝；实际凭据、反诈求助成对回归。
- [ ] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。
