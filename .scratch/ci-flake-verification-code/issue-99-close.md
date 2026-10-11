## 已修（PR [#103](https://github.com/DrErwin/hackerthon-bank-agent/pull/103)，squash `8a9b3b6`）

检查口径从「整行拼成一个字符串做子串匹配」换成「**逐列 + 数字边界**」：

- 六张表每一列仍然检查，含 `checkpoint_writes` / `checkpoint_blobs` 的 `value_blob`（BLOB）与各数值列；
- 字符串按文本、BLOB 按字节、其它类型按其文本形式匹配；验码必须作为**独立 token**（前后不是数字）才算落盘；
- 失败信息带表名与命中值，便于定位。

**残余口径**：唯一不再命中的是「验码被拼进更长的数字串」这一形态（例如 `...30.8499763Z` 里的 `499763`）。当前落盘形态（JSON / msgpack 里验码都是独立值，前后是引号、长度字节或字段边界）仍会命中；若将来出现拼接式落盘，需另行收紧。

首版实现用 `isinstance(value, str)` 过滤，被审查指出 BLOB 列整类漏检（实测该用例会扫到 324 个 bytes 单元格，验码最可能落盘的正是 LangGraph 状态），已改为全列覆盖并补字节级用例。

**验证**：`python -m pytest -q app/api/test_verification_fault.py` **7 passed**（含确定性口径用例：文本/字节长数字串内部不命中、整数值落在更长串内不命中、JSON 值 / 参数串 / 整数 / BLOB 独立 token 命中）；`app/api/` **58 passed**；Repository checks 绿。票面与规格：`.scratch/ci-flake-verification-code/`（票 01）。

顺带核查：仓库内同款「整行子串」断言还有 3 处（`api/test_payee_reference.py`、`agent_platform/test_payee_references.py`、`modules/transfer/test_payee_checkpoint.py`），匹配的都是 16/19 位账号，不会偶然撞上，未纳入本票。
