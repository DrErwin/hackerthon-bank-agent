# 03：Harness 受控子任务衔接

Ticket ID: v05-cross-platform/03

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/agent_platform/`

Status: delivered — 受控派发/恢复机制与 D1 执行接缝已合入（PR #258，squash f029e74，2026-10-24）；D1 错误呈现的 source/field 偏差已如实记录待转账负责人适配；Ringo 安全审查与 E2E 另行记录。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: 待 Erwin 指派

Accepted by: 未记录（具体票的实施执行者）

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-S01、X02—X08；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

以正确能力输入启动/等待/恢复原子任务，沿用原安全执行链；计划与操作可追溯，账单来源继承不回归；先用符合契约的入口验证机制

## Blocked by

- [v05-cross-platform/01：公共模型落地](01-public-models.md)
- [v05-cross-platform/02：任务关系与安排记录持久化](02-durable-task-relations.md)

## Start when

- 包负责人 Erwin 已于 2026-10-24 接包；本聊天只细化票据，具体执行者由 Erwin 另行指派并记录领取。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。
- 父子任务授权与恢复规则需安全审阅。

## Acceptance criteria

- [x] 父级只可调用允许的已注册能力，可信身份由服务端传递；各业务接收其正确公开输入。（dispatch_child：registry 校验+CHILD_INPUT_CONTRACTS 白名单+服务端构造子 TrustedContext）
- [x] 原子任务等待输入/确认/验证时父级准确挂起，成功后继续后继；失败/未知先说明或回查，不盲目续办。（FAILED 释放槽位、NEEDS_ATTENTION 阻塞新副作用步骤；测试覆盖全序列）
- [x] 同一父任务同一时刻只有一个需用户响应或副作用的步骤推进；旧交互不能推进新版本。（CHILD_STEP_ALREADY_ACTIVE；resume_child 强制 plan_revision→PLAN_SUPERSEDED；通用子任务路径靠单活跃不变量，票 04/05 注意）
- [x] 重复请求、重启、新会话和取消沿原关联恢复；现有账单来源继承及单项业务不回归。（task_relations 持久+重启恢复测试；_inherited_bill_scope 零改动，test_bill_scope/test_harness 全绿；父级取消沿通用任务取消，票 05 验证）

## 实施交接：先提供机制，后装配业务

1. 输入为父任务可信身份、当前计划/步骤和已注册能力的合法参数；输出为稳定关联的子任务及其实际结果/等待状态。关联应在可恢复的边界持久保存。
2. 用真实注册表与符合契约的测试业务入口验证机制，避免先依赖尚未实现的 cross 形成循环。实际 cross 注册与 Demo 配置属于 05/09。
3. 推进顺序由合法计划决定；模型不能覆写可信身份、直接构造放行状态或回填成功。父级等待对应真实子交互，取消停止新步骤；恢复沿原关联查未知。
4. 复用当前锁、检查点和运行限制；若现有安全执行器无法承载已确认规则，向安全负责人登记具体缺口，不能在平台另建安全门。

**本票验证步骤**：对一次子业务依次返回等待输入、确认、验证、成功、明确失败、未知，检查父任务及下一步行为；重复请求/恢复仅有一个子任务和一份动作。回归现有账单来源继承，确保 parent_task_id 不被重解释破坏旧流程。

**交付物与边界**：平台受控调用/恢复接缝及本目录机制测试，现有审计字段的可追溯记录。不得提前把 fake 业务写成真实联调成功。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：已合入。[PR #258](https://github.com/DrErwin/hackerthon-bank-agent/pull/258)，squash 提交 `f029e74`（2026-10-24）。交付：`harness.py` dispatch_child/resume_child/child_task_summaries、`transfer_runtime.py` D1 守卫（提交前 PAUSE+ARRANGEMENT_CONFLICT、_bank_authorized 兜底、世系放行）、`test_child_dispatch.py`。
- 本票验证：`app/agent_platform/` 238 passed（新增 7 项，含真实转账路径零银行写入与真实世系放行）；全量后端 1460 passed；CI 通过（PR #258）。
- 审查：子代理审查 A—G 全 PASS、无必须修复代码项；建议项已转交票 04/05（见 PR #258 说明）。
- **已知偏差（待转账负责人适配，纯 modules/transfer 改动）**：D1 冲突经转账 workflow 渲染为 `source="security"`、`field=None`、通用暂停文案；平台接缝已保证 code=ARRANGEMENT_CONFLICT 与银行零写入，需转账模块 PAUSE 分支透传 message/source/field 以完全达到契约 §5.4 修订口径。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 3](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（接包后细化）：Erwin 明确接受第一个交付包，授权本聊天完成拆票后交其他执行者实施。本票沿用原编号、目录和依赖；具体执行者尚未领取。总交接见[本包交接说明](../handoff.md)。

2026-10-24（包 03 接包核对 G1，转给 Erwin 平台线）：源码 CHILD_INPUT_CONTRACTS 目前仅含 StartTransferInput/CrossStartInput，减支需要的 BillSummarizeInput、SubscriptionListInput、SubscriptionCancelInput 会在创建子任务前被 INVALID_CAPABILITY_INPUT 拒绝。因此基础派发已交付不表示减支真实接入就绪。后续修正在 agent_platform 单目录内按能力核对合法输入，验证账单/订阅实际工厂可派发、等待/恢复与错误类型拒绝，并提供合入证据。本轮仅登记缺口，未修代码、未重跑测试；业务 01 保留此开始条件，不能将其延后至依赖业务 01 的平台 05 而造成循环。
