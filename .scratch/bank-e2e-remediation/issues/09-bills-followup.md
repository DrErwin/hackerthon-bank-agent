# 09：账单范围与明细续查

Ticket ID: bank-e2e-remediation/09
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `backend/app/modules/bills/`
Priority: P1
Status: ready-for-agent
Blocked by: bank-e2e-remediation/04
Core scenarios: S06
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
常用范围或明确可点替代；分类追问继承已选日期/账户，陌生扣款走已有核对能力。

模块通过 `start(..., inherited_scope=...)` 接收平台已核实的 BillScope；只在没有新日期/账户要求的追问中继承。API 来源绑定与平台传递分别由 09a、09b 实现，避免跨目录混票。

## Acceptance criteria
- [ ] 日期/账户不丢失；超范围说明不引用不存在入口；只查本人事实。
- [ ] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。
