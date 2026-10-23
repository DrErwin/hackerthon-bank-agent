# 交付包 02：v0.4 联合验收与收口

Status: done（**2026-10-22 联合验收完成；2026-10-24 PM Erwin 正式接受（含例外 E1—E10）**。证据汇总与逐项判定见[v0.4 联合验收记录](../../../docs/versions/v0.4.0/acceptance-evidence-2026-10-22.md)；版本状态已翻转，飞书同步因用户身份授权过期暂缓）
Owner: Erwin 牵头；参与：周恩宇（账单）、梁爽/六水（前端）、Ringo 或 PM 代行（安全）、Erwin（平台/底座，[v04-platform/01](../v04-platform/packages/01-foundation-agent-mockbank.md)）
Activation: 2026-10-11 建立（v0.4 启动同日）
Start when: ① [包 01 账单业务能力与评测](01-bills-backend.md) 主体交付（BF01—BF06 通过、评测下限达标）；② [frontend-complete/01](../../frontend-complete/packages/01-v04-complete-frontend.md) 交付（FE-01—FE-06 通过、替换简易前端）；③ [v04-security/01](../../v04-security/packages/01-detector-and-coverage.md) 检测器与评测完整性完成；④ [v04-platform/01](../v04-platform/packages/01-foundation-agent-mockbank.md) 主体交付——F21—F24 报告与文件交付已合入 main，**真实账单模块接入（[票 05](../v04-platform/issues/05-real-bills-integration.md)）完成**后账单纵向链路才具备联调条件。任一线未齐时如实记录阻塞与提供方
Spec: [v0.4 账单纵向场景规格](../spec.md) · [v0.4 需求](../../../docs/versions/v0.4.0/requirements.md)

Accepted by: Erwin（PM，本人）
Accepted at: 2026-10-24
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

## 2026-10-22 联合验收启动与证据汇总

PM Erwin 2026-10-22 决定：**不硬凑评测数量指标**，按现有实跑证据 + 如实例外收口。交付包状态由 `planned` 转 `in_progress`，证据汇总与 BF01—BF07 逐项判定见 [v0.4 联合验收记录](../../../docs/versions/v0.4.0/acceptance-evidence-2026-10-22.md)。

启动条件核对（原 4 条）：

1. 账单包：L01 17/17、L02 14/14、L03 14/14、四规则对照 12/12、HTTP 15/15，合计 72 条实跑全过；票 06/07 于 2026-10-22 收口为"已完成、含例外"（错误种类补量约 13 条不补，例外 E1）。
2. 前端包：票 03/04/05 全部合入并回归，PM 2026-10-21 验收通过（单会话、不部署）。
3. 安全包：#86/#88 由 PM 2026-10-22 决定关闭（**非 Ringo 签核**）；离线全量 20/0/337、批次 A 24 轮真实模型、页面离线 24/24 与 PM 真实页面走查均完成；批次 B/C、安全侧真人复核与签核登记为例外。
4. 平台包：真实账单模块接入阶段一（L01，10-18）与阶段二（L03，10-20）均验收；L02 真实链路 10-20 完成；[Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) 于 2026-10-22 关闭。

**验收记录已出，正式接受与版本状态翻转待 PM Erwin 确认。** 本包不代签 Ringo 安全结论，例外不因收口消失。
