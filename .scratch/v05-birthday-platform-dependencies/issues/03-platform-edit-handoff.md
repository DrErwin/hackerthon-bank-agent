# 03：原任务受控撤离并回到未执行编辑输入

Ticket ID: v05-birthday-platform-dependencies/03
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [平台提供条件及最小规格](../spec.md)
Type: 开发（本轮只规划，不实施）
Owner: Erwin（v0.5阶段统一负责）
Directory: `backend/app/agent_platform/`
Status: planned / blocked — 本轮无编码授权，不是ready-for-agent。
Planning assignee: Codex，01a1718a-26a3-7523-a0bf-2591d8e83618；2026-10-25。
Implementation assignee / accepted at: 未领取。
Blocked by: [本组01：真实数量与稳定项装配](01-quantity-item-binding.md)、[本组02：安全原子撤离](02-security-retire-unsubmitted.md)；与[v05-cross-business/08：生日商品数量与未执行部分调整](../../v05-cross-business/issues/08-birthday-quantity-and-unexecuted-revision.md)的受控进入编辑接缝G3达成一致；中控授权；与[PR #298：预算来源平台接缝](https://github.com/DrErwin/hackerthon-bank-agent/pull/298)同Harness改动按指定合入顺序，不修改该原PR。
Core scenarios: P02/P03/P04/P05/P06/P07/P08；[P01—P08验证框架](../spec.md#6-testing-decisions只设计未运行)对应Cross08 Q01—Q10及XL-B01—B07。

## What to build

专用后台入口从原任务重读目标和绑定，调用安全02；只有撤离成功或原号已核实的无订单/无在途明确失败，才能由Cross08进入原任务新input。
平台保存撤离/编辑关联与恢复事实，不在普通resume响应中接受模型自报“已安全退出”。不实施Cross的方案编辑业务。

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

## Verification / downstream

实施后真实Harness与安全02/隔离银行检查等待确认/验证、两种并发胜序和各持久断点；Cross未接线时可用明示stand-in测试平台边界。
API04与Cross08消费；真实联合验收复用原E2E03。G1未收口前不宣称公开入口可用。
本轮不编码、不跑测试/模型/CI。
