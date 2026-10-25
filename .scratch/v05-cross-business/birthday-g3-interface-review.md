# Cross08对生日G3的评议与内部接口建议

Status: planned / blocked — consumer_proposal，尚未达成提供方最终接口约定或取得G1/G2本人决定；不实施08/06。
Date / reader: 2026-10-25，Erwin授权的Cross消费方设计对话。
核查main `2a070b9cf992a109d8b54718a49dc3e3b56bd236`；#297已合入，本稿不整理或修改原PR。

依据：[Cross08](issues/08-birthday-quantity-and-unexecuted-revision.md)、[平台规格G1/G2/G3](../v05-birthday-platform-dependencies/spec.md)
及其01—04候选票（源f481f4b）。另完整读取本地Git对象
`bce306d07e429b8ce604dd8232fa58cd3836f0a3:.scratch/v05-birthday-security-review/review.md`；
不假定该安全评议已入main或代表本人批准。以下均为只读设计判断，未运行测试/模型。

## 1. 消费方结论

原G3方向可承接，但进入编辑必须区分以下路径，不能只检查一个“可编辑”布尔值：

| 原状态/证据 | Cross可消费的事实 | 后续 |
|---|---|---|
| 原本就在安全的input节点，没有待执行动作 | 现有原交互、服务端选项和检查点 | 沿普通F10；不伪造撤离记录，也不因此声称确认/验证编辑已覆盖 |
| 旧动作尚未claim（后台领取执行资格） | 安全02核验原attempt并永久封锁旧写入，必要审计齐备后的持久撤离证据 | 平台03受控交接给Cross；旧确认/验证/迟到授予均不能重启原动作 |
| 原下单已claim，但银行明确失败、已证明无订单且无在途 | 平台核实的原操作失败结果、无订单/无在途依据和对应不可变旧attempt | 不要求无claim证据、不删旧claim；有原编辑受理则受控交接，无则原号核实后普通新input，详见§7 |
| claim在先、未知、查询异常或仅not_found | 只有原号观察事实，不能证明可替代 | 不进入可能在途项编辑；原号核实。capture失败也不代表它的已建订单不存在 |

已建未付/已付项不可改写；仍可编辑其他证实未成单且无在途项。新input仅是重新讨论方案，
不创建新银行attempt、生成个人预算采用或放行新购买。取消、终态（含partially_succeeded终态）、
安全终止和无效会话不能借恢复复活购买；needs_attention也不是自动可编辑。

## 2. 最小内部输入输出（拟议名称，不新增公共字段）

| 提供接缝 | 最小输入 | 最小输出 / Cross核对 |
|---|---|---|
| 01→原BirthdayPorts | TrustedContext、原BirthdayPlan、服务端项快照；保留原方法名和结果形状，execute显式原号的兼容扩展见§7 | 每项有稳定item/step身份、product_id、显式quantity、服务单价、行小计和原送达/受控配送引用；平台按此下单和展示，不能product_id碰撞 |
| 04→03专用后台编辑入口 | 已认证TrustedContext及原F10 request_id/interaction_id/selected_option_id；text为空 | 平台从原任务重读绑定，不采信前端传入的item/attempt/operation/hash或editable标记；该入口不注册为模型工具 |
| 03→Cross专用进入编辑入口 | TrustedContext + 原请求的持久edit_ref；只在本次专用调用或其精确受控恢复中可解析 | 解析为下述完整绑定和一种可信proof；普通resume/text/模型字典即使知道edit_ref也不能激活它。可参考既有平台专用来源隔离方式，但不复用预算来源作为商品编辑授权 |
| Cross→03 | 原edit_ref、源已发布checkpoint_ref、隔离待发布checkpoint_ref及对应ModuleResult | 原task_id、新input交互及业务plan_revision；平台用严格原任务CAS同时发布检查点引用/结果/新task_revision；不是Cross自行宣称已发布 |

**edit_ref背后的服务端最小绑定**：user/session/round/task、原请求及请求摘要、原交互/选项、
原task_revision、plan_revision、源已发布checkpoint_ref、目标（freeze目标或稳定执行项）、attempt_id、action_name、operation_id、
action_revision、原参数引用及可读取快照、确认ID/版本、关联挑战和限定授权的历史引用/必要脱敏快照。
attempt_id在此是逻辑含义，可直接用该次operation_id表达，不要求新增第二个UUID或公共字段。
任务版本与业务计划版本不同；后续平台自有写入产生的dispatch/CAS版本须与原接受版本显式关联，不能只读最新revision跳过冲突。
冻结目标不伪造商品项；order/capture绑定相应项，capture还须关联已建订单及原创建参数。

proof为内部两类之一，**不新增公开SecurityDecision/ConfirmationDecision/任务状态**：

- `retired_before_claim`：安全方原绑定撤离记录及审计完成事实，关联原授权/挑战处理结论；Cross只能经平台核验读取，不能自写安全表。
- `verified_failed_no_order`：原create_order的确切OperationResult/operation与结果引用，以及银行语义或可信回读证明“无订单、无在途”的依据。
  仅WriteOutcome.state=failed、claim.state=completed、任意错误码或not_found均不够；证据无法提供就blocked，不能由Cross猜造。

原确认/参数快照必须在替换前可读且不可变，不能仅留会被UPSERT覆盖的confirmation_id或悬空引用。
配送原文与验证码不进入edit_ref普通展示/日志/模型。未变项身份不随全局plan_revision重建；
新同款替代项与历史项分开，新项的新attempt/确认只在其重新采用后办理；同一原项重放或查询沿原号。

## 3. 持久顺序与失败恢复

以下指已有专用编辑受理的交接；无原受理的明确失败替代走§7，不强造edit_ref。

1. 03核对原主体、当前交互/原任务阶段及原项/attempt，固定原编辑请求关联；若准备记录失败，不能开始撤离。
2. 普通未提交路线调用安全02。撤离须与claim、旧授权grant/store/bind及挑战准备资格持久排序；
   不是“查到无claim再写标记”。G2建议采用同事务必要审计；审计未齐不能给Cross可消费证据。
   已claim明确失败路线则只核实原结果/无订单依据，不为了迎合第一条路线删除claim。
3. 03持久保存或按可信原请求找回同一个proof/edit_ref；安全已撤离而平台记录未落库时，
   只能从安全原记录恢复关联，不能重新撤离、重授予或凭当前新卡重建原事实。若撤离仍缺必要审计，保持旧动作封锁并等原事实补齐，不能先发布编辑。
4. Cross按精确源已发布checkpoint_ref核对proof，归档原pending/attempt及确认/验证引用，构造仅撤出旧活动待办的新状态；
   原订单、失败、成功消费、预算来源和active冻结/收尾授权不抹除。新检查点写在隔离的待发布位置，
   不改变普通恢复可见的活动状态。同一edit_ref须通过持久唯一关联或等价CAS只选定一份转换/检查点/新input结果；
   并发重放读取同一胜者，不能各自生成可生效的新交互。检查点失败不报成功、不解除旧安全封锁、不新建银行操作。
5. 平台以原任务版本和源checkpoint_ref作CAS，在同次任务更新中发布胜出的checkpoint_ref、原结果投影及新task_revision。
   普通Cross恢复只能读取已发布引用对应的状态；不能沿用当前`CrossEntry._load/_save`默认取最新检查点的路径，
   否则CAS失败留下的新检查点也可能被误用。CAS冲突先检查取消/安全终止/新会话/其他方案是否已胜出，不能盲取最新revision覆盖。
   已有同edit_ref发布结果则重放该结果；仅有隔离待发布状态且原绑定仍可办理，才受控补原发布；否则保持拒绝/只读核对，孤立检查点不可成为活动状态。
6. CAS已成功、HTTP receipt未写或响应丢失时，同参返回已保存的原结果/receipt，不能把当前较新计划当原请求结果。
   原input后来已作答或任务已停止，不重挂旧输入或启动购买；当前界面另查当前任务，历史重放不授予新的输入权限。

优先复用任务现有checkpoint_id/原CAS发布关联，配合现有saver可验证的精确引用读取/隔离能力，
不先建通用检查点框架。03负责发布守卫、08负责按该已发布边界读写自己的状态；候选01/03须证明旧任务的源引用映射可唯一核验。
若现有saver做不到隔离、精确读取或同请求单胜者，要先回交具体缺口，不由Cross假装现有字段已经提供原子性。
交接pending且新状态未发布时，普通resume只读原结果并保持待核对，不推进旧动作，也不读取待发布新input；取消仍按真实资金事实收尾。

撤离不能回滚成旧动作重新可写；进入新input也不能自动执行freeze/order/capture。
撤离待冻结attempt时，迟到旧grant或平台写回必须被同一守卫挡住。确证未提交/无真实冻结时，
Cross按撤离事实表达“原动作未提交，没有该笔冻结”，不能将pending授权invalid误写成银行FREEZE_FAILED；
有真实active冻结时照原限定授权收尾，不追加冻结、换账户或重置预算。

## 4. 既有ports兼容与确需补的能力

- 沿用BirthdayPlan.items及现有item字典承载内部稳定项/attempt、quantity和原报价；quantity已有银行字段。
  旧单件调用只在唯一旧映射可证明时保留原1件语义；新协议必填稳定身份和数量，不能缺值静默变1，不能给历史未知动作重新编号。
- GateAnswer/WriteOutcome继续表示原门和银行结果，**不把撤离塞成ALLOW、cancel或failed**。
  `requery`继续按原operation只观察已claim操作；当前运行实现接受operation_id，Protocol声明未列该参，实施时需对齐声明与实际调用，
  不以None推断失败/未提交。不在本轮改代码或创建新协议框架。
- 真正新增的是01的稳定项/数量及历史查找能力、02的不可恢复撤离与审计/挑战/授权守卫、03的持久交接和CAS恢复、04的受控公开分流。
  当前普通resume/F10/转账draft不足以提供这些能力；现存字段可表达结果，不表示这些过程已经实现或获批。
- 现行Cross按线程最新checkpoint加载，任务CAS本身不隔离它；G3还须补精确源引用、待发布写隔离、同edit_ref单胜者及原子发布指针/结果。
  该能力列入03/08的协同前置；不把“保存检查点后再CAS”当成已证明的恢复保证。
- 03须保留“两类proof”的窄消费接缝；原下单的failed结果可由既有requery返回，但额外“无订单/无在途”依据和持久绑定仍须提供方证明。
  Cross不会伪造撤离、挑战失效、授权invalid或跨目录写安全记录。

## 5. 依赖顺序与本人未决项

使用正式**候选**票，不重复建实施票：
[v05-birthday-platform-dependencies/01：数量/稳定项](../v05-birthday-platform-dependencies/issues/01-quantity-item-binding.md)、
[02：安全撤离](../v05-birthday-platform-dependencies/issues/02-security-retire-unsubmitted.md)、
[03：原任务编辑交接](../v05-birthday-platform-dependencies/issues/03-platform-edit-handoff.md)、
[04：F10分流](../v05-birthday-platform-dependencies/issues/04-api-edit-entry.md)。

后续固定提供稿d9f8b96另补 [v05-birthday-platform-dependencies/05：生日编辑候选检查点的一次封存](../v05-birthday-platform-dependencies/issues/05-immutable-edit-checkpoint.md)，
作为03/08真实前置；该候选链接以d9f8b96的Git树核对，本轮取回的origin/main `855497f`尚未收录05，不能视为已交付。消费意见见§8。

建议先核对01内部快照与本页两类proof，再取得G1/G2决定并由提供方更新其稿；01数量与02安全能力可按目录独立准备。
02真实接缝就绪后03可用明确stand-in自验交接；与Cross08接通并完成04后才验证公开全链路。
跨票G3签名先在设计层达成，不要求03等08全实现、08又等03全实现形成循环；每张开发票仍需另行授权。
同birthday_runtime/Harness/API文件的已有PR按中控指定顺序处理，不把“同文件顺序”混成新业务依赖。
个人预算路径仍另等[cross06](issues/06-adopted-budget-integration.md)及其F10来源链；商品编辑不改个人预算版本/限额。

**与安全建议的差别是完成范围，不是擅改规则**：bce306d的G2-B建议首批只纳入未开始准备挑战的确认等待，
这尚未由本人批准；若选择该子集，它只能是局部交付，Cross08的验证等待态要求仍blocked，不能关闭整票。
若本人要求完整确认/验证编辑，需先决定并证明已安全撤离旧挑战如何退出后续任务级失败/超时判断，以及准备/发码/撤离的可靠胜序；
不能删除已发生失败、忽略终止或凭“库里还没挑战”放行。G2-A非终止撤离、G2-C未生效授权失效及G1 F10状态语义同样未获本人决定。
本评议不替本人批准，也不把AI设计复审或第二批合入授权当作G1/G2接受。

## 6. 交付与独立检查

只新增本页、更新08前置引用/本轮说明；不改平台/安全稿、297/06、原缺口历史或共享进度。
独立Standards初审PASS（必须项/建议0）；Spec初审1项P2：检查点可能先成为最新可读状态、再发生任务CAS失败。
修订提交`c0752632f088857838661b13739ce2170466f0e6`补源checkpoint_ref、待发布隔离、同edit_ref单胜者、CAS发布检查点引用和结果及普通resume读取守卫。
独立复审：Standards PASS（必须项0、建议0）；Spec PASS（原1项P2关闭，新增必须项0、建议0）。两方均仅静态核查。
本页为接口建议，具体名称和最终绑定待提供方收口。
纯文档仅做内容/链接锚点/编号/格式/差异空白检查，不跑测试、模型、CI，不写产品代码或新实现PR。
本地两份文档23处相对链接/锚点及差异空白核对通过；分支`codex/v05-birthday-g3-interface`本地提交回交，不推送/合并。

## 7. 对平台c5959dd候选的消费核对（静态，未闭合提供能力）

完整读取本地`c5959dd6afcdac4c3745c04c9ef41b310dcda97d`的本组平台`spec.md`“G3最小内部快照/调用候选”及`decision.md`（基线3239fd7）；
以下只确认字段/时序关系，不修改对方稿、不表示接口已实现或G1/G2本人已批准。拟议方法名和keyword均为后台接口建议。

| 候选关系 | 消费方结论与最小兼容条件 |
|---|---|
| operation_id作为attempt | **足够，无需第二UUID。** 一次freeze/order/capture各有自己的原号及不可变参数；同一尝试的检查/执行/恢复沿原号。合法撤离或明确失败后重新采用的新尝试必须新原号，即使商品/数量/参数碰巧相同。原号不是可自由调用的授权令牌，仍核对主体、项、动作、版本和原参数 |
| check返回原号，execute显式带回 | **方向一致，现签名不足。** 保留GateAnswer.operation_id，Cross在check后持久保存原号及item/参数绑定；也覆盖非冻结动作ALLOW后直接_submit的分支，不能只在等待确认时保存。新协议的execute显式带回该原operation_id（拟议后台keyword），平台精确解析不可变attempt并校验，不能按最新商品键挑选；冻结ALLOW仍照原规则拒绝 |
| grant_release / bind_freeze | **必须捕获原绑定。** grant使用原pending.operation_id、原确认ID/版本及冻结上下文；bind已有operation_id参数可复用，同时绑定该原attempt的限定授权引用。迟到grant/bind/指针写回均不读取“当前freeze”当原动作，不把旧pending授权挪给新尝试；真实active冻结收尾不失效 |
| 原确认版本从哪里来 | **仍缺明确提供方式。** 当前GateAnswer/InteractionRequest有operation_id/record_ref，没有确认版本；不能声称Cross已拿到版本。建议平台在check时将确认版本/参数/授权上下文按原号持久冻结，Cross通过原号对应的可信只读视图捕获版本或其不可变上下文引用，再显式带回。不得迟到时按可变confirmation_id重新查最新版；不因此新增公共字段 |
| item_id复用step_id | **可复用，但非现成映射。** 仅当step_id是服务端持久且与商品执行项一一对应、未变项跨plan_revision保持、新同款替代项有新step_id；freeze仍是任务级资金动作。现生日orders主要按product_id定位，须先由01/08补稳定项映射，不能拿执行事实投影行或product_id硬充同款多项身份 |
| 旧单件调用 | **原则一致，但“已指定quantity”措辞需修正。** 现`birthday.py:67—76、100、299`的旧项/订单已显式quantity=1，字段存在本身不能标记升级。仅在服务端可核验旧调用绑定、每商品一项且原操作/参数唯一对应时，旧显式1或旧省略为1的语义可保留。quantity>1，或服务端已进入新item/operation绑定的调用，缺必要身份不得降级旧键；未能判定协议或唯一映射则blocked，不猜测重建。旧已办/未知沿保存的原号查，不重发。此为对c5959dd的具体兼容差异，只回交，不改平台稿 |
| 两类proof命名 | `withdrawn_unsubmitted`与本页`retired_before_claim`语义对应；`verified_failed_no_order`一致。最终可统一一套私有名称，不按客户端字符串授予能力。两类均要原绑定/历史及必要审计，不把claimed/completed或任意失败当无订单证明 |
| 明确失败的新替代入口 | **接受候选的两种来源区分。** 已有精确编辑受理事实时，以原request/operation恢复核实，不因interaction=None先截断，也不因历史记录跳过当前任务/会话/终止检查；没有原受理时，不能拿旧确认ID走专用编辑捷径，而是原query/resume核实失败并保存可信结果/无订单无在途依据，父任务仍可办理才发布普通新input替代选项，再走当前F10采用与新逐动作确认。不伪造edit_request、无claim证明或新授权 |

check/execute/grant/bind的上述新绑定尚非现运行能力；普通失败替代输入也不能绕过§3的检查点发布边界。
平台候选`begin_birthday_edit`与`enter_birthday_edit`的职责可对应本页专用后台入口：edit_context可为按edit_ref解析的当前调用只读视图，
但不能只是可被普通resume构造的字典。**源checkpoint精确绑定、待发布隔离、持久单胜者、CAS同次发布引用/结果必须保留**；
对方此版未纳入不构成删除理由，真实saver/加载/发布提供能力仍由03/08协同核实，未具备继续blocked。
`decision.md`的完整/首批收窄两选项均为本人未决；确认/验证编辑完整要求不删、不代选，G1/G2与实施批准另取。

本节独立Spec/Standards初审各有1项P2必须澄清、建议0，均指“quantity字段存在即升级”会误拒现有单件调用。
修订提交`a3b287c217d43a3663192896dd6d2d9fa833150e`已按真实旧quantity=1及服务端绑定/唯一历史映射修正。
两轴静态复审均PASS：各自原P2关闭，新增必须项0、建议0；未测试、运行模型或CI。
本轮基于已交付e4cb7b7仅增补本页，未动票据、平台稿、297/06或shared tracker；新绑定、检查点发布、G1/G2及完整验证编辑仍按前述条件blocked。

## 8. 对d9f8b96封存提供稿的最终消费意见（设计，仍blocked）

只读固定`d9f8b96bb66a1e1198cbf3325a664ba1e189814e`的`g3-reconciliation.md`、05票及spec/03依赖。
**可接受其作为§3发布边界的最小提供方向，不能认定能力已交付；下列起始源封存关系仍须提供方写清。**

| 核对点 | 消费意见 / 真实能力边界 |
|---|---|
| 完整ref与父关系 | source/candidate都用可信task所属thread_id + checkpoint_ns + checkpoint_id，另绑定内容摘要和原项/原号。每份候选新namespace，跨namespace来源保存完整source_ref；不得把源ID直接填成目标namespace的原生parent_id。若没有真实同namespace父节点，原生父关系不伪造；这已说清，非新增通用父图框架 |
| 先预留→封存→发布 | 03先以原CAS预留同edit及唯一candidate_ref，再取02/原号失败依据；Cross只从精确source准备候选，05在同一持久边界选择首份完整胜者，03只用此胜者在同次任务CAS发布完整ref/ModuleResult/版本/完成投影。四项返回包可承接，不另加公开字段或购买授权 |
| 首份胜者不可覆盖 | 05须保护完整回读内容及必要元数据/关联写，旧put/put_writes也不能改封存值，发布后继续保护。当前saver的channel值按namespace/channel/version覆盖，精确ID本身不足；隔离namespace与05窄封存都是实际前置，不回退为仅新UUID或内存锁 |
| 普通及异常恢复 | d9明确覆盖Cross普通start/resume及Harness异常记账，不再以默认latest猜结果；handoff未完不推进旧动作，CAS失败的孤立候选不活动。后续每次状态写用新的隔离引用，完成重放不回挂旧输入；这一责任划分可承接原P2，但须03/05/08真实接线验证 |
| 旧任务可核验性 | d9已明确：旧checkpoint_id非空、namespace为空也只是候选来源，仍需原状态/结果/项/原号一致且内容可核验；新补hash不能证明过去未被覆盖。缺源或不唯一就保持编辑blocked，原查询/合法收尾保留，不回latest、重编号或另开任务绕开。不能宣称所有旧任务都可升级 |

**剩余提供差异一——起始/普通已发布源也须受保护。** d9“旧任务与旧单件”要求新生日首次状态保存published_ref，
05“最小输入输出”却以edit/source/请求摘要绑定封存编辑候选；目前未明确**尚无edit_ref、尚无前驱source**的新任务初始状态，
以及无编辑请求的普通输入/事实更新/异常转换，如何取得同等不可变源。请03/05在这些具体段落明确：
可沿同一窄能力以原task/请求或状态转换关联封存，初始根状态不伪造source/edit请求，之后每份将被发布的G3状态也保持不可变；
不能只封编辑candidate，却让下一次读取的source仍来自可被旧put改写的普通blob。不能提供时，新协议起点和相应恢复仍blocked。
这不是要求扩大通用框架或全库迁移，也不要求先有03/08代码再设计05；本轮不替提供方修改其票或选实现。
需提供方同步的具体位置：对账稿“旧任务与旧单件/最小协议候选”、05“最小输入输出/验收条件”、03的起始与普通发布条件；不另建重复实施票。

**剩余提供差异二——§7旧显式quantity=1的兼容意见仍有效。** d9虽认可旧单件语义，未替代c595的具体调用判定差异；
后续01/03仍应以服务端绑定/唯一历史映射区分，不能按quantity字段存在就判新。原operation作为attempt、原确认版本/授权上下文、两类proof及失败替代入口沿§7，不重复收口为已实现。

08仅新增05正式候选依赖；03已在d9正式依赖05。建议03/05与08先补齐上述设计输入，再另行取得实施授权并分目录交付；
G1/G2本人未决、完整确认/验证修改要求及06原预算依赖均不变，全部planned/blocked。
本轮固定审查提交`b21867097a19c5e55d4152842cca5871213486af`：独立Standards PASS（必须项0、建议0），
独立Spec PASS（必须项0、建议0），确认上述起始/普通源缺口成立且属窄必要条件；均只静态核对。
仅检查两份自有文档的内容、链接/锚点、范围/编号和差异空白；05链接按固定Git树验证，不复制提供稿补本地文件。
只修改本页与08必要依赖，不改提供稿、其他票或shared tracker，不跑测试/模型/CI，不写代码或新实现PR。
