# 04：同动作顺序多笔确认放行（平台 09 前置微票）

Ticket ID: v05-cross-security/04

Package: [v05-cross-linkage/packages/02-security：安全边界与专项核验](../../v05-cross-linkage/packages/02-security.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin（2026-10-24 阶段分工：v0.5 剩余安全工作由 Erwin 承接，AI 审查与真人签核分开标注）

Directory: `backend/app/security/`

Status: in_review — 实现+测试完成，待审查合入。

Core scenarios: XL-B01（生日多商品逐笔下单）；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)。

## What to build

`SQLiteSecurityState.create_confirmation` 对同 (task, action_name) 上一张已 claimed 的确认一律抛 OPERATION_UNKNOWN——单确认动作（转账/退订）下正确的防并行规则，但生日场景对同一 `bank.create_order`/`bank.capture_frozen` 逐笔办理多个商品（花→蛋糕），第二笔永远无法建确认。平台票 09 装配实测发现。

## Blocked by

None（#272 已合入）。

## Acceptance criteria

- [ ] 上一张确认 claimed 且其执行已非 processing（completed/unknown 终结记账后）→ 允许新建同动作确认（顺序逐笔）。
- [ ] 上一张 claimed 且其执行仍 processing（真正并行/未决）→ 仍拒绝 OPERATION_UNKNOWN（原安全语义保持）。
- [ ] 其余分支（跨主体、cancelled、同 operation 参数漂移）行为不变；security 全量回归。

## Delivery record

- 实现 / PR / 合入：待合入。
- 本票验证：见 PR。
- 审查：待子代理审查。

## Comments

2026-10-24：平台 09 全链装配（冻结→下单→付款→释放）实测发现；不放宽任何确认/验证/claim 要求，仅允许同动作顺序逐笔。
