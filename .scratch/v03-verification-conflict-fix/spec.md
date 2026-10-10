# v03-verification-conflict-fix：验证码提交同号异内容冲突修复

> 本组对应 [Issue #79](https://github.com/DrErwin/hackerthon-bank-agent/issues/79)：同一银行 `submission_id` 换不同验证码内容时返回 503 而非 409，且后续真实错误不再计入。

## 背景与根因（已定位）

1. `backend/app/services/mock_bank/verification.py` 的 `_previous_submission`：同号异内容抛通用 `ValueError("VERIFICATION_SCOPE_MISMATCH")`，与越权/范围错误混用。
2. `backend/app/api/app.py` 验证码提交守卫把未识别错误一律转 `503 / DEPENDENCY_UNAVAILABLE`。
3. 因被当成技术故障，API 按容错设计发布"验证待核实"快照，后续新编号提交被同任务重传闸挡住 → 错误计数停滞。

## 目标口径（已冻结，见 [安全与审计字段 §6](docs/contracts/安全与审计字段-2026-09-24.md)）

- 操作记录冲突 → **409 `REQUEST_CONFLICT`**，不改原提交结果、不计为新错误、不转入待核实；
- 新编号的真实错误可正常增加计数；同号同内容重传仍只读原结果一次；
- 去重存储不含验证码原文；不产生未授权资金写入。

## 范围与目录拆分（一张票 = 一个目录 = 一个 PR）

| 票号 | Directory | 内容 |
|---|---|---|
| `v03-verification-conflict-fix/01` | `backend/app/services/mock_bank/` | 同号异内容抛专用冲突码，与越权/范围错误分离 |
| `v03-verification-conflict-fix/02` | `backend/app/api/` | 识别冲突码 → 409；不发布待核实快照；后续计数恢复正常 |
| `v03-security-eval-integration/04` | `evals/security/` | SEC-V-002 断言翻转（503失败态 → 409正确行为）+ 重跑取证 |

## 验收

- 01、02 各自测试红→绿（先写断言后改实现），相关既有测试不回归；
- 04 重跑后 SEC-V-002 由 Failed 转 Passed（或如实记录仍失败）；
- 每题 PR 走 CI；涉及验证与错误码规则，按原则交安全侧审查（口径已冻结，不阻塞）；纯文档票直接提交 main。