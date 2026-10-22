# 03：退订验证动作与清单事实修复

Ticket ID: bank-e2e-remediation/03
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `backend/app/modules/subscription/`
Priority: P0
Status: ready-for-agent
Blocked by: 无
Core scenarios: S03
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
验证阶段声明 verify；签约、疑似周期消费、已取消区分；未知外部渠道不编造操作路径。

## Acceptance criteria
- [ ] 确认后验证码可提交；重复验码不重复取消；疑似不显示已签约退订承诺。
- [ ] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。
