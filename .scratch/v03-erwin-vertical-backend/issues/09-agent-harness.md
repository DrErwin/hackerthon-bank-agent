# 09：集成主 Agent Harness 与恢复协调

Type: task\
Status: resolved\
Merged PR: #10\
Owner: Erwin\
Directory: `backend/app/agent_platform/`\
Blocked by: 02、03、05、06、07、08\
Integration dependency: 04\
Unlocks: 10

## 业务目的

让自然语言请求通过一套主 Harness 进入已登记的普通转账能力，并在暂停、刷新或重启后继续同一任务，而不是把业务步骤写进主 Agent。

## 交付

- 主 Harness、模型适配和能力注册中心。
- 普通转账公开能力适配，不访问其私有工具或内部状态。
- LangGraph Checkpoint、任务恢复与中断协调。
- 模型输入输出、能力选择、节点、工具和恢复事件的统一记录。
- 对模型产物的格式校验和确定性状态更新边界。
- v0.3 所需的最小上下文装配与模型配置。

## 验收

- “给妈妈转 500 元”能够被路由到普通转账公开能力。
- 主 Harness 不包含转账 14 步、银行规则或安全放行逻辑。
- 模型只能理解、追问和提出候选动作，不能直接提交资金工具。
- 等待输入、确认或验证时保存同一 `task_id`；刷新与服务重启后恢复原位置。
- 恢复不会重复执行暂停点之前的资金副作用。
- 模型、流程、工具和恢复事件可以通过同一追踪编号关联。

## Handoff

真实 Harness、恢复和事件链路跑通后，将 10 改为 `ready`。

## Comments
