# B26 银行重置接缝

Status: implemented_pending_review — 银行服务与定向验证完成，待主代理独立两轴审查及合入；不代表整体 B26。
Owner: Erwin（v0.5）；执行：bank_reset_completion 子代理。
Accepted by: Erwin，通过 2026-10-27“除比赛资料外的任务完成”及主代理明确分派。
Accepted at: 2026-10-27
Package: [v05-cross-linkage/packages/01-platform-bank](../v05-cross-linkage/packages/01-platform-bank.md)

## 目标

演示管理端确认重置、停止新业务并排空在途后，银行可按同一个管理操作恢复固定种子，进入新轮次。响应丢失或失败后先查原号，不能换号反复清空。银行只负责自己的数据库，不声称应用、记忆及历史审计已重置。

## 已定边界

- 依据公共契约 §6.8、§7.2/7.3 和银行字段附件 B26；服务接缝由主代理确认。
- 内部 `reset_demo(admin, management_operation_id, source_round_id, target_round_id, initial_logical_at)` 和只读管理结果查询，不注册为 Agent 能力。
- 沿用受控 `AdminContext`。原轮次、新轮次、起点时间和操作者绑定原管理操作；同号异参或异操作者拒绝。
- 银行操作仍 processing 时返回 running，不清空；更高层所有业务排空由平台负责。
- 结果、当前银行轮次和逻辑起点持久化，银行清理与成功结果同一事务；旧验证、操作、冻结、订单及签约变化清除，账户/流水/签约恢复固定种子，故障归默认。
- 历史管理结果保留；业务历史审计在独立审计存储，由平台保留。不得访问共享演示库。

## 核心场景

- R01：受控重置后银行事实与同一逻辑起点的新种子一致，重启仍能查同号结果和新轮次。
- R02：在途转账时原号保持 running，完成后同号续做。
- R03：成功原号重放不清除新轮次后来发生的业务；参数/操作者冲突无副作用。
- R04：拒绝普通身份、错轮次及非法时间/相同新旧轮次。
- R05：种子写入中失败整体回滚，原号绑定保留，修复依赖后仍按原号续做。
- R06：旧挑战失效，旧轮次资金写入拒绝，新轮次合法业务仍可完成。
- R07（2026-10-27 消费前置）：API先持久停收并排空自身执行，再通过公开网关等待接口核对所有已提交的排队/执行中资金写；调用已超时但future未完仍在途。等待不关闭网关，结束后可继续新轮业务。启动可只读取得最近成功重置的持久逻辑起点；未成功为None，running/failed及旧成功重放不能伪造或覆盖它。

## 交付与依赖

首票只改 services 及本组过程材料。F30—F32 的二次确认、停收/排空、应用及记忆重置由主代理另票实现，银行交付不等于 B26 整体或页面验收完成。

本机已读取 to-spec、to-tickets、implement 及 code-review 文件；前三项设置 disable-model-invocation，本轮按明确授权与既有契约形成最小票据，不谎称调用了 slash 工具。独立两轴审查由主代理统一安排。

2026-10-27：首票已由 [PR #322](https://github.com/DrErwin/hackerthon-bank-agent/pull/322) 合入main；整体API消费发现仅查bank_operations.processing不能覆盖生日写、释放及尚未入表的future。[票02](issues/02-gateway-drain-and-clock.md)补公开排空与成功时钟读取；仍不替API做停收、mutation_lock、active_message_jobs或应用/记忆重置。
