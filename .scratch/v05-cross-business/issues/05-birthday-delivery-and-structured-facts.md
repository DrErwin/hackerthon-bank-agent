# 05：生日受控配送入口与结构化收尾视图

Ticket ID: v05-cross-business/05

Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin（v0.5 本阶段统一负责）

Directory: `backend/app/modules/cross/`

Status: implemented — 2026-10-25 本票实现与两轴 AI 审查通过，PR #288 待中控合并；CI 账户计费阻塞，非版本验收完成。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: Erwin 授权的执行对话 01a17183-271b-7663-9517-f31a994de51d

Accepted by: Erwin（授权执行对话代行）

Accepted at: 2026-10-25

Planning approved by: PM，2026-10-25 页面走查裁定「先开后端票补配送入口＋结构化视图，再走查票 02」。

Core scenarios: XL-B01、XL-B02、XL-B04、XL-B05、XL-B06；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

1. 生日流程在需要配送资料时，用一个平台认识的受控配送交互（`required_fields == ["delivery"]`）向用户要资料，而不是让用户把原文/引用编号贴进聊天。
2. 生日流程把已经真实发生的订单、付款、冻结、释放事实放进任务视图，供页面逐项核对（现在只有一段汇总文字）。

## 背景（代码核对，见 [backend-api-surface.md](../../v05-cross-frontend/research/backend-api-surface.md) §5 G3/G10）

- **G3**：`POST /api/v1/tasks/{id}/details` 的 delivery 分支要求当前交互 `required_fields == ["delivery"]`，生日父任务却是 `["cross_selection"]` → 409 `DETAILS_NOT_REQUESTED`；生日流程连 `delivery_ref` 都拿不到。
- **G10**：`CrossTaskView.steps[]` 的 `order_id / payment_status / operation_id / result_ref` 运行期恒空，生日模块也没有可读的冻结/消费/释放金额字段；页面只能显示 `message` 文本。

## Start when

- [03：生日编排](03-birthday-orchestration.md)（#274）与 [v05-cross-platform/09 生日真实装配](../../v05-cross-platform/issues/09-birthday-runtime-wiring.md)（#279）已合入。
- 契约字段已存在（`CrossStep.order_id / payment_status / result_ref`、`CrossTaskView.budget`），本票只补齐「填进去」与「收受控资料」，不新增公共契约语义；确需新增字段时按[公共改动流程](../../../docs/principles/03-review-and-merge.md#公共底座与-api-改动)先提平台票。
- 若发现平台侧（`backend/app/api/`）仍需分支配合，回 [v05-cross-platform/11](../../v05-cross-platform/issues/11-child-interaction-and-text-input.md) 或另开平台票，不在本目录跨目录修改。

## Acceptance criteria

- [x] 生日流程在需要配送资料时返回平台可识别的受控配送交互；用户经该入口提交后，流程拿到的是受控引用（不是原文），聊天与普通日志不出现配送原文。
- [x] 拒绝/过期/重复提交的受控资料不会被当成新资料重复使用；越权或跨轮次引用被拒。
- [x] 订单、付款、冻结、释放的真实事实进入任务视图（至少：订单号、付款状态、冻结金额、已消费、已释放/待释放），金额来自银行/服务返回，不由前端或文案推算。
- [x] 未知（结果待核实）状态下不填入「已完成」事实；等待态不丢已发生事实。
- [x] 回归：现有生日编排用例（含 B04 部分成功停止、B06 限定收尾）不退化；`modules/cross` 不复制转账/订阅内部流程。

## Verification

| 检查 | 预期可观察结果 |
|---|---|
| 配送受控入口 | 生日流程能拿到并消费受控引用；原文不出现在任务视图、消息或日志 |
| 视图事实 | 冻结/消费/释放与银行账实一致；订单状态逐笔可读，订单创建与付款分开 |
| 未知/停止 | 未知只保留待处理与原编号；停止后只做限定收尾，不复活购买 |
| 既有回归 | 生日编排三票既有用例全绿 |

本票只保证业务侧能力与数据；页面与真实服务联调归 [前端票 02](../../v05-cross-frontend/issues/02-birthday-ui.md) 与 [E2E 包 05](../../v05-cross-linkage/packages/05-cross-e2e.md)。

## Delivery record

- 实现 / PR / 合入：已实现，PR [#288](https://github.com/DrErwin/hackerthon-bank-agent/pull/288)，未合并，交中控排队。
- 本票验证：Cross 57 passed；本票测试文件 13 passed；MockBank 14 passed；链接/语法/差异空白通过。
  真实模拟银行完整与停止路径直接对账、HTTP 受控表单/引用推进均有证据。首次实现后端全量
  1600 passed（16m13s），审查回修后复验受影响 Cross 57 项；不是最终代码二次全量。
  两轴独立子代理：Standards PASS；Spec 初轮 P2 已修并复审 PASS（子代理独立回归 1 passed）。
  GitHub CI 未启动，账户付款/支出限额阻塞，不记为 CI 绿。详细证据与遗留见 [本票交接](../review-05.md)。
- 联合 E2E：未因本票发布而通过。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-25：页面走查发现票 02 的两个前端不可解前置（G3/G10），PM 裁定先开后端票补齐再做页面走查。本票不改前端、不改契约字段语义；属性边界以包 03 与本目录规则为准。

2026-10-25（实施裁定）：用户确认配送引用“沿用现有失效规则，不新增有效期”；旧交互、失效会话、跨用户/轮次/任务及重复请求沿用已有规则。
个人预算引用/版本遗留不在本票补完，`budget` 不伪造采用；XL-B07 未因此完成。
配送只在首次资金动作前收集，原始输入阶段保持 data=None，真实资金事实产生后等待态及收尾均保留结构化视图。

2026-10-25（中控紧急复核）：运行装配线在旧生日业务版本发现的“冻结未知后取消，回查重新下单”
P1，已在 #288 `8ea7042` + #289 `18a3f39` 的真实组合中核对：#288 既有停止修复已覆盖。
四条公开 entry/真实 ports 回归通过，独立子代理两轴审查及复验通过；未改生产代码、
未新增业务票或修复 PR，预算另派、共享跟踪由中控维护。详见[组合复核证据](../research/unknown-stop-recheck-2026-10-25.md)。
