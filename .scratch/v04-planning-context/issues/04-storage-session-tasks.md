# v04-planning-context/04：会话任务列表（storage 前置）

Ticket ID: v04-planning-context/04
Package: PM 自拆（不开交付包）；Source issue [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)
Spec: [v04-planning-context 规格链接](../spec.md)
Core scenarios: 支撑 [01 票](01-planner-context.md)受控摘要的数据源（无独立业务场景；不做此票则规划看不见待办）
Verification: `python -m pytest -q app/storage/test_storage.py` 全绿（新增 2 例：活跃优先排序与会话隔离、会话转换后归属新会话）；PR #95 CI 通过
Owner: Erwin
Directory: backend/app/storage/
Status: resolved（PR #95 合入 2026-10-11）
Blocked by: None
Source issue: [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)

## What to build

`ApplicationStore.list_session_tasks(user_id, demo_round_id, session_id)`：按会话返回任务列表，非终态在前、创建顺序最新在前；会话转换（恢复场景）后的任务归属新会话。纯新增只读方法，不改表结构、不改写入路径。

## 完成证据

- PR #95（squash `f5c92ae`）：`application.py` +17 行、`test_storage.py` +26 行；CI Repository checks 通过。
- 独立目录提交，未与 [01 票](01-planner-context.md)的 `agent_platform/` 改动混票（一票一目录）。
