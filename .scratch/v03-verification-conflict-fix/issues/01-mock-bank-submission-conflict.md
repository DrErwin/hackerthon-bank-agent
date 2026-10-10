# 01：MockBank 验证码提交同号异内容抛专用冲突错误

Ticket ID: v03-verification-conflict-fix/01
Package: [transfer-agent-framework/packages/01：v0.3 纵向后端主链路](../transfer-agent-framework/packages/01-vertical-backend.md)
Spec: [本组规格](spec.md)
Core scenarios: 转账纵向场景 AF08（重复确认/幂等）；转账 PRD 附录 C T14（重复确认）、T15（验证失败）。本次为平台验证幂等行为，不复制完整纵向场景。
Verification: 银行验证提交层区分"冲突"与"越权/范围"：同 `submission_id` 已被同挑战同方法占用且内容不同 → 专用冲突码（如 `VERIFICATION_SUBMISSION_CONFLICT`），不改原提交结果、不计新错误；越权仍回 `ACCESS_DENIED`；重发/人脸路径同规则。同号同内容重传仍读原结果一次。
Owner: Erwin
Directory: `backend/app/services/mock_bank/`
Status: resolved
Blocked by: None
Source issue: [Issue #79](https://github.com/DrErwin/hackerthon-bank-agent/issues/79)

## 现场

- `verification.py:_previous_submission`（行243—255）：同号异内容/异挑战/异方法统一抛 `ValueError("VERIFICATION_SCOPE_MISMATCH")`，与越权无法区分；`resend_code`、`start_face`/`verify_face` 存在相同模式（行156、209、254）。
- 期望：冲突是一次明确的业务拒绝（409 语义），不是系统范围错误。

## 交付

1. 先写失败断言（红）：同号异内容 → 冲突码；随后新编号真实错误计数正常 +1。
2. 最小改动 `verification.py`：冲突路径抛专用码（如 `ValueError("VERIFICATION_SUBMISSION_CONFLICT")`），越权/挑战不存在等保持原有错误语义；不引入跨目录类型依赖。
3. 保持既有验证生命周期测试不回归（services 10 项 + 相关）。
4. 不与 API 映射混在同一提交（映射归票02）。

## 验收（本票局部）

- 银行层新断言红→绿；同号同内容重读原结果、同号异内容冲突、新编号计数 +1；
- `python -m pytest backend/app/services/` 全绿；
- 不产生资金写入、去重表不含验证码原文。

## Comments

- 2026-10-10：由 Issue #79 拆出，先于 api 映射票。
- 2026-10-10 实现完成（本地验证）：`_previous_submission`（verify_code/verify_face）与 `resend_code` 的同号异内容改为抛 `VERIFICATION_SUBMISSION_CONFLICT`，与 `VERIFICATION_SCOPE_MISMATCH`（挑战摘要守卫，行156）分离；先写红测试 `test_same_submission_id_with_different_code_raises_submission_conflict`（红：实际抛 SCOPE_MISMATCH）后转绿；`pytest backend/app/services/` 25 通过。
- 2026-10-10 合入：用户授权直推 main（本次不建 PR），提交 `7718633`。转 resolved。