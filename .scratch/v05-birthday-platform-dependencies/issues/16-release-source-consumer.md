# 16：限定释放审计消费原确认只读入口

Ticket ID: v05-birthday-platform-dependencies/16
Package: [生日联动平台](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [限定释放原确认接线](../release-source-16.md)
Owner: Erwin；root 按用户完成非比赛资料任务授权实施
Type: 开发
Directory: `backend/app/agent_platform/`
Status: merged — PR #343 已合入 `c760f0d0`；2026-10-29 核对。原验证及审查按各批记录，CI 计费未启动；真实业务/页面和本人接受另见[v0.5 完成情况](../../../docs/versions/v0.5.0/completion.md)。

原交付时状态（历史）：ready_for_review
Accepted at: 2026-10-27
Blocked by: [v05-birthday-platform-dependencies/17：生日跨会话限定释放只读原确认](17-release-confirmation-origin.md)
Source issue: [Issue #340](https://github.com/DrErwin/hackerthon-bank-agent/issues/340)，转给 Erwin
Core scenarios: XL-B01 跨会话结束时仅释放未消费冻结额
Verification: 真实本地 Harness/安全/MockBank 局部红绿；Cross09 组合完整断言；独立两轴及 CI 状态分开记录。

- [x] 真实 S2 只读原冻结批准，审计记录精确 ID/version；普通 get/history 不放宽。
- [x] 已消费部分不退款，未消费部分按原条款释放；重复收尾只观察原编号。
- [x] 来源缺失继续暂停，无审计批准不能提交释放。
- [x] 单目录提交、必要回归和原始证据，交独立 Standards/Spec 审查。

[验证记录](../release-source-16-verification.md)：有效红3 fail/1 pass，修后4 pass；准确主线组合受影响四文件28 pass，均无模型。Cross09完整实际消费与页面证据仍另记。
