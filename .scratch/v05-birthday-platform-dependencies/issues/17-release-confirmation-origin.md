# 17：生日跨会话限定释放只读原确认

Ticket ID: v05-birthday-platform-dependencies/17
Package: [生日联动安全](../../v05-cross-linkage/packages/02-security.md)
Spec: [限定释放原确认只读来源](../release-confirmation-17.md)
Type: 开发
Owner: Erwin；Codex按用户完成非比赛资料任务及中控本轮分派实施
Directory: `backend/app/security/`
Status: merged — PR #342 已合入 `dcb989a8`；2026-10-29 核对。原验证及审查按各批记录，CI 计费未启动；真实业务/页面和本人接受另见[v0.5 完成情况](../../../docs/versions/v0.5.0/completion.md)。

原交付时状态（历史）：developed — 47 targeted / 574 security tests passed; independent review/consumer integration pending
Accepted by: Erwin本轮中控明确分派；非本人最终安全接受
Accepted at: 2026-10-27
Blocked by: 无实施前置；335/main已含原会话退休及确认历史，平台16后继消费
Source issue: [Issue #340](https://github.com/DrErwin/hackerthon-bank-agent/issues/340)，转给Erwin / Assignee DrErwin

创建前核对本组已用01–06、09–13，中控票15在独立待审提交，16为平台消费预留，17未占用。普通get/history不放宽；接口读取已生效限定授权唯一原批准，不是新资金权限。

## 验收

- [x] RC17-1/2：冻结后跨会话原确认读取、S2新version替换后的历史来源、时间经过不改写原已生效批准。
- [x] RC17-3：缺失/无效/foreign/异绑定/歧义及错误版本拒绝，不能读取不相关确认。
- [x] RC17-4：当前/历史/授权/claim/审计与银行不变；同一只读事务；迟到旧回调仍被原门拒绝。
- [x] 红绿记录、必要局部及安全目录回归完成，单目录独立分支备交两轴；不自合并/关闭Issue或代签接受。

[局部验证及证据](../security17-verification.md)。平台16仍需消费后真实联合回放，不把提供接口当联合通过。
