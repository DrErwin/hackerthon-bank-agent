# v04-bills-bank-seam/01：契约模型（B08 Transaction + L01 账单模型）

Ticket ID: v04-bills-bank-seam/01
Package: PM 自拆（不开交付包）；Source issue [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91)
Spec: [v04-bills-bank-seam 规格](../spec.md)
Core scenarios: 支撑 BF01/BF03/BF05/BF06 的真实取数（账单侧通过统一入口验证本人读取、半开区间/24 个月边界、完整性与错误传播）
Verification: `python -m pytest -q app/contracts/`（backend/ 下）全绿；模型校验用例覆盖必填/枚举/等式/退款原单/区间非法；公开导入路径可用
Owner: Erwin
Directory: backend/app/contracts/
Status: open
Blocked by: None（可立即开始）
Source issue: [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91)

## What to build

冻结契约已定义、代码尚未落地的两类模型，供账单模块与银行接缝消费：

1. `contracts/bank.py` 增 `Transaction` 与查询结果模型（`transactions[]` + `as_of`），供 B08 返回；字段与枚举严格按[银行接口字段 §3](../../../docs/contracts/银行接口字段-2026-09-24.md)（含 `nature`/`category`/`direction`/`channel`/`counterparty_*`/退款原单两字段），不新增字段、不改语义。
2. 新增 `contracts/bills.py`：`BillScope`、L01 输入模型（`scope`、`mode: summary|details`、可选 `comparison_scope`、可选 `category`）、`SpendingSummary`、`CategoryTotal`、`SpendingComparison`、`BillDetails`；字段按[公共契约 §5.3](../../../docs/contracts/公共契约-2026-09-23.md)。
3. `common.py` 补 `SignedMoney`（有符号整数分），用于 `consumption_net_fen`/`net_fen`/`delta_fen` 等——不用裸 `int` 顶替领域概念。

## 实现要点

- 落位与不变量见[规格 Implementation Decisions](../spec.md#implementation-decisions)（`BillScope` 非空去重、`start<end` 半开声明、净额等式、退款必填原单、明细稳定排序）。
- 只引冻结文档，不复制其字段表；枚举值与文档一一对应（如七类 `dining…other` 与 02 中文七类的映射由 bills 侧负责）。
- 不新增 `QueryOk`/`QueryFailure`/`BankError` 之外的结果外壳；B08 成功用既有 `QueryOk`，失败用 `QueryFailure`。

## Acceptance criteria

- [ ] `from app.contracts.bank import Transaction`（及查询结果模型）、`from app.contracts.bills import BillScope, SpendingSummary, BillDetails` 可用
- [ ] 模型校验测试覆盖：必填与枚举、`consumption_net_fen = gross − refund`、退款必填 `original_transaction_id`/`original_occurred_at`、`BillScope` 空/重复/`start_at >= end_at` 拒绝
- [ ] `python -m pytest -q app/contracts/` 全绿；PR 合入、CI 通过
- [ ] 完成后 [02 银行接缝票](02-bank-seam-list-transactions.md)解除阻塞
