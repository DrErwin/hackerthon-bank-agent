# 01：真实数量、稳定执行项与原参数确认装配

Ticket ID: v05-birthday-platform-dependencies/01
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [平台提供条件及最小规格](../spec.md)
Type: 开发（本轮只规划，不实施）
Owner: Erwin（v0.5阶段统一负责）
Directory: `backend/app/agent_platform/`
Status: planned / blocked — 本轮无编码授权，不是ready-for-agent。
Planning assignee: Codex，01a1718a-26a3-7523-a0bf-2591d8e83618；2026-10-25。
Implementation assignee / accepted at: 未领取。
Blocked by: 中控明确授权实施；与[v05-cross-business/08：生日商品数量与未执行部分调整](../../v05-cross-business/issues/08-birthday-quantity-and-unexecuted-revision.md)确认内部项/attempt格式；与[PR #296：订单来源门](https://github.com/DrErwin/hackerthon-bank-agent/pull/296)同一birthday_runtime文件按先合原PR再开本票的顺序处理（这是文件合入顺序，不冒称数量依赖其新能力）。
Core scenarios: P01/P02/P07/P08；[P01—P08验证框架](../spec.md#6-testing-decisions只设计未运行)对应Cross08 Q01—Q10及XL-B01—B07。

## What to build

平台接收Cross08的服务端项快照，真正下对应数量并展示同一组数量/单价/小计/时间；保留原项与原操作历史，新同款项不复用旧订单或旧付款。
本票不实施Cross菜单、编辑业务、安全撤离或API入口，不新增公共字段和银行规则。

## Acceptance criteria

- [ ] quantity透传到CreateOrderInput；行小计与可信原服务单价/数量一致；送达时间与确认及银行回执一致。
- [ ] 原未升级单件调用的省略quantity=1/每商品一项语义兼容；新协议显式quantity及稳定项缺失不默默回落，旧在途参数与映射不猜测改写。
- [ ] 确认和验证摘要展示数量、原单价、行小计、时间、商品/商户、账户；冻结保留限定释放条款；配送仅掩码。
- [ ] Cross稳定执行项与product_id分开；动作键/查项/_enriched/原参数回查共同使用稳定项和attempt，未变项不因plan_revision变化重建。
- [ ] 已付花与新同款花的item/attempt/order/capture身份不同；原失败/成功/未知记录不被同商品键覆盖；action_revision基于保留的完整历史单调。
- [ ] 同一未撤离attempt的同参重放/未知查询保留原操作；合法撤离后的新attempt不能复活旧操作，即使参数碰巧相同。
- [ ] 核销展示绑定已创建订单与其原创建参数，不拿新报价改旧单；不影响PR296订单来源门、既有199/268路径及原号恢复。
- [ ] 旧任务不能唯一映射执行项时不猜测或覆盖，保留原事实；局部无法修改如实记限制，不当整条要求完成。

## Verification / downstream

实施后使用公开ports和真实隔离银行验证两件398元、变价/时间、同款替代只付新项一次及恢复，平台只在本目录写测试。
不等待293即可自验该装配；真实个人预算另循cross06原依赖。Cross08消费本票，等待态修改仍依赖本组02/03/04。
本轮只有静态规划与文档检查，无测试/模型/CI运行；不改Cross08/06或原PR。
