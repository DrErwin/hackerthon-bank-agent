# 01：减支核心与关键异常 E2E

Ticket ID: v05-cross-e2e/01

Package: [v05-cross-linkage/packages/05-cross-e2e：三主线 E2E 与全面验收](../../v05-cross-linkage/packages/05-cross-e2e.md)

Spec: [本工作组规格](../spec.md)

Type: 评测

Owner: Erwin（本执行对话代行本票评测）

Directory: `evals/cross/`

Status: blocked — 2026-10-25最新指令暂停真实执行，设计交Erwin后续手工跑；S01原Failed保留，修复合入不触发自动复跑。

Accepted by: Erwin（授权本执行对话）

Accepted at: 2026-10-25

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-S01—S05、相关 X；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

真实页面/模型/HTTP/模拟银行实跑 XL-S，核对签约变化和副作用次数；报告失败、阻塞和相关 X 分支，缺陷回原目录

## Blocked by

- [v05-cross-platform/05：联动主入口及现有业务装配](../../v05-cross-platform/issues/05-cross-runtime-wiring.md)
- [v05-cross-frontend/01：总方案、子确认和结果页面](../../v05-cross-frontend/issues/01-plan-and-child-interactions.md)

- [v05-cross-business/01：减支编排和共用计划骨架](../../v05-cross-business/issues/01-expense-reduction.md)（已合PR #269；账单类型化输入缺口仍由账单线提供修复）
- [v05-cross-platform/11：子任务交互登记与联动文本输入](../../v05-cross-platform/issues/11-child-interaction-and-text-input.md)（PR #281已合）；前端01以PR #283为合入证据，原#282关闭。
- 正式比较数据与签约种子已准备；账单输入PR #284和平台断言PR #292已由中控合入。本轮仅准备PR295合入，真实运行等待独立启动信号，适用风险事实仍须核实。

## Start when

- 最新停止线撤回自动续跑授权。本轮只静态交设计；未来由Erwin自行执行，或经用户明确要求和中控另派后再委派AI。依赖就绪不自动启动。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

当前只交[手工执行设计与缺口](../manual-execution-handoff.md)，不执行下列真实验收。原S01失败和PR300@31e995e及原数据原样保留；本规划完成不关闭本票。

- [ ] XL-S01 从真实页面自然表达贯通真实模型、HTTP 和模拟银行，选定协议实际取消，保留项不变。
- [ ] XL-S02—S05 以及相关共性变体留独立证据：多协议、无签约、反悔、部分成功、未知和恢复。
- [ ] 银行写入次数、任务与回执一致；实际失败/阻塞保留，跨目录缺陷回原票。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。必须执行真实页面 → 真实模型 → HTTP → 隔离模拟银行/生活服务链路；单模块或离线结果不能替代。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 前次Markdown准备8488e3a/61e6687已由中控整合；本次数据代码分支`codex/v05-cross-e2e-01-fixtures`待PR审查合入。
- 实际运行 / 本票完成：blocked，未关闭。
- 局部验证：10 passed，两个独立案例实际prepare和真实运行时构建/银行回读通过；[证据](../../../evals/cross/fixture-validation-2026-10-25.md)。真实模型/HTTP/页面仍未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 8](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

## 2026-10-25 接包与执行细化

01为本分支准备增量，覆盖XL-S01—S05及X适用分支；依赖就绪先跑S01，失败回归属线修复并保留批次。平台11 #281与前端01替代交付#283已合，不再以这两项未合为阻塞。账单入口仍只接受StartTransferInput而cross派发BillSummarizeInput，交账单线（中控已另派；具体新票号待提供）。

运行入口、数据/故障要求见[runbook](../../../evals/cross/runbook.md)；逐场景可观察断言和独立变体见[覆盖映射](../../../evals/cross/coverage-plan.md)；证据字段和归档见[批次模板](../../../evals/cross/batch-template.md)。[当前准备快照](../../../evals/cross/readiness-2026-10-25.md)只证明准备，不是页面或模型结果。总状态由中控维护。

## 2026-10-25 续派：正式案例数据和最小入口

中控续派本票的数据准备增量，代码归属仍仅`evals/cross/`，沿用批准S01/P01，不另立业务规则。分支`codex/v05-cross-e2e-01-fixtures`从main `9a479ea`开始；前次纯文档准备8488e3a/61e6687由中控另行整合。

- [x] 新批次独立播种：完整上月/上上月账单、两取消一保留、5000养老金、本账户A1与储蓄A5/家庭联系人A4可查询。
- [x] 保留源风险事实，不增补signals/checked维度，不造低风险；源库不修改，旧批次不重置。
- [x] 最小prepare/serve入口复用真实运行时，初始化数据与业务输出严格分开；重启保留已办状态和操作。
- [x] 定向10项测试、实际两个案例prepare及规范/规格子代理审查均通过；已提代码PR #295，真实模型/HTTP/页面仍not_run。

详细数据、风险事实归属和接入缺口见[案例数据与入口](../../../evals/cross/fixture-runbook.md)。账单#284及平台旧断言是S01前置；P01还发现既定业务的本人A5去向、入账方向适配缺口，回cross业务线，不以fixture伪造契约或风险覆盖。#160未知维度语义交PM/安全线，本票不修改。此增量完成不关闭原E2E票。

### 本轮代码回交

- [PR #295](https://github.com/DrErwin/hackerthon-bank-agent/pull/295)，分支codex/v05-cross-e2e-01-fixtures，代码提交e166638（原受审提交157d9b5同步最新main fd6cd70后重放，运行代码相同）；审查记录441571f。
- 独立规范轴/规格轴均PASS，各0必须修复，见[审查记录](../review.md)；只证明数据与入口增量。
- CI在441571f批次失败：GitHub检查121095901251明确说明付款失败或spending limit导致job未启动；没有运行测试，记计费blocked，不写CI绿。后续纯记录提交不改变代码验证结论。
- 本PR未合并；中控排队审阅。S01可在账单#284及平台旧断言修复、适用事实就绪后从真实页面开始；P01还需cross侧本人去向/入账方向适配及风险来源核实。原票、包和版本未因局部交付关闭。

## 2026-10-25 第二批批准后的等价合入准备

Erwin已批准第二批298→284→292→295→297及仅本批CI计费本地验证例外，依据中控本次直接续派。前三项实际squash：298=6ce7fb0、284=4d9bd57、292=e402bc4d6c4a70be8082fb4b79cbd77b483e2dc2；本票不自行合并，也不把本批例外扩展到后续交付。

- 原干净head：3a76ae2885e4e52df30a55669a2b5e3e70882b2b；原base fd6cd703846a9614e32cff1434fdfe343fdd18c8。
- fetch后固定新base：e402bc4d6c4a70be8082fb4b79cbd77b483e2dc2。三提交rebase无冲突，重放head daa1403c7a10f320596a62e2cd6f1570ed7e4466。
- range-diff三项均为“=”：e166638→bc5c430、441571f→f81f8fb、3a76ae2→daa1403，原补丁逐项等价。
- evals/cross完整tree：原head、新重放head、受测五项组合0aed529dfff0a4e557bb66340370bea51632a769三者均为2b25ccb8497261045e1e0d0c8ead88701abfd809；本次只额外补本票合入准备记录，没有改运行代码/fixture。
- 差异限evals/cross和本工作组01票/review.md；未改共享跟踪、版本completion或其他目录。
- 沿用原10项、两批实际prepare/构建回读及原双轴PASS/0必须项；未重复执行测试、模型或全量。五项组合证据见[第二批材料](../../v05-control/merge-batch-02.md)，本轮只读复核原始XML：targeted.xml 155节点、pension.xml 1节点，合计156个唯一节点，零失败/错误；哈希分别84f8c1dd9426477be6ae9e99924b684116aaf92b8b757032230b6458a161c7c9、3ce116bf6aaa9b1fac20dd193f855d87d3358d7288a378d3fa44d25fd0114efb，与材料一致。原失败批次保留。
- 原PR #295复用；远端更新使用精确旧head 3a76ae2885e4e52df30a55669a2b5e3e70882b2b的force-with-lease。CI依新head实际检查记录，计费未启动仍记Blocked，不写CI通过。精确新head/检查诊断在本次最终回报和PR说明登记，避免为回填自身SHA重复制造提交。

本条只完成合入准备，尚未启动HTTP服务、模型或页面。中控合入后另发启动信号，再先S01、后S02—S05；不提前启动。养老金风险信息不足仍暂停，#160没有新政策批准；生日数量/页面/预算前置仍待。

## 2026-10-25 正式真实E2E01开始

实际开始：2026-10-25 18:49（Asia/Taipei）。已获中控正式运行授权；固定main 2a070b9cf992a109d8b54718a49dc3e3b56bd236，298/284/292/295/297均已合入。账单、平台13和正式案例数据不再作为未合入阻塞。新分支codex/v05-cross-e2e-01-live；复用本独立managed worktree，隔离案例live-20261025-01，源风险配置原样继承，不新增#160政策。

先S01真实页面→模型→HTTP/SSE→逐项确认/验证→隔离银行；失败保留原批次并回派准确目录，不盲循环重跑。核心通过后才继续S02—S05/X。02—04依后续中控信号与原依赖。本轮只更新本票与evals/cross，AI审查/PM接受/真人签核分开。

### S01首次实跑回交（保留失败）

- 批次s01-live-20261025-01，真实页面发送原表达一次，glm-5.3 Coding Plan真实回包选择subscription.cancel_subscription；实际单任务succeeded且仅签约清单，没有cross父子关联。HTTP未失败、没有模型异常。S01验收失败，未继续S02—S05或改话术重跑。
- 工具执行开始4次且全为读取；银行写请求0、原操作0、结算效果0；确认/验证未到达。两项应取消签约与保留项均未变。没有因HTTP成功或订阅任务succeeded计主目标通过。
- [原批次完整证据与最小复现](https://github.com/DrErwin/hackerthon-bank-agent/blob/31e995e75c12af57e05ae8cc9cda56b3da2d9693/evals/cross/evidence/2026-10-25/s01-live-20261025-01.md)；原脱敏JSON gzip和附件哈希保留。精确归属首先是agent_platform入口选择，另请原订阅线核对未类型化list/cancel行为，不越界修复。具体修复票由中控关联。
- 仅新增evals/cross观察器以捕获真实模型/HTTP/银行请求；不修改模型结果、风险或银行决策。13项局部测试通过，与实际E2E分开。观察器代码走新独立PR；未自行合并。
- 本批页面和本票服务进程已停止，原数据/秘密/操作留本机忽略目录；没有重置共享环境。E2E02—04及体验、真人安全/PM接受未推进。

### 失败批次采集代码PR与审查

- [PR #300](https://github.com/DrErwin/hackerthon-bank-agent/pull/300)，分支codex/v05-cross-e2e-01-live，运行产品基线2a070b9；代码/原失败证据69f41ff，元数据补齐b6bd14d，双轴复核df76e85。新增代码仅evals/cross，未自行合并。
- 规范轴/规格证据轴最终均PASS，0剩余必须项。P2观察器摘要已在manifest显式补足，原报告/失败/4附件保留；13项局部测试通过，不计S01通过。
- 原task d9936966-fc1d-48e0-ae38-61131117203f、原run81342dc1-7e8d-4ae8-bb01-50910d9a67fe及模型/HTTP/银行证据可复核，恢复修复前不重发。回派目录优先backend/app/agent_platform，次级订阅入口解析交原线核对；S02—S05因核心失败Blocked。
- CI精确head df76e85166760a0e7df6a559f5377d104b70f84a检查121152103072失败，任务因账号付款/额度未启动，记Blocked，不写测试失败或CI通过。本轮最终head状态在PR/最终回报登记；上一批例外不自动延伸到PR300。
