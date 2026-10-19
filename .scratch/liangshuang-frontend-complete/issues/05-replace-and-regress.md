# 05：替换简易前端与全面回归

Ticket ID: liangshuang-frontend-complete/05
Type: 开发 / 联调验收
Owner: 梁爽（Erwin 集成验收）
Directory: frontend/
Status: blocked（v0.4，**PM 2026-10-20 01:45 决定：不顺延，本期完成**〔撤回同日 01:41 的 deferred 记录〕。Blocked by 票 04 账单插槽与所需真实接口；替换主入口需宕机窗口 + 全面回归 / 适老化走查证据）
Package: [frontend-complete/packages/01：v0.4 完整前端实现与替换](../../frontend-complete/packages/01-v04-complete-frontend.md)
Spec: [梁爽完整前端实施规格](../spec.md)
Core scenarios: [FE-01～FE-06](../../frontend-complete/spec.md)
Blocked by: [liangshuang-frontend-complete/03](03-transfer-slot.md)、[liangshuang-frontend-complete/04](04-bills-slot.md) 及所需真实接口可运行
Verification: 切换主入口后运行前端测试与构建；在真实 API 组合重跑转账、账单、刷新恢复、待核实查询、过期 / 重复点击；桌面和 390×844 适老化走查；保存证据交 Erwin 验收。

## 交付与验收

- 正式前端成为主入口，简易前端不再承担默认流程；保留必要回滚依据。
- FE-01～FE-06 均有可定位的验证证据，区分自动测试、契约 demo 和真实联调。
- 已验证的安全门、交易结果与恢复能力不回退；跨目录缺陷回归归属负责人修复。
- AI 审查、CI、Ringo 审查和 Erwin 验收分别记录，不互相替代。

## Comments
- 2026-10-20（PM 01:45 撤回顺延，AI 代填）：本票**留在 v0.4 完成**，同日 01:41 记录的「顺延 v0.5」作废。票 03 转账插槽已合入 main（PR #142 `92ee700`）；替换主入口与全面回归（含替换后复跑 `evals/security/react_evidence.py`、转账 TF-OBS-03—07、FE-01—FE-06 页面证据与适老化走查）在 v0.4 内排期，前置＝票 04 与真实接口可运行。
