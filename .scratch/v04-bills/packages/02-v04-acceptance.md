# 交付包 02：v0.4 联合验收与收口

Status: planned（依赖各线交付，条件见 Start when；不冒充通过。**2026-10-20 收口日核对**：① 账单——L01/L03/评测/审计证据已合入，L02 与 Issue #136 票 09 未开 PR，BF01—BF06 未全部通过；② 前端——票 03 已交付，票 04/05 按 PM 01:45 决定留在本期、不顺延；③ 安全——三张 Ready（#149/#159/#162）待退修合并，检测器与观察端未完成；④ 平台——F21—F24 与票 05 阶段一已合入，L03 注册与阶段二未完成。**任一线未齐不启动、不记通过**）
Owner: Erwin 牵头；参与：周恩宇（账单）、梁爽/六水（前端）、Ringo 或 PM 代行（安全）、Erwin（平台/底座，[v04-platform/01](../v04-platform/packages/01-foundation-agent-mockbank.md)）
Activation: 2026-10-11 建立（v0.4 启动同日）
Start when: ① [包 01 账单业务能力与评测](01-bills-backend.md) 主体交付（BF01—BF06 通过、评测下限达标）；② [frontend-complete/01](../../frontend-complete/packages/01-v04-complete-frontend.md) 交付（FE-01—FE-06 通过、替换简易前端）；③ [v04-security/01](../../v04-security/packages/01-detector-and-coverage.md) 检测器与评测完整性完成；④ [v04-platform/01](../v04-platform/packages/01-foundation-agent-mockbank.md) 主体交付——F21—F24 报告与文件交付已合入 main，**真实账单模块接入（[票 05](../v04-platform/issues/05-real-bills-integration.md)）完成**后账单纵向链路才具备联调条件。任一线未齐时如实记录阻塞与提供方
Spec: [v0.4 账单纵向场景规格](../spec.md) · [v0.4 需求](../../../docs/versions/v0.4.0/requirements.md)

Accepted by: 未记录
Accepted at: 未记录
Work spec: 待启动时建立（Erwin 自拆）

Source issue: [Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87)（总索引；飞书同步按 [git-workflow §4](../../../docs/agents/git-workflow.md) 执行，#90 已于 2026-10-11 完成）

## 业务目标

按 [v0.4 需求验收标准](../../../docs/versions/v0.4.0/requirements.md) 5 条逐项收口：证据落 [completion.md](../../../docs/versions/v0.4.0/completion.md)，状态翻转 docs/README 与 ROADMAP，飞书按人决定同步（#90），并确认 v0.5（联动）启动条件。

## 交付范围

1. 双场景（转账+账单）端到端联调证据汇总。
2. 前端替换简易前端后的回归汇总（FE-01—FE-06，重点：确认、验证、刷新恢复、重复点击、真实结果展示不回退）。
3. 安全补验：#86 检测器与检测层交付后，v0.3 遗留的 gated 项补验加回（记录为补验，不追溯改写 v0.3 收口结论）。
4. 底座 #84/#85 完成情况并入证据（规划入口上下文、确认/验证历史只读回放）；v04-platform/01 平台侧并入证据（F21—F24 报告与文件交付、账单任务接线 `module=bills`/`report_ready`、真实账单模块接入与联调）。
5. `docs/versions/v0.4.0/completion.md` 更新、docs/README 与 ROADMAP 状态翻转、飞书同步与甘特图重建按 [git-workflow §4](../../../docs/agents/git-workflow.md) 执行。
6. v0.5 启动条件确认（联动线：业务能力、评测与前端接入）。

## 验收标准

- v0.4 需求验收标准 1—5 逐条有可复核证据；未齐项如实记录为阻塞或例外，不写成通过。
- 收口后 v0.3 已验证的安全与资金闭环无回退记录。

## 拆票

Erwin 自拆：证据汇总与 completion 更新归 `docs/versions/`（文档票）；如需代码修复，回到对应归属目录的实施票，本包不跨目录改代码。

## 候选证据（已产出，待联合验收汇总时正式并入）

- 2026-10-18 [票 05 阶段一（L01）独立检查验收记录](../v04-platform/issues/05-real-bills-integration.md)：真实 GLM 规划（`glm-5.3`）→ 消息入口 → `bills.summarize` 任务（`module=bills`）→ 月份等待 → 恢复 → succeeded（15 笔 / 576100 fen / 账户 A1+A5），零资金动作，审计成对、无验证码原文；两次独立运行一致。基线 main `c10ba00`（PR #143 白名单 `81345b5` + #144 接线 `c10ba00`，代行已记录）。阶段二与前端/账单线纵向联调证据仍缺。
