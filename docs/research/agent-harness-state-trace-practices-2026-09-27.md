# 成熟 Agent Harness 的输出、状态与调试记录实践

> 调研日期：2026-09-27\
> 目的：为银行 Agent 的整体框架设计回答两个问题：每轮模型应该产出什么；为了调试和恢复，系统应该保存什么。\
> 来源口径：仅使用 LangGraph / LangChain Deep Agents、OpenAI Agents SDK、DeepSeek Harness 的官方文档或官方源码仓库。

## 1. 结论先行

### 对 Q21 的结论：不要把“模型回复”当成唯一输出

成熟 harness 通常保留四种不同层次的产物：

1. **原始模型产物**：模型原始响应及供应商元数据，用于定位模型问题。
2. **标准化运行事件**：助手消息、工具调用、工具结果、人工审批、错误等，用于继续 Agent 循环。
3. **结构化业务状态更新**：意图、已提取字段、缺失字段、草稿版本、下一业务状态等，用于确定性流程判断。
4. **用户可见回复**：给前端展示的自然语言或确认卡片，只负责沟通，不作为转账授权或业务事实。

因此，转账场景不宜要求模型每轮只返回一个混合大对象，然后让所有后续逻辑都依赖它。更合适的方式是：

- 模型用标准消息或结构化工具调用表达“它建议做什么”；
- 字段抽取、意图判断等需要稳定读取的内容，用 Pydantic / JSON Schema 校验；
- 确定性节点校验并写入 LangGraph State；
- 用户文案从已校验状态生成；
- 原始响应和完整运行事件进入调试记录，但不直接成为银行业务事实。

LangChain 官方把结构化结果放在 Agent 最终 State 的 `structured_response` 中，并优先使用模型供应商原生的结构化输出；如果供应商不支持，则退回工具调用策略。LangGraph 则明确把 State 定义为当前应用快照，节点只返回局部更新，由 reducer 合并。这说明“模型输出”和“应用状态”是两个边界，不应混成一段自由文本。[LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)；[LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)

OpenAI Agents SDK 也把结果拆开：`final_output` 用于最终展示，`new_items` 保存助手、工具、交接和审批等富事件，`raw_responses` 保存每次模型调用的原始响应，`interruptions` 与 `to_state()` 用于暂停恢复。这进一步说明成熟实现不会只保留最终回答。[OpenAI Agents SDK — Results](https://openai.github.io/openai-agents-python/results/)

### 对 Q26 的结论：为了 debug 应保存完整“事件”，但不是无边界保存所有秘密

“完整记录”应该理解为：**所有能重建这次运行的事件都要记录**，而不是“任何敏感值都永久明文保存”。

DeepSeek Harness 的官方实现就是很强的参照：Session 是追加式、带类型的事件日志，是单一事实源；模型消息历史、回放、恢复、界面投影和遥测都从事件日志派生。核心事件包括 turn/step 开始与结束、用户/系统/助手消息、失败的助手尝试、工具调用与结果、请求头和请求上下文。[DeepSeek Harness — Sessions](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/session.md)；[DeepSeek Harness — Core](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/core.md)

但 DeepSeek Harness 同时把“本地规范日志”和“向外发送的遥测”分开：对外遥测有独立的 redaction 扩展点，脱敏只作用于导出的副本，不改写本地规范日志。官方也明确警告，如果部署方没有挂脱敏规则，完整内容可能原样外发；其安全说明要求不要暴露敏感凭据或数据。[DeepSeek Harness — Session telemetry](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/session-telemetry.md)；[DeepSeek Harness — Safety](https://github.com/deepseek-ai/deepseek-harness/blob/master/SAFETY.md)

OpenAI Agents SDK 同样默认追踪模型生成、工具调用、handoff、guardrail 等，并允许关闭敏感输入输出的采集。官方还特别说明：如果导出前必须脱敏，应由同一个应用自有 exporter 完成“复制、脱敏、发送”，失败时丢弃该批数据，不能让未经脱敏的旁路 exporter 继续收到原文。[OpenAI Agents SDK — Tracing](https://openai.github.io/openai-agents-python/tracing/)

对本项目的直接建议是：

- **开发环境**：保留可回放的完整事件链，敏感业务值放在受限、加密的本地存储中；日志界面默认遮盖。
- **测试与演示环境**：使用假数据，允许完整采集模型输入输出、工具参数和结果。
- **生产式设计**：日志事件保持完整，但凭据、验证码、密钥绝不进入日志；完整卡号等敏感字段使用引用、token 或受控加密字段；对外 trace 默认脱敏。
- **审计记录与 debug trace 分开**：审计记录回答“谁在何时批准、系统执行了什么、银行返回什么”；debug trace 回答“模型和节点为什么走到这里”。两者通过 ID 关联，但权限和保留策略不同。

一句话：**全事件，不等于全明文；可回放，不等于可随意外发。**

## 2. 推荐的四层数据模型

| 层次 | 主要问题 | 典型内容 | 是否驱动业务 | 建议保存方式 |
|---|---|---|---|---|
| LangGraph State / Checkpoint | 任务现在走到哪 | 意图、字段、草稿 ID/版本、状态、安全检查结果、确认状态、下一节点 | 是 | 持久化 checkpointer |
| Session Event Log | 这次 Agent 实际发生了什么 | 用户消息、模型消息、工具调用与结果、interrupt、错误、状态变更 | 间接；用于恢复与回放 | 追加式事件表或 JSONL |
| Trace / Span | 哪一步慢、错或行为异常 | 模型调用、节点、工具、guardrail 的输入输出、耗时、父子关系 | 否 | 可观测性系统，支持脱敏与采样 |
| Business Audit | 谁授权了什么操作 | 用户身份、确认动作、草稿版本、执行编号、银行结果、时间 | 是，且是合规事实 | 只追加、严格授权、独立保留 |

这四层不可互相代替：

- Checkpoint 是“可恢复的当前快照”，不是完整审计流水。
- Event Log 是“完整发生史”，可派生对话和调试视图。
- Trace 是运行诊断树，适合看嵌套和耗时，但不应成为业务真相源。
- Audit 是业务证据，不需要保存每个 token 或模型内部细节。

LangGraph 官方说明 checkpointer 会在每个 super-step 保存 State 快照，同时保存节点级 pending writes；它支持恢复、人工审批、time travel 和故障恢复。StateSnapshot 本身包括 state values、下一节点、checkpoint/thread 标识、节点 writes、step、时间、父 checkpoint、错误和 interrupts。[LangGraph — Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)

LangSmith 官方把 Trace 定义为一棵 run 树，把 Thread 定义为多轮 trace 序列，把 Trajectory 定义为扁平消息路径。Trace 含完整输入输出，适合诊断单次操作；Thread 适合查看跨轮行为；Trajectory 适合阅读对话。这正好支持把“运行诊断”和“对话历史”分开。[LangSmith — Observability concepts](https://docs.langchain.com/langsmith/observability-concepts)

## 3. 每轮 Agent 输出的推荐合同

### 3.1 模型可产出的标准类型

每次模型调用只需要落到以下一种或多种标准产物：

- `assistant_message`：面向用户的说明或追问。
- `tool_call`：工具名、结构化参数、唯一 `tool_call_id`。
- `structured_decision`：经 schema 校验的意图/字段/缺失项/建议动作。
- `final_output`：本轮 Agent 循环结束后的用户输出。
- `model_metadata`：模型、响应 ID、token 用量、延迟、停止原因等诊断数据。

不要把以下内容当作模型的自由决定：

- 确认是否有效；
- 当前草稿是否仍是用户看到的版本；
- 是否有权限执行；
- 是否已执行过；
- 银行交易是否成功。

这些必须由确定性节点从 State、审计记录和模拟银行结果中判断。

### 3.2 转账字段抽取节点的建议输出

模型抽取可以使用一个小而稳定的 schema，例如：

```text
intent
recipient_text
account_text
amount
currency
missing_fields
ambiguities
user_message
```

其中 `user_message` 只负责沟通；其余字段仍需确定性校验后才能写入正式草稿。不要在这个对象里放 `approved=true`、`transfer_allowed=true` 或 `success=true` 之类由模型判断的高权限结论。

### 3.3 为什么仍要保留原始响应

结构化对象适合程序使用，但不足以 debug 以下问题：供应商返回格式异常、工具调用参数在解析前发生变化、模型重试、流式输出中断、模型响应元数据异常。OpenAI Agents SDK 因此同时暴露 `new_items` 与 `raw_responses`；DeepSeek Harness 也会记录成功助手消息和失败/重试/取消的 `assistant/attempt`，而失败尝试不会污染模型后续看到的消息历史。[OpenAI Agents SDK — Results](https://openai.github.io/openai-agents-python/results/)；[DeepSeek Harness — Session architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md)

## 4. Checkpoint、interrupt 与副作用

### 4.1 银行 Agent 为什么需要持久化暂停

LangGraph 官方直接把 financial transactions 列为 interrupt 的典型用途。暂停后使用相同 `thread_id` 和 `Command(resume=...)` 恢复；恢复值会成为 `interrupt()` 的返回值。[LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

### 4.2 一个容易踩坑的官方语义

恢复时，LangGraph 会从包含 `interrupt()` 的节点开头重新运行，因此 interrupt 之前的代码会再次执行。官方要求 interrupt 的载荷保持简单、可序列化，并提醒不要在节点内改变多个 interrupt 的顺序。[LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

对转账流程的含义：

- “展示确认并暂停”节点本身不要在 interrupt 前执行转账或其他不可重复副作用。
- 草稿创建如果发生在此前节点，必须有稳定 `draft_id + draft_version`，重复调用只能返回同一草稿或安全拒绝。
- 真正执行节点必须使用稳定 `execution_id / idempotency_key`。
- 用户确认后仍需按当前草稿版本和当前安全状态复查，不能因为 checkpoint 里曾经通过就直接执行。

DeepSeek Harness 的 checkpoint policy 也明确指出，它只能保证“执行意图已持久化”，不能天然保证外部副作用 exactly-once；有副作用的工具应把调用 ID 转成下游幂等键。对于崩溃后只有调用、没有结果的情况，应记录 outcome unknown，而不是自动重试。[DeepSeek Harness — Session checkpoint policy](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/session/session-checkpoint-policy/README.md)

### 4.3 持久化粒度

LangGraph 提供三种 durability mode：`exit`、`async`、`sync`。`sync` 会在下一步开始前同步写入每个 checkpoint，耐久性最高，但有性能成本。涉及转账确认和执行边界时，建议关键图运行使用同步耐久语义；普通只读对话可以再评估性能取舍。[LangGraph — Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)

## 5. 调试事件建议清单

下面是这个项目值得保存的最小完整事件集。它借鉴 DeepSeek Harness 的 typed event log，但按银行场景简化：

| 事件 | 关键字段 |
|---|---|
| `turn.started` / `turn.ended` | session、task、turn、开始/结束时间、结束原因 |
| `user.message` | message_id、原始输入引用、渠道、时间 |
| `model.requested` | model、prompt/version、可用工具名、输入引用 |
| `model.responded` / `model.attempt_failed` | response_id、标准化内容、原始响应引用、usage、latency、错误 |
| `decision.extracted` | schema version、字段、缺失项、歧义、校验结果 |
| `state.updated` | node、checkpoint_id、更新字段摘要、下一节点 |
| `tool.requested` | tool_call_id、工具名、参数、安全级别 |
| `tool.completed` / `tool.failed` / `tool.outcome_unknown` | tool_call_id、结果引用、耗时、错误 |
| `confirmation.requested` | task_id、draft_id、draft_version、过期时间、展示摘要 |
| `confirmation.resolved` | confirmer、decision、draft_version、时间 |
| `execution.requested` | execution_id、idempotency_key、确认与复查引用 |
| `bank.responded` | bank_request_id、状态、原始结果引用 |
| `run.interrupted` / `run.resumed` | interrupt_id、checkpoint_id、原因、恢复来源 |

每个事件建议至少关联这些 ID：

```text
session_id / thread_id
task_id
trace_id / run_id
turn_id / step_id
checkpoint_id
tool_call_id
draft_id / draft_version
execution_id / idempotency_key
```

## 6. “完整记录”需要的边界

### 应完整记录

- 用户输入和系统实际发送给模型的输入版本；
- 模型的标准化消息、工具调用、原始响应引用和失败尝试；
- 每个节点的开始、结束、更新和路由结果；
- 工具参数、工具结果、错误、耗时和调用 ID；
- interrupt、确认、拒绝、过期和恢复；
- checkpoint 元数据；
- 安全策略版本、判断结果和命中规则；
- 模拟银行原始返回及其请求关联 ID。

### 不应进入普通日志

- API key、密码、短信验证码、访问令牌；
- 可直接用于冒用身份的凭据；
- 无访问控制的完整银行卡号等高敏感值；
- 与重建决策无关的模型供应商私有内部数据。

如果为了本地排障必须保留某些高敏感业务原文，应做到：加密、严格访问控制、短期保留、可删除、与普通 trace 分库存放。对外发送的 trace 只发送脱敏副本。

这不是削弱 debug，而是避免日志本身成为新的安全事故来源。DeepSeek Harness 的安全说明与 OpenAI Agents SDK 的敏感 trace 配置都证明，成熟 harness 也不会把“记录完整”解释为“秘密可以无限制明文传播”。[DeepSeek Harness — Safety](https://github.com/deepseek-ai/deepseek-harness/blob/master/SAFETY.md)；[OpenAI Agents SDK — Tracing](https://openai.github.io/openai-agents-python/tracing/)

## 7. 对当前框架讨论的建议定案

### Q21 建议定案

> 每次模型调用保留原始响应，并规范化为消息、工具调用和结构化决定；只有经过 schema 校验和确定性业务校验的字段才写入 LangGraph State。用户回复是 State 的展示投影，不作为授权或业务事实。

这比“模型同时输出一段自然语言和一个结构化决定，然后后续完全信任”更稳，因为它保留了完整诊断数据，同时让业务控制权留在确定性代码中。

### Q26 建议定案

> 建立追加式、可回放的完整 Agent 事件日志，记录模型请求/响应、失败尝试、工具调用/结果、状态变化、确认、interrupt、恢复和银行结果；另建业务审计记录。开发环境可保存完整假数据，生产式环境对秘密和高敏字段加密或引用化，对外 trace 必须脱敏。

这保留了 DeepSeek Harness 式的 debug 能力，也符合银行 Agent 的权限和隐私边界。

## 8. 关于“DeepSeek Harness”的核实结果

用户提到的 `deepseekharness` 很可能就是 DeepSeek 官方项目 **DeepSeek Harness (`dsh`)**，而非泛称。已核实的一手来源：

- 官方仓库：[deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)
- 官方说明称它是 DeepSeek AI 开发的开源 agent harness，采用“everything is a plugin”架构。
- 当前官方仍标记为 developer preview，并提醒会有破坏性兼容变更，因此适合借鉴设计原则，不宜直接把它当成银行生产框架依赖。

其最值得本项目借鉴的不是插件数量，而是三件事：

1. append-only typed event log 是会话事实源；
2. 模型消息、回放、恢复、界面和遥测从同一事件流派生；
3. 本地规范日志、checkpoint policy、外发 telemetry 是三个不同能力边界。

## 9. 一手资料索引

- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangChain Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview)
- [LangSmith Observability concepts](https://docs.langchain.com/langsmith/observability-concepts)
- [OpenAI Agents SDK — Results](https://openai.github.io/openai-agents-python/results/)
- [OpenAI Agents SDK — Sessions](https://openai.github.io/openai-agents-python/sessions/)
- [OpenAI Agents SDK — Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)
- [OpenAI Agents SDK — Tracing](https://openai.github.io/openai-agents-python/tracing/)
- [DeepSeek Harness official repository](https://github.com/deepseek-ai/deepseek-harness)
- [DeepSeek Harness — Session subsystem](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/session.md)
- [DeepSeek Harness — Session persistence](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/persistence.md)
- [DeepSeek Harness — Session checkpoint policy](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/session/session-checkpoint-policy/README.md)
- [DeepSeek Harness — Session telemetry](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/session-telemetry.md)
- [DeepSeek Harness — Safety](https://github.com/deepseek-ai/deepseek-harness/blob/master/SAFETY.md)
