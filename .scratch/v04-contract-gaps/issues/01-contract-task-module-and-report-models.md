Ticket ID: v04-contract-gaps/01
Package: 不适用（PM 自拆，不开交付包；见 [spec](../spec.md)）
Spec: [v04-contract-gaps spec](../spec.md)
Core scenarios: CG-1（`module` 承载）、CG-2（`BillReport`）、CG-3（`ExportView`）、CG-4（旧调用兼容）
Verification: 在 `backend/` 下 `python -m pytest -q app/contracts` 通过；新增字段 / 模型的断言先失败后通过；全后端回归无新增失败。合入后通知前端线（[#89](https://github.com/DrErwin/hackerthon-bank-agent/issues/89) 与 [liangshuang-frontend-complete/03](../../liangshuang-frontend-complete/issues/03-transfer-slot.md)）：`api.generated.ts` 重建归其执行。
Owner: Erwin
Directory: backend/app/contracts/
Status: planned
Blocked by: None
Source: 无独立 Issue（缺口来源 [PR #108](https://github.com/DrErwin/hackerthon-bank-agent/pull/108) 审查意见，缺口 ①③）

## 交付

1. `tasks.py`：`TaskView` 新增 `module`——`BusinessModule = Literal["transfer", "bills", "cross"]`，可空（`BusinessModule | None`，默认 `None`）：任务所属业务模块，供前端选插槽；未接入模块 / 旧运行时为 `null`。
2. `bills.py`：新增 `BillReport`（§5.3 字段：`report_id`、`scope`、`summary`、`spoken_summary`、`monthly_average_fen`、`statistical_days`、`average_basis`、`generated_at`）。
3. `api.py`：新增 `ExportView`（§6.7 字段：`export_id`、`kind:card|details|audit`、`status:preparing|waiting_verification|ready|failed`、`task_id`、`file_name`、`media_type`、`download_path`、`error`）。
4. `__init__.py` 导出新增模型。
5. 测试：`test_contracts.py` 补 `TaskView.module`（含默认 `None` 与取值）与 `ExportView` 用例；`test_bills_contracts.py` 补 `BillReport` 往返用例。
6. 契约正文：§6.5 `TaskView` 行补 `module` 口径；文件顶部修订记录加一条（2026-10-12 晚）。

## 契约变更记录（PR 四件事）

- **为什么改**：前端底盘要从任务视图本身判断业务插槽（现只有 SSE 外壳有 `module`）；账单线的报告卡与导出状态缺公共承载模型（正文早有定义，代码没落地）。
- **原来 / 现在**：`TaskView` 无 `module` → 新增可空 `module`；无 `BillReport` / `ExportView` 模型 → 按 §5.3 / §6.7 新增。
- **影响方**：api（票 02 填充 `module`）；前端线（类型生成后消费 `module`、`BillReport`、`ExportView`）；账单模块与将来的 F21 / F22 / F23 端点消费报告 / 导出模型。
- **旧调用**：`module` 为可空新增字段，`BillReport` / `ExportView` 为新增模型，既有字段与取值不变，属兼容变更；以全后端回归验证。

## Comments
