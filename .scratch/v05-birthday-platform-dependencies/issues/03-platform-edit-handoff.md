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
Blocked by: [本组01：真实数量与稳定项装配](01-quantity-item-binding.md)、[本组02：安全原子撤离](02-security-retire-unsubmitted.md)及本人所选G2完整条件；与[v05-cross-business/08：生日商品数量与未执行部分调整](../../v05-cross-business/issues/08-birthday-quantity-and-unexecuted-revision.md)核对[候选G3快照/接口](../spec.md#g3最小内部快照候选待cross08逐项核对不是公共新模型)；中控授权。[PR #298](https://github.com/DrErwin/hackerthon-bank-agent/pull/298)已合主线6ce7fb0，保留其预算来源边界，不在本轮整理原PR。
Core scenarios: P02/P03/P04/P05/P06/P07/P08/P09/P10/P11；[P01—P11验证框架](../spec.md#6-testing-decisions只设计未运行)对应Cross08 Q01—Q10及XL-B01—B07。

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
- [ ] 分开接收“已安全撤离且审计齐备”和“原号核实银行明确失败、无订单/无在途”的依据。后者保留已有claim，不要求不可能的无claim证明，不删除失败以凑撤离条件。
- [ ] 必要审计不齐不向Cross发布可编辑事实；恢复仍核对当前身份/会话/版本/阶段，不能仅凭存在记录。needs_attention或_task_terminated=false不等于可编辑；partially_succeeded终态也不可复活。
- [ ] 旧grant/绑定迟到写birthday_release指针须核对原attempt与CAS；撤离未提交、真实银行失败及active冻结分别展示，不能把invalid直接投影成真实FREEZE_FAILED。
- [ ] grant_release/bind_freeze使用Cross pending中捕获的原operation/确认版本或等效冻结上下文，不在迟到回调中重新按“当前freeze键”挑动作；拟议兼容签名等待G3确认。
- [ ] G3候选专用后台入口和Cross进入编辑方法不注册模型工具，不接受普通resume自报edit_context；新旧单件/显式operation协议及两条依据须Cross确认后才实施。
- [ ] 已受理编辑的精确原request在原操作失败核实后可受控恢复，不以当前interaction=None自动拒死或产生新授权；无原受理事实时由Cross08沿原查询保存失败后发布新普通input，旧确认不能作编辑捷径。
- [ ] 若本人选首批收窄，只接入准备资格尚未开始且获安全02证明的确认态；验证码/动作验证等待保持blocked，原完整修改验收要求不删、不写已完成。

## Verification / downstream

实施后真实Harness与安全02/隔离银行检查等待确认/验证、两种并发胜序和各持久断点；Cross未接线时可用明示stand-in测试平台边界。
API04与Cross08消费；真实联合验收复用原E2E03。G1未收口前不宣称公开入口可用。
本轮不编码、不跑测试/模型/CI。
