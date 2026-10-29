# 22：API可信子上下文保留持久父关联

Ticket ID: v05-birthday-platform-dependencies/22
Package: [跨场景平台与银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [API父关联](../api-child-parent-22.md)
Type: 开发
Owner: Erwin；root按本轮用户授权实施
Directory: `backend/app/api/`
Status: merged — PR #350 已合入 `ef8f9220`；2026-10-29 核对。原验证及审查按各批记录，CI 计费未启动；真实业务/页面和本人接受另见[v0.5 完成情况](../../../docs/versions/v0.5.0/completion.md)。

原交付时状态（历史）：ready_for_review
Accepted at: 2026-10-27
Blocked by: 无；已有ApplicationStore.parent_of_task
Source issue: [Issue #345](https://github.com/DrErwin/hackerthon-bank-agent/issues/345)，转给Erwin
Core scenarios: XL-P01子转账确认/验证/原号查询
Verification: 真实已有A2组合红绿、API已有权限/会话/恢复受影响检查；21完整P01独立消费。

- [x] 续办来源来自已认证同user/round的持久关联，原session/task门不变。
- [x] 子确认/验证完成及原号读取不重复银行写，根任务None、异主体/会话拒绝。
- [ ] 单目录PR、原始证据、独立两轴与CI状态分开记录，无模型重跑/共享库操作。

[验证](../api-child-parent-22-verification.md)：最终8项passed；原风险绑定暂停和测试误用终态查询的失败分别保留，不沿错误入口放宽动作。
