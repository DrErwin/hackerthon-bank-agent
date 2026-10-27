# v05-birthday-platform-dependencies/12：重置后的业务时钟与可信轮次接线

Ticket ID: v05-birthday-platform-dependencies/12
Package: [v05-cross-linkage/packages/01-platform-bank：底座与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [本组规格](../spec.md)，本票补充规格见下方
Type: 开发
Owner: Erwin（v0.5 统一负责）
Directory: `backend/app/agent_platform/`
Status: ready_for_review — 完整平台合并态 393 passed / 13 skipped，待中控两轴审查与合入
Blocked by: None（前置 [v05-bank-reset/02：银行重置排空与起点读取](../../v05-bank-reset/issues/02-gateway-drain-and-clock.md)、PR #323 均已合入）
Accepted by: 本对话 AI，依据 2026-10-27 用户完成非比赛资料任务授权及中控委派
Accepted at: 2026-10-27
Core scenarios: 公共契约 B26 / F25、F30—F32；API 协调另票
Verification: 本地替身规划器与真实平台/银行的定向组合回归；安全有效期保持真实时钟，不作为真实模型/页面验收。

## 补充规格

- 公开 `runtime.bank` 和 `runtime.set_demo_clock(datetime)`，供 API 管理协调消费；setter 只改变业务逻辑日期，API 负责持久管理回执与总体停收。
- 银行业务、账单、订阅、联动共享一个可变业务时钟。确认/验证码/人脸有效期、安全授权及网络等待继续使用真实时钟。有限解冻安全记录也不使用业务日期。
- 安全策略、记忆和生日平台的当前轮次读取银行持久 `current_demo_round_id`；只有银行尚无成功重置标记时才使用配置起始轮次。
- 本地 runtime 重启从银行公开 `current_demo_logical_at` 恢复最近成功重置起点；API 随后可从自身持久管理状态恢复更近的逻辑时间。不读取银行私表、不把整体未完成写作已完成。
- 保留旧应用任务历史；旧轮次 TrustedContext 被拒绝。应用记忆重置、旧会话失效和停收/排空属于 API 消费票，不在本目录伪造执行状态。

## Comments

- 2026-10-27：中控安排本票，敏感等待 Cross 消费方票 09 后置；分支 `codex/v05-demo-runtime-clock`，依赖 PR #325 head `45bf2612`。
- 2026-10-27：前置合入后 rebase main `0b72b0a1`；[PR #328](https://github.com/DrErwin/hackerthon-bank-agent/pull/328)，[最终验证](../recovery-12-verification.md)。受测 `cd6a1690` 完整平台 393 passed / 13 skipped；原 UTC 月界失败证据保留。
