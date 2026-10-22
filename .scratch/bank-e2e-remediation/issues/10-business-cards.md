# 10：账户与订阅逐项卡片和账单明细操作

Ticket ID: bank-e2e-remediation/10
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `frontend/`
Priority: P1
Status: ready-for-agent
Blocked by: bank-e2e-remediation/02, bank-e2e-remediation/03, bank-e2e-remediation/05, bank-e2e-remediation/08, bank-e2e-remediation/09
Core scenarios: S03 S06
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
本人账户、联系人、订阅及账单结果的最小操作入口；签约/疑似/已退订分组；结构化选择绑定目标。

## Acceptance criteria
- [ ] 所选条目准确；不把内部指令回填聊天冒充操作；无重复长文本；键盘和大字号检查。
- [ ] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。
