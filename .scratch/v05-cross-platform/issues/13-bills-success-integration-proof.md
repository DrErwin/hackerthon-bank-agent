# 13：联动账单成功后的真实事实组合断言

Ticket ID: v05-cross-platform/13

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [公共接缝与模拟银行规格](../spec.md)，沿用[票 05 的真实组合验收](05-cross-runtime-wiring.md)；本票补充如下已授权验证范围。

Type: 开发（集成测试）

Owner: Erwin（v0.5 统一承担）

Directory: `backend/app/agent_platform/`

Status: merged — PR #292 已合入 `e402bc4`；原定向组合及本批 CI 计费例外见[合入记录](../../v05-control/merge-batch-02.md)，不代页面与最终接受。2026-10-29 核对。

Blocked by: None（原前置 [v05-bills-cross-input/01](../../v05-bills-cross-input/issues/01-typed-input.md) / [PR #284](https://github.com/DrErwin/hackerthon-bank-agent/pull/284) 已合入 `4d9bd577`；原隔离组合历史保留）。

Execution assignee: Codex，运行装配遗留线

Accepted by: Erwin 授权 Codex 执行（中控续派）

Accepted at: 2026-10-25

Core scenarios: XL-S01、XL-P01、XL-X07，见[共享规格](../../v05-cross-linkage/spec.md)；本票聚焦减支账单读取组合，不替代页面或真实模型 E2E。

Verification: 在 PR #284 组合上先复现旧断言失败，再验证真实 SpendingSummary 与实际银行 B08 读取结果的金额、来源、scope、对照期一致，父子关系保留、资金零写入；执行完整装配测试文件和账单类型化入口套件。模型为原测试替身，真实安全门/执行器/SQLite/银行；不调用真实模型，不改 services 或账单业务代码。

## 授权与最小规格

2026-10-25 中控明确续派：平台12/PR289先完成审查交付，另开平台后续票解决账单PR284引出的旧断言，不能只改状态期望词。来源为[账单交接](../../v05-bills-cross-input/research/integration-handoff.md)。创建前核对本线12及最新main的01—11，本票使用下一空闲13；不修改总进度/包状态。

现有 `test_real_composition_mounts_cross_and_traces_children` 将旧账单类型化输入缺口的 failed 当预期。PR284已经使真实工厂成功，应验证：

- [x] 账单子任务 succeeded、error=None，结果通过 SpendingSummary 公共模型校验，非占位。
- [x] 主 scope 是本人所选全部账户的上月范围，对照 scope 是相同账户的再前一月；日期采用半开区间。
- [x] 查询确经真实 BankGateway/B08，调用上下文绑定父任务、子任务、用户及轮次；返回的账户来源时点与 summary 匹配。
- [x] 主期交易数、消费/退款/净额、转入转出及对照净额/差额可回核本次银行实际返回的事实；不把硬编码结果或自身服务输出当预期。
- [x] 保留原订阅真实盘点、任务关系和父视图断言；所有本人账户的非种子流水与资金操作数量不增加。
- [x] 本票独立子代理两轴审查后独立PR，依赖284；不自行合并或代签E2E/真人接受。

## Delivery record

- 组合基线：PR284 head `198586a7c149da886f81e36f125cc29031c51b02`；最新main `9a479ea`。独立worktree `v05-platform13-bills-proof`，分支 `codex/v05-platform13-bills-proof`。
- 平台12/PR289不含本票改动；本票也不带平台12或风险决策文档提交。
- 旧断言复现：PR284 head 上原目标用例 **1 failed in 20.08s**，明确 `succeeded != failed`；未将业务修通误报为业务失败。
- 验证：本工作树源码（已核实 bills entry.__file__ 指向本树），复用平台12隔离虚拟环境的解释器，从 `backend/` 执行 `python -m pytest -q app/agent_platform/test_cross_runtime_wiring.py app/modules/bills/test_typed_entry.py --basetemp=<本worktree专属临时目录>`，**21 passed in 16.16s**。使用真实工厂/安全门/执行器/银行和临时SQLite，仅规划器为脚本模型；观察器返回真实B08结果，不造响应。
- 本轮实际结果（只读回查测试留下的SQLite核对）：账户 A1/A5；主期 `[2026-09-01, 2026-10-01)`（+08:00），18 笔，消费586400分、退款4500分、净消费581900分、转出0分、转入821000分；对照期 `[2026-08-01, 2026-09-01)` 同账户，净消费282600分、差额299300分。两个账户各有真实银行来源时点，测试逐项与实际B08返回核对；bank_operations 最终为0。这些只是该隔离种子的观测，断言不硬编码这些金额/笔数。
- 差异空白、改动Python编译、项目链接检查通过。仅变更一个平台测试文件及本票，不改变运行行为；本票按影响范围验证，没有再次跑全后端，也不拿平台12的1591项替代此组合的验证。账单线原全量三失败事实仍保留在原交接（旧平台断言本票已修，两项20ms银行重放不由本票改）。
- 独立 Standards 子代理：PASS，必须修复0、建议0。独立 Spec 子代理：PASS，必须修复0，独立复跑21 passed in 23.98s。非阻塞建议“对照期样本显式非空”已采纳，追加后目标用例 **1 passed in 11.88s**。
- 交付：[PR #292](https://github.com/DrErwin/hackerthon-bank-agent/pull/292)，base=`codex/v05-bills-cross-input`，Draft；前序284合入后须只保留本票提交再更新main，不直接把前序历史作为本票差异。代码提交 `f7a1c3b`、审查增强提交 `05c137f`，后续仅回填证据。未自行合并。
- CI：head `05c137f` 的 [Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40168791897/job/121095223353) 结论failure，注解明确账户付款/spending limit导致job未启动；无执行证据，不代批例外。后续纯文档回填不主动触发/等待新CI。
- Spec 对 `05c137f` 建议采纳复核 PASS、必须项0；未重复无关测试。真实模型/业务HTTP/页面E2E、CI通过、真人安全/PM接受均未由本票完成。
- 下游：随284合入后，旧“账单应failed”的平台回归阻塞解除，可进入减支/养老金真实页面联调；本票自身不表示两主线E2E通过。原交接两项银行20ms短超时遗留不由本票处理。

## 2026-10-25 批准后的PR292仅自身提交同步

- 中控已实际将284 squash合入main4d9bd5774461e177b0289a80a9c00663386fa34b，298亦已合入。本批及CI计费本地验证例外由Erwin批准，不重复申请，不等同CI绿、真人安全签核或版本接受；本对话不自行合并。
- 开工原worktree干净，原292 head6f0a56de3ca1f58ace98703f5d5555b9c0585af9；明确以旧284边界198586a7c149da886f81e36f125cc29031c51b02，执行rebase --onto新main。仅自身f7a1c3b/05c137f/6f0a56d移为fff72c9/8550cd8/22c686c，未重复284祖先或298。票据补本记录前新head22c686c92fb5d0f57f9a2c7262bf429d00364366。
- 旧范围198586a..6f0a56d与新范围4d9bd57..22c686c的range-diff三项均为“=”；完整补丁字节相同，SHA256 `4515c4f88193c3c1c06ca7da1780e6320128403b367b9859bcae2440252b1182`。平台测试文件blob仍为a41e4239e05c56e20dae15c30bed90d3865dedb5，与原292和五项组合受测0aed529相同。
- 差异仅agent_platform/test_cross_runtime_wiring.py及本票；沿用原21项、原Standards/Spec双轴PASS，以及五项组合37fb62f的155+1=156唯一节点通过/双轴0必须项。源码等价，没有新跑测试、全量或503诊断，不借用其他组合160项。
- PR实际base已核对为main；本次保留该base，原Dependent Draft历史仅作旧记录。链接、差异空白与源码等价检查通过。旧组合/失败证据不改写，503根因仍未定。
- 原分支将以明确旧head6f0a56de3ca1f58ace98703f5d5555b9c0585af9的force-with-lease更新，新head CI状态由推送后的PR说明与回交实时记录；计费未启动仍Blocked，本地例外不称CI通过。不改其他PR/票或共享进度。
