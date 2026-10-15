# v04-ringo-security/06：离线集成与全量覆盖核查

Ticket ID: v04-ringo-security/06
Package: [v04-security/01：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Core scenarios: RS01 至 RS10 的当前版本适用部分
Type: 评测
Owner: Ringo
Directory: evals/security/
Status: blocked
Blocked by: [v04-ringo-security/01：覆盖缺口及冲突用例修订](01-coverage-and-case-revision.md)、[03：检测与攻击观察评测接入](03-attack-observers-and-adapters.md)、[04：明细导出通知口径回归](04-details-export-regression.md)；/05 是否为必需前置以 #133 结论为准
Source issue: #86 / #88（[#86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)、[#88](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)）
Verification: 先跑核心实例及现有结构/适配器测试，必要问题修复后复验受影响路径，再运行完整适用离线计划。逐轮核对断言与银行记录，独立校验规模和报告指纹；本票不调用付费模型。

## 交付结果

核心路径就绪即联调，核心检查通过后执行当前范围完整离线覆盖，形成可追踪报告及仍缺能力的清单。

## 验收条件

- [ ] 每条已就绪核心路径先联调，再做阶段全量；跨目录缺陷回归所属 owner 修复。
- [ ] 所有适用用例均进入计划，未接入适配或缺观察如实标 Blocked；当前阶段不适用项有版本依据。
- [ ] 资金相关场景分别核对确认/验证前提交、原操作查询和最终副作用。
- [ ] 重新核对逐功能及异常类型覆盖，修订当前索引与数量，历史报告保持。
- [ ] 运行先写仓库外唯一新路径，再按指南归档报告并登记解压后内容 sha256。
- [ ] 报告记录代码、数据及评测器版本；Passed、Failed、Blocked、NotRun 与 PENDING_SPEC 分别统计。

## 实施边界

本票只修改 Directory 指定目录。开发或编写运行代码时使用 implement；有代码时按 code-review 分别核对仓库规范与本票要求，实际测试和本人批准分别记录。纯文档按仓库例外做内容检查；代码和执行配置走独立 PR 及必要验证。

本票在 2026-10-15 随已确认的七项拆分建立。当前未开始实施，最终交付以本票实际证据为准。

## Comments

- 2026-10-15：Ringo 本人在本会话确认测试边界及七项拆票。接票执行前补实际领取时间与状态；本条不作为已执行或验收通过的记录。
