# v0.3 原契约缺口补票：新会话恢复与仅回复

Status: in_progress
Owner: Erwin
Milestone: v0.3.0
Source package: [纵向后端主链路](../transfer-agent-framework/packages/01-vertical-backend.md)
Original spec: [纵向后端实施规格](../v03-erwin-vertical-backend/spec.md)

## Problem Statement

票 10 接入 API 时发现两项原冻结契约要求未实现：同用户重新登录后不能合法恢复原任务；无业务意图的消息不能仅回复。两项缺口于 2026-09-30 15:33:55、15:34:01（北京时间）登记为 [#23](https://github.com/DrErwin/hackerthon-bank-agent/issues/23)、[#24](https://github.com/DrErwin/hackerthon-bank-agent/issues/24)，随后在票 10、PR #25 和版本进度中披露，但没有另建本地实施票。本次补齐追踪，不增加 v0.3 业务范围。

需求依据：[公共契约](../../docs/contracts/公共契约-2026-09-23.md) §6.3 会话过期后原任务恢复、§6.4 F05 无明确业务意图时可仅回复；安全约束沿用[安全底座原则](../../docs/principles/02-security-platform.md)。

## Solution

补齐原任务的新会话恢复及聊天仅回复能力：未提交动作重新确认并按风险重新验证；已提交或提交不确定的动作只回查原操作；普通闲聊返回安全回复，不制造转账任务。按单目录拆票，底座与业务提供公开入口，API 只消费公开结果。

## User Stories

1. 作为用户，我希望重新登录后仍看到原任务，避免丢失进度。
2. 作为用户，我希望未提交转账在新会话重新确认和按风险验证，避免旧授权继续生效。
3. 作为用户，我希望已提交转账只查原结果，避免重复扣款。
4. 作为用户，我希望普通闲聊只收到回复，不出现多余转账任务。
5. 作为用户，我希望聊天中的“确认”不能代替正式确认。
6. 作为服务端维护者，我希望不同用户、演示轮次及过期会话不能恢复他人任务。
7. 作为审查者，我希望恢复保留原任务与操作编号，并记录旧、新会话的转换证据。
8. 作为前端开发者，我希望任务按钮、历史消息和事件反映当前真实可用操作。

## Implementation Decisions

- 现有公共 HTTP 字段可表达仅回复（MessageAccepted.task_id 可为空）；不预设新增公共字段、枚举或修改冻结契约。实施发现确需契约调整时，先独立分档确认并拆公共契约票。
- 新会话恢复不能通过冒用旧会话、直接改写他目录检查点或转移旧确认 / 验证实现。底座在当前有效身份、原任务归属和演示轮次内协调公开入口。
- 会话转换保留 task_id、原 operation_id、业务参数、历史审计；新会话不自动获得旧授权。已 claimed / unknown / processing 的动作只能回查，不能重新规划或提交。
- 未提交动作恢复后仍需当前权限检查和新确认，按当前风险取得新会话验证；终态历史读取不制造新执行。
- 普通闲聊由模型 / Harness 表达受控仅回复结果；API 不写关键词分类规则。仅回复不登记业务任务、不产生确认 / 验证、不调用银行或资金工具。
- 每张实施票、分支和 PR 只改一个归属目录；过程记录按队员开工规范更新。
- 本轮只补规格和正式实施票；不认领实施、不修改业务代码、不关闭 #23 / #24、不将票 10 或 v0.3 标为完成。

## Testing Decisions

- 复用现有公开入口测试：存储任务归属入口、转账 workflow 公开恢复入口、Harness / TransferRuntime 公开协调入口、HTTP 与 SSE 接口。
- 测用户可观察结果和资金副作用，不测试内部结构。覆盖重新登录、跨用户 / 轮次、旧确认 / 验证、取消、处理中 / 未知交易、重启和故障恢复；同一 operation_id 最多一次扣款。
- 仅回复覆盖闲聊、含“确认”的聊天、明确转账、模糊意图、模型失败及重复请求；断言仅回复没有任务、银行调用或授权。
- 各目录先独立验证，API 接入后再证明后端链路。真实提供商与 React 联调仍需单独提供证据，不将测试模型候选冒充真实模型验收。

## Out of Scope

账单、跨场景、完整安全平台、预约转账、部署组合配置、React 实现及 AF01—AF14 最终联合验收。本规格仅补两项已披露缺口的实施追踪。

## 正式实施票

| 本地编号 | 来源 | 标题与归属目录 | 前置依赖 | 可检查结果 |
|---|---|---|---|---|
| [01](issues/01-task-session-transition.md) | #23 | 原任务的新会话归属转换；backend/app/storage/ | 无新增依赖 | 同用户 / 轮次合法转换，旧授权引用不生效，保留原任务与操作 |
| [02](issues/02-transfer-session-recovery.md) | #23 | 转账公开新会话恢复；backend/app/modules/transfer/ | 无新增依赖 | 未提交回到新确认；已提交只回查原操作，不重复扣款 |
| [03](issues/03-harness-session-recovery.md) | #23 | Harness 新会话恢复协调；backend/app/agent_platform/ | 01、02 | 有效新身份协调存储与公开转账入口，记录恢复审计 |
| [04](issues/04-api-session-recovery.md) | #23 | API 新会话恢复接入；backend/app/api/ | [03](issues/03-harness-session-recovery.md) | 重新登录后通过原任务入口恢复，按钮与权限一致 |
| [05](issues/05-harness-reply-only.md) | #24 | Harness 无业务意图仅回复；backend/app/agent_platform/ | 无新增依赖 | 模型 / Harness 明确返回仅回复，无银行调用或业务任务 |
| [06](issues/06-api-reply-only.md) | #24 | API 仅回复接入；backend/app/api/ | [05](issues/05-harness-reply-only.md) | 保存聊天并推送回复，消息不挂转账任务，重复请求不重复执行 |

01、02、05 的原基础依赖已经通过现有 PR 合入；02 可用符合当前契约的测试接缝独立验证，无须人为依赖 01。03 消费两者后，04 提供 HTTP 后端验证。05 与 #23 工作线独立；06 只依赖 05。

## Further Notes

- 用户于 2026-09-30 明确限定“先补正式实施票”；本轮实施状态应保持未开始，不能把补票授权记为代码实施授权或 Erwin 本人领取。
- 本机 to-spec、to-tickets、implement、code-review 文件存在，本轮读取并使用前两项；implement 未执行。来源固定基线沿用队员开工规范 d81f3a183412e71a5b1e84ca21bc1a35eea03a60；本轮未独立校验本机 Skill 内容与上游提交一致性，不静默替换。
- 用户已确认六张单目录票的粒度、依赖及公开验证入口；正式发布一票一文件并更新原票、交付包与正式项目跟踪。GitHub #23 / #24 仍为缺口问题记录，不替代本地实施票。

- 规格与票据于 2026-09-30 经用户确认发布；ready 表示原依赖已具备、可由负责人领取，blocked 表示仍等新增前置票。没有开始编码。

## 2026-10-01 验收更新

上文“仅补票、未开始”描述的是 2026-09-30 发布时的历史状态；此后 01—04 按用户指示本地实现。初验时 01—04 保持 in_progress，实施尚未推送或合入；03 有两个 P1 恢复阻塞，04 受其影响，详见[本次验收记录](acceptance-2026-10-01.md)。05 仍 ready、06 仍 blocked，未开始实现。真实模型、React、真人安全批准及原票 12 联合验收均未完成。

- 修复后更新：8c7a6be 已修复初验阻塞，双轴 AI 复审通过；完整后端212项、模拟银行14项通过，实施合入证据仍按[验收记录](acceptance-2026-10-01.md)更新，未将 AI 复审记为真人批准。

## 当前收口状态

本轮补票05验收发现三个问题并已修复（`2f850b8`）；定向36项与独立双轴AI复审通过，详见[验收记录](acceptance-2026-10-01.md)。05已由用户明确批准合入PR #35（0613a1a），合并提交主线CI通过（后端228项、模拟银行14项），05标为resolved；06的实现及合入前置依赖已满足，API仍待完成，#24仍开放。下文01—04合入时的05 ready状态为历史快照。

01—04已经PR #30—#33按单目录合入并标为resolved，初始化、转换中断与重复恢复修复已包含；[代码主线CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36774040361)通过：后端212项（63.64秒）、模拟银行14项（0.46秒），文档链接、Python语法及差异空白检查通过。#23已关闭。用户于2026-10-01明确指示「我豁免批准，合并」，本轮补票01—04的Ringo真人批准门槛由用户豁免；AI复审不记为真人批准，长期审查规则不变。05仍ready、06仍blocked（等待05），未开始实现；规格整体保持in_progress。

## 2026-10-01 补票05开始实施

用户明确要求在新 worktree 完成剩余补票；Codex 已开始 [v03-session-recovery-reply/05：Harness 无业务意图仅回复](issues/05-harness-reply-only.md)，并创建 [PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35)，Repository checks 已通过。票状态仍为 `in_progress`；Deep Agents 接缝未暴露完整系统提示与会话上下文，审计如实将 `model.started` 请求证据标记为缺失。Ringo 真人审查与05合入未完成，因此 [v03-session-recovery-reply/06：API 仅回复接入](issues/06-api-reply-only.md)继续阻塞。#24、真实模型、React及原票12联合验收仍未完成。


## 补票05合入记录（2026-10-01）

用户在已告知本票缺少Ringo真人批准后明确指示「补票05合并」，本轮依该指示批准合入，豁免仅限补票05；不记录为Ringo真人批准，长期审查规则不变。[PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35)已squash合入main，提交 `0613a1a1eb8df9bde86de1c0d364bee48f4664cc`；最终PR提交 `36713e4` 的CI通过。三个验收问题的修复均包含在合并提交中，定向36项、后端228项、模拟银行14项通过，双轴AI复审无剩余阻塞。[合并提交主线CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36810100834)通过：后端228项（70.51秒）、模拟银行14项（0.47秒），文档链接、Python语法及差异空白检查通过。05标为resolved。

05已合入；06的公开能力及合入前置依赖已提供。06的API实现及验收仍未合入，Issue #24保持开放；真实模型、React、原票10全部验收、原票12和v0.3联合收口均未完成，未同步飞书。此前待批准、未合入等条目为历史记录。
