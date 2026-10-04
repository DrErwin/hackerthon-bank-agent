# 03实跑发现的跨目录问题

Date: 2026-10-04
Source ticket: v03-transfer-evals/03：转账自动化评测套件与Live GLM Runner（本地实施票）
Status: Open；仅记录缺口，未授权本票跨目录修复或合并

证据：[离线全量](evidence/2026-10-04/offline-full.md)、[真实GLM全量](evidence/2026-10-04/live-full.md)。这些是实现验证证据，不是04的专业业务签署。各运行原始结构化结果以同名json.gz保存，解压方法见[实现证据](automation-evidence.md)。真实GLM非确定性结果不能用离线通过替代。

| 问题 | 实际观察 | 期望与影响 | 涉及目录及负责人 |
|---|---|---|---|
| TF-OBS-08：专用卡号进入普通检查点 | F36合法手动核验A2后，完整卡号出现在`checkpoint_blobs`、`checkpoint_writes`；普通聊天/日志检查同时执行。仅记录命中表名，凭据原文不展示 | 普通检查点不应留完整专用录入号码，受控参数快照例外；需要核对流程状态是否携带完整PayeeInput | `backend/app/modules/transfer/` Erwin（v0.3临时），`backend/app/agent_platform/` Erwin；Ringo专业秘密边界审查 |
| TF-VFY-03/04/08/09/10/11/21/24：验证终止状态 | 基础第三次错误或中风险错误/超时/人脸失败后，任务实际`needs_attention`，矩阵要求`failed`；资金未新增提交 | 用户应得到确定的本次验证失败，旧挑战不能复活；不能以90%成功率放宽此规则 | `backend/app/modules/transfer/` Erwin（v0.3临时）；安全规则归Ringo |
| TF-VFY-06：基础码到期不能重发 | 到期拒绝后，resend非200，新5分钟挑战及成功转账预期未满足 | 低风险基础验证应可重新获取；保持第三次错误终止与中风险不延期规则 | `backend/app/security/` Ringo / v0.3 Erwin；依证据确定唯一修复目录 |
| TF-VFY-19：同会话基础验证没有跨任务复用 | 第一任务真实基础验证后取消；同一cookie新建第二任务，确认后再次创建挑战，旧verification未绑定，资金0 | 有效会话基础记录可用于新任务，但每个新动作仍必须新确认 | `backend/app/agent_platform/` Erwin；安全范围由Ringo审查 |
| TF-VFY-12 / TF-OBS-10 / TF-OBS-15：技术故障后状态 | 验证服务或执行前审计写入故障后，实际`waiting_approval`；预期`needs_attention`。审计故障实际触发且没有调用资金接口；模拟异常秘密未进入报告 | 明确呈现依赖故障，不能把技术异常计为用户答错，不能虚报完成 | `backend/app/modules/transfer/` Erwin、`backend/app/api/` Erwin；审计/安全实现需按目录另票 |
| TF-QRY-08：回查途中会话失效后的任务状态 | 在首个真实原操作回查中使会话过期；后续没有无权银行回查，旧HTTP查询401；服务端任务快照实际仍`waiting_approval`而不是`needs_attention` | 原task/operation保留且不重提，用户重新登录后应看到待核实状态，不应停在旧验证阶段 | `backend/app/api/` / `agent_platform/` Erwin |
| TF-PAY-15：手动账户不匹配后的状态 | F36返回400 PAYEE_MISMATCH，实际任务保持`waiting_input`，矩阵要求`failed`；资金0 | 需要业务负责人确认状态设计或按既有矩阵修复，03不擅改预期 | `backend/app/api/` / `modules/transfer/` Erwin |
| GLM理解与缺项：TF-INP-08/09/13、TF-BNK-01/02、TF-RCV-01/21 | 第二轮真实GLM对部分输入返回ReplyOnly或把模糊金额视为具体金额，未得到要求的任务/追问；离线正确追问不能代表真实理解通过 | 真实缺项追问指标6/9，未达到100%；标准成功任务21/21不能覆盖这些硬失败 | `backend/app/agent_platform/` Erwin；业务歧义由Erwin确认 |

第二轮TF-INP-14、TF-CNF-15、TF-OBS-12的实际模型调用没有返回可用proposal（安全记录error_type=ValueError），记GLM Blocked；未凭异常类宣称网络故障、供应商故障或某个确定根因。第一轮对应结果见保留报告，不覆盖重写。

TF-VFY-16缺Ringo真实来源的绕过攻击语料与可信检测入口，Blocked；其余样本的受控风险事实只证明可信裁决后的业务响应。专业安全列NotRun，不能代签。

上述缺口不是新实施票，也不是已修复的GitHub Issue。本票没有替其他目录改代码；后续由相应负责人确认，再按单目录拆票。04/原12/v0.3继续未验收。
