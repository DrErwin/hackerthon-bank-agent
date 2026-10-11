# v04-planning-context/06：API 测试替身适配规划上下文

Ticket ID: v04-planning-context/06
Package: PM 自拆（不开交付包）；Source issue [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)
Spec: [v04-planning-context 规格](../spec.md)
Core scenarios: 等待确认期聊天应答（User Story 1/2/3）在 API 层的回归守卫
Verification: `python -m pytest -q app/api/`（backend/ 下）全绿；`test_message_retries_and_plain_chat_assent_never_duplicate_business` 断言应答轮真的产生了引用待办的回复，且不再出现 `stream_error`
Owner: Erwin
Directory: `backend/app/api/`
Status: done（2026-10-12 实现并合入，PR [#105](https://github.com/DrErwin/hackerthon-bank-agent/pull/105)，squash `b823c7a`；`app/api/` 58 passed、CI 绿、只读审查后按意见收紧替身分支与断言）
Blocked by: None
Source issue: [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)

## 问题（05 票同源，02 票复验时实测）

`test_app.py` 的规划器替身 `Planner.select` 是五参签名；而有等待中业务时 harness 会多传 `context_summary=`。实测（探针复现）：

- 先发「给妈妈转 500 元」→ 任务 `waiting_approval`；再发「确认」→ 该轮以 `stream_error`（`DEPENDENCY_UNAVAILABLE`）结束，`planner.calls` 停在 1；
- 现有用例 `test_message_retries_and_plain_chat_assent_never_duplicate_business` **看的是 task_id 与既有任务状态**，恰好漏掉这一轮的失败——即 #84 的 API 层回归守卫目前是空的。

生产路径不受影响（`DeepAgentPlanner` 接受该关键字），但测试替身与任何注入式规划器会踩同一个坑。

## 任务

1. `test_app.py` 的规划器替身 `select` 增可选 `context_summary=None`（与 harness 约定一致；替身不需要用它，但必须能接收）。
2. 强化上述用例的断言：应答轮要有**助手侧回复**（`api_message_replies` 或事件里的 `message_completed`），且**不得出现 `stream_error`**；回复文本仍不得产生资金动作（既有断言保留）。
3. 不改生产代码路径与安全语义。

## Acceptance criteria

- [x] 规划器替身接受 `context_summary`；`app/api/` 全部用例通过
- [x] 用例断言应答轮产生助手回复且无 `stream_error`（修签名前的探针即 `stream_error DEPENDENCY_UNAVAILABLE`、`planner.calls=1`，新断言在该状态下必红）
- [x] 后端全量无回归；PR 合入、CI 通过
