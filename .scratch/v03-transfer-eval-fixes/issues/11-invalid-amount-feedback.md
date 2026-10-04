# 11 — 非法金额保留明确拒绝原因

Ticket ID: v03-transfer-eval-fixes/11\
Package: [transfer-agent-framework/packages/01-vertical-backend](../../transfer-agent-framework/packages/01-vertical-backend.md)\
Spec: [修复规格](../spec.md)；[诊断及规划](../online-diagnosis-20261005.md)\
Owner: Erwin\
Directory: backend/app/agent_platform/\
Status: resolved — 用户授权AI代审，代码CI通过并合入主线，专业安全验收另待\
Blocked by: None\
Source issue: [Issue #71](https://github.com/DrErwin/hackerthon-bank-agent/issues/71)

交付：非法金额保留明确拒绝原因。复用真实HTTP/平台/隔离银行验证，一个目录、一分支、一PR。不恢复模型10，不改银行规则、不自动重试或下一阶段。

- [x] 重现BNK01正确proposal=0被校验拒绝后丢失金额提示。
- [x] 保留确定性校验；零/负金额得到明确金额拒绝或待输入，合法金额正常，不自动默认/绝对值/舍入。
- [x] 真实HTTP/SSE可观察金额原因；无可执行确认、银行无提交。优先复用现有通道，不修改公共契约；如发现缺口，另报单目录依赖。
- [x] 在本目录建立真实边界回归，保留原在线失败证据；不以prompt替代拒绝保证。

## Comments

- 2026-10-05：用户授权诊断、问题记录与修复规划；本票是后续最小修复范围，未获实施、prompt修改、合并授权。纯规划只核对内容/链接/编号/空白，不运行CI。

- 2026-10-05：用户明确批准上一轮建议的11/12实施；按票执行并独立验证/提交PR，未授权恢复10或合并。

- 2026-10-05：独立交付[PR #74](https://github.com/DrErwin/hackerthon-bank-agent/pull/74)，代码HEAD `401a281ec4f13f6d4e9719661c12817fae14bb09`。Standards与Spec AI复审各0剩余发现；不代替Ringo真人安全审查。原10仍paused，原01—09保持resolved，未合并本PR。

## 验证证据

4项原拒绝Harness/HTTP回归先红后绿；平台与API137项回归通过。审计补充后，相关文件48项通过，两个审计证据读取测试字段更正后最后3项拒绝/审计故障回归通过；HTTP/SSE事件持久化回归亦通过。拒绝先记既有chat.message/denied及固定INVALID_AMOUNT，不创建任务，审计写入失败也停止在银行之前。

两个修复目录组合回放原五项输出：BNK01/INP09 Passed，PAY11/INP03/INP08 Failed；全部原输出回放无提交/出流。限定真实GLM各一次：BNK01 Passed（真实proposal=0），INP09 Blocked/MODEL_PROPOSAL_AMBIGUOUS，无银行副作用，未跑到绿。该在线验证在审计补充前，补充后以审计/HTTP回归和再次组合回放验证；没有153全量或React页面验收声明。证据在本机忽略目录.mnemon/online-diagnosis-20261005/implementation-{replay,live}.json。涉及资金输入/审计须Ringo审查；此前01—09豁免不适用于本票。

- 最终代码HEAD的[Repository checks通过](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37225409981)。PR #74仍OPEN；CI绿不表示真人批准、合并或版本验收。

## 2026-10-05 用户授权AI代审与合并，票10恢复

用户明确要求AI代替Ringo审查并合并PR #73/#74；随后新对话完成票10，Prompt保持简洁统一，测试与审查通过后可以合并。此授权是本次AI代审/合并授权，不记作Ringo本人审查或专业安全验收。

| 实施票 | 合并PR | 合并提交 | 最终代码CI |
|---|---|---|---|
| v03-transfer-eval-fixes/11 | [#74](https://github.com/DrErwin/hackerthon-bank-agent/pull/74) | `2c7ecafd2a94a4ebcd80c651c704f49ca0d98599` | [通过](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37226355691) |
| v03-transfer-eval-fixes/12 | [#73](https://github.com/DrErwin/hackerthon-bank-agent/pull/73) | `ba77dbbf30c01e0244be58c9153807638cb43a6e` | [通过](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37226561639) |

两轴AI与安全代审无剩余发现；PR #73已重新基于合入#74的主线。合并组合23项评测判据通过，主线权限/拒绝/审计6项与最终评测冒烟8项通过。Issue #71/#72按已合入交付关闭；模型Issue #68/#69/#70继续开放。

11/12标为resolved。10由paused恢复ready-for-agent，由新对话领取实施与测试/审查/合并；[票10交接](../ticket10-handoff-20261005.md)规定以业务意图、字段确定性、单一结果三条统一原则组织Prompt，具体用例放测试。不得选择首个/末个候选兜底或把普通确认当授权。用户无需再细化技术规划。

真实GLM模型遗留失败与专业TF-VFY-16缺材料依然存在；这些合并不表示模型票10完成或v0.3验收通过。原153在线报告保留，未同步飞书、未进入下一阶段。纯文档进度按主线独立发布，仅内容/链接/编号/空白检查。
