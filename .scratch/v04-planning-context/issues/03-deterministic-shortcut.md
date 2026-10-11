# v04-planning-context/03：确定性等待应答短路（可选）

Ticket ID: v04-planning-context/03
Package: PM 自拆（不开交付包）；Source issue [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)
Spec: [v04-planning-context 规格链接](../spec.md)
Core scenarios: 同 01（SEC-C-001 固定话术类变体）；本票为 [01 基线](01-planner-context.md)的可选增强
Verification: 等待确认/验证期的固定话术（嗯/确认/催促类）零模型调用即得到与待办一致的确定性回复；运行时间线可区分确定性应答与模型应答；离线缝断言同 01
Owner: Erwin
Directory: backend/app/agent_platform/
Status: optional（采纳判据见下）
Blocked by: [v04-planning-context/02：真实运行复验与移交](02-live-retest-handoff.md) 的复验结论
Source issue: [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)

## What to build

等待确认/验证期的固定话术走确定性分支不经模型，直接给出与当前待办一致的应答——端到端效果：这类应答不再消耗模型调用、不受模型波动影响。

## 采纳判据（YAGNI 门）

- 仅当 [01 基线](01-planner-context.md)经 [02 复验](02-live-retest-handoff.md)后**仍有余留问题**（固定话术类应答不一致或规划失败）才采纳；
- 基线复验全绿则本票关闭为「不需要」，不挡 10-15 截止。

## 实现要点

- 分流发生在 harness 层进入模型之前；确定性回复同样只描述状态，不构成批准、不产生资金动作。
- 若确定性回复的对外形态与现行模型回复口径差异明显，先判断是否触及公共契约/API 契约，触及先走契约变更流程。
- 运行时间线标注应答来源（确定性/模型），便于审查与走查。

## Acceptance criteria

- [ ] 固定话术类应答零模型调用、与待办一致、零资金副作用
- [ ] 时间线可区分应答来源；pytest 全绿
- [ ] PR 合入、CI 通过；若触发契约判断，先走变更流程再实现
