# 01：预算 F10 来源持久化与受控恢复

Ticket ID: v05-budget-adoption-origin/01

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [预算采用来源最小设计](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/agent_platform/`

Status: in_review — 平台实现、定向验证与独立双轴审查通过，待全量槽位/CI及Erwin合入；不代表API/cross联调或安全接受

Blocked by: None（289已合入，296已整理；无需新增storage表或等待#293接口变更）

Execution thread: `01a1718a-26a3-7523-a0bf-2591d8e83618`，GPT-6.1-sol/high；2026-10-25中控依Erwin既有分派授权正式派发。完成后分别调用规范轴与规格轴子代理审查，必须项修复后复验；不自行合并。

Execution assignee: Codex，运行装配遗留线

Accepted by: Erwin 授权 Codex 实施（中控续派）

Accepted at: 2026-10-25

Core scenarios: O01—O08，定义见规格；预算业务语义仍由 cross06 实施。

## What to build

提供专用后台预算输入入口及当前调用来源读取。复用任务快照/CAS/锁，固定认证主体、原 F10 请求/交互/选项、原候选/计划绑定、写入前后任务版本；普通 resume 和模型不激活来源。来源记录不是采用或动钱授权。

## Acceptance criteria

- [x] 先核对并持久来源，失败零模块调用；禁止模型字段创建来源。
- [x] 核对当前等待输入、真实候选与原选项，记录 accepted_task_revision 与写后 dispatch_task_revision；不把 revision 当授权。
- [x] 私有读取只对当前专用输入/受控恢复有效，跨任务/线程/异常返回不串用句柄，snapshot 中存在历史来源不等于当前可用。
- [x] 同交互双请求、同号异参、旧候选和跨主体/会话/轮次均拒绝或仅返回原事实，不生成第二来源。
- [x] 原来源 + 稳定 cross attempt 支撑断点恢复，result 与 completed 投影在同次 CAS 中保存；缺 attempt 不重新推定已采用（平台接缝由持久stand-in验证）。
- [x] 首次/尚未采用的原写仍严格核对当前 input；已有采用事实的历史核实可处理 needs_attention / interaction=None，只补原结果，不激活来源/新写采用，取消/终态不继续新步骤。
- [x] 修改/取消/新会话等不能复活旧来源；API receipt 断点恢复所需输出稳定可读。
- [x] 提供 API 与 cross06 的调用样例，公共字段不变；设计若发现不能用现有持久接缝完成，先回中控，不跨目录写 storage。

## Verification

2026-10-25：真实 Harness/ApplicationStore、临时SQLite、checkpointer、任务锁/CAS验证 O02—O08 的平台边界。`test_budget_inputs.py`共35项，连同既有`test_harness.py`、`test_child_dispatch.py`、`test_fault_snapshot.py`共 **87 passed in 44.27s**。覆盖来源/attempt/采用/发布断点、重开、同号异参、同交互并发、会话切换、候选替换、普通模型续答和异常后句柄隔离。此前一轮86通过、1项测试夹具版本值不合法；修正夹具后上述87项通过。

实现基线：`0930d6be59c728b9dc0ef4c4ef0b5430da12943e`。独立worktree：`v05-budget-origin-01/hackerthon-bank-agent`；分支：`codex/v05-budget-origin-01`。接入说明与API/cross样例见[专用预算F10来源接缝](../../../backend/app/agent_platform/budget-inputs-seam.md)。

业务为明确标记的持久stand-in，仅证明平台边界，**不代替真实cross06/#293采用、HTTP receipt或生日E2E验收**。全量后端测试未启动，遵中控503/审计诊断独占全量槽位的安排排队；未自行豁免CI、合入或真人安全审阅。未改共享tracking/completion/包状态、API、storage、cross或#160政策。

## Comments

2026-10-25：代码交付 [PR #298](https://github.com/DrErwin/hackerthon-bank-agent/pull/298)，保持Draft/未合并。双轴固定基线`0930d6be59c728b9dc0ef4c4ef0b5430da12943e`，受审实现`2c8dae93b2ffcc6e13a177744fa0ec3f7e323449`；后续仅追加本票证据，不改变受审代码。

- **Standards**：`platform12_standards_review`独立审查PASS，硬规范违反0、气味建议0；独立来源测试 **35 passed in 9.18s**。确认目录、CAS/锁、派发前复核、来源隔离及接入边界符合要求。
- **Spec**：`platform12_spec_review`独立审查PASS，必须修复0、建议0；独立来源测试 **35 passed in 9.19s**。确认历史优先分流、原写严格绑定、冻结结果、并发及上下文隔离符合规格。
- **CI**：受审head的Repository checks未启动，GitHub注明账户近期付款失败或需提高spending limit；这是外部账单阻塞，不能记作绿灯。本PR未获此前首批PR的CI/合入例外，不自行豁免。
- **下一步**：中控安排全量槽位与Erwin合入；API02待本接缝稳定合入后接线，cross06按自己的采用映射/稳定attempt/准确事实实现只读恢复，再做真实联合验收。上述AI审查不代替真人安全签核。
