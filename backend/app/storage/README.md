# storage —— 数据访问与持久化适配

归属：底座（Erwin）。

放什么：应用侧数据访问、迁移、持久化适配；检查点与记忆的持久化后端在此接入（Store 选型为架构 §13 待定项，SQLite/SQLModel 起步）。

边界：应用数据与银行数据分属不同服务管理——即使同库文件也不跨边界直读写表（架构 §2 读图判据 3）。

## v0.3 接入

`StoragePaths.from_env()` 默认把数据放在用户目录的 `.ai-banking-agent/`，也可用 `BANK_AGENT_DATA_DIR` 指向持久化目录。应用和模拟银行分别使用 `application.sqlite3`、`mock_bank.sqlite3`；部署时这两个文件必须放在持久化卷上。创建 `ApplicationStore(paths.application)` 会执行应用库 v7 迁移，重复初始化不会清空数据。银行服务单独创建 `MockBankStore(paths.bank)` 并执行银行库迁移。

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

## v0.5 联动持久记录（v05-cross-platform/02，应用库 v5）

应用库 v5 迁移新增四张表，全部要求用户与轮次范围，计划版本仍保存在任务快照里：

- `task_relations`：父子任务组织关系（`link_child_task` 幂等登记，子任务只能属于一个父任务；`parent_of_task` / `task_lineage` 供平台核对归属）。它只表达组织关系，账单来源继承仍由平台按原事实来源字段处理，不复用此表。
- `arrangements`：已采用资金安排（`AdoptedArrangement` 快照 + `payer_account_id` 列）。`acquire_arrangement` 是 D1 的原子接缝——同一 user/round/account 只允许一份 active 安排：他人持有抛 `ArrangementConflictError`（带持有者 task/arrangement 编号），同父任务改版自动 supersede 旧记录；`close_arrangement` 只关 active（在途未核实不得关闭由调用方核实）；`get_active_arrangement` 供其他应用入口做只读冲突核对。数据库另有部分唯一索引兜底。
- `budget_commitments`：按 `budget_id`（不分版本）串行的预算占用记录。`register_budget_commitment(..., max_in_flight_fen=...)` 在同一写事务内核对非 closed 占用的 unconsumed 合计并登记，超出抛 `BudgetOccupationExceededError`；`update_budget_commitment` 原地更新（budget/task 身份不可变），unknown 占用一直可查，closed 不再计入在途。
- `controlled_details`：受控资料原文（`delivery` / `payee` / `payee_search`）按本人、轮次、任务存储；`get_controlled_detail` 越权一律返回 `None`，不泄露存在性。原文是否可进入某条路径由 API/安全层决定，存储本身不是脱敏边界。

存储不判断生活费、银行余额、限额或风控；金额上限等业务参数由调用方以参数传入。

## 已采用个人预算（v05-adopted-budget-storage/01，应用库 v6）

`adopted_budgets` 保存现行 `AdoptedBudget`，按可信 user/round 隔离，每个 budget_id 可保留多个版本、最多一个 active。只新增表及索引，v5 任务、安排、占用和受控资料原样保留。

- `adopt_budget(user_id, demo_round_id, record, expected_task_revision=..., previous_version=...)`：受控写入。初次 version=1 / previous_version=None；改版 version=旧版+1 / previous_version=旧版。一个事务内核对记录归属、来源任务、任务 revision 和当前 active 版本，再将旧版 superseded 并写入新版。竞争失败抛 `ValueError`，不部分提交。
- 同源任务的 adoption_interaction_id 绑定不可变的原采用快照和任务 revision；精确重放返回原版本的当前状态，不重复写入。同交互异参（包括换 budget_id/version）拒绝。原采用已 superseded 时，重放也不会复活旧版本。
- `get_adopted_budget(user_id, demo_round_id, BudgetRef(...))`：按准确版本返回记录（含 superseded），不存在或其他用户/轮次返回 None。调用方须核对 status，不能把查到历史记录当作 active。
- `list_adopted_budgets(user_id, demo_round_id, include_superseded=False)`：默认只返回本轮 active 候选，显式可读历史；每条保留原 scope/purpose/source_task_id，排序不代表优先级。cross 必须按真实付款账户、消费日期及用途筛选，多条重叠先澄清，省略引用也要检查。

下面展示后续 cross 的调用接缝，尚未接线。actor 和任务来自可信上下文；`verified_record` 是 cross 完成原 F10 adopt、原交互、当前计划版本、原 scope/purpose/limit 快照核对后生成的 `AdoptedBudget`，不是模型输入。task.revision 是应用任务版本，不是 plan_revision；传入核对时读取的同一个值。

```python
from app.contracts import BudgetRef

# 初次采用：verified_record.version == 1、status == "active"
adopted = application.adopt_budget(
    actor.user_id, actor.demo_round_id, verified_record,
    expected_task_revision=task.revision,
)
saved = application.get_adopted_budget(
    actor.user_id, actor.demo_round_id,
    BudgetRef(budget_id=adopted.budget_id, version=adopted.version),
)
candidates = application.list_adopted_budgets(actor.user_id, actor.demo_round_id)

# 重新明确采用：revised_record 保留 budget_id、version=adopted.version+1，
# 携带新的采用交互及快照；modified_task 是本次验证时读取的来源任务。
revised = application.adopt_budget(
    actor.user_id, actor.demo_round_id, revised_record,
    expected_task_revision=modified_task.revision,
    previous_version=adopted.version,
)
occupations = application.list_budget_commitments(
    actor.user_id, actor.demo_round_id, revised.budget_id,
)
```

存储不解析 cross 检查点、不验证 F10 的选项或计划业务快照；来源任务存在和版本一致本身不等于采用授权。上述真实性由 cross 调用前保证，写接口不暴露为模型工具/HTTP。业务层还须保存生日 task_id 与 budget_ref 的绑定、刷新 L01、判断额度及冻结前登记 pending；本票没有完成这些路径。`list_budget_commitments` 仍按同 budget_id 返回各版本未关闭占用，不因采用改版清除旧占用。

重置沿用演示轮次更换：新 demo_round_id 读取不到旧采用状态，原轮次记录保留供追溯。没有新增清库/重置接口；同轮次重开数据库也不会自动撤销采用。

## 生日候选检查点一次封存（v05-birthday-platform-dependencies/05，应用库 v7）

应用库 v7 只新增 `checkpoint_seals` 表与索引，旧表、旧检查点和历史 namespace 原样保留，不做数据回填或清理，因此不需要迁移共享库内容。`SqliteCheckpointSaver` 新增内部接口 `seal_candidate(...)`（配套 `CheckpointRef`、`SealedCandidate`、`CandidateBindingConflictError`），供 03 在用自己的任务 CAS 持久预留候选 ref 后，把一份完整 G3 状态及其元数据、必要关联写一次性封存为不可变候选。存储不选可编辑项、不做安全撤离、不发布任务，也不验证绑定内容的业务真假；可信转换关联由 03 传入。

三类来源共用同一窄能力，结构条件不同：

- `root`：新任务的第一份状态，没有前驱 source，也没有 `edit_ref`；只有任务仍无已发布 checkpoint（`tasks.checkpoint_id IS NULL`）且该线程没有任何历史检查点/待写行时才能写入。已有历史或已发布状态的任务不能冒充新根。
- `normal`：无编辑请求的普通输入/事实/异常后继；必须绑定此前已封存的完整 `source` ref 与来源摘要，不能绑定旧 namespace 里可被覆盖的 blob。
- `edit`：真正受理的编辑候选；除已封存 source 外必须带原 `edit_ref`（安全/原号事实摘要由调用方并入 `conversion_digest`）。

一次调用的输入是：受控 user/round/task、`kind`、预先预留的 `candidate`（task thread + 新 namespace + checkpoint id）、`accepted_version`、原转换摘要 `conversion_digest`、`source`/`source_digest`（root 之外必填）、`edit_ref`（仅 edit）、完整 `checkpoint` 及 `metadata`/`new_versions`/`writes`。候选 namespace 必须非空且完全未使用（默认 namespace 留给普通 LangGraph 流程），每份候选独占一个 namespace；同一绑定（kind/edit/source/摘要/接受版本）只封存首份内容，之后重试或并发竞争都返回该胜者和原新 input（自动测试覆盖同进程多线程并发；跨进程同绑定行为经独立双进程探针复核，尚未固化为测试）；同一 ref 换绑定抛 `CandidateBindingConflictError`，不写后比较。`content_digest` 记录完整封存内容摘要，供 03 在发布快照中保存。

封存后该 namespace 内的 `put`、`put_writes` 被拒绝（按持久表判断，不依赖进程内锁），`delete_thread` 也拒绝含封存候选的线程；03 发布胜者、任务继续推进都不解除保护，每份后续状态必须再预留新的隔离 namespace。默认 namespace 与既有普通 LangGraph/旧模块保存路径不变。

边界：本接口不能独立证明 source 已由 03 发布（只保证 source 是此前已封存的完整 ref），也不核验 root 的原 start 预留语义；这两项仍由 03 的受理/CAS 负责。旧任务未封存的历史检查点不能作为 source，G3 编辑按对账稿保持 blocked。
