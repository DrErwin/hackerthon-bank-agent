# 08 输出探针凭据口径收紧：机器载荷不误报

Ticket ID: v05-observer-seams/08
Package: 无独立交付包——v0.5 平台遗留收口（[spec](../spec.md)），来源 [Issue #216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)
Spec: [v05-observer-seams/spec.md](../spec.md)
Core scenarios: S5（导出不得因机器数据被误拦）
Type: 开发（缺陷修复）
Owner: Erwin（AI 代行实施与审查，非 Ringo 本人审查）
Directory: `backend/app/audit/`
Status: Done
Blocked by: [v05-observer-seams/03](03-output-probe.md)（探针已合入）
Source issue: Issue #216

## 背景（2026-10-22 合并后 CI 失败定位）

票 04 在导出下载口接 `probe_secrets` 后，main `3f8d71d` 与 PR #223 的 CI 在 `test_f35_task_scope_and_f24_audit_download_checks` 上失败：审计证据包 JSON 里 `"reason_code"` 等键包含 `code` 字样，附近若出现 6 位数字（如 `duration_ms`），探针即误报 `credential`，导致管理端审计导出被 503 拦下。**这是探针的误报缺陷**（机器载荷 ≠ 自然语言验证码），也是 CI 在不同运行间不稳定的来源。

复现：`probe_output('{"duration_ms": 123456, "reason_code": "CAPABILITY_SELECTED"}')` → `credential`（不应命中）。

## 交付物

`backend/app/audit/output_guard.py` 收紧「6 位数字 + 码/code 上下文」启发式，改为**短语相邻**判定，不再用 ±20 字符窗口：

- 中文标签后紧邻：`(?:验证码|短信码|动态码|登录码|校验码)\s*(?:是|为|[:：=])?\s*(?<!\d)\d{6}(?!\d)`——保留「验证码123456」「验证码是 123456」形状；
- 数字在前的中文短语：`(?<!\d)\d{6}(?!\d)\s*(?:是|为)[^，,。;；\n:：]{0,10}(?:验证码|登录码|校验码|短信码|动态码)`——保留「123456 是本次登录的验证码」形状；
- 英文标签必须是独立词并带分隔符：`(?<![A-Za-z0-9_])(?:code|otp)(?![A-Za-z0-9_])\s*(?:[:：=]|是|为|\s)\s*(?<!\d)\d{6}(?!\d)`——`reason_code` / `"method": "code"` 这类机器键值不再命中，「code: 123456」仍命中；
- 其余三类（`full_account` / `personal_name` / `personal_phone`）与 `SECRET_LABEL` 口径不变；脱敏仍复用 `journal.redact`。

## 验收（E2E，真实审计库/导出包形状）

| 编号 | 场景 | 通过条件 |
|---|---|---|
| H01 | 机器载荷不误报 | 上述复现 JSON、含 UUID 且 `"method": "code"` 的事件、含 `duration_ms`/`reason_code` 的真实审计包形状 → `credential` 零命中，`probe_secrets` 为 False |
| H02 | 自然语言仍命中 | 「验证码123456」「验证码是 123456」「code: 123456」「123456 是本次登录的验证码」「登录码 135790」→ 均命中 credential，原文被脱敏或被调用方拦截 |
| H03 | 回归 | 票 03 既有 C01—C05 语义与 `backend/app/api/test_app.py::test_f35_task_scope_and_f24_audit_download_checks` 在真实审计包上通过；`pytest -q backend` 全绿 |
| H04 | 稳定 | 同一审计包重复探测结果一致；不因 UUID/时长等随机数字改变判定 |

## 备注

- 只改 `backend/app/audit/`；不改票 04 的接线（`probe_secrets` 仍是布尔门）。
- 修复后 `probe_secrets` 对审计/账单导出不再误拦，真凭据（标签 + 值）仍拦截。

## Comments

- **2026-10-22 交付**：[PR #224](https://github.com/DrErwin/hackerthon-bank-agent/pull/224) squash `86e3752` 已合入（修 main CI 红）。6 位码凭据改为短语相邻判定（中文标签紧邻 / 数字在前中文短语 / 英文独立词），机器载荷零误报；真凭据仍拦截。验证：`backend/app/audit/` 19 passed（新增 H01/H04）+ F35 审计导出用例恢复通过；合并后 main CI 恢复绿。
