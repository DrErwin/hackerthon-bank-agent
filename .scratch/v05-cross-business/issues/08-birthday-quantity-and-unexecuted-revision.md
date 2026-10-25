# 08：生日商品数量与未执行部分调整

Ticket ID: v05-cross-business/08

Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)

Spec: [生日数量与未执行方案缺口及最小规格](../birthday-quantity-gap.md)

Type: 开发（本轮只核查、规划和拆票）

Owner: Erwin（v0.5阶段统一负责）

Directory: `backend/app/modules/cross/`

Status: claimed / blocked — 2026-10-26 已由授权执行对话领取；前置为平台 01 接口稳定与 02/03 交付，未开始编码；适用个人预算路径仍等待 06。

Implementation assignee: Erwin 授权执行对话（本对话，AI 代理）；accepted at 2026-10-26。
领取与顺序见[生日系列执行记录](../../v05-control/birthday-series-2026-10-26.md)。

Core scenarios: XL-B01/B02/B03/B04/B05/B06/B07，回归XL-X02/X05/X08；
见[共享场景](../../v05-cross-linkage/spec.md)、[本票Q01—Q10框架](../birthday-quantity-gap.md#6-testing-decisions仅框架未写或运行)。

## What to build

用户能在服务真实候选中调整数量、移除或替换尚未成单且无在途的部分（含银行明确失败、已证实无订单后的新替代），看到重新核算的方案，再采用和逐动作确认。
已建订单/已付消费与原操作不改写；未知先核实，停止只收尾，个人预算约束不因修改被绕过。

## Blocked by / Start when

- 中控明确授权本票实施并确认平台交付边界；本轮只有规划授权。
- 正式候选 [v05-birthday-platform-dependencies/01：真实数量、稳定执行项与原参数确认装配](../../v05-birthday-platform-dependencies/issues/01-quantity-item-binding.md)：
  数量/价格/时间与动作键、同款新旧项及attempt历史绑定。候选仍planned/blocked，不等于已有能力。
- 候选 [v05-birthday-platform-dependencies/02：尚未提交动作的原子撤离守卫](../../v05-birthday-platform-dependencies/issues/02-security-retire-unsubmitted.md)：
  真实持久撤离、claim/授权/挑战竞争及必要审计；G2本人未决定，安全建议不能自动替代原要求。
- 候选 [v05-birthday-platform-dependencies/03：原任务受控撤离并回到未执行编辑输入](../../v05-birthday-platform-dependencies/issues/03-platform-edit-handoff.md)：
  消费撤离或已claim明确失败/无订单/无在途两类事实；源检查点精确绑定、待发布隔离及任务CAS同次发布引用/结果，普通resume不读孤立新状态；G3待双方确认。
- 候选 [v05-birthday-platform-dependencies/04：F10当前生日待办的受控编辑分流](../../v05-birthday-platform-dependencies/issues/04-api-edit-entry.md)：
  G1状态语义按契约§8确认后接入；不借普通F10/转账draft/取消伪造编辑，不在Cross跨目录补代码。
- 候选 [v05-birthday-platform-dependencies/05：生日编辑候选检查点的一次封存](../../v05-birthday-platform-dependencies/issues/05-immutable-edit-checkpoint.md)：
  固定提供稿d9f8b96新增storage单目录窄能力，03已在该稿依赖05。精确ref不等于内容不可变；05首份持久胜者及原put/put_writes防覆盖、03原子发布、08普通/异常恢复只读已发布源共同就绪才可消费。
  新初始/普通状态的不可变源绑定仍待03/05明确，见[G3最终消费意见§8](../birthday-g3-interface-review.md#8-对d9f8b96封存提供稿的最终消费意见设计仍blocked)。本地基线尚未收录05，以上候选链接以d9f8b96 Git树验证，不当作已交付。
- [v05-cross-business/06：个人预算采用、版本与冻结前占用](06-adopted-budget-integration.md)
  是适用个人预算资金路径前置；其[平台来源01](../../v05-budget-adoption-origin/issues/01-platform-origin.md)
  与[API来源02](../../v05-budget-adoption-origin/issues/02-api-f10-origin.md)按原顺序交付。
  数量候选/无个人预算约束的局部设计可独立，不扩大或提前实施06。
- [v05-cross-business/05：生日受控配送及事实](05-birthday-delivery-and-structured-facts.md)及#288/#289已合入，
  作为保留基线，不重做。07仍属原PR#297，本票不混入其分支。
- 拟采用既有F10与已有银行quantity。若发现现行输入/状态不足，先交具体契约差异、兼容方案及受影响方，
  不自行新增字段或放宽确认。完整确认等待态修改未验证前不得宣称整票完成。

## Acceptance criteria

- [ ] 原真实商品可调整正整数数量、移除/替换未提交项；显示数量、单价、小计、总计、时间与账户。
- [ ] 只用当前服务端选项/受控提问，旧交互/请求重放/越权不能更改新方案；空篮子/非法量零新资金写入。
- [ ] 修改产生新计划与交互；采用前重新核算，冻结后留在原账户/上限/冻结边界，不自动追加或重置预算。
- [ ] 新价按单价×数量核算；服务价格/送达变化重新采用并确认，旧确认/验证不能执行改后参数。
- [ ] 待确认/验证修改先证明原动作未提交并安全退出旧待办；并发、恢复与未知沿原编号核实，不能将隐藏按钮当作失效。
- [ ] 已建未付/已付订单与成功消费保留原事实；无订单/无在途的明确失败可重新提出替代，原失败记录保留，不撤单退款。
- [ ] 商品ID与稳定执行项身份分离；同款新替代项不复用历史成功订单/付款，原项及新项各自重放沿原号，累计消费不重置。
- [ ] 适用个人预算路径经06真实F10采用/刷新/占用核验；商品方案采用不替代个人预算采用或资金授权。
- [ ] 与平台真实下单及确认展示对齐quantity/金额/时间，最终银行回执一致，受控配送和原停止收尾回归不退化。
- [ ] 局部回归、平台装配与原E2E按层留证；依赖不足保持blocked；独立规范/规格审查必须项清零。

## Verification / downstream

实施后按Q01—Q10，从公开CrossEntry/F10及真实模拟银行检验外部行为；测试保持本目录，平台边界由平台自验。
页面承接原[v05-cross-frontend/02](../../v05-cross-frontend/issues/02-birthday-ui.md)，
整条路径承接原[v05-cross-e2e/03](../../v05-cross-e2e/issues/03-birthday-e2e.md)，不新建重复收口票。
原型可标明未实现能力，本轮没有生产页面编码授权。

## Delivery record

- 本轮：只读事实核查、规格/最小测试框架和本票；未实施、未跑测试/模型/CI/全量、未新建代码PR。
- 设计审查：见[本轮记录](../birthday-quantity-design-review.md)，AI审查不等于PM或真人安全签核。
- 不修改共享跟踪或交付包总状态。编号08经main01—06与已发布07共同核对，07不复用。

## Comments

2026-10-25（G3消费方协同）：以main `2a070b9` 的平台01—04候选及本地安全评议`bce306d`核对，
补[内部接口建议](../birthday-g3-interface-review.md)。明确未claim撤离与已claim明确失败的两类持久证据、
稳定项/attempt、历史快照、审计齐备、检查点/CAS恢复及原ports兼容。G1/G2本人尚未决定，G3待提供方收口；
检查点转换必须有同edit_ref持久单胜者及已发布引用边界，不能仅先写最新检查点再CAS任务。
确认/验证编辑完整要求保留，安全稿的首批收窄建议不能自动变成整票范围或完成事实。仍只规划，不实施08/06。
