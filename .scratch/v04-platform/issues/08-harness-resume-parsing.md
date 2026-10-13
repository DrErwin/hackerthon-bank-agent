# 08：harness 恢复解析去掉转账视图定型（Issue #122 第 2 项）

Ticket ID: v04-platform/08
Type: 开发
Owner: Erwin
Directory: backend/app/agent_platform/
Status: resolved（[PR #127](https://github.com/DrErwin/hackerthon-bank-agent/pull/127) squash `3613ce0` 合入 main，2026-10-14；两轴独立子代理审查：Spec 轴无 P0、Standards 轴 P1 一条已修并补断言〔AI 审查、非真人，意见与处置见 PR 评论〕；合入后本目录 120 passed、主线后端全量 533 passed + 模拟银行 14 passed）
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P01、P02](../spec.md)
Verification: 等待类第二模块任务（`waiting_input` / `waiting_approval`）沿原任务 `resume()` 能继续推进，不再因结果被定型为转账视图而校验失败；转账的恢复与会话转换路径不回归。
Blocked by: 无（与 06 并行，目录不重叠）
Source issue: [Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122) 第 2 项

## 交付

1. `backend/app/agent_platform/harness.py` 的 `_result()` 按任务快照的 `capability_name` 前缀分模块解析：转账任务保持既有定型（其消费方读字段），第二模块按通用 `ModuleResult` 原样交回自身载荷（§6.5；API 侧本就按 dict 消费）；`_check_result_scope()` 参数标注同步。
2. 同一目录内其余「结果一定是转账视图」的假设一并去掉（按票 06 审查 P3 明确范围）：`registry.py` 的 `TransferEntry` 协议与 `bills_stub.py` 的桩入口标注；`harness.py` 故障兜底与 resume 审计里对 `result.data.operation_id` / `previous.data.operation_id` 的属性访问（改为共用取值助手：仅转账载荷提供 operation 引用，其余按「无引用」记空）。
3. 公开返回标注（`start` / `handle_message` / `get` / `resume` / `recover_session`）不再声称结果一定属于转账模块。
4. 断言：注册一个等待类账单能力（返回 `waiting_input` + 账单载荷），`start()` 后 `get()` 能按账单契约模型解析回快照载荷、`resume()` 能正常推进到成功；转账恢复与会话转换路径回归不变。

## 边界与依赖

- 只改 `backend/app/agent_platform/`；契约归 06，API 归 07。
- 证据强度：等待类账单任务用测试替身（登记的账单能力）复现，真实账单能力接入后的复验随 [票 05](05-real-bills-integration.md) 补，本票不声称真实模型或真实账单行为已验证。
- 与契约 06 的关系：本票不依赖 06（06 放宽的是 SSE 事件载荷，属 `contracts/`）；06 先合入时 rebase 即可，不合层。

## Comments

- 2026-10-14 Erwin（AI 代填）：按 Issue #122 第 2 项建立本票。当前账单桩只返回终态，等待类账单任务在真实模块接入前无自然触发，故断言以登记测试替身复现接缝。
- 2026-10-14 红灯证据（先红后绿）：新断言在改动前的失败点是 `harness.py:195`——账单载荷被按 `ModuleResult[TransferTaskView]` 解析，报 `data.consumption_*: extra_forbidden`；证明断言咬住的是接缝本身，不是夹具。
- 2026-10-14 实现中发现并一并收口两处同因假设：`resume()` 成功与故障路径用 `previous.data.operation_id` 取审计证据、`start()` 恢复分支用 `result.data.operation_id`，第二模块载荷为 dict 时会属性错误（其中故障路径在 `except` 块内二次抛错）；改法见交付 2。全目录回归 **118 passed**。
- 2026-10-14 双轴 AI 审查（非真人）：Standards 轴 **无 P0、P1 一条**——`recover_session()` 成功路径的审计取值点漏改（跨会话恢复时 `AttributeError`，且失败点在会话已切换、结果未落库之后：任务半提交、重试永久卡死）；Spec 轴独立复现同一处。**已修** `d496571`：改用 `_operation_ids_from()`，并补 `test_waiting_second_module_task_recovers_into_a_new_session`（先红后绿：改动前红在 `harness.py:639`）。
- 2026-10-14 按 Spec 轴 P2 补断言：`test_resume_audit_keeps_the_transfer_operation_reference` 钉住转账 resume 的 `PUBLIC_CAPABILITY_RESUMED` 审计 `operation_ids`——用变异检验（把助手改成恒返回空 → 该用例失败；此前全库无守卫，静默清空也能全绿）。加固后 `app/agent_platform` **120 passed**。
- 2026-10-14 登记审查提出的边界：①模块前缀≠载荷类型——契约 §5.2 的 T03/T04 若返回 `ScheduleTaskView`/`TransferSummary`，必须先改 `_result()` 的分派（已在代码注释写明）；②第二模块结果在首次执行时是契约模型对象、快照回放时是 dict，调用方须两形兼容（随票 05 真数据接入确认）；③本票不假设导出任务会进 harness 恢复路径（对账责任见 [票 07](07-export-task-module-and-event-payload.md)）。
