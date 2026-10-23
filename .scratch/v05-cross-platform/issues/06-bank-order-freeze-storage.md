# 06：生日银行数据与原子提交

Ticket ID: v05-cross-platform/06

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/storage/`

Status: delivered — 银行库 v4 原子对象提交已合入（PR #260，squash 39835d2，2026-10-24）；银行规则判定归票 07；E2E 另行记录。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: 待 Erwin 指派

Accepted by: 未记录（具体票的实施执行者）

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-B01、B04—B07；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

冻结、订单、核销关联及操作记录能一致落库，重复提交不重复消费；账本与业务对象同时成功或失败

## Blocked by

- [v05-cross-platform/01：公共模型落地](01-public-models.md)

## Start when

- 包负责人 Erwin 已于 2026-10-24 接包；本聊天只细化票据，具体执行者由 Erwin 另行指派并记录领取。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [x] 冻结、订单、核销/释放与操作登记在必要事务边界内一致；失败不得留下无法回查的资金变化。（commit/finalize_operation effects 参数，同一 BEGIN IMMEDIATE 事务；中途失败连账户变化回滚有测试）
- [x] 同号同参返回同一结果，同号异参拒绝；同订单不能因换编号被重复付款。（操作表幂等+order_payments 主键+付款状态检查；换号重付四项全回滚有测试）
- [x] 本人/轮次、关联冻结和订单正确，未消费余额可核对；未知操作和占用不得被提前抹除。（user 范围读取/效果归属检查；captured/released 合计可算 remaining；processing 保留由 finalize 单次生效）
- [x] 迁移与演示重置可重复；旧银行记录及已有单业务结果仍可读。（v3→v4 IF NOT EXISTS；重启持久与升级测试；submit_transfer/订阅 115 项回归通过）

## 实施交接：银行对象与操作必须一起落地

1. 按 01 的生日银行模型存储冻结、订单、核销/释放关联和操作结果；明确哪几个对象必须在一个原子提交中改变。
2. 对同编号同参数保留原结果，同编号异参拒绝；订单付款唯一性和未消费冻结必须在持久层可约束，而非依赖模型或一次内存检查。
3. 操作处理中/结果未知的记录保留可回查事实；失败回滚不留下已动资金却无原操作记录的中间状态。
4. 与 02 协调同目录迁移，但不把应用预算/父任务逻辑复制到银行库。

**本票验证步骤**：围绕冻结/核销/释放/订单提交注入存储失败，核对相关对象与操作记录共同提交或回滚。覆盖重复/并发付款、隔离、重开数据库、旧数据迁移和种子重置。

**交付物与边界**：银行存储接口、原子性/唯一性及迁移测试；价格、送达、余额和限额等银行业务判断由 07 使用存储实现。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：已合入。[PR #260](https://github.com/DrErwin/hackerthon-bank-agent/pull/260)，squash 提交 `39835d2`（2026-10-24）。交付：`storage/mock_bank/repository.py` v4 迁移+四类对象效果+get_freeze/get_order、`test_bank_cross_objects.py`。
- 本票验证：`app/storage/` 37 passed（新增 6 项）；全量后端 1469 passed；CI 通过（PR #260）。
- 审查：子代理审查 A—G 全 PASS、无必须修复项；建议（删未用常量、补 processing+effects 拒绝断言）已采纳。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 11](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（接包后细化）：Erwin 明确接受第一个交付包，授权本聊天完成拆票后交其他执行者实施。本票沿用原编号、目录和依赖；具体执行者尚未领取。总交接见[本包交接说明](../handoff.md)。
