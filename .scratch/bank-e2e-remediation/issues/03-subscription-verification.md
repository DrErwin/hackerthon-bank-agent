# 03：退订验证动作与清单事实修复

Ticket ID: bank-e2e-remediation/03
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `backend/app/modules/subscription/`
Priority: P0
Status: in_progress
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

2026-10-23：823d8aa / [PR #230](https://github.com/DrErwin/hackerthon-bank-agent/pull/230) 已开发；原回归4失败，修复后全模块48通过；GPT-6.1-sol双轴代审无阻塞。等待CI与合入，完整真实订阅路径仍待票11。

CI发现API和底座两处测试将“微信支付/支付宝”当成必须事实，1244通过/2失败。新增本票前置 [03a API断言](03a-api-expectation.md)、[03b底座断言](03b-platform-expectation.md)，各单目录提交；顺序合入后本票同步main重跑。修复不恢复虚构渠道。

2026-10-23：03a [PR #231](https://github.com/DrErwin/hackerthon-bank-agent/pull/231) 21ea91e、03b [PR #232](https://github.com/DrErwin/hackerthon-bank-agent/pull/232) 790590f 均经 GPT-6.1-sol 双轴代审及 CI 通过后合入。本票同步主线后 CI 通过，已由 [PR #230](https://github.com/DrErwin/hackerthon-bank-agent/pull/230) 合入 240d814。开发与合入完成，真实页面全路径仍待票11。
