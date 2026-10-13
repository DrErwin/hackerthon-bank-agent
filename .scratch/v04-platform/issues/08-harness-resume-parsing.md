# 08：harness 恢复解析去掉转账视图定型（Issue #122 第 2 项）

Ticket ID: v04-platform/08
Type: 开发
Owner: Erwin
Directory: backend/app/agent_platform/
Status: in_progress
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
