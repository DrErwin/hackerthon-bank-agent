# 03：cross 公共入口授权白名单（平台 05 前置微票）

Ticket ID: v05-cross-security/03

Package: [v05-cross-linkage/packages/02-security：安全边界与专项核验](../../v05-cross-linkage/packages/02-security.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin（2026-10-24 阶段分工：v0.5 剩余安全工作由 Erwin 承接，AI 审查与真人签核分开标注）

Directory: `backend/app/security/`

Status: in_progress — 实现+测试完成，待审查合入。

Core scenarios: XL-S01；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)。

## What to build

`DemoSecurityPolicy` 的冻结能力表与权限集不含 `cross.start_task` / `cross.start`；平台票 05 把 cross 注册进真实运行环境后，第一道能力授权即被拒。本票按本文件既有「安全自有快照、与模块声明刻意独立」的模式补上该入口：能力只读、无副作用、无确认，敏感动作全部留在子任务各自的安全门。

## Blocked by

None（独立微票；平台 05 的直接前置由本票补齐）。

## Acceptance criteria

- [ ] `_CROSS_CAPABILITIES` 冻结快照与 cross 模块 manifest 声明逐字段一致（漂移即拒绝，有测试）。
- [ ] `cross.start` 权限入表；越用户/越轮次/字段漂移拒绝（有测试）。
- [ ] 既有策略行为不变：transfer/bills/subscription 全量测试通过；policy_version 升 `v05-local-demo-cross-1`。

## Delivery record

- 实现 / PR / 合入：待合入。
- 本票验证：`app/security/` 426 passed（新增 cross 白名单测试；三个硬编码旧权限集/版本的既有测试同步更新）。
- 审查：待子代理审查。
- 真人安全签核：未由本票代签；按 2026-10-24 阶段分工由 Erwin 代行审查时分别记录。

## Comments

2026-10-24：发现于平台票 05 装配前置核对——cross 模块（PR #269）与平台派发（PR #258/#264）均已就绪，但真实装配的安全策略仍无该入口。按 #264 先例（平台后续缺口以最小单目录微票补齐）开本票。
