# bills — 账单业务（周恩宇 / Ethan）

本增量对应 [v04-ethan-bills-backend/03](../../../../.scratch/v04-ethan-bills-backend/issues/03-public-summary.md)、BF01/BF05/BF06 的 L01 首条可运行模块路径。只改本目录，只引用公共契约，不修改平台、安全、银行或前端，不提前做 v0.5 跨场景。

L02 的后续实现、注册和验收限制见 [L02 交易定位与异常核对](README-L02.md)，对应 [v04-ethan-bills-backend/04](../../../../.scratch/v04-ethan-bills-backend/issues/04-anomalies.md)。L01、L02、L03 使用独立 manifest/factory，分别完成正式平台/安全审核后才能注册；本分支不自动部署 L02。

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

Erwin 2026-10-14 先用 `bills.summarize` 完成首条真实接线：真实模块登记后，原三能力演示桩整体让位。L03 实现已经通过 PR #151 合入，装配注册已完成（#178，`public_catalog` 含 L03）；安全白名单仍未收录（Issue #177），真实报告调用仍被安全门拒绝。L02 的独立入口在本分支，必须在合并及安全审查后另行注册，均不可显示假成功。`bills.export_details` 仍是平台 F22 的任务标签/短路恢复路径，本模块不虚假登记敏感导出 handler；能力名对账留 #123。

## 输入、错误与当前限制

公开 typed L01 接受任意符合 `BillScope` 的范围、summary/details/对比。银行负责最近24个月支持范围，不在本模块复制银行限额或范围规则。

当前 Harness 给第二模块的 transport 仍是 `StartTransferInput`。本 entry 仅使用 request_id 与 intent_text，不把转账金额/收款人当账单事实；会话内支持明确 `YYYY年M月`、`YYYY-MM`、本月/上月，以及 F10 的 option-choice 回复。账户没有明确选择时不猜。自定义日期区间、年度范围及复杂对比在 typed L01 已支持，但聊天适配尚未完成：会明确追问而非静默缩短范围。本增量不是“所有自然语言均能理解”。

B01 账户列表与 B08 流水发生临时取数失败时可在原任务选择重试；权限拒绝仍为终态，不返回账单。否定类别请求（如“不含转账”）不会反写成该类别的肯定支出；非转账类别排除未在冻结 L01 定义，先追问并提供查看全部分类的选择，不静默减项。末态原任务不重新执行；范围改变应建立有明确修订语义的新选择，不能复用旧 interaction。当前 entry 的范围修改和任意文本 F10 接入需要后续扩充，BF05/BF06 不因此整体关闭。

L02 模块在本分支实现、L03 模块已在 main 并完成装配注册（#178）；L02 的生产注册、两者的安全白名单、真实模型/HTTP/前端联调和 BF01—BF07 联合验收仍未完成。平台实际装配归 Erwin，不在本目录越界修改。

## #136 / v04-ethan-bills-backend/08 返修说明

- B01 临时错误采用与 B08 相同的原任务等待重试；权限拒绝继续终态拒绝，没有放宽读权限。
- 识别否定类别；“不含转账”返回转账单列的完整消费统计，不将其改写为“转账支出”；不支持的其他类别排除明确澄清后再查询。
- 区分客户端输入错误 `INVALID_ARGUMENT`、服务输出契约不一致 `BILLS_RESULT_INVALID` 与模块内部故障 `BILLS_INTERNAL_ERROR`。内部故障仅记录受控 task_id 和错误类名，不记录原始银行异常、摘要或敏感流水。
- 2026-10-19 之前的返修未修改 `reads.py` 审计证据；本轮已按安全侧 #137 书面口径通过 Issue #145 单独整改，详见下节。

## Issue #145 读路径审计证据

- 按 #137 / #145 的安全侧书面口径，`tool.started` 只持久化共享 `parameter_digest` 计算的 `parameters_sha256`（无盐 SHA-256：确定性、不可逆、不含原文）。
- 注意：共享 `AuditJournal` 的通用脱敏会对 12–19 位连续数字做账号式遮盖，摘要中若出现这类数字串会被改写，**落盘值不保证与原始哈希逐字一致**；同一参数仍稳定得到同一落盘值（测试按脱敏后的值断言）。
- `tool.finished` 只持久化 `result_ref`、执行状态和账户/流水条数；失败时条数为 `null`（未知，不是假零），错误只留固定 `BILLS_BANK_QUERY_FAILED`。
- 读取流程抛出未预期异常时记 `BILLS_READ_FAILED`，不生成证据快照（`reads.py` 异常分支）。
- `result_ref` 指向当前 `RunTrace` 用户、任务和演示轮次内的摘要快照，不是可展开完整银行响应的访问凭据。完整响应仍只返回原受控读取调用方，不复制进 `audit_evidence`，也不新增结果展开入口。
- 此处不依赖 `AuditJournal` 自动过滤银行事实：逐笔商户名、金额、摘要、流水号、账户余额以及上游错误详情均不写入读取证据。历史已落盘记录的处理仍由审计底座负责人决定。
- `test_public_integration.py` 直接核对真实 SQLite `audit_evidence` 中 B01/B08 的参数摘要、结果引用、作用域、实际条数和失败证据形态；测试中的规划器和风险策略仍是明确替身。

## 验证

L03 对非法月份、未支持的细分时间或类别/明细限制先追问，不把请求静默扩大为全年或全部类别；用户确认查看完整报告后才读取本人账户。已生成报告的原任务重放恢复为真实 `BillReport`，沿用原 report_id，不重新取数或生成新报告。年度/月度报告仍只提供聚合内容，敏感明细导出与生产权限由公共平台处理。

```sh
cd backend
python -m pytest -q app/modules/bills/
```

`test_public.py` 验证公共模型、错误、回执、范围及 entry 协议（网关/checkpointer 为测试替身）；`test_public_integration.py` 使用仓库真实 Harness、SQLite scoped saver、SecurityGate、BankGateway 和公共种子 Mock Bank，**规划器与风险策略仍是明确测试替身**。不能据此声称真实模型、页面或专业安全验收通过。具体提交和 CI 结果以本次 PR 评论为准。

既有 `_statistics.py` 和其97项测试来自已合并 #92，本次未改动。规则依据：[公共契约 §5.3/§5.9/§6.11](../../../../docs/contracts/公共契约-2026-09-23.md) · [02 PRD](../../../../docs/prd/02-账单分析-PRD-2026-09-23.md)。


## L03 月度/年度报告开发增量（PR #151）

- 新增 `BillsReportService.generate_report(trusted, GenerateReportInput)`：只在本人的 B01/B08 全量读取通过且生成 `SpendingSummary` 后返回冻结公共 `BillReport`；月均按 gross×30÷实际北京时间天数，最终舍入到整数分；本期不足、银行失败不生成假报告。
- 新增独立 `REPORT_MANIFEST`（`bills.generate_report`，`GenerateReportInput` → `BillReport`）与 `register_bills_report(registry, reads_factory, clock)`：不能把 L03 简单追加到既有 `MANIFEST`，因为每次 `register_module` 会复用同一个 factory。该 L03 factory 使用 `BillsReportService` 和原有 scoped checkpoint 及账户/月度澄清；支持今年、去年和明确年度的账单范围，当前年度只统计至受信时钟。
- 仅表达 `purpose=self_view|print|share_request`，**分享请求不授予第三方权限**；不在模块中保存验证码、生成敏感导出链接或代替 F22—F24 的审批/验证。
- **尚需平台/安全工作线实际调用 `register_bills_report` 并将 L03 公共只读能力纳入正式审批清单**；生产聊天规划路由、真实报告落库、F21—F24 与前端联调均需另做真实验收。PR #151 模块级测试通过不等于 BF03/BF04 最终完成。

## #136 票09：模块防重独立回归

`test_module_start_replay_returns_saved_result_without_reads_or_checkpoints` 绕开 Harness，直接重建 `BillsEntry` 并重放同一请求，分别验证成功结果和账户选择等待结果：不重复读取银行、不新增 checkpoint，并仅将回执 `run_id` 更新为当前运行。删除 `BillsEntry.start` 内的已保存结果防重分支时，两项用例均须失败。`test_harness_replay_does_not_duplicate_bank_reads` 只声明平台层防重覆盖，不能替代上述模块用例。对应 [v04-ethan-bills-backend/09：模块防重用例补真实覆盖](../../../../.scratch/v04-ethan-bills-backend/issues/09-module-dedup-test-coverage.md)，来源 [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136)。
