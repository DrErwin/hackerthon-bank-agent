# 普通转账评测缺口：已确认拆分与正式票索引

Status: resolved — 本轮01—09程序范围已合入并验证；10保持paused，版本验收另待\
Date: 2026-10-04\
Spec: [v0.3修复规格](spec.md)

## 确认记录

用户在简要说明三项决定后回复“按你建议”。本轮确认范围：

1. 户名不匹配按正式F36保留原任务waiting_input、明确PAYEE_MISMATCH，允许纠正；修订PAY15评测，不新增强制结束规则。
2. 非法金额有明确输入拒绝事实、无可执行确认且银行零副作用时，允许不创建任务；保留专用字段分支。明确转账只缺金额仍须建立待输入任务。
3. 十张单目录票、02→03→04真实能力依赖，以及现有真实HTTP/平台入口、受控故障和银行账本的验收方式。

批准仅用于规划定稿和本地Markdown tracker发布；未授权本轮实施、提交/合并、联系队员、飞书同步或版本收口。没有代填新票领取或Ringo安全批准。

随后用户明确要求“暂缓10，先只看程序问题”。当前仅保留01评测判据修正和02—09程序修复；10标为paused，LLM理解、模型输出调整与ValueError诊断暂缓。十张票的编号和历史批准记录保留，当前范围以本次收窄为准。

## 正式票

每票一个分支/PR、一个归属目录，正式字段、交付物和验收条件以链接文件为准。Owner为Erwin；安全与转账按v0.3临时安排，长期归属不变。

| Ticket ID与标题 | Directory | Status | Blocked by |
|---|---|---|---|
| [v03-transfer-eval-fixes/01：核准户名不匹配与非法金额评测判据](issues/01-eval-expectations.md) | evals/transfer/ | ready-for-agent | None |
| [v03-transfer-eval-fixes/02：提供任务绑定的受控收款资料引用](issues/02-controlled-payee-reference.md) | backend/app/agent_platform/ | ready-for-agent | None |
| [v03-transfer-eval-fixes/03：转账检查点仅保留资料引用](issues/03-checkpoint-payee-reference.md) | backend/app/modules/transfer/ | blocked | 02 |
| [v03-transfer-eval-fixes/04：F36通过受控引用继续原任务](issues/04-api-payee-reference.md) | backend/app/api/ | blocked | 02、03 |
| [v03-transfer-eval-fixes/05：基础验证码过期后可重发](issues/05-basic-code-expiry-resend.md) | backend/app/services/ | ready-for-agent | None |
| [v03-transfer-eval-fixes/06：安全门区分验证终止与技术故障](issues/06-verification-terminal-facts.md) | backend/app/security/ | ready-for-agent | None |
| [v03-transfer-eval-fixes/07：同会话基础验证跨任务复用](issues/07-session-verification-reuse.md) | backend/app/agent_platform/ | ready-for-agent | None |
| [v03-transfer-eval-fixes/08：验证HTTP技术故障发布待核实状态](issues/08-verification-error-task-state.md) | backend/app/api/ | ready-for-agent | None |
| [v03-transfer-eval-fixes/09：流程故障与回查失效保存真实任务快照](issues/09-durable-task-fault-snapshot.md) | backend/app/agent_platform/ | ready-for-agent | None |
| [v03-transfer-eval-fixes/10：缺项转账建立任务并诊断模型无有效输出](issues/10-model-transfer-missing-input.md) | backend/app/agent_platform/ | paused（用户暂缓） | None |

## 测试节奏与PR

用户确认保持一票一个PR，同时采用[规格中的测试与PR安排](spec.md)：

- 每票只做针对性复现、修复验证与受影响的必要回归，不逐票跑153样本或全部回归。
- 02/03/04卡号保护、05/06/07/08验证生命周期、08/09故障恢复分别在能力齐备后集中联调；同基线重叠场景引用已有证据。
- 01—09完成后，在实际集成基线上做一次完整离线评测和必要整体回归；只有后续改动、失败或影响范围需要时再扩大复跑。
- 保留独立PR和现有代码CI，不改实施依赖，不新增最终验收票；10及真实LLM批量评测继续暂缓，剩余模型失败/安全缺证据仍如实记录。

这次只更新规划文档，未启动实现、测试、CI或PR。

## 执行次序与验收边界

02→03→04是唯一新增能力链。05重发、06终止分类、07同会话复用、08接口故障、09流程快照各自没有新增票的代码前置；组合回归不等于相互阻塞。01使用来源评测能力，执行前核对实际代码基线，不把原票03尚未全绿误作不能修评测的循环前置。01—09不依赖10，无需等待模型问题处理。

建议实施授权后优先隐私链02→03→04，再05/06/07和08/09；01按已确认口径修订评测。10不进入当前执行次序。无代码依赖不等于授权同时开多个PR，仍遵守仓库并行上限。ready-for-agent表示规格和拆分已确认、可领取，当前未领取或实现；03/04因真实能力未提供保持blocked。

真实失败、ValueError根因未知、安全语料缺证据仍按规格分别记录。保留153样本及旧报告，不挑最好一次结果，不因规划批准认定产品问题已修。

继续复用[v03-transfer-evals/03：转账自动化评测套件与Live GLM Runner](../v03-transfer-evals/issues/03-eval-automation-suite.md)、[v03-transfer-evals/04：转账业务评测实跑、报告生成与版本收口](../v03-transfer-evals/issues/04-eval-acceptance-closeout.md)和[v03-erwin-vertical-backend/12：v0.3联合验收与版本收口](../v03-erwin-vertical-backend/issues/12-v03-acceptance-closeout.md)。不新建最终验收票、不修改这些票状态。所有修复的专业审查、实际回归及联合验收仍待后续授权执行。


## 2026-10-04 实施进展

02已交付PR52，针对性41项通过；真人审批与合入待处理。01、03—09待继续，03/04的合入能力依赖未闭合；10保持paused。当前两未合PR（51、52）达到仓库上限，已请求数量豁免；现有表格是规划时状态，当前状态以各票及[执行记录](execution.md)为准。

2026-10-04最新执行：用户已授权01—09实施、必要验证和独立PR，并放宽本次开放PR数和04第三层Draft；09复现后原目录修复，额外补票提案撤回。各PR及事实以[执行记录](execution.md)为准。上文仅规划未授权说明为初始历史，不代表当前授权；未授权合并/真人安全豁免/Feishu/GLM/下一阶段。


## 2026-10-04 最新合入状态

用户本轮明确豁免Ringo审批并授权合并；PR51及修复01—09已合入，程序主线复验完成。审批豁免不是Ringo已审查；10继续暂停，专业安全评测与v0.3验收未提升。上文未授权/待合入为历史；最新逐票提交及验证见[执行记录](execution.md)。
