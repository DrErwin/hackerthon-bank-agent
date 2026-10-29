# 生日数量与未执行修改：平台提供条件及最小规格

Status: in_progress — 各实施票与后续提供方修补已合入；生日编辑、跨会话恢复、原号释放有实际接口证据，完整页面及最终接受仍待。2026-10-29 核对，最新结果见[v0.5 完成情况](../../docs/versions/v0.5.0/completion.md)。

原规格状态（历史）：planned / blocked — 2026-10-25，仅只读核查、设计与最小拆票；未授权实施。
Owner: Erwin（v0.5统一负责）；Planning assignee: Codex，01a1718a-26a3-7523-a0bf-2591d8e83618。
Implementation assignee / accepted at: 已按独立票执行；实际执行者、领取日期及合入证据见各票。下文原 planned/blocked 叙述保留最初设计时点。

## Problem Statement / 固定依据

用户应能真正订两束花，并修改尚未形成订单且没有在途提交的剩余方案；不能只改页面数量，也不能让旧确认在修改后继续写入。本轮没有运行复现，以下均为固定源码推演。

- 本worktree起点 main `af779df431a7f650851ffe3e2ede8b763dcdb1c5`；独立分支 `codex/v05-birthday-platform-dependencies`。中控材料入主线后，本地文档基线快进至`dab17d030b4a4a481280d5cc5900176db38c9aeb`，仅文档变化，所查运行代码未变。
- 本轮收口另用本地文档分支`codex/v05-birthday-dependency-closeout`，基线`3239fd75417e8f1e47aea0c0db83d734cdfffe6c`；旧分支与原证据不改。原四票及本轮新增05全部planned/blocked。
- Cross材料固定提交 `1d7f1fab8d5e2622c1d319e178abf9f1654fc73c`，基线608255f，读取该提交完整三份文件，不以其最后一条commit的单文件差异代替材料：
  [缺口/数量设计](../v05-cross-business/birthday-quantity-gap.md)、
  [设计审查](../v05-cross-business/birthday-quantity-design-review.md)、
  [v05-cross-business/08：生日商品数量与未执行部分调整](../v05-cross-business/issues/08-birthday-quantity-and-unexecuted-revision.md)（planned/blocked，不修改）。三份main文件blob与固定1d7f1fa内容逐一相同。
- 原[PRD §2.4](../../docs/prd/06-跨场景联动-PRD-2026-09-23.md#24-xl-b家人生日安排)：流程4展示数量/费用/时间，流程7只改未执行部分；失败与收尾明确不撤单/退款、未知沿原号。
- [现行契约](../../docs/contracts/公共契约-2026-09-23.md)：§5.4、§6.5 F10/F15、§3.5与§8；[安全原则](../../docs/principles/02-security-platform.md)保持确认绑定和原操作恢复。
- 已查main、所有本地/远端已取回refs的本组路径历史：新slug尚无票；原platform13/PR292、14/PR296虽未合仍占号，不在原组重占。Cross07/08与预算来源01/02均不改；原security01/04不是本次安全撤离交付。
- **精确安全来源S-G2**：本地提交`bce306d07e429b8ce604dd8232fa58cd3836f0a3`，父`f21db3b00c6365132323f85b104c184a88aa4a20`，基线41c01ae；完整文件`.scratch/v05-birthday-security-review/review.md`，Git blob `53f9196dc9d2a16c1bc92b6235902b840fc3343a`。已通过`git show`读取；本轮读取时该文件尚不在所选main，按本地固定Git对象引用，不宣称远端可读，也不修改或复制覆盖原稿。它是AI安全评议，G2-A/B/C仍待Erwin本人决定，不能用原设计双轴PASS替代。
- **精确消费方来源S-G3**：本地`e4cb7b7dad5ef78b31e52c64e845f7db8a55ea78`的`.scratch/v05-cross-business/birthday-g3-interface-review.md`，父c0752632f088857838661b13739ce2170466f0e6、产品基线2a070b9、blob`3ae7559a14f36b1e501f274b8d0f36baed510f33`。全文只读不改。其检查点P2已纳入[本组G3对账与提供条件](g3-reconciliation.md)，不把消费建议写成最终接口已确认。
- **消费方兼容补充S-G3-7**：本地`727045d76ad84e7b2071410acfb022f2a8a0bc4c`同一完整文件§7，父a3b287c217d43a3663192896dd6d2d9fa833150e、blob`8e0b7e8ecef0e0e32d337fa71ca8e1f6b8eb7ad4`。全文只读；Cross已认可operation_id承担attempt，无需第二UUID，其他提供条件/具体签名未闭合。旧代码本已显式quantity=1，以下兼容判定据此修正；该版本尚未核对新增05/发布稿，不宣称727已确认d9f8b96，后续见S-G3-8。
- **最终消费方向S-G3-8**：本地固定`896fd7e5d1728b1202818a212ffcb622a658d9b3`（父b21867097a19c5e55d4152842cca5871213486af）。完整评议文件blob`a02f5b6ff08fe7ea4e046da4f71da5cc4a931e03`、Cross08票blob`28b8a4b68f85eae7ab5dca71302eb575c7f8592a`均只读；§8接受d9f8b96窄封存/发布方向，明确尚缺无edit/source初始根及普通输入/事实/异常后继的同等保护。本轮补[初始与普通发布条件](g3-reconciliation.md#没有编辑请求的初始与普通状态)，保留8cdc08f已修正的旧显式quantity=1判定，03/05承接；不修改Cross原稿，不将设计接受写成能力已提供。

## 1. 现状：什么能复用，哪里真的缺

| 位置（上述main基线） | 源码事实 | 判断 |
|---|---|---|
| [银行模型](../../backend/app/contracts/bank.py) L284—328、[银行服务](../../backend/app/services/mock_bank/birthday.py) | CreateOrderInput已含正整数quantity、expected_total_fen及deliver_by，订单回执有quantity/total/送达 | 不缺公共quantity字段，不加银行规则/订单修改接口 |
| [生日装配](../../backend/app/agent_platform/birthday_runtime.py) L55—70、432—498 | 请求固定quantity=1；展示只有动作/金额/商品；参数记录绑定原请求；order/capture以product_id作键，_enriched也按product_id找项 | 数量、原价/数量/时间展示、稳定项/attempt及历史参数查找是agent_platform接线缺口 |
| 同文件L127—160、370—417 | 参数相同重用旧operation；参数变了会生成新operation并覆盖同键；执行前比较原参数 | 不能把商品ID或plan_revision当稳定执行项；新同款项不能借旧成功结果，旧未知操作也不能被覆盖丢失 |
| [API service](../../backend/app/api/service.py) L1523—1575 | current_input_task只接受kind=input；revise_draft限定transfer且拒recovery；cross仅转发当前input选项/text | 确认/验证卡发F10会409 INTERACTION_STALE；cross走draft会409 DRAFT_NOT_EDITABLE。这是源码分支推演，未运行 |
| [API app](../../backend/app/api/app.py) L335—384、[确认请求模型](../../backend/app/contracts/api.py) | F10先走current_input_task；draft只收转账字段；resume只传choice=resume；F15只收approve/cancel | 均不是现成的Cross“先退出旧待办再编辑”入口，不能借cancel或聊天revise冒充 |
| [安全状态](../../backend/app/security/state.py) L217—383、420—500；[执行器](../../backend/app/security/gate.py) L1073—1180 | 新确认可递增版本；claim在SQLite事务内取得；已有claim先按原操作观察。没有非终止式撤离方法 | 查到“无claim”到下一刻claim可能产生，任务锁或银行not_found都不能单独证明未提交；需要security原子守卫 |
| 安全状态L57—68及L536起；[Cross生日](../../backend/app/modules/cross/birthday.py) L422—450 | claim.state只有processing/completed/unknown，completed不等于银行成功；冻结确认批准后、写前可能已经授予限定释放 | 必须看银行实际结果。撤离待冻结验证不能把旧释放授权转给新freeze_operation；已冻结则保留原限定收尾 |
| [任务快照/CAS](../../backend/app/storage/application.py)、[saver](../../backend/app/storage/checkpoints.py) | 可同次CAS写checkpoint_id/完整snapshot/revision；可精确ID+namespace读取 | 初轮没有证实新的存储缺口；本轮发现latest读取及共享channel-version覆盖、候选无封存，新增05窄存储前置。现字段不等于已实现隔离/单胜者/发布；安全SQL仍归security |

以上表格是初轮固定源码推演；本轮所选main已包含PR298（6ce7fb0）及292，不再把它们写为待合。PR296的b41ef64是原订单门固定来源；本轮不整理任何原PR。预算来源、订单范围门和快照保留仍须兼容，它们不交付本次数量或安全编辑能力。初轮占号结论只说明当时来源；本轮沿用原01—04，不重复建票。

## 2. Solution / User Stories

1. 选两件时，下单、确认、验证摘要与最终回执都对应两件及真实总价，时间不丢失。
2. 已付花199元、未下单蛋糕换为同款花时，原花保留，新花是另一执行项/订单/付款；合计398，不把旧花改成两件。
3. 确认或验证时请求编辑，后台先证明并锁死旧未提交动作，再回原任务新input；页面隐藏按钮不能替代这一事实。
4. 若批准/提交先发生或结果不明，先查原操作；已建未付订单、已付消费、失败事实保留，只有明确无订单/无在途的失败可提出新替代。
5. 任务终止/会话无效/越权不能借编辑复活；原账户、原上限、原冻结和个人预算规则不被修改重置。

## 3. 平台自身可补：数量、执行项与确认

由[01：真实数量与稳定执行项装配](issues/01-quantity-item-binding.md)提供；Cross08仍负责候选、数量输入、计划核算与编辑业务。

- 与Cross08先约定内部项快照：服务端稳定执行项标识（优先已有step_id/内部计划项）、product_id、quantity、服务单价、行小计、送达时间/受控配送引用；不新增公共字段。方案变更不是把所有未变项的身份重建。
- 兼容现有尚未升级的单件调用：旧代码本已显式quantity=1，也有省略后按1处理的路径，不能凭quantity字段存在判升级。只有后台可核验旧调用绑定、每商品一项且原操作/参数唯一对应时，才保留旧显式1或省略为1的语义；quantity>1或后台已进入新item/operation绑定时，缺身份不得降级旧键。来源/协议或唯一映射无法判定则blocked，旧已办/未知只沿保存原号查询，不猜测重建或重签。新协议仍须显式稳定项及quantity，客户端自报标记不构成可信协议来源。
- 新替代项使用新执行项；同项未提交动作被合法撤离后，新参数有新attempt/operation/确认；原attempt不改写。未撤离attempt的同参重放/未知观察保持原attempt与operation；已撤离attempt即使参数相同也不能复活。不能只拼product_id或plan_revision。
- _enriched、order/capture键、参数查找、原号观察必须都能唯一找到执行项/attempt；保留已成功、明确失败、未知及撤离的原记录，不覆盖旧键而失去原参数。已有旧任务无法唯一映射时不得猜测合并；仍保留历史，不能计作编辑覆盖完成。
- 真正CreateOrderInput透传quantity，amount为服务单价×数量的行小计；银行仍是价格/可购/送达与执行结果真相源。报价变化交回Cross08重新采用，不在平台自动减量、改日期或补预算。
- 确认和VerificationSummary都展示数量、原服务单价、行小计、最晚送达、商品/商户、账户及既有必要内容；冻结继续含限定释放条款。精确时间原样绑定，裸日期只沿原明确转换规则，不将18点变为日末。
- 下单原快照与实际请求完整一致，金额/数量/时间变更使旧确认不适用。核销显示来自已创建订单及原创建参数绑定，不拿最新商品报价改写已有未付订单。配送只掩码展示，不把原文加进普通显示/模型。
- 已冻结后新增计划核算由Cross08/06负责；平台不得追加冻结、换账户、自动增预算或重新授予扩大后的资金权。
- 内部项/attempt的具体最小候选与旧单件兼容见下文G3表，仍只供Cross08核对，不能把本稿当作对方已确认的协议。

## 4. 确认/验证退回编辑：具体缺口与拟议接缝

### 4.1 现行拒绝路径与契约裁定G1

真实状态为waiting_approval + interaction.kind=confirmation或verification，**没有新增waiting_verification枚举**。
拿该interaction_id提交F10，current_input_task因非input拒绝；走普通draft又因module=cross拒绝。
F15 cancel表示停止，安全get/create/answer也没有“撤离但不终止原任务”的现成语义。
用新确认覆盖旧版本只能在已有新动作时使用，不能伪造一个动作/过期时间来换取编辑许可。

**建议G1（待Erwin按§8与安全/API/Cross/前端协同确认）**：复用F10原请求体，仅增加Cross当前确认/验证卡的一个受控“修改未提交部分”选项分支。
输入仍只有request_id、interaction_id、selected_option_id（text须为空）；选项ID由后端发布并绑定当前任务/执行项/原operation/确认版本，客户端不提交actor、可编辑布尔值或安全通过标记。
普通F10继续只答input；新分支不把普通text/provide_input或模型revise开放到确认态。F15仍只有approve/cancel，不把编辑改成资金批准或取消整个任务。

输出复用TaskView：撤离与Cross检查点完成后，同task_id、新task_revision、新interaction_id、waiting_input；
抢先提交/未知时仍沿原操作显示核实状态，不假装已进入编辑；越权/过期/旧交互按既有拒绝。
可复用allowed_actions现有值，无新增公共状态或权限等级；新选项只在新后端明确发布后可用，旧卡片/普通模块行为不变。
**这改变F10适用状态及暂停恢复语义，当前契约并未批准**，不是“原接口已足够”。
若G1不采用，中控须选择另外的明确入口并更新本设计；不能由API票擅加端点或在平台先放宽检查。
现有类型可表达所提字段与状态，暂不造contracts运行代码票；G1收口须同步正式契约和必要模型/样例，若最终必须改模型，再由contracts单目录追加具体票。

### 4.2 Security真正需要提供的能力G2

[02：尚未提交动作的原子撤离守卫](issues/02-security-retire-unsubmitted.md)独占backend/app/security/。以下是拟议后台语义，未存在、未批准实现：

- 输入：可信context、原动作/operation/action_revision/确认版本与参数绑定、原编辑请求关联；均从原任务取，不信body自报。作用只限当前生日动作，不是通用取消权限。
- 在与claim_execution竞争的**同一持久事务边界**，核对归属/原绑定/任务未终止；仅当不存在已领取执行的claim，才记录不可恢复的旧attempt撤离事实并阻止未来claim。
  “查到无claim”再单独写标记或只有进程内锁不合格。旧验证后来成功也不能使旧动作恢复写入。
- 后台返回语义：原绑定已安全撤离且必要审计齐备（含幂等原记录引用）；或已有claim须原号观察；或拒绝/依赖不可用。按可信task及原编辑request须能只读找回同一撤离记录，以覆盖撤离后平台快照尚未写入的断点。未审计齐备不能作为可编辑输出。命名/存储形状由安全方收口，不新增公开SecurityDecision/ConfirmationDecision值。
- 已有claim无论processing、unknown还是completed，都不能只凭状态推断无提交；completed也可能是银行失败，交原号观察其准确结果。
- 旧确认/验证、原授权快照和失败事实保留，不把cancelled/expired改作隐含“编辑”，不清空任务安全终止。安全02同时约束gate/claim/旧验证回调，不让任何旧路径绕过撤离。
- 待冻结验证可能已有§3.5的pending_freeze授权：原动作确证未提交并撤离后，须以该原绑定处理旧未生效授权（现有pending_freeze→invalid可复用，具体由G2审阅），保留历史且不挪用到新freeze_operation；不能让新input后的停止反复查询一个永远未提交的旧冻结而假报未知。新冻结仍须新的有效冻结确认/限定授权；已有真实冻结及其active合法收尾不作废、不追加资金。授权与原动作事实矛盾时拒绝，不猜测清除。会话级验证是否可复用只沿原规则，动作级验证不跨新attempt扩权。
- 必要审计写入失败仍fail closed，先复用既有事件和证据引用；审计本身未证实需要audit/storage新原语。G3候选不可变保存的独立缺口见05，不与审计原子事务混称。
G2须Erwin本人按本阶段代行安全职责明确审阅；AI设计通过不代替其决定，也不写成Ringo本人签核。

**S-G2提出的补齐条件全部纳入，不能把上述初稿直接用于实施。** 以下分清不应削弱的约束和待选择的新语义；通俗例子与两种范围见[本人决策稿](decision.md)。G2-A/B/C是本次安全问题编号，与此前D1/D2业务裁定无关。

| 必须保持的现有约束 | 必须补齐的提供条件，尚未实现 |
|---|---|
| 旧参数/旧确认不批准新动作；原失败/终止不可复活 | 撤离事实不仅与claim竞争，还须覆盖旧确认重发、迟到批准、grant/store/bind限定授权和平台birthday_release指针回写。旧grant在撤离前胜出须按同一原attempt处理pending；撤离胜后不得再创建旧pending，指针回写须校验原attempt与CAS，不能覆盖新指针 |
| 发码前后不能靠列表为空推断安全；验证失败/时限规则不变 | gate先verification_preparer、后remember_challenge，存在准备中/已发未登记窗口。发码准备资格必须先持久并与撤离排序；准备结果未知不可编辑。旧挑战的发码/重发、验证码/人脸回调也受原退役绑定控制，不能迟到重建旧资格。选收窄范围也需要这个守卫，不是只隐藏验证码卡按钮 |
| 现行同任务failed/动作级expired会阻止后续动作，旧会话事实也可能终止任务 | **G2-B尚待本人选择**：完整支持时，是否仅将“在权威失败/到期/终止前已经安全撤离”的确切旧动作挑战排除出撤离后的新方案任务级判定。未选择前不排除任何旧挑战；已发生失败、已到期但尚未刷新字段、已有终止均不能因编辑清除。错误次数/时限历史不删、不重置；会话级与其他未撤离动作不扩用例外 |
| 原确认必须真实可读，不改写旧决定 | create_confirmation复用ID并UPSERT覆盖JSON，单留旧ID/版本可能悬空。替换前保存当时**完整可读的脱敏确认版本**、原参数绑定及必要验证/授权快照或真实可回读的不可变版本；配送/秘密原文不进入普通证据。不得伪造cancelled/expired |
| 必要审计失败不能给出可编辑事实 | 优先用现有AuditJournal.append_in_transaction在同应用库连接内与撤离记录共同提交，失败整笔回滚；另开append事务不等于原子。若撤离已持久但证据不齐，旧动作继续封锁，补齐同一原事实必要记录后才恢复发布，不能把有记录当已审计，也不回滚成旧动作可写 |
| 未提交、银行失败、真实冻结是不同事实 | G2-C接受何种pending→invalid新原因待本人确认；现finalizer将invalid解释成FREEZE_FAILED。须保留明确的“安全撤离、未提交”依据并正确呈现无冻结，不能伪造银行失败；active真实冻结的原限定收尾不得作废 |

本轮额外静态核对：[银行验证服务](../../backend/app/services/mock_bank/verification.py)create_verification也会扫描同任务旧failed/动作级expired并抛VerificationTerminated，不只是gate扫描。因此完整选项不能只在security忽略旧挑战；安全、API验证回调及银行验证提供方须证明共享的权威退役/失败/到期胜序。现有应用库与银行库不是已证明的跨库原子边界。若仅凭读取后字段或回调到达时间不能证明，保持blocked；必要提供目录差异交中控追加，不让02/03越界改services或预建通用事务框架。既有动作级验证失败规则不改写成“可错三次”。

**尚待本人选择**：G2-A是否允许已批准但未claim的原动作非终止撤离；G2-B选完整或首批收窄，以及旧挑战后续任务级作用的精确范围；G2-C是否接受确证未提交作为pending授权退役的新原因和真实展示。两选项都须满足历史、迟到授权、准备竞态、审计及恢复条件。收窄建议不是当前最终范围，确认和验证等待态的原要求完整保留。

### 4.3 平台撤离/恢复与Cross交接G3

[03：原任务受控进入未执行编辑](issues/03-platform-edit-handoff.md)只改agent_platform，依赖01/02；[04：F10受控编辑接入](issues/04-api-edit-entry.md)只改api，依赖03及G1。

拟议平台专用后台入口接TrustedContext + 原F10 request/interaction/option；从当前任务重读目标，固定原候选、项/attempt/操作、状态与版本。
它不接受source=human、editable=true或客户端候选hash，不注册为模型工具；普通resume不能凭字典声称已撤离。
平台与Cross08需先约定一个受控的“进入原任务编辑”方法/命令：Cross消费后台核实的持久撤离引用，修改自己的检查点并返回新input；API或模型不能伪造该引用。**该方法目前没有实现，G3待双方确认**。

顺序收口为：03先以原CAS固定同一编辑请求、精确源已发布ref与唯一待发布ref → 安全02按本人所选范围排序并审计，或原号核实明确失败 → Cross08只按该源准备隔离候选 → 05封存唯一胜者 → 03以严格原版本在同次任务CAS发布胜出ref/结果/完成投影。准备受理记录失败不开始撤离；必要审计未齐不交Cross；候选落库不是已发布。
同一请求恢复沿同一撤离记录与原绑定，不重新授权/新建attempt；安全撤离成功而检查点/结果CAS/HTTP回执失败时，旧动作仍不能写，新input未完成则不假报已完成。
重开后先按原记录恢复发布，再接新的数量输入；不能把当下新计划当原请求结果。正常快照、生日原参数和预算来源历史均保留。
API04保留receipt参数冲突、当前会话/轮次/归属和原交互检查；中断恢复只限已有持久编辑事实的精确请求，不给所有F10开重试。

| 原状态/事实 | 进入编辑的条件与必须保留的事实 |
|---|---|
| waiting_input安全节点 | Cross08沿原F10处理；如果尚无待执行动作，不需要伪造安全撤离。不能以此局部通过替代以下等待态 |
| 等待冻结/下单/核销确认或验证，尚无claim | 安全02原子撤离成功后才能离开旧卡；未改变的项仍保留。若是核销，已建未付订单必须保留并计入后续待支付，不许改其商品/数量 |
| 批准与编辑并发 | 若只批准但未claim，安全守卫仍可使旧动作不再领取；若claim先胜，编辑不能宣称成功，先观察。SQL事务决定先后，不按按钮/HTTP先到猜测 |
| 已有claim / 结果未知 | 不进入可能在途项编辑，不换操作号；B14精确核实原操作。not_found或查询异常本身不是“未提交”证明 |
| 银行明确失败且证实无订单/无在途，父任务仍可办理 | 保留原失败attempt/operation/result；只对可替代的未成单部分进入新方案，用户重新采用/确认后建新attempt。银行操作失败不等于父任务已终态；已终态父任务不复活。不是把所有失败退化为只能停止 |
| 已建未付/已付订单 | 原订单不可改，付款/未付款事实不抹除；仍可编辑其他已证实未成单且无在途的部分。撤离尚未提交核销后，原未付订单后续付款需新有效确认，不复活旧撤离attempt |
| 取消/终态/安全终止/旧会话 | 不恢复购买；仅现有历史读取和获准收尾。冻结/释放未知先核实，不用编辑绕过资金约束 |

私有安全状态的持久事务和原任务CAS不要求一个跨层大事务：安全撤离先持久，任务发布晚失败时保持拒绝并可受控恢复。
本轮静态核对已明确候选不可变保存缺口，补[05：候选检查点一次封存](issues/05-immutable-edit-checkpoint.md)，仍不跨目录实现或承诺已验证原子性。精确读取和task CAS复用现有能力，发布策略由03/08实现；memory已有归属与namespace透传，未证实其新增缺口，不另拆票。

#### G3最小内部快照候选（待Cross08逐项核对，不是公共新模型）

沿用BirthdayPlan已有账户、预算引用/上限/冻结金额、deliver_by、delivery_ref和items，不重复造购物车。下列仅描述后台字段关系，不是客户端可上传的数据。

| 快照 | 建议最小内容与来源 |
|---|---|
| 计划与执行项 | 原plan_revision；稳定item_id（如已有step_id可保持一一对应即复用）；product_id、merchant_id/name、name/category沿原服务事实；quantity、unit_price_fen、amount_fen（行小计）及原服务报价绑定；共同deliver_by/delivery_ref仍在原计划上，不把配送原文复制到项 |
| 一次动作尝试 | **复用operation_id作为attempt身份**，不另造无意义的第二UUID；绑定item_id、action_name（freeze/order/capture）、action_revision、parameters_ref和不可变原参数；相应order_id/原银行结果保留。冻结仍是任务资金动作，不假装成商品项 |
| 旧确认/验证/授权 | confirmation_id/version之外，须有当时完整脱敏确认/参数/必要授权验证快照，或确能回读的不可变版本引用；challenge/限定授权引用也绑定原operation。旧可变ID查询不能冒充当时历史 |
| 编辑受理事实 | 可信主体/会话/轮次/原task、原F10 request/interaction/option、后台接受task_revision/后续dispatch关联、plan_revision及项/operation/action_revision；必要审计/冻结依据；源已发布与预留候选完整ref（thread+namespace+id）、源内容绑定和同edit_ref的胜者完成投影。记录不是新购买授权 |

后台依据分两条，**不得混成一张“无claim证明”**：

- `withdrawn_unsubmitted`：安全02原子撤离且必要审计齐备，附原绑定、撤离/审计引用和本人所选范围下的挑战/未生效授权处理事实。
- `verified_failed_no_order`：原operation精确银行失败结果及无订单/无在途依据、保留的原claim/attempt和可办理父任务；这里可能已经claim，不要求或伪造无claim撤离记录。claim.state=completed本身不是此依据。

明确失败入口也分清来源：若此前已有精确编辑受理事实，先沿原request/operation核实，再受控恢复该请求，不能被当前interaction=None截断或当成新授权；没有原受理事实时，不拿旧确认ID调用编辑捷径。由Cross08沿原query/resume核实失败并保存后，发布**新的普通input替代选项**，用户再走当前F10选择/采用，原失败不改，新购买仍逐动作确认。

原waiting_input且没有待执行动作的安全节点仍走Cross08原F10，无需制造上述证据。未知、不可判断、已有终止及部分完成终态均不是可编辑依据；needs_attention或现_task_terminated返回false也不够。

#### G3最小调用候选与兼容

优先保留BirthdayPorts现有order_check/order_execute/capture_check/capture_execute、GateAnswer.operation_id及WriteOutcome，不建立通用新授权框架：

1. check输入项增加明确item_id/quantity/unit_price_fen，与原plan字段组成快照；返回现有operation_id，Cross在任何execute前持久保存该次原号与稳定item_id/参数绑定，不再只记product_id。包括非冻结动作ALLOW后直接_submit的分支，不能只在等待确认时保存；冻结ALLOW仍按原规则拒绝。
2. 新协议的execute必须带回该次check所得operation_id及原项绑定（建议后台keyword参数；最终签名待Cross确认），平台核对它与当前未撤离attempt一致；不得按“最新相同商品”重挑operation。查询沿现有requery并带**精确原operation_id**；新替代项产生新原号，同一尝试恢复不换号。
   限定授权继续优先用现有grant_release/bind_freeze，但拟要求显式传递原pending.operation_id与原确认版本或等效冻结上下文（bind已有原号参数优先复用）；平台以捕获的原attempt校验，不能迟到后再按当前freeze键选取“原动作”。该兼容签名也待Cross核对。
3. 旧显式quantity=1不等于新协议；旧显式1/省略为1只在后台旧绑定、每商品一项及原操作/参数唯一对应可核验时兼容。quantity>1或服务端已有新item/operation绑定的调用，缺身份不能静默回落旧键；协议来源或唯一映射不明则blocked。旧已办/未知只沿保存原号查，不猜测重建；本条不把quantity>1或客户端标记当新授权。
4. 拟议Harness后台`begin_birthday_edit(trusted, input_request_id, interaction_id, selected_option_id)`只接G1专用入口；加载后台冻结事实并预留唯一ref。拟议Cross后台`enter_birthday_edit(trusted, edit_context, thread_id)`还须接精确源已发布ref和预留候选ref，返回后台包`edit_ref/source_checkpoint_ref/candidate_checkpoint_ref/ModuleResult`，不是自行发布。**两个方法当前均不存在，命名/签名及读取责任待双方核对。**edit_context不是普通resume字段、模型工具或客户端标记。
5. Cross只写隔离待发布候选，03读取05首次胜者再CAS同次发布引用/结果/版本/完成投影。G3任务普通恢复和异常路径只读已发布ref；handoff未完成不推进旧动作，不能沿用默认latest。候选或CAS失败不宣布新input生效，完成请求只重放原胜者，取消/新会话/终态先胜后不得回挂孤立候选。详见[对账协议](g3-reconciliation.md#最小协议候选先预留后安全再隔离准备最后发布)。

**对账例子**：原花item-A/order-A/capture-A已付199；蛋糕item-B的order-B尚未提交且合法撤离，换同款花建立item-C/order-C/capture-C，新花仅199、累计398。原A不改成quantity=2，B的撤离历史不删；原冻结500不变，无在途且全部结清后差额仍由银行事实核实。若B原操作已经明确银行失败且无订单，则保留B失败，走第二种依据提出C，不删除claim以凑第一种依据。

Cross08的727045d §7已认可原operation承担attempt身份；step_id复用须稳定一一对应，不能拿现商品键硬充。execute显式回传、确认版本/冻结上下文读取与grant/bind具体签名、两种依据的实际提供、新input检查点/05封存及发布恢复仍待核对/交付。这里只记录消费方已作的局部认可，不代其确认全部G3，也不改其08/06票。

896fd7e §8进一步接受05/发布的窄方向，尚非真实能力。05输入不再仅限edit/source：新生日及场景澄清起点以原task/start受理关联和版本预留无前驱根候选，无edit/source不伪造；普通输入/事实/异常转换沿原请求或原运行事件的持久关联，以最后已封存且已发布ref为源预留新候选。05封存完整首份胜者，03同次CAS发布完整ref/ModuleResult/版本/完成投影；所有根、普通和编辑状态发布后同等不可覆盖。根重试沿原start，普通缺源/历史不明不得伪装根或回latest，未发布转换不得被新普通调用越过；详细条件见上述初始与普通发布段。数量字段兼容与源保护分别满足，不互相豁免；不增加通用框架、公开字段或重复票。

## 5. 最小拆票与下游开始条件

| 票 | 唯一实施目录 | 实际前置与交付 |
|---|---|---|
| [01 数量/稳定项/展示](issues/01-quantity-item-binding.md) | agent_platform | 与Cross08约定内部项/attempt；按同文件顺序先处理原PR296。无需等待293即可隔离验证数量装配 |
| [02 安全撤离](issues/02-security-retire-unsubmitted.md) | security | G2本人安全审阅；提供无claim与claim原子竞争的窄拒绝接缝，不依赖Cross08完整实现 |
| [03 原任务编辑交接](issues/03-platform-edit-handoff.md) | agent_platform | 01 + 02 + 05 + G3；与PR298同Harness改动按中控安排顺序。可用明确stand-in自验，真实Cross由08消费 |
| [04 F10接入](issues/04-api-edit-entry.md) | api | 03 + G1；不代做预算来源API02，也不将其未合当成商品编辑的业务依赖，具体同文件顺序交中控 |
| [05 候选不可变封存](issues/05-immutable-edit-checkpoint.md) | storage | 同一窄能力封存G3初始无前驱根、普通输入/事实/异常后继及编辑候选；与03/08先约定ref/可信转换绑定，交付后03方可验证单胜者/发布。无需等03/08代码先完成 |
| [06 银行验证侧挑战退役](issues/06-verification-retirement-authority.md) | services | 2026-10-26 核对 G2-B 后新增（[胜序设计](verification-authority.md)）；银行库单一权威判定「撤离先于失败」，任务级扫描忽略已退役挑战、拒绝对已退役尝试再建挑战。02 消费本票，06 先于 02 交付 |

原01—04及新增05全部planned/blocked，实施还需中控明确授权；03的真实前置补05。G1/G2-A/B/C/G3不闭合不能把确认或验证等待态编辑标完成。若本人选首批收窄，验证码/验证等待仍blocked，原完整需求不删；本稿不激活任何票。
Cross08的数量/安全节点局部可在01接口稳定且实施获授权后推进；整票仍需02→03→04接入与原等待态组合验证；个人预算路径另等原cross06及其既有依赖。
真实联合验收复用[v05-cross-e2e/03：生日E2E](../v05-cross-e2e/issues/03-birthday-e2e.md)，页面承接[v05-cross-frontend/02](../v05-cross-frontend/issues/02-birthday-ui.md)，不另造总验收票、不修改其状态。

## 6. Testing Decisions（只设计，未运行）

最高接缝优先真实F10/确认/验证入口→同一Harness/Cross→隔离银行；组件测试只用于准确制造并发/中断，不替代整条路径。
下列编号映射Cross08 Q01—Q10及原XL-B01—B07/X02/X05/X08：

| ID | 以后实施时的外部检查 |
|---|---|
| P01 / Q01/Q08 | quantity=2，单价199元，小计398，确认/验证/请求/订单/送达完全一致；变价不盲提 |
| P02 / Q09 | 花已付199，蛋糕换同款花；两个执行项/订单/付款不同，旧原号可查，新项只付一次，总398 |
| P03 / Q03/Q06 | 三动作的确认与验证等待都能受控撤离；旧批准/旧验证迟到零原动作写，任务仍原号新input；待冻结撤离后停止应保留零资金事实，不把未生效旧授权当未知冻结 |
| P04 / Q06 | 跨进程编辑/claim竞争，含已批准但未claim；claim胜后沿原号观察，不借not_found换号 |
| P05 / Q05/Q10 | 原下单明确失败且无订单可替代；已建未付、已付与未知对照不可改写，原失败保留 |
| P06 / Q06 | 撤离后、记录后、Cross检查点后、结果CAS后及HTTP回执前各断点，重开/重复/同号异参/新会话/轮次不乱写 |
| P07 / Q02/Q04/Q07 | 数量/时间/价格变化重新采用确认，冻结后原资金/个人预算/占用不重置；未付项继续计待支付 |
| P08 / Q03/Q06/Q08 | 越权/终态/安全终止/审计依赖故障拒绝；配送掩码，普通F10与转账/订阅旧流程兼容 |
| P09 / Q03/Q06 | 发码准备资格/实际发出/登记与撤离的各种胜序；晚到grant/store/bind及birthday_release CAS不得重建旧pending或覆盖新指针；准备结果不明不编辑 |
| P10 / Q03/Q06 | 旧挑战失败/到期先胜、撤离先胜、旧会话及懒刷新时限；安全gate与银行验证两侧一致，已发生终止不可复活；本人选首批收窄时验证态仍blocked |
| P11 / Q05/Q06 | 新确认UPSERT后旧完整版本仍可回读；必要审计失败回滚，撤离已持久但审计不齐保持封锁，重启不把有记录当已审计 |
| P12 / Q03/Q06 | 精确ID仍可能被同namespace/channel-version覆盖；隔离候选不可变，旧put/put_writes不能绕过 |
| P13 / Q03/Q06 | 同edit_ref跨进程双准备只返回同一持久胜者；候选写后任务CAS失败，普通/异常resume仍读已发布源且不推进旧动作 |
| P14 / Q06 | 候选封存、发布CAS、receipt各断点；取消/终态/新会话/其他方案胜出则孤立候选不生效；历史重放不回挂旧input |
| P15 / Q03/Q06 | 旧显式quantity=1/省略1且唯一映射可核验仍兼容；quantity>1或后台新绑定缺身份不降级、协议/映射不明blocked；缺源ID/值绑定不回latest补证；check含非冻结ALLOW直交分支及execute/grant/bind均捕获并回传原绑定 |
| P16 / Q03/Q06 | 无edit_ref/无source的新生日及场景澄清根，首次写前预留原task/start关联；封存、CAS发布、同start重试及各断点均守同一根胜者，无旧源不暴露候选；旧缺ID/普通缺源不能冒充初始化 |
| P17 / Q03/Q06 | 无编辑请求的普通输入/事实/异常更新绑定原请求或原运行事件/接受版本，从已封存已发布source准备新隔离候选；完整值/元数据/关联不被旧put/put_writes覆盖，CAS失败不活动、不重做外部写、重放不回挂旧输入；正常/异常记账均不取latest |

P16/P17与既有P01—P15均为未来验收设计：先按票定向验证03/05边界，再由08/04接线后交既有E2E03承接。真实E2E由Erwin后续亲自安排；本轮完成设计与独立双轴回交后即停，不自动启动S01或三主线真实E2E、不实施生日01—05。

实施时分开记录平台局部、真实安全/银行装配、HTTP、页面/模型E2E和本人安全接受。本轮只做内容、链接/锚点、编号、格式、diff空白检查，不运行测试、模型、全量或CI。

## Out of Scope / Further Notes

2026-10-27 后续授权补充：用户明确要求完成非比赛资料任务，中控委派 [12：重置后的业务时钟与可信轮次接线](issues/12-demo-runtime-clock.md)。该票仅在平台消费银行公开重置轮次与成功起点，提供业务时钟 setter 和公开 bank；业务日期可调整，确认/验证/安全授权时限及网络等待不受影响。API 整体管理协调另票；平台不清任务历史、不伪造排空或完成状态。原规划阶段的禁止实施/PR 停线不适用于这张已明确授权的新票，历史证据保持。

不新增撤单、退款、追加冻结、换账户、自动增预算/新风险事实，不改变#160或既有限定收尾。
不修改Cross08/06、PR298/296、原组合证据、共享跟踪/completion/包状态，不推送或创建PR。
已读取本机to-spec/to-tickets模板：disable-model-invocation且无显式调用入口，按本次已授权材料/最小拆票手工整理，不声称调用斜杠技能；本轮planned/blocked优先，不标ready-for-agent，也不将规划当实施授权。
