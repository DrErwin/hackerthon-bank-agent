# 19：转账风险输入补可信父原话和受控跟进

Ticket ID: v05-birthday-platform-dependencies/19
Package: [生日及跨场景联动平台](../../v05-cross-linkage/packages/03-platform.md)
Spec: [可信父风险来源](../risk-parent-source-19.md)
Type: 开发
Owner: Erwin；root 按用户完成非比赛资料任务授权顺序实施
Directory: `backend/app/agent_platform/`
Status: in_progress
Accepted at: 2026-10-27
Blocked by: 无；已有持久父子关联与RiskConversation
Source issue: [Issue #345](https://github.com/DrErwin/hackerthon-bank-agent/issues/345)，转给Erwin / Assignee DrErwin
Core scenarios: XL-P01；跨场景内子转账仍检查用户原话风险
Verification: 本地真实组合红绿和受影响回归、独立两轴；新演示profile不属于本票批准。

- [ ] 真实父/子来源精确绑定，危险原话与受控跟进不丢，原参数检查不变。
- [ ] 关联/主体/step/plan/原请求缺失均暂停，不回退marker或猜测。
- [ ] 重启及历史跟进保持，公开证据不回显原话；无新风险事实/权限。
- [ ] 必要验证与证据、单目录分支PR、独立两轴与CI状态分开记录。
