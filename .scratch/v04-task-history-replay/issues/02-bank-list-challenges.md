Ticket ID: v04-task-history-replay/02
Package: 不适用（PM 自拆，不开交付包；见 [spec](../spec.md)）
Spec: [v04-task-history-replay spec](../spec.md)
Core scenarios: HR-3、HR-4（跨会话回放完整性——按任务而非当前会话列举挑战）
Verification: `python -m pytest -q app/services/test_verification.py` 通过（含新增失败方式用例）；票03 E2E 以真实流程复验。本票为隔离测试：先列失败方式、先写用例再写实现。
Owner: Erwin
Directory: backend/app/services/
Status: resolved（PR #110，squash 91f69e8，2026-10-12 合入；services 38 passed、CI 绿；双轴审查发现的 _expire 副作用越界由 PR #112 修复：先归属过滤、仅终态化本任务挑战，39 passed）
Blocked by: None
Source issue: Issue #85（https://github.com/DrErwin/hackerthon-bank-agent/issues/85）

## 失败方式（先写）

1. **越权列举**：非任务所有者（不同 user_id 或 demo_round_id）调用按任务列举，拿到他人挑战 → 必须空/拒绝。
2. **跨会话漏记**：按当前会话过滤会漏掉旧会话创建的历史挑战（HR-4 反例）——列举不得看 session。
3. **串任务**：同用户其他任务的挑战混入 → 必须 task_id 精确匹配。
4. **终态漂移**：pending 挑战已过截止时间仍显示 pending → 与 `get_verification` 一致做惰性终态化。
5. **顺序不稳**：列表无稳定排序（created_at, challenge_id）→ 时间线抖动。

## 交付

1. `mock_bank/verification.py`：新增只读 `list_task_challenges(context, task_id)`——按 (user_id, demo_round_id, task_id) 归属过滤全量挑战，pending 惰性终态化复用 `_expire`，按 (created_at, challenge_id) 排序返回；不改 `_in_scope` 与既有读写语义。
2. `bank_gateway/gateway.py`：新增 `list_verifications(context, task_id)` 只读透传。
3. `test_verification.py`：按上述失败方式补用例（先写）。
