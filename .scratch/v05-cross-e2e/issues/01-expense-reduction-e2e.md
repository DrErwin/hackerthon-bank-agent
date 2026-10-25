# 01：减支核心与关键异常 E2E

Ticket ID: v05-cross-e2e/01

Package: [v05-cross-linkage/packages/05-cross-e2e：三主线 E2E 与全面验收](../../v05-cross-linkage/packages/05-cross-e2e.md)

Spec: [本工作组规格](../spec.md)

Type: 评测

Owner: Erwin（本执行对话代行本票评测）

Directory: `evals/cross/`

Status: blocked — 2026-10-25 案例数据/入口局部已验证，真实E2E待账单及相应平台前置；风险事实不由数据工具补齐。

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
- 正式比较数据与签约种子已由本轮准备；账单输入PR #284及平台旧断言待原线交付，适用风险事实仍须核实，不把数据准备当执行批准。

## Start when

- 已获2026-10-25本轮执行授权；准备可立即做，真实运行按当前前置单独放行，不把领取当作验收通过。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

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
- [ ] 定向测试、实际本机prepare和子代理规范/规格审查后提代码PR；真实模型/HTTP/页面仍not_run。

详细数据、风险事实归属和接入缺口见[案例数据与入口](../../../evals/cross/fixture-runbook.md)。账单#284及平台旧断言是S01前置；P01还发现既定业务的本人A5去向、入账方向适配缺口，回cross业务线，不以fixture伪造契约或风险覆盖。#160未知维度语义交PM/安全线，本票不修改。此增量完成不关闭原E2E票。
