# 08：L01 返修——失败口径 / 结论文案 / 错误映射 / 清单声明

Ticket ID: v04-ethan-bills-backend/08
Type: 开发
Owner: 周恩宇（Ethan）
Directory: backend/app/modules/bills/
Status: resolved
Package: [v04-bills/packages/01-bills-backend：v0.4 账单业务能力与评测](../../v04-bills/packages/01-bills-backend.md)
Spec: [v04-ethan-bills-backend 账单实施规格](../spec.md)
Core scenarios: BF01 / BF05（查询失败与恢复口径、结论不误导）；局部返修不改变场景边界
Verification: `backend/` 下 `app/modules/bills` 全量回归（基线 152 passed）+ 本票新增用例全绿；四项各自有可复核断言（见交付）。命令与输出记入本票 Comments。
Blocked by: None（基于已合入的 [PR #131](https://github.com/DrErwin/hackerthon-bank-agent/pull/131) L01 切片返修）
Source issue: [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136)

## 交付（对应 [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136) 清单项 1/2/3/5）

1. **项 1（entry.py:120-128）**：账户列表（B01）失败即终态不可重试，与 README「读失败可在原任务重试」不一致——改行为（对齐 B08 的可重试等待）或改文档（README 收窄宣称），二选一并在本票 Comments 说明选择理由。
2. **项 2（entry.py:139-144）**：单类别否定语义结论句错误——用户否定式筛选（如「不含转账」）时结论句不得写成肯定式「转账支出 X 元」；补一条否定语义用例。
3. **项 3（service.py:178-186）**：契约自校验失败（ValidationError）报成 `INVALID_ARGUMENT`、其他异常一律 `DEPENDENCY_UNAVAILABLE` 且无日志无审计——区分口径（校验失败 vs 依赖故障不混报）并补留痕（日志或审计事件，按模块现有机制，不越目录改审计底座）。
4. **项 5（manifest.py:17）**：`output_schema_ref="SpendingSummary"` 未覆盖 details 模式返回的 `BillDetails`——修正声明口径（描述写清两种输出或按冻结契约修正 ref），不改契约语义。

## 边界与依赖

- 只改 `backend/app/modules/bills/`；`reads.py` 的 `audit_evidence` 内容不在本票（等 [Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137) 安全侧书面结论）。
- 不改公共契约；平台侧问题（规划入口、审计 outcome）另见 [v04-platform/10](../../v04-platform/issues/10-planner-second-module.md)、[/11](../../v04-platform/issues/11-audit-outcome-denial.md)。

## Comments

- 2026-10-16：PM 侧按 [PR #131 审查结论第四节](https://github.com/DrErwin/hackerthon-bank-agent/pull/131#issuecomment-6198615597) 开票（[Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136)），Owner 周恩宇接手实施。
- 2026-10-18：[PR #140](https://github.com/DrErwin/hackerthon-bank-agent/pull/140) 三轴审查后 squash 合入 main（`e7e7b8f`）。四项交付由作者完成并通过审查；唯一合前必修 P2（`entry.py:141` 内部码进用户文案）为 **PM 授权代行修复、非作者本人修改**，代行与验证记录见 [PR #140 评论](https://github.com/DrErwin/hackerthon-bank-agent/pull/140#issuecomment-6250305741)。Verification（P2 部分，固定 worktree 实测）：`app/modules/bills` **159 passed**（含新增 message 断言）；后端全量 **612 passed / 0 failed**；变异检验 1/1 杀（放回 `exc.args[0]` 前缀用例变红，实测消息「INCOMPLETE_FACTS，账户暂时查不到…」）；分支已 rebase 最新 main，合并后主线树与已测树一致（tree `089c78f`）、CI 绿。P3 顺手项（summarize 安全拒绝镜像用例、entry 层非 BillsError 用例、流程补记）不阻塞，留作者后续取舍。票面置 resolved。
