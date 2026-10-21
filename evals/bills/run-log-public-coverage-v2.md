# 票06 · L02/L03 公共业务 + 四类异常对照运行台账（2026-10-21）

状态：**专项实跑通过（40/40）；整票仍为 partial，不是整包验收。**

## 环境与基线

- 仓库：`DrErwin/hackerthon-bank-agent`；PR [#209](https://github.com/DrErwin/hackerthon-bank-agent/pull/209)
- 分支：`test/bills/06-public-coverage-v2-20261021`
- 被测源码（exact commit）：[`b1f9982ff1f79f1e7d6e6acd5a45273e193c6459`](https://github.com/DrErwin/hackerthon-bank-agent/commit/b1f9982ff1f79f1e7d6e6acd5a45273e193c6459)
- 被测 tree：`3750898675f2c073150456b11cea9b64fc47ebbe`
- 基线（PR base / merge-base）：[`0d829d5a458d553ad0d975709b88f1f4b8a0529f`](https://github.com/DrErwin/hackerthon-bank-agent/commit/0d829d5a458d553ad0d975709b88f1f4b8a0529f)
- 执行时 `origin/main`：`ca3f579d22d0261ff4466e8c4a5d7317ee9f75e2`；其相对基线只改 `evals/security/`，未触及账单、公共契约、Harness、SecurityGate 或 MockBank 源码。
- 主机：Windows；Python 3.12.3；pytest 9.1.1；pydantic 2.13.5；fastapi 0.141.1；langgraph 1.2.12；deepagents 0.7.19。
- 隔离方式：独立 worktree `D:\hb-worktrees\pr209`，未改动主仓库工作区；使用主仓库 venv，`PYTHONPATH` 指向 worktree 的 `backend`。执行前确认 `import app` 解析为 `D:\hb-worktrees\pr209\backend\app\__init__.py`。

## 实际命令

```powershell
cd D:\hb-worktrees\pr209
$env:PYTHONPATH="D:\hb-worktrees\pr209\backend"
D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe -c "import app; print(app.__file__)"

D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe -m pytest -q evals/bills/test_public_coverage_v2.py

$rev = git rev-parse HEAD   # b1f9982ff1f79f1e7d6e6acd5a45273e193c6459
D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe evals/bills/run_public_coverage_v2.py --revision $rev
```

## 结果

| 分组 | 用例数 | 通过 | 失败 | 跳过 |
|---|---:|---:|---:|---:|
| L02 公共入口 | 14 | 14 | 0 | 0 |
| L03 公共入口 | 14 | 14 | 0 | 0 |
| 异常规则对照（规则1—4 各 3） | 12 | 12 | 0 | 0 |
| **合计** | **40** | **40** | **0** | **0** |

- `pytest`：`40 passed in 26.76s`，exit code 0。
- 正式 runner：`collected=40`、`passed=40`、`failed=0`、`skipped=0`、`error=0`、`collection_errors=0`，`test_exit_code=0`、`phase_result=Passed`；`overall_status=partial`、`full_ticket_acceptance=false` 保持原样。
- 规则对照：每条规则的 HIT/MISS/INSUFFICIENT（规则3第三条为 NONELIGIBLE）均按公开 `RuleCheck.status` 与公开 `findings` 断言，未调用私有规则函数作为被测对象。
- 完整性：143 个 Git 源码 blob 运行前后逐一校验（141 个文本源在 Windows 下做 CRLF→LF 规范化后比对）；56 个运行时 `app.*` 模块均来自被测源码；40 例 `funds_submit_calls=0`；每例银行完整表 SHA256 与余额前后一致；无 skip、无 collection error。
- 时间：`2026-10-21T12:21:24Z` — `2026-10-21T12:21:51Z`（北京时间 20:21），`run_id=876f4a63-2f59-4d22-a404-234af4b6aad3`。

## 证据

- [通过报告 gzip](evidence/2026-10-21/20261021T122151264650Z-python3.12.3-public-coverage-v2-b1f9982ff1f7.json.gz)
  - gzip SHA256：`1eba7f43984aaee726d33edd37a3a1f2dffcabf7ae2a91335f3b1d4ef6a5bbc6`
  - 解压 JSON SHA256：`25f8e01c3168decb8349e5f0ba86771b54fa9ad5b0813e0f0a30af3dab5bce44`
  - Git blob：`d92ba77b2a0e66d9e1dd19c0d6a4459671253d87`；25,561 bytes
  - 报告 `command` 为 `["-q", "--rootdir", ".", "evals/bills/test_public_coverage_v2.py"]`，无本机绝对路径。

## 首次失败与修复（保留原始失败证据）

- 首次在原始提交 `d77b9f9c9a100e50041cfb033097da2bccdbd024` 执行：**28 passed / 12 failed / 0 skipped / 0 error**，exit 1；12 条全部是规则对照，失败点位于 `test_public_bank_rule_contrast` 读取 `RuleCheck.matched`。
- 判定：**测试/用例问题，不是产品缺陷**。公开契约 `app.contracts.bills.RuleCheck` 只有 `rule_id/status/reason`；`matched` 是 `app.modules.bills._anomalies.RuleCheck` 的内部字段，从未进入公开契约（`git log -S matched -- backend/app/contracts/bills.py` 未发现该字段的公开版本）。
- 修复（仅 `evals/bills/`）：改为断言公开 `check.status`，matched/not-matched 由已有的公开 `findings` 断言覆盖；未改产品代码，未放宽断言。
- 同时把 runner 记录的 pytest `--rootdir` 从绝对路径改为 `.`，使归档报告不含本机绝对路径。
- 失败证据：[gzip](evidence/2026-10-21/20261021T121730587740Z-python3.12.3-public-coverage-v2-d77b9f9c9a10.json.gz)
  - gzip SHA256：`9428e3910704cf4749176cf22b2d2327e2a787ee63bef9961d60f9d74227514e`
  - 解压 JSON SHA256：`2f3b329acfbb39d805afa7344110e60b7bb441ab4df2492887a0eba37864fdf0`
  - Git blob：`bc5f15cb16b62cbf71b3cbb5d832974d19ad13f0`；25,795 bytes
  - 该报告只记录崩溃文件与行号，不含 traceback、交易明细或凭据；因生成于 runner 路径修正前，其 `command` 的 `--rootdir` 为绝对路径。
- 修复提交：`b1f9982ff1f79f1e7d6e6acd5a45273e193c6459`；修复后重跑得到上面的 40/40 证据。

## 范围与未覆盖

- 覆盖：真实注册的 BillsEntry + Harness + task-scoped SecurityGate/执行器 + BankGateway B01/B08 + 新建 SQLite MockBank；planner、LOW 风险/授权事实与银行时钟是显式测试替身。
- 不覆盖：真实 LLM、HTTP/SSE/浏览器/React、生产安全审批、真实银行连接；票07 与 Erwin/Ringo 的独立验收仍需进行。
- 本证据不把新 40 例与既有 L01 17 例、算术 147 例合并计数；`overall_status=partial` 保持不变。
- 执行/合并留痕：PM Erwin 授权代行跑证据与合并；AI 实施与审查，非 Ethan 本人审查。
