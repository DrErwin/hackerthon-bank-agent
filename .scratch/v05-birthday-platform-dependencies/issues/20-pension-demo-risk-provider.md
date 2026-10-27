# 20：P01有限演示风险提供方

Ticket ID: v05-birthday-platform-dependencies/20
Package: [v0.5安全交付包](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [P01明确标注的有限演示风险](../pension-demo-risk-20.md)
Type: 开发
Owner: Erwin；Codex按中控本轮分派实施
Directory: backend/app/security/
Status: in_progress
Accepted by: Erwin本轮中控分派，转达用户明确批准两笔限定演示范围；非最终真人安全接受
Accepted at: 2026-10-27
Blocked by: 无局部实施前置；真实来源依赖平台19，显式opt-in依赖后继平台21

本组17及以前已用，18/19为中控其他票，20按本轮分派独立占号；21为平台消费，不混入本分支。

## What to build

公开pension_demo_risk(inputs)；仅精确父原话、四项完整跟进及A1 ownA5/250000或savedA4/100000返回p01-marked-demo-v1的十二维模拟覆盖。真实危险先胜、银行两收款人维度独立，缺失来源/银行事实继续未知；其他输入沿现有危险或unknown。只提供函数和契约，不接运行时。

## 验收

- [ ] P20-1 两笔、四项跟进、银行新/常用/未知事实及分类层面的确认风险保持。
- [ ] P20-2 异参/额外参数/异源或缺字段/未知附言均不继承模拟覆盖。
- [ ] P20-3 危险前后缀与后续文本先胜，检测器异常不变成LOW。
- [ ] P20-4 原A2规则与输入不变、opaque引用，必要局部/目录回归和实际证据完成。
- [ ] 单目录独立PR交两轴审查；不自合入，不称实际P01、真人安全验收或#160完成。

## Comments

2026-10-27：中控确认仅四项原跟进，不额外扩展自由语法。历史缺捕捉来源不回填，新实际集成用新隔离案例。
