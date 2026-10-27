# 01：未提交生日动作跨会话撤离

Ticket ID: v05-birthday-session-security/01
Package: [v05-cross-linkage/packages/02-security：联动安全](../../v05-cross-linkage/packages/02-security.md)
Spec: [跨会话安全撤离](../spec.md)
Type: 开发
Owner: Erwin；Codex 按中控明确分派实施
Directory: `backend/app/security/`
Status: implemented — independent review/acceptance pending
Accepted at: 2026-10-27
Blocked by: None（G2已合入，跨会话proof与平台已对齐）
Core scenarios: [SS01–SS06](../spec.md#核心场景)

## 验收

- [x] 同事务validator+源当前/历史确认核对，持久绑定目标session；缺失/变化/越权拒绝。
- [x] begin→真实银行退役→seal；claim/unknown/active先胜，pending不冒充sealed。
- [x] 旧pending授权失效、历史与审计保留；审计故障回滚、同参可续；异参/异目标拒绝。
- [x] 迟到旧授权/挑战/确认/执行不可复活，新attempt重新确认/验证并正常可办。
- [x] 局部与受影响安全回归完成，独立分支交中控审查；不是整条Cross09或真人接受。

Verification: 隔离SQLite的真实应用状态/安全/银行接缝，不改其他目录；原Cross09 1fail/1pass不覆盖。消费修复另由platform_completion承接。

实际结果见[验证记录](../verification.md)。独立Standards/Spec审查、PR合入与消费方联调待中控，不代签本人安全接受。
