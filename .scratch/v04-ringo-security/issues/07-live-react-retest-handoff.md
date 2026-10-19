# v04-ringo-security/07：真实模型及页面补验与移交

Ticket ID: v04-ringo-security/07
Package: [v04-security/01：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Core scenarios: RS01 至 RS10 中需要真实模型或页面观察的部分
Type: 评测
Owner: Ringo
Directory: evals/security/
Status: blocked（仍在 v0.4，范围已定，等待所列技术前置）
Blocked by: [v04-ringo-security/06：离线集成与全量覆盖核查](06-offline-integration-and-audit.md)核心检查通过；Ringo 执行前确认真实模型入口与预算；所测前端公开路径就绪
Source issue: #86 / #88（[#86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)、[#88](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)）
Verification: 已确认预算后按独立实例及共享轮运行，观察真实模型输入与回复、页面交互和独立银行事实；逐轮判定说明缺口，计算报告 sha256，移交时链接完整证据。

## 交付结果

对照 C-001 历史证据与原 33 gated 缺口补验，将本期实际安全证据移交既有联合验收包。

## 验收条件

- [ ] 先核对 2026-10-12 C-001 六变体 18 轮与解释复核的适用条件，关联原余 14 轮记录；旧报告状态保持。
- [ ] 执行前由 Ringo 确认提供方入口、模型、调用上限与费用预算；本票本轮不预设已获批准。
- [ ] 33 gated 各自满足检测、资料或观察条件后才调用；能力不足保持 Blocked。
- [ ] 真实模型没有离线回退；模型解释依据与实际后端行为分别核对，页面证据匹配同范围版本。
- [ ] 不得用流程零副作用代替识别通过，也不得用 AI 复核代填 Ringo 本人签核。
- [ ] 报告和页面附件按指南归档，台账记录模型及策略版本、实际调用数与结果；移交 v04-bills/02 并保留未决项。

## 实施边界

本票只修改 Directory 指定目录。开发或编写运行代码时使用 implement；有代码时按 code-review 分别核对仓库规范与本票要求，实际测试和本人批准分别记录。纯文档按仓库例外做内容检查；代码和执行配置走独立 PR 及必要验证。

本票在 2026-10-15 随已确认的七项拆分建立。当前未开始实施，最终交付以本票实际证据为准。

## Comments

- 2026-10-15：Ringo 本人在本会话确认测试边界及七项拆票。接票执行前补实际领取时间与状态；本条不作为已执行或验收通过的记录。

- 2026-10-19：[Issue #86 最新 PM 排期结论](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)撤回 10-18 的延期决定，本票保留在 v0.4。分母随实际用例变更重算，旧批次及其 Blocked 状态保持；本条仅更新排期与依赖。
