# storage —— 数据访问与持久化适配

归属：底座（Erwin）。

放什么：应用侧数据访问、迁移、持久化适配；检查点与记忆的持久化后端在此接入（Store 选型为架构 §13 待定项，SQLite/SQLModel 起步）。

边界：应用数据与银行数据分属不同服务管理——即使同库文件也不跨边界直读写表（架构 §2 读图判据 3）。

## v0.3 接入

`StoragePaths.from_env()` 默认把数据放在用户目录的 `.ai-banking-agent/`，也可用 `BANK_AGENT_DATA_DIR` 指向持久化目录。应用和模拟银行分别使用 `application.sqlite3`、`mock_bank.sqlite3`；部署时这两个文件必须放在持久化卷上。创建 `ApplicationStore(paths.application)` 会执行应用库 v1 迁移，重复初始化不会清空数据。银行服务单独创建 `MockBankStore(paths.bank)` 并执行银行库 v1 迁移。

应用入口只导出 `ApplicationStore`。所有任务读取、确认／验证／记忆引用和工具操作记录都要求用户与演示轮次；`checkpoint_saver(user_id, demo_round_id, task_id)` 先核对任务归属，再返回只接受该任务内部 thread_id 的 LangGraph saver。外层须先持久化操作编号，再调用银行；结果未知时只用原编号回查。任务快照只保存脱敏展示与受控引用，不存验证码或完整账户资料。记忆正文与管理机制由后续 06 票接 Deep Agents Store；这里仅保存任务关联引用，06 仍须验证正文的用户与轮次隔离。

银行库仅供 `services/mock_bank/` 通过 `storage.mock_bank.repository` 使用。`commit_operation` 在一次事务里保存已经由银行服务决定的账户变化、流水与原操作结果；同编号同参数返回原结果，参数或调用主体变了就拒绝。这里不计算余额、限额或风控规则。

从 `backend/` 运行存储层验证：

```powershell
python -m pytest -q app/storage/test_storage.py
```
