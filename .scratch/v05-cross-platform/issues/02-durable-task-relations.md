# 02：任务关系与安排记录持久化

Ticket ID: v05-cross-platform/02

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/storage/`

Status: delivered — 应用库 v5 持久化与并发接缝已合入（PR #257，squash 3f14a89，2026-10-24）；子代理审查发现的跨用户写缺口已修复并复测；Ringo 安全审查与 E2E 另行记录。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: 待 Erwin 指派

Accepted by: 未记录（具体票的实施执行者）

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-P06、B07、X03—X05；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

父子关系、采用/占用、受控引用及必要并发接缝持久保存；重启、双任务冲突、用户/轮次隔离可核对；不在存储复制业务算法

## Blocked by

- [v05-cross-platform/01：公共模型落地](01-public-models.md)

## Start when

- 包负责人 Erwin 已于 2026-10-24 接包；本聊天只细化票据，具体执行者由 Erwin 另行指派并记录领取。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [x] 父子关系、当前计划、采用记录及作用域引用重启后仍可定位；已有快照能继续读取。（task_relations/arrangements/budget_commitments/controlled_details；计划版本仍在任务快照；重启与 v4→v5 升级有测试）
- [x] 两个任务竞争同一账户安排或同一预算占用时，核对和登记不可被交错绕过；未知占用保留。（BEGIN IMMEDIATE 原子接缝+部分唯一索引兜底；真实双线程竞争测试；unknown 占用保留并持续占额）
- [x] 记录按本人/轮次隔离，重复关联不生出第二个子任务；存储不承担银行余额/风控判断。（全部方法带 user/round 范围；审查修复 update_budget_commitment 跨用户写缺口；业务金额上限由调用方传参）

## 实施交接：应用记录，不是银行账本

1. 使用 01 的模型和既有应用存储/检查点保存父子关系、计划版本、采用/占用、受控引用；尽量复用现有数据结构，只补真实缺口。
2. 明确“业务核对最新事实并登记待执行安排”所需的原子接缝，供 cross/平台调用；存储不能决定留多少生活费，也不独立判断银行是否可转。
3. 同账户安排与同预算占用必须能阻止重复承诺，未知占用仍可查；敏感引用原文如何保存与读取以已确认隐私方案为准。
4. 与 06 同属 storage：两票不要同时编辑同一迁移/初始化段；执行者协调合入顺序，不能各自占用相同迁移版本。

**本票验证步骤**：以两个独立请求竞争同一记录证明只有合法状态变更生效；重新打开存储后父子/占用仍在。覆盖重复登记、未知保留、错误用户/轮次和旧数据库升级；使用合约数据，不等待生日业务实现。

**交付物与边界**：受控存取/一致性接缝说明、迁移/重置行为和本目录测试；不修改 mock_bank 的生日资金对象（归 06）。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：已合入。[PR #257](https://github.com/DrErwin/hackerthon-bank-agent/pull/257)，squash 提交 `3f14a89`（2026-10-24）。交付：`storage/application.py` v5 迁移+四个受控接缝、`storage/test_cross_records.py`、`storage/README.md` v0.5 节。
- 本票验证：`app/storage/` 31 passed（新增 5 项）；全量后端 1453 passed；CI Repository checks 通过（PR #257）。
- 审查：子代理审查 A—G 中发现 1 项必须修复（`update_budget_commitment` 缺 user/round 过滤，跨用户可改写他人占用），已修复并补错误用户/轮次测试；其余 PASS。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 2](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（接包后细化）：Erwin 明确接受第一个交付包，授权本聊天完成拆票后交其他执行者实施。本票沿用原编号、目录和依赖；具体执行者尚未领取。总交接见[本包交接说明](../handoff.md)。
