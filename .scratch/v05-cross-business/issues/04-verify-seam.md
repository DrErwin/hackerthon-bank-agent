# 04：生日写动作 step-up 验证接缝（平台 09 前置微票）

Ticket ID: v05-cross-business/04

Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin（2026-10-24 阶段分工承接）

Directory: `backend/app/modules/cross/`

Status: in_review — 实现+测试完成，待审查合入。

Core scenarios: XL-B01 验证步；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)。

## What to build

安全票 01（#272）把生日资金动作定为 MEDIUM：每笔写=确认+step-up 验证码。但 #274 的 BirthdayFlow/Ports 只支持「确认即执行」——真实门在确认批准后返回 REQUIRE_VERIFICATION 时 flow 无法呈现验证挑战、也无法在验证通过后继续同一写动作。平台票 09 装配核对发现此协议缺口，按 #264 先例以单目录微票补齐。

## Blocked by

None（#274、#272 均已合入）。

## Acceptance criteria

- [ ] `WriteOutcome` 增加 `verify_wait` 状态与 `verify` 交互字段（协议向后兼容：默认 None）。
- [ ] Flow：approve 后遇 `verify_wait` 持有验证挑战（holding=verify，重放不重复提交）；新 `resume_gate` 在平台 resume 信号后重提交同一写动作；终态出口统一清理 pending。
- [ ] entry 路由：birthday 且 choice=resume 且 holding=verify → resume_gate（验证服务答复走通用 code 端点后平台的继续信号）。
- [ ] 既有 19 项生日测试无回归；新增接缝测试覆盖 持有→重放→resume→完成。

## Delivery record

- 实现 / PR / 合入：待合入。
- 本票验证：`app/modules/cross/` 44 passed（新增 1 项接缝测试）。
- 审查：待子代理审查。

## Comments

2026-10-24：平台 09 装配前置核对发现（真实 gate MEDIUM 语义 vs flow 单步确认）；不改任何安全规则，仅补编排侧的验证呈现与继续接缝。
