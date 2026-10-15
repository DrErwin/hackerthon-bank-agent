# 09：模块防重用例补真实覆盖（杀变异 M2）

Ticket ID: v04-ethan-bills-backend/09
Type: 测试
Owner: 周恩宇（Ethan）
Directory: backend/app/modules/bills/
Status: open
Package: [v04-bills/packages/01-bills-backend：v0.4 账单业务能力与评测](../../v04-bills/packages/01-bills-backend.md)
Spec: [v04-ethan-bills-backend 账单实施规格](../spec.md)
Core scenarios: BF01（同请求不重复读银行）；测试覆盖真实性返修
Verification: 新用例绕开平台短路（`harness.py:417-418` 同 request_id 短路）直接驱动模块入口，证明 `entry.py:160-161` 的模块级防重独立生效：同 `(session, request_id, intent)` 重放不再触发银行读取、返回同一结果；对防重判断做变异（删掉模块防重分支）用例必须变红。`app/modules/bills` 全量回归通过。命令与输出记入本票 Comments。
Blocked by: None
Source issue: [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136)

## 交付（对应 [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136) 清单项 4）

1. `test_public_integration.py:194-201` 的 `test_no_duplicate_reads_when_original_start_is_replayed` 用例名声称覆盖模块防重，实际由平台短路满足（变异 M2 存活）——补一条真正覆盖模块级防重（`entry.py:160-161`）的用例，或若平台短路即设计意图则改用例名并说明。
2. 变异自证：在票内 Comments 记录「改坏模块防重 → 新用例红」的证据（杀了几个、活了几个）。

## 边界与依赖

- 只改 `backend/app/modules/bills/` 测试（必要时含被测分支的最小修正）。
- 与 [08](08-l01-rework-consistency.md) 相互独立，可并行；同目录分支注意先后合入与 rebase。

## Comments

- 2026-10-16：PM 侧按 [PR #131 审查结论第四节](https://github.com/DrErwin/hackerthon-bank-agent/pull/131#issuecomment-6198615597) 第 4 项开票（[Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136)），Owner 周恩宇接手实施。
