# G3对账与检查点发布提供条件

Status: planned / blocked — 只读设计收口，原01—04及新增05均未授权实施；G1/G2未裁定。
d9f8b96前轮基线c5959dd（父系产品基线3239fd7），当时静态读取main c02c70d对应源码；本次仅按727045d及既有源码核对旧单件兼容，不运行程序或测试。

精确消费方来源：本地Git提交`e4cb7b7dad5ef78b31e52c64e845f7db8a55ea78`，父c0752632f088857838661b13739ce2170466f0e6、核查基线2a070b9；完整文件`.scratch/v05-cross-business/birthday-g3-interface-review.md`，blob`3ae7559a14f36b1e501f274b8d0f36baed510f33`。已git show全文，只读不改；不声称已入远端main或双方最终接口确认。安全来源S-G2仍见[规格](spec.md#problem-statement--固定依据)。

兼容补充只读来源：`727045d76ad84e7b2071410acfb022f2a8a0bc4c`同一完整文件§7，父a3b287c217d43a3663192896dd6d2d9fa833150e、blob`8e0b7e8ecef0e0e32d337fa71ca8e1f6b8eb7ad4`。它核对的是平台c5959dd，已认可operation_id作attempt并指出旧显式quantity=1；不把它写成对d9f8b96新增05/发布协议的最终确认。

最新固定消费稿S-G3-8：本地`896fd7e5d1728b1202818a212ffcb622a658d9b3`（父b21867097a19c5e55d4152842cca5871213486af），完整读取同一评议文件（blob`a02f5b6ff08fe7ea4e046da4f71da5cc4a931e03`）及Cross08票（blob`28b8a4b68f85eae7ab5dca71302eb575c7f8592a`）。§8接受d9f8b96的窄封存/发布方向，但指出初始与普通源尚未明确；本轮只补该设计及保留旧quantity=1判定，不将消费设计意见写成真实能力、G1/G2决定或实施授权。

## 简短对账表

| 类别 | 已达成的方向 / 现有条件 | 尚缺的提供与待核对 |
|---|---|---|
| 方向一致，非最终签名确认 | 两类proof、稳定项/原操作、完整旧历史、未知原号、先安全后编辑、未提交与银行失败分开 | 727045d §7认可operation_id作attempt；896fd7e §8接受05/发布最小方向，剩余初始/普通源设计见下；具体签名与真实提供仍未闭合 |
| 方向一致 | 普通input沿原F10；新编辑不产生银行attempt或购买授权；旧单件不盲改、终态不复活 | check产生的operation/action_revision/确认版本须落原pending；execute/grant/bind显式消费捕获的原绑定，迟到回调不按当前商品/freeze键重选 |
| 提供缺口 | saver已有精确ID+namespace读取；ApplicationStore一次CAS可同时写checkpoint_id、snapshot与revision | 现调用默认latest；通道值可覆盖；没有同edit_ref不可变候选和发布流程。新增[05存储窄能力](issues/05-immutable-edit-checkpoint.md)，03+Cross08接线，不能只说已有字段保证原子性 |
| 提供缺口 | task snapshot可保存私有完整引用/编辑关联；memory adapter已有用户/会话/任务校验并透传namespace | 03须持久保留唯一edit_ref/候选引用并管发布；Cross08按精确已发布源读、仅写隔离候选；新协议普通resume不能走latest或推进handoff中的旧动作。不新增memory票或通用框架 |
| 待本人政策 | G1、G2-A/B/C与安全原稿全部条件不变 | 完整验证等待或首批收窄尚未选定；本检查点补齐不批准任何新语义，不删原要求、不改#160 |

## 静态事实：现有能力不能拼成已交付保证

- [CrossEntry._config/_load/_save](../../backend/app/modules/cross/entry.py)默认namespace为空、未传checkpoint_id；_save先put，后返回ModuleResult。
- [saver.get_tuple](../../backend/app/storage/checkpoints.py)有checkpoint_id时可精确读取，否则按row_id取最新。_tuple再按(thread, namespace, channel, version)读channel_values；put的checkpoint_blobs使用INSERT OR REPLACE。因此即便指定旧checkpoint_id，同namespace/版本被重写也可能读到别人的值。
- [ApplicationStore.update_task](../../backend/app/storage/application.py)只用归属和expected_revision作CAS，能同次写checkpoint_id+完整snapshot+revision，但没有候选封存、edit胜者或源引用策略；提交后再get_task也可能已看到另一更新，调用方不能将返回值盲当自己刚发布的结果。
- [Harness._checkpoint_id](../../backend/app/agent_platform/harness.py)也取默认latest，成功/异常记账均可能采用它。只改Cross编辑入口，保留普通resume/故障分支的latest路径不合格。
- [ScopedCheckpointSaver](../../backend/app/memory/adapter.py)已有归属与会话检查、可传namespace，不负责识别已发布和待发布状态。问题不是缺通用memory框架，而是本G3的读写协议与不可变保存缺口。

以上为源码推演，不是本轮运行反例。现有put事务/唯一checkpoint约束可复用，但不能仅在新方法防覆盖、旧put/put_writes仍能修改同候选。

## 最小协议候选：先预留，后安全，再隔离准备，最后发布

1. **03先受理**：用原任务CAS固定request摘要、同一edit_ref、源已发布完整引用及接受版本，并预留唯一候选引用；同参竞争读取同一记录，异参冲突。受理失败不撤离。完整引用为task所属thread_id + checkpoint_ns + checkpoint_id；新协议再绑定当时内容摘要与原计划/项/attempt，不接受客户端自报。接受/后续dispatch版本显式关联，不用最新revision追着重试。
2. **02给真实依据**：撤离+必要审计齐备，或原操作准确失败且无订单/无在途；后者保留已有claim、不伪造撤离。安全已持久而03关联未落时只按原request恢复同一事实。
3. **Cross隔离准备**：按精确源引用读取，保留原pending/完整历史；不生成银行动作。接收03预留的候选ref，只写该ref。每份候选使用后台限定的新namespace，不与源或其他候选共用channel version；不能只给同namespace换一个checkpoint UUID。跨namespace来源关系存完整引用，不能伪造saver同namespace的parent_id。
4. **05不可变单胜者**：对该候选ref及其edit/source绑定只允许首次持久化；同绑定竞争/重试读首次完整胜者（含原新input ID），不同绑定冲突。候选封存后，包括原put/put_writes在内的覆盖路径都拒绝，不得改旧checkpoint_blobs。选择/封存必须持久，不能靠进程锁或晚写的标记。
5. **03原任务CAS发布**：读取05的胜者，验证原source/请求/审计及当前归属/阶段；用受理时关联的严格版本，在**同次update_task**发布胜者checkpoint_id、snapshot内完整published_ref、该ModuleResult、新revision及本edit完成投影。发布前先核对source_ref，任何合法指针变化应递增revision使CAS失败；不能盲取新版本覆盖。此为03/08须实现并验证的协议，不是当前update_task已提供完整语义。
6. **普通恢复与竞争**：G3任务的普通start/resume/异常恢复也由03传精确已发布ref，Cross08不可再默认读latest；候选ref与结果经后台窄返回包交03。handoff未完成时普通resume仅返回已发布原结果/待核对，不调旧执行分支；取消仍按原操作与真实冻结收尾。取消/终止/新会话/其他方案胜出时孤立候选不得变活动状态；同edit_ref已完成则只重放冻结的胜者结果，不重挂旧输入。
7. **断点**：候选写失败或CAS失败不报发布成功；已封存候选且原绑定仍合法时可补原发布；证据不足/终态只读核对。发布成功但receipt丢失返回原完成投影，不拿当前新计划充数。已发布候选之后也保持不可变，每次后续状态写用新的隔离引用。

后台编辑返回包沿用Cross消费方的四项：`edit_ref / source_checkpoint_ref / candidate_checkpoint_ref / ModuleResult`；03不再用latest猜这次结果。edit_ref只属于真实受理编辑；初始/普通分支以03保存的原转换关联及候选ref回交结果，初始source明确无前驱，不为凑包伪造edit_ref/source。私有签名中缺席项的具体表示仍待接线确认，不加公开字段。其他旧模块仍返回原ModuleResult，不声称现有方法签名已兼容。

## 没有编辑请求的初始与普通状态

05同一窄封存能力须覆盖**每份将被发布的本G3状态**，不限编辑候选；只封编辑结果而让下一次source可覆盖不合格。03在调用Cross准备状态前，以现任务CAS预留原转换关联、接受版本与唯一隔离候选ref；Cross08构造状态，05封存首份完整胜者，03同次任务CAS发布完整ref/对应ModuleResult/新版本及该转换完成投影。封存或发布失败不报告新状态成功，不预建通用框架或重复实施票；必要持久元数据仅按05实际缺口最小补齐。

| 状态来源 | 03的可信关联与source条件 | 05封存及03发布 |
|---|---|---|
| 新任务首次状态（含先场景澄清后转生日的起点） | 复用原task/已受理start request及接受版本，在首次Cross状态写前持久预留根候选。后台核实确为首次初始化、从未发布Cross状态；没有edit_ref，source明确无前驱，不伪造编辑请求、源ID或跨namespace parent_id | 05只允许该已预留根关联无source，封存独立namespace内的完整初始状态/结果与必要关联。03严格CAS把该根ref和结果正式发布，才成为首份可读源；不能先put默认namespace再补hash。第一次发布前失败只按原根关联恢复；无可读旧源时使用现有初始化失败/待核对表现，不把候选当活动状态 |
| 普通输入、采用/继续、原号事实回读与异常转换 | 不制造edit_ref。用户输入沿已受理原request；无用户请求的事实/异常沿原运行/事件与接受版本固定关联，保存在task snapshot。恢复复用该原关联，不能以新run_id或最新revision冒充原转换。source必须是上次已封存且已发布的完整ref | 预留新隔离候选；05按原转换/源/请求或事实摘要绑定选择持久首份胜者，保护完整值/元数据/必要关联写。03只发布胜者，旧source永不原地改；所有成功、失败、异常记账分支都不得以latest选结果。外部操作事实仍沿原operation核实，不因发布失败重做银行写或伪造银行失败 |
| 真正的专用编辑 | 已有原edit受理、精确已发布source及安全/原号失败依据，仍走上节协议 | 复用同一05封存与03发布边界；不能用普通转换关联代替安全proof或新购买授权 |

根重试必须匹配已预留的原task/start关联；任务已有历史却缺published_ref、旧源无法核验、或普通更新没有可核验前驱，都不能冒充新根、从latest/孤立候选补源或新编号。维持G3相应起点/恢复blocked，保留已知原号查询和获准收尾。

同任务尚有未发布转换时，普通读取只看最后已发布结果；没有已发布结果则只显示初始化待核对，不启动另一转换越过原受理。取消/终态/会话变化或合法其他写入获胜使原CAS失效，孤立候选不得活动；已发布后receipt丢失按原完成投影重放。所有已发布根/普通状态仍受05同等防覆盖保护，下一次写再用新namespace；原put/put_writes不能绕过保护。先做03/05/08设计协同即可，不互等对方代码形成实施循环。

## 原操作绑定如何经过现有接口

以下是拟议兼容约定，仍待Cross08核对；不声称现接口已全部提供。

| 入口 | 原事实在哪里捕获 | 后续如何使用 |
|---|---|---|
| check | 沿现有GateAnswer.operation_id；平台01将该原号绑定稳定项、action_revision、不可变参数与完整确认版本；Cross在execute前持久捕获原号/项/参数，包括非冻结ALLOW直交分支，不能只在等待确认时存pending | 确认版本须由后台按原号提供不可变绑定/只读上下文，具体方式未交付，不假装GateAnswer已返回不存在的新字段；冻结ALLOW仍拒绝 |
| execute | 新协议显式带回pending捕获的原operation_id，平台按该号取原绑定 | 核对当前仍是该未撤离动作；不按当前product_id重选或产生新原号 |
| grant_release | 由原pending捕获的operation_id及原确认版本/等效冻结上下文显式传递；拟补后台参数 | 保存返回的release_authorization_id；迟到grant不能依据当前freeze键覆盖新计划 |
| bind_freeze | 优先复用现有显式operation参数，并传捕获的授权引用（若现签名不足再最小补齐） | 按原attempt与授权绑定验证，不把当前birthday_release指针当原依据 |
| requery | 现实现按明确原operation_id查询，Cross08须补齐其Protocol所缺参数声明 | 恢复同一尝试沿原号；替代方案才另起新动作。查询失败/not_found不等于无在途 |

operation_id本身承担一次动作尝试身份已获Cross727045d §7认可，不再叠加随机attempt_id；这不把原号变成自由授权令牌。具体签名与提供能力仍未最终闭合，不能以此解除G3阻塞。

## 旧任务与旧单件

- 旧TaskRecord.checkpoint_id非空且namespace确为空时可构成候选源引用，但还须证明完整状态/原结果/原项与历史绑定一致、未受通道覆盖影响；不能只凭这个ID或新补一个hash就“证明”旧源。
- 缺已发布ID、只剩latest、同版本值可能覆盖或无法核验原pending时，G3编辑保持blocked，保留已知原操作的查询/获准收尾；不重新编号、不从孤立候选回填、不另开任务规避。不能据此宣称旧任务编辑已全部支持。
- 新协议生日及可转入生日的场景澄清起点，在首次状态写前预留无前驱根关联，经同等05封存及03发布建立精确published_ref；普通输入/事实/异常后继沿本页条件承接。旧正常单件的数量/唯一商品兼容不豁免已发布源保护，也不让旧调用读到候选。
- 旧birthday._chosen_items和_plan_items本已显式写quantity=1，不能凭字段存在判升级。旧显式1/省略1只在后台旧绑定、每商品一项和原操作/参数唯一对应可核验时保留；quantity>1或服务端已进入新item/operation绑定时，缺身份不得回落旧商品键。协议来源/唯一映射不明则blocked；客户端标记或quantity>1本身不授予新协议权限，旧已办/未知仍只沿保存原号查，不猜测重建/重发。
- 本轮不写旧库迁移或清理孤立候选程序；储存05只补窄不可变候选能力。源精确读和现任务CAS已有，03/08仍须接好，组合验证前一律不宣称原子发布已成立。

## 最小提供依赖与未来检查（未运行）

新增05归backend/app/storage/；原03增加05前置，Cross08按其自有票接精确读写/返回包，不互写票。memory现有接口无已证实的新缺口，故不另建票。若05设计发现现有表/元数据不能安全封存，应在本目录列必要最小持久变化，不在03跨目录补SQL，也不先造通用框架。

未来至少检查：旧源ID精确读取但共享version被覆盖的反例；候选写后CAS失败仍看不到新input；同edit跨进程双准备只回同一胜者；put/put_writes绕过封存被拒；普通/异常resume不读候选也不推进旧动作；取消/新会话/终态胜出；候选/发布/receipt各断点；旧源缺失不回latest；check/execute/grant/bind全程原绑定。补P16/P17覆盖无edit/source初始根、同start根重试、普通输入/事实/异常后继及初始失败/普通CAS失败；旧显式quantity=1边界仍按P15。所有这些仍是planned验收设计，无实跑证据；真实E2E由Erwin后续亲自安排，本轮双轴审查材料回交后即停。
