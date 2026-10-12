# v0.4 确认与验证历史只读回放规格（v04-task-history-replay）

Status: resolved（后端交付合入：PR #109 契约 / PR #110 银行列举 + #112 副作用收紧 / PR #111 端点，2026-10-12；前端重建回放与组件测试移交 #89）
Owner: Erwin（PM 自拆，不开交付包）
Source issue: [Issue #85](https://github.com/DrErwin/hackerthon-bank-agent/issues/85)（缺少按任务查询确认与验证历史的只读公共接口）
Deadline: 不晚于 2026-10-15（前端线 #89 依据本能力重建刷新后回放）

## Problem Statement

任务完成后刷新页面，前端的确认单与验证记录无法重建：公共 API 没有「按任务列出历史确认单与验证记录」的只读接口，只读回放只在前端页面生命周期内保留，刷新即丢失（边界由前端 PR #81 声明）。银发用户回看一笔已完成或中断的转账时，看不到当时的确认单与验证过程；恢复场景也缺确认/验证历史口径。

## Solution

底座提供 `GET /api/v1/tasks/{task_id}/records` 只读端点：按任务标识返回该任务的确认单视图列表与验证挑战视图列表，复用既有 `ConfirmationView` / `VerificationView` 公共投影（无验证码原文、无任何秘密）。授权口径 = 任务所有者本人（user_id + demo_round_id 归属），越权与不存在对象一致 404。读取身份用任务归属会话构造以复用安全存储与银行的既有 owner 校验；银行侧新增按任务只读列举验证挑战的能力（不看会话，按 user + demo_round + task 归属），不动 `_in_scope` 的进行中挑战口径。不改动确认/验证写入语义、执行与安全规则、审计事实。

## Core Scenarios（测试覆盖框架）

| 编号 | 场景 | 覆盖方式 |
|---|---|---|
| HR-1 | 任务所有者按任务取回确认单（状态、金额、收款人、转出账户、时间，经 display_fields 与 decision/created_at）与验证记录（challenge_status、code_result、face_result），响应不含验证码原文 | API E2E（真银行 + 安全门 + 转账图） |
| HR-2 | 同一会话内刷新后按任务重建回放（同一端点幂等只读） | API E2E |
| HR-3 | 会话过期、重新进入（新会话）后，本人仍能回看已完成/中断任务的历史 | API E2E（过期 session + re-enter） |
| HR-4 | 任务经新会话恢复后，恢复前（旧会话）与恢复后的验证挑战都在回放列表 | API E2E（session 恢复流程） |
| HR-5 | 非任务所有者与不存在的任务同样 404（一致拒绝，不泄露存在性） | API E2E |
| HR-6 | 回放只读零副作用：不改变任务状态与 task_revision、不写审计、不改动确认/验证存储语义 | API E2E + 代码路径复核 |

契约模型（`TaskRecordsView`、`VerificationView.created_at`）用契约目录模型测试覆盖；银行侧按任务列举（票02）先列失败方式再做隔离测试（E2E 为最终验收）。

## User Stories

1. 作为银发用户，我回看昨天办完的转账，能看到当时的确认单（金额、收款人、转出账户、时间与最终状态）和验证过程（挑战状态与结果），确认「我批准过什么」。
2. 作为用户，我刷新页面或第二天再打开，回放依然完整，不需要重新办理。
3. 作为任务所有者，别人（其他演示用户）看不到我的确认与验证历史；查一个不存在的任务与查别人的任务返回同样的错误。
4. 作为前端（#89 工作线），我用公共契约生成的类型调用一个只读接口即可重建回放，不解析 SSE 历史、不复制契约。
5. 作为安全审查者（Ringo），我确认回放只有任务所有者可读、视图无验证码原文或秘密、不改变确认门的执行与安全规则。
6. 作为调试人员，我确认回放是纯读：不改任务状态、不写审计事实。

## Implementation Decisions

- **归属与授权**：端点先按当前身份对任务做归属校验（既有 `link`，user_id + demo_round_id，不比对会话），失败一律 404；通过后用**任务归属会话**（`api_tasks.session_id`）构造只读身份传递给安全存储/银行读取，复用其 owner 校验，不授予当前会话任何新权力。
- **确认单来源**：`api_records(kind='confirmation')` 枚举 + 安全存储既有读取（同任务确认单按版本原地改写，历史即最终状态；pending 惰性过期与单条端点口径一致）。
- **验证来源**：银行新增按任务只读列举（user + demo_round + task 归属，不看会话；pending 惰性终态化与 `get_verification` 一致），覆盖跨会话恢复前后的全部挑战；网关加对应只读方法。
- **契约**：`VerificationView` 新增 `created_at`（轻量确认档：新增字段，旧调用有效）；新增 `TaskRecordsView`（api.py）。前端类型生成（`generate_contract_schema.py` 的 PUBLIC_MODELS 登记）归 `frontend/` 工作线在接入时执行。
- **排序**：确认单按 `(created_at, confirmation_id)`、验证按 `(created_at, challenge_id)`，时间线稳定。
- **目录边界**：票01 `backend/app/contracts/`、票02 `backend/app/services/`、票03 `backend/app/api/`，一票一分支一 PR。不触碰 `backend/app/security/`（Ringo）；安全口径（谁可见、是否含验证细节）在 PR 中请 Ringo 审查，本规格不预设。
- 契约变更按第 8 章轻量确认档记录于 PR：为什么改、前后、影响方、旧调用仍可用。

## Testing Decisions

- E2E 为最终验收（AGENTS 规则）：`backend/app/api/test_app.py` 模式，真实 TransferRuntime + 模拟银行，断言外部行为（响应字段、状态码、零副作用），不断言内部拼装。
- 票02 属隔离测试：先写全部失败方式（见票文），再写代码；断言银行侧归属与完整性。
- 契约模型测试在 `contracts/test_contracts.py` 既有模式内追加。
- 不新增评测基建；evals 不动。

## Out of Scope

- 前端回放界面与组件测试（归 `frontend/`，#89 工作线接入时交付）。
- 确认门执行、验证流程、权限与资金安全规则的任何语义变化。
- `backend/app/security/` 目录改动；审计事实与写入语义。
- SSE 事件回放改造、账单/联动场景扩展。

## Tickets

- [v04-task-history-replay/01：公共契约只读回放模型](issues/01-contract-models.md)——resolved（PR #109）
- [v04-task-history-replay/02：银行按任务只读列举验证挑战](issues/02-bank-list-challenges.md)——resolved（PR #110 + 审查修复 PR #112）
- [v04-task-history-replay/03：按任务只读回放端点](issues/03-api-records-endpoint.md)——resolved（PR #111）

## Further Notes

- 2026-10-12 建组。通用 Skill（to-spec / to-tickets / implement）在本会话不可用（非 mattpocock skills 环境，亦无安装工具），按 delivery-workflow §3 的失败报告要求在此记录；spec 与票据按其固定结构手工产出，代码审查用本会话可用的 `code-review` 双轴流程。
- 现状依据：`api_records` 已按 (kind, record_id, task_id) 登记确认/验证记录但无按任务列出入口；确认单同任务按版本原地改写（session 随最新版本更新）；验证挑战按会话归属且跨会话恢复会新建挑战（旧挑战保留），因此验证列举必须按任务而非当前会话。
- **实施结果（2026-10-12 当日建组并收口）**：三票三目录三 PR 全部合入——PR #109（契约，`TaskRecordsView` + `VerificationView.created_at`，轻量确认档已在公共契约 §6.5 登记 F39）、PR #110（银行 `list_task_challenges` + 网关 `list_verifications`）、PR #111（`GET /tasks/{task_id}/records` + `_owner_security_context` 复用 + 4 个 E2E）。双轴 AI 审查（Standards/Spec）发现并在当日修复：PR #111 内补 README 路由表、`_confirmation_view` 提取、银行故障 503 兜底用例（零任务副作用）；PR #112 收紧 `_expire` 只终态化本任务挑战（他人 pending 不因回放被改写）。测试：契约 44、services 39、后端全量 385（本机无 langchain，按既有口径排除 2 个真模型模块）、CI 全绿。**遗留（移交 #89 前端线）**：`generate_contract_schema.py` PUBLIC_MODELS 登记 + `api.generated.ts` 重生成、刷新后回放界面与组件测试；安全口径（谁可见/是否含验证细节）已在 PR #111 请 Ringo 审查，Ringo 本人复核仍待（记录为待审，非本人签署）。
