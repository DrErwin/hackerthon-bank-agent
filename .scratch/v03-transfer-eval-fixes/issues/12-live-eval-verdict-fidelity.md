# 12 — 在线判据与前置交互失败保真

Ticket ID: v03-transfer-eval-fixes/12\
Package: [transfer-agent-framework/packages/03-v03-evaluation](../../transfer-agent-framework/packages/03-v03-evaluation.md)\
Spec: [修复规格](../spec.md)；[诊断及规划](../online-diagnosis-20261005.md)\
Owner: Erwin\
Directory: evals/transfer/\
Status: implemented — 已实现并针对性验证，PR开放，未合入/未完成真人批准\
Blocked by: None\
Source issue: [Issue #72](https://github.com/DrErwin/hackerthon-bank-agent/issues/72)

交付：在线判据与前置交互失败保真。复用真实HTTP/平台/隔离银行验证，一个目录、一分支、一PR。不恢复模型10，不改银行规则、不自动重试或下一阶段。

- [x] INP09实际拒绝和“需要精确到分，无法处理”被正确识别；无任务无提示、静默舍入、可执行确认/出流反例仍失败。
- [x] INP03任务failed且无interaction时停止输入动作，记录此前状态/账户追问失败，保留资金/隐私检查，不被TypeError覆盖、不改Passed。
- [x] 脱敏结果区分模型结果数量/格式/接入异常与供应商故障；没有证据时保留未知，固定码/阶段能力若跨目录需另列依赖。
- [x] 原153分母、红线、专用非法金额入口和首次报告保留，定向验证不冒充完整验收。

## Comments

- 2026-10-05：用户授权诊断、问题记录与修复规划；本票是后续最小修复范围，未获实施、prompt修改、合并授权。纯规划只核对内容/链接/编号/空白，不运行CI。

- 2026-10-05：用户明确批准上一轮建议的11/12实施；按票执行并独立验证/提交PR，未授权恢复10或合并。

- 2026-10-05：独立交付[PR #73](https://github.com/DrErwin/hackerthon-bank-agent/pull/73)，代码HEAD `a16efc4668894fa3c54d72a7436a511081ac1308`。Standards与Spec AI复审各0剩余发现；不代替Ringo真人安全审查。原10仍paused，原01—09保持resolved，未合并本PR。

## 验证证据

原四个针对性回归先红后绿；审查发现“舍入后请确认”误判，增加反例并移除“请确认”独立拒绝判据。最终23项判据/真实链路回归通过，6项相关正常场景通过。INP03字符串null仍为真实Failed，停止无交互动作后执行共同资金/隐私检查；不把模型故障改Passed。只保存固定白名单错误码和异常类，未知不输出原始异常内容或归因供应商。

组合回放与限定真实GLM边界见[诊断报告追加实施记录](../online-diagnosis-20261005.md)；原153分母、标准21与缺项8分母不变。来源Issue #72继续开放到合入及交付核对。

- 最终代码HEAD的[Repository checks通过](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37224931011)。PR #73仍OPEN；CI绿不表示真人批准、合并或版本验收。
