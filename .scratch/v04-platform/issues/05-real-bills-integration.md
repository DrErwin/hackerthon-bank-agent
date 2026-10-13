# 05：真实账单模块接入平台与纵向联调（替换契约形状桩）

Ticket ID: v04-platform/05
Type: 开发
Owner: Erwin
Directory: backend/app/api/
Status: blocked
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P01、P02、P03、P04](../spec.md)（真实数据链路下的端到端验收）
Verification: E2E：真实账单任务（L01—L03）→ 报告自动落库 → F21 读取 → F22/F24 明细导出与下载；与前端账单插槽、账单线 BF01—BF07 的纵向联调记录；报告与导出无秘密泄漏。命令与输出、联调记录链接记入本票 Comments；整条路径通过才算 P01—P04 场景通过，局部接线不替代联调证据。
Blocked by: 账单公开能力可运行（周恩宇 [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)，跨线前置，非本组票）；[Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) 记录缺口
Source issue: [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123)

## 交付

1. 按可用性条件注册真实 bills 工厂，替换 `agent_platform/bills_stub.py` 的桩（桩保留为测试替身 / 降级路径，不删除、不作为生产默认）。**注册口径是「全有或全无」**：`ApiService` 装配时只在注册表里没有任何 `bills.*` 能力时才挂桩（`service.py:64-67`），真实模块一旦注册、桩整体让位——只注册部分能力时其余能力不会被桩补上；注册前须把 [modules/bills/manifest.py](../../../backend/app/modules/bills/manifest.py) 的 owner / version / 能力声明统一成真实一份（现为空清单，空清单会被 `NO_PUBLIC_CAPABILITY` 拒绝）。
2. 真实账单任务：任务视图 `module=bills` + 真实载荷、报告自动落库与 `report_ready` 事件端到端验证（票 04 接线在真数据下的确认）。
3. 纵向联调：与前端账单插槽（frontend-complete/01）和账单线 BF01—BF07 联调，证据并入 [v04-bills/02](../../v04-bills/packages/02-v04-acceptance.md) 联合验收。
4. [Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122) 的三处接缝已按一票一目录**提前单独收口**（[06](06-sse-event-payload-union.md) 契约 / [07](07-export-task-module-and-event-payload.md) api / [08](08-harness-resume-parsing.md) agent_platform，2026-10-14）；本票保留**真数据下的复验**：真实账单任务触发等待类交互时确认 resume 可推进、第二模块 `task_updated` 带真实载荷、导出任务归属 `bills`。

## 边界与依赖

- 不在本票：账单业务实现与评测（周恩宇，[v04-bills/01](../../v04-bills/packages/01-bills-backend.md)）；前端页面实现（梁爽/六水）。
- 前置未满足时保持 `blocked`；平台侧接口（F21—F24、模块注册点 `register_module`）已就绪，可先做接线准备与非真数据（测试替身）验证。
- **能力名对账（票 07 审查提出）**：`bills.export_details`（敏感导出任务用的能力名）没有契约或 manifest 依据、注册表里查不到；导出任务在 `continue_task()` 处被 `export_for_task()` 短路、不进 harness，因此今天无需注册。本票须明确对账方式——真实模块登记同名能力，或与 API 侧改名对齐；并保持导出任务与 harness 恢复路径分离（任何把导出任务引入 harness 的改动都会因该能力未注册而失败）。

## Comments

- 2026-10-13：v0.4 盘点发现"真实账单模块接入"无归属票（票 03/04 只交付注册点与契约形状桩），登记 [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) 并建立本票；前置=账单公开能力可运行。
- 2026-10-14 平台侧解封核对与 checkpoint：账单线票 03 的两个 `Blocked by` 事实上已满足——[Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91) 于 10-11 关闭、统计内核 PR #92 于 10-13 合入；但 `backend/app/modules/bills/` 至今只有私有内核与空清单（无 L01 注册入口），台账停在 10-11。平台侧已发解封通知（[Issue #123 回帖](https://github.com/DrErwin/hackerthon-bank-agent/issues/123#issuecomment-6150429852)），F21—F24、`register_module`、module/载荷/事件接线均已就绪。**10-16 checkpoint**：若 L01 仍不可运行，平台侧按降级口径推进（测试替身级接线 + 证据降级）并把延后如实写入版本文档，不再等待。
- 2026-10-14 本票保留的真数据复验范围按三票提前收口后的状态更新（见交付 4 与边界）；#122 关闭后若有真数据下的新发现，按一票一目录另开票。
