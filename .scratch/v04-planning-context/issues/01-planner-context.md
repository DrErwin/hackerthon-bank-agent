# v04-planning-context/01：规划入口上下文实现

Ticket ID: v04-planning-context/01
Package: PM 自拆（不开交付包）；Source issue [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)
Spec: [v04-planning-context 规格链接](../spec.md)
Core scenarios: SEC-C-001（聊天同意与模糊回答均不代替按钮）· TF-CNF-03[嗯]（共享轮）——修复目标为回答与待办一致且仍不构成批准
Verification: ① `python -m pytest -q app/agent_platform/`（backend/ 下）全绿；② 定向复现：等待确认时输入「嗯/确认/快多久」，回答引用当前待办、不否认业务、确认单仍待按钮、银行零写；③ 若采用受控注入方向：秘密扫描确认原始消息与秘密不落盘、不入审计长期存储
Owner: Erwin
Directory: backend/app/agent_platform/
Status: open
Blocked by: None
Source issue: [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)

## 任务

按[规格候选方向](../spec.md#候选方向issue-84-已登记本规格不指定实现票内定稿)定稿并实现其一（或组合）：

1. 确定性层短路——确认/验证等待期的固定话术走确定性分支，不依赖模型；
2. 受控上下文注入——结构化待办摘要（非原始消息）+ 固定会话 checkpoint_ns。

## 实现要点

- 根因位置：`model.py` `DeepAgentPlanner.select`——只传当前一条消息、`checkpoint_ns=f"harness-{uuid4()}"` 随机且不挂 checkpointer（有意设计：规划期原始消息可能含秘密）、业务状态不注入。
- 方向 2 的秘密边界口径（哪些结构化字段可进规划上下文）先取得 Ringo 确认，或 PM 代行并如实记录；方向 1 不改变模型路径，优先评估其覆盖面是否足够（仅固定话术场景 vs 更广的等待期应答）。
- 方案若改变公开行为/字段（尤其确定性短路的对外回复形态）：先判断是否触及公共契约或 API 契约，触及则先走契约变更流程，另开票实现 `contracts/` 或 `api/` 改动，不混入本票 PR。
- 涉及 `memory/`（上下文存储）或 `modules/transfer/`（受控待办摘要来源）的接缝改动：登记依赖，需要改动的部分另开票，本票只落 `agent_platform/`。

## 完成判据

- Verification 三项全部满足并有证据；
- 分支 rebase 最新 `origin/main`，PR 合入（squash），CI 通过；
- 本票完成不等于 Issue #84 关闭——复验与移交见 [02 票](02-live-retest-handoff.md)。
