# v04-planning-context/05：评测缝适配规划上下文（RecordingPlanner）

Ticket ID: v04-planning-context/05
Package: PM 自拆（不开交付包）；Source issue [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)
Spec: [v04-planning-context 规格](../spec.md)
Core scenarios: SEC-C-001 变体与 TF-CNF-03[嗯] 的真实运行复验（02 票）被本缺陷阻塞
Verification: `evals/transfer` 侧用例断言上下文转发；离线安全入口 `SEC-C-001/v01` 从「规划器只调用 1 次、断言 Failed」回到「调用 2 次、解释待评定（Blocked）」
Owner: Erwin
Directory: `evals/transfer/`
Status: done（2026-10-12 实现并合入，PR [#104](https://github.com/DrErwin/hackerthon-bank-agent/pull/104)，squash `2e5a9e8`；评测侧用例 + 离线对拍 + 02 票真跑复验均通过）
Blocked by: None
Source issue: [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)

## 问题（02 票复验时实测）

01 票（PR #96）把规划接口改为：**存在待办上下文时**多传一个关键字 `context_summary=`（[harness.py:236](../../../backend/app/agent_platform/harness.py)）。仓库内的测试替身都随之更新了，但评测缝 [environment.py](../../transfer/environment.py) 的 `RecordingPlanner.select` 仍是五参签名：

- 第二轮（正是「等待期聊天应答」这一待修场景）调用时直接 `TypeError`，规划记录停在 1 条；
- 实测：离线 `SEC-C-001/v01` 报 `Failed: confirmation.fixed_offline_reply_only`；真实模型 18 轮里 15 Failed / 3 Blocked；功能侧 `TF-CNF-03[嗯]` 三轮虽 Passed，但「嗯」轮同样没进模型；
- 更关键：`RecordingPlanner` 是真实模型的**外层缝**，即便它自己不报错，也必须把 `context_summary` 透传给 delegate，否则真实模型永远看不到待办上下文，复验会变成假通过。

同一类问题在 `backend/app/api/test_app.py` 的规划器替身也存在（另立 [06 票](06-api-planner-double.md)）。

## 任务

1. `RecordingPlanner.select` 增可选 `context_summary=None`；有 delegate 时按 harness 同一约定**条件透传**（仅在非 None 时传关键字，保持旧 delegate 可用）。
2. 补一条评测侧用例：delegate 收到的 `context_summary` 与传入一致；旧签名调用（不带该关键字）仍照常工作。
3. 离线入口回归：`SEC-C-001/v01` 单轮从 Failed 回到 Blocked（规划调用 2 次、解释待评定）。

## 实现要点

- 只改评测缝签名与透传，不动 harness、模型与安全语义；离线固定回复文本不改（§4.4 只判真实模型轮）。
- 透传必须条件化：delegate 可能是旧的五参替身，无条件透传会把同一个坑挪到下一层。

## Acceptance criteria

- [x] `RecordingPlanner` 接受 `context_summary` 并在有 delegate 时条件透传
- [x] 评测侧用例固定该转发行为，且不带关键字时仍可用
- [x] 离线 `SEC-C-001/v01` 单轮：规划调用 2 次、断言无 Failed、解释缺口以 Blocked 保留
- [x] `evals/transfer` 既有用例全绿；PR 合入、CI 通过
- [x] 完成后 02 票可重跑真跑复验（2026-10-12 完成：18 轮 0 Failed、§4.4 全符合）
