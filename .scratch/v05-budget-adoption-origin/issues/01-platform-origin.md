# 01：预算 F10 来源持久化与受控恢复

Ticket ID: v05-budget-adoption-origin/01

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [预算采用来源最小设计](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/agent_platform/`

Status: merged — PR #298 已合入 `6ce7fb03`；2026-10-29 核对。原验证及审查按各批记录，CI 计费未启动；真实业务/页面和本人接受另见[v0.5 完成情况](../../../docs/versions/v0.5.0/completion.md)。

原交付时状态（历史）：in_review / merge_prepared — 已获Erwin第二批本PR合入及CI计费本地验证例外，完成等价同步；待中控核对并squash，尚未合入，不代表API/cross联调或最终安全接受

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

业务为明确标记的持久stand-in，仅证明平台边界，**不代替真实cross06/#293采用、HTTP receipt或生日E2E验收**。完整后端回归在中控释放503/审计诊断槽位后顺序运行，结果见下节；未自行豁免CI、合入或真人安全审阅。未改共享tracking/completion/包状态、API、storage、cross或#160政策。

### 完整后端回归（2026-10-25，槽位释放后）

- 固定提交：`4f1824789baf88048eae32367d4c008624f3fc4b`，运行前后HEAD及源码相同、工作区干净。仅运行一轮，不覆盖首次输出。
- 本worktree新建独立`.venv`（Python 3.12.3，离线安装现有声明依赖；依赖清单留存），确认`app.agent_platform.budget_inputs.__file__`指向本worktree源码。独立临时数据及`BANK_AGENT_DATA_DIR`，未使用共享演示数据；关闭外部追踪并移除进程内真实模型凭据/本地运行配置，测试使用脚本或模型替身，无真实模型调用。
- 从`backend/`运行：`.venv/Scripts/python.exe -m pytest -q --basetemp=.venv/validation/full-4f18247-01/tmp --junitxml=.venv/validation/full-4f18247-01/junit.xml`。
- **1752 passed in 764.59s（12分44秒）；0 failed / 0 errors / 0 skipped，退出码0**。已交叉核对JUnit计数。开始`2026-10-25T08:28:09Z`，结束`08:41:03Z`；数量只对应上述固定树，不与中控其他分支的1606项混算。
- 本地原始证据目录：`backend/.venv/validation/full-4f18247-01/`；保留`head.txt`、`dependencies.txt`、起止时间、`exit-code.txt`、完整`pytest.log`、`junit.xml`及专属临时数据库。日志SHA256：`AD6720D792E85A70A314B9FA143DDA2647978633D7972B556E8F5A992F4E79D7`；JUnit SHA256：`7A4F28B54208B4E3173C2B59E15BDFA3D2450493398D8F0117C9603670BDAF2D`。
- 本轮无失败，不据此声称此前503根因已定位或修复。后续提交仅补本票证据，不改受测运行代码；API02仍等待本票稳定合入及中控信号，不提前代做。

## Comments

2026-10-25：代码交付 [PR #298](https://github.com/DrErwin/hackerthon-bank-agent/pull/298)，保持Draft/未合并。双轴固定基线`0930d6be59c728b9dc0ef4c4ef0b5430da12943e`，受审实现`2c8dae93b2ffcc6e13a177744fa0ec3f7e323449`；后续仅追加本票证据，不改变受审代码。

- **Standards**：`platform12_standards_review`独立审查PASS，硬规范违反0、气味建议0；独立来源测试 **35 passed in 9.18s**。确认目录、CAS/锁、派发前复核、来源隔离及接入边界符合要求。
- **Spec**：`platform12_spec_review`独立审查PASS，必须修复0、建议0；独立来源测试 **35 passed in 9.19s**。确认历史优先分流、原写严格绑定、冻结结果、并发及上下文隔离符合规格。
- **CI**：受审head的Repository checks未启动，GitHub注明账户近期付款失败或需提高spending limit；这是外部账单阻塞，不能记作绿灯。本PR未获此前首批PR的CI/合入例外，不自行豁免。
- **当时下一步**：全量按释放槽位顺序通过，交Erwin处理CI阻塞与合入决定；298/296当时均未获此前首批五PR的合入/CI例外。以下第二批本人批准仅更新298的当前准备状态，296仍未获本批批准。API02仍待本接缝稳定合入和中控信号，cross06仍按自己的采用映射/稳定attempt/准确事实接线；AI审查不代替最终真人安全接受。

## 第二批批准后的合入准备（2026-10-25）

**本人批准来源**：Erwin在中控对话答复“批准本批五项及CI例外（推荐）”；[中控主线记录](../../v05-control/dispatch-2026-10-25.md#1818-核查新平台材料与第二批明确批准)，固定来源`41c01aed544718f459e8dffcea3be3de42df18e0`。仅覆盖298→284→292→295→297及等价同步，允许以已记录本地验证作为CI账户计费故障期间依据；CI仍Blocked，不扩到296/293、数据库升级、新安全政策或最终安全/体验接受。本执行者只准备原PR，中控核对并squash；没有自行合并。

| 项目 | 精确版本 |
|---|---|
| 原base | `0930d6be59c728b9dc0ef4c4ef0b5430da12943e` |
| 原head | `5ebc1332d958f08e1900ab19cfb6815e737384d6` |
| 最新main / 新base | `41c01aed544718f459e8dffcea3be3de42df18e0` |
| 四条原提交rebase后的head | `6b8ca8d2de28ac26bad1d9298ffeff9b09513954` |
| 原受测 / 受审head | `4f1824789baf88048eae32367d4c008624f3fc4b` / `2c8dae93b2ffcc6e13a177744fa0ec3f7e323449` |

干净的原独立worktree中fetch后rebase，无冲突、无产品/测试代码改动；主线相对旧base仅有Markdown变化。四条range-diff均为`=`：15d4d12→108b93a、2c8dae9→5080035、4f18247→d6eea83、5ebc133→6b8ca8d。原/新累计补丁逐字节相同，SHA256均为`f99662c442fcc882044da187d9097c1da4bab5b0393d5fcfc1981f44e6edcf09`。此后只补本票准备记录，不改受测实现。

对原head、原1752受测head、原双轴受审head与新head逐一比较：排除docs/.scratch后的**651个受版本管理文件全部相同**，backend/evals/frontend/tools/.github各子树一致；含本票后台实现和测试。原1752 JUnit、退出码0、日志/XML哈希再次核对不变。因此沿用1752/87及双轴35独立复验证据，不重复跑全量/定向，不运行模型。

本地保留`refs/codex/v05-budget-origin-01-before-approved-sync`指向旧5ebc133；`backend/.venv/validation/pr298-approved-main-sync/`保存原/新补丁、原四提交、range-diff及equivalence.json，原完整测试证据未覆盖。原PR分支以明确旧head的force-with-lease更新；最终发布head由PR与回交给出。本票未新增业务代码或公共字段，不改共享进度、其他PR或生日新四票（仍planned/blocked）。
