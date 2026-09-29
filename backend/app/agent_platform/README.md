# agent_platform —— Agent 平台（Harness 层）

归属：底座（Erwin）。本目录只接公开能力，不访问转账私有工具或银行规则。

`DeepAgentPlanner` 使用 Deep Agents 处理自然语言，但模型只看见 `propose_transfer`：它只能提出收款人、金额与账户候选，不能执行银行动作。模型和配置版本由调用方以 `ModelSettings` 提供；切换模型只替换这一配置。其他内置工具及通用子 Agent 在此入口关闭。无效、多次或缺失的候选会被拒绝，可信身份、任务编号与请求编号从服务端传入。

`CapabilityRegistry` 只登记清单中的 `transfer.start_transfer`。`AgentHarness` 需要已建立的用户会话、`ApplicationStore`、`MemoryAdapter`、`AuditJournal`、公开能力工厂和权限判定回调。工厂收到当前可信上下文及任务专属的持久检查点，返回实现 `start` / `resume` 的公开入口。应用必须在工厂中把当前 `run_id` 交给安全上下文，并完成转账模块 README 要求的当前动作校验与银行授权回调；Harness 本身不构造私有银行工具。

首次请求记录模型输入、候选输出和任务状态；恢复沿原 `task_id` 与检查点继续，使用新的 `run_id`，不重新调用模型。`RunTrace` 保留同一 `trace_id` 并按每次运行排序；安全、私有工具与银行事件的实际写入仍须由集成方接到同一审计链路。

本 PR 可审查主 Harness、能力准入、模型提议边界、持久恢复与基础审计。生产级银行授权回调、当前确认/验证记录装配、私有工具和图节点全链路事件，以及 HTTP/前端接线尚未完成；完成这些接线并跑真实端到端验收前，不把 #09 标记完成。

从 `backend/` 运行 `python -m pytest -q app/agent_platform/test_harness.py` 验证此目录。
