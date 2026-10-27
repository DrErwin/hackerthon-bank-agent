# 平台14：明确规划失败的受控消息结果

Status: approved_pending_335
Owner: Erwin（v0.5）
Accepted by: 中控明确授权，2026-10-27
Directory: `backend/app/agent_platform/`
Package: [底座与模拟银行](../v05-cross-linkage/packages/01-platform-bank.md)

## 结果与边界

保留DeepAgentPlanner严格outcome门、原模型/prompt及失败审计；仅将明确PlanningError在建任务前转换成既有MODEL_PROPOSAL_FAILED失败ModuleResult。由API已有error_completed分支发布固定、日常话的reason，说明可重新表述与查看原卡；没有资金任务、资金安全或已拦截保证。普通不可确定中断继续遵守原恢复规则。

固定reason：`这次没能处理好您的消息，请换个说法。如果是在继续之前的办理，请先查看原任务卡片。`

原失败分类仍为失败；不复用自由回复，不补造业务提案/参数，不重跑同一原请求，不改API、安全、账本或B/C报告。平台13的335必须先合入，修改基于其最新main，不并改旧harness工作树。

## 验证

- P14-01：三条原B的0-tool回复只读精确回放；严格Planner仍PlanningError(result_count,0)，HTTP受控失败固定reason，无新任务/银行提交/资金gate。
- P14-02：原request重复、重新装配后仍回放原完成消息，不重新调用模型或产生重复助手消息。
- P14-03：原先待确认任务/确认/operation不被当前失败消息替换或推进；风险对话记录仍按原安全规则，不抹去新披露。
- P14-04：合法ReplyOnly与正常proposal/continuation、缺/多outcome、解析失败和真实不可确定中断分别保持原语义。必要局部与一次完整平台回归，原13skip不当通过。

前期诊断与未修复红例见[独立记录](../v05-model-protocol-diagnosis/README.md)。脚本模型、原回复回放与真实批分层记录；交PR后如需真实验证，最多另跑原三失败+一个正常对照一次新小批，不覆盖原B/C。
