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
| 原下单已claim，但银行明确失败、已证明无订单且无在途 | 平台核实的原操作失败结果、无订单/无在途依据和对应不可变旧attempt | 另一条受控交接路径；不要求无claim证据、不删旧claim；新替代以后重新采用/确认 |
| claim在先、未知、查询异常或仅not_found | 只有原号观察事实，不能证明可替代 | 不进入可能在途项编辑；原号核实。capture失败也不代表它的已建订单不存在 |

已建未付/已付项不可改写；仍可编辑其他证实未成单且无在途项。新input仅是重新讨论方案，
不创建新银行attempt、生成个人预算采用或放行新购买。取消、终态（含partially_succeeded终态）、
安全终止和无效会话不能借恢复复活购买；needs_attention也不是自动可编辑。

## 2. 最小内部输入输出（拟议名称，不新增公共字段）

| 提供接缝 | 最小输入 | 最小输出 / Cross核对 |
|---|---|---|
| 01→原BirthdayPorts | TrustedContext、原BirthdayPlan、服务端项快照；已有check/execute方法签名保留 | 每项有稳定item/step身份、product_id、显式quantity、服务单价、行小计和原送达/受控配送引用；平台按此下单和展示，不能product_id碰撞 |
| 04→03专用后台编辑入口 | 已认证TrustedContext及原F10 request_id/interaction_id/selected_option_id；text为空 | 平台从原任务重读绑定，不采信前端传入的item/attempt/operation/hash或editable标记；该入口不注册为模型工具 |
| 03→Cross专用进入编辑入口 | TrustedContext + 原请求的持久edit_ref；只在本次专用调用或其精确受控恢复中可解析 | 解析为下述完整绑定和一种可信proof；普通resume/text/模型字典即使知道edit_ref也不能激活它。可参考既有平台专用来源隔离方式，但不复用预算来源作为商品编辑授权 |
| Cross→03 | 原edit_ref、源已发布checkpoint_ref、隔离待发布checkpoint_ref及对应ModuleResult | 原task_id、新input交互及业务plan_revision；平台用严格原任务CAS同时发布检查点引用/结果/新task_revision；不是Cross自行宣称已发布 |

**edit_ref背后的服务端最小绑定**：user/session/round/task、原请求及请求摘要、原交互/选项、
原task_revision、plan_revision、源已发布checkpoint_ref、目标（freeze目标或稳定执行项）、attempt_id、action_name、operation_id、
action_revision、原参数引用及可读取快照、确认ID/版本、关联挑战和限定授权的历史引用/必要脱敏快照。
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
