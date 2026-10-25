# L02：交易定位与异常核对

实施票：[v04-ethan-bills-backend/04：L02交易定位与四类异常规则](../../../../.scratch/v04-ethan-bills-backend/issues/04-anomalies.md)。场景 BF02 / BF05 / BF06；依据为 [账单 PRD SOP-2](../../../../docs/prd/02-账单分析-PRD-2026-09-23.md)及[公共契约 §5.3 / §5.9](../../../../docs/contracts/公共契约-2026-09-23.md)。票内早期公共模型和夜间端点阻塞，以已解决的 [Issue #138](https://github.com/DrErwin/hackerthon-bank-agent/issues/138) / [Issue #132](https://github.com/DrErwin/hackerthon-bank-agent/issues/132) 后续决定为准；06:00 已按 PM 2026-10-18 决定落实。

## 公开入口与数据

`BillsAnomalyService.detect(trusted, DetectAnomaliesInput)` 使用现行公共模型，返回 `ModuleResult`。身份只来自平台 `TrustedContext`，B01 / B08 仍经过同一个受控 `GatewayBillsReads`。必要账户查询失败时不输出部分候选或“没有异常”。

| mode | 冻结输入 | 成功 data / 任务语义 |
|---|---|---|
| locate | `scope` + 至少一项 `clues` | `TransactionCandidates`，所有候选均为银行事实；空列表是完整查询后无匹配 |
| single | `account_id` + `transaction_id` | `AnomalyResult.transaction` 是重新读取的银行交易，含金额、北京时间、商户/收款方、渠道；渠道缺失显示“未知” |
| scan | `scope` | `AnomalyResult.transaction=null`，只检查规则4，不冻结、不取消、不推送 |

`ANOMALY_MANIFEST` 的 `output_schema_ref=AnomalyResult` 引用已存在的真实模型；manifest 描述明确 locate 返回 `TransactionCandidates`，不另造公共 union 标识。能力声明为 `bills.detect_anomalies`、`bills.read`、READ、无副作用、免确认、10,000ms、`read_only`，与安全执行器的 risk 独立；异常 attention 只用于业务提示。

## 同一任务内的定位和续办

`BillsAnomalyEntry` 使用现有 entry 协议，平台每次恢复创建新对象也可从 scoped checkpointer 接续，不依赖进程内候选缓存。

- 聊天信封只解析原始 `intent_text` / `request_id`；工厂另接收 `DetectAnomaliesInput` 并按冻结模式原样交服务，locate 返回候选集。当前 Harness 的 `StartTransferInput.amount_fen`、收款人、账户字段均不成为账单事实或选择结果。
- 缺少模式、月份或本人账户时逐项询问；单个本人账户也不替用户默认选择。明确“所有账户”才枚举全部本人账户。
- 明确单月支持 `YYYY年M月`、`YYYY-MM`、本月/上月；周期扫描可明确选择“最近三个完整月份”。半月、单日、第二月份、模糊区间、年度等尚未支持的聊天约束先询问完整月份，不在询问前读取银行；任意结构化范围可通过 typed 服务或注册工厂使用。
- 数值线索按整数分精确解析；多个金额、排除/大小关系、千位分隔或超过两位小数等不擅自取其中一部分。商户和渠道只接受带字段名的明确引号内容，字面值不当作金额或类别指令。无法精确解释时先由用户选择是否列出原范围流水。
- 没有可用线索时，内部 `candidates(scope, clues=None)` 直接列出完整范围的银行流水，不伪造违反冻结模型的空 `TransactionClues`。
- 一个候选可在原任务继续 single；多个候选返回 `waiting_input` 和真实 `TransactionCandidates`。随机 F10 option ID 仅映射至检查点中的 `(account_id, transaction_id)`，不能用前端金额、编号或“已验证”字段覆盖。选中后重新读取原范围，再读取该笔前三个月基线；保存过的展示数据不作为新事实。
- 空候选仍等待用户选择调整月份、账户、去除线索或重试原范围，不结束成“没有异常”。临时银行失败在原任务重试，权限拒绝直接停止。取消及终态不复活，同请求号异内容拒绝；旧 interaction / 旧 option / 跨用户或轮次状态均拒绝。重放恢复原来的公共 data 类型及候选按钮，不重复银行读取或 checkpoint 写入，只更新当前 `run_id`。
- 跨会话恢复保留原任务和查询约束，废弃旧按钮及已选目标；继续后重新鉴权并查询候选。每次 B01/B08 均经过当前安全门，不保存可复用的放行标记。

## 四类规则与完整性

1. 金额突变使用目标发生前同一本人账户的三个月完整支出流水，分别检查“超过历史最大单笔”或“超过平均单笔两倍”；计算不使用浮点。当前 `Transaction` 不提供可信亲属关系，转账的规则1标记 `insufficient_data`，不从姓名或用户文字推断亲属豁免。
2. 陌生对手方按银行 `counterparty_id` 和前三个月全部交易关系判断，既有转入也说明该对手方曾有交易；金额基线仍独立只用支出。陌生转账为 `high_attention`；陌生消费须同时达到规则1的大额标准。对手方或消费金额基线缺失时不作正常结论。
3. 北京时间 **[22:00, 06:00)**。22:00 和 05:59:59.999999 命中；恰好 06:00 为 `evaluated/not_matched`，不再保留早期“待 PM 决定”的不足状态。提示要求核对本人操作，不判定盗刷。
4. 同一商户、完全相同的整数分、至少三个连续自然月；首笔为日期锚点，±3天含端点，月底按实际月末对齐；不逐月漂移、不把同月多笔当多个月份。scan 只检查本规则。三个真实月份已有匹配可作为线索；没有匹配时，尚未观察到三个完整月份不能报告检查清楚。消费流水缺少商户标识时，规则4为 `insufficient_data`，不把跳过未知商户得到的空结果当成已核对；已知商户的真实匹配仍可提示。未来日期以银行 `as_of` 截断观察期。

银行逐账户返回的 `as_of` 在读完后与当前时钟比较，避免正常的持续前进时钟被误判为未来事实。重复流水编号、跨账户混入、范围外流水、发生时间晚于 `as_of`、两次读取事实不一致均拒绝完整结果。缺失前三个月的银行范围只使相应基线规则不足，仍可核对该笔真实时间；其他必要查询失败不冒充不足或零数据。

## 平台接入与依赖

```python
from app.modules.bills.anomaly_entry import register_bills_anomalies

# reads_factory 必须是平台实际的 task-scoped SecurityGate + GatewayBillsReads。
# 在 ApiService 装配前追加；L01 / L03 的 factory 各自独立。
register_bills_anomalies(registry, reads_factory, clock)
```

平台装配归 Erwin；Ringo 的现有三条冻结声明仅涵盖 L01 与两条私有读取工具，新增公共 `bills.detect_anomalies` 尚需安全目录明确登记其预期声明。当前实现不修改 L01 的 `CapabilityDefinition`、两条私有声明或任何安全、API、底座文件；声明未登记时应保持拒绝。真实模型路由、HTTP/页面、生产安全准入和 [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) 阶段二联合验收仍由对应工作线收口。

**单独 ID 调用的现有接缝限制**：冻结 single 只有账户和交易编号，B08 只有按范围列表，缺少按编号查询接口。内部同任务定位后可保留已选择的范围，因此能稳定重读。独立 single 则先请求完整时间轴，由 B08 的结构化 `RANGE_UNSUPPORTED.earliest_supported_at` 提供实际支持起点，只按该起点重试一次，不在本模块复制 24 个月银行规则。银行边界继续前进或不给合法起点、导致无法完成查询时，返回 `BILLS_LOCATE_REQUIRED`，要求先按月份定位；不加时间裕量后伪报 `RECORD_NOT_FOUND`。已成功完整读取银行支持范围但没有该 ID，则按契约返回 `RECORD_NOT_FOUND`，并明确其查询范围。按 ID 的稳定性缺口需要银行/平台负责人决定是否补公开接缝；本模块不修改冻结输入或绕过银行范围。

本实现继续复用读取适配器；读取审计证据的收窄已由 [Issue #145](https://github.com/DrErwin/hackerthon-bank-agent/issues/145) 经 [PR #171](https://github.com/DrErwin/hackerthon-bank-agent/pull/171) 合入 main——`tool.started` 只保存参数摘要，`tool.finished` 只保存 `result_ref`、执行状态和账户/流水条数，不持久化逐笔流水、商户名或余额。公共摘要哈希的长期保存行为仍归审计底座。L02 的三个月基线与按编号读取复用同一适配器，因此同样只落收窄后的证据（`test_anomaly_integration.py` 的 L02 审计断言）。

## 验证与证据边界

```sh
cd backend
python -m pytest -q app/modules/bills/test_anomalies.py app/modules/bills/test_anomaly_service.py app/modules/bills/test_anomaly_entry.py app/modules/bills/test_anomaly_integration.py
```

当前 L02 定向 **98 passed**（含 single 模式规则 4 命中、`DemoSecurityPolicy` 拒绝未登记声明、三个月基线读取的审计证据、旧检查点结果兜底四项）。06:00 用例在修复前实际复现为红，修复后夜间全部六个边界为绿。独立 Spec 复核指出的“既有转入误判陌生”“缺商户仍判周期规则清楚”“完整查询无 ID 错误码”三项，各有实际红用例，修复后原三项全绿。覆盖 locate 零/一/多候选、F10 forged/stale、候选选后事实重读、同任务重试/取消/跨会话、所有权与权限拒绝、四规则边界及基线不足、未知渠道、银行失败和移动保留边界。商户/渠道字面值不能替用户选择查询月份、全部账户或扫描模式。

`test_anomaly_integration.py` 的六项接缝测试使用仓库真实 Harness、scoped SQLite、SecurityGate、DeterministicExecutor、BankGateway 和种子 Mock Bank，银行和模块共用持续前进的时钟；F10 选项通过真实 `ApiService.input_response` 转换。规划器和 LOW 风险策略为明确测试替身，F10 helper 测试没有走 HTTP。结果不代表付费模型、前端页面或真人专业安全验收；完整套件及 CI 以本分支实际运行记录为准。
