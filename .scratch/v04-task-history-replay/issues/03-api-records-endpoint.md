Ticket ID: v04-task-history-replay/03
Package: 不适用（PM 自拆，不开交付包；见 [spec](../spec.md)）
Spec: [v04-task-history-replay spec](../spec.md)
Core scenarios: HR-1—HR-6（E2E 全覆盖；见 spec 表）
Verification: `python -m pytest -q app/api/test_app.py` 与后端全量通过；PR 含场景↔断言对照。联调验收（前端重建回放 + 组件测试）归 #89 前端线，不在本票。
Owner: Erwin
Directory: backend/app/api/
Status: resolved（PR #111，squash 96fefe4，2026-10-12 合入；4 个 E2E 全过、后端全量 385 passed、CI 绿；双轴审查意见当日修复——README 路由表补记、_confirmation_view 提取、银行故障 503 兜底用例零任务副作用）
Blocked by: [v04-task-history-replay/01](01-contract-models.md)、[v04-task-history-replay/02](02-bank-list-challenges.md)
Source issue: Issue #85（https://github.com/DrErwin/hackerthon-bank-agent/issues/85）

## 交付

1. `service.py`：`task_records(identity, task_id)`——`link` 归属校验（越权/不存在一致 404）；确认单从 `api_records(kind='confirmation')` 枚举、以任务归属会话构造 owner 上下文读取（复用既有投影）；验证走网关按任务列举；各自按 (created_at, id) 排序；纯读：不写任务、不写审计、不触发 `verification_fault`。
2. `app.py`：`GET /api/v1/tasks/{task_id}/records` 返回 `TaskRecordsView`（no-store）。
3. `test_app.py` E2E：HR-1 字段完整且无验证码原文；HR-2 幂等；HR-3 过期会话 + re-enter 后回放完整；HR-4 恢复前后挑战都在；HR-5 越权/不存在一致 404；HR-6 读取前后任务快照与 revision 不变。

## 安全口径（请 Ringo 审查）

可见性 = 任务所有者本人（user_id + demo_round_id）；读取身份以任务归属会话构造仅为复用底层 owner 校验，不授予新权力；视图字段沿用既有公共投影（无验证码原文）；保留策略不变（随既有存储）。
