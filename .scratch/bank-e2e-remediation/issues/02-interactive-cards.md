# 02：可填写、可修改的卡片及可靠等待反馈

Ticket ID: bank-e2e-remediation/02
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `frontend/`
Priority: P0
Status: implemented
Blocked by: bank-e2e-remediation/01
Core scenarios: S01 S02 S03 S07 S08
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
卡片表单与明确选中的聊天续办共用 F10；修改直接更新原任务并显示新确认；等待不以固定计时结束；保留失败草稿；语音清楚标注演示。

## Acceptance criteria
- [ ] 金额/账户输入走真实接口；多任务明确选中；旧卡只读；失败可重试同请求；不自动授权。
- [ ] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。

2026-10-23：代码已开发，Draft PR [#229](https://github.com/DrErwin/hackerthon-bank-agent/pull/229)，head 346c439，Depends on PR #228。47 tests passed，build PASS；两轴 AI 审查发现的异步确认版本与会话失效问题已修复。未合入，完整验收与专业安全批准未完成。[首批真实页面证据](../verification-2026-10-23.md)。

2026-10-23 00:18：用户授权 GPT-6.1-sol 双轴代审通过；前序合入后同步main，代码与审查版本一致，47测试/build及更新后的CI通过。#229 已合入，提交 e4231b6；不是 Ringo 本人签核，票11完整验收待办。
