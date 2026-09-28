# memory —— Agent 长期记忆与上下文后端

归属：底座（Erwin）。安全规则由 Ringo 审查。这里提供 Deep Agents 的用户记忆 Store 后端与任务上下文接缝；业务权限、确认、验证和银行事实仍由各自服务判定。

`MemoryAdapter` 使用应用 SQLite 文件保存 LangGraph Store 的 `/memories/` 文件。每份记忆按用户和演示轮次隔离，重启后可读；预置称呼、分配偏好、月度预算和虚构配送资料来自冻结契约 §7.4。预置中的 A2/A4/A5 只是银行种子标识的线索，办理前仍须查银行并核验。

Harness 为可信用户会话取得 `MemoryContext` 后，使用 `agent_backend(context)` 作为 Deep Agents `backend`，使用 `middleware(context)` 作为附加中间件；主对话用 `conversation_checkpointer(context)` 与 `conversation_thread_id(context)`，具体任务用 `checkpointer(context, task_id)`。记忆通过 Deep Agents `StoreBackend` 读写；任务文件使用 `StateBackend` 与现有检查点。中间件每次从 Store 重载记忆，避免旧检查点把已删记忆重新放进提示。

模型写入只允许单行记忆线索或用户偏好；含认证秘密、执行授权、旧银行事实、一次性转账要求及常见注入语句的内容会被拒绝。模型不能直接删除或覆盖既有记忆。`list` 与 `delete` 读取同一 Store；删除检查整批归属和版本，在同一事务中完成并按 `request_id` 去重。删除的内容在本轮设墓碑，阻止旧上下文按原路径或相同内容写回。演示重置清理该用户旧轮次记忆，并原子恢复预置。真实 API、工具权限登记与审计事件在后续 07/09/10 集成时接线。

从 `backend/` 验证：`python -m pytest -q app/memory/test_memory.py`。安全侧需复核受控写入词表及可查看范围；该模块未代替 Ringo 的批准。
