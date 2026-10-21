# v04-ringo-security/02：真实风险识别与安全门组合

Ticket ID: v04-ringo-security/02
Package: [v04-security/01：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Core scenarios: RS01、RS02、RS03、RS06；执行与检测证据分别验证
Type: 开发
Owner: Ringo
Directory: backend/app/security/
Status: in_progress（离线检测器 #169 已合；三档结论见 evals/security/offline-2026-10-21-closeout.md；真实模型/页面待 Erwin 联调，演示装配按 PM 决定 A 挂 v0.5）
Blocked by: PR #165/#149合入与专业批准；真实低/中风险事实不足，离线部分证据已交；演示接线按PM决定A延期而非本期阻塞
Source issue: #86（[#86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)、[#88](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)）
Verification: 在本目录测试判定输入对照及既有安全门外部行为；观察裁决与实际执行次数，覆盖确认后参数变化和高风险终止恢复。先跑受影响测试，再按影响检查安全目录；联合入口与独立银行事实由 /03 验证。

## 交付结果

从真实请求及可信动作事实形成有来源的风险判定，复用既有安全门，既定高风险终止与确认/验证流程继续生效。

## 验收条件

- [x] 实施前核对原始请求及动作事实的现有受控读取入口，记录可用接口与证据；确需改 API 或底座时交 Erwin 单独实施。
- [ ] 输出含可追踪的策略版本、命中规则及脱敏证据，并能在真实安全裁决中观察。
- [ ] 固定等级夹具只用于流程对照，真实识别验证必须从实际输入产生判定。
- [ ] 按既定 PRD 验证低、中、高三档与合法对照；必要事实缺失时沿现有暂停语义处理。
- [ ] 高风险任务零资金提交，确认或恢复无法继续同一终止任务；合法低/中风险遵循原确认及验证门。
- [ ] 所需运行接线未完成时保留相应依赖，不把本目录单元测试记成整体接入完成。

## 实施边界

本票只修改 Directory 指定目录。开发或编写运行代码时使用 implement；有代码时按 code-review 分别核对仓库规范与本票要求，实际测试和本人批准分别记录。纯文档按仓库例外做内容检查；代码和执行配置走独立 PR 及必要验证。

本票在 2026-10-15 随已确认的七项拆分建立。历史建立时尚未实施，当前结果以本票Comments及关联PR为准。

## Comments

- 2026-10-15：Ringo 本人在本会话确认测试边界及七项拆票。接票执行前补实际领取时间与状态；本条不作为已执行或验收通过的记录。

- 2026-10-19：[Issue #86 最新 PM 排期结论](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)撤回 10-18 的延期决定，本票保留在 v0.4。分母随实际用例变更重算，旧批次及其 Blocked 状态保持；本条仅更新排期与依赖。

- 2026-10-19 实施记录：已核对main ecf90d0：风险回调存在，转账运行装配仍匹配transfer_fixtures；API原文已有存储，缺按可信主体、会话、任务、动作关联的受控读取路径。该目录外依赖已交Erwin，不通过SQL直读或固定等级冒充真实识别。未知设备/金额基线不自行判低；本票未据依赖单视为检测器已完成。

- Erwin已建立[v04-risk-inputs/01](../../v04-risk-inputs/issues/01-risk-input-read-path.md)及[02](../../v04-risk-inputs/issues/02-detector-assembly-and-fixture-removal.md)。当前是接缝规格和实施票，未据此认定接缝已可运行。180天历史窗口、2倍单笔最大等默认口径在提供方规格中仍待PM确认，本票未将其当冻结业务规则；unknown事实与checked_signals的映射需在接入时明确。

## Ringo 2026-10-19 后续离线交付

- [PR #162](https://github.com/DrErwin/hackerthon-bank-agent/pull/162)：Issue #161 修复合入后独立复验18 Passed / 0 Failed，报告器5项通过，旧4项Failed保留。新报告sha256为036109E268DB504EA01C85EDEA11F19C452D3436832F0B7E4C1FCC5759D32BD0，台账建立retest_of关联；PR已Ready，精确head e510085的CI成功run39265275458。该专项使用平台L03卡片夹具，真实账单L01-L03另验。
- [PR #169](https://github.com/DrErwin/hackerthon-bank-agent/pull/169)：可信输入规则识别器及正向HIGH终止；29项新增检测测试通过，security与平台输入组合287项通过。精确代码head fb24cfb的GitHub CI后端945 passed、模拟银行14 passed（run39265498469）。双轴初审Standards0/Spec2，返修后各0；未知事实继续未检查，其他部分覆盖保持暂停。依赖PR #165/#149，未自动合并，真人批准另记。
- [PR #170](https://github.com/DrErwin/hackerthon-bank-agent/pull/170)：实际检测器HTTP观察，SEC-T-003/004/005及MAT-FRAUD-01共12轮专项通过，合法对照1项通过；整例12 Blocked，待实际模型和提示复核。evals/security全目录69项通过；聚合返修后专项5项另跑通过。初始断言错误和旧结果保持，最新报告sha256 A74C92FDE599BF7DADD7FF535BFBCACBEDFCE66C799B8FFC1BFC095C499515D8。依赖PR #163/#169，模型调用0次。

### 最新PM决定与未交付边界

main 399a2fe记录Erwin本人决定A：Demo继续固定等级流程对照，真实检测器仅用于离线评测，不采集设备信息；平台v04-risk-inputs/02生产装配deferred至v0.5。本轮交付按此执行，不把未接演示写成检测失败，也不声称演示具备真实识别。180天历史窗口和金额2倍阈值仍待PM确认，检测器未使用usual生成低风险信号。

四类攻击的其他入口及全集离线适配仍按实际观察证据推进；工具备注、不可信资料、记忆实际模型载入缺口保持。现有137/294/356计划及20P/336B历史报告不因本专项自动改写。真实模型和页面补验遵用户决定另行确认；合入与真人签核由责任人分别完成。以上为已提交及离线证据，整体安全验收保持未完成。
