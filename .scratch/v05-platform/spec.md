# v0.5 平台遗留收口场景规格（v05-platform）

> Status: Confirmed — 2026-10-21 Erwin 指派实施 [Issue #121](https://github.com/DrErwin/hackerthon-bank-agent/issues/121)
> 场景负责人 / Owner：Erwin —— 底座（`backend/app/api/`、`backend/app/audit/`）归 Erwin
> 版本：v0.5（[需求](../../docs/versions/v0.5.0/requirements.md)）；本项为 v0.4 审计出的包外遗留，2026-10-13 PM 决定挂 v0.5、2026-10-20 改为提前实施、2026-10-21 指派当下完成
> 交付包：[v04-platform/packages/01 底座、Agent 与模拟银行](../v04-platform/packages/01-foundation-agent-mockbank.md)（遗留来源；本组只承接 #121，不重开该包）

## 1. 目的

公共契约 §6.7 定义了 F24（导出下载，含 audit 分支）与 §6.8 定义了 F35（`POST /admin/audit/exports`），但 v0.4 平台线只实现了 F21—F24 的 card/details 分支：**审计导出是「契约已定义、没有实现、没有归属票」的裸奔项**（Issue #121）。本规格把它的行为边界、验收和目录归属写死，避免再次掉进账单线与底座之间的缝。

## 2. 事实来源

- [公共契约](../../docs/contracts/公共契约-2026-09-23.md)：§6.7（F21—F24、`ExportView`）、§6.8（F33—F35、`AuditEventSummary/Detail`）、§6.11（`ExportView.task_id` 可空、下载为文件响应）。
- [安全与审计字段附加](../../docs/contracts/安全与审计字段-2026-09-24.md)：`audit.accessed` payload（`action:list/read/export/download`、`filter_ref`、`target_refs`、`export_id`、`permitted`、`reason_code`）。
- 既有实现：[v04-platform/02 导出链路](../v04-platform/issues/02-export-chain.md)（api）、`backend/app/audit/journal.py` 的只读端 `AuditReader`（已具备 JSON 证据包与脱敏/缺失说明）。
- [v0.5 需求](../../docs/versions/v0.5.0/requirements.md)、Issue #121。

## 3. 交付范围（单一实施票 [v05-platform/01](issues/01-audit-export.md)）

1. **F35 `POST /api/v1/admin/audit/exports`**（管理员专用）：输入 `request_id`、`demo_round_id`、`task_id?`；按固定筛选范围生成 JSON 证据包并返回 `ExportView(kind=audit, status=ready)`；缺省 `task_id` 表示整轮范围，带上则只导出该任务范围。导出即冻结，不重复生成。
2. **F24 `GET /exports/{export_id}/download` 的 audit 分支**：下载时重新核验独立管理身份与创建时固定的导出范围，不要求同会话重新验证、不走验证码；未就绪 409；文件编号或链接本身不授权。
3. **留痕**：导出与下载均追加 `audit.accessed` 事件（`export_id` 可回指），读取不调用模型或业务、不产生资金动作。
4. **口径**：`ExportView.task_id` 对审计导出可空（§6.11）；内容复用审计只读端既有脱敏、证据缺失说明与 manifest 哈希；数据源只读 `audit/journal`。

## 4. 验收（E2E，HTTP 边界 + 真实运行时 + 真实审计库）

| 编号 | 场景 | 通过条件 |
|---|---|---|
| A01 | 整轮审计导出 | 管理员创建 → `status=ready`、`kind=audit`、`task_id=null`；下载得到 JSON 证据包（事件、脱敏证据、`manifest` 哈希可复算、缺失说明）；包内可见本次导出的 `audit.accessed(action=export)` 且 `export_id` 回指 |
| A02 | 任务范围导出 | 传 `task_id` 时包内事件全部属于该任务；不传时包含无业务任务的管理事件（如查看留痕） |
| A03 | 权限与范围 | 普通用户调用 F35 → 403；普通用户查看/下载管理导出 → 404；轮次不符、任务不在本轮的 task_id → 403；管理员换会话后仍可下载（审计下载不绑会话） |
| A04 | 冻结与幂等 | 导出后新增审计事件不影响已生成文件，重复下载字节一致；同 `request_id` 重放返回同一导出，不重复生成 |
| A05 | 脱敏与只读 | 验证码等秘密不出现在包内；导出/下载不调用模型、不触达银行业务 |

## 5. 不在范围

- **前端管理页入口**：PM 2026-10-21 决定本次不加（只交后端契约能力，页面可见改动与前端目录都不动）；以后要演示按钮另开前端票。本条如实登记为已知限制。
- F25—F32 管理操作、F37/F38 记忆接口（依赖其他提供方）。
- `evals/security/` 对 F35 的评测登记（归安全线后续同步；本票不改安全评测目录）。

## 6. 已知限制（如实登记，不记作已覆盖）

- **前端入口**：见 §5 第一条。
- **历史轮次 / 跨轮次管理授权**：现状与 F33/F34 一致，只允许管理员当前演示轮次；契约所述「管理授权范围内的历史轮次亦可读取」仍未实现。
- **task-less 访问留痕的读取**：`audit.accessed` 事件不带 `task_id`，因此不能经 F33 任务时间线 / F34 事件详情读取（既有只读口径，本票未改）；整轮 F35 证据包里可见这些事件。
- **同步建包**：F35 在 API 的 `mutation_lock` 内同步生成证据包，轮次历史越大越慢（旧演示库 3636 事件约 12s，期间其他写请求串行等待）；演示规模可接受，未做异步任务。
- **下载拒绝留痕范围**：未命中本人 / 当前轮次范围的下载尝试返回 404 且不写留痕（最小披露）；只有命中已冻结导出行的 409（未就绪）与 403（非管理身份）写 `audit.accessed(download, permitted=false)`。
