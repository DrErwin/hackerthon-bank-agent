# v04-subscription/09-cancel-refusal-and-unknown-recovery: 退订失败与结果未知的如实回执

Ticket ID: `v04-subscription/09-cancel-refusal-and-unknown-recovery`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§4 SF02、§5.7）
Core scenarios: SF02（SOP-2 ⑥⑦）＋ PRD T05/T13、E06/E09、§2.4「结果待核实」
Verification: `pytest backend/app/modules/subscription -q`；连带 `pytest backend/app/agent_platform/test_subscription_runtime.py backend/app/api/test_subscription_api.py -q`；评测票 `v04-subscription/10` 的 SUB-CAN-12/13/14 在同提交上通过
Owner: Erwin
Directory: `backend/app/modules/subscription/`
Status: resolved
Blocked by: None
Source issue: 2026-10-19 完整覆盖核对实测发现（本票记录；如需对外跟踪再开 GitHub Issue）

---

## 1. 现象（2026-10-19 平台层实测复现）

驱动真实 `MockBankService` + `SecurityGate` + `DeterministicExecutor` + `DemoSecurityPolicy` 的平台组装（模型入口为脚本替身），两处退订收尾分支与 PRD 不符：

1. **银行明确拒绝被吞成系统故障（对应 E09）**：预置扣款账户 `A1` 非 `active` 后走完整退订链路，B30 返回 `ACCOUNT_UNAVAILABLE`；平台回执为 `SUBSCRIPTION_INTERNAL_ERROR`「订阅服务暂时不可用，请稍后再试。」，而模块内 `_MESSAGES["ACCOUNT_UNAVAILABLE"]` 已写好正确话术（「这个扣款账户状态异常，暂时不能在线退订，请拨打银行卡背面的客服电话。」）却永远到不了。协议保持 `active`、银行无操作，资金侧正确，**错在如实说明**。
2. **结果未知被报成失败且无从回查（对应 T05/E06、§2.4 结果待核实）**：注入 B30 超时后，平台回执同样是 `SUBSCRIPTION_INTERNAL_ERROR`；任务落 `failed` 终态，再 resume 仍为 `failed`。实测中后台线程的 B30 实际已成功、银行协议已变 `cancelled`，用户却被告知「服务暂时不可用」；全过程没有按原 `operation_id` 查 B14，也没有「先不要重复点、稍后查询结果」的入口。

## 2. 根因（已定位）

- `reads.GatewaySubscriptionPorts._observe_result` 对 `QueryFailure` 直接 `raise ValueError`，统一执行器据此把该次调用记为 `unknown`（`result=None`）。于是：
  - 明确的银行拒绝与「超时/未知」在模块侧无法区分；
  - `service.cancel_task` 收到 `executed=True, result=None` 只能落到 `SUBSCRIPTION_INTERNAL_ERROR`。
- 模块状态机没有「待核实」态：未知结果被当作 `failed` 终态，`resume` 直接返回旧结果，执行器自带的 `operation_lookup`（B14）永远不会被触发。

transfer 模块已有同场景的既有约定可对齐：`workflow._pending` 返回 `TaskStatus.NEEDS_ATTENTION` + `recovery_reason="OPERATION_UNKNOWN"`，由 `_manual_reconcile` 按原操作号回查，绝不再次提交。

## 3. 期望行为

1. 银行明确拒绝（`ACCOUNT_UNAVAILABLE` / `STATE_CONFLICT` / `RECORD_NOT_FOUND` / `OPERATION_CONFLICT` / `BANK_REJECTED` 等安全码）→ `failed`，`error.code` 为该码、`source="bank"`、`upstream_code` 保留原码，文案取模块既有 `_MESSAGES`；状态与资金事实不变。
2. 超时/结果未知 → **不**报系统故障、**不**报成功或失败：返回 `TaskStatus.NEEDS_ATTENTION`、`recovery_required=True`、`recovery_reason="OPERATION_UNKNOWN"`，文案为既有 `_MESSAGES["CALL_TIMEOUT"]`（「这次退订还没拿到银行的最终确认，请先不要重复操作，稍后再查询结果。」）；任务不再落 `failed` 终态。
3. 待核实任务再次 resume（用户点「查询结果」）→ 经统一执行器对**原 `operation_id`** 走一次 `get_operation`（B14）：查到成功按成功回执、查到失败如实报失败、仍未知保持 `NEEDS_ATTENTION`；全过程 B30 银行操作行数恒为 1，不换编号、不重复提交。
4. 现有成功路径、确认门/验证门、幂等重放、三条红线行为不变。

## 4. 范围与边界

- **只改 `backend/app/modules/subscription/`**：不改 `backend/app/security/`（Issue #164 属安全线未决）、不改 transfer 的既有约定、不新增契约字段与状态值（复用既有 `TaskStatus.NEEDS_ATTENTION` / `recovery_required`）。
- `evals/subscription/` 的机器断言属票 `10`，本票只保证平台行为正确并更新模块内测试。
- 若需要共享约定变更（例如 executor 对 `QueryFailure` 的统一语义），先记录问题，不在本票内改公共目录。

## 5. 验收

- 模块内新增/更新测试先红后绿：明确拒绝如实回执、超时 → `NEEDS_ATTENTION`（不再 `failed`）、待核实 resume → B14 回查得到真实结果、回查仍未知保持待核实、银行操作行数恒为 1。
- `pytest backend/app/modules/subscription -q` 全绿；`pytest backend/app/agent_platform/test_subscription_runtime.py backend/app/api/test_subscription_api.py -q` 不回归。
- 提交前 `git diff --check`，确认只改本目录。

## Comments

- 2026-10-19 由完整覆盖核对实测发现并开票；PM 已拍板先修本票再做完整验收集（票 10）。

- 2026-10-19 晚实施完成：仅 `backend/app/modules/subscription/` 7 文件（+377/−31），security/contracts/api/agent_platform/evals 零改动。
  - `_observe_result` 只把 B30 `CALL_TIMEOUT` 视为未知（executor claim=unknown，resume 才走 B14）；其余 `QueryFailure` 视为银行明确答复（completed 观测 + 保留 `QueryFailure` 本体）→ 模块按 `error.code/source/upstream_code/_MESSAGES` 如实落 failed。
  - 超时/未知：首次立即返回 `NEEDS_ATTENTION`（OPERATION_UNKNOWN、CALL_TIMEOUT 文案、allowed_actions=["query"]），checkpoint 冻结 plan payload 与 item；resume 先经统一执行器按原 operation_id 走一次 B14：成功→真实回执、失败→如实失败、仍未知→继续待核实；全程不重提，银行操作行数恒 1。
  - 附带修复 D3（E01/T12）：批量菜单后的文字回答先清 batch 再按普通选中处理；初始批量话术仍拒绝。
  - 测试：先在模块内写失败清单再实现；`pytest backend/app/modules/subscription -q` 45 passed（新增 11 用例/49 断言）；`test_subscription_runtime.py` + `test_subscription_api.py` 23 passed；`pytest backend -q` 738 passed。
  - 交付：PR #172（squash 合入 main `c1cdde3`）。Lead 复核 + 平台组装交叉验证（票 10 的 5 条用例在修复上通过）。AI 复核，非 Ringo 本人签署；未触及安全目录。
- 遗留：NEEDS_ATTENTION 的 `allowed_actions=["query"]` 与平台 `/query-result` 一致（api 层自动追加 cancel）；拒绝路径 claim 记为 completed、failed 为终态，正常流程不可达重复回查。
