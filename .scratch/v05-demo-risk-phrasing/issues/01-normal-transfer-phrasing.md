# 01：常见转账语序保留既有演示风险边界

Ticket ID: v05-demo-risk-phrasing/01
Package: [bank-e2e-remediation/packages/01-demo-remediation：Demo 修复](../../bank-e2e-remediation/packages/01-demo-remediation.md)
Spec: [有限演示转账语序修复](../spec.md)
Type: 开发
Owner: Erwin；Codex 按本轮已授权子任务实施
Directory: `backend/app/security/`
Status: merged — PR #324 已合入 `16487651`；2026-10-29 核对。原验证与审查按各批记录，CI 计费未启动；实际结果与待接受项见[v0.5 完成情况](../../../docs/versions/v0.5.0/completion.md)。

原交付时状态（历史）：implemented — review/acceptance pending
Blocked by: None
Core scenarios: [RP01–RP04](../spec.md#user-stories--core-scenarios)
Source issue: [Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)

## What to build

仅在已有参数绑定演示数据下，让两种有限普通转账语序得到相同分类；原始未知、危险及无数据请求保持原有暂停/终止边界。

## Acceptance criteria

- [x] 原“转账500元给妈妈”失败回归先失败，修复后通过；旧语序、已有礼貌前缀/账户/金额保持。
- [x] 危险前后缀、否定与未知附句不能沿用低风险夹具；正向威胁优先 HIGH。
- [x] 无夹具暂停，真实新收款人覆盖夹具熟悉收款人，检测异常不回退低风险。
- [x] 实现只改本目录及自有规格/票据/验证；独立分支交中控两轴审查。

Verification: 既有真实安全策略接缝的定向回归 + 安全目录及受影响装配/可信输入回归；真实模型/页面复验由中控安排，非本票局部通过可替代。

## Comments

2026-10-27：中控明确分派本票，已领取。保留原页面失败证据与 #160 未完成事实。

局部交付：[验证记录](../verification.md)。独立审查、合入与整体页面复验待中控处理；未代签本人安全批准。
