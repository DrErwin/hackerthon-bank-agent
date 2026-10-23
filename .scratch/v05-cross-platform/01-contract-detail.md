# 票 01：字段、状态、兼容与验收详稿

Status: proposed — 2026-10-24；对应[业务裁定稿](01-decision.md)。D1、D2 业务要求已获 PM 确认；本文件的具体字段与接入方案仍是待确认的契约差异材料，不替代 [docs 中的公共契约](../../docs/contracts/公共契约-2026-09-23.md)。未编码、未做模型校验或 E2E。

核对基线：`07741a5`。引用 [common](../../backend/app/contracts/common.py)、[platform](../../backend/app/contracts/platform.py)、[tasks](../../backend/app/contracts/tasks.py)、[api](../../backend/app/contracts/api.py)、[bank](../../backend/app/contracts/bank.py)、[银行字段附件](../../docs/contracts/银行接口字段-2026-09-24.md)。金额为严格整数分，时间为带时区时间戳；标记 `?` 表示输入可省略，`null` 表示没有确定事实，不用零或空串冒充。

## 1. 现状、最小改动与提供方

| 对象 | 核对结果 | 票 01 的模型工作 | 后续实际承接 |
|---|---|---|---|
| CrossTaskView / BudgetView 等 | 文档已有，公共 Python 模型尚无 | 落地现行字段，补本稿确认后的增量 | cross 业务及平台/API |
| TaskStatus | 已含 running、waiting_input、waiting_approval、succeeded、partially_succeeded、failed、cancelled、needs_attention | 原样复用，不新增枚举 | 父状态映射由 cross/平台实现 |
| ModuleResult / TaskView | 既有交互校验；TaskView 已支持 module=cross | 复用外壳，新增字段放 CrossTaskView | API 票 04 校验/输出真实 cross 数据 |
| 可信 parent_task_id | 已有，但账单来源继承也在使用 | 保留旧字段含义，不靠模型填可信身份 | 平台票 03 区分组织父子关系与账单来源关系 |
| 配送输入 | api.py 已有 DeliveryDetailsFields、SubmitDetailsRequest(kind=delivery)、DetailsResponse；F36 文档已有受控入口 | 不重复建一组前端输入模型或新路由 | API 票 08 接通现有 delivery 分支，前端另接表单 |
| 生日银行模型 | B10—B13/B20—B22 文档已定义，bank.py 未实现相应结构；B14 外壳已有 | 按现行银行字段落模型，复用现有返回外壳 | 银行存储票 06、服务票 07 |
| 模块实际启动输入 | Harness 当前仍通过 StartTransferInput 适配调用 | 提供 CrossStartInput 等准确输入，保留旧业务类型 | 平台票 03 适配不同能力输入，不在票 01 改注册/运行代码 |

票 01 只改公共模型及必要契约说明/样例；不把父子调度、数据库事务、安全执行或银行判断塞进模型验证器。缺少当前用户、银行事实或持久状态时，模型只能验证形状，不能证明权限、可用余额和执行资格。

## 2. 入口与候选约束

### 2.1 CrossStartInput

| 字段 | 类型 / 必填 | 含义与检查 |
|---|---|---|
| request_id | RequestId，必填 | 同请求编号由服务端检查内容冲突；模型不负责幂等存储 |
| goal | 非空 string，必填 | 用户生活目标；不得把空白当有效目标 |
| scenario | CrossScenario?，默认 null | 允许模型识别或澄清；不能默认生日 |
| constraints | CrossConstraints?，默认 null | 用户提供或模型提出的候选参数，不能携带已采用/已授权标记 |

`CrossScenario` 建议为 `monthly_arrangement | expense_reduction | birthday | budget | income_distribution`。前两项为新增，birthday 沿用；后两项保留旧调用含义。产品展示仍只有三个生活目标，旧 budget 是预算子目标，旧 income_distribution 是不额外引入退订的分配子目标。

不提供静默别名把 income_distribution 改成 monthly_arrangement。无 scenario 时由实际目标识别；未知枚举按非法参数拒绝，合法场景尚未实现时由能力层明确报告不可办理。模型通过不等于能力已注册。

### 2.2 CrossConstraints

沿用既有平铺结构，避免为尚未实现的旧消费者新增多层转换。各字段均可缺省；显式给出非法结构则拒绝，业务必需信息尚未提供则在运行时等待输入。

| 字段组 | 字段及类型 | 规则 |
|---|---|---|
| 生日（已有） | recipient_hint:string?、recipient_ref:ID?、birthday_on:日期?、deliver_by:Timestamp?、delivery_ref:ID?、budget_fen:Money?、budget_ref:BudgetRef?、preferences:string[]? | 配送仅传引用；冻结前预算及必要条件由业务补齐；生日采购需正金额，零预算可以只查询/解释，不能提交零冻结 |
| 个人预算（已有） | scope:BillScope?、personal_limit_fen:Money?、purpose:string? | 与生日单次预算不同；用户采用后才生成 BudgetRef |
| 分配（已有） | payer_account_id:ID?、income_transaction_ids:ID[]?、income_hint:string?、allocation_rule_ref:ID?、allocations:Allocation[]? | 收入交易编号不等于仍可花的余额；目标身份仍需业务核实 |
| 本月安排（新增） | funds_basis:available_balance\|selected_income?、arrangement_amount_fen:Money?、living_reserve_fen:Money?、reserve_includes_known_debits:bool?、upcoming_debit_scope:BillScope? | funds_basis 或留存口径缺失必须澄清；false 表示已知未来扣费另留。可安排金额采用后不能由模型随余额变化自行扩大 |
| 减支（新增） | comparison_scope:BillScope?、selected_subscription_ids:ID[]? | scope 表示调查范围；对照期须同账户集合；选择签约只是意愿，仍要逐项确认 |

非 null 的 ID 数组不得重复。显式 `funds_basis=available_balance` 与收入限定 ID 同时出现是矛盾输入，按 INVALID_ARGUMENT 拒绝本次矛盾输入，不替用户选一种；selected_income 但尚缺交易 ID 可以进入查询澄清。未指定 funds_basis 的旧 income_distribution 继续按旧收入分配流程解释，不从新字段缺省推导自动转走当前余额。

不新增 `authorized=true`、`adopted=true`、`success=true` 等输入字段。所有这些服务端状态不能从模型候选复制。

### 2.3 Allocation（现行含义落模型）

字段：destination=`transfer|retain`；target_account_id:ID?；payee:PayeeInput?；amount_fen:Money?；ratio_bps:整数 1..10000?。

- amount_fen 与 ratio_bps 必须且只能填一个；transfer 的 target_account_id 与 payee 必须且只能填一个；retain 两者均不填。
- transfer 的确定金额须大于零；retain 金额可为零但不产生交易。比例和尾差按公共契约 §5.9，由业务程序统一算出最终确认金额。
- 同一候选的比例模式/金额模式一致性、总额与留存约束由业务核对。模型形状有效不证明银行允许转账。
- PayeeInput 的 manual 分支仅限受控后端路径；不能因公共模型能表示它，就把完整账号放进模型提示或前端普通结果。

## 3. 本次安排、预算与持久记录

### 3.1 ArrangementView（新增、服务端生成）

| 字段 | 类型 | 含义 |
|---|---|---|
| arrangement_id | ID | 服务端分配的候选/采用记录标识 |
| plan_revision | 正整数 | 关联当前方案版本 |
| payer_account_id | ID | 本次资金来源 |
| funds_basis | available_balance / selected_income | 用户选定的范围解释 |
| income_transaction_ids | ID[] | selected_income 的已核实来源；当前余额模式为空 |
| base_fen | Money | 用户本次明确拿来安排的金额，不随模型建议自动扩大 |
| living_reserve_fen | Money | 用户明确留存的生活费 |
| reserve_includes_known_debits | bool | 已知扣费是否包含在生活费内 |
| upcoming_debit_scope | BillScope | 明确预留的未来期间和付款账户，区别于历史账单调查范围；只包含已知下一期事实，不推算未知扣费 |
| known_debits_fen | Money | 对指定期间、已知仍有效签约确定的预留额，不声称覆盖所有未来支出 |
| protected_fen | Money | 口径为 true 时等于 living_reserve_fen；false 时为其加 known_debits_fen |
| distributable_fen | 有符号整数分 | base_fen − protected_fen；负数表示方案不满足要求，不能擅自降低留存 |
| facts_as_of | Timestamp | 本次核对事实的保守截至时间，不能伪装银行原子快照 |
| adopted | bool | 服务端依据当前交互记录填写，模型不能设定 |

个人预算引用仍由 BudgetView 表达，不把 ArrangementView 当成银行冻结或长期余额保证。已执行/未知金额由实际步骤和操作记录核对，不能仅依赖这个展示快照继续转账。

新持久记录 `AdoptedArrangement` 保存：arrangement_id、user_id、demo_round_id、source_task_id、plan_revision、上述已采用参数快照、adopted_at:Timestamp、adoption_interaction_id:ID、status=`active|superseded|closed`。它是本次约束记录，不是执行授权；参数发生实质变化重新采用，原在途动作不能因旧版 superseded 就丢失。

候选生活费之外另留的代扣，必须明确 upcoming_debit_scope；查询只能证明已知签约的下一期等已提供事实，不能把未提供的未来周期自动展开成确定债务。事实不足时等待澄清/核实，不用零造出可执行分配。

依照已确认的 D1，存储还须支持以 user_id/demo_round_id/account_id 唯一核对活动资金安排，并保留其 task_id/arrangement_id 和关闭状态。这是应用协调记录，不写入银行冻结余额；持续保护的范围以 D1 为准。提交前刷新及登记的事务边界由票 02/03 和受控执行接缝落实，不能只用一个字段假装已解决并发。

D1 的活动归属在用户采用时原子核对并取得：其他任务可继续查询和规划，但不能取得该账户另一份活动资金安排。相同父任务重试/改版沿用原归属，不重复占用；合法子动作由服务端父子关联识别，不能靠模型传 parent_task_id 获得例外。未知或收尾未核实不关闭记录，不按聊天超时自动解锁；演示重置按轮次清理。

若另一份联动安排占用该账户，当前父任务进入 waiting_input，由父自身交互给出“换付款账户 / 重新检查 / 停止本次安排”；重新检查只读活动记录并刷新事实，不是重新提交资金动作。本期不设置自动排队。普通转账等其他应用入口若遇冲突，由统一受控入口在提交前返回应用侧 ModuleError(code=ARRANGEMENT_CONFLICT, source=platform, field=payer_account_id, upstream_code=null)，reason 使用脱敏说明，不伪装成银行拒绝；其前端/任务能否正确展示需提供方验证。D1 如需修改已有安全、转账或前端的错误处理，由对应负责人追加明确依赖，本票不得宣称既有代码无需适配。

### 3.2 BudgetView / BudgetRef / AdoptedBudget / BudgetCommitment

严格沿用主契约 §5.4 的现有字段：

- `BudgetRef`：budget_id:ID、version:正整数。
- `BudgetView`：budget_ref:BudgetRef|null、purpose:string、scope:BillScope、personal_limit_fen:Money、used_fen:有符号整数分、remaining_fen:有符号整数分、facts_as_of:Timestamp、adopted:bool。remaining=limit−used；负数保留。
- `AdoptedBudget`：budget_id/user_id/demo_round_id/source_task_id:ID、version:正整数、scope、purpose、personal_limit_fen、adopted_at:Timestamp、adoption_interaction_id:ID、status=active|superseded。
- `BudgetCommitment`（为既有记录命名）：budget_ref、task_id、commitment_id、committed_fen、unconsumed_fen、freeze_id:ID|null、operation_ids:OperationId[]、settled_transaction_ids:ID[]、state=pending|active|unknown|closed、updated_at:Timestamp。

服务端读写这些记录。预算模型检查金额关系和字段形状，不验证采用交互的真实性；真实采用、范围/版本和其他占用由业务及存储核实。跨版本旧在途占用仍计入同一 budget_id；消费已入账后不得在已用和未消费占用中双算。

## 4. 父任务、计划和子交互

### 4.1 CrossTaskView / CrossStep

保留所有旧字段：CrossTaskView 的 scenario、plan_revision、steps、budget、summary；CrossStep 的 step_id、action、child_task_id、operation_id、status、amount_fen、order_id、payment_status、result_ref、error。

仅新增以下可选字段；旧载荷缺省时仍可解析，不需要发明新状态：

| 所在结构 | 增量字段 / 缺省 | 用途 |
|---|---|---|
| CrossTaskView | plan_step_ids:ID[]\|null，默认 null | 当前方案涉及的步骤；null 兼容旧载荷“所有 steps”，新生产者必须显式给数组。旧成功/未知步骤保留在 steps 中，即使目标变化也不能删掉资金事实 |
| CrossTaskView | active_step_id:ID\|null，默认 null | 当前正在推进/等待的步骤 |
| CrossTaskView | interaction_task_id:ID\|null，默认 null | 外壳 interaction 的真实所属任务；自己的澄清填父任务 ID，代理子交互时填对应子任务 ID |
| CrossTaskView | arrangement:ArrangementView\|null，默认 null | 本月安排视图；未形成可靠完整候选时为空 |
| CrossTaskView | stop_reason:user_cancelled\|security_blocked\|business_failure\|null，默认 null | 解释主动停止、风险终止或业务失败；不作为授权开关 |
| CrossStep | depends_on:ID[]，默认 [] | 必须先有已核实结果的前置步骤；按当前业务要求检查成功条件 |

本票模型应校验：step_id 唯一；plan_step_ids/active_step_id/depends_on 引用存在；无自依赖和环；数组无重复；操作编号满足原类型。尚未启动步骤 status=null；付款未知 payment_status=null，不能自填 unpaid。

**不由模型验证器决定**：该前置是不是已经满足、是否允许启动后继、是否有权操作 referenced task、是否成功付款。静态引用有效不代表真实业务/权限有效。

### 4.2 交互路由与版本

父级继续返回 `ModuleResult<CrossTaskView>` / `TaskView<CrossTaskView>`。waiting_input 需要 input 交互，waiting_approval 需要 confirmation 或 verification 交互，遵守现有外壳校验。

等待子交互时，父页面呈现**原子交互的原 ID/record_ref**，`interaction_task_id` 指向真实子任务；确认、验证、补充输入仍提交通用 API 的该子任务路径。父自身方案采用/澄清则提交父任务路径。父级 cancel 仍针对父任务，不能仅取消一张展示卡而让后继继续。

平台核对 child_task_id 确实属于该父任务、该用户/轮次，且响应属于当前步骤和参数版本。不得仅因为某个 ID 存在就放行。父与子不能分别创建两份有效确认。新前端必须读取交互所属任务；旧前端尚未适配时不开放 cross 路由。

修改候选、金额、账户、商品、配送或依赖时，新方案版本递增；成功/未知动作的原版本及参数不改写。当前未执行动作若已生成确认，应停止使用旧确认并按新方案核对，不能把“用户改了另一个字段”当成自动扩大授权的理由。无动作改变的普通解释或插入查询不生成新计划版本。

### 4.3 父状态映射（D2 业务规则已确认；具体契约映射待审阅）

按下表优先级判定，不只看最后一个子任务：

| 条件 | 父状态 | 交互及结果 |
|---|---|---|
| 有相关写操作未知、收尾未知/失败或恢复待核实 | needs_attention | 提示待核实；不推进依赖动作，不显示已结清。allowed_actions 按真实可用动作给出 |
| 当前合法步骤等待输入 | waiting_input | 原交互 + interaction_task_id；明确用户在补哪项信息 |
| 当前合法步骤等待确认/验证 | waiting_approval | 原受控记录 + 正确任务引用；聊天“好”不代替要求的动作 |
| 正在查询/执行/核对收尾 | running | 有已完成项也先呈现其事实，不能提前终结整个目标 |
| 当前目标全部达到且必要收尾结束 | succeeded | 所有结果与银行/订单事实一致 |
| 已终止剩余步骤，实际目标一部分完成且无未结事项 | partially_succeeded | stop_reason 说明原因；取消请求不掩盖已经完成的退订/转账/付款 |
| 用户取消且无实际目标完成、无未结事项 | cancelled | 不宣称退款或订单撤销；已发生但未完成目标的事实仍列出 |
| 已停止且无实际目标完成，原因是业务失败/安全阻断 | failed | 给脱敏原因和允许的下一步，不能恢复新购买绕过阻断 |

实际目标：减支是用户选定的退订；养老金是其选定退订/转账；生日是订单已付款；纯查询目标是所请求资料完整返回。生日冻结或仅下单不是目标完成。对“已付一单后叫停”采用 D2 的部分完成；未决定是否继续其余项时则等待用户输入，不直接做终态。

安全终止后是否允许 input/恢复仍按现有安全裁决，父状态映射不改变安全门。needs_attention 不是任意重试许可；终态前所有已发生的在途资金和限定收尾必须核实。

## 5. 生日银行模型：按既有接口落地

写操作共享 operation_id:OperationId 和可信上下文；业务输入模型不接受模型生成的“权限通过”。QueryResult、BankWriteResponse、OperationResult、OperationLookup、BankError、BalanceSnapshot 原样复用，不建立第二套状态。

| 接口 / 建议模型名 | 业务输入 | 结果模型 |
|---|---|---|
| B10 FreezeFundsInput | account_id:ID、amount_fen:PositiveMoney、reason:string | FreezeReceipt：freeze_id、frozen_amount_fen、remaining_fen、balance |
| B11 CaptureFrozenInput | freeze_id、amount_fen:PositiveMoney、merchant_id、merchant_name、purpose、category:Category、order_id:ID? | CaptureReceipt：transaction_id、freeze_id、captured_amount_fen、remaining_fen、balance |
| B12 ReleaseFrozenInput | freeze_id、amount_fen:PositiveMoney | ReleaseReceipt：freeze_id、released_amount_fen、remaining_fen、balance |
| B13 GetFreezeInput | freeze_id | FreezeView：freeze_id、account_id、original_amount_fen、captured_total_fen、released_total_fen、remaining_fen、as_of |
| B14 原接口 | operation_id | 原 OperationLookup 外壳，receipt 可为上述动作回执或订单回执；失败/未找到/processing 不混用 |
| B20 ListProductsInput | merchant_id:ID?、purpose:string?、deliver_by:Timestamp? | ProductList：products:Product[] |
| B21 CreateOrderInput | product_id、quantity:PositiveInt、expected_total_fen:Money、delivery:DeliveryInput | OrderResult：order:OrderView；写入外层为 OperationResult<OrderResult> |
| B22 GetOrderInput | order_id | QueryResult<OrderResult> |

以上未展开 ID 字段为 ID，金额为严格整数分，balance 为既有 BalanceSnapshot。收款/释放等动作金额为正；剩余可为零。读取快照与写回执是不同对象，原回执余额不代表当前余额。

`Product`：product_id、merchant_id、merchant_name、product_name、unit_price_fen:Money、category:Category、earliest_delivery_at:Timestamp。

`DeliveryInput`：recipient_name:string、phone:string、address:string、deliver_by:Timestamp。只在受控银行调用端使用；日志/调试 repr 不打印原文，通用模型序列化本身不是脱敏保证。F36 的 DeliveryDetailsFields 原文在后端结合已确认送达时间形成此对象，不在聊天中拼接。

`OrderView`：order_id、product_id、quantity:PositiveInt、merchant_id、merchant_name、total_fen:Money、created_at、deliver_by、recipient_name_masked、phone_masked、address_masked、payment_status=unpaid|paid、payment_transaction_id:ID|null。paid 必须有关联交易，unpaid 不得伪造交易；银行明确订单状态与应用因超时不知付款状态是两层信息。

模型可检查 FreezeView 的 original=captured+released+remaining，以及已确认订单的付款状态/交易引用一致性；是否可冻结、可释放、价格是否变化、身份/订单/商户是否匹配由银行和受控执行路径判断。B11 通用 order_id 仍按现行可选定义，生日业务实际核销必须带订单 ID，不能借可选结构绕过订单关联。

## 6. 配送与身份复用，不新增平行接口

沿用 F36 `/tasks/{task_id}/details`、SubmitDetailsRequest(kind=delivery)、DeliveryDetailsFields 和 DetailsResponse.detail_ref。cross 中的 delivery_ref 指向该受控 detail_ref，不复制明文或另一套编号；真实存储核对本人、轮次、任务及用途。

当前运行路径对 delivery 分支尚不能办理，票 08 负责接通；模型文件存在不代表功能完成。F36 结果仍返回脱敏 display_fields 和原任务，禁止在普通 TaskView、模型上下文、审计正文或 SSE 中返回原文。

parent_task_id 不从用户/模型输入赋值；当前账单来源继承不应直接改成“凡父任务皆账单来源”。平台保存父子组织关系并按已有事实来源引用处理账单范围，具体存储/接缝在票 02/03。票 01 不为解决此问题悄悄改变 TrustedContext 的旧行为。

## 7. 兼容与切换要求

1. 新增模型先独立落在 contracts；旧转账、账单、订阅的输入、任务状态和交互结构不改名、不改必填。
2. 新 CrossTaskView 增量字段有缺省；旧载荷能读，但新运行生产者必须明确填写当前计划及交互所属。不能用缺省替代对旧权限/事实的核实。
3. 旧 cross 只是文档约定，没有已运行的实现需要强行双栈；仍保留旧输入含义和读取样例，不把模型兼容声称为历史运行行为已验证。
4. 前端生成类型和新插槽属于前端票，API 输出及路由属于平台/API 票。它们尚未接通时不得开放 cross；用户无法看到/确认新结构时不能靠通用按钮勉强执行。
5. 公共模型、正式契约修订及样例须在确认后保持一致；对权限/确认/恢复、资金与隐私的修改按契约 §8 交 Ringo 审阅。未取得确认时本稿保持 proposed。

## 8. 可核对样例（文档示例，非运行结果）

### EX01：新目标缺少参数，允许先澄清

```json
{"request_id":"c591c8a2-ef32-4b2c-8b10-24bd637a4201","goal":"养老金到了，帮我安排本月的钱","scenario":"monthly_arrangement"}
```

输入结构有效，不得自动填写 1500 留存或直接转账。实际业务需查询收入、账户、签约，明确范围与去向后形成方案。

### EX02：5000 元中留 1500 元，已包含已知代扣

```json
{"funds_basis":"selected_income","arrangement_amount_fen":500000,"living_reserve_fen":150000,"reserve_includes_known_debits":true,"income_transaction_ids":["tx_pension_01"],"allocations":[{"destination":"transfer","target_account_id":"own_savings","amount_fen":250000},{"destination":"transfer","payee":{"kind":"saved","payee_id":"family_01"},"amount_fen":100000},{"destination":"retain","amount_fen":150000}]}
```

这是候选约束片段，不是执行授权；服务端核实来源和可用资金、用户采用，再逐笔确认。生活费含代扣时不重复另留；如果 false 且另留 3900 分，最多可分配 346100 分，原 350000 分转出方案应被阻止并要求调整，不偷偷修改金额。取消未来扣费也不使现有资金变成 503900 分。

### EX03：旧收入分配与非法输入

```json
{"request_id":"c591c8a2-ef32-4b2c-8b10-24bd637a4202","goal":"把这笔收入分配到另一张卡","scenario":"income_distribution","constraints":{"income_transaction_ids":["tx_pension_01"]}}
```

旧语义继续澄清分配，不自动查找并取消订阅。`scenario=anything`、负数金额、字符串金额 `"500000"`、同时提供 amount_fen 与 ratio_bps 都应在公共输入校验中拒绝。合法但超银行余额的金额则由后续事实核对/银行拒绝，不能说模型已经验证余额足够。

### EX04：子交互路由（CrossTaskView 增量片段）

```json
{"plan_revision":2,"plan_step_ids":["cancel_01","transfer_01"],"active_step_id":"transfer_01","interaction_task_id":"child_transfer_01","stop_reason":null}
```

对应外壳的 interaction 必须是 child_transfer_01 的真实当前交互。前端向该子任务提交确认，父目标保持可见；父级取消仍针对父任务。若确认属于旧参数版本，不因 interaction_task_id 字面相同而放行。

### EX05：生日结清银行事实（FreezeView）

```json
{"freeze_id":"freeze_01","account_id":"own_daily","original_amount_fen":50000,"captured_total_fen":46700,"released_total_fen":3300,"remaining_fen":0,"as_of":"2026-10-24T18:00:00+08:00"}
```

两订单需分别有关联付款交易；冻结/释放不是消费/收入。此等式正确也不能单凭 JSON 证明银行真的执行过，需由服务真实返回及后续 E2E 核对。

### EX06：部分购买后取消

花付款 19900 分，蛋糕未办。若无在途，释放 30100 分并核实后，按 D2 返回 partially_succeeded、stop_reason=user_cancelled、cancel_requested=true。若释放未知，先 needs_attention，保留原 release operation_id；不宣称资金已全部释放，也不重新购买。

## 9. 模型与后续接缝验证清单

| ID | 条件 | 预期 | 执行层 |
|---|---|---|---|
| CT01 | EX01 只给目标 | 输入可解析；运行时澄清而非资金执行 | 模型 + cross 后续 |
| CT02 | 缺 goal/request_id，空白 goal | 输入拒绝，指出字段 | 模型 |
| CT03 | 未知场景、负数/字符串金额、比例越界 | 输入拒绝，不隐式转换 | 模型 |
| CT04 | Allocation 双金额/比例、双目标、retain 带收款人 | 输入拒绝 | 模型 |
| CT05 | EX03 旧场景，旧 CrossTaskView 无新增字段 | 保留语义，旧载荷可解析，不自动增加副作用 | 模型/兼容样例；运行语义由后续验证 |
| CT06 | 未启动/未知步骤含 null；订单 paid 无交易 | 合法空事实可表达；矛盾付款结构拒绝 | 模型 |
| CT07 | 重复步骤、悬空依赖、自依赖、循环 | 拒绝结构不一致计划 | 模型 |
| CT08 | waiting_approval 无原确认/验证引用 | 沿现有外壳规则拒绝 | 模型；复用已有测试 |
| CT09 | EX02 口径含/不含代扣；改变余额或取消未来扣费 | 正确计算、重新核对采用与最终金额，无虚构收入 | 模型可核字段；算式来源和采用真实性由业务验证 |
| CT10 | 两父任务同账户争用安排，普通转账试图绕过 | 依照已确认的 D1，冲突写入暂停，查询及限定收尾允许；未知不解锁 | 存储/平台/受控执行，非模型通过证据 |
| CT11 | 已付款后取消，释放成功/未知各一例 | 按 D2 区分部分完成与待核实，不重办 | cross/平台/API/E2E |
| CT12 | 同操作号异参、同订单换号再付款 | 银行防重与范围检查真实生效 | 银行；不由模型声明代替 |
| CT13 | 配送 F36 结构、错误 kind/fields；错误用户引用 | 结构不符拒绝；归属由运行路径拒绝，原文不进模型/日志 | 模型 + API/安全后续 |
| CT14 | 同父版本旧确认、跨任务/会话/轮次恢复 | 真实授权检查拒绝或重新验证，不能只比字符串 | 平台/安全/API |
| CT15 | B10/B11/B12 零/负金额；FreezeView 余额等式；OrderView 付款关联 | 结构与已知等式检查；银行规则另测 | 模型 |

当前只完成源码/文档核对和上述样例的 JSON/文档一致性检查；CT01—CT15 均未作为运行测试执行。实现后只将实际验证的层标为通过，不能把模型测试等同完整链路。
