# api —— 后端服务入口

归属：底座（Erwin）。

票据：[10：任务 API、确认验证与事件流](../../../.scratch/v03-erwin-vertical-backend/issues/10-api-task-stream.md)。协议沿用[公共契约 §6](../../../docs/contracts/公共契约-2026-09-23.md)，请求和视图引用 `app.contracts`。本目录负责身份、协议与协调；转账流程、安全规则和银行规则继续由原目录执行。

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

每个 POST 都带 `request_id:UUID`。同用户、轮次、入口同号同内容返回原响应；异内容 409。API 回执只保存 HMAC 比较值和受控响应，不保存验证码明文。验证码另外带 `submission_id`；中断后相同提交通过银行的原记录恢复，不重新理解消息或创建资金动作。其他处理中断的请求不会自动重放，改为查询并显式恢复原任务。

SSE 的 id 为 event_id。先连流，再拉取 messages / tasks 快照；按 event_id 去重，以 task_revision 拒绝更旧状态。游标不存在或属于其他对话返回 409，客户端改用历史与任务补齐。GET 和事件重连不会提交资金。会话到期后停止流，发送 session_expired；后续请求返回 401。

## 验证与交付边界

```powershell
.venv\Scripts\python -m pytest -q app/api/test_app.py
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m pytest -q ../evals/mockbank/test_mockbank_eval.py
```

2026-09-30 本分支完整后端回归 **178 项通过**（其中 API 29 项），模拟银行评测另 **14 项通过**；API 类型检查、Python 语法和文档链接检查通过。两位 AI 分别审查规范与票据，修复意见复查后无新增可执行问题。

接口测试覆盖真实低 / 中风险转账、候选和表单、重复请求、旧确认、用户与会话隔离、验证秘密保护、银行已验证但 API 未绑定时重启、任务成功但 HTTP 收据未保存时重启、未启动任务取消、处理中取消后回查原交易、写前审计故障拒绝、模拟人脸管理权限、只读审计和真实 HTTP SSE 断开重连。实际提供商的模型调用、React 联调及 AF01—AF14 联合验收尚未执行；工程测试不能代替这些验收或真人安全批准。

已确认的公共能力缺口：当前 Harness 和转账公开入口绑定原 session_id，不支持把旧检查点迁移到重新登录后的新会话。新会话能读取本人当前轮次历史，继续旧任务返回 409 `SESSION_RECONFIRMATION_REQUIRED`；不能冒用过期会话沿用确认 / 验证。需另建底座恢复票，提供“重新确认、重新验证、已提交动作仅回查”的公开协调能力，再接入 API。API 不改写其他目录的任务或检查点来绕过这一限制。

当前 Harness 的模型入口也只有普通转账候选，没有无业务意图时仅回复的公开结果类型；API 不自行写意图规则来补齐普通闲聊。相关能力需要底座另票提供。报告、导出及其他业务的入口不属于本票范围。

重新登录读取旧任务时，当前快照清空不可用的 allowed_actions；非终态任务标记 SESSION_RECONFIRMATION_REQUIRED。保留的 interaction 仅用于历史显示，专用确认 / 验证视图仍拒绝旧会话操作。切换会话后先重新 GET 任务，以当前快照权限为准；SSE 回放中的旧快照不能恢复旧按钮。

公共缺口分别跟踪于 [新会话恢复 #23](https://github.com/DrErwin/hackerthon-bank-agent/issues/23) 与 [无业务意图回复 #24](https://github.com/DrErwin/hackerthon-bank-agent/issues/24)。本票工程增量经独立工程、契约与安全 AI 审查，按用户本次授权推进有限增量合入；AI 审查不代表任何真人批准。票 10 验收仍未完成，须补齐依赖缺口与联调证据后更新完成状态；尚不能据此将 v0.3 标为完成。
