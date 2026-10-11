# v0.4 账单银行接缝（B08 + L01 公共模型）

Status: in_progress
Owner: Erwin（PM 自拆，不开交付包）
Source issue: [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91)（账单依赖：落地冻结契约的 B08 流水查询与 L01—L03 公共模型）
Deadline: **不晚于 2026-10-16**（给账单侧真实取数联调留 10-17～10-19 窗口；v0.4 收口 10-20 硬截止）

## Problem Statement

账单业务线（周恩宇，v04-bills/01）要按 02 PRD 算消费、识别异常、出报告，但公共接缝缺两块：**契约层没有流水与账单模型**（`contracts/bank.py` 只覆盖转账面，`contracts/` 无账单模型），**银行接缝没有 B08 查询**（`BankGateway` 无 `list_transactions`）。账单模块因此拿不到真实银行事实——而按铁律 3 与目录边界，它不能直读银行表、不能自建公共模型。没有这条接缝，BF01/BF03/BF05/BF06 只能停在局部 fixtures，无法进入真实取数与前端联调。

## Solution

在公共目录落地冻结契约已定义的接缝，账单侧只消费、不重造：

1. **契约模型**：B08 的 `Transaction` 与查询结果模型；L01 首条路径的 `BillScope`、`SpendingSummary`（含 `CategoryTotal`、`SpendingComparison`）、`BillDetails` 及输入模型。字段与规则严格引用冻结文档，不在本处复制定义。
2. **银行接缝**：`BankGateway` 公开 `list_transactions`，由模拟银行按银行侧时钟与范围规则实现 B08 语义（本人账户、半开区间、最多最近 24 个月、空数据与失败区分、`as_of`）。

**公开导入路径（账单侧按此消费）**：`app.contracts.bank`（`Transaction`、`TransactionList` 等）与 `app.contracts.bills`（`BillScope`、`SpendingSummary`、`BillDetails` 等）。

## Implementation Decisions

- 字段、枚举与业务规则以冻结文档为准：[银行接口字段 §3 B08 与 `Transaction`](../../docs/contracts/银行接口字段-2026-09-24.md)、[公共契约 §5.3 L01—L03 与各模型](../../docs/contracts/公共契约-2026-09-23.md)。本规格只定落位与不变量。
- **契约层落位**：`Transaction` / `TransactionList`（`transactions[]`、`as_of`）进 `contracts/bank.py`（与 `QueryOk`/`QueryFailure`/`BankError` 同处）；账单侧模型进新文件 `contracts/bills.py`。金额类型沿用 `common.py` 既有标量；有符号净额（如 `consumption_net_fen`、`delta_fen`）在 `common.py` 补 `SignedMoney`，不用裸 `int` 顶替领域概念。
- **不变量（写进模型校验，能校验的都校验）**：`BillScope.account_ids` 非空、去重；`start_at < end_at` 且声明「含开始不含结束」；`SpendingSummary.consumption_net_fen = gross − refund`；`categories` 七类口径与文档一一对应；`BillDetails` 按发生时间、再按 `account_id`/`transaction_id` 稳定排序；退款类 `Transaction` 必填 `original_transaction_id` 与 `original_occurred_at`。
- **银行侧落位**：范围查询与 `as_of` 取银行自己的时钟（`services/mock_bank/core.py` 的 `_now()` 模式；测试可注入时钟，沿用 `services/test_verification.py` 的 Clock 模式）。通道语义：`occurred_at >= start_at` 且 `< end_at`（首尾不重复计账）；范围超最近 24 个月返回 `RANGE_UNSUPPORTED`；非本人账户 `ACCESS_DENIED`；参数非法 `INVALID_ARGUMENT`；**空数据返回 `[]`（成功），与查询失败严格区分**。
- **不做分页**：指定范围一次完整返回（mock 数据量下直接读账本）。为将来需要，范围过滤放银行侧服务内（复用 `storage/mock_bank` 现有 `list_ledger` 读取），不为本票改动存储层 schema——如后续数据量或一致性需要下推 SQL，另开 storage 票。
- **银行规则只在模拟银行**：`BankGateway` 只做薄转发与结果映射，不在网关里重写范围/归属规则。
- 不改变 transfer 路径任何行为；L02/L03 模型按 §5.3 随后逐项落地，不在本票范围。

## Testing Decisions

- 只测外部行为：账单侧/网关调用方看到的结果、错误码与边界，不断言 SQL 或内部实现。
- **契约层（既有先例 `contracts/test_contracts.py`）**：模型可导入、必填/枚举/范围校验、`consumption_net_fen` 等式校验、退款必填原单校验、`BillScope` 空/重复/区间非法拒绝。
- **银行侧（既有先例 `services/test_verification.py` 的注入时钟）**：本人账户成功返回；他人账户 `ACCESS_DENIED`；半开区间两端各一条边界样本不重复计账；24 个月边界两侧（恰好 24 个月通过 / 超出报错）；空区间成功 `[]` 与失败可区分；`as_of` 来自银行时钟（前进时钟后变化）；排序稳定。
- **接缝**：一套端到端断言从 `BankGateway.list_transactions` 进入（最高既有缝），覆盖成功/拒绝/范围/空/失败五类。

## Out of Scope

- L02（异常识别）、L03（报告）模型与能力——随后按 §5.3 落地。
- 账单模块的统计计算、评测与前端（respective 负责人）。
- `storage/mock_bank` schema 变更、种子流水扩充（如联调需要更多月份数据，另开票）。
- transfer 路径、安全底座、审计规则。
- 多账户归集统计（模型保留 `source_as_of`，统计归 bills）。

## Tickets

- [v04-bills-bank-seam/01：契约模型（B08 Transaction + L01 账单模型）](issues/01-contracts-models.md)
- [v04-bills-bank-seam/02：银行接缝 list_transactions（模拟银行 + 网关）](issues/02-bank-seam-list-transactions.md)

## Further Notes

- 关闭 [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91) 的条件（引用其正文）：公开接缝有实现与合入证据；账单侧能通过统一入口验证本人读取、拒绝他人账户、半开区间/24 个月边界、完整性与错误传播。
- 依赖顺序：02 需要 01 的模型（模拟银行返回值即契约模型），故 02 等 01；两个目录各自独立 PR（一票一目录）。
- 2026-10-12 建组（PM 授权 AI 建立规格与票据）；实现按 `implement` 走分支/PR/CI。
