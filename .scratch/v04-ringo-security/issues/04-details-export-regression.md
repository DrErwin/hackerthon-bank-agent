# v04-ringo-security/04：明细导出通知口径回归

Ticket ID: v04-ringo-security/04
Package: [v04-security/01：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Core scenarios: RS08，关联 RS04 和 RS09
Type: 开发
Owner: Ringo
Directory: evals/security/
Status: resolved（#162 合入；18 项独立复验通过；整体真实账单验收另列）
Blocked by: PR #162审阅与合入；原CSV缺陷已修复且独立复验通过，真实账单L01-L03由场景验收补齐
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

## Ringo 2026-10-19 后续离线交付

- [PR #162](https://github.com/DrErwin/hackerthon-bank-agent/pull/162)：Issue #161 修复合入后独立复验18 Passed / 0 Failed，报告器5项通过，旧4项Failed保留。新报告sha256为036109E268DB504EA01C85EDEA11F19C452D3436832F0B7E4C1FCC5759D32BD0，台账建立retest_of关联；PR已Ready，精确head e510085的CI成功run39265275458。该专项使用平台L03卡片夹具，真实账单L01-L03另验。
- [PR #169](https://github.com/DrErwin/hackerthon-bank-agent/pull/169)：可信输入规则识别器及正向HIGH终止；29项新增检测测试通过，security与平台输入组合287项通过。精确代码head fb24cfb的GitHub CI后端945 passed、模拟银行14 passed（run39265498469）。双轴初审Standards0/Spec2，返修后各0；未知事实继续未检查，其他部分覆盖保持暂停。依赖PR #165/#149，未自动合并，真人批准另记。
- [PR #170](https://github.com/DrErwin/hackerthon-bank-agent/pull/170)：实际检测器HTTP观察，SEC-T-003/004/005及MAT-FRAUD-01共12轮专项通过，合法对照1项通过；整例12 Blocked，待实际模型和提示复核。evals/security全目录69项通过；聚合返修后专项5项另跑通过。初始断言错误和旧结果保持，最新报告sha256 A74C92FDE599BF7DADD7FF535BFBCACBEDFCE66C799B8FFC1BFC095C499515D8。依赖PR #163/#169，模型调用0次。

### 最新PM决定与未交付边界

main 399a2fe记录Erwin本人决定A：Demo继续固定等级流程对照，真实检测器仅用于离线评测，不采集设备信息；平台v04-risk-inputs/02生产装配deferred至v0.5。本轮交付按此执行，不把未接演示写成检测失败，也不声称演示具备真实识别。180天历史窗口和金额2倍阈值仍待PM确认，检测器未使用usual生成低风险信号。

四类攻击的其他入口及全集离线适配仍按实际观察证据推进；工具备注、不可信资料、记忆实际模型载入缺口保持。现有137/294/356计划及20P/336B历史报告不因本专项自动改写。真实模型和页面补验遵用户决定另行确认；合入与真人签核由责任人分别完成。以上为已提交及离线证据，整体安全验收保持未完成。
