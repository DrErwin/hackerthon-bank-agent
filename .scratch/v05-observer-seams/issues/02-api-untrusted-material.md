# 02 资料投递 HTTP 通路：消息携带受控外部资料

Ticket ID: v05-observer-seams/02
Package: 无独立交付包——v0.5 平台遗留收口（[spec](../spec.md)），来源 [Issue #216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)
Spec: [v05-observer-seams/spec.md](../spec.md)
Core scenarios: S1、S2
Type: 开发
Owner: Erwin（AI 代行实施与审查，非真人审查）
Directory: `backend/app/api/`
Status: Done
Blocked by: [v05-observer-seams/01 不可信数据接缝](01-untrusted-data-seam.md)
Source issue: Issue #216

## 交付物

1. `POST /api/v1/threads/{thread_id}/messages` 的请求体在 `api/app.py` 内用**本地子类**扩展（不动 `backend/app/contracts/`）：

```python
class MessageRequest(SendMessageRequest):
    untrusted_content: str | None = Field(default=None, max_length=8000)
```

- `untrusted_content` 可选；与 `text` 一起提交。`text` 仍是用户本轮问题（如「这条短信是真的吗」），`untrusted_content` 是被粘贴的外部资料。
- 资料在进入存储 / 模型 / SSE 前必须脱敏（复用 `safe_text` 之外的独立路径：`redact(..., free_text=True)`，只做秘密与个人数据替换，**不**因为出现「验证码」而拒绝整条消息）；空串按 None 处理；超长 400 拒绝 `INVALID_ARGUMENT`。

2. 消息任务落库：`api_message_jobs` 增加 `untrusted_content` 列（`ApiStore` 启动时 `PRAGMA table_info` 检查后 `ALTER TABLE ... ADD COLUMN`，旧演示库兼容）；`enqueue_message_job` / `message_job` 读写该列；重放（同 `request_id`）返回同一 job 且资料不重复入库。

3. `ApiService.process_message_job` 调用 `harness.handle_message(..., untrusted_content=job["untrusted_content"])`；`ReplyOnly` 回复照既有 `save_message_reply` 发布。崩溃重试走既有 job 语义，不重复调用模型。

4. 契约登记：在 `docs/contracts/公共契约-2026-09-23.md` §8 变更记录追加一条「兼容扩展：F11 消息请求可选 `untrusted_content`，仅作为外部资料投递，不改变消息语义与鉴权」，并在 PR 描述写「场景 S1/S2、依赖 PR #（票 01）、触及契约（兼容扩展）/安全（外部内容按数据处理）」。

## 验收（HTTP E2E，真实 FastAPI + 真实存储 + 替身规划器）

| 编号 | 场景 | 通过条件 |
|---|---|---|
| B01 | 正常投递 | 202 接受；job 落库；规划器收到脱敏后的资料；回复作为 assistant 消息与 SSE `message_completed` 出现；零任务、零资金（当规划器返回 reply_only） |
| B02 | 依赖票 01 的确定性门 | 资料含注入语句、规划器替身故意返回 `TransferProposal`；接口仍返回固定只读回复，`GET /api/v1/tasks` 无新任务，零 `tool.started` |
| B03 | 脱敏边界 | 资料里的验证码值、完整账号、手机号在数据库 `api_message_jobs` / 消息 / SSE 中都不出现（用已知值搜索断言） |
| B04 | 幂等与校验 | 同 `request_id` 重放返回同一结果且不重复调用规划器；超过 8000 字符或非字符串 → 400 `INVALID_ARGUMENT`；资料与 `text` 均空 → 400 |
| B05 | 旧行为不回退 | 不带 `untrusted_content` 的消息行为与既有 `test_app.py` 用例一致 |

## 备注

- 前端入口不在本票：粘贴框属于用户可见页面改动，须先经 PM 同意并另开前端票；本票只交 API 能力并如实登记。
- 不打印、不提交 `.env.local-demo.json`。

## Comments

- **2026-10-22 交付**：[PR #220](https://github.com/DrErwin/hackerthon-bank-agent/pull/220) squash `ad2d4f7` 已合入（Depends on PR #219）。`MessageRequest.untrusted_content`（≤8000）+ 独立脱敏路径 + `api_message_jobs` 加列（旧库 ALTER）+ Harness 条件传参；契约 §8 追加一条兼容扩展。验证：B01-B05 6 passed（无 skip）；api 目录 117 passed；CI 绿。已知限制：资料只走消息 job 新请求路径；用户消息气泡只回显 `text`。
