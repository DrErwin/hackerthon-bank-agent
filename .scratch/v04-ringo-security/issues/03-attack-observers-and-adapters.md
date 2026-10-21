# v04-ringo-security/03：检测与攻击观察评测接入

Ticket ID: v04-ringo-security/03
Package: [v04-security/01：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Core scenarios: RS01、RS04、RS05、RS10
Type: 开发
Owner: Ringo
Directory: evals/security/
Status: in_progress（观察端 #170 已合；2026-10-21 S2 #212 补三类观察入口；真实模型/页面证据待联调）
Blocked by: [v04-ringo-security/02：真实风险识别与安全门组合](02-real-risk-detector.md)；33 轮各自所需的资料入口与攻击观察公开能力（提供方按真实缺口登记）
Source issue: #86（[#86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)、[#88](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)）
Verification: 对每类门各运行合法对照和攻击样本，核对实际输入、裁决与工具调用；资金相关实例同时检查独立银行提交/流水。先验证本票，再在所需路径就绪时联调；真实模型执行留到 /07。

## 交付结果

为原 9 轮真实检测、3 轮资料入口及 21 轮攻击观察分别提供可核查的运行与判定，已具备路径及时联调。

## 验收条件

- [ ] 优先复用现有 run_instance、共享轮及公开 API，不新建另一套安全执行器。
- [ ] 三类能力门分别探测及记录；删除静态 gate 标记不作为能力交付证据。
- [ ] 实际请求到达检测器及必要模型/工具边界，判定与银行副作用有独立观察。
- [ ] 跨用户拒绝保持资源存在性隐私；工具返回注入不能改变权限与确认规则。
- [ ] 隔离资料和受控观察不能扩展成真实 Shell 或任意外发能力；缺失时记 Blocked 并标提供方。
- [ ] 已完成适配路径先局部验证，未满足前置的轮次不提前转 Passed。

## 实施边界

本票只修改 Directory 指定目录。开发或编写运行代码时使用 implement；有代码时按 code-review 分别核对仓库规范与本票要求，实际测试和本人批准分别记录。纯文档按仓库例外做内容检查；代码和执行配置走独立 PR 及必要验证。

本票在 2026-10-15 随已确认的七项拆分建立。历史建立时尚未实施，当前结果以本票Comments及关联PR为准。

## Comments

- 2026-10-15：Ringo 本人在本会话确认测试边界及七项拆票。接票执行前补实际领取时间与状态；本条不作为已执行或验收通过的记录。

- 2026-10-19：[Issue #86 最新 PM 排期结论](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)撤回 10-18 的延期决定，本票保留在 v0.4。分母随实际用例变更重算，旧批次及其 Blocked 状态保持；本条仅更新排期与依赖。

- 2026-10-19 实施记录：MAT参数的实际聊天传输局部观察已由PR #163提供，工具备注、资料外发及记忆载入端仍缺，5轮明确payload_delivered=false。检测器输入接线依赖#160，其他观察按本票提供方推进；固定ReplyOnly与风险夹具不替代实际攻击观察。

## Ringo 2026-10-19 后续离线交付

- [PR #162](https://github.com/DrErwin/hackerthon-bank-agent/pull/162)：Issue #161 修复合入后独立复验18 Passed / 0 Failed，报告器5项通过，旧4项Failed保留。新报告sha256为036109E268DB504EA01C85EDEA11F19C452D3436832F0B7E4C1FCC5759D32BD0，台账建立retest_of关联；PR已Ready，精确head e510085的CI成功run39265275458。该专项使用平台L03卡片夹具，真实账单L01-L03另验。
- [PR #169](https://github.com/DrErwin/hackerthon-bank-agent/pull/169)：可信输入规则识别器及正向HIGH终止；29项新增检测测试通过，security与平台输入组合287项通过。精确代码head fb24cfb的GitHub CI后端945 passed、模拟银行14 passed（run39265498469）。双轴初审Standards0/Spec2，返修后各0；未知事实继续未检查，其他部分覆盖保持暂停。依赖PR #165/#149，未自动合并，真人批准另记。
- [PR #170](https://github.com/DrErwin/hackerthon-bank-agent/pull/170)：实际检测器HTTP观察，SEC-T-003/004/005及MAT-FRAUD-01共12轮专项通过，合法对照1项通过；整例12 Blocked，待实际模型和提示复核。evals/security全目录69项通过；聚合返修后专项5项另跑通过。初始断言错误和旧结果保持，最新报告sha256 A74C92FDE599BF7DADD7FF535BFBCACBEDFCE66C799B8FFC1BFC095C499515D8。依赖PR #163/#169，模型调用0次。

### 最新PM决定与未交付边界

main 399a2fe记录Erwin本人决定A：Demo继续固定等级流程对照，真实检测器仅用于离线评测，不采集设备信息；平台v04-risk-inputs/02生产装配deferred至v0.5。本轮交付按此执行，不把未接演示写成检测失败，也不声称演示具备真实识别。180天历史窗口和金额2倍阈值仍待PM确认，检测器未使用usual生成低风险信号。

四类攻击的其他入口及全集离线适配仍按实际观察证据推进；工具备注、不可信资料、记忆实际模型载入缺口保持。现有137/294/356计划及20P/336B历史报告不因本专项自动改写。真实模型和页面补验遵用户决定另行确认；合入与真人签核由责任人分别完成。以上为已提交及离线证据，整体安全验收保持未完成。
