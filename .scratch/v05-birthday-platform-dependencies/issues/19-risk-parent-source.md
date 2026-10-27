# 19：转账风险输入补可信父原话和受控跟进

Ticket ID: v05-birthday-platform-dependencies/19
Package: [生日及跨场景联动平台](../../v05-cross-linkage/packages/03-platform.md)
Spec: [可信父风险来源](../risk-parent-source-19.md)
Type: 开发
Owner: Erwin；root 按用户完成非比赛资料任务授权顺序实施
Directory: `backend/app/agent_platform/`
Status: ready_for_review
Accepted at: 2026-10-27
Blocked by: 无；已有持久父子关联与RiskConversation
Source issue: [Issue #345](https://github.com/DrErwin/hackerthon-bank-agent/issues/345)，转给Erwin / Assignee DrErwin
Core scenarios: XL-P01；跨场景内子转账仍检查用户原话风险
Verification: 本地真实组合红绿和受影响回归、独立两轴；新演示profile不属于本票批准。

- [x] 真实父/子来源精确绑定，危险原话与受控跟进不丢，原参数检查不变。
- [x] 关联/主体/step/plan/原请求缺失均暂停，不回退marker或猜测。
- [x] 重启及历史跟进保持，公开证据不回显原话；无新风险事实/权限。
- [x] 必要验证与证据、单目录分支PR、独立两轴与CI状态分开记录。

[验证记录](../risk-parent-source-19-verification.md)：四文件48 passed后Spec抓出原请求重放的误插入，真实2红后移除误块，五文件最终88 passed；两轴0剩余必须项。实际危险父请求通过真实dispatch到安全BLOCK、普通仍确认等待，均零银行写。本人随后明确批准的具体P01演示profile在20/21另票，本票不实现风险放行。
