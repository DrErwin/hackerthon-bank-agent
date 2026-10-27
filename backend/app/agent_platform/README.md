# agent_platform —— Agent 平台（Harness 层）

归属：底座（Erwin）。本目录只接公开能力，不访问转账私有工具或银行规则。

## 明确规划失败的消息结果（v05-birthday-platform-dependencies/14）

`DeepAgentPlanner`仍严格拒绝缺失、多份或无效的受控outcome，不把自由回复补成业务提案。`handle_message`在尚未创建任务的分类阶段，将明确`PlanningError`回传为既有`MODEL_PROPOSAL_FAILED`失败ModuleResult，固定提示重新表述或查看原任务卡片；原`model.finished`审计保持failed，不记录原自由回复，也不宣称资金处理或风险拦截。API消费现有失败分支完成原消息，同request重放与重启不再次推理，旧待办不被替换。其他未知中断仍遵守原恢复规则；此改动不将历史B失败改为通过。

## 生日会话恢复的原尝试证明（v05-birthday-platform-dependencies/13）

敏感卡发布时，平台在原 G3 严格 CAS 所封存的私有 metadata 中保存 action/option 摘要，仅含 hash，不把配送原文加入 Cross checkpoint。新会话迁移前固定该已发布来源，迁移后、Cross 恢复回调之前消费安全330的同事务校验与真实银行原挑战退役证明；安全受理/封存使用真实UTC。只有 sealed 后才用一个 task CAS 关联唯一新attempt并保留原history。已有claim、真实active冻结或银行无法证明未提交时，仅保留原号观察，不制造新attempt或改旧授权。

Cross 消费只读 `ports.session_recovery_status(trusted)`（同能力也由 `birthday.handoff.session_recovery_status` 提供）：返回 `None` 或 `{status: fresh|observe, original_operation_id, action_name, action_revision, replacement_operation_id}`。fresh 的 replacement 是唯一新动作，必须新确认/验证；observe 的 replacement 为None。它不返回参数/配送资料，也不使 Cross 获得修改证明的权限。

**历史边界**：旧敏感源缺少封存摘要，或当前参数不匹配当时已发布摘要时明确 `SOURCE_UNAVAILABLE`，不从当前可变快照补真。因此这类旧任务不能自动跨会话恢复，原历史保留。非敏感G3/legacy边界保持。Cross09仍须另票接入自己的恢复SOP；当前缓存旧卡继续拒绝，不能将本提供方通过写作完整会话闭环。

## 演示重置的时间与轮次（v05-birthday-platform-dependencies/12）

`local_demo.build_runtime` 公开 `runtime.bank` 与 `runtime.set_demo_clock(at)`。银行业务、账单、订阅、联动共享可变业务时钟；确认、验证码/人脸有效期、安全记录和网络等待仍按真实时钟。未装配业务时钟的通用 `TransferRuntime` 调用 setter 时明确报 `DEMO_CLOCK_UNAVAILABLE`。

安全策略、记忆和生日平台的当前轮次读取银行持久 `current_demo_round_id`，只有尚无成功重置标记时使用配置值。启动从公开 `bank.current_demo_logical_at` 恢复最近成功重置起点。API 负责持久的整体管理回执、停收、排空、应用记忆复位及旧会话失效；它可随后调用 setter 恢复自己持久的逻辑时间。平台不会把银行单边成功冒充整体重置完成，也不清除任务历史。依赖银行 PR #325；本地组合回归为 `test_demo_runtime_clock.py`。

`DeepAgentPlanner` 使用 Deep Agents 处理自然语言，模型必须在 `propose_transfer`、`propose_continuation` 与 `reply_only` 中恰好选择一个。前者按 `capability_name` 提出任意已注册能力的业务候选（v04-platform/10：默认仍为 `transfer.start_transfer`，第二业务模块须显式点名；收款人/金额/账户三字段只对转账能力提取，其他能力留空交原任务澄清），后者只返回受控聊天文本。系统提示词按 `public_catalog()` 动态列举当前能力与清单描述，不再硬编码「仅转账」；规划器会拒绝不在 catalog 里的能力名（注册表查询与授权回调仍是闸门）。`AgentHarness.understand()` 是无业务副作用的公开理解入口；`handle_message()` 对仅回复结果不创建任务，对业务候选继续原流程。兼容入口 `start()` 收到仅回复结果时以 `NO_TRANSFER_INTENT` 安全停止。两条路径都不执行银行动作或形成授权。其他内置工具及通用子 Agent 在此入口关闭；缺失、矛盾或无效的模型结果安全失败。模型和配置版本由调用方以 `ModelSettings` 提供，脚本模型测试不能证明真实提供商行为。

`CapabilityRegistry` 登记清单中的公开能力：`register_transfer` 仍专用于转账（单一 `transfer.start_transfer`），`register_module` 面向第二个业务模块——能力名必须以 `模块名.` 为前缀、不可重复、清单非空（v04-platform/03）。`public_catalog()` 按各能力声明的 `input_schema_ref` 提供给规划入口。`AgentHarness` 需要已建立的用户会话、`ApplicationStore`、`MemoryAdapter`、`AuditJournal`、公开能力工厂和权限判定回调。工厂收到当前可信上下文、任务专属的持久检查点及同一 `RunTrace`，返回实现 `start` / `resume` 的公开入口。

第二模块接入（v04-platform/03）：`TransferProposal.capability_name` 从单一 Literal 放开为任意已注册能力名（注册表查询与授权回调仍是闸门），harness 三处恢复/续跑授权改按任务快照的 `capability_name` 取；`bills_stub.py` 按契约 §5.3 形状登记 `bills.summarize` / `bills.detect_anomalies` / `bills.generate_report`（只读、read_only 重试、无副作用、无确认），桩入口不读银行数据、返回明确的桩响应，真实业务由账单模块（`modules/bills/`）替换工厂实现。L02 的输入/输出与 L03 的输入 schema ref 随账单线契约模型落地后解析；同一清单内重名能力按契约 §6.9「名称唯一」拒绝注册。

`TransferRuntime` 是普通转账的实际组合入口：它把 `BankGateway`、`SecurityGate`、`GatewayTransferTools`、`TransferWorkflow`、持久确认与银行验证记录接到同一任务。创建时必须由可信后端传入公开能力权限、私有工具权限及风险判断回调；本目录不自行决定这些安全规则。中风险的模拟人脸需要额外传入管理员授权回调。聊天文字与 `resume` 指令不能批准资金操作；调用方须通过 `answer_confirmation()` 提交绑定当前动作的结构化确认，通过银行验证接口取得已通过的记录后调用 `bind_verification()`。这两个方法都会检查任务归属，平台恢复时只装入当前操作的记录。

资金提交前，组合入口先持久写入安全允许决定、授权与参数证据以及工具开始事件。银行授权回调再次核对当前图动作、已领取的执行记录和冻结参数；直接调用银行网关不能绕过这道门。图节点起止、安全决定、工具调用、银行观察和恢复事件沿同一追踪编号记录，并关联父子步骤；应用侧银行结果与相应观察事件在同一数据库事务内写入。领取过的操作只按原 `operation_id` 回查，不再次提交。

模型回复与候选以脱敏快照记录。当前 Deep Agents 接缝不暴露最终发给模型的完整请求（系统提示与会话上下文），因此 `model.started` 明确把请求证据标记为缺失，不用用户文本摘要冒充完整提示；模型结果仍记录为脱敏受控输出。含可识别验证码、密码等秘密值的请求在入模和建任务前拒绝；没有秘密值的安全求助可进入理解。`recover_session()` 只接受本人当前会话，将原 `task_id` 和检查点关联到新身份，调用注册能力的公开恢复入口，并记录旧 / 新会话、旧 / 新运行和原 `operation_id`。转账动作准备时先把原编号登记在应用存储；任务摘要缺少结果时，恢复审计从该任务最新的持久操作记录补回编号。未提交动作由安全门重新确认；已有执行记录沿原 `operation_id` 只查询。转换前先写恢复审计；存储转换和能力续跑之间中断时，持久阶段标记允许在同一会话重试。普通同会话 `resume()` 仍使用原入口。`RunTrace` 保留同一 `trace_id`，并在数据库事务内为每次运行分配事件顺序；同一任务的跨进程入口用数据库旁的任务锁串行化，进程退出自动释放，等待超过 60 秒则返回 `TASK_BUSY` 供调用方重试。

本目录测试覆盖真实银行与安全门的低/中风险路径、未经确认的拒绝、资金前审计、银行成功但任务摘要尚未写入时的重启恢复、同一任务的会话转换中断续做，以及两个进程同时发起或恢复同一任务。HTTP 接线在 API 票实现；React / 真实模型联调、真人安全审查和跨端验收仍需完成后才能合入或标记整个 v0.3 交付完成。

从 `backend/` 运行 `python -m pytest -q app/agent_platform/` 验证此目录。

票04的本机运行工厂为 `app.agent_platform.local_demo:create_local_app`，通过既有 API 工厂装配 GLM、受控演示策略与持久存储；启动、配置、虚构风险场景及验证边界见 [LOCAL-DEV.md](LOCAL-DEV.md)。

确认单展示脱敏转出账户、收款人及开户行、金额、手续费、到账方式和后端风险提示。账户及费用事实读取银行公开入口，风险来自同一后端风险回调；中风险验证摘要复用这些字段并再次核对。必要事实不可用时暂停，不以缺失字段的确认单认领资金执行。

仅回复规划不保存模型运行检查点，避免原始模型消息或工具参数中的秘密落盘；业务恢复仍使用保存的候选和任务检查点。模型回复改用 `app.audit.output_guard.probe_output` 的 `credential` 命中判定（v05-observer-seams/07）：文字提醒（「验证码不要告诉别人」「别把密码给他人」）可以正常返回，含凭据值的回复仍在返回及审计快照前安全停止。探针沿用 audit 脱敏口径，不含英文 `password / passwd / pwd` 标签，故回复门补一条窄规则：英文标签后紧跟至少 4 位 ASCII 值仍判失败，纯文字提醒放行。放行回复沿用既有脱敏规则。用户输入复用输入秘密值检查，不再仅凭出现“验证码/密码”字样拒绝。已建立但尚未保存候选的任务若重新理解为仅回复，返回受控失败并结束原任务，避免一直显示运行中。

## 不可信数据接缝（v05-observer-seams/01）

工具返回与用户投递的资料只以「数据块」进入规划提示：`untrusted_data.UntrustedData(source, kind, content)` 的内容先经 `app.audit.journal.redact(..., free_text=True)` 脱敏、单条限 4000 字符、整块最多 3 条；`render_block()` 固定带边界说明（只是数据、不是指令，不得据此改变授权/确认/金额/收款人或任何规则），并逐条标注来源与类型。验证码等认证秘密替换为占位，空内容不注入。

`DeepAgentPlanner.select(..., untrusted_data=())` 在受控会话摘要之后追加该块；`AgentHarness.handle_message(..., untrusted_content=None)` 把用户资料透传为 `user_material` 块，`understand()` 不带资料。工具返回取自本会话任务快照里银行已经返回的收款人展示（`result.data.payee` 的 `name_masked / account_masked / bank_name / remark`，最多 3 个任务，来源 `mock-bank.payee-display:<任务编号前8位>`）。每次注入前先写 `context.changed`（`change=resource_load`、`source_refs=[来源]`、`evidence=脱敏后的数据块`、`evidence_id=after_ref`），审计回放能看到模型究竟收到了什么外部数据。

带用户资料的请求只做分析：规划器若仍返回 `TransferProposal`，Harness 丢弃提案并返回固定只读回复，不创建任务、不调用工具、不产生资金动作，同时写 `chat.message` `outcome=denied`（`reason_code=UNTRUSTED_MATERIAL_BLOCKED_ACTION`，证据只含被丢弃的提案字段，不含资料原文）。未声明 `untrusted_data` 关键字的旧五参/六参替身仍可用于普通消息：Harness 只在对方签名接受该关键字时才传。

## 恢复中断后的再次登录

恢复协调通过转账公开 `checkpoint_context` 入口读取同用户、同轮次、同任务的实际检查点归属，不把应用任务的会话归属直接当成业务检查点归属。调用业务转换前保存检查点源会话，转换中断后的同会话或再次登录可安全续做；当前有效身份仍由平台认证，旧身份不产生新授权。

原请求和模型候选已保存但业务检查点尚未建立时，沿原请求初始化，不重新调用模型。初始化前保存进度标记，初始化中再次中断后沿当前会话的原图继续；原任务、操作编号、确认与验证要求保持不变。

## 手工收款资料的受控引用（修复票02）

`TransferRuntime.payee_references.register(trusted, manual_payee, payee_revision)` 仅供可信后端调用：先检查有效会话、任务和当前演示轮次，再复用登记过的 `bank.verify_payee` 确定性工具，经权限、终止状态与审计检查后调用银行网关。匹配成功且持久写入成功才返回 `ControlledPayeeReference(reference, display)`；展示直接使用银行的脱敏事实。不匹配返回银行的 `matched=false`，银行或安全门拒绝返回错误事实，都不生成引用。上游异常只报告固定错误码，不回显原始资料。

`resolve(trusted, reference, payee_revision)` 只供确定性工具准备银行参数。版本由后端业务流程维护，不能信任模型或前端自报；它与当前任务、用户、轮次共同绑定。解析时仍核对当前有效会话；恢复同任务到新会话后可由可信后端继续读取。引用不是确认或资金授权，银行办理前仍需重新核验、预检查和安全门放行。

原文复用应用库 `transfer_snapshots` 中的受控参数保存，专用 `action_name=transfer.controlled_payee` 区分用途；不新增秘密存储库，不写聊天、审计或普通 `checkpoints/checkpoint_blobs/checkpoint_writes`。只有受控解析接口可读出原文，它不注册为模型工具。重新登记前清理旧资料，因此新资料不匹配或登记故障也不能借旧引用继续。取消或退出手工录入时后继接入方调用 `clear(trusted)`；重新登记、清理与解析复用现有跨进程任务锁。银行核验工具及独立资金动作的受控参数快照仍按现有调用审计和确认/执行规则保留，不由此接口删除。

持久化后工厂重建可解析同归属、同版本引用。演示切换轮次后现有 MemoryAdapter 拒绝旧轮次资料；旧库保留到演示数据目录被显式归档/移除，不在轮次变化时自动删除整库。SQLite保存是现有受控存储边界，不声称新增磁盘加密或自动销毁。资料引用接入转账检查点及F36分别由03、04票完成；02单独通过不能证明旧HTTP录入路径已满足TF-OBS-08。

修复票 `v03-transfer-eval-fixes/07`：装载敏感操作上下文时，服务端从同用户/轮次已经绑定的session验证来源发现候选，银行再核对当前会话的真实VerificationRecord及原任务已passed基础挑战，再绑定到新任务；不取消task绑定。每笔仍需新的动作确认，中风险action记录不能跨动作复用，新登录及过期会话不能授权。重建后验证来源仍可发现。定向4项通过：第一任务验证后取消、重建、新任务新确认后一笔500元；新登录/中风险跨笔仍需验证，跨用户/轮次无候选和会话失效拒绝。原评测HEAD58740f5产品定向复现同会话新任务verification_ids为空失败；真实HTTP验证生命周期组合及真人安全审查仍待。

## 原任务续办候选（bank-e2e-remediation/04）

`ContinueProposal` 只携带原任务编号、版本、补充/修改/查询/取消动作；没有批准、验证或银行执行动作。Harness按本人当前会话、唯一未完成任务、版本、等待状态与允许动作检查；外来资料只分析不续办，恢复前不能修改。旧调用方默认返回卡片引导；API票05显式启用 `allow_continuation` 后，须持久化候选并在派发前再次检查状态。此票不等于HTTP/React续办已接通。输入秘密检测是有限可识别格式，并非所有自然语言秘密的完备识别。

## Demo 当前对话风险接线（bank-e2e-remediation/07）

本地演示写操作现在解析原请求、当前不可变动作参数与真实银行历史，再由安全侧文本兜底叠加到参数绑定的演示事实。后续聊天在理解前登记到当前会话未结束的转账任务，记录失败则不继续理解；模型调用失败不会丢掉已披露的受骗线索。记录只用于限制风险，不授权动作，不改变任务版本；会话恢复不丢弃同一任务的旧风险证据。多项未结束转账时保守影响这些任务，不能用另开聊天规避危险线索。

示例配置明确包含 A1 → 妈妈（银行收款人 A2）300/500/600 元普通场景，以及501/502元中高风险演示；账户、收款人、金额必须完全匹配配置。实际新收款人事实可提高风险，文本危险线索优先停止。未知文字、未配置参数和检测器失败暂停。设备等缺乏真实来源的维度仍明确来自虚构演示配置，不能称为生产风险事实。自定义本机配置须显式增加需要演示的金额，不自动给任意金额低风险。

原长诈骗输入的 MODEL_UNDERSTANDING_FAILED 仍是待真实复验项；本地程序测试不替代票11的真实模型、React及银行联合验收。

## 生日受控编辑与 G3 状态发布接缝（v05-birthday-platform-dependencies/03）

`birthday_edit.py` 是平台侧唯一入口，不注册为模型工具。输入只有可信上下文与后端发布的原 F10 request/interaction/option；身份、目标、参数与版本一律取自原任务，不接受客户端自报 actor/editable/operation/候选 hash。

- **受控编辑（A）**：生日确认/验证卡由 `BirthdayTaskPorts` 在返回交互时追加一个后端发布的受控编辑选项，并把 interaction/option/执行项/原 operation/action_revision/确认版本通过任务 CAS 持久化。`begin_birthday_edit` 的冻结顺序是：任务 CAS 预留 edit_ref、源已发布完整 ref（thread+namespace+id）与唯一候选 ref → 安全 02 受理 → 银行 06 退役旧尝试挑战 → 安全 02 封存（含审计，失败即停）→ Cross 08 只按源 ref 准备隔离候选 → 05 一次封存首份胜者 → 同一任务 CAS 发布胜出 checkpoint、snapshot 完整 published_ref、ModuleResult、新 revision 与完成投影。同参重放返回同一胜者；claim 先胜/未知、任务终止、会话变化、旧卡或异参一律不进编辑；撤离后检查点/CAS 失败时旧动作仍不能写，重试沿同一受理记录补发布。
- **初始与普通状态（B）**：`publish_initial_state` 在首次 Cross 状态写前，以原 task/start 受理关联与接受版本预留无前驱 root 候选（无 edit_ref/source，不伪造前驱）；`publish_normal_state` 以受信调用方（Harness 接线）提供的原 F10 请求或原运行事件关联作为 `conversion`，只校验其形状并把摘要持久化到任务快照（平台没有客户端入口，也不反向核验该关联来自哪个客户端请求），然后绑定上次已封存且已发布的完整 source ref 预留普通候选。两者都由 05 封存首份完整胜者，再由本目录同一次任务 CAS 发布完整 ref/结果/新版本/完成投影。缺已发布源、旧任务缺 ID、thread 已有历史都不能冒充初始化；发布失败不暴露候选；已发布根/普通/编辑状态不可覆盖，后续状态另用隔离 namespace。
- **Harness 接线（同一发布适配器）**：`AgentHarness` 在 `handle_message`/`resume(...)` 里对 `cross.start_task` 的生日（或可能转为生日的澄清）任务调用 `BirthdayTransition`：交给 `CrossEntry` 的 saver 改为「读最后已封存已发布 ref（绝不 latest）+ 内存缓冲写」的适配器，entry 返回后由平台预留候选、05 封存该份真实 Cross 状态、同次严格任务 CAS 发布；默认 namespace 不再落任何 Cross 状态。该适配器只用于上述生日 G3 任务，清晰非生日的 life goal 与旧任务仍走原 latest saver。首个状态若不是可发布的首卡（例如首步执行接缝不可用返回失败结果），适配器**跳过 G3 发布、不报错**，既有失败/待核实结果仍由 Harness 结果 CAS 落盘（不会出现「任务无 result」）。entry 返回后 Harness 重新读取任务再 CAS 结果（entry 内端口会写生日 attempt/编辑选项，旧修订号不再误报 TASK_CHANGED/DEPENDENCY_UNAVAILABLE）。`SUCCEEDED/FAILED/CANCELLED/PARTIALLY_SUCCEEDED` 等已收口任务的 resume 直接返回**已发布历史结果**，不开启新 conversion（Cross 对终态不 `_save`，不能要求新候选）。replay 已发布 conversion 时只重绑本次 `run_id`，不改变已发布结果内容。普通确认/验证卡、verify_wait 与确认后的编辑入口均由真实 Harness 路径覆盖（`test_birthday_harness_publication.py`）。
- **普通 resume 的 conversion 身份（`resume(..., request_id=)` 与退化行为）**：API04 应把 F10 `request.request_id` 传给 `AgentHarness.resume(trusted, response, *, request_id=)`，这是最精确的重试身份。未传 `request_id`（票 04 接线前的现状，`service.py` 只调 `resume(trusted, response)`）时，平台**不依赖每次变化的 run_id**，而用「任务当前等待卡的 interaction_id + 该卡发布时的 task_revision + 回答内容摘要」作为 conversion 身份：同一 F10 回答换 run_id 重试会命中同一 conversion（不会误报 TRANSITION_PENDING；发布失败后的同参重试可恢复），真正不同的回答仍按不同 conversion 拒绝。只有既无 request_id、又无等待卡/空内部 resume 时，才退化为「原运行事件」异常转换并显式记录。**退化边界**：无 request_id 时，已发布后的「迟到回执重放」无法与「新的同文回答」区分，票据级重放仍以 API04 receipt 为准；票 04 接线前该点为已知限制，而非隐藏行为。
- **时序与并发窗口（已接受的设计取舍）**：为避免 entry 内生日端口写任务（attempt/编辑选项）与严格受理版本 CAS 冲突，候选预留发生在 entry 返回之后、封存/发布之前；Cross 的准备只在内存发生，**没有任何持久 Cross 状态先于预留落盘**。因此 entry 内已发生的任务写与银行动作早于候选预留：若在 entry 与预留之间出现**不经任务锁的其他合法写**，预留/发布 CAS 会失败（fail-closed，`TASK_CHANGED`/`PUBLISH_CONFLICT`，不盲取最新版本覆盖），需按原 conversion 重新走一次受控转换；同一进程内 Harness 任务锁可避免该竞争。
- **跨会话恢复（票10）**：`recover_session` 对生日 G3 任务先核对本人精确封存源，缺源、异主体/轮次或其他在途转换在迁移前拒绝。迁移后沿 Cross 公开恢复入口把新状态缓冲、封存并严格 CAS 发布，不写默认 namespace；确认/验证卡还须通过新会话记录校验，否则不发布旧卡。恢复发布或收尾中断可沿原 marker 重试，已封存候选不重跑 Cross；已完成恢复后再来旧恢复请求，仅返回当前任务，不回滚后继输入。当前 Cross 的敏感等待卡重建属单独消费方票，在其交付前 provider 明确拒绝旧会话卡；普通输入已支持。legacy 无 G3 的原恢复保持，旧任务编辑仍不能伪造不可变来源。
- **F10 原请求查询（票10，供 API11 消费）**：`birthday.handoff.find_input_conversion(trusted, request_id)` 是只读查询，返回既有 `PublicationOutcome`（原 `result/task_revision/published_ref/content_digest/kind`）、`"pending"` 或 `None`。只认这个 request 的稳定摘要；不能仅看到 `published_ref` 就接受任意旧请求。API 仍须匹配原请求正文，并把原回执回复与最新活动卡/事件分开；平台不替 API 放宽交互校验。
- **Cross 侧**：编辑（A）仍只实现 `CrossBirthdayHandoff.prepare(trusted, CandidateRequest) -> CrossCandidate`：读精确源 ref、返回完整候选内容，不得自行 `put` 预留 namespace（05 封存是唯一写入方）；票 08 未接线时编辑以 `CROSS_HANDOFF_UNAVAILABLE` 明确 block，可用明示 stand-in 验证平台边界。初始/普通（B）不依赖该 Protocol：Harness 适配器直接封存 Cross 自己写的状态内容。API 04 的 F10 分流（`published_option()` / `is_published_edit_option()` 只读判断）仍属 api 目录。
- 测试：`app/agent_platform/test_birthday_edit_handoff.py` 用真实安全状态、06 真实银行验证与 05 真实 saver 加明示 Cross stand-in，覆盖冻结/下单/核销的确认与验证六种等待态、旧卡/异参/异会话/终止与 needs_attention 拒绝、claim 抢先与 M1 胜序、撤离后/候选封存后/回执丢失断点、严格受理版本 CAS、writes 归属、root 首次发布、普通后继、普通缺源拒绝冒充根与发布失败不暴露候选；`test_birthday_harness_publication.py` 用真实 Harness（模型提案用受控 planner 替身，其余真实）覆盖新任务 root 发布→普通输入发布→编辑入口可见、verify_wait/编辑卡不因修订号陈旧失败、发布失败后同参重试、首卡失败跳过 G3 但保留结果、澄清→转生日成功/失败分支、无 request_id 的同回答重试与不同回答拒绝、replay 重绑 run_id、部分成功收口后刷新返回历史结果、G3 跨会话恢复显式拒绝且不迁移会话/marker、legacy 任务恢复对照。

## 撤离后的同参新尝试接缝（v05-birthday-platform-dependencies/09）

票 08 如实报出：03 撤离旧尝试后，若编辑后的计划对同一 action 生成完全相同参数（冻结卡必然同参；order/capture 卡的对应项未改时也同参），`birthday_runtime._action` 会复用已撤离的 operation，安全门按 02 正确返回 `ACTION_RETIRED`，「编辑后继续办理」在真实装配下被阻止；冻结已提交时该前置 BLOCK 还会把 cross 流程带进收口/释放路径。

本目录的接缝：`BirthdayTaskPorts._sealed_retirement` 只读 ticket 02 的 `security_retirements`（`SQLiteSecurityState.get_retirement`，复用本文件既有 `_security_context` 的同绑定）；`_action` 在「参数相同但该 attempt 的撤离已 `sealed`」时创建新 attempt/新 operation——旧 attempt 进入 `birthday_attempts` 保留可回查、`action_revision` 继续单调，安全门对新 attempt 正常评估为确认/验证，而不是 `BLOCK`。读取只吞 `ACCESS_DENIED`（他人记录，不能作为本 attempt 的判断）并注释；其它安全状态错误上抛，不静默降级成「可复用」。**不另存任务快照标记**：03 的编辑发布使用严格受理版本 CAS，seal 之后再写一次任务会破坏该 CAS（并把竞争写掩盖掉）；02 的 `sealed` 记录本身就是「已证明撤离」的持久事实，且能覆盖「已封存、新 input 尚未发布」的窗口。`pending_proof`/`conflict` 不触发新尝试：旧动作仍按 02 的原规则处置（可领取、只能沿原号观察），不在未证明撤离时换号。`handoff.cross is None` 时编辑仍按原文档以 `CROSS_HANDOFF_UNAVAILABLE` 诚实拒绝、不伪造新 input（行为测试见下）。

- 测试：`app/agent_platform/test_birthday_edit_continuation.py` 在真实组合（真实 Harness/安全门/银行/存储/G3 发布 + 票 08 `register_cross` 装配时经 `install_cross_handoff` 挂载的真实 adapter；测试只断言 `handoff.cross` 非空、不自行赋值）上覆盖冻结卡、order 卡、capture 卡三种「编辑后按原方案继续」：同参得到新 operation、走到真实确认/验证、旧 operation 仍 `ACTION_RETIRED`、旧 attempt 历史可查、任务不被收口、无资金释放/重复扣款；同一编辑重复点击仍单结果。`test_birthday_edit_handoff.py::test_an_unmounted_cross_handoff_refuses_instead_of_improvising` 固定未挂载 Cross 时 `CROSS_HANDOFF_UNAVAILABLE` 的诚实拒绝（不发布候选、sealed 撤离仍挡旧动作）。
