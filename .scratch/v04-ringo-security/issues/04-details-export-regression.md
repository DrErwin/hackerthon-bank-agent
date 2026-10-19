# v04-ringo-security/04：明细导出通知口径回归

Ticket ID: v04-ringo-security/04
Package: [v04-security/01：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Core scenarios: RS08，关联 RS04 和 RS09
Type: 开发
Owner: Ringo
Directory: evals/security/
Status: blocked（回归已交付，CSV实际缺陷及真实L03链路待复验）
Blocked by: [Issue #161：CSV单元格安全处理](https://github.com/DrErwin/hackerthon-bank-agent/issues/161)（Erwin）；真实账单L01至L03按业务前置另验
Source issue: #86 平台完成通知（[#86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)、[#88](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)）
Verification: 通过现有公开端点验证生成、查询和下载，使用两个合成用户及会话切换对照；核对挑战和导出状态，扫描可见出口。平台夹具验证和真实账单端到端分别记录。

## 交付结果

核对平台通知的明细导出授权、验证及下载行为，将实际已具备的公开路径接入安全回归。

## 验收条件

- [x] 先核对已有平台回归并复用其可引用证据；明确本票补充的安全断言，避免复制平行测试。
- [x] 卡片普通导出与明细敏感导出分别测试，生成前所需验证有效且与导出任务关联。
- [x] 下载分别验证本人归属、当前会话及本次授权；会话变化后旧授权失效。
- [x] 同会话有效授权下的再次下载遵循契约复用，不能自行新增每次重验的业务要求。
- [ ] 验证码原文不进入模型、事件、日志和评测报告；导出内容按契约脱敏并核对 CSV/HTML 安全处理。
- [ ] 涉及现行实现缺陷时先保留复现，目录外修复交 owner；真实账单链路缺失仍单独标 Blocked。

## 实施边界

本票只修改 Directory 指定目录。开发或编写运行代码时使用 implement；有代码时按 code-review 分别核对仓库规范与本票要求，实际测试和本人批准分别记录。纯文档按仓库例外做内容检查；代码和执行配置走独立 PR 及必要验证。

本票在 2026-10-15 随已确认的七项拆分建立。历史建立时尚未实施，当前结果以本票Comments及关联PR为准。

## Comments

- 2026-10-15：Ringo 本人在本会话确认测试边界及七项拆票。接票执行前补实际领取时间与状态；本条不作为已执行或验收通过的记录。

- 2026-10-19 实施记录：[Draft PR #162](https://github.com/DrErwin/hackerthon-bank-agent/pull/162)已提交且CI成功。复用10项平台测试，补8实例，最终14 Passed / 4 Failed；4条CSV公式型文本缺陷交#161，失败保留。新增ready明细U2下载拒绝及本人对照均通过，报告器5项单元测试通过。授权/风险及L03卡片为受控夹具，真实账单端到端另验；CI成功不代替专项Failed修复。

- Erwin已接单并建立[v04-platform/13](../../v04-platform/issues/13-csv-formula-cell-export.md)，当前in_progress；本票待其实现后另批复验，历史Failed保持。
