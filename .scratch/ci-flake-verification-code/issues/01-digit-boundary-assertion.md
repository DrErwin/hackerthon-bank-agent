# ci-flake-verification-code/01：验码落盘断言改为数字边界匹配

Ticket ID: ci-flake-verification-code/01
Package: PM 自拆（不开交付包）；Source issue [Issue #99](https://github.com/DrErwin/hackerthon-bank-agent/issues/99)
Spec: [ci-flake-verification-code 规格](../spec.md)
Core scenarios: 安全回归——验证码不得落盘；同时不再被数字巧合误判
Verification: `python -m pytest -q app/api/test_verification_fault.py`（backend/ 下）全绿；助手确定性用例覆盖长数字串/独立 token/数值列三种情形；后端全量无回归
Owner: Erwin
Directory: `backend/app/api/`
Status: done（2026-10-12 实现并合入，PR [#103](https://github.com/DrErwin/hackerthon-bank-agent/pull/103)，squash `8a9b3b6`；`app/api/test_verification_fault.py` 7 passed、`app/api/` 58 passed、Repository checks 绿；只读审查指出首版 BLOB 漏检已修）
Blocked by: None（可立即开始）
Source issue: [Issue #99](https://github.com/DrErwin/hackerthon-bank-agent/issues/99)

## What to build

1. 在 `app/api/test_verification_fault.py` 抽出测试助手 `stored_code_leak(rows, code)`：**逐列**判断（字符串按文本、BLOB 按字节、其它类型按文本形式），且用数字边界匹配（文本 `(?<!\d)code(?!\d)`、字节 `rb"(?<!\d)"+code.encode()+rb"(?!\d)"`）；命中返回该单元格值，未命中返回 `None`。
2. 原用例的「六张表逐一检查」改用它，断言意图不变（验码不得落盘），失败信息带表名与命中值。
3. 助手自身加确定性用例：长数字串内部不命中（文本与字节各一例）、整数值落在更长数字串内不命中、JSON 值/参数串/整数/BLOB 独立 token 命中。

## 实现要点

- 只改测试：不动验码生成、去重、日志、审计表结构与生产代码。
- 不缩小检查面：六张表（`api_requests`、`api_events`、`tasks`、`audit_events`、`checkpoint_writes`、`checkpoint_blobs`）仍逐列检查，含 `value_blob` BLOB 与数值列；只把匹配口径从「整行子串」换成「逐列数字边界」。
- 残余口径写清在规格里：唯一不再命中的是「验码被拼进更长数字串」的形态（当前 JSON / msgpack 落盘都是独立值，能命中）。

## Acceptance criteria

- [x] 原用例六张表仍逐列检查；字符串/字节/数值里的独立 token 命中即失败，并给出表名与命中值
- [x] 新增助手确定性用例：长数字串内部不命中（文本、字节）、整数值更长数字串内不命中、JSON 值/参数串/整数/BLOB 独立 token 命中
- [x] `python -m pytest -q app/api/test_verification_fault.py` 全绿；后端全量无回归；PR 合入、CI 通过
- [x] 合入后在 [Issue #99](https://github.com/DrErwin/hackerthon-bank-agent/issues/99) 回帖证据并关闭
