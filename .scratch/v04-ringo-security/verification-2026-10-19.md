# Ringo 安全任务执行记录（2026-10-19）

## 当前结论

本轮按最新仓库任务逐项做离线交付，真实模型另行确认，实际调用0次。共提交五个代码/评测PR，两个依赖交Erwin；代码提交、AI审查、真人批准及最终合并分别记录。当前安全整体验收仍Unverified，#86/#88保持开放。

| 工作 | 交付与实际证据 | 当前状态 |
|---|---|---|
| 账单读边界，票08 / #137 | [PR #149](https://github.com/DrErwin/hackerthon-bank-agent/pull/149)，安全100 passed，完整后端751 passed，新head fad93a3 CI成功 | 待真人批准及合并，账单原文审计整改仍沿#145 |
| 覆盖扩充及B18，票01 / #88 | [PR #159](https://github.com/DrErwin/hackerthon-bank-agent/pull/159)，137/289/345，新增15主例，56回归通过，345行20 Passed / 0 Failed / 325 Blocked，CI成功 | 设计及局部探针已交付，B18整例与新增场景适配仍有缺口 |
| 导出回归，票04 | [Draft #162](https://github.com/DrErwin/hackerthon-bank-agent/pull/162)，18项14 Passed / 4 Failed，报告器5测试通过，CI成功 | CSV失败交[Issue #161](https://github.com/DrErwin/hackerthon-bank-agent/issues/161)，保留失败，修复后另批复验 |
| MAT改编，票05 | [Draft #163](https://github.com/DrErwin/hackerthon-bank-agent/pull/163)，5参数追加11行，137/294/356，64测试通过，MAT11轮整体Blocked，CI成功 | 依赖#159分支；真实检测和间接入口观察未齐 |
| 声明漂移加固，票09 / #164 | [Draft #165](https://github.com/DrErwin/hackerthon-bank-agent/pull/165)，安全/订阅/API定向288 passed；本提交CI完整后端897 passed及模拟银行评测14 passed，两轴遗留0 | 依赖#149分支，前置合入后重基main；真人批准另记 |

## 阶段全量及限制

固定数据的当前356行完整计划为20 Passed / 0 Failed / 336 Blocked / 0 NotRun / 0 PENDING_SPEC；原报告解压sha256为C26D3C03C46854ABAA4C55EDA98C50416998B292B6071734BBDE4E6A4D630156。MAT专项11轮全Blocked，解压指纹120C4F3A472D338D981DE9CD1C130F988EB3B9688F6AFA137FDA800C5135DCC4。原345行、330行等历史批次保持。

两项聊天MAT有真实HTTP到固定规划器的传输及零资金副作用局部断言，原确认保持；缺实际模型或检测器证据，整例仍Blocked。间接入口三项5轮尚未送达，明确payload_delivered=false。当前全量适配器尚未覆盖导出专项的CSV缺陷，专项4 Failed独立保留，不能用全量0 Failed掩盖。

该356行批次使用main ecf90d0加PR #149的后端快照、评测本地提交06744e4，早于票09的新加固，未据此宣称最新全部组合验收通过。54行已采集metadata的评测器及数据哈希与固定文件逐项比对0差异。QA父根缺完整Git对象，报告code_revision unavailable及运行内来源校验false如实保留；七份冻结来源另经GitHub连接器核对匹配。完整来源说明和gzip原始JSON在各PR的evals/security/evidence/2026-10-19/。

## 发现与返修

1. 票01两轴初审发现M010孤立预期、D010重复例及跨run序号假设，均已修正；最终遗留0。
2. 票04补ready明细的U2越权下载对照，修报告器setup skip漏计，原始17项及最终18项证据分别保留；CSV四类公式型单元格缺陷交#161。
3. 票05修中断work目录复用及manifest旧措辞，现独占创建工作目录；模板按case/variant顺序展开，live计划的gated数量更新为13实例39轮。
4. 补审已合入PR #150发现可变声明自比绕过，转账同类路径一并修复。订阅六条及转账六条固定原值，与#149账单三条组合后十五条独立，业务规则变化0。新增146实例由两位审查者分别复跑通过。缺口、测试准备修正与实际加固分别记录于#164和PR #165。

## 依赖和待办

- [#160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)归Erwin：原始请求与动作/环境事实的可信读取及生产装配。票02的识别实现、票03观察端和全量转正也仍待交付，依赖单不代表仅剩一处接线。
- [#161](https://github.com/DrErwin/hackerthon-bank-agent/issues/161)归Erwin：CSV文本单元格处理，完成后复跑#162并保留首次Failed。
- #163以#159分支为base，#165以#149分支为base。前置合入后须重基main及重新检查CI，未自动合并。
- #145账单审计整改沿原Owner；前端#142的提供方整改及页面安全审查另待公开路径就绪。
- 本轮依用户确认仅离线，真实模型入口及预算另行确认。真人专业批准与联合验收仍按门槛实际记录，飞书未同步。

## 本机全量的单次回归异常

票09本机Python3.13.5完整后端一次为896 passed / 1 failed（453.23s），失败位于app/services/test_bank.py:141：原操作已查得成功后，同号重放在20ms超时预算下返回QueryFailure。随即单例1 passed及test_bank.py全9 passed；相同head的Linux/Python3.12 CI完整897 passed及模拟银行14 passed。已建[Issue #166](https://github.com/DrErwin/hackerthon-bank-agent/issues/166)交Erwin归因，环境调度开销仅为假设，尚未稳定复现。首次失败中末尾单流水断言未执行，未据此推定其已验证。CI通过与本机异常分别保留，未把单次失败删除或笼统记成全绿。

## 环境

GitHub连接可读写，命令行Git缺认证，本轮未发起登录或读取用户凭据。源码在隔离QA工作副本按固定提交取得；远端只发布明确归属的路径。主机Python3.13.5定向验证，最新PR #165的GitHub Actions使用Python3.12完成完整后端897项及模拟银行评测14项，原始日志可由该PR的checks复核。单元测试数量与正式评测分母分别统计。

## Ringo 2026-10-19 后续离线交付

- [PR #162](https://github.com/DrErwin/hackerthon-bank-agent/pull/162)：Issue #161 修复合入后独立复验18 Passed / 0 Failed，报告器5项通过，旧4项Failed保留。新报告sha256为036109E268DB504EA01C85EDEA11F19C452D3436832F0B7E4C1FCC5759D32BD0，台账建立retest_of关联；PR已Ready，精确head e510085的CI成功run39265275458。该专项使用平台L03卡片夹具，真实账单L01-L03另验。
- [PR #169](https://github.com/DrErwin/hackerthon-bank-agent/pull/169)：可信输入规则识别器及正向HIGH终止；29项新增检测测试通过，security与平台输入组合287项通过。精确代码head fb24cfb的GitHub CI后端945 passed、模拟银行14 passed（run39265498469）。双轴初审Standards0/Spec2，返修后各0；未知事实继续未检查，其他部分覆盖保持暂停。依赖PR #165/#149，未自动合并，真人批准另记。
- [PR #170](https://github.com/DrErwin/hackerthon-bank-agent/pull/170)：实际检测器HTTP观察，SEC-T-003/004/005及MAT-FRAUD-01共12轮专项通过，合法对照1项通过；整例12 Blocked，待实际模型和提示复核。evals/security全目录69项通过；聚合返修后专项5项另跑通过。初始断言错误和旧结果保持，最新报告sha256 A74C92FDE599BF7DADD7FF535BFBCACBEDFCE66C799B8FFC1BFC095C499515D8。依赖PR #163/#169，模型调用0次。

### 最新PM决定与未交付边界

main 399a2fe记录Erwin本人决定A：Demo继续固定等级流程对照，真实检测器仅用于离线评测，不采集设备信息；平台v04-risk-inputs/02生产装配deferred至v0.5。本轮交付按此执行，不把未接演示写成检测失败，也不声称演示具备真实识别。180天历史窗口和金额2倍阈值仍待PM确认，检测器未使用usual生成低风险信号。

四类攻击的其他入口及全集离线适配仍按实际观察证据推进；工具备注、不可信资料、记忆实际模型载入缺口保持。现有137/294/356计划及20P/336B历史报告不因本专项自动改写。真实模型和页面补验遵用户决定另行确认；合入与真人签核由责任人分别完成。以上为已提交及离线证据，整体安全验收保持未完成。
