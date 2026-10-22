# 08：本人账户余额和联系人只读能力

Ticket ID: bank-e2e-remediation/08
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `backend/app/agent_platform/`
Priority: P1
Status: ready-for-agent
Blocked by: bank-e2e-remediation/08a
Core scenarios: S01 S06
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
最小注册查询入口复用受控银行工具、会话身份与所有权；脱敏事实可供后续转账。

## Acceptance criteria
- [ ] 本人查询成功；跨用户与注入拒绝；零银行写操作。
- [ ] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。

2026-10-23：安全策略逐字段冻结公开能力，不能由平台自行开放。新增前置 [08a 查询声明准入](08a-query-policy.md)，保持安全与平台各自单目录审查。
