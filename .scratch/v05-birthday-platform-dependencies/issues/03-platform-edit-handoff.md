# 03：原任务受控撤离并回到未执行编辑输入

Ticket ID: v05-birthday-platform-dependencies/03
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [平台提供条件及最小规格](../spec.md)
Type: 开发（本轮只规划，不实施）
Owner: Erwin（v0.5阶段统一负责）
Directory: `backend/app/agent_platform/`
Status: implemented — 2026-10-26 实施完成、提交 `8e93485` 已推分支，两轴独立审查进行中；Harness/API 接线与真实 Cross 消费留 04/08。
Implementation assignee: Erwin 授权执行对话（本对话，AI 代理）；accepted at 2026-10-26。
领取与顺序见[生日系列执行记录](../../v05-control/birthday-series-2026-10-26.md)。
Blocked by: [本组01：真实数量与稳定项装配](01-quantity-item-binding.md)、[本组02：安全原子撤离](02-security-retire-unsubmitted.md)、[本组05：候选检查点一次封存](05-immutable-edit-checkpoint.md)及本人所选G2完整条件；与[v05-cross-business/08：生日商品数量与未执行部分调整](../../v05-cross-business/issues/08-birthday-quantity-and-unexecuted-revision.md)核对[候选G3快照/接口](../spec.md#g3最小内部快照候选待cross08逐项核对不是公共新模型)；中控授权。[PR #298](https://github.com/DrErwin/hackerthon-bank-agent/pull/298)已合主线6ce7fb0，保留其预算来源边界，不在本轮整理原PR。

新增真实提供前置：[本组05：候选检查点一次封存](05-immutable-edit-checkpoint.md)。现有精确读/CAS可复用，但不可变候选和原子发布策略尚未交付；[G3对账](../g3-reconciliation.md)为待核对方案，不是已实现保证。
Core scenarios: P02—P17；[P01—P17验证框架](../spec.md#6-testing-decisions只设计未运行)对应Cross08 Q01—Q10及XL-B01—B07。

## What to build

专用后台入口从原任务重读目标和绑定，调用安全02；只有撤离成功或原号已核实的无订单/无在途明确失败，才能由Cross08进入原任务新input。
平台保存撤离/编辑关联与恢复事实，不在普通resume响应中接受模型自报“已安全退出”。不实施Cross的方案编辑业务。

同一G3保存接缝还须为初始/普通状态建立不可变已发布源，不限专用编辑：新生日及先澄清后转生日的起点，在首次Cross状态写前以原task/start受理CAS预留根候选；初始无edit_ref/source，不伪造编辑或前驱。普通输入/事实/异常后继复用原请求或原运行事件及接受版本的持久关联、绑定上次已封存已发布source，再预留新候选；05封存首份完整胜者后，本目录同次task CAS发布ref/结果/版本/完成投影。具体条件见[三类来源及发布](../g3-reconciliation.md#没有编辑请求的初始与普通状态)，不建立通用调度框架或新实施票。

## Acceptance criteria

- [ ] 输入只含TrustedContext及原F10 request/interaction/option；身份/目标/参数/版本来自服务端原任务。
- [ ] 等待冻结/下单/核销的confirmation与verification均纳入；安全input节点无需伪造撤离，不能用局部通过充全部。
- [ ] claim抢先或结果未知时沿原operation观察，不换号、不进可能在途项编辑，not_found/查询失败不当未提交证明。
- [ ] 活动原任务中，下单明确失败且银行证实无订单/无在途可重新提替代；父任务已终态则不借银行失败复活。
- [ ] 已建未付与已付订单不改写；其他未成单部分仍可编辑，原未付金额继续计待支付；后续付款须有效新确认。
- [ ] Cross08返回的新input保持原task_id、新交互/任务版本；原订单/失败/成功/旧attempt/预算来源快照均保留。
- [ ] 安全撤离后平台记录/检查点/结果CAS失败仍禁止旧动作；能按原编辑request从安全记录恢复，不伪造新授权或把当前新计划作原结果。
- [ ] 原任务CAS及恢复严格比较原绑定，不用盲取最新revision越过竞争；cancel/终止/会话变化不重启购买。
- [ ] 未知冻结/付款/释放先核实，原账户/上限/冻结/个人预算约束不被编辑重置。
- [ ] 待冻结验证被合法撤离后，区分原pending_freeze未生效授权与真实已冻结；新input后停止如实零冻结，不错误进入永久未知，也不撤销已有active收尾。
- [ ] 必要审计失败停止新动作；没有安全G2或CrossG3时明确blocked，不能仅隐藏旧卡。
- [ ] 分开接收“已安全撤离且审计齐备”和“原号核实银行明确失败、无订单/无在途”的依据。后者保留已有claim，不要求不可能的无claim证明，不删除失败以凑撤离条件。
- [ ] 必要审计不齐不向Cross发布可编辑事实；恢复仍核对当前身份/会话/版本/阶段，不能仅凭存在记录。needs_attention或_task_terminated=false不等于可编辑；partially_succeeded终态也不可复活。
- [ ] 旧grant/绑定迟到写birthday_release指针须核对原attempt与CAS；撤离未提交、真实银行失败及active冻结分别展示，不能把invalid直接投影成真实FREEZE_FAILED。
- [ ] grant_release/bind_freeze使用Cross pending中捕获的原operation/确认版本或等效冻结上下文，不在迟到回调中重新按“当前freeze键”挑动作；拟议兼容签名等待G3确认。
- [ ] G3候选专用后台入口和Cross进入编辑方法不注册模型工具，不接受普通resume自报edit_context；新旧单件/显式operation协议及两条依据须Cross确认后才实施。
- [ ] 已受理编辑的精确原request在原操作失败核实后可受控恢复，不以当前interaction=None自动拒死或产生新授权；无原受理事实时由Cross08沿原查询保存失败后发布新普通input，旧确认不能作编辑捷径。
- [ ] 若本人选首批收窄，只接入准备资格尚未开始且获安全02证明的确认态；验证码/动作验证等待保持blocked，原完整修改验收要求不删、不写已完成。
- [ ] 撤离前先CAS固定同edit_ref、精确源已发布ref及唯一候选ref；同参竞争沿同一受理记录，异参冲突，版本变化不盲取最新值。
- [ ] Cross只按源ref准备隔离候选，05封存胜者；同次task CAS发布胜出checkpoint_id、snapshot完整ref、ModuleResult、新revision及完成投影。不能先写最新检查点再把任务CAS当隔离。
- [ ] G3普通start/resume/异常分支同样使用已发布ref；handoff中只读原结果/待核对，不推进旧动作。取消按真实原操作收尾；取消/终态/新会话胜出则不得发布候选。
- [ ] 精确读取仍须不可变内容保障；旧task.checkpoint_id、namespace和原状态不能唯一核验时编辑blocked，不回latest、不新补hash伪证或重编号。
- [ ] 初始根的原task/start关联和接受版本在首次状态准备前持久预留；核实从未发布Cross状态才允许无前驱。无edit_ref/source不妨碍05封存真实初始根，但不得把普通缺源、旧任务缺ID当首次初始化；先场景澄清后转生日也具备同等起点。
- [ ] 普通输入、事实回读及异常转换都预留原转换关联/新候选、绑定不可变已发布source；05选完整胜者，03同次CAS发布完整ref/对应结果/新版本/完成投影。普通和异常记账不沿latest、恢复不拿新run_id/最新revision重造原转换，不因持久失败重做银行写。
- [ ] 根封存或首次发布失败不暴露候选；无旧published_ref只用现有初始化失败/待核对表现，按原根关联恢复，不从latest补源。同任务未发布转换未结束时，不推进另一转换越过原受理；取消/终态/会话变化或其他合法写入胜出则旧CAS拒绝。已发布根及普通后继继续不可覆盖。
- [ ] 旧显式quantity=1或省略1只在后台旧绑定、每商品一项及原操作/参数唯一对应可核验时兼容；字段存在不判新协议。quantity>1或后台新绑定缺身份不得降级，来源/唯一映射不明blocked；数量兼容不豁免上面的源保护。

## Verification / downstream

实施后真实Harness与安全02/隔离银行检查等待确认/验证、两种并发胜序和各持久断点；Cross未接线时可用明示stand-in测试平台边界。
API04与Cross08消费；真实联合验收复用原E2E03。G1未收口前不宣称公开入口可用。
新增P16/P17只交初始根/普通后继、发布失败/重试/并发的验收设计，P15旧单件边界保持。本轮不编码、不跑测试/模型/CI；真实E2E由Erwin后续亲自安排，材料独立双轴回交后即停。

## Delivery record（2026-10-26 本对话实施）

- 实现：新增 `backend/app/agent_platform/birthday_edit.py`（平台唯一受控编辑与 G3 发布入口，未注册模型工具，
  只收 TrustedContext + 后端发布的原 F10 request/interaction/option）；改 `birthday_runtime.py`（确认/验证卡含
  verify_wait 返回时追加后端发布的编辑选项并持久化发布事实）；`agent_platform/README.md` 登记接缝/边界/后续责任；
  新增 `test_birthday_edit_handoff.py`（45 例，真实安全状态 + 06 真实银行验证 + 05 真实 saver + 明示 Cross stand-in）。
  分支 `codex/v05-birthday-edit-handoff`，提交 `8e93485`（rebase 后）；PR 待两轴审查闭合后提交。
- 核心编排：`begin_birthday_edit` → 任务 CAS 预留 `edit_ref`/源已发布完整 ref/唯一候选 ref →
  安全 02 `begin_retirement` → 银行 06 `retire_action_challenges` → 安全 02 `seal_retirement`（审计失败即停）→
  Cross `CrossBirthdayHandoff.prepare` 准备隔离候选 → 05 `seal_candidate(kind=edit)` 首胜 →
  **同一次任务 CAS** 发布 checkpoint_id/完整 published_ref/ModuleResult/新 revision/完成投影。
  初始 root 与普通后继走同一发布边界（`publish_initial_state`/`publish_normal_state`），缺源/历史不得冒充根。
- 定向验证：`app/agent_platform` **354 passed / 13 skipped**（含 45 例）、`app/api/test_app.py` **85 passed**；
  本对话在 rebase 后复跑 `app/agent_platform`（结果见回交）。未跑全量后端/真实模型/CI。
- **作者如实列出的接线缺口（本票未跨目录实现）**：
  1. Harness/API 调用接线未做：`publish_initial_state` 需在 `entry.start` 前调用、`publish_normal_state` 在每次普通转换调用、
     API04 调 `begin_birthday_edit`；真实 Cross 由票 08 实现 `CrossBirthdayHandoff`，故 P16/P17 只用 stand-in 验平台边界。
  2. **既有集成风险（作者观察到，待规格轴核实）**：`AgentHarness._resume`/`handle_message` 在 entry 返回后用旧
     `task.revision` 做 CAS，而生日 ports 在 entry 内已 CAS 任务快照——即 Cross 生日流经 Harness 的普通 resume 可能本就未接通；
     本票未改 harness，待审查判定是否属本票范围。
  3. 第二依据 `verified_failed_no_order` 与「原操作失败核实后恢复」归 Cross08/API04；旧任务编辑按 `SOURCE_UNAVAILABLE` 明确 blocked。
- 两轴独立子代理审查（AI，非本人/Ringo 签核）：**进行中**，必须项闭合后再提交 PR。
