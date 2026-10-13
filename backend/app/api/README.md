# api —— 后端服务入口

归属：底座（Erwin）。

票据：[10：任务 API、确认验证与事件流](../../../.scratch/v03-erwin-vertical-backend/issues/10-api-task-stream.md)、[v03-session-recovery-reply/06：API 仅回复接入](../../../.scratch/v03-session-recovery-reply/issues/06-api-reply-only.md)。协议沿用[公共契约 §6](../../../docs/contracts/公共契约-2026-09-23.md)，请求和视图引用 `app.contracts`。本目录负责身份、协议与协调；转账流程、安全规则和银行规则继续由原目录执行。

## 启动与配置

应用工厂为 `app.api.app.create_app(runtime, config)`：传入已有 `TransferRuntime` 和 `ApiConfig` 即可启动。测试使用真实存储、模拟银行、安全门及转账图，仅将模型替换为可重复的测试候选。

部署入口为 `app.api.app:app`。从 `backend/` 运行：

```powershell
# module:function 必须指向服务端受控配置，返回已配置的 TransferRuntime。
$env:BANK_RUNTIME_FACTORY = 'your_bootstrap:build_runtime'
# 从密钥配置载入不少于 32 字节的固定值；重启时保持相同值。
$env:BANK_API_SECRET = '<从服务端密钥配置载入>'
$env:BANK_DEMO_ROUND = 'D1'
$env:BANK_API_ORIGINS = 'http://127.0.0.1:8000,http://localhost:8000'
.venv\Scripts\python -m uvicorn app.api.app:app --host 127.0.0.1 --port 8000 --workers 1
```

工厂配置模型和权限 / 风险回调；API 不提供默认为所有用户放行的配置。当前仓库尚无面向部署的模型与策略组合工厂，需要底座及安全负责人提供该配置。已有嵌入式组合也可直接将工厂返回值传给 `create_app`。缺少工厂或有效签名密钥时启动失败。

普通演示登录固定为配置中的演示用户，不接受 HTTP 传入的用户编号或角色。会话从建立起固定两小时有效，刷新及再次 enter 复用有效会话。登录凭据为签名、HttpOnly、SameSite=Strict Cookie；POST 必须携带受控 Origin。HTTPS 部署设置 `BANK_COOKIE_SECURE=1`，反向代理需保留 Cookie 与 Origin。此版按单 ASGI worker 部署：API 写操作串行检查和推进，Harness 继续提供原任务的跨进程执行锁。

管理身份使用独立 Cookie 容器：服务端配置 `BANK_ADMIN_KEY` 后，以该密钥作为 `X-Demo-Admin-Key` 头调用 enter。普通登录不授予管理权限，已有普通会话不能切换成管理会话。管理密钥不得嵌入普通前端；管理登录由受控管理端配置。

## 前端入口

所有路径前缀为 `/api/v1`。成功为 `{data:T}`，参数错误 400、登录失效 401、权限拒绝 403、本人范围内不存在 404、状态 / 重复请求冲突 409、依赖不可用 503；失败为 `{error:ModuleError}`。请求体验证错误不会回显原始字段。

| 路径 | 用途 |
|---|---|
| POST `/session/enter`、GET `/session` | 建立或读取演示会话 |
| POST / GET `/threads` | 新建对话和查询历史对话 |
| POST / GET `/threads/{id}/messages` | 受理消息，查询完整消息；POST 返回 202 |
| GET `/threads/{id}/events` | SSE，支持 Last-Event-ID 继续持久事件序列 |
| GET `/tasks`、GET `/tasks/{id}` | 原任务快照及待恢复列表 |
| GET `/tasks/{id}/records` | 按任务只读回放确认单与验证历史（本人任务，跨会话可读，不含验证码原文） |
| GET `/reports/{id}` | F21 受控报告卡片：校验本人范围，只返回报告卡内容，不含原始全量明细（v04-platform/01） |
| POST `/reports/{id}/exports`、GET `/exports/{id}`、GET `/exports/{id}/download` | F22—F24 导出链路（v04-platform/02）：卡片导出为普通操作即时就绪；明细导出创建敏感导出任务，须重新完成本次验证（basic_identity 验证码）后生成 CSV；下载核验本人、当前会话与验证授权，未就绪 409 |
| POST `/tasks/{id}/inputs` | 回答当前交互或选择服务端候选 |
| POST `/tasks/{id}/details` | 专用收款人资料、按指定银行字段查询候选；查询本身不选中候选 |
| POST `/tasks/{id}/resume`、`cancel`、`query-result` | 原任务恢复、停止未执行动作及回查原操作 |
| GET `/confirmations/{id}`、POST `/confirmations/{id}/answer` | 读取正式确认卡片、提交绑定版本的确认 |
| GET `/verifications/{id}`、POST `/verifications/{id}/code` | 专用验证视图与验证码提交 |
| POST `/verifications/{id}/resend-code`、`face/start` | 重发及开始模拟人脸等待，不延长中风险原截止时间 |
| GET `/verifications/{id}/demo-code` | 演示提示区专用响应，no-store，禁止进入聊天或日志 |
| POST `/admin/verifications/{id}/face-result` | 管理员回答当前模拟人脸，记录实际操作者和目标用户 |
| GET `/admin/audit/events?task_id=...`、GET `/admin/audit/events/{id}` | 脱敏、只读时间线及证据详情，查看留痕 |

普通消息不批准资金动作；意图判断交给 Harness。任务缺金额时，inputs.text 为人民币元，例如 `500` 或 `500 元`，API 转成契约中的整数分。账户及收款人选项只接受当前交互 / 当前查询产生的编号。资料表单的完整账号不回传聊天、SSE 或请求回执。

POST `/threads/{id}/messages` 在意图理解前返回 202，`MessageAccepted.task_id` 此时为空。API 原子保存用户消息和待处理消息记录，再调用 Harness 的公开 `handle_message()` 结果：`ReplyOnly` 只保存关联为空的助手消息；转账结果才创建 API 任务链接，并通过同一消息历史和 SSE 发布任务状态。普通闲聊、聊天中的“确认”及外部指令不经过 API 关键词规则，也不创建确认或验证入口。

每个 POST 都带 `request_id:UUID`。同用户、轮次、入口同号同内容返回原响应；异内容 409。API 回执只保存 HMAC 比较值和受控响应，不保存验证码明文。验证码另外带 `submission_id`；中断后相同提交通过银行的原记录恢复，不重新理解消息或创建资金动作。其他处理中断的请求不会自动重放，改为查询并显式恢复原任务。消息作业保存稳定的内部候选任务编号；服务重启后，同号重试只恢复这条作业，Harness 已生成转账任务时沿原任务结果补齐 API 关联。

SSE 的 id 为 event_id。先连流，再拉取 messages / tasks 快照；按 event_id 去重，以 task_revision 拒绝更旧状态。新会话恢复前，旧会话的 `task_updated` 和 `interaction_required` 不会重放给当前会话；恢复成功后发布新会话任务状态。游标不存在或属于其他对话返回 409，客户端改用历史与任务补齐。GET 和事件重连不会提交资金。会话到期后停止流，发送 session_expired；后续请求返回 401。

## 验证与交付边界

```powershell
.venv\Scripts\python -m pytest -q app/api/test_app.py
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m pytest -q ../evals/mockbank/test_mockbank_eval.py
```

PR #25 合入时的基线回归为后端 **178 项**（API 29 项）、模拟银行评测 **14 项**；当时的 API 类型检查、Python 语法和文档链接检查也已通过。2026-09-30 补票 01—04 的本地集成 worktree 全后端回归 **204 项通过**（API 32 项）；该次未重跑模拟银行评测或静态类型 / 文档链接检查。票 01—04 双轴 AI 复审均无剩余 P0–P3 代码发现。AI 复审不代表目录负责人决定或 Ringo 真人安全批准。

接口测试覆盖真实低 / 中风险转账、候选和表单、重复请求、旧确认、用户与会话隔离、验证秘密保护、银行已验证但 API 未绑定时重启、任务成功但 HTTP 收据未保存时重启、未启动任务取消、同一任务在新会话查询处理中原操作、API 关联写入中断后的恢复、100 条旧会话控制事件后的 SSE 跨页重放、处理中取消后回查原交易、写前审计故障拒绝、模拟人脸管理权限、只读审计和真实 HTTP SSE 断开重连。实际提供商的模型调用、React 联调及 AF01—AF14 联合验收尚未执行；工程测试不能代替这些验收或真人安全批准。

新会话可从本人当前轮次的原任务入口调用 `POST /tasks/{id}/resume`。API 沿公开 Harness / 转账入口完成会话转换；未提交动作产生当前会话的新确认和所需验证，已有操作只查原 `operation_id`。转换前后任务快照、可用按钮、请求回执与 SSE 使用当前状态；转换前旧会话的确认 / 验证写入口仍拒绝。会话转换标记使 API 请求在存储切换后中断时可用相同 `request_id` 安全续做。其他写入口不会借此放宽跨会话访问。

无业务意图的公开 `ReplyOnly` 结果由 [补票 05](../../../.scratch/v03-session-recovery-reply/issues/05-harness-reply-only.md) 的 Harness 提供；本目录只消费 Harness 结果。`ReplyOnly` 路径不创建 `api_tasks` 记录，也不经过确认、验证或银行入口。~~报告、导出及其他业务的入口不属于本票范围~~：报告读取（F21）已由 [v04-platform/01](../../../.scratch/v04-platform/issues/01-report-storage-read.md) 落地；导出链路（F22—F24）已由 [v04-platform/02](../../../.scratch/v04-platform/issues/02-export-chain.md) 落地，账单任务接线见 v04-platform/04。

导出链路口径（v04-platform/02）：明细导出是平台任务（`api_exports` 行 + `api_tasks`/application 任务 + 银行 basic_identity 挑战），暂停 / 恢复 / 取消沿同一平台任务；验证经既有 F16—F20 端点完成，文件生成在验证通过后惰性触发；明细 CSV 直接取自银行 B08 流水（报告 scope 找回，商户名不打码、账号沿用银行打码），HTML 卡片由导出器转义；会话变化后旧导出授权失效，重新发起须重走验证。验证口径选择（basic_identity 仅验证码、无 operation 绑定、绑定走导出任务）由 PM 于 2026-10-13 代行豁免 Ringo 审批（非本人审查，如实记录）。

重新登录读取旧任务时，当前快照清空不可用的 allowed_actions；非终态任务标记 SESSION_RECONFIRMATION_REQUIRED。保留的 interaction 仅用于历史显示，专用确认 / 验证视图仍拒绝旧会话操作。切换会话后先重新 GET 任务，以当前快照权限为准；SSE 回放中的旧快照不能恢复旧按钮。

公共缺口分别跟踪于 [新会话恢复 #23](https://github.com/DrErwin/hackerthon-bank-agent/issues/23) 与 [无业务意图回复 #24](https://github.com/DrErwin/hackerthon-bank-agent/issues/24)。本票工程增量经独立工程、契约与安全 AI 审查，已按用户授权通过 [PR #25](https://github.com/DrErwin/hackerthon-bank-agent/pull/25) 于 2026-09-30 合入（cd50ebd），合并提交主线 CI 后端 178 项和模拟银行 14 项通过；AI 审查不代表任何真人批准。票 10 验收仍未完成，须补齐依赖缺口与联调证据后更新完成状态；尚不能据此将 v0.3 标为完成。

## 2026-10-01 恢复补票复验

初验发现的初始化与会话转换中断问题已在转账 / Harness 公开入口修复；API 增加三项 HTTP 故障恢复用例，证明首个业务检查点前中断、转换前后中断、再次登录、重启、重复回执、重新确认 / 验证及最终仅一次扣款。最终本地集成快照 8c7a6be 全后端212项（API35项）与模拟银行14项通过，文档链接、语法及差异空白检查通过；Standards / Spec最终AI复审无P0–P3。

存储、转账与Harness分别经PR #30、#31、#32合入；API的当前PR按上述依赖同步最新main并独立运行CI。用户于2026-10-01明确豁免本轮补票01—04的Ringo真人批准门槛并授权合并，AI复审不记为真人批准；该决定不改变长期规则。#23的后端恢复缺口在本票合入及主线验证后关闭；#24仅回复、真实模型、React与AF01—AF14仍待完成。

## 2026-10-01 本轮 API 验证

ticket 06本地回归：完整后端234 passed（168.83秒），API单目录41 passed（116.02秒）；MockBank评测14 passed。Pyright检查app/api/app.py、service.py、store.py为0 errors、0 warnings、0 informations；Python compileall、文档链接检查及差异空白检查通过。用例使用可重复模型候选，不证明真实模型行为或React联调。Draft [PR #37](https://github.com/DrErwin/hackerthon-bank-agent/pull/37)以main为基线，Repository checks已通过（[CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36812809932)）；Standards / Spec双轴独立AI复审均无发现，不代表真人批准。

## 补票06验收修复（2026-10-01）

未开始的消息在同用户、同轮次重新登录后，以当前会话继续原请求；已有转账任务只补齐原关联，并通过专用恢复入口重新确认。仅回复结果在发布前单独持久化，发布中断后复用原回复。运行中断且没有可恢复任务或已保存回复时，发出受控错误并结束原作业，请用户重新发起；不重新调用模型将闲聊改判为转账。


修复票 `v03-transfer-eval-fixes/04` 的F36接线：手工资料先由平台受控登记核验，使用服务端任务修订号生成资料版本，仅将任务绑定引用传给图；完整资料不进入resume/checkpoint写入、去重响应或SSE事件。公开F36字段保持现有语义，错误户名明确返回PAYEE_MISMATCH、原任务继续等待可纠正资料。Depends on PR #52/#54。隔离组合基线6d53860 + API工作区改动的真实HTTP2项通过：同request幂等、刷新/重建后确认与验证成功、500元单笔结果、错误户名同任务纠正、HTTP/历史/普通库表秘密扫描。用户已明确放宽本次第三层Draft限制；本票独立Draft交付，真人安全审查及合入仍待。

追加真实HTTP测试3通过：受控资料修改金额后新操作/新确认，旧交互和旧确认拒绝，跨用户F36拒绝且不泄漏，银行流水零。原两项重启/成功证据保留。
修复票 `v03-transfer-eval-fixes/08`：验证码/重发/人脸写入的技术异常发布同任务needs_attention快照，不保留旧确认/验证提示冒充可继续。快照仅保存原challenge/submission/method引用，错误不含异常原文；银行错误次数不由API增加。未知结果只允许按原提交重传，不通过通用resume推进或换新submission重做；同HTTP请求的503可按原HMAC指纹与银行submission幂等恢复。银行已经保存结果但API未绑定的重传仍读原事实。基础过期重发交给银行裁定，不在API复制规则，组合依赖05的银行修复。定向2项真实故障测试与12项直接相关回归共14通过；全体生命周期/故障恢复组合及真人安全审查仍待。
