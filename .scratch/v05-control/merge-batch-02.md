# 第二批优先合入材料（2026-10-25）

Status: merged — Erwin于2026-10-25明确批准本批五项及CI计费本地验证例外；298→284→292→295→297已依次实际squash合入，最终代码main为2a070b9。五项新head的CI均计费未启动，未记绿；合入不等于E2E或最终接受。

本批选择五个已有PR，目的是让减支场景开始真实E2E，并让预算专用输入的API接线开工。它们补齐真实账单入口、隔离案例、养老金入账/本人账户选择以及预算输入来源；不是整版验收，也不改变风险信息不足时暂停办理的规则。

## 已批准范围与顺序（原候选版本）

| 顺序 / PR | 实施票与单目录 | 业务结果 | 精确候选head |
|---|---|---|---|
| 1 / [298](https://github.com/DrErwin/hackerthon-bank-agent/pull/298) | [v05-budget-adoption-origin/01](https://github.com/DrErwin/hackerthon-bank-agent/blob/5ebc1332d958f08e1900ab19cfb6815e737384d6/.scratch/v05-budget-adoption-origin/issues/01-platform-origin.md)；agent_platform | 保留用户在专用入口针对哪份预算候选提交了什么；模型普通回答不能伪造该来源 | `5ebc1332d958f08e1900ab19cfb6815e737384d6` |
| 2 / [284](https://github.com/DrErwin/hackerthon-bank-agent/pull/284) | [v05-bills-cross-input/01](https://github.com/DrErwin/hackerthon-bank-agent/blob/198586a7c149da886f81e36f125cc29031c51b02/.scratch/v05-bills-cross-input/issues/01-typed-input.md)；modules/bills | 联动能通过已声明的输入取得真实账单依据 | `198586a7c149da886f81e36f125cc29031c51b02` |
| 3 / [292](https://github.com/DrErwin/hackerthon-bank-agent/pull/292) | [v05-cross-platform/13](https://github.com/DrErwin/hackerthon-bank-agent/blob/6f0a56de3ca1f58ace98703f5d5555b9c0585af9/.scratch/v05-cross-platform/issues/13-bills-success-integration-proof.md)；agent_platform | 修正旧失败预期，核对真实账单范围、金额与来源 | `6f0a56de3ca1f58ace98703f5d5555b9c0585af9` |
| 4 / [295](https://github.com/DrErwin/hackerthon-bank-agent/pull/295) | [v05-cross-e2e/01的数据准备增量](https://github.com/DrErwin/hackerthon-bank-agent/blob/3a76ae2885e4e52df30a55669a2b5e3e70882b2b/.scratch/v05-cross-e2e/issues/01-expense-reduction-e2e.md)；evals/cross | 用独立案例库验证减支/养老金，保留失败批次与已办结果，不补造风险事实 | `3a76ae2885e4e52df30a55669a2b5e3e70882b2b` |
| 5 / [297](https://github.com/DrErwin/hackerthon-bank-agent/pull/297) | [v05-cross-business/07](https://github.com/DrErwin/hackerthon-bank-agent/blob/9e25a8f010c86e6e7f83bd9f63e26fce83ab1c48/.scratch/v05-cross-business/issues/07-pension-income-and-own-destination.md)；modules/cross | 选择真实养老金入账和本人储蓄账户，保留家人去向及原安全门 | `9e25a8f010c86e6e7f83bd9f63e26fce83ab1c48` |

硬依赖：284先于292；284/292是297真实账单组合的前置。292目前以284分支为base，前序squash后仅保留292自身补丁，不能把284重复合入。其余均以main为base；每项仍单目录、独立PR及squash记录。

本次申请只覆盖上述五项及其等价同步：批准后逐项同步最新main，记录最终head，核对受审补丁和运行树；若出现新业务代码、未解决冲突或验证失败，先暂停该项、修复复审并更新材料，不把批准扩成任意改动许可。

## 已核对的验证层级

| 层级 | 已有实际结果 | 使用边界 |
|---|---|---|
| 298独立分支完整后端 | 固定4f18247：1752通过、0失败/错误/跳过；最终5ebc133仅补证据。中控直接核对JUnit、退出码及日志/报告哈希 | 不是本批五项共同全量；平台来源业务使用明确的持久stand-in，不代表真实采用预算 |
| 284账单与292装配 | 账单353、本票18；292真实装配及入口21。两票各自双轴PASS、必须项闭合 | 原1603P/3F全量失败保留；旧断言由292处理，原网关超时及后续503不凭单跑通过宣称修好 |
| 295隔离数据 | 10通过；两批实际准备/运行时启动和银行回读，银行操作0 | 无真实模型、业务HTTP或页面E2E；数据工具不修改风险判定 |
| 297主线同步 | 70通过、Spec独立2通过；README/manifest冲突已由作者解决，生日与养老金能力均保留；两轴无必须项 | 养老金首笔仍因安全事实不足暂停，第二笔未派发；2500/1000是计划，未写成已转出 |
| 原四项组合 | 284/292/295/297，固定28d941a基线及b1c06a1代码：82+1通过，独立两轴0必须项；中控核对原始XML和哈希 | 证据材料8367cd9；是实际同版本定向，未跑整套后端或页面E2E |
| 本批五项共同组合 | main608255f + 五项自身补丁，受测0aed529：主组155、养老金探针1，共156个唯一节点通过；两轴PASS、0必须项。中控直接核对XML/哈希与受测到材料提交运行树零差异 | 是本批实际同版本定向，未再跑全量；不借用含293/296等其他候选的160项成绩，也不把各分支成绩相加 |

每个原PR的独立Standards/Spec审查均已有记录；最终文档head与受审运行代码的关系已核对。组合审查另核对来源去重、实际导入目录、原始报告、零新增转账和结论边界。

五项组合完整材料：本地提交`37fb62f`的`.scratch/v05-bills-cross-input/research/batch-02-five-pr-readiness.md`，工作区`C:/Users/57652/.codex/worktrees/v05-batch02-readiness/hackerthon-bank-agent`，分支`codex/v05-batch02-five-pr`；未推送混合目录代码。受测head=`0aed529dfff0a4e557bb66340370bea51632a769`，backend tree=`83b766fd3c15bec6939511049ec4b8ef1e3adb3c`，evals tree=`977ce1d074c6fcd0eee18f4039bda0c191b6b6ba`。原四项报告与分支8367cd9保持原样。

原始本机报告在`C:/Users/57652/AppData/Local/Temp/bank-five-pr-51c8e5a6/`：targeted.xml 155/0/0/0、SHA256=`84f8c1dd9426477be6ae9e99924b684116aaf92b8b757032230b6458a161c7c9`；pension.xml 1/0/0/0、SHA256=`3ce116bf6aaa9b1fac20dd193f855d87d3358d7288a378d3fa44d25fd0114efb`。中控独立解析两个XML，按classname/name去重确认为156个唯一节点；未将原四项83重复计入。日志、实际导入路径、独立临时库和命令由原组合材料索引，未复制凭据或数据库。

原503本轮相关定向未复现，真实根因仍未定。[恢复诊断检查点](recovery-503-checkpoint.md)保留原1603P/1F/2setupError、观察工具干扰1604P/2F及修正观察后的1606通过三层证据；不把任何后续通过改写成原产品缺陷已修复。

## CI与本批所需批准

中控于本轮直接读取以下精确head的检查与注释：五项均因GitHub账户付款/支出额度导致job未启动，无远端测试执行证据，记 **CI Blocked**。没有重跑CI，也不记绿灯。

| PR | 最终head对应检查 |
|---|---|
| 298 | [40177710551 / 121121899661](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40177710551/job/121121899661) |
| 284 | [40167516712 / 121091499442](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40167516712/job/121091499442) |
| 292 | [40168840592 / 121095366167](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40168840592/job/121095366167) |
| 295 | [40169072679 / 121096041887](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40169072679/job/121096041887) |
| 297 | [40177249180 / 121120506315](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40177249180/job/121120506315) |

原申请已获Erwin明确回复：按以上顺序合入，并**仅对本批**采用已记录的本地验证作为计费故障期间的合入依据，CI仍记Blocked。此为第二批自身批准，没有移用首批例外。批准来源遵循[Review与合并原则](../../docs/principles/03-review-and-merge.md)及根AGENTS本阶段Erwin本人审查规则；AI审查不代签真人。

## 合入后可推进与继续保留

- 298稳定合入后，给原来源/存储对话API02的明确开始信号；cross06继续等API02、293采用存储及真实来源。
- 账单/装配/隔离数据合入后，续派真实页面→模型→HTTP→银行的E2E01减支。E2E02养老金随后推进，但已知风险事实不足仍需如实暂停，不靠改夹具让资金通过。
- 本批不含293，不升级共享应用库；不含291、296、294、290，不关闭安全/银行专项；这些候选与五项支撑160通过另行排队。293原1607历史工具输出及v6回退边界已补齐并双轴复核，未找到当时独立JUnit/日志，不把新摘录当成原测试报告；共享库升级前提仍待后续具体裁定。
- #160多样输入/自然对话仍在讨论，不授权新的未知放行规则；#216/#227、生日页面走查及最终安全/体验接受不自动关闭。
- 生日页面02已在独立worktree盘点，工具审批与页面批准分开；数量调整缺口已交原cross对话只读核查/最小拆票，不在本批临时加入实现。

## 申请与实际合入记录

Erwin于2026-10-25对本对话第二批问题卡明确回复：**“批准本批五项及CI例外（推荐）”**。批准范围为#298→#284→#292→#295→#297及其等价同步，按已记录本地验证合入，CI仍记Blocked；不含#293等其他PR、共享数据库升级、#160新政策或最终安全/体验/E2E接受。不再重复请求本批批准。

五项作者均在干净独立worktree顺序同步最新main，原提交range-diff全部等价，仅追加各自准备记录；使用明确旧head的force-with-lease更新原PR。中控复核准确目录差异、新head计费注释并以expected_head_sha逐项squash；292仅移植自身3提交，未重复284祖先，base已改main。五项均已从远端元数据核实merged=true。

| PR | 最终合入head | 实际squash提交 | 最终head检查 |
|---|---|---|---|
| 298 | `7670c8f1cc217c27aa2280dbfeb899b4f61d77b3` | `6ce7fb03a3765df00773885953151619c43f52c7` | [CI计费未启动](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40184895685/job/121143509746) |
| 284 | `6ae4f4a56dee7d8c57bb78ffe08134e0c8753aa3` | `4d9bd5774461e177b0289a80a9c00663386fa34b` | [CI计费未启动](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40185244819/job/121144547831) |
| 292 | `7a43d4f9c7a4b7797db62c202062fe8d584688de` | `e402bc4d6c4a70be8082fb4b79cbd77b483e2dc2` | [CI计费未启动](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40185488889/job/121145275952) |
| 295 | `ba023807a4baf510293567adaac06314840d0b26` | `3239fd75417e8f1e47aea0c0db83d734cdfffe6c` | [CI计费未启动](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40185840929/job/121146318571) |
| 297 | `b1e9486106c5eed8de076a2c51650bfc861edc59` | `2a070b9cf992a109d8b54718a49dc3e3b56bd236` | [CI计费未启动](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40186132694/job/121147180497) |

**合入后核对**：main `2a070b9cf992a109d8b54718a49dc3e3b56bd236` 的backend/evals/frontend/tools/.github以及养老金组合探针与受测 `0aed529dfff0a4e557bb66340370bea51632a769` 零差异。backend tree仍为 `83b766fd3c15bec6939511049ec4b8ef1e3adb3c`，evals tree仍为 `977ce1d074c6fcd0eee18f4039bda0c191b6b6ba`。因此沿用既有156唯一节点与双轴结果，不重复跑相同测试、全量或503诊断；这是运行代码等价核对，不是新测试批或页面E2E。

**已发下游开始信号**：原来源/存储对话已开始 `v05-budget-adoption-origin/02` 的API实现；原E2E对话已开始 `v05-cross-e2e/01` 的真实页面/模型/HTTP/隔离银行实跑，先S01再关键变体。新API代码、实际E2E结果和后续养老金/生日路径各自回交，不由本批合入代验收。293/296/294/291/290及生日新语义没有纳入批准。
