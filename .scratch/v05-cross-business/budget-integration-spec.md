# 个人预算进入生日办理：business/06 设计

Status: review_pending — 2026-10-25 仅规格、实施票和测试框架；禁止据此自动实施。

Owner / planning assignee: Erwin 授权执行对话 01a17183-271b-7663-9517-f31a994de51d。

Implementation directory: `backend/app/modules/cross/`。

来源：[工作组规格](spec.md)、[生日 PRD](../../docs/prd/06-跨场景联动-PRD-2026-09-23.md)、
[公共契约 §5.4](../../docs/contracts/公共契约-2026-09-23.md#54-联动模块入口与返回06)、
[storage 交接](https://github.com/DrErwin/hackerthon-bank-agent/blob/codex/v05-adopted-budget-storage/.scratch/v05-adopted-budget-storage/handoff.md)、
[预算缺口](https://github.com/DrErwin/hackerthon-bank-agent/blob/codex/v05-platform12-birthday-response-loss/.scratch/v05-cross-platform/research/birthday-budget-gap-2026-10-25.md)。

## Problem Statement

用户的“本月总消费最多 3000 元”和“这次生日最多花 500 元”是两条不同约束。
当前生日入口丢失 constraints，内部以用户和月份另造编号、版本固定为 1，且冻结后才登记占用。
这不能证明用户采用过个人预算，也可能漏掉其他任务正在使用的额度。

## Solution

用户明确采用个人预算后才保存生效引用；生日任务核实适用账户、消费日期、用途和活动版本，
即使调用方省略引用也查已有预算。每次承诺前刷新账单并先预留额度，银行未知时保留预留，
核实消费后按交易编号消重，只有确定未使用且已释放的部分才退回额度。
购买、确认/验证及限定释放仍走已有生日路径，不把“采用预算”变成动钱授权。

## User Stories

1. 用户已给的预算、日期、账户、配送引用不被丢弃，缺项仍明确追问。
2. 同一请求完全重放返回原任务，改了预算引用、版本或约束时明确冲突。
3. 用户看到个人预算的账户、期间、用途、限额、真实已用与剩余，再选择采用、修改或不采用。
4. 用户修改候选后需要重新采用；旧按钮不能采用新快照。
5. 用户不采用新候选时不生成引用；已有适用预算仍有效，不能用“不采用”绕过。
6. 采用结果在崩溃/重开后可追溯，重放不重复建预算或复活旧版本。
7. 生日省略引用也服从已有适用预算；他人、旧轮次、旧版、不适用引用不能放行。
8. 用途不清或多个候选重叠时先澄清，不自动挑额度最多的预算。
9. 本次上限、个人剩余和其他任务占用分别显示；冻结并不等于消费。
10. 两个任务竞争同一预算时，只有额度足够的一方获得预留；待确认和未知的占用不会凭空消失。
11. 相同交易从“已核实待入账”变成账单已用时只算一次，不重占也不漏算。
12. 改版、跨月、查询失败、取消或安全停止后，不新增未经核对的购买，仍允许原操作核实及限定收尾。

## Implementation Decisions

### 1. 输入与请求幂等

- 保留完整已校验 CrossConstraints，以服务端生成的规范化快照纳入请求摘要；不再只摘要 goal。
  摘要至少含 goal、显式 scenario、constraints 的全部有效字段及引用版本，排除 request_id 本身。
  同义的缺省/None 统一处理；不因字典键序差异冲突，不擅自改写金额、日期、用途或账户集合。
- 兼容 StartTransferInput 的生日自然意图入口：没有显式约束时继续询问；不能从 goal 数字直接生成生效预算。
  不扩大减支/养老金的行为，旧不支持的 scenario 不增加购买副作用。
- birthday budget_fen 是本次上限；personal_limit_fen/scope/purpose 是个人预算候选；budget_ref 是待核实引用。
  明确本次上限为 0 时零写入，不能当作“未提供”后默认 500。配送原文仍不进聊天/检查点。
- payer_account_id 必须来自本人账户公开事实；delivery_ref 走原受控绑定核验；既有合法条件不反复索要。
  deliver_by 保留原时间精度，不把送达月份当作付款/消费月份。

### 2. 真实采用：cross 校验原交互和快照，storage 只守持久一致性

本票仅在生日目标中补个人预算子流程，不增加第四个产品入口，也不借 legacy budget 枚举启动购买。

显示候选前，保存不可变的候选快照：scope、purpose、personal_limit_fen、当前 plan_revision、
interaction_id、三种服务端选项与候选摘要；账单消费和时间仅为当次展示事实，后续要刷新。
候选 BudgetView 为 adopted=false / budget_ref=null。修改候选重签交互，不沿用旧选项。

采用前的核验顺序：

1. 可信 user/round/task/session 通过原 Harness；另核验后台持久的真实 F10 采用证据。
   不接受模型提供的身份、adopted 或 BudgetRef 生成结果。**当前此来源证据缺失，列平台前置，未解决前不实施采用。**
2. selected option 属于检查点当前交互的服务端映射，确为 adopt；裸文本“采用”、任意 literal adopt、
   模型字段或仅存在某个 interaction_id 均不构成采用。
3. 当前应用任务结果的交互必须与检查点候选交互一致，仍为本任务等待输入；核对当前 plan_revision、
   原 scope/purpose/limit 快照及摘要全部相同。API 已核 interaction_id 不能替代这一步。
   当前 API 只转发 option_id，且模型 provide_input 也能走同一转换；选项不可猜不能当作真人来源证明。
   平台前置提供可信来源事实后，cross 才同时核对来源事实、当前选项和持久快照。
4. 在同一次验证读取的来源任务 revision 下构造 AdoptedBudget；source_task_id 是实际发生此次采用的本任务，
   不能冒用另一个任务的历史快照。expected_task_revision 不是 plan_revision，也不是 F10 授权。
5. 调用 storage.adopt_budget；冲突就刷新/澄清，不换编号、增加限额或重填最新 revision 强行重试。

动作及结果：

| 选择 | 当前任务的行为 | 生效记录 |
|---|---|---|
| adopt | 通过上述核验后保存，准确读取返回记录并核对 active | 初次 version=1；改版沿同 budget_id、previous_version=原活动版、新版=旧版+1 |
| modify | 修改候选、显示完整新快照、签发新交互，等待再次 adopt | 未再次采用前不改生效版本，也不扩额度 |
| decline | 不保存新候选，不产生 BudgetRef | 已有适用 active 预算不被撤销；用户仍要求新约束时继续澄清或停止 |

对于改版，新交互必须重新展示原预算编号、原版本与完整新快照。不得以新 budget_id 绕开旧占用。
来源任务存在、revision 一致、候选看起来相同，都不足以替代真实 adopt。

**平台前置的最小输入输出（不在本票跨目录实施）**：已认证用户从专用 F10 提交 request_id、
task、interaction 和采用 option；后台生成绑定 user/session/round/task、原交互/选项、来源任务版本、
源计划快照标识与唯一输入请求的不可由模型伪造的事实。建议存于平台受控任务快照，cross 只读后
核验与自己的原计划快照相同；存放方式与原子/重放实现由平台票确定并给稳定接缝。
聊天/模型 continuation 不得生成该证明，也不能只传一个可伪造的 source='human' 字段。
缺失、失效、异快照、异主体证据均不 adopt；精确重放只认已有原采用结果。
这项输入需求交中控另派 API/platform，不占其票号、不修改 #293，也不把 storage revision 当授权补丁。

### 3. 采用重放与崩溃窗口

- 真正的 adopt 核验通过后，先在受控检查点保存 adoption_attempt：不可变 record 全部字段、
  原任务 revision、原计划/交互/快照摘要、稳定 budget_id/version/adopted_at，然后才调用存储。
- 原采用精确重放使用同一 record 和原 expected_task_revision，不能重新生成时间、UUID 或版本。
  结果写回检查点/任务后重复 F10 返回原结果，不再写第二条采用。
- 存储已成功而任务尚未发布的中断，恢复仅核对原 attempt 与准确引用、补发原结果；没有原 attempt
  证明的历史交互不能借 storage replay 分支变成新采用。
- 已 superseded 的历史重放保留历史状态，不重新激活、不自动绑定为当前预算；新写仍要求当前真实交互。
  未完成保存且来源任务已改变时回到新交互，不把旧 attempt 的 revision 改成当前值继续写。

### 4. 适用查找、任务绑定与版本

- 每次都从可信主体查候选：显式引用用 get_adopted_budget 精确读取并核对 active；省略引用仍用 list_adopted_budgets。
- 核对实际付款账户属于 scope.account_ids，真实预计付款时间处于半开区间 [start_at,end_at)，用途明确匹配；
  消费以银行真实 occurred_at 为准。生日/送达日期不替代消费日期，跨月不自动继承。
- purpose 是约束适用说明，不是 L01 的消费过滤器。L01 scope 只有账户和期间，used 始终取该 scope
  的全部消费净额。若用户要求“仅生日类别”等当前模型无法准确表达的统计口径，先说明并澄清，
  不能靠商户/摘要字符串过滤成较小的 used，也不能偷偷换成全消费口径后采用。
- 0 条适用：没有要求个人约束时仅执行生日上限；仍要求但尚未采用时停在澄清。1 条明确适用：绑定准确 BudgetRef。
  多条/用途含糊：展示真实范围、用途和限额，澄清实际适用范围，不提供“选更宽松限额”捷径。
  澄清后仍重叠就保持等待，不自行决定叠加规则，不静默忽略其中一条。
- 绑定保存在生日 task 的受控状态：原引用、已采用快照、实际账户、个人约束与本次上限分别保存。
  无已采用个人预算时不伪造用户月度 budget_id/version 或 BudgetView.adopted=true。
  BirthdayPlan 的个人引用可为空；已核对现有平台只消费 freeze_amount/account/delivery/items，
  不要求借修改平台来伪造个人预算。若接口核验出现真实差异，回报提供方，不跨目录修改。
- 方案采用前、恢复后、每次新增资金承诺前重读 active 版本与 L01。引用失效/改版/账户或时间不适用：
  停止新增承诺，显示变化并回到当前任务重新澄清/采用；不自动跳到最新版。
  旧版未结占用仍计入同 budget_id，既有成功订单不重做，原操作查询/限定释放不被新版本拦住。
- 每次新的订单/核销也检查适用性，不能以“已经冻结”为由跳过。原先没有个人预算、冻结后另一任务
  新采用了适用约束时，先暂停；若继续原任务，须明确绑定并以真实未消费冻结登记该预算的占用，
  核验不通过只允许原操作核实/收尾，不把已有冻结伪装为该个人预算早已批准的承诺。
- 新快照改变银行动作参数时必须重新确认/验证；预算 adopt 不能替代资金确认，也不能通过清本地 pending
  就宣称已废止安全侧的旧记录。无法确保旧动作不会执行时先停止新增动作，交原安全/平台接缝核查。

### 5. 账单事实、双限额与消重

- 在原 scope 使用 bills.summarize 的公开、已注册能力，显式请求 summary；核对准确 scope、
  全部 source_as_of 和 as_of。不能复用当前通用骨架固定“上月”的账单步骤。
- 对需要与 settlement 交易逐笔核对的同一 scope 使用“summary A → details → summary B”（details 不带类别过滤）。
  三次主体、账户集、期间和覆盖完整性必须一致；source_as_of 分别保留并核对先后，不要求自然增长的时间戳相等。
  当前 Demo 的同轮次账本只有追加、没有修改/删除历史流水的公开操作；需同时确认 A/B 的 transaction_count
  及各真实汇总金额不变、details 完整笔数相同，才能用中间 details 的编号核对该汇总的消费集合。
  任一不一致本轮暂停，下一次重新查；不得按摘要/价格自行重算另一份账单，也不无限循环刷新。
  若银行不保证这一读窗的历史追加语义，则在同快照公开接缝提供前停止新增承诺，不能声称读窗原子化。
  这是消费消重的事实需要，不用内部账单表或私有业务状态代替；银行外部的新支出仍受契约明示边界约束。
- used = summary.consumption_net_fen；remaining = personal_limit_fen - used（可为负数）。
  BudgetView 的 remaining 不扣占用；占用与可新增承诺额另行说明，不能改公共字段含义。
- 有效占用 O：同 budget_id 所有版本未关闭记录的 unconsumed，含本任务，含 pending/active/unknown。
  已核实且已在本次完整账单中的消费不再保留为 unconsumed；按 transaction_id 做集合核对，不用操作次数或商品价推算。
- 已核实但尚未出现在当前完整账单的消费 G：以真实 CaptureReceipt 的交易编号/金额及原操作关联逐笔证明，
  在账单出现前继续约束新增承诺；账单出现后从 G 移入 used，不能两边同时计。
  包括已 closed 记录中尚未对上的真实消费，不能因收尾结束就丢掉账单时差保护。
- G 仅包含确实属于当前采用 scope 的消费；旧版本在别的月份/账户已发生的消费不永久计为 G。
  用完整 L01 details 中的实际 account_id/occurred_at 核对；必要时对原采用 scope 请求公开 details
  查原交易。原 scope 完全不相交可排除；部分重叠而缺少实际交易归属时暂停，不能猜归属或将缺失当0。
  与此不同，O 仍按契约汇总同一 budget_id 各版本尚未关闭的 unconsumed，不能因旧 scope 而丢在途占用。
- 为可恢复核对，commitment.operation_ids 保存原冻结及每笔核销 operation_id，settled_transaction_ids
  只保存银行核实的真实交易；原任务保存对应安全脱敏回执/金额。跨任务的可用主接缝是
  ApplicationStore.get_task(可信 user/round, commitment.task_id) 中本模块的公开 ModuleResult/CrossTaskView：
  只取 succeeded 的 bank.capture_frozen 行，用 operation_id、result_ref（transaction_id）和 amount_fen
  与 commitment 交叉核对，不重复取汇总行，不读取别的业务私有状态。
  这个公开投影证明交易/金额，不单独证明交易属于当前账户/期间，归属仍按上一条核对。
  #289 的 BirthdayPorts.requery 仅查当前 task 的 _actions，不能在任务B用任务A的编号，或伪造 TrustedContext.task_id。
  缺少完整可信事实时保留约束、暂停新增承诺，提示回原任务通过受控入口查询后再刷新。
  若必须从当前任务直接读另一任务完整 CaptureReceipt，则另列平台可信查询前置，不能假称本票已有此接口。
- 新增个人预算承诺 C 必须满足 C <= remaining - G - O。
  使用 register_budget_commitment 时 max_in_flight_fen = remaining - G；由其事务把其他和本任务的有效
  unconsumed 加上本次新 pending 再比较，不能先从 max_in_flight 再减 O 造成重复扣减。
  原 commitment 精确重放沿用稳定编号，不登记第二份；仅缩减未提交方案可复核后下调，不通过 update 增额绕过登记。
- 同时满足生日上限：已核实本次消费 + 本次未消费承诺 + 新增承诺不能超过生日 budget_fen；
  商品合计也不得超过本次上限。冻结金额保持用户本次确认的上限，不偷偷缩成商品合计。
  例如个人3000、已用2600、其他未消费占用100，最多新增300；本次上限500需用户调整，不自动冻结300。

### 6. 同预算并发与当前运行边界

当前公开 Demo 启动说明明确 --workers 1。仅依赖 storage 的 sum(unconsumed) 不够：
任务A消费落账后将占用从500降到301，任务B若还用付款前的剩余额度600登记200，会漏掉刚消费199。

本票在 cross 内使用最小的 (user,round) 串行临界区，所有候选发现、首次采用/改版、刷新与消重、
pending 登记、settlement 状态更新、资金新写前的版本复核及有界 ports 提交共同遵守。
不仅锁已知 budget_id：否则任务A查到无适用预算时，任务B可用新编号并发采用，造成省略引用绕过。
不跨用户等待持锁；ports 返回 verify_wait/unknown/失败或成功后即退出，确认/验证交互不持锁。
实际银行写入可能尚在途，但原 pending/unknown 在锁外继续占用；结果核实和更新重新进同一临界区。
存储的原子 register 仍是最终额度登记，不用仅进程字典取代它，不在 cross 执行 SQL/迁移。

本票的并发验收覆盖同一受支持进程内两个 task/两个数据库连接的真实交错，包含“无候选→并发首次采用”，
不宣称多进程原子预算。
若装配改为多 worker/多主机，或另有写入方绕过此业务入口，实施须先停并向 storage 提交最小原子接缝需求：
在同一预算串行事务中校验活动版本、消费/占用快照世代并登记增量 pending；本票不自行增加它或私设分布式锁。

### 7. 冻结前 pending 与恢复/停止

| 时点/结果 | 受控业务记录 | 可继续的动作 |
|---|---|---|
| 确认/验证后将尝试冻结 | 先刷新校验，持久 pending、稳定 commitment_id 和原 freeze operation_id | 只有持久成功才调用 freeze_execute |
| 仍需验证 | 保留原预留/原操作；不持锁等待用户 | 原验证或取消，不新建承诺 |
| 冻结成功 | 同记录变 active，绑定真实 freeze_id | 原计划已确认动作 |
| 冻结未知 | 同记录 unknown；原金额继续占用 | 仅查原操作，不能先释放或重冻 |
| 明确拒绝/证明未提交 | 核对原执行/银行事实后关闭未消费 pending | 不把查询失败/not_found 单独当未执行证明 |
| 核销成功 | 记原操作、真实交易和金额；只将对应消费从未消费占用转为 G/账单事实 | 下次新动作仍刷新、消重 |
| 核销未知 | 不减少占用，不填已消费成功 | 原编号核实 |
| 取消/安全停止 | 持久 stop_reason，禁止新增购买 | 未知先查，之后只做限定收尾 |
| 释放未知/被拒 | 保留未消费占用、非结清状态 | 原释放查询/限定重查，不重买 |
| 释放核实成功 | 只撤销确实已释放的未消费部分；真实消费关联仍可查 | 保留实际成功事实，终态由事实决定 |

调用银行前先保存 submission intent 与原 operation_id；崩溃后不凭“本地没有结果”撤销预留。
采用后版本变化、刷新失败或限额不足时不新增承诺，旧占用不变；清理原冻结仍沿 #288/#289 已核实停止路径。

## Testing Decisions

本轮只制定框架，不写测试代码、不运行测试、模型或银行。核心关联 XL-B07，回归 XL-B01/B03/B05/B06、XL-X02—X05。
详见[验证矩阵](budget-integration-tests.md)。实施后的主要观察点为 CrossEntry/Harness 公开入口及其
ModuleResult、真实 ApplicationStore 采用/占用记录、账单公开结果和银行原操作事实；不直接测试私有分支。
F10 采用必须经过真实任务结果/交互，不能用任意 record 预塞 storage 后冒充已验证用户采用。
账单/存储/安全/银行接入的替身证据、真实组件、HTTP/模型/页面 E2E 分层记录。

## Out of Scope

本轮不实施、不执行测试，不改 PR #288，不改 storage/contracts/API/platform/security/frontend/evals，
不改共享项目跟踪、completion 或包总状态。不新增独立预算产品、自动提额、自动退款/撤单、跨月套用、
类别/商户预算、多 worker 预算保证或新的长期记忆授权。页面与完整生日 E2E 复用既有下游票。

## Further Notes

设计基线 origin/main `fd6cd703846a9614e32cff1434fdfe343fdd18c8`；PR #293 草稿头
`d0ae73ee3f46a21595311dc236e744b241132652` 的接口已读取，未合入、未把其全量运行当通过。
实施须等待 #293 实际验证/合入与中控明确续派，也需 #288/#289 的对应业务/未知恢复能力就绪。
还需平台真实 F10 采用来源证明：这是接口核查发现的技术前置，不是新增未裁定业务规则；
当前仅 option_id 的 cross 输入不能完成该证明。未拿到稳定接缝前不得把本票改成可实施。
测试接缝来自中控已指定的真实采用、公开能力及占用边界，不扩大成新的平台工程。
2026-10-25 已读取 to-spec/to-tickets；二者 disable-model-invocation，按文件手工执行，不声称调用斜杠命令。
团队 skill 来源基线 d81f3a183412e71a5b1e84ca21bc1a35eea03a60，本轮不更换来源。设计审查结果另记。
