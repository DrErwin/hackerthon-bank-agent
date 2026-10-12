Ticket ID: v04-task-history-replay/01
Package: 不适用（PM 自拆，不开交付包；见 [spec](../spec.md)）
Spec: [v04-task-history-replay spec](../spec.md)
Core scenarios: HR-1（视图字段完整）、HR-2/HR-3（created_at 支撑刷新与跨会话回放时间线）
Verification: `python -m pytest -q app/contracts/test_contracts.py`（backend 目录）通过；`TaskRecordsView` 模型可从既有视图构造并序列化；`VerificationView` 带 `created_at` 且旧字段不变。合入后通知前端线（#89）：类型生成登记归其执行。
Owner: Erwin
Directory: backend/app/contracts/
Status: resolved（PR #109，squash b4e3f70，2026-10-12 合入；契约测试 44 passed、旧消费方回归 94 passed、CI 绿）
Blocked by: None
Source issue: Issue #85（https://github.com/DrErwin/hackerthon-bank-agent/issues/85）

## 交付

1. `security.py`：`VerificationView` 新增 `created_at: Timestamp`（轻量确认档：新增字段，旧调用与响应保持有效）。
2. `api.py`：新增 `TaskRecordsView`——`task_id: ID`、`confirmations: list[ConfirmationView]`、`verifications: list[VerificationView]`。
3. `__init__.py` 导出新增模型；`test_contracts.py` 追加模型测试。

## 契约变更记录（PR 四件事）

为什么改：#85 需要按任务的只读回放，验证视图缺时间线字段，确认/验证列表无公共承载模型。原来/现在：无 → 新增 `TaskRecordsView`；`VerificationView` 七字段 → 八字段（加 `created_at`）。影响方：后端 api（票03 消费）、前端 #89（类型生成后消费）。旧调用：`VerificationView` 既有构造路径（`verification_view()` 用 include 投影）自动带上新字段，无破坏；以全量回归验证。
