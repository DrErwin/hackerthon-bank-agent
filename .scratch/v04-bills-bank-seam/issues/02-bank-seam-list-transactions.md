# v04-bills-bank-seam/02：银行接缝 list_transactions（模拟银行 + 网关）

Ticket ID: v04-bills-bank-seam/02
Package: PM 自拆（不开交付包）；Source issue [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91)
Spec: [v04-bills-bank-seam 规格](../spec.md)
Core scenarios: BF01/BF03/BF05/BF06 取数前置；关闭 #91 的验收面（本人读取、拒绝他人账户、半开区间/24 个月边界、完整性与错误传播）
Verification: `python -m pytest -q app/services/`（backend/ 下）全绿；接通测试从 `BankGateway.list_transactions` 进入，覆盖成功/他人账户拒绝/半开边界/24 个月拒绝/空成功/失败区分/as_of 随银行时钟变化
Owner: Erwin
Directory: backend/app/services/
Status: open
Blocked by: [v04-bills-bank-seam/01：契约模型](01-contracts-models.md)
Source issue: [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91)

## What to build

账单模块能通过公开入口拿到本人账户在指定时间范围内的**完整**流水事实：

1. **模拟银行（`services/mock_bank/`）**：按 B08 语义实现范围查询——本人账户校验、半开区间（`occurred_at >= start_at` 且 `< end_at`，首尾不重复计账）、最多最近 24 个月、`as_of` 取银行自己的时钟（可注入，沿用 `services/test_verification.py` 的 Clock 模式）、空数据成功返回 `[]`、失败与空严格区分；错误分类 `INVALID_ARGUMENT` / `ACCESS_DENIED` / `RANGE_UNSUPPORTED`。范围过滤在银行服务内基于 `storage/mock_bank` 既有 `list_ledger` 读取完成，本票不改存储层 schema。
2. **网关（`services/bank_gateway/gateway.py`）**：公开 `list_transactions(context, account_id, start_at, end_at)`，薄转发 + 结果映射（成功 `QueryOk[TransactionList]`、失败 `QueryFailure`），不在网关重写银行规则。
3. 返回的 `Transaction` 按发生时间、再按 `account_id`/`transaction_id` 稳定排序；保留来源账户与 `as_of` 供多账户统计核对。

## 实现要点

- 字段与规则引用冻结文档（[B08 + Transaction](../../../docs/contracts/银行接口字段-2026-09-24.md)、[§5.3](../../../docs/contracts/公共契约-2026-09-23.md)），不复制定义、不新增字段。
- 确定性：范围与 24 个月判断相对银行时钟，不依赖调用方时间；测试注入时钟覆盖边界两侧。
- 不改变 transfer 路径与既有方法行为；账单业务计算（消费/退款/转账拆分、七类归总）仍在 bills 模块。

## Acceptance criteria

- [ ] 本人账户指定范围返回完整流水 + `as_of`；排序稳定
- [ ] 他人账户 `ACCESS_DENIED`；`start_at >= end_at` 或时间格式非法 `INVALID_ARGUMENT`；超出最近 24 个月 `RANGE_UNSUPPORTED`
- [ ] 半开区间边界样本不重复计账；空区间成功 `[]` 且与失败可区分；失败不得伪装成空成功
- [ ] `as_of` 随注入时钟前进而变化（银行侧时钟，不用调用方时间）
- [ ] `python -m pytest -q app/services/` 全绿；PR 合入、CI 通过
- [ ] 完成后向 [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91) 回帖：公开导入路径 + 合入 PR + 验证方式，供账单侧接真实取数
