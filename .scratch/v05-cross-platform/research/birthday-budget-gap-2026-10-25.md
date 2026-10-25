# 生日个人预算引用与版本：提供方及最小依赖

核查：2026-10-25；基线 `e9517b8466f4ca408a6173c2be7d87b116efe5a8`。仅核查与复现，不改 `modules/cross`、storage、contracts 或 API；business05 继续只交配送/结构化事实。关联 [v05-cross-business/03：生日编排及预算约束](../../v05-cross-business/issues/03-birthday-orchestration.md) 残留、[v05-cross-platform/12：故障装配](../issues/12-birthday-response-loss-assembly.md)。

## 结论

这不是生日平台装配遗失字段，而是**业务输入未接线 + 已采用预算持久存取缺失**。不能只把 `budget_version=1` 换成输入版本，更不能把本次生日 500 元上限当成用户已采用的个人预算。

| 层级 | 当前具备 | 真实缺口/提供方 |
|---|---|---|
| 公共模型 | [cross.py](../../../backend/app/contracts/cross.py) L43–85 的 `BudgetRef` / `BudgetView` / `AdoptedBudget`；L134–188 的 constraints 支持 budget_ref/budget_fen/deliver_by/delivery_ref；BirthdayPlan 也携带 budget_id/version | 字段已具备，按现有契约实施无需先新增字段。 |
| 业务入口 | [entry.py](../../../backend/app/modules/cross/entry.py) L181–208 能收 `CrossStartInput` | 仅取 goal/scenario，constraints 不进入状态；幂等摘要也只有 goal。**modules/cross 提供**。 |
| 生日业务 | [birthday.py](../../../backend/app/modules/cross/birthday.py) L306–316 收到本次金额后生成 `bud_<user>_<month>`、固定 version=1；L675–695 登记占用 | 未按原采用记录的范围/用途/版本核验，没有省略引用时自动找适用预算；占用在冻结成功后登记，未落实契约要求的冻结前 pending。**modules/cross 提供**。 |
| 存储 | [application.py](../../../backend/app/storage/application.py) L833–917 有串行预算占用登记/更新/查询；按同预算编号统计各版本未关闭占用 | 没有 `AdoptedBudget` 的保存、active/superseded 改版、按主体/轮次/范围读取能力。现有模块也没有保存采用记录。**backend/app/storage 提供**。 |
| 生日装配 | [birthday_runtime.py](../../../backend/app/agent_platform/birthday_runtime.py) 从业务 BirthdayPlan 准备银行参数，未重写 budget_id/version | 不负责选择适用预算或判断业务额度；不会在此目录伪造采用记录。 |

代码检索 `rg -n 'AdoptedBudget|adopted_budget|adopt_budget|budget_adoption|active_budget' backend/app` 在本基线仅命中公共模型/导出/契约测试；`ApplicationStore` 的 budget 方法只有 register/update/list_budget_commitment(s)。这不是“已有存储只缺一个调用”的情况。

现行规则已明确：[公共契约 §5.4](../../../docs/contracts/公共契约-2026-09-23.md#54-联动模块入口与返回06) L341–349：真实采用后才有 budget_ref；改范围/用途/限额需新版本；服务端核实适用范围；省略引用不可绕过；本次上限与个人预算同时生效；冻结前 pending；未知保留；跨版本占用及消费不双算。此处仅核对已批准需求，不新增业务规则。

## 本轮最小真实复现

用本 worktree 的独立虚拟环境与 `TemporaryDirectory(prefix='budget-wiring-probe-')`；复用 `test_birthday_runtime_wiring.composition` 装配真实 entry/银行/安全门，模型构建为 NoopModel，**模型调用 0 次、银行写入 0 次、无 HTTP/页面**。

1. `entry.start(trusted, CrossStartInput(request_id=uuid4(), goal='给妈妈过生日', scenario=BIRTHDAY, constraints=CrossConstraints(budget_ref=BudgetRef(budget_id='adopted-budget-probe', version=7), budget_fen=50000, payer_account_id='A1', deliver_by='2026-10-30T18:00:00+08:00')))`。
2. 返回 waiting_input，仍要求本次生日预算；保存状态为 `phase=budget / budget_id=None / budget_version=1 / budget_limit_fen=None / deliver_by=None`。
3. `entry.resume(trusted, {'text':'500元'})` 后，状态是 `budget_id=bud_U1_2026-10 / budget_version=1 / budget_limit_fen=50000 / deliver_by=None`，原引用及 version=7 均未使用。
4. `dir(runtime.application)` 中含 budget 的公开方法仅为 `list_budget_commitments / register_budget_commitment / update_budget_commitment`。

传入引用为探针，不是假装已有采用记录；正确行为至少应核验/拒绝该引用，而不是丢弃后另造 version=1。复现仅证明输入被丢和持久能力缺失，不宣称已测试任意预算绕过后的付款。

## 交中控拆出的最小依赖（建议，未建票/未领取）

1. **storage 独立平台票**：复用既有 AdoptedBudget，提供受控采用/改版持久记录与当前用户/轮次下的读取；明确采用记录、source_task 与版本关系，重置及重开数据库可复现，跨主体拒绝。范围/用途匹配与限额判断仍由 cross 决定；现有占用接口复用，真实不足才扩充。没有新业务决定时按现行契约，不借机新增通用预算框架。
2. **modules/cross 独立业务票**（依赖 1，顺序接在 business05 之后，避免同目录并行）：保留 CrossStartInput constraints 并纳入请求冲突检查；落实原交互采用/修改/拒绝、服务端适用预算核验/省略查找及任务绑定；保留真实版本；按真实 L01 消费与未结占用核对剩余，冻结前 pending、未知只回查，跨版本/同交易不双算。本次生日上限与个人限额分别保留。缺失/过期/他人引用、范围不符、重叠用途、修改版本、并发、未知及停止均需验证。
3. **沿用原 cross E2E/03**：待 1、2 合入后，验证真实生日采用预算/版本变更、同预算并发、未知回查及限定收尾；不以平台12超时回归或 business05 的真实视图代替个人预算验收。

不预占下一平台/业务票号（中控及其他工作线可能同时追加），由中控核对最新 main 后正式拆票；不改总进度，不接管 platform11/business05。当前不是契约字段/新 HTTP 的能力缺口；若实施中发现真实公共能力不足，再按单目录补依赖。
