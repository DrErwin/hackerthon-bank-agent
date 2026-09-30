# v0.3.0 完成情况：普通转账纵向链路

> 状态：进行中\
> 最后更新：2026-10-01

## 已完成

- 普通转账纵向场景、五个交付包与 12 张 Erwin 单目录实施票已建立；阶段范围、负责人和排期已确认。
- 后端工程骨架、公共契约代码、运行存储、模拟银行与接入层、审计回放、记忆、最小安全门、普通转账参考流程和主 Agent Harness 已通过 PR 合入 `main`。对应实施票为 01—09；模拟银行评测票 11 也已合入。PR #1—#19 均已合并，其中部分为缺陷修复与 CI 加固。
- 票 10 的 API 工程增量已于 2026-09-30 经 [PR #25](https://github.com/DrErwin/hackerthon-bank-agent/pull/25) squash 合入 `main`，提交 `cd50ebdf36795b6883641e7494e4a29acfbbdcbc`。包含任务、确认验证、取消 / 原结果回查、持久事件流及管理员只读审计。独立工程、契约与安全 AI 审查通过，跨会话不可用操作问题已修复并复查；未记录真人批准。
- 合并提交的 [主线 CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36687051464) 通过：完整后端 **178 passed**（API 29 项），模拟银行评测 **14 passed**；文档链接、语法及差异空白检查通过。合并后的跨会话专项回归另 **1 passed**。

这些结果证明已合入后端模块能通过当前自动测试；不代表部署配置、真实模型、前端联调或完整用户路径已经验收。

## 仍待完成

- 票10全部验收仍未完成：新登录恢复缺口#23已由补票01—04解决；普通闲聊仅回复[#24](https://github.com/DrErwin/hackerthon-bank-agent/issues/24)的05 / 06仍未开始。部署模型 / 策略组合、真实模型调用及React联调仍待提供。API工程增量与恢复补票合入不代表v0.3完成。
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

## 下一更新点

继续补票05 / 06的仅回复能力及部署组合；本次不自动启动后续实现。API 和前端具备真实接口联调条件后，记录端到端预跑结果；三类代表性评测可运行后，执行 AF01—AF14 联合验收。收口前补齐验证证据、差异和遗留，再判断是否进入 v0.4.0。
