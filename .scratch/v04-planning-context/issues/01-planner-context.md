# v04-planning-context/01：受控上下文基线（历史与待办摘要注入）

Ticket ID: v04-planning-context/01
Package: PM 自拆（不开交付包）；Source issue [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)
Spec: [v04-planning-context 规格链接](../spec.md)
Core scenarios: SEC-C-001（聊天同意与模糊回答均不代替按钮）· TF-CNF-03[嗯]（共享轮）——修复目标：回答与待办一致且仍不构成批准
Verification: ① `python -m pytest -q app/agent_platform/`（backend/ 下）全绿；② 定向复现（离线缝，scripted 工厂驱动 harness）：等待确认时输入「嗯/确认/快多久/我刚才已经同意了」，回复引用当前待办、不否认业务、确认单仍待按钮、银行零写；③ 秘密检查：注入仅结构化摘要，原始消息与秘密不落长期存储、不入审计正文
Owner: Erwin
Directory: backend/app/agent_platform/
Status: resolved（PR #96 合入 2026-10-12；前置 PR #95 storage）
Blocked by: None（已开始并完成）
Source issue: [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)

## What to build

等待确认/验证期间的用户应答（确认、催促、模糊回复、引用前文）得到与当前待办一致、结合最近对话历史的回答——端到端效果：页面显示待确认单时，无论用户怎么应答，助理不再答非所问或否认业务，聊天仍不构成批准。这是用户 2026-10-10 拍板的必做基线。

## 实现要点

- 根因位置：`model.py` `DeepAgentPlanner.select`——只传当前一条消息、`checkpoint_ns=f"harness-{uuid4()}"` 随机且不挂 checkpointer（有意设计：规划期原始消息可能含秘密）、业务状态不注入。
- 注入**受控摘要**（当前待办状态要点 + 该业务的原请求文本，经 `redact(free_text=True)` 打码），不是原始模型消息。
- **实现修正**：`checkpoint_ns` 保持每次随机——规划 backend 为 `StateBackend` 且每次调用新建，稳定 ns 无实际效果；反而在将来误挂持久 checkpointer 时会让原始消息落盘，故不改（规格 Further Notes 已记录）。
- 秘密口径以 PM 代行记录为准（注入字段清单见[规格 Implementation Decisions](../spec.md)），Ringo 可复核。
- 接缝纪律：本次新增 storage 前置方法单独成票（[04 票](04-storage-session-tasks.md)，PR #95 独立目录合入），本票只落 `agent_platform/`。

## Acceptance criteria

- [x] 离线定向复现四类应答全部与待办一致、不否认业务、零资金副作用（test_planning_context.py 7 例）
- [x] pytest 全绿（agent_platform 113/113、api 57/57、后端全量 357/357）；秘密检查通过（仅打码摘要，无原始消息落盘）
- [x] 分支 rebase 最新 `origin/main`、PR 合入（squash）、CI 通过（PR #95/#96 Repository checks 绿）
- [x] [02 复验票](02-live-retest-handoff.md)解除阻塞（2026-10-12）

## 完成证据（2026-10-11 实现，2026-10-12 合入）

- **PR #96**（`agent_platform`）：harness `_session_context_summary` 生成受控摘要，`_select_outcome` 条件传参（兼容旧五参 planner）；`Planner`/`DeepAgentPlanner.select` 增可选 `context_summary`，注入系统提示「当前会话背景」段并声明非用户指令。
- **PR #95**（`storage`，前置）：`list_session_tasks` 按会话列任务（活跃优先、会话转换归属新会话）。
- 双轴 code-review：Standards 0 硬违规（双调用分支按建议合并为单调用点）；Spec 差距两条——「最近对话」半边待 api 接缝、「稳定 checkpoint_ns」按代码事实修正，均登记于规格。
- 定向复现为**输入侧**证据（模型能看见待办）；**回复质量**以真实模型复验为准 → [02 票](02-live-retest-handoff.md)。
