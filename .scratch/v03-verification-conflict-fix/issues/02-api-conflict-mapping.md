# 02：API 验证码提交冲突映射 409 并恢复后续计数

Ticket ID: v03-verification-conflict-fix/02
Package: [transfer-agent-framework/packages/01：v0.3 纵向后端主链路](../transfer-agent-framework/packages/01-vertical-backend.md)
Spec: [本组规格](spec.md)
Core scenarios: 转账纵向场景 AF08（重复点击只动一次钱）、AF11（不可绕过安全入口）；验证码提交的幂等与冲突（公共契约 F17）。
Verification: 验证码提交入口识别票01的专用冲突码 → HTTP **409 REQUEST_CONFLICT**（按[安全与审计字段 §6](docs/contracts/安全与审计字段-2026-09-24.md)操作记录冲突语义）；冲突**不**发布"待核实"快照（`verification_fault` 不触发），后续新编号提交可正常到达银行并计入错误（1→2）；同号同内容重传仍只读原结果一次。
Owner: Erwin
Directory: `backend/app/api/`
Status: pending
Blocked by: [v03-verification-conflict-fix/01](01-mock-bank-submission-conflict.md)
Source issue: [Issue #79](https://github.com/DrErwin/hackerthon-bank-agent/issues/79)

## 现场

- `app.py` 验证码提交守卫（行337—384）：未识别异常一律转 503（行352），并进入 `verification_fault` 待核实快照（`service.py:verification_fault`），随后 `check_verification_retry` 挡住新编号 → 计数停滞。

## 交付

1. 先写失败断言（红）到 `test_app.py`：不同 API request_id、同银行 submission_id、异内容 → 409 且**不**进待核实；随后新 submission_id 真实错误计数 +1。
2. 最小改动：识别票01冲突码 → `ApiProblem(409, "REQUEST_CONFLICT")`，不走故障快照；保持既有同 request_id 异内容 409、同号同内容幂等、503 仅用于真实依赖故障的语义。
3. 不混入 bank 层改动（归票01）与评测改动（归 v03-security-eval-integration/04）。

## 验收（本票局部）

- 新断言红→绿；后端 api 全量测试绿；既有 `test_app.py::...changed.status_code == 409` 保持；
- 无资金写入；验证码原文不进 API 记录/日志。

## Comments

- 2026-10-10：依赖票01的专用冲突码。