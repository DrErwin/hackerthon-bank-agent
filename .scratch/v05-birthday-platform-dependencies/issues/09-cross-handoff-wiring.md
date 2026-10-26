# 09：Cross 编辑交接接线与「已撤离后同参新尝试」接缝

Ticket ID: v05-birthday-platform-dependencies/09
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [平台提供条件及最小规格](../spec.md)、[G3 对账](../g3-reconciliation.md)
Type: 开发（2026-10-26 由票 08 交付时如实报出的两个平台缺口新增）
Owner: Erwin（v0.5 阶段统一负责）
Directory: `backend/app/agent_platform/`
Status: in_progress — 2026-10-26 已派实施（从票 08 分支出发，08 合入后 rebase）；未合入。
Implementation assignee: Erwin 授权执行对话（本对话，AI 代理）；accepted at 2026-10-26。
Blocked by: 票 08 合入（提供 `install_cross_handoff` 与真实 adapter）；03 已合入（`handoff` 接缝）。
Core scenarios: P02/P03/P07/P12—P17；对应 Cross08 Q03/Q05/Q06。

## 为什么新增这一票

票 08 交付时如实报出两个缺口，均属 `agent_platform/`、不能跨目录补：

1. **`handoff.cross` 未挂载**：`local_demo.build_runtime` 建 `BirthdayRuntime` 后没有把 Cross 实现挂上，
   真实组合点 F10 编辑入口只会得到 `CROSS_HANDOFF_UNAVAILABLE`；Cross 已提供一行 `install_cross_handoff(...)`。
2. **撤离后同参 action 被判 `ACTION_RETIRED`**：03 撤离旧尝试后，若新计划对同一 action 生成完全相同参数
   （冻结卡必然同参；order/capture 卡对应项未改时也同参），平台 `_action` 会复用已撤离的 operation，
   安全门正确返回 `ACTION_RETIRED`——结果「编辑后继续办理」在真实装配下走不通，需平台提供
   「已证明撤离后的同参**新尝试**」接缝：旧 attempt 永不复用，新参数必须新 operation/新确认，历史保留可回查。

## What to build

1. 组装点挂载 Cross 实现（真实组合下编辑入口可用），修正/更新「handoff.cross is None」的既有断言。
2. 平台 `birthday_runtime`：03 `seal_retirement` 成功后标记被撤离 attempt 不可复用；`_action` 在「参数相同但 attempt 已撤离」时
   创建新 attempt/operation（旧 attempt 入 history、action_revision 单调），安全门对新 attempt 正常评估。
3. 不改其它目录；不改公共契约/枚举。

## Acceptance criteria

- [ ] 真实组合（`build_runtime` + 真实安全/银行/存储 + 票 08 真实 adapter）下，F10 编辑入口不再返回 `CROSS_HANDOFF_UNAVAILABLE`。
- [ ] 冻结卡编辑：确认等待态撤离后，同一冻结参数重新提交得到**新 operation**，能走到确认/验证；旧 operation 仍 `ACTION_RETIRED` 不可执行、历史可查。
- [ ] order/capture 卡编辑且对应项未改：同参也得到新 attempt/新 operation；旧订单/付款事实不改写、不重复扣款。
- [ ] 重复点击/同参重放单结果；action_revision 严格单调；安全门不因「已撤离」误放行新尝试。
- [ ] 只改 `backend/app/agent_platform/`；测试含真实组合用例；未把真实 E2E 写成通过。

## Verification / downstream

局部：`app/agent_platform` 全量 + 票 08 的 `app/modules/cross` + `app/api/test_app.py`。
真实 E2E、页面与安全接受由本人后续安排。
