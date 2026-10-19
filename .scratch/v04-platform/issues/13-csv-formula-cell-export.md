# 13：F22/F24 明细 CSV 公式型单元格安全处理

Ticket ID: v04-platform/13
Type: 开发（缺陷修复）
Owner: Erwin
Directory: backend/app/api/
Status: resolved（[PR #168](https://github.com/DrErwin/hackerthon-bank-agent/pull/168) squash `1b1a786` 合入 main，2026-10-19；CI 绿；独立子代理审查〔AI，非真人〕判**通过、无必修项**，变异 M1/M2/M3 全部被杀；合并后在 main 实跑 Ringo 票 04 runner **18 Passed / 0 Failed**；[Issue #161](https://github.com/DrErwin/hackerthon-bank-agent/issues/161) 已关闭）
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: P04（F22 / F24 明细导出）；公共契约 §6.7「HTML 转义和 CSV 单元格安全处理由导出器负责」
Verification: HTTP 端到端复现（真实 FastAPI + 导出服务 + 隔离模拟银行）覆盖 `=`、`+`、`-`、`@` 四类起始符及前置空白；普通文本与中文商户名原样；现有 app/api 导出测试全绿；复跑 Ringo 票 04 的 `evals/security/export_regression.py`（修复前 14 Passed / 4 Failed，修复后 18 Passed）。命令与输出记入本票 Comments。
Blocked by: None
Source issue: [Issue #161](https://github.com/DrErwin/hackerthon-bank-agent/issues/161)（Ringo 复现，转给 Erwin）

## 交付

1. `backend/app/api/service.py:_details_csv` 由导出器统一处理文本单元格：单元格值 `lstrip` 后以 `=`、`+`、`-`、`@` 起头时加单引号前缀，使其按字面文本落盘；金额分、时间等字段语义不变，正常文本与中文商户名原样输出。
2. 回归：从真实 F22（创建 details 导出任务）→ 验证码验证 → F24 下载 → `csv.DictReader` 解析，断言 4 类起始符与前置空白的 `counterparty_name` / `summary` 单元格不再以危险字符起头；普通行断言「楼下面馆」「6222****1234」等仍原样可读。
3. 复跑：`backend/app/api` 现有导出用例全绿；Ringo 票 04 复现脚本 18 项全通过；全量后端测试通过；CI 绿。

## 边界与依赖

- 只改 `backend/app/api/`；卡片 HTML 已按 §6.7 转义，不动。
- 不新增业务规则、不改冻结契约、不改文件格式；`evals/security/`（Ringo 目录）只作复跑引用，不提交改动。
- 历史失败证据由 Ringo 保留；本票只提供修复与新证据。

## Comments

- 2026-10-19：按 [Issue #161](https://github.com/DrErwin/hackerthon-bank-agent/issues/161) 建立。复现依据：[PR #162](https://github.com/DrErwin/hackerthon-bank-agent/pull/162)（Draft）的 `evals/security/test_export_boundary.py` 4 条失败实例；Ringo 已记录 18 项 14P/4F 首轮结果，失败均为 CSV 公式型文本原样下载。
- 2026-10-19 实施与合并（[PR #168](https://github.com/DrErwin/hackerthon-bank-agent/pull/168)，`9301f5c` → squash `1b1a786`）：`service.py` 新增 `safe_csv_cell`（`CSV_FORMULA_OPENERS` + `lstrip()` 判定，文本列统一过，`amount_fen` 保持 int），`test_app.py` 新增 2 个真实 HTTP 端到端用例（6 个公式型样本 + 1 个普通行对照）。实施侧实数：TDD 修复前 6F/1P → 修复后 7P；`pytest app/api -q` 91 passed；`pytest -q` 715 passed；Ringo runner 修复前 14P/4F → 修复后 18P/0F。
- 2026-10-19 独立审查（子代理，AI、非 Ringo 真人）：**通过、无必修项**；隔离 worktree 固定 `9301f5c`，`app.__file__` 自证；`-k details_csv` 7 passed、`app/api` 91 passed；Ringo runner 先在 base 复现 14P/4F，再在修复后 18P/0F；变异 M1（删除前缀分支）6F/1P、M2（只处理 counterparty_name）6F/1P、M3（对 int 也加前缀）1F/6P，全部被杀并已还原（blob 与 HEAD 一致）。非阻塞建议：`safe_csv_cell` 可补返回标注；前置空白变体只配了 `=`/`+`。
- 2026-10-19 合并后复验（Lead，main `1b1a786`）：Ringo `export_regression.py` 18 Passed / 0 Failed（报告 `status_counts={"Passed": 18}`，源文件 sha256 记于报告）；#161 已回帖并关闭，PR #162 待 Ringo 另批复验并转 Ready（历史 Failed 保留）。
- 备注：返修后全量后端一次运行 **716 passed / 2 failed**，两项失败均为 `app/services` 的超时预算用例（`test_bank.py::test_timeout_returns_unknown_then_original_result_becomes_visible`、`test_subscriptions.py::test_gateway_cancel_timeout_is_unknown_and_b14_finds_the_bank_result`），单跑 2 passed、与本票改动无关，属 [Issue #166](https://github.com/DrErwin/hackerthon-bank-agent/issues/166) 已登记的 Windows 计时抖动；PR CI（Linux）绿。
