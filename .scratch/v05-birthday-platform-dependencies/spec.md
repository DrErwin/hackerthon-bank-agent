# 生日数量与未执行修改：平台提供条件及最小规格

Status: planned / blocked — 2026-10-25，仅只读核查、设计与最小拆票；未授权实施。
Owner: Erwin（v0.5统一负责）；Planning assignee: Codex，01a1718a-26a3-7523-a0bf-2591d8e83618。
Implementation assignee / accepted at: 未领取。

## Problem Statement / 固定依据

用户应能真正订两束花，并修改尚未形成订单且没有在途提交的剩余方案；不能只改页面数量，也不能让旧确认在修改后继续写入。本轮没有运行复现，以下均为固定源码推演。

- 本worktree起点 main `af779df431a7f650851ffe3e2ede8b763dcdb1c5`；独立分支 `codex/v05-birthday-platform-dependencies`。中控材料入主线后，本地文档基线快进至`dab17d030b4a4a481280d5cc5900176db38c9aeb`，仅文档变化，所查运行代码未变。
- Cross材料固定提交 `1d7f1fab8d5e2622c1d319e178abf9f1654fc73c`，基线608255f，读取该提交完整三份文件，不以其最后一条commit的单文件差异代替材料：
  [缺口/数量设计](../v05-cross-business/birthday-quantity-gap.md)、
  [设计审查](../v05-cross-business/birthday-quantity-design-review.md)、
  [v05-cross-business/08：生日商品数量与未执行部分调整](../v05-cross-business/issues/08-birthday-quantity-and-unexecuted-revision.md)（planned/blocked，不修改）。三份main文件blob与固定1d7f1fa内容逐一相同。
- 原[PRD §2.4](../../docs/prd/06-跨场景联动-PRD-2026-09-23.md#24-xl-b家人生日安排)：流程4展示数量/费用/时间，流程7只改未执行部分；失败与收尾明确不撤单/退款、未知沿原号。
- [现行契约](../../docs/contracts/公共契约-2026-09-23.md)：§5.4、§6.5 F10/F15、§3.5与§8；[安全原则](../../docs/principles/02-security-platform.md)保持确认绑定和原操作恢复。
- 已查main、所有本地/远端已取回refs的本组路径历史：新slug尚无票；原platform13/PR292、14/PR296虽未合仍占号，不在原组重占。Cross07/08与预算来源01/02均不改；原security01/04不是本次安全撤离交付。

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
| [任务快照/CAS](../../backend/app/storage/application.py)、原检查点 | 可保存任务私有记录、版本、原操作引用并恢复；security已有同库私有持久状态 | 未发现必须新增ApplicationStore表/方法的证据，暂不建storage票；安全记录由security所有，不能让平台直接改其SQL |

PR296固定b41ef64、PR298固定5ebc133均仍是待合来源，必须保留其订单范围门、来源隔离和快照保留规则；本轮只读，不修改原PR或组合证据。它们不交付本次数量或安全编辑能力。

## 2. Solution / User Stories

1. 选两件时，下单、确认、验证摘要与最终回执都对应两件及真实总价，时间不丢失。
2. 已付花199元、未下单蛋糕换为同款花时，原花保留，新花是另一执行项/订单/付款；合计398，不把旧花改成两件。
3. 确认或验证时请求编辑，后台先证明并锁死旧未提交动作，再回原任务新input；页面隐藏按钮不能替代这一事实。
4. 若批准/提交先发生或结果不明，先查原操作；已建未付订单、已付消费、失败事实保留，只有明确无订单/无在途的失败可提出新替代。
5. 任务终止/会话无效/越权不能借编辑复活；原账户、原上限、原冻结和个人预算规则不被修改重置。

## 3. 平台自身可补：数量、执行项与确认

由[01：真实数量与稳定执行项装配](issues/01-quantity-item-binding.md)提供；Cross08仍负责候选、数量输入、计划核算与编辑业务。

- 与Cross08先约定内部项快照：服务端稳定执行项标识（优先已有step_id/内部计划项）、product_id、quantity、服务单价、行小计、送达时间/受控配送引用；不新增公共字段。方案变更不是把所有未变项的身份重建。
- 兼容现有尚未升级的单件调用：其省略quantity只代表原有1件语义、每商品一项约束；新数量/同款多项协议必须显式给出稳定执行项及quantity，不可缺字段后默默回落为1。旧在途/已办映射保留，无法唯一关联不猜测重签；接口切换与Cross08共同确认并验证原单件链路。
- 新替代项使用新执行项；同项未提交动作被合法撤离后，新参数有新attempt/operation/确认；原attempt不改写。未撤离attempt的同参重放/未知观察保持原attempt与operation；已撤离attempt即使参数相同也不能复活。不能只拼product_id或plan_revision。
- _enriched、order/capture键、参数查找、原号观察必须都能唯一找到执行项/attempt；保留已成功、明确失败、未知及撤离的原记录，不覆盖旧键而失去原参数。已有旧任务无法唯一映射时不得猜测合并；仍保留历史，不能计作编辑覆盖完成。
- 真正CreateOrderInput透传quantity，amount为服务单价×数量的行小计；银行仍是价格/可购/送达与执行结果真相源。报价变化交回Cross08重新采用，不在平台自动减量、改日期或补预算。
- 确认和VerificationSummary都展示数量、原服务单价、行小计、最晚送达、商品/商户、账户及既有必要内容；冻结继续含限定释放条款。精确时间原样绑定，裸日期只沿原明确转换规则，不将18点变为日末。
- 下单原快照与实际请求完整一致，金额/数量/时间变更使旧确认不适用。核销显示来自已创建订单及原创建参数绑定，不拿最新商品报价改写已有未付订单。配送只掩码展示，不把原文加进普通显示/模型。
- 已冻结后新增计划核算由Cross08/06负责；平台不得追加冻结、换账户、自动增预算或重新授予扩大后的资金权。

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
- 后台返回语义：原绑定已安全撤离（含幂等原记录引用）；或已有claim须原号观察；或拒绝/依赖不可用。按可信task及原编辑request须能只读找回同一撤离记录，以覆盖撤离后平台快照尚未写入的断点。命名/存储形状由安全方收口，不新增公开SecurityDecision/ConfirmationDecision值。
- 已有claim无论processing、unknown还是completed，都不能只凭状态推断无提交；completed也可能是银行失败，交原号观察其准确结果。
- 旧确认/验证、原授权快照和失败事实保留，不把cancelled/expired改作隐含“编辑”，不清空任务安全终止。安全02同时约束gate/claim/旧验证回调，不让任何旧路径绕过撤离。
- 待冻结验证可能已有§3.5的pending_freeze授权：原动作确证未提交并撤离后，须以该原绑定处理旧未生效授权（现有pending_freeze→invalid可复用，具体由G2审阅），保留历史且不挪用到新freeze_operation；不能让新input后的停止反复查询一个永远未提交的旧冻结而假报未知。新冻结仍须新的有效冻结确认/限定授权；已有真实冻结及其active合法收尾不作废、不追加资金。授权与原动作事实矛盾时拒绝，不猜测清除。会话级验证是否可复用只沿原规则，动作级验证不跨新attempt扩权。
- 必要审计写入失败仍fail closed，先复用既有事件和证据引用；未证实需要audit/storage新原语，不先拆新票。
G2须Erwin本人按本阶段代行安全职责明确审阅；AI设计通过不代替其决定，也不写成Ringo本人签核。

### 4.3 平台撤离/恢复与Cross交接G3

[03：原任务受控进入未执行编辑](issues/03-platform-edit-handoff.md)只改agent_platform，依赖01/02；[04：F10受控编辑接入](issues/04-api-edit-entry.md)只改api，依赖03及G1。

拟议平台专用后台入口接TrustedContext + 原F10 request/interaction/option；从当前任务重读目标，固定原候选、项/attempt/操作、状态与版本。
它不接受source=human、editable=true或客户端候选hash，不注册为模型工具；普通resume不能凭字典声称已撤离。
平台与Cross08需先约定一个受控的“进入原任务编辑”方法/命令：Cross消费后台核实的持久撤离引用，修改自己的检查点并返回新input；API或模型不能伪造该引用。**该方法目前没有实现，G3待双方确认**。

顺序必须是：核对原任务和当前绑定 → 安全02持久撤离/原号观察 → 固定编辑请求记录 → Cross08进入编辑检查点 → 现有任务CAS发布新input。
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
若实施发现现有存储不能持久重放该关联，应回中控提供失败步骤再补storage单目录票；本轮不跨目录实现或承诺已验证原子性。

## 5. 最小拆票与下游开始条件

| 票 | 唯一实施目录 | 实际前置与交付 |
|---|---|---|
| [01 数量/稳定项/展示](issues/01-quantity-item-binding.md) | agent_platform | 与Cross08约定内部项/attempt；按同文件顺序先处理原PR296。无需等待293即可隔离验证数量装配 |
| [02 安全撤离](issues/02-security-retire-unsubmitted.md) | security | G2本人安全审阅；提供无claim与claim原子竞争的窄拒绝接缝，不依赖Cross08完整实现 |
| [03 原任务编辑交接](issues/03-platform-edit-handoff.md) | agent_platform | 01 + 02 + G3；与PR298同Harness改动按中控安排顺序。可用明确stand-in自验，真实Cross由08消费 |
| [04 F10接入](issues/04-api-edit-entry.md) | api | 03 + G1；不代做预算来源API02，也不将其未合当成商品编辑的业务依赖，具体同文件顺序交中控 |

全部planned/blocked，实施还需中控明确授权。G1/G2/G3不闭合不能把确认等待态编辑标完成。
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

实施时分开记录平台局部、真实安全/银行装配、HTTP、页面/模型E2E和本人安全接受。本轮只做内容、链接/锚点、编号、格式、diff空白检查，不运行测试、模型、全量或CI。

## Out of Scope / Further Notes

不新增撤单、退款、追加冻结、换账户、自动增预算/新风险事实，不改变#160或既有限定收尾。
不修改Cross08/06、PR298/296、原组合证据、共享跟踪/completion/包状态，不推送或创建PR。
已读取本机to-spec/to-tickets模板：disable-model-invocation且无显式调用入口，按本次已授权材料/最小拆票手工整理，不声称调用斜杠技能；本轮planned/blocked优先，不标ready-for-agent，也不将规划当实施授权。
