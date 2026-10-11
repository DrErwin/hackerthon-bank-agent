# CI flake 修正：验码落盘断言的数字巧合（Issue #99）

Status: done（2026-10-12 收口：票 01 已合入 PR [#103](https://github.com/DrErwin/hackerthon-bank-agent/pull/103)，[Issue #99](https://github.com/DrErwin/hackerthon-bank-agent/issues/99) 关闭）
Owner: Erwin（PM 授权 AI 建立规格与票据）
Source issue: [Issue #99](https://github.com/DrErwin/hackerthon-bank-agent/issues/99)
Deadline: 无独立硬截止；随 v0.4（最晚 10-20）一并完成

## Problem Statement

`Repository checks` 会偶发失败在 `app/api/test_verification_fault.py` 的「验证码不得落盘」断言：它把整行数据拼成一个字符串再做子串匹配，而演示验码是 6 位随机数字，行里有大量长数字串（`occurred_at` 的小数秒、UUID 数字段、金额、耗时）。6 位数字在其中偶然出现并不罕见，于是正确的检查被数字巧合误判为泄漏：PR [#98](https://github.com/DrErwin/hackerthon-bank-agent/pull/98) 的 head `d83646d` 首次 run [38162082608](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/38162082608) 因此判红（`audit_events`），同提交重跑即绿（attempt 2 success），本地全量同期 394 passed。这会让任何 PR 间歇性白红一次，浪费重跑、误导审查者。

## Solution

把「整行子串匹配」换成「逐列 + 数字边界匹配」：六张表每一列仍然检查，但验码必须作为**独立 token**出现（前后不是数字）才算落盘——字符串按文本匹配，BLOB（LangGraph 状态）按字节匹配，其它类型按其文本形式匹配。这样既保留旧口径的扫描面（含 `checkpoint_*` 的 blob 与数值列），又不再把「被更长数字串包住」的巧合当成泄漏。

检查只存在于测试助手内：不改验码生成、存储与日志链路，也不改审计表结构，原用例的断言意图（六张表逐一检查、验码不得落盘）不变。

## Implementation Decisions

- 助手落位 `app/api/test_verification_fault.py`（测试专用），签名 `stored_code_leak(rows, code)`，命中时返回该单元格值便于定位，未命中返回 `None`；断言消息带表名与命中值。
- 模式：文本 `(?<!\d){re.escape(code)}(?!\d)`；字节 `rb"(?<!\d)" + re.escape(code.encode("ascii")) + rb"(?!\d)"`；其它类型先转成 `str` 再走文本模式。`re.escape` 保证即便将来验码含元字符也安全。
- **覆盖范围**：与旧口径逐行扫描的列集合一致（含 `checkpoint_writes` / `checkpoint_blobs` 的 `value_blob` BLOB 与各数值列），只把匹配口径从「整行子串」换成「逐列数字边界」。
- **残余口径**：唯一不再命中的形态是「验码被拼进更长的数字串」（例如 `...30.8499763Z` 里的 `499763`）。当前落盘形态（JSON / msgpack 里验码都是独立值，前后是引号、长度字节或字段边界）仍会命中；若将来出现拼接式落盘，需要另行收紧口径。

## Testing Decisions

- 助手自身加确定性用例，固定三种情形：长数字串内部不命中；JSON 值 / 参数串等独立 token 命中并返回该字段；数值列（如 `123456` 的整数）不命中。
- 原用例保持六张表逐一检查，跑通即可——不需要复现 flake（它是概率事件，靠口径用例固定）。

## Out of Scope

- 改验码生成、去重、日志与审计存储链路；改审计事件结构；给其它测试做同类体检。
- Issue #99 里提到的其它 CI 健康项。

## Tickets

- [ci-flake-verification-code/01：验码落盘断言改为数字边界匹配](issues/01-digit-boundary-assertion.md)
