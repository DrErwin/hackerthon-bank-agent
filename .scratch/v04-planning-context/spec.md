# v0.4 规划入口上下文修复规格（v04-planning-context）

Status: in_progress
Owner: Erwin（PM 自拆，不开交付包）
Source issue: [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)（规划入口无对话历史与待办状态：等待确认时模型回复脱节并否认已有业务）
Deadline: **不晚于 2026-10-15**（为安全线 33+14 轮全量转正复跑留 10-16～10-18 窗口，见 [v04-security/01](../v04-security/packages/01-detector-and-coverage.md)）

## Problem

用户在等待确认（确认单已生成）或等待验证时回复「嗯 / 确认 / 快要多久」，`DeepAgentPlanner.select` 只看到这一条消息：无对话历史（`checkpoint_ns` 每次随机且不挂 checkpointer，属有意设计——规划期原始消息可能含秘密）、无待确认单/验证状态注入、无查询待办的受控工具。结果：24 轮真实复核中 11 轮回复与待办脱节、2 轮否认业务存在（零资金动作，交互质量问题而非安全违规；证据 `b319598` 与安全用例正文 4.4 节）。

## Goal

等待确认/验证期间，用户应答（确认、催促、模糊回复）得到与当前待办一致的回答，不否认已有业务——同时不破坏既有秘密边界：原始消息与秘密不因上下文机制落盘或外泄，不引入资金动作、授权或越权判断。

## 候选方向（Issue #84 已登记，本规格不指定；实现票内定稿）

1. **确定性层短路**：确认/验证等待期的固定话术走确定性分支，不依赖模型判断。
2. **受控上下文注入**：注入结构化待办摘要（非原始消息）+ 固定会话 checkpoint_ns（需先解决原始消息落盘顾虑）。

方向 2 涉及「哪些结构化字段可进规划上下文」的秘密边界口径，由 Ringo 定（或 PM 代行并如实记录）；方向 1 基本绕开该问题。

## Scope

- 主改动：`backend/app/agent_platform/`（`model.py` 的 `DeepAgentPlanner.select` 与相关装配）。
- 可能接缝（若触及则另开票，不混同一 PR）：`backend/app/memory/`（会话上下文存储）、`backend/app/modules/transfer/`（受控待办摘要）、`backend/app/contracts/` 或 `api/`（仅当方案改变公开行为或字段时，先走契约变更流程再实现）。
- 安全规则不由本工作组自行决定；确认/验证的既有安全语义不变。

## Acceptance（与 Issue #84 预期验收对齐）

1. 等待确认或验证时，用户回复确认、催促或模糊应答，回答与当前待办一致，不否认已有业务。
2. 不因上下文机制引入资金动作、授权或越权判断；聊天文字仍不构成批准。
3. 原始消息与秘密不进入长期存储或外部出口（沿用现有秘密扫描与脱敏口径）。
4. 修复后用**真实运行**证据确认改善（SEC-C-001 代表变体 + 共享轮重点子集，本工作组复验票执行）；不得用离线通过替代。
5. 全量转正复跑（SEC-C-001 余 14 轮 + 33 轮 gated）不属本工作组——完成后移交 [v04-security/01](../v04-security/packages/01-detector-and-coverage.md) 在 10-16～10-18 窗口执行。

## Tickets

- [v04-planning-context/01：规划入口上下文实现](issues/01-planner-context.md)
- [v04-planning-context/02：真实运行复验与移交](issues/02-live-retest-handoff.md)

## Further Notes

- 2026-10-11 由 PM 授权 AI 建立本规格与票据（队员开工规范的自拆路径）；实现按 `implement` 走分支/PR/CI，本机 Skill 检查在开工会话执行。
