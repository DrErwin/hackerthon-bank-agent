# 10 — 缺项转账建立任务并诊断模型无有效输出

Ticket ID: v03-transfer-eval-fixes/10\
Package: [transfer-agent-framework/packages/01-vertical-backend：v0.3纵向后端主链路](../../transfer-agent-framework/packages/01-vertical-backend.md)\
Spec: [修复规格](../spec.md)\
Type: 开发（先复现诊断，未确定原因不承诺异常已修）\
Owner: Erwin\
Directory: backend/app/agent_platform/\
Status: resolved — 2026-10-05 PR #75已按授权合入；AI代审与软件验证完成，专业/联合验收另待\
Blocked by: None

Historical pause: 用户2026-10-04要求暂缓，本记录保留；2026-10-05最新明确授权已恢复实施。

交付：明确转账而缺项时提供缺项proposal并建立原任务；近似金额不确定，合法十六元能形成确认并在同任务纠正。INP14/CNF15/OBS12的ValueError先诊断，再决定本目录最小修复；不能证明的外部故障保留Blocked及处理建议，不扩大本票。

- [x] INP08追问精确金额，INP13初单16元、专用改60元重新确认后仅6000分；RCV01/21保持同task_id追问原缺金额。
- [x] INP14金额区间不选端点或平均数；D2非法金额明确拒绝/待输入，无默认值、绝对值或舍入；普通闲聊仍不创建业务任务。
- [x] 固定模型配置、同输入多次预定复跑，保留全部proposal/安全异常类型和失败；真实模型与离线分别报告，不用替身结论代替GLM。
- [x] 定向缺项追问覆盖及全量指标按批准分母100%核对；真实GLM未达标则继续记录产品失败，不能用合法21/21放宽。
- [x] 三个无可用输出样本区分模型工具调用数量/字段解析/接入故障，有证据才定根因；不新增自动重规划、转账兜底或供应商错误假结论。

## 执行与验证边界

本节保留初始授权历史，已由下文2026-10-05恢复授权及合入记录覆盖。

本票已按用户“按你建议”确认的规划发布，尚未领取或启动。后续代码实现需另获执行授权，使用implement并遵守单目录边界；涉及隐私、验证、资金或审计须Ringo安全审查，当前没有合并批准或豁免。按规格复用真实接口/平台入口、现有故障接缝和银行账本验证，必要回归只写在本票目录。纯文档规划不运行CI。

## Comments

- 2026-10-04：用户在简要解释D1、D2及十项拆分/依赖/验收方式后回复“按你建议”。批准规划与本地票发布，未授权本轮实现、提交或合并；来源03、验收04/12和v0.3状态未提升。
- 2026-10-04：用户要求“暂缓10，先只看程序问题”，本票由ready-for-agent改为paused；模型理解、提示词/规划输出调整及三个ValueError样本诊断退出当前修复范围。01—09不依赖本票；原缺口和完整验收要求保留。

- 2026-10-05：最新用户允许诊断但未恢复实施；Status保持paused。诊断见[报告](../online-diagnosis-20261005.md)，关联[Issue #68](https://github.com/DrErwin/hackerthon-bank-agent/issues/68)、[Issue #69](https://github.com/DrErwin/hackerthon-bank-agent/issues/69)、[Issue #70](https://github.com/DrErwin/hackerthon-bank-agent/issues/70)。建议实施获授权后补明确转账分类、空账户null与单结果终止；CNF10/15已复现双工具结果，原INP14/RCV21 ValueError归因仍未知，不填写成网络故障。

## 2026-10-05 恢复与实施边界（覆盖旧暂停）

用户明确要求“开一个新对话来完成这一个票10”，Prompt不要补丁式，应简洁统一，测试完成后可以合并。Status恢复ready-for-agent，新对话负责领取、最小实现、必要测试/审查与CI，通过后按本次用户授权合并；无需用户再细化技术规划。上文“尚未实施授权”和“paused”为历史记录，不能继续作为阻止执行的理由。

关联[Issue #68](https://github.com/DrErwin/hackerthon-bank-agent/issues/68)、[Issue #69](https://github.com/DrErwin/hackerthon-bank-agent/issues/69)、[Issue #70](https://github.com/DrErwin/hackerthon-bank-agent/issues/70)。扩充当前已诊断PAY11明确转账分类、INP03真正空账户、CNF10双工具结果回归，保留原INP13/RCV01/21等全部验收。

- [x] Prompt以“意图是否明确、字段是否确定、本轮单一结果”为统一原则，不按失败样本逐条加特例；具体近似/区间/缺项/非法值留测试。
- [x] 一次有效结果后结束本轮规划，保留真正冲突输出的拒绝；空值用JSON null/省略，不默认A1。
- [x] 在本目录以固定安全码/数量/阶段区分无结果、多结果、字段解析和调用异常，不泄漏原始provider内容或敏感参数；原异常证据不足的历史归因继续未知。

代码仅backend/app/agent_platform，一目录/分支/PR。11/12已合入，不夹带其旧实施。读[新对话交接](../ticket10-handoff-20261005.md)后开始；实际领取时改in_progress。Ringo本人审查/专业安全材料另列，不能用AI代审或代码合并冒充专业验收。


## 2026-10-05 领取、验证与授权合入

Codex于2026-10-05按Erwin执行线领取in_progress；[PR #75](https://github.com/DrErwin/hackerthon-bank-agent/pull/75)合入`c49269e718d4db9f56865c4a2e42c467c6fbcde1`后标resolved。最终21项各2次Passed；离线/GLM各153样本152 Passed/1专业材料Blocked，标准21/21、缺项8/8。最终代码CI通过，规范/需求及安全AI独立复审无剩余代码发现。全部失败、历史未知归因及专业/联合验收边界见[验证记录](../ticket10-verification-20261005.md)。用户AI代审授权不等于Ringo本人或专业安全验收。
