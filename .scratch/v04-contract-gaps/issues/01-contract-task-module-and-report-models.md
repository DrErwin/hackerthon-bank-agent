Ticket ID: v04-contract-gaps/01
Package: 不适用（PM 自拆，不开交付包；见 [spec](../spec.md)）
Spec: [v04-contract-gaps spec](../spec.md)
Core scenarios: CG-1（`module` 承载）、CG-2（`BillReport`）、CG-3（`ExportView`）、CG-4（旧调用兼容）
Verification: 在 `backend/` 下 `python -m pytest -q app/contracts` 通过；新增字段 / 模型的断言先失败后通过；全后端回归无新增失败。合入后通知前端线（[#89](https://github.com/DrErwin/hackerthon-bank-agent/issues/89) 与 [liangshuang-frontend-complete/03](../../liangshuang-frontend-complete/issues/03-transfer-slot.md)）：`api.generated.ts` 重建归其执行。
Owner: Erwin
Directory: backend/app/contracts/
Status: in_review（[PR #113](https://github.com/DrErwin/hackerthon-bank-agent/pull/113)，2026-10-12；契约 47 passed、叠加票 02 的后端全量 391 passed、CI 绿；双轴审查意见已处置）
Blocked by: None
Source: 无独立 Issue（缺口来源 [PR #108](https://github.com/DrErwin/hackerthon-bank-agent/pull/108) 审查意见，缺口 ①③）

## 交付

1. `tasks.py`：`TaskView` 新增 `module`——`Literal["transfer", "bills", "cross"] | None`（默认 `None`）：任务所属业务模块，供前端选插槽；未接入模块 / 旧运行时为 `null`。
2. `bills.py`：新增 `BillReport`（§5.3 字段：`report_id`、`scope`、`summary`、`spoken_summary`、`monthly_average_fen`、`statistical_days`、`average_basis`、`generated_at`）。
3. `api.py`：新增 `ExportView`（§6.7 字段：`export_id`、`kind:card|details|audit`、`status:preparing|waiting_verification|ready|failed`、`task_id`、`file_name`、`media_type`、`download_path`、`error`），并把 §6.7 两条正文规则写成校验：明细导出必绑任务、下载路径保持应用内相对路径。
4. `__init__.py` 导出新增模型。
5. 测试：`test_contracts.py` 补 `TaskView.module`（含默认 `None` 与取值）与 `ExportView` 用例；`test_bills_contracts.py` 补 `BillReport` 往返用例。
6. 契约正文：§6.5 `TaskView` 行补 `module` 口径；文件顶部修订记录加一条（2026-10-12 晚）。

## 契约变更记录（PR 四件事）

- **为什么改**：前端底盘要从任务视图本身判断业务插槽（现只有 SSE 外壳有 `module`）；账单线的报告卡与导出状态缺公共承载模型（正文早有定义，代码没落地）。
- **原来 / 现在**：`TaskView` 无 `module` → 新增可空 `module`；无 `BillReport` / `ExportView` 模型 → 按 §5.3 / §6.7 新增。
- **影响方**：api（票 02 填充 `module`）；前端线（类型生成后消费 `module`、`BillReport`、`ExportView`）；账单模块与将来的 F21 / F22 / F23 端点消费报告 / 导出模型。
- **旧调用**：`module` 为可空新增字段，`BillReport` / `ExportView` 为新增模型，既有字段与取值不变，属兼容变更；以全后端回归验证。

## Comments

- 2026-10-12 晚：按票先写失败断言（`ExportView` / `BillReport` 导入即失败），再补模型；`test_contracts.py` 47 passed。改动列表：`tasks.py`（`TaskView.module`）、`bills.py`（`BillReport`）、`api.py`（`ExportView`）、`__init__.py` 导出、两个测试文件、契约正文 §6.5 与顶部修订记录。后端全量 390 passed（排除本机缺 `langchain_openai` 的 2 个真模型模块）。PR #113 已开，等 Erwin 复审合并；合并后通知前端线跑类型生成（票 03 前置）。
- 2026-10-12 晚（双轴审查后）：`code-review` Standards / Spec 两轴子代理审查（[意见与处置](https://github.com/DrErwin/hackerthon-bank-agent/pull/113#issuecomment-6127798394)，AI 辅助、非真人审查）提出 5 条，已全部处置——提交补「为什么」正文、rebase 最新 main、删除只用一处却进公开面的 `BusinessModule` 别名（改为内联字面量）、`ExportView` 补两条正文规则校验、契约 §6.5 把 `module` 填写范围从「F08、F09」改为「所有对外任务视图（F08—F13、F15、F36 等）」。改后复跑：契约 47 passed、叠加票 02 的后端全量 391 passed、CI 绿（2m39s）。
