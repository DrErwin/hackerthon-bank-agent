# 05 F37 / F38 记忆查看与删除 HTTP 接口

Ticket ID: v05-observer-seams/05
Package: 无独立交付包——v0.5 平台遗留收口（[spec](../spec.md)），来源 [Issue #216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)
Spec: [v05-observer-seams/spec.md](../spec.md)
Core scenarios: S6
Type: 开发
Owner: Erwin（AI 代行实施与审查，非 Ringo 本人审查）
Directory: `backend/app/api/`
Status: Todo
Blocked by: None（复用 `backend/app/memory/` 已有 `MemoryAdapter.list/delete`）
Source issue: Issue #216

## 交付物

按公共契约 §7.6 接 HTTP（F37/F38 已定义、模块有能力、接口未接）：

1. `GET /api/v1/memories`（F37）→ `{"items": MemoryItem[], "demo_round_id": ID}`；`MemoryItem = {memory_id, version, content, updated_at}`。只用当前身份的用户/会话/轮次调 `runtime.memory.list(MemoryContext(...))`；会话过期按既有 `AUTH_REQUIRED` 401，旧轮次按 `STALE_ROUND` 409。
2. `POST /api/v1/memories/delete`（F38）请求体：`{request_id, memory_ids: list[str] (非空), expected_versions: {memory_id: int}}`；调 `memory.delete(...)`，返回 `{deleted_ids, deleted_at, demo_round_id}`。走既有 `mutation()` 收据：同 `request_id` 重放返回同一结果，指纹冲突 409 `REQUEST_CONFLICT`。
3. 错误映射（只改 `api/app.py` 的 `problem()` 映射表，不改契约枚举）：非本人/他人记忆或索引文件 → 403 `ACCESS_DENIED`；版本过期 → 409 `MEMORY_VERSION_CONFLICT`；旧轮次 → 409 `STALE_ROUND`；非法参数（空列表、重复 id、版本非正）→ 400 `INVALID_ARGUMENT`。
4. 删除行为复用 `MemoryAdapter.delete`：整批校验、同事务删文件 + 写墓碑 + 重建索引 + `memory_deletions` 幂等记录；删除后 F37 不再返回该条，重新加载提示时不再出现（墓碑阻止同内容回灌）。不改 `backend/app/memory/` 目录。

## 验收（HTTP E2E，真实 FastAPI + 真实 store + 预置记忆）

| 编号 | 场景 | 通过条件 |
|---|---|---|
| E01 | 查看 | 预置记忆全部列出，字段与版本正确；只含本人当前轮次；未登录 401 |
| E02 | 删除 | 明确选择 + 正确版本删除成功；F37 不再返回；同 `request_id` 重放返回同结果；新任务上下文索引不含已删内容 |
| E03 | 版本与归属 | 旧版本 → 409 `MEMORY_VERSION_CONFLICT`；别人的 memory_id → 403；空列表/重复 id → 400 |
| E04 | 轮次与会话 | 旧轮次 → 409 `STALE_ROUND`；过期会话 → 401，且不执行删除 |
| E05 | 墓碑 | 删除后用同一内容写回被拒（`validate_memory` 路径与墓碑阻断），索引不变；`memory_deletions` 保留原请求结果 |

## 备注

- 已知限制：契约 §7.6 期望的「工具开始/结果记录所删编号与版本」审计事件受冻结事件类型限制，本票不改契约，登记为缺口；删除的幂等记录与墓碑已可回查。
- 前端记忆管理页不在本票（用户可见页面改动须先经 PM 同意，另开前端票）。
