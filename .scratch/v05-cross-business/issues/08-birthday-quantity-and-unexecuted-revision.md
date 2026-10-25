# 08：生日商品数量与未执行部分调整

Ticket ID: v05-cross-business/08

Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)

Spec: [生日数量与未执行方案缺口及最小规格](../birthday-quantity-gap.md)

Type: 开发（本轮只核查、规划和拆票）

Owner: Erwin（v0.5阶段统一负责）

Directory: `backend/app/modules/cross/`

Status: planned / blocked — 未授权实施；平台数量透传、确认展示与安全退回编辑接缝待中控另派；适用个人预算路径仍等待06。

Planning assignee: Erwin授权执行对话 01a17183-271b-7663-9517-f31a994de51d

Planning accepted at: 2026-10-25

Implementation assignee / accepted at: 未领取。

Core scenarios: XL-B01/B02/B03/B04/B05/B06/B07，回归XL-X02/X05/X08；
见[共享场景](../../v05-cross-linkage/spec.md)、[本票Q01—Q10框架](../birthday-quantity-gap.md#6-testing-decisions仅框架未写或运行)。

## What to build

用户能在服务真实候选中调整数量、移除或替换尚未成单且无在途的部分（含银行明确失败、已证实无订单后的新替代），看到重新核算的方案，再采用和逐动作确认。
已建订单/已付消费与原操作不改写；未知先核实，停止只收尾，个人预算约束不因修改被绕过。

## Blocked by / Start when

- 中控明确授权本票实施并确认平台交付边界；本轮只有规划授权。
- 平台由Erwin另派**单目录**任务，尚无新票号：真实CreateOrderInput不再写死quantity=1；
  确认展示及参数绑定含实际数量/价格/时间；确认/验证待办安全退出为新输入的接缝经验证。
  动作键能区分同一商品的历史已办项与新替代项，并保留原attempt/operation供回查，不只按product_id覆盖。
  不将已完成平台09冒称覆盖此缺口，也不在Cross跨目录补代码。
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
