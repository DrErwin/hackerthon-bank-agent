# services —— 底座共享的应用能力

归属：底座（Erwin）。

放什么：可复用的应用能力。当前两个子目录：`bank_gateway/`（银行接入实现，业务模块唯一银行调用入口）、`mock_bank/`（模拟银行）。

边界：业务模块不直接修改这里；银行调用一律经 `bank_gateway`，不直连。

修复票 `v03-transfer-eval-fixes/05`：基础验证码过期且未达到三错时可重发，新挑战重新计五分钟、保留累计错误次数；旧挑战失效。同submission重传读取原结果。中风险失败/超时、已通过和跨归属继续拒绝，中风险重发仍沿用原期限。先复现过期重发TASK_TERMINATED，再最小修复；services验证生命周期10项测试通过。真实HTTP组合及一笔500元资金事实在验证生命周期集中联调记录，不由银行单测冒充。涉及验证规则，仍待真人安全审查和合入。

06组合恢复接缝：银行准备验证遇到本任务已有终止挑战时，内部ValueError携带现有VerificationChallenge事实（不含验证码或输入）。这不修改银行规则及公开契约字段，用于安全门识别重发已落库但应用尚未登记的恢复窗口；原ValueError兼容保持。services新增定向覆盖，新总计11通过。

## G2-B 旧尝试挑战退役（v05-birthday-platform-dependencies/06）

**表**：`bank_verification_retirements` 与验证挑战同库。同一 `(user_id, demo_round_id, task_id, operation_id, action_revision)` 只保存一份退役事实（`retirement_id`、`retired_challenge_ids` 为退役时仍 `pending` 的挑战编号 JSON list、`retired_at`）。退役只增不改：挑战行、原结果与时间戳不删除、不改写；`VerificationChallenge` 与公开契约/枚举不变。

**写接缝**：`MockBankVerification.retire_action_challenges(context, *, operation_id: UUID, action_revision: int) -> VerificationRetirement`（keyword-only）。在**同一个银行库事务**内先按既有规则刷新到期挑战，再判该尝试是否已有 `passed`/`failed`/`expired`：有则抛 `ChallengeNotRetireable`，`reason_code` 为 `ALREADY_PASSED` / `ALREADY_FAILED` / `ALREADY_EXPIRED`，不写退役事实、整笔回滚；否则写退役行。幂等：同参重复返回同一事实；异 operation/revision 互不影响。该尝试**没有任何挑战**（确认等待）时同样成功并写退役行，从而阻止之后为旧尝试再创建挑战——但银行此时无法校验 operation 归属（见下方已知残留）。

**读接缝**：`MockBankVerification.retirement_for(context, operation_id, action_revision) -> VerificationRetirement | None` 只读返回同一银行库中的退役事实，不产生副作用；按 context 的 user/round/task 归属，跨 scope 返回 `None`（不泄露存在性）。`BankGateway` 只做协议转发，不塞业务判断。

**已退役尝试（`CHALLENGE_RETIRED`）**：`create_verification` 拒绝为它再创建挑战；`resend_code`/`verify_code`/`start_face`/`verify_face`/`get_demo_code` 拒绝新请求，不改挑战状态、不生成新挑战或提交记录。既有 submission 幂等不受影响：退役前已记录的同一 `submission_id` 重放仍原样返回原结果，只有新提交才被拒。任务级终止扫描跳过该退役尝试的旧挑战；其它 `failed` / `action_step_up` `expired` 挑战照旧抛 `VerificationTerminated`，既有失败/过期规则不变。

**错误码口径**：`ALREADY_*` / `CHALLENGE_RETIRED` 只是后台内部异常属性（`.reason_code` / 机器错误码），不作为用户可见文案经 API 展示；API 的 `reason` 仍走既有通用 409 说明，前端/文档不得把它们当提示语。

**已知残留风险（登记）**：该 operation 在银行库尚无任何挑战时，银行无法区分「合法新尝试」与「错 task 自报 operation」；退役仍成功并写退役行防迟到创建。operation 归属与调用授权必须由 02/03 用可信上下文把关，不能依赖银行侧认 operation 归属。

**回滚语义**：退役被拒时整笔事务回滚，判定时刷新出的惰性过期不落库，挑战行仍为 `pending`；下一次读取/扫描再按既有规则终态化（不是「永远 pending」）。

验证：从 `backend/` 运行 `python -m pytest -q app/services/test_verification_retirement.py`（15 项）与 `python -m pytest -q app/services/`（75 passed）。
