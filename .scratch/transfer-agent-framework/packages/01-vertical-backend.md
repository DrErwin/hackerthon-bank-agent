# 交付包 01：v0.3 纵向后端主链路

Status: ready\
Owner: Erwin\
Activation: Erwin 已于 2026-09-27 确认，可立即拆票\
Start when: 场景规格与公共契约已冻结（当前已满足）\
Spec: [普通转账驱动的 Agent 框架纵向场景](../spec.md)

Accepted by: 未记录（Owner / Activation 不代替本人接受记录）\
Accepted at: 未记录\
Work spec: [Erwin 详细规格与票据](../../v03-erwin-vertical-backend/spec.md)

领取与执行按[队员开工规范](../../../docs/agents/delivery-workflow.md)：明确接受后 AI 自动登记包与项目跟踪，检查通用 Skill，再续做已有规格和票据；已有实现证据保持原记录。

Detailed tickets: [v0.3 Erwin 纵向后端实施规格与 12 张票](../../v03-erwin-vertical-backend/spec.md)；[原契约缺口补票：#23 / #24 六张单目录票](../../v03-session-recovery-reply/spec.md)

## 业务目标

由一个人贯穿首条后端路径，尽快证明“Agent 理解 → 转账流程 → 安全确认 → 模拟银行 → 结果回放”能够真实运行，减少跨人等待。

## 交付范围

- 公共契约代码、主 Harness、能力注册、Checkpoint、恢复与最小记忆。
- API、追加式运行日志、只读时间线和脱敏证据。
- 银行接入、模拟银行、稳定操作编号、防重复和结果查询。
- 满足首条转账路径所需的最小安全门、确认、验证与最终放行。
- 按冻结 PRD 实现普通转账 14 步参考流程及关键异常分支。

## 边界

- 这是 v0.3 的临时执行安排，不改变 `security/` 和 `transfer/` 的长期归属。
- 不在本包扩建完整安全平台、全部转账变体或通用工作流系统。
- 一个交付包可以覆盖多个目录，但拆票、分支和 PR 必须按目录分开。

## 对其他交付包提供

- 可联调的任务、确认、验证、恢复、状态和时间线 API。
- 可执行的普通转账参考路径与稳定的模拟银行环境。
- 供安全、转账和端到端评测调用的真实系统入口。

## 验收

- 主 Harness 能进入普通转账能力并沿原任务暂停、恢复。
- 未经当前确认和有效验证不能提交资金动作。
- 同一 `operation_id` 最多产生一次资金动作。
- 用户状态、任务状态、银行结果和运行时间线可以关联核对。
- Ringo 完成安全审查、Erwin 完成转账业务审查（09-28 全员会定，原梁爽）后，相关路径才计入联合验收。

## 拆票要求

Erwin 的 12 张实施票已经建立。执行时每张票只对应一个目录，并按票中的前置依赖、可观察结果和验收方式推进。底座、安全、转账不得合并成一张大票。

## 2026-09-30 补票记录

#23 / #24 是票 10 接入 API 时发现的原契约实现缺口，现已按用户确认补为六张单目录实施票。这里只记录补票，未启动实现、不代填 Erwin 本人接受记录，不将交付包标为 accepted。

## 2026-10-01 补票初验

补票 01—04 已按用户要求本地实现，未推送或合入。当前完整后端 204 项及模拟银行 14 项通过，但复验发现两个 P1 恢复阻塞；03 验收未通过，04 链路受阻，详见[验收记录](../../v03-session-recovery-reply/acceptance-2026-10-01.md)。本包不标 accepted；Ringo 真人安全批准与原票 12 联合验收仍待完成，05 / 06 未开始。

## 2026-10-01 补票05实施进度

用户明确要求在新 worktree 完成剩余补票后，Codex 开始 [v03-session-recovery-reply/05：Harness 无业务意图仅回复](../../v03-session-recovery-reply/issues/05-harness-reply-only.md)。本票实现与测试位于 `backend/app/agent_platform/`，当前仍在 `in_progress`，工程 PR 与 Ringo 真人安全审查尚未完成；依赖票 [v03-session-recovery-reply/06：API 仅回复接入](../../v03-session-recovery-reply/issues/06-api-reply-only.md)须等05合入后再开始。本包仍未记录本人接受，未标记为 accepted。

- 修复后：8c7a6be 工程复验后端212项、模拟银行14项、双轴AI复审通过；真人批准与实施合入仍待完成，本包不标accepted。

## 补票合入与收口更新

补票05本轮验收发现两个秘密泄漏和一个初始化恢复阻塞，已在 `2f850b8` 修复并推送 [PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35)。定向36项通过，Standards / Spec独立AI复审无剩余阻塞；真人安全批准和合入仍待完成，06仍blocked，本包仍不标accepted。详见[本轮验收记录](../../v03-session-recovery-reply/acceptance-2026-10-01.md)。

01—04已经PR #30—#33合入并标为resolved；[代码主线CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36774040361)通过：后端212项（63.64秒）、模拟银行14项（0.46秒），文档链接、Python语法及差异空白检查通过。#23已关闭。用户于2026-10-01明确指示「我豁免批准，合并」，本轮补票01—04的Ringo真人批准门槛由用户豁免；AI复审不记为真人批准，长期审查规则不变。05 / 06、部署组合与原票12联合验收仍未完成，本交付包不标accepted。


## 补票05合入记录（2026-10-01）

用户在已告知本票缺少Ringo真人批准后明确指示「补票05合并」，本轮依该指示批准合入，豁免仅限补票05；不记录为Ringo真人批准，长期审查规则不变。[PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35)已squash合入main，提交 `0613a1a1eb8df9bde86de1c0d364bee48f4664cc`；最终PR提交 `36713e4` 的CI通过。三个验收问题的修复均包含在合并提交中，定向36项、后端228项、模拟银行14项通过，双轴AI复审无剩余阻塞。[合并提交主线CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36810100834)通过：后端228项（70.51秒）、模拟银行14项（0.47秒），文档链接、Python语法及差异空白检查通过。05标为resolved。

05已合入；06的公开能力及合入前置依赖已提供。06的API实现及验收仍未合入，Issue #24保持开放；真实模型、React、原票10全部验收、原票12和v0.3联合收口均未完成，未同步飞书。此前待批准、未合入等条目为历史记录。
