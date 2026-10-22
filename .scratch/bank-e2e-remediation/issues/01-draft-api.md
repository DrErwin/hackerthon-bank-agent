# 01：原任务补充与转账草稿修改入口

Ticket ID: bank-e2e-remediation/01
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `backend/app/api/`
Priority: P0
Status: in_progress
Blocked by: 无
Core scenarios: S01 S02 S07
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
F10 补付款账户；新增绑定任务版本的草稿修改入口，复用原转账续办；只允许未提交且等待输入/确认的转账。

## Acceptance criteria
- [ ] 同一 task_id 补字段；改金额/账户/收款人保留其他字段；旧确认不可批准；重放不重复修改；越权、过期交互、已提交任务拒绝。
- [ ] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。
