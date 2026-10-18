# bills — 账单业务（周恩宇 / Ethan）

本增量对应 [v04-ethan-bills-backend/03](../../../../.scratch/v04-ethan-bills-backend/issues/03-public-summary.md)、BF01/BF05/BF06 的 L01 首条可运行模块路径。只改本目录，只引用公共契约，不修改平台、安全、银行或前端，不提前做 v0.5 跨场景。

## 已实现

- `BillsService.summarize(trusted, BillSummarizeInput)`：通过受控 B01/B08 获取本人完整账户流水，返回公共 `ModuleResult`，data 是 `SpendingSummary` 或 `BillDetails`。
- summary 包括消费/退款/净额、转入/转出、七类占比与排序、可选同期对比；details 按已解析的原消费类别筛选退款、保持银行的渠道/脱敏元数据。
- 跨月退款原单通过同一授权账户 B08 补取；补取仅作来源证据，不重复计入本期。任一必要账户/原单/对照期缺失或失败，不返回完整成功或假零值。
- `GatewayBillsReads` 使用公共 `SecurityGate` + `DeterministicExecutor` + `BankGateway`，记录 tool.started/finished。安全策略和身份解析由平台注入，无默认放行器；无写银行处理器，错误详情不原样写入日志。
- `BillsEntry` 实现现有平台 entry 协议，使用平台传入的 scoped checkpointer 保存同一任务。支持明确单月和本人账户选择、原范围重试、取消、重复开始防重以及跨会话恢复后的再次选择。
- `register_bills(registry, reads_factory, clock)` 提供真实注册入口，能力清单非空，owner=`zhouey314-cloud`、version=`0.4.0-l01`；`bills.summarize` 在 manifest 描述中明确说明按 mode 返回 `SpendingSummary` / `BillDetails`；`output_schema_ref` 保留已有真实类型 `SpendingSummary`，避免发明不存在的 schema union 标识。

## 平台接入约定（Issue #123）

```python
from app.modules.bills.entry import register_bills
from app.modules.bills.reads import GatewayBillsReads

# 由平台工作线在 ApiService 装配前执行。
# reads_factory(trusted, trace) 应返回：
# GatewayBillsReads(gateway, task_scoped_security_gate,
#                   trusted_execution_context_factory, trace)
register_bills(registry, reads_factory, clock)
```

`reads_factory` 必须提供现有平台的可信身份/轮次/任务校验和真实安全门；不能使用测试中的 LOW 风险/身份回调替身替代生产策略。gate 注册两种本模块私有 READ 工具（`bills.bank.list_accounts` / `bills.bank.list_transactions`），其参数形状定义在 `reads.py`，分别映射公开 B01/B08，不是新公共 HTTP 契约。

按 Erwin 2026-10-14 的优先级说明，这次只宣告实际实现的 `bills.summarize`。真实清单注册后，三能力演示桩整体让位：**L02/L03 不再出现在可执行目录中**，不能保留返回成功的假能力冒充实现。该最小切片需由平台票05明确接受后部署；后续 L02/L03 各按自身实施票追加。`bills.export_details` 仍是平台 F22 的任务标签/短路恢复路径，本模块不虚假登记敏感导出 handler；能力名对账留 #123。

## 输入、错误与当前限制

公开 typed L01 接受任意符合 `BillScope` 的范围、summary/details/对比。银行负责最近24个月支持范围，不在本模块复制银行限额或范围规则。

当前 Harness 给第二模块的 transport 仍是 `StartTransferInput`。本 entry 仅使用 request_id 与 intent_text，不把转账金额/收款人当账单事实；会话内支持明确 `YYYY年M月`、`YYYY-MM`、本月/上月，以及 F10 的 option-choice 回复。账户没有明确选择时不猜。自定义日期区间、年度范围及复杂对比在 typed L01 已支持，但聊天适配尚未完成：会明确追问而非静默缩短范围。本增量不是“所有自然语言均能理解”。

B01 账户列表与 B08 流水发生临时取数失败时可在原任务选择重试；权限拒绝仍为终态，不返回账单。否定类别请求（如“不含转账”）不会反写成该类别的肯定支出；非转账类别排除未在冻结 L01 定义，先追问并提供查看全部分类的选择，不静默减项。末态原任务不重新执行；范围改变应建立有明确修订语义的新选择，不能复用旧 interaction。当前 entry 的范围修改和任意文本 F10 接入需要后续扩充，BF05/BF06 不因此整体关闭。

L02、L03、报告与敏感导出、真实模型/HTTP/页面、专业安全审查及 BF01—BF07 联合验收仍未完成。平台实际装配归 Erwin，不在本目录越界修改。

## #136 / v04-ethan-bills-backend/08 返修说明

- B01 临时错误采用与 B08 相同的原任务等待重试；权限拒绝继续终态拒绝，没有放宽读权限。
- 识别否定类别；“不含转账”返回转账单列的完整消费统计，不将其改写为“转账支出”；不支持的其他类别排除明确澄清后再查询。
- 区分客户端输入错误 `INVALID_ARGUMENT`、服务输出契约不一致 `BILLS_RESULT_INVALID` 与模块内部故障 `BILLS_INTERNAL_ERROR`。内部故障仅记录受控 task_id 和错误类名，不记录原始银行异常、摘要或敏感流水。
- 不修改 `reads.py` 审计证据内容，仍等待安全线 Issue #137 的正式结论。

## 验证

```sh
cd backend
python -m pytest -q app/modules/bills/
```

`test_public.py` 验证公共模型、错误、回执、范围及 entry 协议（网关/checkpointer 为测试替身）；`test_public_integration.py` 使用仓库真实 Harness、SQLite scoped saver、SecurityGate、BankGateway 和公共种子 Mock Bank，**规划器与风险策略仍是明确测试替身**。不能据此声称真实模型、页面或专业安全验收通过。具体提交和 CI 结果以本次 PR 评论为准。

既有 `_statistics.py` 和其97项测试来自已合并 #92，本次未改动。规则依据：[公共契约 §5.3/§5.9/§6.11](../../../../docs/contracts/公共契约-2026-09-23.md) · [02 PRD](../../../../docs/prd/02-账单分析-PRD-2026-09-23.md)。
