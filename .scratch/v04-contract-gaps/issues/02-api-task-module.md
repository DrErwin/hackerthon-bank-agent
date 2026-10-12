Ticket ID: v04-contract-gaps/02
Package: 不适用（PM 自拆，不开交付包；见 [spec](../spec.md)）
Spec: [v04-contract-gaps spec](../spec.md)
Core scenarios: CG-1（任务视图与 `task_updated` 带 `module`）
Verification: E2E——`backend/` 下 `python -m pytest -q app/api/test_app.py`：既有「真 `TransferRuntime` + 模拟银行 + 安全门」路径上，F09（`GET /tasks/{task_id}`）、F08（`GET /tasks`）响应与 `task_updated` SSE 事件载荷的 `module` 均为 `transfer`。先加断言看到失败，再填实现。
Owner: Erwin
Directory: backend/app/api/
Status: in_review（[PR #114](https://github.com/DrErwin/hackerthon-bank-agent/pull/114)，2026-10-12；api 53 passed、后端全量 391 passed；依赖 PR #113 先合）
Blocked by: [v04-contract-gaps/01：任务视图补模块名与报告 / 导出公共模型](01-contract-task-module-and-report-models.md)（`TaskView.module` 未合入前无法填充）
Source: 无独立 Issue（缺口来源 [PR #108](https://github.com/DrErwin/hackerthon-bank-agent/pull/108) 审查意见，缺口 ①）

## 交付

1. `service.py` 的 `task_view()` 构造 `TaskView` 时填 `module`——当前服务只注册转账运行时，取值 `transfer`；接入账单 / 联动时在同一处按已注册模块解析（不新建抽象）。
2. `test_app.py` 补 E2E 断言：任务视图响应与 `task_updated` 事件载荷都带 `module`，且重启 / 刷新读取路径（F09）与列表路径（F08）一致。

## 说明

- 不改模块结果外壳 `ModuleResult`：业务模块（transfer / bills）继续只返回自己的结果，模块名由平台在对外任务视图上拼装。
- 不新增「模块名注册表」抽象：现在只有一个运行时，硬编码 `transfer` 并写明接入时改这一处，符合 KISS。

## Comments

- 2026-10-12 晚：先加断言看到失败（`module` 为 `null`），再在 `service.task_view()` 填 `transfer`；新增 E2E `test_task_views_name_their_business_module_for_slot_selection`（F09 / F08 / F15），并在既有 SSE 重连用例断言 `task_updated` 载荷带 `module`。PR #114 基于 #113 分支开出，`Depends on PR #113`，合并顺序 #113 → #114。
