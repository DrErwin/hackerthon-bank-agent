# storage —— 数据访问与持久化适配

归属：底座（Erwin）。

放什么：应用侧数据访问、迁移、持久化适配；检查点与记忆的持久化后端在此接入（Store 选型为架构 §13 待定项，SQLite/SQLModel 起步）。

边界：应用数据与银行数据分属不同服务管理——即使同库文件也不跨边界直读写表（架构 §2 读图判据 3）。

## v0.3 接入

`StoragePaths.from_env()` 默认把数据放在用户目录的 `.ai-banking-agent/`，也可用 `BANK_AGENT_DATA_DIR` 指向持久化目录。应用和模拟银行分别使用 `application.sqlite3`、`mock_bank.sqlite3`；部署时这两个文件必须放在持久化卷上。创建 `ApplicationStore(paths.application)` 会执行应用库 v4 迁移，重复初始化不会清空数据。银行服务单独创建 `MockBankStore(paths.bank)` 并执行银行库 v3 迁移。

应用入口只导出 `ApplicationStore`。所有任务读取、确认／验证／记忆引用和工具操作记录都要求用户与演示轮次；确认引用不能跨任务绑定，验证引用不能跨会话绑定。引用关联不代表安全授权，安全模块仍须核验原记录、具体动作和有效状态。`checkpoint_saver(user_id, demo_round_id, task_id)` 先核对任务归属，再返回只接受该任务内部 thread_id 的 LangGraph saver。外层须先持久化操作编号，再调用银行；结果未知时只用原编号回查。任务快照只保存脱敏展示与受控引用，不存验证码或完整账户资料。记忆正文与管理机制由后续 06 票接 Deep Agents Store；这里仅保存任务关联引用，06 仍须验证正文的用户与轮次隔离。

银行库仅供 `services/mock_bank/` 通过 `storage.mock_bank.repository` 使用。`commit_operation` 在一次事务里保存已经由银行服务决定的账户变化、流水与原操作结果；若先记录处理中，银行服务用 `finalize_operation` 在同一原编号下原子写入终态、账户变化和流水。同编号同参数返回原结果，参数或调用主体变了就拒绝。银行库 v1/v2 数据在初始化时升到 v3：补账本对手方 / 渠道 / 摘要 / 退款原单事实列，早期缺账本表的库按 v3 形状补建，既有操作结果与流水保留。`seed_ledger_rows(rows)` 按 `transaction_id` 幂等写入**已成形**的银行事实行（种子行 `operation_id` 以 `seed:` 标明来源，不是真实操作），账户不属于该用户或行缺必填事实时整批回滚；它默认不被任何路径调用。这里不计算余额、限额、范围或风控规则。

从 `backend/` 运行存储层验证：

```powershell
python -m pytest -q app/storage/
```

恢复审计需要知道任务最初保留的银行操作编号。`list_task_operations(user_id, demo_round_id, task_id)` 先核对任务范围，再按显式持久序号返回此任务的操作记录，包括尚未得到银行结果的预留操作；它不会触发银行查询或重提，也不依赖 SQLite 的隐藏行号。

## 新会话恢复

`ApplicationStore.transition_task_session(...)` 将已有任务关联到同一用户、同一演示轮次中的有效新会话。调用时传入原会话、新会话和读取到的任务版本号；有效期由服务端当前时间核对。

转换在一个数据库事务中完成；同一来源、目标和版本号的重试会在任务仍处于该转换版本时返回原结果。任务 ID、检查点线程、快照、操作 ID 和引用记录都保留。旧确认和验证引用仍留在存储中供追溯；任务切换会话后，`has_ref` 不再把它们视为当前有效引用。安全服务为新会话签发同一确认 ID 的更高版本后，绑定可随当前确认版本更新；旧版本仍由安全服务拒绝。验证引用不跨会话重绑。记忆引用仍可跨会话读取。

```python
task = store.transition_task_session(
    user_id, demo_round_id, task_id,
    source_session_id, target_session_id, task.revision,
)
```

如果任务版本或来源会话已变化、目标属于其他用户或轮次，或目标会话尚未生效 / 已过期，调用会失败。
