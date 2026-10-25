# 02：尚未提交动作的原子撤离守卫

Ticket ID: v05-birthday-platform-dependencies/02
Package: [v05-cross-linkage/packages/02-security：安全边界与专项核验](../../v05-cross-linkage/packages/02-security.md)
Spec: [平台提供条件及最小规格](../spec.md)
Type: 开发（本轮只规划，不实施）
Owner: Erwin（v0.5阶段统一负责）
Directory: `backend/app/security/`
Status: claimed / blocked — 2026-10-26 已由授权执行对话领取；前置为 01/05 交付后的目录顺序及 G2-B 跨库权威胜序核对，未开始编码。
Implementation assignee: Erwin 授权执行对话（本对话，AI 代理）；accepted at 2026-10-26。
领取与顺序见[生日系列执行记录](../../v05-control/birthday-series-2026-10-26.md)。
Blocked by: 中控明确授权实施；Erwin本人按本阶段代行安全职责确认[两选项及G2-A/B/C条件](../decision.md)，包括旧动作拒绝、挑战对后续任务的作用、准备/授权/claim竞争和审计恢复；G2-B收窄建议不是既定范围，AI设计审查不代替决定。
Core scenarios: P03/P04/P05/P06/P08/P09/P10/P11；[P01—P11验证框架](../spec.md#6-testing-decisions只设计未运行)对应Cross08 Q01—Q10及XL-B01—B07。

## 实施设计（2026-10-26 本对话补充，按 [G2-B 胜序](../verification-authority.md)）

1. **应用库新表 `security_retirements`**（本目录，只加表）：`retirement_id PK`、`user_id/demo_round_id/task_id/operation_id/action_revision`、`state`（`pending_proof`|`sealed`|`conflict`）、`original_binding_json`（原参数绑定摘要、确认 id/版本、编辑 request 关联）、`bank_evidence_json`（06 返回的 retirement_id/挑战 id/时间）、`audit_ref`、`created_at/sealed_at`、`UNIQUE(user,demo_round_id,task,operation,action_revision)`。
2. **两段式**（避免把银行调用塞进应用库事务）：
   - `begin_retirement(context, action, now)`：单一应用库事务内核对归属/任务未终止；`get_execution` 已有 claim（processing/completed/unknown）→ 抛拒绝（只能原号观察）；记录不存在则写 `pending_proof`；同参重放返回原记录，异参冲突。
   - `seal_retirement(context, retirement_id, bank_evidence, now)`：事务内重新确认无 claim、受理记录仍是本人任务与原绑定；写 `sealed` + `bank_evidence` + 审计引用；同参幂等。若 claim 在此期间出现 → 记 `conflict` 并拒绝。
3. **claim 拒绝**：`claim_execution` 在既有事务内查 `security_retirements`，只要该 (task, operation_id, action_revision) 存在 `pending_proof` 或 `sealed` → 抛 `SecurityStateError("ACTION_RETIRED")`，旧动作永远不能再领取。撤销/终态路径不变。
4. **确认历史保留**：`create_confirmation` 的 UPSERT 覆盖前，把当时的**完整脱敏 ConfirmationRecord**（含 display_fields、参数 ref、版本）写入新表 `security_confirmation_history`（同事务）；`get_confirmation_history(confirmation_id, version)` 只读回读。不改旧 `cancelled/expired` 含义。
5. **pending_freeze 授权退役**：仅当 `sealed` 且原绑定一致时，把该 operation 的 `pending_freeze` 授权按原绑定置 `invalid`，原因写 `RETIRED_UNSUBMITTED`（不写成 FREEZE_FAILED）；真实 `active` 授权不动；并列 `birthday_release` 指针回写时按原 attempt + CAS 校验（`update_task` 的 revision 检查已有，补 attempt 比较）。
6. **审计**：seal 的同一应用库事务内用 `AuditJournal.append_in_transaction` 写既有事件（`security.retired_unsubmitted` 证据引用），失败整笔回滚；撤离已持久但审计不齐→保持 `pending_proof` 不放行。
7. **平台回调（03 提供）**：`begin` → 调银行 06 `retire_action_challenges` → `seal`；银行拒绝（先失败/先过期/已通过）直接返回不可编辑原因，不写 `sealed`。
8. 不新增公开 `SecurityDecision`/任务状态枚举；本目录测试用隔离库+真实 `AuditJournal` 路径。

以上为设计，实施前需 06 交付；`pending_freeze` 具体列名与 `birthday_release` 指针校验以实际源码为准，不改契约。

## What to build

提供当前生日动作的窄后台接缝：与执行claim在同一持久事务中决定“旧attempt已安全撤离”或“已经领取，须观察原操作”。
保留原任务、历史确认/验证和原失败事实，不靠cancel/伪造过期或清空安全终止换取编辑。
不是重做已合security01/04：它们约束执行与顺序确认，没有交付本次非终止式原子撤离。

## Minimum input / output（拟议，待本人安全确认）

输入仅来自可信后台：context、原operation/action_revision/参数/确认版本、原编辑request关联。
输出语义为带原绑定/幂等关联的持久撤离记录，或须原号观察，或拒绝/依赖不可用；不是ALLOW、不是新采用授权。
须能按可信task及原request只读找回同一记录，以覆盖撤离落库后平台记录尚未写入的断点；不接受客户端自报operation或授权标记。
还须绑定原item/operation、完整确认版本/参数、已知挑战/准备资格、限定授权及原request摘要和必要审计引用；安全来源S-G2完整缺口见[规格补齐表](../spec.md#42-security真正需要提供的能力g2)。这里没有新公开裁决枚举或通用授权框架。

## Acceptance criteria

- [ ] 无claim检查和持久撤离不可分割；抢先claim则不签“未提交”结论；跨进程也保证此边界。
- [ ] 撤离后所有旧gate/claim/迟到验证路径不能再提交原动作；旧attempt不得重新激活。
- [ ] 原request同参恢复原记录；异参/越权/过期会话/终止任务拒绝；必要持久化/审计失败不发可编辑事实。
- [ ] processing/completed/unknown claim都不直接当无提交，completed也不等于银行成功；由原号准确事实决定后续。
- [ ] 原记录不冒改cancelled/expired，不清空TASK_TERMINATED；不新增公开任务/安全决定枚举。
- [ ] 待冻结验证前已授pending_freeze授权按原绑定处理失效（可复用现有pending_freeze→invalid，须G2确认），历史保留、不挪给新freeze_operation；后续停止不把确证未提交当未知冻结。已有真实冻结active收尾不作废，不追加冻结/金额；事实矛盾拒绝。
- [ ] 动作级验证不跨新attempt，session级复用沿原规则；不改风险政策、声明权限或#160。
- [ ] 安全私有持久状态由本目录实现；若确实需要storage/audit/contract新能力，交具体缺口再拆，不在本票跨目录补。
- [ ] 迟到批准、gate重发、grant/store/bind及平台指针回写都服从原attempt撤离事实；撤离胜后不再生旧pending，grant先胜则原子处理其未生效记录。保留原因，不挪用/作废真实active授权。
- [ ] 发码准备资格在实际preparer前持久取得，并与撤离排序；准备先胜、结果未知或已发未登记不能用列表为空放编辑。选首批收窄也必须实现此边界。
- [ ] G2-B未决定前保留全部原失败/超时规则；若选完整，只有本人批准的精确安全撤离挑战例外才可在安全及银行验证两侧一致应用，撤离前已发生失败/到期/终止、其他挑战不例外。无法证明先后保持blocked，不在security跨目录改银行服务。
- [ ] 旧确认完整脱敏版本、不可变原参数与必要验证/授权快照在覆盖前留存并确能回读，不能只存ID/版本。秘密/配送原文不进普通证据。
- [ ] 必要审计优先append_in_transaction与撤离同连接提交；失败回滚且不签编辑依据。已持久撤离但证据不齐继续封锁，补齐同一原事实必要记录后才恢复，不伪造取消/ALLOW/完成事件。
- [ ] invalid既有收尾含义为FREEZE_FAILED；新的未提交撤离原因须经G2-C确认并正确表达“未提交、无冻结”，不能把它当真实银行失败。

## Verification / downstream

实施后以真实安全状态/执行器验证claim、准备资格、迟到grant/绑定和撤离的胜序，批准但未claim、挑战失败/到期先后、完整历史、必要审计中断与重开、终止及外来身份。P09—P11同属本票框架，未编写或运行。
银行未知/已失败只读观察保持原号。平台03消费本票；本票通过不等于API已能编辑，也不代替本人安全接受。
本轮未写或运行测试、模型、CI。
