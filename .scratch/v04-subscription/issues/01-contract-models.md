# v04-subscription/01-contract-models: 订阅代扣公共契约模型与枚举扩值

Ticket ID: `v04-subscription/01-contract-models`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§0 口径统一决议、§5.1）
Core scenarios: SF01–SF06（[spec §4](../spec.md)）
Verification: 本票局部——`pytest backend/app/contracts/test_subscription_contracts.py -q`；整条路径由 `07-subscription-evals` 覆盖
Owner: Erwin
Directory: `backend/app/contracts/`
Status: todo
Blocked by: None
Source issue: Issue #123（场景 05 票据组）

---

## 1. 目标（Why & What）

为场景 05 落地公共契约模型与两处枚举扩值，对齐[公共契约](../../../docs/contracts/公共契约-2026-09-23.md) §5.5 / §6.5 与[银行接口字段](../../../docs/contracts/银行接口字段-2026-09-24.md) §7A，供模拟银行、`subscription` 模块、安全策略、平台编排与 API 层统一引用（严禁各模块复制私有契约副本）。

口径按 spec §0：**以冻结公共契约为准**；金额单位 `fen`；周期 `monthly|yearly`（无 quarterly、无月度折算指标）。

> **目录边界**：只允许修改 `backend/app/contracts/` 下的文件。

---

## 2. 改动清单

### 2.1 新增 `backend/app/contracts/subscription.py`
字面量：`SubscriptionSourceType = mandate|suspected_ledger`、`SubscriptionCycle = monthly|yearly`、`SubscriptionStatus = active|cancelled|suspected`、`SubscriptionScanStatus = evaluated|insufficient_data`。

模型（字段与校验见 spec §5.1）：
1. `SubscriptionMandate`、`SubscriptionMandateList`（银行侧，§7A）
2. `SubscriptionCancelReceipt`（§7A）
3. `SubscriptionItem`（§5.5 + 新增 `billed_count` / `billed_total_fen` / `channel`）
4. `SubscriptionListResult`（§5.5 + 新增 `suspected_scan_status` / `suspected_scan_reason`）
5. `SubscriptionTaskView`（§5.5）
6. `SubscriptionListInput`、`SubscriptionCancelInput`（S01/S02 逻辑入参，§5.5）

一致性校验：`upcoming_renewals == [i for i in items if i.is_upcoming_renewal]`、`upcoming_total_fen == sum(upcoming_renewals.amount_fen)`、`active_count == len([i for i in items if i.status=="active"])`；`SubscriptionTaskView(action="list")` 必带 `list_result`、`action="cancel"` 必带 `selected_item`、`operation_id` 与 `operation.operation_id` 一致。

### 2.2 `backend/app/contracts/tasks.py`（仅枚举扩值）
- `ModuleError.source`：`Literal[...]` 增加 `"subscription"`。
- `TaskView.module`：`Literal[...] | None` 增加 `"subscription"`。

### 2.3 `backend/app/contracts/__init__.py`
导出上述全部新模型与字面量并更新 `__all__`（若该文件以 import 列表导出则按同风格追加）。

### 2.4 新增 `backend/app/contracts/test_subscription_contracts.py`
覆盖：序列化/反序列化、`extra="forbid"`、`amount_fen >= 0` 边界、`reminder_days` 1..90 边界、`subscription` 枚举扩值（`ModuleError(source="subscription")`、`TaskView(module="subscription")`）、三个一致性 `model_validator` 的正反例。

---

## 3. 影响评估（本票必须在 PR 说明里写清）

- 本次契约变更**全部为新增**：新文件 + 两处枚举扩值 + 追加可选字段（均带默认值），既有字段名称/类型/语义/必填性未改。
- 已检索仓库内 `ModuleError(` 与 `module=` 构造点：无按枚举穷举匹配的代码路径；旧任务快照的 `module` 仍取旧值，反序列化不受影响。

---

## 4. 验收与自检命令

```bash
pytest backend/app/contracts/test_subscription_contracts.py -q
pytest backend/app/contracts -q
```
