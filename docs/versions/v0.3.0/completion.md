# v0.3.0 完成情况：普通转账纵向链路

> 状态：进行中\
> 最后更新：2026-10-02

## 已完成

- 普通转账纵向场景、五个交付包与 12 张 Erwin 单目录实施票已建立；阶段范围、负责人和排期已确认。
- 后端工程骨架、公共契约代码、运行存储、模拟银行与接入层、审计回放、记忆、最小安全门、普通转账参考流程和主 Agent Harness 已通过 PR 合入 `main`。对应实施票为 01—09；模拟银行评测票 11 也已合入。PR #1—#19 均已合并，其中部分为缺陷修复与 CI 加固。
- 票 10 的 API 工程增量已于 2026-09-30 经 [PR #25](https://github.com/DrErwin/hackerthon-bank-agent/pull/25) squash 合入 `main`，提交 `cd50ebdf36795b6883641e7494e4a29acfbbdcbc`。包含任务、确认验证、取消 / 原结果回查、持久事件流及管理员只读审计。独立工程、契约与安全 AI 审查通过，跨会话不可用操作问题已修复并复查；未记录真人批准。
- 合并提交的 [主线 CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36687051464) 通过：完整后端 **178 passed**（API 29 项），模拟银行评测 **14 passed**；文档链接、语法及差异空白检查通过。合并后的跨会话专项回归另 **1 passed**。

上述178项结果为历史工程验证。本轮本机组合、真实GLM与简易前端已验收，证据见下方2026-10-02收口；AF01—AF14完整联合验收仍未完成。

## 仍待完成

- 票10已于2026-10-02完成全部六项验收：新登录恢复缺口#23已由补票01—04解决；普通闲聊仅回复[#24](https://github.com/DrErwin/hackerthon-bank-agent/issues/24)的05已由PR #35合入并标为resolved，06前置依赖已满足、API仍待完成。部署组合、真实GLM/Coding Plan及React联调已在2026-10-02完成并合入；原票10六项验收通过。API工程增量与恢复补票合入不代表v0.3完成。
- 最小 React 前端及与真实后端的联调。
- Ringo 负责的安全评测、Erwin 负责的转账业务评测及相应审查结论。
- 票 12：AF01—AF14 联合验收、问题回归和 v0.3 收口决定。

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
