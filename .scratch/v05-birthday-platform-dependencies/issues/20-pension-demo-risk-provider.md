# 20：P01有限演示风险提供方

Ticket ID: v05-birthday-platform-dependencies/20
Package: [检测器与评测完整性交付包](../../v04-security/packages/01-detector-and-coverage.md)，本票按v0.5中控明确授权追加
Spec: [P01明确标注的有限演示风险](../pension-demo-risk-20.md)
Type: 开发
Owner: Erwin；Codex按中控本轮分派实施
Directory: backend/app/security/
Status: developed — 82 targeted / 656 security tests passed；独立两轴审查及平台集成待完成
Accepted by: Erwin本轮中控分派，转达用户明确批准两笔限定演示范围；非最终真人安全接受
Accepted at: 2026-10-27
Blocked by: 无局部实施前置；真实来源依赖平台19，显式opt-in依赖后继平台21
Delivery PR: [PR #347](https://github.com/DrErwin/hackerthon-bank-agent/pull/347)，已附当前任务，待中控两轴独立审查

本组17及以前已用，18/19为中控其他票，20按本轮分派独立占号；21为平台消费，不混入本分支。

## What to build

公开pension_demo_risk(inputs)；仅精确父原话、四项完整跟进及A1 ownA5/250000或savedA4/100000返回p01-marked-demo-v1的十二维模拟覆盖。真实危险先胜、银行两收款人维度独立，缺失来源/银行事实继续未知；其他输入沿现有危险或unknown。只提供函数和契约，不接运行时。

## 验收

- [x] P20-1 两笔、四项跟进、银行新/常用/未知事实及分类层面的确认风险保持。
- [x] P20-2 异参/额外参数/异源或缺字段/未知附言均不继承模拟覆盖。
- [x] P20-3 危险前后缀与后续文本先胜，检测器异常不变成LOW。
- [x] P20-4 原A2规则与输入不变、opaque引用，必要局部/目录回归和实际证据完成。
- [x] 单目录独立PR已交中控安排两轴审查（结果仍待）；不自合入，不称实际P01、真人安全验收或#160完成。

## Comments

2026-10-27：中控确认仅四项原跟进，不额外扩展自由语法。历史缺捕捉来源不回填，新实际集成用新隔离案例。

[实际验证与边界](../security20-verification.md)。实现提供函数，真实来源/运行时开启/HTTP与页面银行闭环仍按平台19/21及中控后继验收。
