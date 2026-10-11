# v04-planning-context/01：受控上下文基线（历史与待办摘要注入）

Ticket ID: v04-planning-context/01
Package: PM 自拆（不开交付包）；Source issue [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)
Spec: [v04-planning-context 规格链接](../spec.md)
Core scenarios: SEC-C-001（聊天同意与模糊回答均不代替按钮）· TF-CNF-03[嗯]（共享轮）——修复目标：回答与待办一致且仍不构成批准
Verification: ① `python -m pytest -q app/agent_platform/`（backend/ 下）全绿；② 定向复现（离线缝，scripted 工厂驱动 harness）：等待确认时输入「嗯/确认/快多久/我刚才已经同意了」，回复引用当前待办、不否认业务、确认单仍待按钮、银行零写；③ 秘密检查：注入仅结构化摘要，原始消息与秘密不落长期存储、不入审计正文
Owner: Erwin
Directory: backend/app/agent_platform/
Status: open
Blocked by: None（可立即开始）
Source issue: [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)

## What to build

等待确认/验证期间的用户应答（确认、催促、模糊回复、引用前文）得到与当前待办一致、结合最近对话历史的回答——端到端效果：页面显示待确认单时，无论用户怎么应答，助理不再答非所问或否认业务，聊天仍不构成批准。这是用户 2026-10-10 拍板的必做基线。

## 实现要点

- 根因位置：`model.py` `DeepAgentPlanner.select`——只传当前一条消息、`checkpoint_ns=f"harness-{uuid4()}"` 随机且不挂 checkpointer（有意设计：规划期原始消息可能含秘密）、业务状态不注入。
- 注入**结构化摘要**（最近对话要点 + 当前待确认单要点 + 验证状态），不是原始消息；`checkpoint_ns` 改为稳定会话标识。规划期不持久化原始模型消息的原则保持。
- 秘密口径（哪些结构化字段可进规划上下文）开工前取得 Ringo 确认，或 PM 代行并如实记录。
- 接缝纪律：需要动 `memory/`（摘要存储）、`modules/transfer/`（待办摘要来源）时登记依赖另开票；本票只落 `agent_platform/`。

## Acceptance criteria

- [ ] 离线定向复现四类应答全部与待办一致、不否认业务、零资金副作用
- [ ] pytest 全绿；秘密检查通过（无原始消息/秘密落盘）
- [ ] 分支 rebase 最新 `origin/main`、PR 合入（squash）、CI 通过
- [ ] 完成后 [02 复验票](02-live-retest-handoff.md)解除阻塞；本票完成不等于关 issue
