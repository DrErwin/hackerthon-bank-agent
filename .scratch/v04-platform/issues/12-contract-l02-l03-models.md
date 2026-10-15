# 12：L02/L03 公共契约模型落地（冻结 §5.3 的书面模型进代码）

Ticket ID: v04-platform/12
Type: 开发
Owner: Erwin
Directory: backend/app/contracts/
Status: open
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P06 契约受理与联调](../spec.md)（受理账单线公共模型缺口）
Verification: 契约用例：locate / single / scan 三态输入构造合法、缺必需字段与未知附加字段拒绝；`RuleCheck` 能区分 evaluated / insufficient_data；L03 `purpose` 只接受已定义三值、purpose 不增加权限；现有 L01 / 转账公共模型与既有契约回归不变；新模型从 `app.contracts` 可导入。命令与输出记入本票 Comments。合入后账单线 [v04-ethan-bills-backend/04](../../v04-ethan-bills-backend/issues/04-anomalies.md)、[/05](../../v04-ethan-bills-backend/issues/05-report-export.md) 的公共类型前置解除。
Blocked by: None
Source issue: [Issue #132](https://github.com/DrErwin/hackerthon-bank-agent/issues/132)

## 交付

1. **L02 输入三态**：`DetectAnomaliesInput`（mode=locate / single / scan；single 携 `transaction: Transaction`、scan 下该字段为 null 的书面口径落成模型校验）与 `TransactionClues`、`TransactionCandidates`。
2. **L02 结果**：`RuleCheck`（区分 evaluated / insufficient_data）、`AnomalyFinding`、`AnomalyResult`。
3. **L03 输入**：`GenerateReportInput`（purpose: self_view | print | share_request；purpose 不增加权限、不加明细导出授权）。
4. 全部从 `app.contracts` 导出；复用既有 `BillScope` / `Transaction` / `Category`（`contracts/bills.py`、`contracts/bank.py`）；用模型校验禁止客户端改金额、商户或塞授权通过标记。

## 边界与依赖

- 只落已冻结 [公共契约 §5.3](../../../docs/contracts/公共契约-2026-09-23.md) 的语义，不改契约文字、不动既有 L01 / `BillReport` 字段；不是新增能力。
- 运行中形状桩（`agent_platform/bills_stub.py`）已有这些能力的 `schema_ref` 字符串；本票落模型后 stub 的 ref 即有对应代码，不在本票改 stub 行为。
- **06:00 端点口径不属本票**：PRD 规则 3「22:00—06:00」的恰好 06:00 边界（[Issue #132](https://github.com/DrErwin/hackerthon-bank-agent/issues/132) 末段另待 Erwin 书面明确）——端点取值等 PM 口径后由账单线录入 L02 反例，本票不擅自定。
- 关联：周恩宇已开 `feat/bills/l02-private-rules`、`feat/bills/l03-report-core` 两分支（2026-10-15，**尚未开 PR**）——本票合入后账单线 L02/L03 的 PR 才能引用公共模型，按公共改动流程「公共 PR 先合，受影响业务再同步」。

## Comments

- 2026-10-16：按交接清单建立，承接 [Issue #132](https://github.com/DrErwin/hackerthon-bank-agent/issues/132)（周恩宇 → Erwin）。账单线 F21—F24 报告链路闭环需要 L03 产出 `report_id`，本票是 L02/L03 解锁的第一跳。
