# v0.3.0 完成情况：普通转账纵向链路

> 状态：进行中\
> 最后更新：2026-10-10

## 本轮最新状态（2026-10-10）

安全评测前置工程已完成并入库（2026-10-09/10）：真实GLM全量57轮与转正24轮证据、React页面证据（SEC-C-001/P-002，`react_evidence.py`）、解释口径§4.4及两轮复核档案均已归档于 `evals/security/evidence/` 与运行台账；S07—S09专项用例与导出失败分支补齐（SEC-E-008/L-009/V-017/X-008），SEC-N-008收口，分母122/274/330，评测测试50/50通过、离线冒烟无伪造通过。验收下限核对：每类异常≥3达标，R06（演示管理）8条低于10条下限由Ringo核定。

按用户2026-10-10决定：真实威胁检测移出v0.3验收范围（相关gated轮保持Blocked为已知缺口，Ringo交付后补验加回）；规划入口上下文问题（只传当前消息、无对话历史与业务状态）暂缓实现，已记录"交互至少带历史数据"。给Ringo的交接清单已开 [Issue #86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)（立即项：专业签核+全量适用性核查+验收边界确认；后续项：检测器规格与补验）。v0.3仍未验收：待Ringo签核、转账评测专业结论与原票12（AF01—AF14、T01—T18）联合验收。

## 已完成

- 普通转账纵向场景、五个交付包与 12 张 Erwin 单目录实施票已建立；阶段范围、负责人和排期已确认。
- 后端工程骨架、公共契约代码、运行存储、模拟银行与接入层、审计回放、记忆、最小安全门、普通转账参考流程和主 Agent Harness 已通过 PR 合入 `main`。对应实施票为 01—09；模拟银行评测票 11 也已合入。PR #1—#19 均已合并，其中部分为缺陷修复与 CI 加固。
- 票 10 的 API 工程增量已于 2026-09-30 经 [PR #25](https://github.com/DrErwin/hackerthon-bank-agent/pull/25) squash 合入 `main`，提交 `cd50ebdf36795b6883641e7494e4a29acfbbdcbc`。包含任务、确认验证、取消 / 原结果回查、持久事件流及管理员只读审计。独立工程、契约与安全 AI 审查通过，跨会话不可用操作问题已修复并复查；未记录真人批准。
- 合并提交的 [主线 CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36687051464) 通过：完整后端 **178 passed**（API 29 项），模拟银行评测 **14 passed**；文档链接、语法及差异空白检查通过。合并后的跨会话专项回归另 **1 passed**。

上述178项结果为历史工程验证。本轮本机组合、真实GLM与简易前端已验收，证据见下方2026-10-02收口；AF01—AF14完整联合验收仍未完成。

- 本机GLM运行组合、完整确认展示、恢复终态提示及前端修复已由PR #43/#44/#45/#42合入；真实GLM 5.3/Coding Plan与React/API联调通过，原票10六项验收满足，Issue24已关闭。
- 本轮代码主线eabc682的CI通过：后端269项、MockBank14项；前端10项及build、主线启动专项10项通过。详细证据见下方2026-10-02收口。

## 仍待完成

- 梁爽、六水的普通转账关键流程原型图；Erwin简易前端已交付，不代填原型图完成。
- Ringo本人专业安全签核与全量适用性核查（安全评测前置已完成并归档，交接见 [Issue #86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)）；核定R06是否扩充至10条下限。
- 转账业务评测的专业审查结论（套件已交付：离线与真实GLM各153样本152 Passed/1专业材料Blocked，标准21/21、缺项8/8；按用户2026-10-10指示，专业结论与TF-VFY-16材料并入 [Issue #86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86) 由Ringo完成）。
- 原票12：AF01—AF14完整联合验收、T01—T18覆盖说明、问题回归和v0.3收口决定。
- 已知缺口（不阻塞本次签核，结论需引用）：规划入口上下文问题（底座，暂缓+已记录方案方向）；真实威胁检测（按用户决定移出v0.3验收，Ringo交付后补验加回）。

## 补票 01—04 初验与修复（2026-10-01）

- 审查对象为本地集成提交 `e786e644737e82085e5f0bbf9905bf95bde8d34e`，比较基线为 `origin/main` 的 `041a6e4`；不是主线或远端 PR 的测试结果。
- 完整后端 **204 passed**（148.18 秒），模拟银行评测 **14 passed**；文档链接、Python 语法与差异空白检查通过。测试使用可重复模型候选，真实模型、React 与 AF01—AF14 未验收。
- Standards 轴发现 1 项 P1：任务和模型候选已保存，但第一个业务检查点建立前中断，新会话恢复连续返回 `TASK_NOT_FOUND`，原任务无法继续。
- Spec 轴发现 1 项 P1：S1→S2 恢复在存储转换后、业务检查点迁移前中断；再次登录 S3 时原转换信息被覆盖，连续恢复返回 `ACCESS_DENIED`。
- 两项均用临时数据库和公开 Harness 入口注入中断复现，未改动交付代码；现有 204 项测试未覆盖这两个窗口。详见[验收记录与复现步骤](../../../.scratch/v03-session-recovery-reply/acceptance-2026-10-01.md)。
- 用户要求修复后，集成快照 `8c7a6be` 已修复上述问题及复审追加的初始化中断、终态运行编号问题。最终全后端 **212 passed**（169.16 秒）、模拟银行 **14 passed**；文档链接、Python 语法和空白检查通过。新增 8 项定向用例证明重新确认 / 验证、重启、再次登录、原任务 / 操作身份、重复回执及单次扣款；Standards / Spec 最终 AI 复审均无 P0–P3。
- 四票工程复验通过，已经[PR #30](https://github.com/DrErwin/hackerthon-bank-agent/pull/30)、[PR #31](https://github.com/DrErwin/hackerthon-bank-agent/pull/31)、[PR #32](https://github.com/DrErwin/hackerthon-bank-agent/pull/32)、[PR #33](https://github.com/DrErwin/hackerthon-bank-agent/pull/33)按依赖顺序合入；各PR的最终提交CI通过。主线验证通过后四票标为resolved，#23已关闭。
- 用户于2026-10-01明确指示「我豁免批准，合并」，本轮补票01—04的Ringo真人批准门槛由用户豁免；AI复审不记为真人批准，长期审查规则不变。

## 补票01—04合入与收口（2026-10-01）

| 完整票号 | PR | 主线合并提交 | 状态 |
|---|---|---|---|
| [v03-session-recovery-reply/01：原任务的新会话归属转换](../../../.scratch/v03-session-recovery-reply/issues/01-task-session-transition.md) | [PR #30](https://github.com/DrErwin/hackerthon-bank-agent/pull/30) | `712d104dc673d53071a720a5e8046521f6cab560` | resolved |
| [v03-session-recovery-reply/02：转账公开新会话恢复](../../../.scratch/v03-session-recovery-reply/issues/02-transfer-session-recovery.md) | [PR #31](https://github.com/DrErwin/hackerthon-bank-agent/pull/31) | `f431b88f34424487effab59975e68c7fd2d84068` | resolved |
| [v03-session-recovery-reply/03：Harness新会话恢复协调](../../../.scratch/v03-session-recovery-reply/issues/03-harness-session-recovery.md) | [PR #32](https://github.com/DrErwin/hackerthon-bank-agent/pull/32) | `651860433d6d9ebc1aba4c507f643324f455af7b` | resolved |
| [v03-session-recovery-reply/04：API新会话恢复接入](../../../.scratch/v03-session-recovery-reply/issues/04-api-session-recovery.md) | [PR #33](https://github.com/DrErwin/hackerthon-bank-agent/pull/33) | `f487ff5f002de03fd560b28ddb2b8df0a8c57dbc` | resolved |

- [代码主线CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36774040361)通过：后端212项（63.64秒）、模拟银行14项（0.46秒），文档链接、Python语法及差异空白检查通过。
- 最终代码主线`f487ff5f002de03fd560b28ddb2b8df0a8c57dbc`与验收快照8c7a6be的四目录Python实现和测试一致；API只追加交接文档。
- 用户于2026-10-01明确指示「我豁免批准，合并」，本轮补票01—04的Ringo真人批准门槛由用户豁免；AI复审不记为真人批准，长期审查规则不变。
- [恢复缺口#23](https://github.com/DrErwin/hackerthon-bank-agent/issues/23)已关闭；#24仅回复仍开放。05 / 06、原票10全部验收、原票12联合验收及v0.3阶段收口仍未完成，未同步飞书。

## 补票05：Harness 无业务意图仅回复（2026-10-01）

- 按用户指示在新 worktree 开始 [v03-session-recovery-reply/05](../../../.scratch/v03-session-recovery-reply/issues/05-harness-reply-only.md)，实现通过 [PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35)提交，Repository checks 已通过；票保持 `in_progress`，Ringo 真人审查与合入尚未完成。
- 最新目标用例 **33 passed**，后端全量回归 **225 passed**（157.05秒），模拟银行评测 **14 passed**；文档链接检查与差异空白检查通过。代码支持仅回复、模糊意图、模型失败和显式转账兼容，并拒绝在审计前留下可识别凭据；模型输出记录脱敏快照。
- Deep Agents 未向 Harness 暴露最终组装的系统提示与会话上下文，故 `model.started` 如实标记请求证据缺失；这不是完整模型调用回放，也不代表真实模型验证通过。
- [v03-session-recovery-reply/06：API 仅回复接入](../../../.scratch/v03-session-recovery-reply/issues/06-api-reply-only.md)继续阻塞，直到05的实现PR合入；#24保持开放，v0.3仍未完成。

## 下一更新点

### 补票05本轮复验（2026-10-01）

- [PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35) 验收发现并修复三个问题：原始模型回复通过规划检查点落盘、英文密码标签绕过回复脱敏、初始化中断后的任务重新理解为仅回复却一直处于运行中。
- 修复提交 `2f850b8`：临时规划不持久保存模型消息；回复复用既有凭据检查后再脱敏；已有任务无法继续转账时明确转为受控失败。业务恢复检查点与资金确认规则保持原路径。
- 定向测试 **36 passed**，Standards / Spec 独立 AI 复审无剩余阻塞。真人安全批准与合入尚未完成；05保持 `in_progress`、06保持 `blocked`，#24及版本联合收口未完成，未同步飞书。

补票05已合入，继续在独立工作线完成06的API实现与验收。之后补部署组合；API 和前端具备真实接口联调条件后，记录端到端预跑结果；三类代表性评测可运行后，执行 AF01—AF14 联合验收。收口前补齐验证证据、差异和遗留，再判断是否进入 v0.4.0。

- 最终修复复验：后端 **228 passed**（120.43秒）、模拟银行 **14 passed**（1.05秒），文档链接、Python语法及差异空白检查通过；代码提交 `2f850b8` 的 [PR CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36807503540) 通过。


## 补票05合入记录（2026-10-01）

用户在已告知本票缺少Ringo真人批准后明确指示「补票05合并」，本轮依该指示批准合入，豁免仅限补票05；不记录为Ringo真人批准，长期审查规则不变。[PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35)已squash合入main，提交 `0613a1a1eb8df9bde86de1c0d364bee48f4664cc`；最终PR提交 `36713e4` 的CI通过。三个验收问题的修复均包含在合并提交中，定向36项、后端228项、模拟银行14项通过，双轴AI复审无剩余阻塞。[合并提交主线CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36810100834)通过：后端228项（70.51秒）、模拟银行14项（0.47秒），文档链接、Python语法及差异空白检查通过。05标为resolved。

05已合入；06的公开能力及合入前置依赖已提供。06的API实现及验收仍未合入，Issue #24保持开放；真实模型、React、原票10全部验收、原票12和v0.3联合收口均未完成，未同步飞书。此前待批准、未合入等条目为历史记录。

## 补票06：API仅回复接入（2026-10-01）

- 前置依赖补票05已由[PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35)合入main（0613a1a）；补票06已切换到合并后的main提交54b6e7c作为基线，当前仅含API目录实现与关联过程记录。
- 消息入口返回可空task_id的202受理；API原子保存消息与可恢复作业，通过Harness公开handle_message结果分别保存ReplyOnly回复或关联转账任务。请求重放沿原作业，历史及SSE保留稳定事件编号，显式转账仍使用既有确认与验证流程。
- 本地验证：完整后端234 passed（168.83秒）、API单目录41 passed（116.02秒）、MockBank14 passed；API源文件Pyright 0 errors，Python语法、文档链接与差异空白检查通过。Draft [PR #37](https://github.com/DrErwin/hackerthon-bank-agent/pull/37)已以main为基线打开、Repository checks已通过（[CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36812809932)）；Standards / Spec双轴独立AI复审均无发现，不代表真人批准。
- ticket 06和Issue #24仍开放。真实模型、React、原票10全部验收、原票12联合验收及v0.3收口未完成；不把本地测试或AI复审记为真人批准。

## 补票06本轮验收（2026-10-01）

用户明确授权「验收补票6，有问题就修复，验收完合并，不用别人批准，更新文档」；本票豁免其他人批准，不记录为Ringo真人批准，不改变长期规则。

发现并修复两项恢复问题：未开始消息在旧会话过期后无法继续；闲聊回复发布中断后重试可能重新分类为转账。未创建任务的合法重传使用当前会话，已有任务只关联原任务并要求显式恢复。先保存脱敏仅回复结果再发布，无法确定原结果时受控停止，不再次理解原消息。

复验：完整后端240 passed，MockBank14 passed；专项7项通过，隐私及回复中断追加3项通过；API源文件Pyright 0 errors，链接、Python语法和差异空白检查通过。Standards与Spec独立AI复审均无剩余阻塞。补票06后端验收通过；[PR #37](https://github.com/DrErwin/hackerthon-bank-agent/pull/37)待最终提交CI及合入。此前未实现、未验收等条目为历史快照。真实模型、React、原票10全部验收、原票12及v0.3收口仍未完成；Issue #24包含真实模型与前端验收条件，继续开放。未同步飞书。

## 补票06合入收口（2026-10-01）

[v03-session-recovery-reply/06：API仅回复接入](https://github.com/DrErwin/hackerthon-bank-agent/pull/37)后端验收通过，PR #37已squash合入main，提交 `1d284b10107f37369c1cefb953939fdaccc14c92`。两项恢复问题修复包含在主线；最终提交 `e249d23` 的[PR CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36814814315)通过。完整后端240项、MockBank14项以及类型和仓库静态检查通过，双轴AI复审无剩余阻塞。补票06标为resolved，六张补票均已合入；本票按用户明确授权豁免他人批准，未记录为Ringo真人批准。

[合并提交主线CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36815003880)通过：后端240项、MockBank14项，文档链接、语法及差异空白检查通过。Issue #24包含真实模型和前端验收条件，继续开放；真实模型、React、部署组合、原票10全部验收、原票12联合验收及v0.3收口仍未完成。交付包与版本保持in_progress / 进行中，不据此开启下一阶段；未同步飞书。此前未合入、待验收条目为历史记录。下一步补齐部署组合与真实接口联调证据，再执行联合验收。

## 2026-10-02 本阶段实际合入与验收收口

用户在本会话明确回复“已批准合并”，用于上轮列明的PR #42/#43/#44/#45及所需人工安全门槛；记录为项目负责人本轮批准，不冒充Ringo本人审查，不改变长期规则。四PR已按43、44、45、42顺序squash合入。代码主线`eabc68211cd53eb3ca0ea3021dfcfe326bf877fa`的[CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36965745330)通过，完整后端269项、模拟银行评测14项；前端10项及build通过。后端主线本机工厂重启后专项10项通过；主线与已验收组合的业务实现及测试一致，仅README空行和交接说明有差异。

真实GLM 5.3使用用户指定的Coding Plan入口，真实React/API连受控策略与模拟银行。普通回复、缺项补充/候选、低风险验证码、中风险独立管理员模拟人脸、修改取消、刷新、重启、新登录显式原任务恢复、处理中查询原操作已提供证据。主线重启后浏览器又验证普通回复与500元完整确认，取消该复验任务后未新增资金操作；四个既有成功操作和原回执仍保留，各一笔流水。聊天“确认”仅回复，不创建任务或银行动作。模拟银行延迟故障已移除，常规工厂运行；配置秘密仅从Git忽略的后端本机文件读取，无仓库/前端秘密。

本阶段v03-local-demo/01、04及缺陷票05、06标为resolved；前置02、03已由PR40、41交付。原v03-erwin-vertical-backend/10的六项验收在工程回归、实际React/GLM、主线恢复及台账证据下满足，标为resolved。Issue24实际模型和前端仅回复条件满足，按证据关闭。原票12继续blocked：AF01—AF14完整逐项证据、T01—T18覆盖说明及专业安全/转账评测未齐（两评测目录仍仅README）。v0.3仍进行中，不进入v0.4；原型图/完整前端不代填其他负责人完成。此前尚未实现、额度阻断和待批准文字为历史状态，以本段为当前结论。未同步飞书。

## 转账评测与程序修复合入（2026-10-04）

用户明确指示“我豁免ringo审批，合并吧”，适用于本轮转账评测 PR #51 和修复01—09。本轮 Ringo 真人审批由用户豁免；不记作 Ringo 本人审查，不替代专业安全评测，不改变长期审查规则。各代码 PR 更新到最新主线，最终提交的 Repository checks 均通过后，按依赖 squash 合入。

来源套件 [PR #51](https://github.com/DrErwin/hackerthon-bank-agent/pull/51) 合入提交 `86b158eb9db94d9b4352ab1262bea54d7f571f0d`，覆盖151场景、153独立样本及两项平台回归。原始失败与真实GLM历史结果保留。

| 完整票号 | PR | 主线合并提交 |
|---|---|---|
| v03-transfer-eval-fixes/01 | [#59](https://github.com/DrErwin/hackerthon-bank-agent/pull/59) | `a8218ffd2fdb777a9c9382bed9f3ff5cd3f29524` |
| v03-transfer-eval-fixes/02 | [#52](https://github.com/DrErwin/hackerthon-bank-agent/pull/52) | `4d1fd3e4ad0934b4a44afed1e266b7f64cec490f` |
| v03-transfer-eval-fixes/03 | [#54](https://github.com/DrErwin/hackerthon-bank-agent/pull/54) | `ade5393648508f89c9f944efa544f4ca97982378` |
| v03-transfer-eval-fixes/04 | [#58](https://github.com/DrErwin/hackerthon-bank-agent/pull/58) | `086891cfb14f835cf9a29f6fe1876b31c7cea91c` |
| v03-transfer-eval-fixes/05 | [#53](https://github.com/DrErwin/hackerthon-bank-agent/pull/53) | `29fc65e58cbab6ddd87b47d0fbbc314e420be8a4` |
| v03-transfer-eval-fixes/06 | [#55](https://github.com/DrErwin/hackerthon-bank-agent/pull/55) | `6b19e915a345689ce629f35f9f6375780d8d347b` |
| v03-transfer-eval-fixes/07 | [#56](https://github.com/DrErwin/hackerthon-bank-agent/pull/56) | `e4993f9b7bb11ab79bfa56620a530437c08af02b` |
| v03-transfer-eval-fixes/08 | [#57](https://github.com/DrErwin/hackerthon-bank-agent/pull/57) | `bf45957451c51327778f3e04a28e66fb0aeb11b2` |
| v03-transfer-eval-fixes/09 | [#64](https://github.com/DrErwin/hackerthon-bank-agent/pull/64) | `ddcf5b192d74e705b7933867cbc4ea5389853a39` |

代码主线 `a8218ffd2fdb777a9c9382bed9f3ff5cd3f29524` 的实际验证：

- [主线 CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37190825047)通过：完整后端 **327 passed**（97.58秒）、模拟银行评测 **14 passed**（0.40秒）；文档链接、语法与差异空白检查通过。此前隔离组合仅收集backend/app的326项，两种范围不相加。
- 合入后的67个实现、测试和评测文件，与此前已验证组合按规范换行文本逐个核对一致。合并时保留双方README说明，同时保留BankError和PayeeDisplay导入，没有增加业务行为。
- 新增评测判据的15项正例、反例测试通过。主线完整单次153离线样本：**147 Passed / 6 Blocked，0 Failed / 0 Error**；标准用例21/21、离线缺项追问8/8，两项平台回归通过。非法精度单独计分，样本总数仍153，不放大真实模型成绩。
- 六项Blocked为TF-VFY-16缺真实攻击来源材料，及TF-OBS-03—07本次未提供真实React构建；不认定前端功能失败，也不认定当前代码下已通过这些浏览器用例。完整红线仍Unverified，版本NotAccepted；CLI退出码1来自Blocked。

主线报告和逐文件比较保存在本轮隔离worktree的 `.mnemon/merged-main-offline-153/20261004T090228191321Z/report.json`、`report.md` 与 `.mnemon/merged-source-comparison.json`；这些是本机运行证据，未作为跨目录文件塞入代码PR。

`v03-transfer-eval-fixes/01—09` 按程序修复范围标为resolved。票10保持paused，本轮未运行GLM或调整模型/提示词；真实模型历史失败仍待处理。`v03-transfer-evals/03` 的工程套件已合并，但真实GLM及原全绿条件尚未全满足，继续in_progress；该组04及原 `v03-erwin-vertical-backend/12` 仍blocked。AF01—AF14、T01—T18及专业安全/转账结论未齐，不收口v0.3、不进入下一阶段。此前“评测目录仅README”等描述为历史，当前转账目录已交付上述套件。未同步飞书，其他成员PR60—63未在本轮合并。

## 仓库同步记录（2026-10-04）

遗漏的正式规格、实施票及执行记录已整理入库：[转账评测组](../../../.scratch/v03-transfer-evals/spec.md)、[程序修复组](../../../.scratch/v03-transfer-eval-fixes/spec.md)、[纯文档CI维护票](../../../.scratch/docs-only-ci/issues/01-skip-docs-ci.md)。程序修复01—09已resolved，模型票10paused；评测03保持in_progress，04和原票12保持blocked。本次未重新运行评测，不增加验收证据、不启动下一阶段，也未同步飞书。

## 2026-10-05 票11/12实施交付（未合并）

用户明确回复“可以，实施吧”，授权前述票12→11实施；未恢复票10或授权合并。独立交付[PR #73：评测判据与失败交互保真](https://github.com/DrErwin/hackerthon-bank-agent/pull/73)（evals/transfer，HEAD a16efc4）、[PR #74：非正金额明确拒绝及审计](https://github.com/DrErwin/hackerthon-bank-agent/pull/74)（agent_platform，HEAD 401a281）。两轴AI复审无剩余发现，非真人批准。票11/12为implemented、待审查/合入；10仍paused；Issue #68—#72保留开放。没有主线代码修复合入、飞书同步或下一阶段。

23项评测判据回归、6项相关正常场景通过。平台/API137项回归通过；审计补充后48项相关测试通过，两个测试证据字段读取更正后最后3项拒绝/审计故障回归通过。HTTP重复请求保持一次规划/回复，message_completed事件可回放，无资金提交；未直接读取SSE流或新增React页面验收。

最后组合回放原五项在线输出：BNK01、INP09 Passed；PAY11、INP03、INP08继续Failed。原INP03 Error已正确归还业务Failed，保留真实ACCESS_DENIED与共同检查，未修其模型空值。所有原输出回放无银行提交/出流。

限定真实GLM各一次：BNK01 Passed，真实proposal=0由确定性代码拒绝；INP09 Blocked，安全码MODEL_PROPOSAL_AMBIGUOUS。未反复跑到绿，不改原153全量成绩。真实在线发生在审计补充前；其后审计/HTTP及最终组合回放覆盖新分支。模型双结果与缺项问题留票10，专业TF-VFY-16继续依赖Ringo材料，v0.3仍NotAccepted。完整本机实施证据在.mnemon/online-diagnosis-20261005/，未上传原JSON或敏感配置。

最终[PR #73 CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37224931011)与[PR #74 CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37225409981)均通过。代码PR仍开放，真人安全批准未记录；纯文档记录另行发布主线，未运行/等待文档CI。

## 2026-10-05 用户授权AI代审与合并，票10恢复

用户明确要求AI代替Ringo审查并合并PR #73/#74；随后新对话完成票10，Prompt保持简洁统一，测试与审查通过后可以合并。此授权是本次AI代审/合并授权，不记作Ringo本人审查或专业安全验收。

| 实施票 | 合并PR | 合并提交 | 最终代码CI |
|---|---|---|---|
| v03-transfer-eval-fixes/11 | [#74](https://github.com/DrErwin/hackerthon-bank-agent/pull/74) | `2c7ecafd2a94a4ebcd80c651c704f49ca0d98599` | [通过](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37226355691) |
| v03-transfer-eval-fixes/12 | [#73](https://github.com/DrErwin/hackerthon-bank-agent/pull/73) | `ba77dbbf30c01e0244be58c9153807638cb43a6e` | [通过](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37226561639) |

两轴AI与安全代审无剩余发现；PR #73已重新基于合入#74的主线。合并组合23项评测判据通过，主线权限/拒绝/审计6项与最终评测冒烟8项通过。Issue #71/#72按已合入交付关闭；模型Issue #68/#69/#70继续开放。

11/12标为resolved。10由paused恢复ready-for-agent，由新对话领取实施与测试/审查/合并；[票10交接](../../../.scratch/v03-transfer-eval-fixes/ticket10-handoff-20261005.md)规定以业务意图、字段确定性、单一结果三条统一原则组织Prompt，具体用例放测试。不得选择首个/末个候选兜底或把普通确认当授权。用户无需再细化技术规划。

真实GLM模型遗留失败与专业TF-VFY-16缺材料依然存在；这些合并不表示模型票10完成或v0.3验收通过。原153在线报告保留，未同步飞书、未进入下一阶段。纯文档进度按主线独立发布，仅内容/链接/编号/空白检查。


## 2026-10-05 票10软件交付完成，版本仍未验收

[PR #75](https://github.com/DrErwin/hackerthon-bank-agent/pull/75)合入`c49269e718d4db9f56865c4a2e42c467c6fbcde1`；[票10验证记录](../../../.scratch/v03-transfer-eval-fixes/ticket10-verification-20261005.md)保留首轮完整GLM150 Passed/2 Failed/1 Blocked、中间固定运行失败及最终修复结果。最终HEAD `8acb1c7` 两轮21/21定向、离线/GLM各153的152 Passed/1专业Blocked，标准21/21与缺项8/8；OBS03—07真实浏览器通过。最后代码CI后端346/MockBank14通过，规范/需求与安全AI独立代审无剩余代码发现。用户授权的AI代审不记为Ringo本人或专业安全验收。

票10及修复01—12 resolved。专业TF-VFY-16缺真实攻击来源材料，完整红线Unverified；AF01—AF14、T01—T18与专业安全/转账结论仍待，原联合验收票12保持blocked，v0.3 NotAccepted。不关闭原联合验收、不联系队员、不同步飞书、不进入v0.4。

## 2026-10-10 安全评测证据入库与验收边界（收口推进）

**证据与工具（提交 `cc21015`、`b319598`、`f846366` 已推送 main）**

- 离线全集模板330行：19 Passed / 1 Failed / 其余Blocked或NotRun，无伪造通过。
- 真实模型：10-09全量57轮（24真实执行，GLM-4.7 @ Coding Plan）；10-10转正实跑24轮（报告内3 Passed：SEC-P-002×3 经 `--react-evidence` 引用）。证据均在 `evals/security/evidence/2026-10-09|10/`，台账见 `evals/security/run-log.md`。
- React页面证据：`react_evidence.py`（构建版前端+真实API+Playwright）取证SEC-C-001（聊天不批准、确认单仍待按钮）与SEC-P-002（按钮批准→验证码→成功全链），截图入库 `evidence/2026-10-10/react-browser/`。
- 解释口径：正文§4.4定稿；10-09证据首轮复核 + 10-10实跑复核（7符合/11不符合/3规划失败，含对上午判宽的更正：解释以模型reply_only回复为主证据）。
- 用例补齐：SEC-E-008（S07）、SEC-L-009（S08，含/v05快照缺失）、SEC-V-017（S09，含/v06摘要故障）、SEC-X-008（导出生成故障2变体）；SEC-N-008收口转基线；分母122/274/330；测试50/50通过。

**验收边界（用户2026-10-10决定）**

- 真实威胁检测移出v0.3验收范围：SEC-T-003~005等gated轮（33轮）保持Blocked为已知缺口，Ringo在 `backend/app/security` 交付检测器后补验并加回验收（规格见`evals/security/README.md`与Issue #86）。
- 规划入口上下文问题（只传当前一条消息、无对话历史/业务状态注入）归底座（`backend/app/agent_platform`+transfer runtime）暂缓，已记录方案方向（至少带历史数据）与影响（SEC-C-001余14轮待转正）。

**交接与收口**

- [Issue #86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86) 已开给Ringo：立即项=专业签核+全量适用性核查（含R06核定）+转账专业材料+验收边界确认；后续项=检测器实现规格与评测接入。
- 原票12联合验收证据已补齐：[AF01—AF14与T01—T18证据表](acceptance-evidence-2026-10-10.md)（13项通过、AF11主体通过、T适项全覆盖；红线0违规、标准21/21、缺项8/8），票12仍blocked直至Ringo专业结论（Issue #86）汇总。
- 当前结论：v0.3 仍未验收。剩余门槛=Ringo本人签核与全量核查（含转账专业材料）、原票12汇总与收口决定。未同步飞书；纯文档进度按主线独立发布。
