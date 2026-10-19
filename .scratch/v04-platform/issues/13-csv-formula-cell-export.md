# 13：F22/F24 明细 CSV 公式型单元格安全处理

Ticket ID: v04-platform/13
Type: 开发（缺陷修复）
Owner: Erwin
Directory: backend/app/api/
Status: in_progress（2026-10-19 接 [Issue #161](https://github.com/DrErwin/hackerthon-bank-agent/issues/161)）
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
