# v04-bills-bank-seam/03：模拟银行账本事实列与种子写入机制

Ticket ID: v04-bills-bank-seam/03
Package: PM 自拆（不开交付包）；Source issue [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91)
Spec: [v04-bills-bank-seam 规格](../spec.md)
Core scenarios: BF01/BF03/BF05/BF06 的统计与判断必须来自银行自己的流水事实，不能由上层补造
Verification: `python -m pytest -q app/storage/`（backend/ 下）全绿；覆盖 v2→v3 迁移不丢数据、事实列可写可读、种子写入幂等、既有排序与 7 元组写入路径不变
Owner: Erwin
Directory: `backend/app/storage/mock_bank/`
Status: open
Blocked by: None（可立即开始）
Source issue: [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91)

## What to build

票 02 的 B08 要返回契约 `Transaction`，但账本只有 9 列、也没有任何历史流水：银行拿不出商户名 / 渠道 / 摘要 / 退款原单，只能返回空或编造。本票只补**存储层的能力**，事实内容由票 02 提供：

1. `ledger_entries` 增可空列：`counterparty_id`、`counterparty_name`、`counterparty_account_masked`、`channel`、`summary`、`original_transaction_id`、`original_occurred_at`。
2. schema `v2 → v3` 迁移：老库就地 `ALTER TABLE` 补列，既有账户 / 操作 / 流水一行不丢，新列为 NULL，不重建表、不回溯编造旧行。
3. `seed_ledger_rows(rows: list[dict]) -> int`：按 `transaction_id` 幂等写入**已成形**的账本事实行（`operation_id` 用 `seed:<transaction_id>` 标明是种子），返回新写入条数。
4. `list_ledger` 返回新列；既有排序 `(occurred_at, transaction_id)` 不变；既有 7 元组写入路径（`commit_operation` / `finalize_operation`）行为不变，只是 INSERT 改成显式列名、事实列留空。

## 实现要点

- **存储层不认识银行时钟**：`seed_ledger_rows` 只接收成形行（`occurred_at` 已是 ISO 带时区字符串），相对月份与"当前月"的换算留给票 02 的银行服务；测试用固定时间戳。
- **只存事实不做规则**：范围、24 个月、归属、统计一律不在存储层出现。
- **迁移不补造**：升级前转账产生的流水没有商户列，票 02 按银行自己的操作回执如实处理，不在这里写死文本。
- **幂等**：同一 `transaction_id` 重复写入不产生重复行、不覆盖既有行（与 `commit_operation` 的同编号幂等口径一致）。
- 种子写入默认不被任何既有路径调用：`seed_demo()` 仍只种账户，既有 30+ 处 `list_ledger` 断言的语义不变。

## Acceptance criteria

- [ ] v2 库迁移到 v3 后既有数据完整、新列存在且为 NULL；重复初始化幂等
- [ ] `seed_ledger_rows` 幂等、写入行含全部事实列、返回新写入条数
- [ ] `list_ledger` 返回事实列，排序与既有行为不变
- [ ] `commit_operation` / `finalize_operation` 的既有 7 元组调用不变，同编号幂等与原子性不变
- [ ] `python -m pytest -q app/storage/` 全绿、后端全量无回归；PR 合入、CI 通过
- [ ] 完成后 [02 银行接缝票](02-bank-seam-list-transactions.md)解除阻塞
