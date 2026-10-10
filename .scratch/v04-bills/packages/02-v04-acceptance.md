# 交付包 02：v0.4 联合验收与收口

Status: planned（依赖各线交付，条件见 Start when；不冒充通过）
Owner: Erwin 牵头；参与：周恩宇（账单）、梁爽/六水（前端）、Ringo 或 PM 代行（安全）
Activation: 2026-10-11 建立（v0.4 启动同日）
Start when: ① [包 01 账单业务能力与评测](01-bills-backend.md) 主体交付（BF01—BF06 通过、评测下限达标）；② [frontend-complete/01](../../frontend-complete/packages/01-v04-complete-frontend.md) 交付（FE-01—FE-06 通过、替换简易前端）；③ [v04-security/01](../../v04-security/packages/01-detector-and-coverage.md) 检测器与评测完整性完成。任一线未齐时如实记录阻塞与提供方
Spec: [v0.4 账单纵向场景规格](../spec.md) · [v0.4 需求](../../../docs/versions/v0.4.0/requirements.md)

Accepted by: 未记录
Accepted at: 未记录
Work spec: 待启动时建立（Erwin 自拆）

Source issue: [Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87) · [#90](https://github.com/DrErwin/hackerthon-bank-agent/issues/90)（飞书同步与版本进度）

## 业务目标

按 [v0.4 需求验收标准](../../../docs/versions/v0.4.0/requirements.md) 5 条逐项收口：证据落 [completion.md](../../../docs/versions/v0.4.0/completion.md)，状态翻转 docs/README 与 ROADMAP，飞书按人决定同步（#90），并确认 v0.5（联动）启动条件。

## 交付范围

1. 双场景（转账+账单）端到端联调证据汇总。
2. 前端替换简易前端后的回归汇总（FE-01—FE-06，重点：确认、验证、刷新恢复、重复点击、真实结果展示不回退）。
3. 安全补验：#86 检测器与检测层交付后，v0.3 遗留的 gated 项补验加回（记录为补验，不追溯改写 v0.3 收口结论）。
4. 底座 #84/#85 完成情况并入证据（规划入口上下文、确认/验证历史只读回放）。
5. `docs/versions/v0.4.0/completion.md` 更新、docs/README 与 ROADMAP 状态翻转、飞书 publish 判断（#90）。
6. v0.5 启动条件确认（联动线：业务能力、评测与前端接入）。

## 验收标准

- v0.4 需求验收标准 1—5 逐条有可复核证据；未齐项如实记录为阻塞或例外，不写成通过。
- 收口后 v0.3 已验证的安全与资金闭环无回退记录。

## 拆票

Erwin 自拆：证据汇总与 completion 更新归 `docs/versions/`（文档票）；如需代码修复，回到对应归属目录的实施票，本包不跨目录改代码。
