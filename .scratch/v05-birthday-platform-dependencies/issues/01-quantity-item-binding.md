# 01：真实数量、稳定执行项与原参数确认装配

Ticket ID: v05-birthday-platform-dependencies/01
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [平台提供条件及最小规格](../spec.md)
Type: 开发（本轮只规划，不实施）
Owner: Erwin（v0.5阶段统一负责）
Directory: `backend/app/agent_platform/`
Status: in_progress — 2026-10-26 本人「按交接开始」后由授权执行对话领取并开工；只在本目录实施。
Planning assignee: Codex，01a1718a-26a3-7523-a0bf-2591d8e83618；2026-10-25。
Implementation assignee: Erwin 授权执行对话（本对话，AI 代理）；accepted at 2026-10-26。
领取与顺序见[生日系列执行记录](../../v05-control/birthday-series-2026-10-26.md)。
Blocked by: 中控明确授权实施；与[v05-cross-business/08：生日商品数量与未执行部分调整](../../v05-cross-business/issues/08-birthday-quantity-and-unexecuted-revision.md)确认内部项/attempt格式；与[PR #296：订单来源门](https://github.com/DrErwin/hackerthon-bank-agent/pull/296)同一birthday_runtime文件按先合原PR再开本票的顺序处理（这是文件合入顺序，不冒称数量依赖其新能力）。
Core scenarios: P01/P02/P07/P08/P11；[P01—P11验证框架](../spec.md#6-testing-decisions只设计未运行)对应Cross08 Q01—Q10及XL-B01—B07。

本轮补充：按[候选G3快照](../spec.md#g3最小内部快照候选待cross08逐项核对不是公共新模型)与Cross08核对，尚未达成接口确认；G2两选项均未定，不能因此实施等待态修改。

## What to build

平台接收Cross08的服务端项快照，真正下对应数量并展示同一组数量/单价/小计/时间；保留原项与原操作历史，新同款项不复用旧订单或旧付款。
本票不实施Cross菜单、编辑业务、安全撤离或API入口，不新增公共字段和银行规则。

## Acceptance criteria

- [ ] quantity透传到CreateOrderInput；行小计与可信原服务单价/数量一致；送达时间与确认及银行回执一致。
- [ ] 旧代码已显式quantity=1，不凭字段存在判升级；后台旧绑定、每商品一项及原操作/参数唯一对应可核验时兼容旧显式1/省略1。quantity>1或后台已有新item/operation绑定却缺身份时不降级旧键；协议来源/唯一映射不明blocked，旧已办/未知沿保存原号，不猜测重建或重发。
- [ ] 确认和验证摘要展示数量、原单价、行小计、时间、商品/商户、账户；冻结保留限定释放条款；配送仅掩码。
- [ ] Cross稳定执行项与product_id分开；动作键/查项/_enriched/原参数回查共同使用稳定项和attempt，未变项不因plan_revision变化重建。
- [ ] 已付花与新同款花的item/attempt/order/capture身份不同；原失败/成功/未知记录不被同商品键覆盖；action_revision基于保留的完整历史单调。
- [ ] 同一未撤离attempt的同参重放/未知查询保留原操作；合法撤离后的新attempt不能复活旧操作，即使参数碰巧相同。
- [ ] 核销展示绑定已创建订单与其原创建参数，不拿新报价改旧单；不影响PR296订单来源门、既有199/268路径及原号恢复。
- [ ] 旧任务不能唯一映射执行项时不猜测或覆盖，保留原事实；局部无法修改如实记限制，不当整条要求完成。
- [ ] 复用operation_id作attempt身份已获Cross727045d §7认可，不新增第二UUID；具体接口仍待核对。check后所有分支（含非冻结ALLOW直交）均须在execute前持久捕获原号/item/参数绑定；新协议execute显式回传，requery始终原号，不按“当前同商品”重挑；冻结ALLOW仍按原规则拒绝。
- [ ] 本目录保留原动作不可变参数；完整确认/必要验证授权版本由安全02提供后联合核对实际可回读，不在01跨目录仿造历史存储。数量接线可单独验证，编辑历史边界未就绪仍blocked；旧可变ID/版本不能代替历史，秘密/配送原文不进普通快照。
- [ ] 与Cross明确check回交后如何捕获原operation/参数版本/确认版本；execute及grant/bind只消费捕获绑定，不能从新计划的当前商品/freeze键重挑。发布前的pending不能被普通resume读作已发布，具体由03/05及Cross08交付。

## Verification / downstream

实施后使用公开ports和真实隔离银行验证两件398元、变价/时间、同款替代只付新项一次及恢复，平台只在本目录写测试。
不等待293即可自验该装配；真实个人预算另循cross06原依赖。Cross08消费本票，等待态修改仍依赖本组02/03/04。
本轮只有静态规划与文档检查，无测试/模型/CI运行；不改Cross08/06或原PR。
