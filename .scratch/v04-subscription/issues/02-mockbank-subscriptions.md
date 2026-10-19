# v04-subscription/02-mockbank-subscriptions: 模拟银行 B29/B30、自包含表与种子数据

Ticket ID: `v04-subscription/02-mockbank-subscriptions`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§5.2、§6 种子数据）
Core scenarios: SF01、SF02、SF03、SF06（银行侧事实）
Verification: 本票局部——`pytest backend/app/services/test_subscriptions.py -q`；整条路径由 `07-subscription-evals` 覆盖
Owner: Erwin
Directory: `backend/app/services/`
Status: todo
Blocked by: [`v04-subscription/01-contract-models`](01-contract-models.md)
Source issue: Issue #123

---

## 1. 目标（Why & What）

在 `backend/app/services/` 下实现模拟银行签约代扣查询（`B29 bank.list_subscriptions`）与单笔本行签约解约（`B30 bank.cancel_subscription`），补齐种子数据并扩展 B14 `get_operation` 还原 `SubscriptionCancelReceipt`，满足公共契约验收项 **M19/M20/M21** 的银行侧能力。

> **目录边界**：只允许修改 `backend/app/services/` 下的文件。**不修改 `backend/app/storage/`**：参照 `bank_operation_scopes` 与 `MockBankVerification` 的既有模式，直接在 `self.store.path` 上 `CREATE TABLE IF NOT EXISTS bank_subscriptions (...)` 自包含建表。**不改动 `seeds/flow_history.json`**（避免波及 02 账单既有验收）。

---

## 2. 改动清单

### 2.1 新增 `backend/app/services/mock_bank/subscriptions.py`
- `ensure_schema(connection)`：建 `bank_subscriptions` 表。
- `seed(connection, at)`：按 `seeds/subscriptions.json` 幂等写入（存在即跳过，不覆盖运行期解约结果）。
- `list_mandates(connection, user_id, account_id, status)`：按 `mandate_id` 排序返回行。
- `cancel_mandate(connection, user_id, mandate_id, operation_id, at)`：更新 `status="cancelled"`、`next_billing_at=NULL`、`cancelled_at`、`cancel_operation_id`。

### 2.2 新增种子 `backend/app/services/mock_bank/seeds/subscriptions.json`
日期用**相对演示当天 D 的偏移量**（`next_billing_day_offset` / `last_billed_month_offset`），不用绝对日期：

| mandate_id | merchant_id | merchant_name / service_name | amount_fen | cycle | status | 下一期 | 近 6/3 月流水 |
|---|---|---|---|---|---|---|---|
| `sub_001` | `M_UYUN` | 优酷视频 / 优酷 VIP 连续包月 | 2500 | monthly | active | D+5 | 6 笔 × 2500 |
| `sub_002` | `M_UDRV` | 云端网盘 / 超级会员连续包月 | 3900 | monthly | active | D+12 | 3 笔 × 3900 |
| `sub_003` | `M_XMAL` | 喜马拉雅 / 巅峰会员连续包月 | 1500 | monthly | cancelled | — | 历史流水 |

扣款账户统一 `account_id="A1"`、`account_masked="****0001"`（与既有种子账户对齐）；`signed_at` 用相对偏移。

### 2.3 新增 `backend/app/services/mock_bank/seeds/subscription_flows.json`
与 `flow_history.json` 同 schema 的独立流水种子（**单独成文件，不动共享种子**）：
- 优酷视频：近 6 个自然月每月同日 2500 分 `direction="outflow"`、`nature="consumption"`、`category="other"`（仓库既有 `Category` 只有 dining/transport/medical/shopping/housing/transfer/other）、`counterparty_id="M_UYUN"`；
- 云端网盘：近 3 个月每月 3900 分；
- 绿洲健身（`M_OASIS`）：连续 5 个自然月每月 3900 分、`channel="快捷支付"`、无签约记录 → 满足契约 §5.9 规则 4 的疑似序列。

### 2.4 `MockBankService`（`core.py`）
- `__init__` 中调用 `self.seed_subscriptions()`：建表 + 幂等写签约种子与订阅流水种子（用 `self.store.seed_ledger_rows(...)`，参照 `seed_flow_history`）。
- `list_subscriptions(self, user_id, account_id=None, status=None) -> QueryOk[SubscriptionMandateList] | QueryFailure`：空 `user_id` → `INVALID_ARGUMENT`；账户非本人/不存在 → `ACCESS_DENIED`；`as_of` 取 `self.clock()`；`account_masked` 取账户标签。
- `cancel_subscription(self, context, operation_id, mandate_id) -> OperationResult[SubscriptionCancelReceipt] | QueryFailure`：按 spec §5.2 与契约 §7A 规则（UUID4 校验、`bank_operation_scopes` 作用域、同 `operation_id` 幂等重放、同编号异参数 `OPERATION_CONFLICT`、跨用户 `ACCESS_DENIED`、不存在 `RECORD_NOT_FOUND`、换新编号重退 `STATE_CONFLICT`、账户非 active `ACCOUNT_UNAVAILABLE`），成功写 `bank_operations`（`action_name="bank.cancel_subscription"`）并落 `receipt_json`。
- `get_operation`：`operation_type == "bank.cancel_subscription"` 时返回 `OperationFound[SubscriptionCancelReceipt]`。

### 2.5 `BankGateway`（`bank_gateway/gateway.py`）
- `list_subscriptions(context, account_id=None, status=None)`；
- `cancel_subscription(context, operation_id, mandate_id)`：与 `submit_transfer` 同样走线程池超时保护（超时 → `CALL_TIMEOUT`），并接受 `authorize_cancel` 回调；未配置回调时 **fail-closed** 返回 `ACCESS_DENIED`。

### 2.6 新增 `backend/app/services/test_subscriptions.py`
覆盖 M19–M21：B29 返回 3 条签约（2 active / 1 cancelled）与账户过滤、空/越权入参；B30 正常解约、幂等重放、`OPERATION_CONFLICT`、`STATE_CONFLICT`、`RECORD_NOT_FOUND`、`ACCESS_DENIED`、`ACCOUNT_UNAVAILABLE`、`CALL_TIMEOUT`；B14 还原回执；订阅流水种子幂等（重复 seed 不增量）。测试用固定 clock 得到确定性日期。

---

## 3. 验收与自检命令

```bash
pytest backend/app/services/test_subscriptions.py -q
pytest backend/app/services -q          # 不破坏既有 mock bank 用例
```
