# v0.4 前端契约缺口闭合规格（v04-contract-gaps）

Status: in_progress
Owner: Erwin（PM 自拆，不开交付包）
Source: [PR #108](https://github.com/DrErwin/hackerthon-bank-agent/pull/108) 申报的 6 条契约缺口，2026-10-12 双轴审查核对「全部属实」
Deadline: 票 01 / 02 不晚于 2026-10-14（前端线 [liangshuang-frontend-complete/03](../../.scratch/liangshuang-frontend-complete/issues/03-transfer-slot.md) 与账单线 [v04-ethan-bills-backend/05](../../.scratch/v04-ethan-bills-backend/issues/05-report-export.md) 依赖）

## Problem Statement

v0.4 通用前端底盘（PR #108）按「前端不造字段」的口径停下来，把 6 条契约缺口交回契约负责人：

| # | 缺口 | 归属 |
|---|---|---|
| ① | `TaskView` 无 `module`，只有 SSE 事件外壳里有，底盘无法从任务视图本身选业务插槽 | 底座 / 契约（本组） |
| ② | 生成类型只有转账版 `TaskView` | `frontend/`（类型生成脚本，本组不动） |
| ③ | F21 账单报告（`BillReport`）有契约正文、无后端模型 | 底座 / 契约（本组） |
| ④ | 无任务历史确认 / 验证列表接口 | 已由 [v04-task-history-replay](../../.scratch/v04-task-history-replay/spec.md) 收口（F39，Issue #85） |
| ⑤ | F15 确认只有 `approve\|cancel`，缺「返回修改」 | 契约文字归本组，可用值与语义在 `security/`、业务模块（见 Out of Scope） |
| ⑥ | 无结构化进度字段，等待时只能显示 `task.message` | 底座 / 契约（本组，结论 = 不新增字段，见下） |

## Solution

本组只做底座 / 契约目录内、能独立交付并且**旧调用不被破坏**的部分：

- **票 01（`backend/app/contracts/`）**：`TaskView` 增加可空 `module`；补 F21 `BillReport` 与 F22/F23 `ExportView` 公共模型（契约正文 §5.3 / §6.7 早有字段定义，代码缺模型）。
- **票 02（`backend/app/api/`）**：任务视图（F08—F13、F15 等）与 `task_updated` 事件载荷填写 `module`。

**⑥ 的处理口径（本组结论：不新增字段）**：等待态与进行态的结构化信息已经存在——`status`（第 1 章八态）、`interaction.kind`（input / confirmation / verification）、`interaction.options`、`allowed_actions`、`recovery_required`；`message` 只作展示文本。前端底盘正是按这几项渲染等待卡、选择卡、确认卡与验证卡，不需要新字段。契约 §6.6 `task_updated` 行提到的「计划步骤」当前无承载，若票 03/04 走查后确有具体需求，按该需求另立票（要 harness 发布步骤，改动面比本组大），不预先造字段。

**⑤ 的处理口径（不在本组实施）**：前端要的「返回修改」是一个新的确认可用值。契约文字（F15 `choice:approve|cancel`）归契约负责人，但**可用值以执行器为准**：选项在 `backend/app/security/gate.py`（Ringo 目录），`answer()` 的语义（非 `approve` 一律 `cancelled`）在 `backend/app/security/state.py`，恢复收集流程在 `backend/app/modules/transfer/`、`bills/`。只改契约文字会让后端把 `modify` 当取消执行，属于会误导前端的假承诺。因此本组不单方面改文字，按契约 §8.1 协同修改口径登记受影响方；等受影响方确认后单独走票。

## Core Scenarios

| 编号 | 场景 | 覆盖方式 |
|---|---|---|
| CG-1 | 前端只看任务视图本身就能判断该用哪个业务插槽（不必等 SSE 事件） | API E2E：F08 / F09 响应与 `task_updated` 事件载荷都带 `module` |
| CG-2 | 账单报告卡与口头摘要字段有公共模型可依，不自造字段 | 契约模型测试：`BillReport` 按 §5.3 构造并往返序列化 |
| CG-3 | 导出状态（准备 / 等验证 / 完成 / 失败）有公共模型可依 | 契约模型测试：`ExportView` 字段与可空项 |
| CG-4 | 旧调用不被破坏 | 新增字段可空、新增模型不改既有字段；全后端回归通过 |

## Implementation Decisions

- `module` 取值 `transfer|bills|cross`（任务所属业务模块），**可空**：旧运行时的任务视图或未接入模块时为 `null`，前端回退通用插槽。平台侧负责填充（票 02）。
- **不改 `ModuleResult`**：模块结果外壳不强制 transfer / bills 等业务模块设置该字段，避免把公共改动扩散到 `backend/app/modules/` 与既有 harness 构造点；任务视图是平台对外拼装的，由平台填。
- `BillReport` / `ExportView` 字段严格照 §5.3 / §6.7，不加契约外字段、不加契约没写的校验（KISS）。
- 一票一目录一分支一 PR；契约正文修订按第 8 章轻量确认档在 PR 说明记录。

## Testing Decisions

- 契约票：先在新增字段 / 模型上写失败断言（模型测试），再补模型；在 `backend/` 下跑 `python -m pytest -q app/contracts`。
- api 票：E2E 为唯一验收——`backend/app/api/test_app.py` 既有「真 `TransferRuntime` + 模拟银行 + 安全门」路径，断言对外响应与事件载荷；先加断言看到失败，再填实现。
- 纯文档改动（本 spec 与两票）直推 main，不跑 CI；代码改动走 PR + CI。

## Out of Scope

- ② 生成类型仅转账版：`frontend/scripts/generate_contract_schema.py` 的 `PUBLIC_MODELS` 登记与 `api.generated.ts` 重建，归前端工作线（票 03 前置）。
- ⑤ F15「返回修改」的实现：`backend/app/security/`（选项与 `answer` 语义）、`backend/app/modules/transfer|bills/`（返回收集流程）；本组只在 Further Notes 登记口径与受影响方。
- ⑥ 结构化进度新增字段、「计划步骤」发布（按上面的结论收口）。
- F21 / F22 / F23 端点与报告存储、导出文件生成、明细导出再验证：属 `backend/app/api/` 后续票（账单线 [v04-ethan-bills-backend/05](../../.scratch/v04-ethan-bills-backend/issues/05-report-export.md) 的前置），不在本组 6 条缺口内。
- `backend/app/security/`、`backend/app/modules/`、`frontend/` 的任何改动。
- 账单异常检测（`AnomalyResult` 等）与其他尚未落地的账单模型：账单线接入时按其票提出。

## Tickets

- [v04-contract-gaps/01：任务视图补模块名与报告 / 导出公共模型](issues/01-contract-task-module-and-report-models.md)
- [v04-contract-gaps/02：任务视图填写业务模块名](issues/02-api-task-module.md)

## Further Notes

- 2026-10-12 晚建组。依据：PR #108 审查意见（契约缺口核对「全部属实」）与 [项目跟踪](../../docs/01-项目跟踪.md) 10-12 行。
- 现有实现只注册转账运行时（`backend/app/agent_platform/transfer_runtime.py`），api 只服务转账任务；票 02 按此填 `transfer`，接入账单时在同一处按注册表解析。
- ⑤ 受影响方登记（等确认后单独走票）：Ringo（`security/gate.py` 交互选项、`state.py` `answer()` 语义）、梁爽（转账流程返回收集与重确认）、周恩宇（账单流程同口径）。
- ② 交给前端线的同时，本组票 01 交付后其类型生成即可带上 `BillReport` / `ExportView` 与可空 `module`，不需要等端点。
