# 02：尚未提交动作的原子撤离守卫

Ticket ID: v05-birthday-platform-dependencies/02
Package: [v05-cross-linkage/packages/02-security：安全边界与专项核验](../../v05-cross-linkage/packages/02-security.md)
Spec: [平台提供条件及最小规格](../spec.md)
Type: 开发（本轮只规划，不实施）
Owner: Erwin（v0.5阶段统一负责）
Directory: `backend/app/security/`
Status: planned / blocked — 本轮无编码授权，不是ready-for-agent。
Planning assignee: Codex，01a1718a-26a3-7523-a0bf-2591d8e83618；2026-10-25。
Implementation assignee / accepted at: 未领取。
Blocked by: 中控明确授权实施；Erwin本人按本阶段代行安全职责确认规格G2，包含旧动作拒绝、claim并发及恢复语义；AI设计审查不代替该决定。
Core scenarios: P03/P04/P05/P06/P08；[P01—P08验证框架](../spec.md#6-testing-decisions只设计未运行)对应Cross08 Q01—Q10及XL-B01—B07。

## What to build

提供当前生日动作的窄后台接缝：与执行claim在同一持久事务中决定“旧attempt已安全撤离”或“已经领取，须观察原操作”。
保留原任务、历史确认/验证和原失败事实，不靠cancel/伪造过期或清空安全终止换取编辑。
不是重做已合security01/04：它们约束执行与顺序确认，没有交付本次非终止式原子撤离。

## Minimum input / output（拟议，待本人安全确认）

输入仅来自可信后台：context、原operation/action_revision/参数/确认版本、原编辑request关联。
输出语义为带原绑定/幂等关联的持久撤离记录，或须原号观察，或拒绝/依赖不可用；不是ALLOW、不是新采用授权。
须能按可信task及原request只读找回同一记录，以覆盖撤离落库后平台记录尚未写入的断点；不接受客户端自报operation或授权标记。

## Acceptance criteria

- [ ] 无claim检查和持久撤离不可分割；抢先claim则不签“未提交”结论；跨进程也保证此边界。
- [ ] 撤离后所有旧gate/claim/迟到验证路径不能再提交原动作；旧attempt不得重新激活。
- [ ] 原request同参恢复原记录；异参/越权/过期会话/终止任务拒绝；必要持久化/审计失败不发可编辑事实。
- [ ] processing/completed/unknown claim都不直接当无提交，completed也不等于银行成功；由原号准确事实决定后续。
- [ ] 原记录不冒改cancelled/expired，不清空TASK_TERMINATED；不新增公开任务/安全决定枚举。
- [ ] 待冻结验证前已授pending_freeze授权按原绑定处理失效（可复用现有pending_freeze→invalid，须G2确认），历史保留、不挪给新freeze_operation；后续停止不把确证未提交当未知冻结。已有真实冻结active收尾不作废，不追加冻结/金额；事实矛盾拒绝。
- [ ] 动作级验证不跨新attempt，session级复用沿原规则；不改风险政策、声明权限或#160。
- [ ] 安全私有持久状态由本目录实现；若确实需要storage/audit/contract新能力，交具体缺口再拆，不在本票跨目录补。

## Verification / downstream

实施后以真实安全状态/执行器验证claim和撤离两种胜序、批准但未claim、迟到验证、重开/持久故障、终止与外来身份。
银行未知/已失败只读观察保持原号。平台03消费本票；本票通过不等于API已能编辑，也不代替本人安全接受。
本轮未写或运行测试、模型、CI。
