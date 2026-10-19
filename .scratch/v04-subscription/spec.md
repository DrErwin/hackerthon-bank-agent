# v0.4 订阅代扣管理（场景 05：代扣盘点、单笔退订与 30 天到期提醒）规格说明

> 对齐 PRD：[docs/prd/05-订阅代扣管理-PRD-2026-10-19.md](../../docs/prd/05-订阅代扣管理-PRD-2026-10-19.md)  
> 唯一接口事实源：[公共契约](../../docs/contracts/公共契约-2026-09-23.md) §5.5 / §6.5 · [银行接口字段](../../docs/contracts/银行接口字段-2026-09-24.md) §7A · [确认验证字段](../../docs/contracts/确认验证字段-2026-09-24.md)  
> 关联里程碑：[docs/versions/v0.4.0/requirements.md](../../docs/versions/v0.4.0/requirements.md)  
> 关联交付包：[`v04-subscription/01`](packages/01-subscription-e2e.md)  
> 负责人：Erwin（`backend/app/contracts/`、`backend/app/services/`、`backend/app/modules/subscription/`、`backend/app/security/`、`backend/app/agent_platform/`、`backend/app/api/`、`evals/subscription/`）

---

## 0. 口径统一决议（2026-10-19，PM 指示后落定）

统一前存在三套写法：PRD §三（`next_charge_at`/`subscription_status`/`stopped_from_at`）、冻结公共契约 §5.5/§7A（`SubscriptionItem`/`SubscriptionListResult`/`SubscriptionTaskView`/`SubscriptionMandate`/`SubscriptionCancelReceipt`）、本 spec 与 7 张票据（`amount_cents`/`billing_cycle`/`can_cancel_online`/`upcoming_renewal_count` 等）。

PM 指示：**「把契约全部统一一下。之前冻结的契约是可以再加东西的，但修改的话要注意评估影响。」**

统一结论：

1. **接口命名与形状以冻结公共契约 §5.5 / §7A 为准**；本 spec、7 张票据、PRD 的字段表与模型名同步改写（纯文档）。
2. **本次契约变更全部是「新增」**：新增 §5.5 场景 05 能力与模型（追加字段 `billed_count` / `billed_total_fen` / `channel`、`suspected_scan_status` / `suspected_scan_reason` 属新增字段）、新增 §7A B29/B30、`ModuleError.source` 与 `TaskView.module` 两个枚举**扩值**。既有字段的名称、类型、语义与必填性一处未改。
3. **影响评估**：两个枚举扩值属可加性扩展；已检索仓库全部构造点（`ModuleError(`、`module=`）与前端产物引用，无按枚举穷举匹配的代码路径，无历史快照反序列化风险（旧任务快照的 `module` 仍是旧值之一）。`extra="forbid"` 契约模型新增字段为带默认值的可选新增，不破坏既有数据回读。
4. **金额单位统一用仓库既有口径 `fen`**（`Money`），不使用 `cents`；周期枚举为 `monthly | yearly`（**不含 quarterly**），**取消「月度折算」指标**，改用契约的 `upcoming_total_fen`（提醒窗口内合计）。
5. **疑似周期扣费的识别口径引用公共契约 §5.9 第 4/5 条**，由 `subscription` 模块基于 B08 流水本地实现（02 规则 4 的同口径实现）；**v0.4 期间不修改 `backend/app/modules/bills/`，也不改动 `flow_history.json`**（避免波及 02 既有验收），订阅种子流水单独成文件。

---

## 1. Problem Statement

老年用户常在试用会员、免密支付或弹窗引导下无意间开通周期性自动扣款（视频会员月费、网盘年费、听书连续包月等）。传统手机银行的「代扣协议管理」入口深、商户主体名称晦涩，且流水里的周期性扣费与本行签约代扣混杂，导致用户：

1. **看不清**：不知道自己签约了哪些自动扣费、哪些近期会扣款；
2. **退不掉**：分不清「银行可直接解约的本行代扣」与「只能去微信/支付宝/商户端关闭的疑似周期扣费」；
3. **不敢退 / 被误导**：退订文案若承诺「会员还能用到某天」或建议「先退再重订」，会引发权益与扣费争议；过度叠加人脸识别又会抬高正常退订门槛。

因此 v0.4 交付独立的**场景 05：订阅代扣管理（`subscription`）**纵向闭环：在不触碰并行开发的 `backend/app/modules/bills/` 的前提下，打通 SOP-1（代扣与疑似周期扣费盘点）、SOP-2（单笔本行签约代扣退订写操作 + 确认门 + 会话级基础身份验证码）与 SOP-3（未来 30 天被动续费提醒）。

---

## 2. Solution

**主 Agent 直接路由 + 独立 `subscription` 业务模块 + 模拟银行 B29/B30 + 既有确认门与会话级 `basic_identity` 验证**：

1. **与场景 02 物理目录解耦**：不修改 `backend/app/modules/bills/`；主 Agent 规划器把代扣盘点/退订意图直接路由到 `backend/app/modules/subscription/`（`S01 subscription.list_subscriptions`、`S02 subscription.cancel_subscription`）。
2. **三种事实等级分开摆（SOP-1 + SOP-3）**：
   - **签约事实**：B29 返回本行签约协议 `SubscriptionMandate`（`source_type="mandate"`、`status="active"|"cancelled"`）；
   - **扣款事实**：B08 流水按 `merchant_id == counterparty_id` 归集到签约项，给出 `billed_count` / `billed_total_fen`；
   - **疑似线索**：对 B08 流水按契约 §5.9 第 4/5 条扫描（同商户、金额整数分完全相同、连续 ≥3 个自然月、锚点 ±3 天），排除已归属签约（含已解约）的商户后，产出 `source_type="suspected_ledger"`、`status="suspected"`、`can_cancel_in_bank=False`；流水不足 3 个月时整表标 `insufficient_data`，**不报「未发现异常」**。
   - 未来 30 天（`reminder_days` 默认 30，1..90）内的 `active` 签约计入 `upcoming_renewals` 与 `upcoming_total_fen`。
3. **确定性单笔退订与确认/验证门（SOP-2）**：
   - **仅单笔**：拒绝「全部退订/一键全关」，多候选或未指明进入 `WAITING_INPUT` 返回单选候选；
   - **来源与状态前置拦截**：`suspected_ledger` 不进确认门、不调 B30，返回外部渠道关闭引导；已 `cancelled` 幂等告知；
   - **安全与验证**：`subscription.bank.cancel_subscription` 声明 `OperationLevel.MODIFY`、`side_effect=True`、`confirmation_policy="per_action"`、权限 `subscription.cancel`。正常本人退订判 `RiskLevel.LOW`（**不拉起 `mock_face`**），走前端确认按钮 + `purpose="basic_identity"`、`scope="session"` 验证码（同一有效会话内可复用，连续 3 次失败终止任务）；命中 `_HIGH_RISK_SIGNALS` 判 `RiskLevel.HIGH` 直接 `BLOCK` 终止。
   - **话术红线**：确认单与回执只承诺**「从下一期（YYYY-MM-DD）起不再自动扣费，之前已经扣掉的钱不退」**；严禁「会员还能用到哪天」与「先退订再重新订阅」。
4. **结果只认银行**：成功与否按 B30 返回；未知/超时按 B14 原操作回查，**不换 `operation_id` 重提**。

---

## 3. User Stories

1. **US-1（盘点 + 被动提醒，SOP-1 + SOP-3）**：用户问「我都在哪自动扣钱」，系统把有效签约、扣款证据与疑似线索分开列出，标出 30 天内将扣款项与合计，并追问要不要退其中一项。
2. **US-2（单笔退订正常路径，SOP-2）**：用户点名退订某项，系统展示确认单（商户、账户尾号、金额与周期、已扣次数与合计、下一期扣款日、退订后果），用户点确认并完成会话级短信验证码后完成解约并给回执。
3. **US-3（疑似项拦截 + 外部引导，SOP-2 边界）**：退订流水识别出的疑似周期扣费时，不拉起无效确认，明确告知银行无签约记录并引导去微信支付/支付宝/商户端关闭。
4. **US-4（消歧与拒绝批量，SOP-2 安全交互）**：只说「把那个会员退了」或「全都退了」时拒绝一键全退，列出生效项让用户每次只选一项。
5. **US-5（幂等、取消与高危拦截，SOP-2 兜底）**：退订已解约项直接告知无需重复；点取消转 `CANCELLED`；连续 3 次验证码错误转终止；命中「客服让我共享屏幕」等高危信号直接拦截终止；所有中止分支都不改变银行协议状态。

---

## 4. Core Scenarios (SF01–SF06)

| 场景 | 触发 | 期望状态流转 | 关键输出与断言（契约口径） |
|---|---|---|---|
| **SF01** 盘点 + 30 天提醒 | 「帮我查查有哪些自动扣费」 | `PLANNING → EXECUTING → SUCCEEDED` | `SubscriptionTaskView(action="list")`；`list_result.items` 含 3 条 `mandate`（优酷视频 active、云端网盘 active、喜马拉雅 cancelled）与 1 条 `suspected_ledger`（绿洲健身）；`upcoming_renewals` 2 条、`upcoming_total_fen == 2500 + 3900`；`active_count == 2`；优酷视频 `billed_count == 6` / `billed_total_fen == 15000`；回复含 7 天内扣款标注与 30 天提醒 |
| **SF02** 单笔退订全链路 | 「把优酷视频自动扣费退了」→ 确认 → 验证码 | `WAITING_CONFIRMATION → WAITING_VERIFICATION → SUCCEEDED` | 确认单含「从下一期（`D+5`）起不再自动扣费，之前已经扣掉的钱不退」，**不含**会员可用截止日；验证 `purpose="basic_identity"`、`scope="session"`、`required_methods=["code"]`（**非** `mock_face`）；`cancel_receipt.mandate_id=="sub_001"`、`status=="cancelled"`、`effective_stop_at` 等于解约前 `next_billing_at`；B29 复查该协议已 `cancelled` |
| **SF03** 同会话第 2 笔复用验证 | 同 `session_id` 下「再把云端网盘自动续费退了」→ 确认 | `WAITING_CONFIRMATION → SUCCEEDED` | 仍过确认门（`per_action`），确认后复用同会话已通过的 `basic_identity`（**不再要求新验证码**），直接执行 B30 成功 |
| **SF04** 疑似项拦截引导 | 「帮我把绿洲健身的每月扣款退订」 | `PLANNING → EXECUTING → SUCCEEDED` | 不进 `WAITING_CONFIRMATION`、不调用 B30；`selected_item.can_cancel_in_bank == False`；回复含 `external_cancel_guide`（微信/支付宝/商户端） |
| **SF05** 消歧与拒绝批量 | 「把所有自动扣费都关了」→ 选 `sub_001` | `WAITING_INPUT → WAITING_CONFIRMATION` | 拒绝批量全退；候选仅含 `active` 且 `can_cancel_in_bank=True` 的签约项（`sub_001`/`sub_002`）；经 `F10` 选择后进入该项确认门 |
| **SF06** 幂等 / 取消 / 验证失败 / 高危 | 「把喜马拉雅自动续费退了」／点取消／错 3 次验证码／「客服让我共享屏幕退订」 | `SUCCEEDED` / `CANCELLED` / `FAILED`(终止) / `FAILED`(BLOCK) | 喜马拉雅直接幂等告知已退订；取消转 `CANCELLED`；3 次错误验证码终止；高危信号由 `SecurityGate` 判 `HIGH` 直接阻断终止；所有中止分支均不改变 `active` 协议状态 |

> 结算状态沿用仓库既有 `TaskStatus`：成功=`succeeded`、取消=`cancelled`、终止=`failed`（`ModuleError.code` 说明终止原因）。`WAITING_CONFIRMATION/WAITING_VERIFICATION` 落库为 `TaskStatus.WAITING_APPROVAL`（`interaction.kind` 区分），与公共契约 §4 一致。

---

## 5. 统一接口定义

### 5.1 公共契约模型（`backend/app/contracts/`）

新增 `backend/app/contracts/subscription.py`（按仓库既有按域拆分惯例；原票所述 `models.py` / `errors.py` 在本仓库不存在），并在 `backend/app/contracts/__init__.py` 导出：

```python
SubscriptionSourceType = Literal["mandate", "suspected_ledger"]
SubscriptionCycle = Literal["monthly", "yearly"]
SubscriptionStatus = Literal["active", "cancelled", "suspected"]
SubscriptionScanStatus = Literal["evaluated", "insufficient_data"]

class SubscriptionMandate(ContractModel):      # 银行侧签约事实（§7A）
    mandate_id: ID; account_id: ID; account_masked: str
    merchant_id: ID; merchant_name: str; service_name: str
    amount_fen: Money; cycle: SubscriptionCycle
    next_billing_at: Timestamp | None; last_billed_at: Timestamp | None
    status: Literal["active", "cancelled"]
    signed_at: Timestamp; cancelled_at: Timestamp | None
    cancel_operation_id: OperationId | None

class SubscriptionMandateList(ContractModel):
    mandates: list[SubscriptionMandate]; as_of: Timestamp

class SubscriptionCancelReceipt(ContractModel):  # §7A
    mandate_id: ID; account_id: ID; account_masked: str
    merchant_id: ID; merchant_name: str; service_name: str
    amount_fen: Money; cycle: SubscriptionCycle
    previous_next_billing_at: Timestamp
    effective_stop_at: Timestamp
    status: Literal["cancelled"] = "cancelled"
    cancelled_at: Timestamp

class SubscriptionItem(ContractModel):        # §5.5
    subscription_id: ID; source_type: SubscriptionSourceType
    mandate_id: ID | None
    merchant_id: ID; merchant_name: str; service_name: str
    amount_fen: Money; cycle: SubscriptionCycle
    account_id: ID; account_masked: str
    last_billed_at: Timestamp | None; next_billing_at: Timestamp | None
    status: SubscriptionStatus
    can_cancel_in_bank: bool
    days_until_renewal: int | None
    is_upcoming_renewal: bool
    external_cancel_guide: str | None
    billed_count: NonNegativeInt = 0        # 新增：扣款事实（次数）
    billed_total_fen: Money = 0             # 新增：扣款事实（合计）
    channel: str | None = None              # 新增：已知扣款渠道

class SubscriptionListResult(ContractModel):  # §5.5
    items: list[SubscriptionItem]
    upcoming_renewals: list[SubscriptionItem]
    active_count: NonNegativeInt
    upcoming_total_fen: Money
    as_of: Timestamp
    suspected_scan_status: SubscriptionScanStatus = "evaluated"   # 新增
    suspected_scan_reason: str | None = None                     # 新增

class SubscriptionTaskView(ContractModel):    # §5.5
    action: Literal["list", "cancel"]
    list_result: SubscriptionListResult | None = None
    selected_item: SubscriptionItem | None = None
    operation_id: OperationId | None = None
    operation: OperationResult[SubscriptionCancelReceipt] | None = None

class SubscriptionListInput(ContractModel):   # S01 逻辑入参（§5.5）
    request_id: RequestId; intent_text: str
    account_ids: list[ID] | None = None
    status_filter: Literal["active", "cancelled", "suspected", "all"] = "all"
    reminder_days: Annotated[int, Field(strict=True, ge=1, le=90)] = 30

class SubscriptionCancelInput(ContractModel): # S02 逻辑入参（§5.5）
    request_id: RequestId; intent_text: str
    subscription_id: ID | None = None
    merchant_hint: str | None = None
    account_id: ID | None = None
```

模型一致性校验（`model_validator`，与仓库既有 `ContractModel` 风格一致）：`upcoming_renewals` 必须等于 `items` 中 `is_upcoming_renewal=True` 的子序列且 `upcoming_total_fen == sum(amount_fen)`、`active_count == count(status=="active")`；`SubscriptionTaskView(action="list")` 必带 `list_result`，`action="cancel"` 必带 `selected_item`，`operation_id` 与 `operation.operation_id` 一致。

`backend/app/contracts/tasks.py`：`ModuleError.source` 增加 `"subscription"`；`TaskView.module` 增加 `"subscription"`（两处均为枚举扩值）。

测试：新增 `backend/app/contracts/test_subscription_contracts.py`（与 `test_bills_contracts.py` 同惯例），覆盖序列化、`extra="forbid"`、`amount_fen >= 0`、一致性校验与两个枚举扩值。

### 5.2 模拟银行 B29 / B30（`backend/app/services/`）

- 自包含建表：新增 `backend/app/services/mock_bank/subscriptions.py`，在 `MockBankService.__init__` 中 `CREATE TABLE IF NOT EXISTS bank_subscriptions (...)` 并用 `seeds/subscriptions.json` 幂等写种子（**不修改 `backend/app/storage/`**，参照 `bank_operation_scopes` 与 `MockBankVerification` 模式）。
- 种子日期用**相对演示当天 D 的偏移量**（PRD §3.2.5），在银行 `clock()` 上解析；测试注入固定 clock 即得确定性日期。
- `bank.list_subscriptions`（B29）：

```python
def list_subscriptions(self, user_id: str, account_id: str | None = None,
                       status: Literal["active", "cancelled"] | None = None
                       ) -> QueryOk[SubscriptionMandateList] | QueryFailure
```
  空 `user_id` → `INVALID_ARGUMENT`；非本人/不存在账户 → `ACCESS_DENIED`；按 `mandate_id` 排序；`as_of` 取银行 clock。

- `bank.cancel_subscription`（B30）：

```python
def cancel_subscription(self, context: TrustedContext, operation_id: UUID, mandate_id: str
                        ) -> OperationResult[SubscriptionCancelReceipt] | QueryFailure
```
  规则（§7A）：非 UUID4 → `INVALID_ARGUMENT`；`(user_id, demo_round_id)` 作用域预留（复用 `bank_operation_scopes`）；同 `operation_id` + 同参数幂等重放；同 `operation_id` 不同参数 → `OPERATION_CONFLICT`；跨用户 → `ACCESS_DENIED`；不存在 → `RECORD_NOT_FOUND`；换新 `operation_id` 对已 `cancelled` 再退 → `STATE_CONFLICT`；绑定账户非 `active` → `ACCOUNT_UNAVAILABLE`；成功写入 `bank_operations`（`action_name="bank.cancel_subscription"`，`receipt_json` 为 `SubscriptionCancelReceipt`）并更新该行 `status="cancelled"`、`next_billing_at=NULL`、`cancelled_at`、`cancel_operation_id`。
- B14 `get_operation` 扩展：`operation_type == "bank.cancel_subscription"` 时还原 `OperationResult[SubscriptionCancelReceipt]`（`OperationFound[SubscriptionCancelReceipt]`）。
- `BankGateway`（`services/bank_gateway/gateway.py`）新增 `list_subscriptions(context, account_id=None, status=None)` 与 `cancel_subscription(context, operation_id, mandate_id)`；写路径与 `submit_transfer` 同样超时保护与授权回调（`authorize_cancel`，未配置时 fail-closed 返回 `ACCESS_DENIED`）。
- 订阅种子流水单独成文件 `seeds/subscription_flows.json`（与 `flow_history.json` 同 schema），由 `MockBankService.seed_subscriptions()` 幂等写入，**不改动 `flow_history.json`**。

**种子数据（D = 银行 clock 当天）**

| 项 | 商户 / 服务 | 金额 | 周期 | 状态 | 下一期 | 流水证据 |
|---|---|---|---|---|---|---|
| `sub_001` | 优酷视频 / 优酷 VIP 连续包月（`merchant_id="M_UYUN"`, `account_id="A1"`, `account_masked="****0001"`） | 2500 | monthly | active | D+5（7 天内） | 近 6 个月每月 25 元 → `billed_count=6`、`billed_total_fen=15000` |
| `sub_002` | 云端网盘 / 超级会员连续包月（`M_UDRV`） | 3900 | monthly | active | D+12 | 近 3 个月每月 39 元 → `billed_count=3`、`billed_total_fen=11700` |
| `sub_003` | 喜马拉雅 / 巅峰会员连续包月（`M_XMAL`） | 1500 | monthly | cancelled | — | 历史流水；防误报（不混入待退与疑似区） |
| `sus_oasis_01`（派生） | 绿洲健身（`M_OASIS`） | 3900 | monthly | suspected | 最近扣款 +1 月 | 连续 5 个月每月 39 元、`channel="快捷支付"`，无签约记录 |

`SubscriptionItem` 组装口径：`mandate` 项 `subscription_id == mandate_id`；疑似项 `subscription_id` 由商户序列稳定派生（`sus_` 前缀）、`mandate_id=None`；`can_cancel_in_bank = (source_type=="mandate" and status=="active")`；`days_until_renewal = (next_billing_at - as_of).days`；`is_upcoming_renewal = (status=="active" and 0 <= days_until_renewal <= reminder_days)`。

### 5.3 业务模块（`backend/app/modules/subscription/`）

- `manifest.py`：`SUBSCRIPTION_MANIFEST`（`module_name="subscription"`, `version="0.4.0"`, `owner="Erwin"`, `implementation_kind="workflow"`, `dependencies=["bank_gateway", "security_gate"]`）
  - `S01 subscription.list_subscriptions`：`input_schema_ref="SubscriptionListInput"`、`output_schema_ref="ModuleResult[SubscriptionTaskView]"`、`required_permissions=["subscription.read"]`、`OperationLevel.READ`、`side_effect=False`、`confirmation_policy="none"`、`retry_policy="read_only"`
  - `S02 subscription.cancel_subscription`：`input_schema_ref="SubscriptionCancelInput"`、`output_schema_ref="ModuleResult[SubscriptionTaskView]"`、`required_permissions=["subscription.cancel"]`、`OperationLevel.MODIFY`、`side_effect=True`、`confirmation_policy="per_action"`、`retry_policy="none"`
- `reads.py`：`SUBSCRIPTION_PRIVATE_TOOLS`（命名按 bills 的模块前缀惯例，避免与 transfer 的 `bank.*` 私有工具在同一个策略字典里冲突）：
  - `subscription.bank.list_subscriptions`（READ / `subscription.read` / none / read_only）
  - `subscription.bank.list_transactions`（READ / `subscription.read` / none / read_only）
  - `subscription.bank.cancel_subscription`（MODIFY / `subscription.cancel` / per_action / side_effect=True / retry none）
  并实现 `GatewaySubscriptionReads`：与 `modules/bills/reads.py` 同构（任务级 `SecurityGate` + `DeterministicExecutor` + `parameters_ref` 解析，所有读写都过安全门，绝不直连银行表）。
- `service.py`：`SubscriptionService(ports, clock)`
  - `list_subscriptions(context, SubscriptionListInput)`：B29 + B08 流水 → 组装 `SubscriptionListResult`（排序：`active` 按 `next_billing_at` 升序 → `suspected` → `cancelled`）→ 适老化回复（分清「本行签约可直接退」与「疑似需去微信/支付宝/商户端」；列出 30 天内扣款项与合计；7 天内标「7 天内会扣款」；`insufficient_data` 时如实说明）→ `SUCCEEDED`。
  - `prepare_cancel(context, SubscriptionCancelInput)`：批量全退拒绝 / 多候选 / 未命中 → `WAITING_INPUT` + 单选候选；`suspected_ledger` → `SUCCEEDED` + 外部引导；`cancelled` → `SUCCEEDED` + 幂等告知；唯一 `active` 且 `can_cancel_in_bank` → 生成确认单 6 项展示字段与待执行参数（`mandate_id`、`amount_fen`、`merchant_name`、`service_name`、`account_id`、`account_masked`、`effective_stop_at`）。
  - `execute_cancel(context, plan)`：经统一执行器调 `subscription.bank.cancel_subscription`，按银行回执组装 `SubscriptionTaskView(action="cancel", selected_item=..., operation_id=..., operation=...)`；失败按银行错误码如实说明。
  - 话术红线常量：`CANCEL_NOTICE = "从下一期（{date}）起不再自动扣费，之前已经扣掉的钱不退。"`，禁止出现「会员可用至 / 还能用到 / 先退订再重新订阅」。
- `entry.py`：`SubscriptionEntry`（实现 registry 的 `start`/`resume`/`recover_session`/`checkpoint_context` 协议，参照 `modules/bills/entry.py` 的 checkpoint 用法）+ `subscription_factory(ports_factory)` + `register_subscription(registry, ports_factory)`。状态机：`WAITING_INPUT →(选择)→ 确认门 → WAITING_APPROVAL(confirmation) → WAITING_APPROVAL(verification) → 执行 → SUCCEEDED`；`unconfirmed → CANCELLED`；验证 3 次失败 → `FAILED`（终止）；`BLOCK` → `FAILED`（终止）。
- 测试 `test_subscription.py`（模块目录内）：SOP-1 排序/汇总/提醒/三种事实等级、SOP-2 各分支与话术红线、`insufficient_data`、疑似项与已退项不进确认门。

### 5.4 安全策略（`backend/app/security/`）

`demo_policy.py` 三处白名单（全字段相等比较，缺一即拦）：
1. `_permissions` 增加 `"subscription.read"`、`"subscription.cancel"`；
2. `_capabilities` 增加 `SUBSCRIPTION_MANIFEST.capabilities`；
3. `_private_tools` 增加 `SUBSCRIPTION_PRIVATE_TOOLS`。

`assess_risk` 增加显式分支：当 `declaration.name == "subscription.bank.cancel_subscription"`（退订唯一写动作）时，**命中 `_HIGH_RISK_SIGNALS` → `RiskLevel.HIGH`，否则一律 `RiskLevel.LOW`**——不受转账金额阈值/首次收款人影响，确保退订永远走「确认按钮 + `basic_identity` 验证码」而不会落到中风险 `mock_face`。该分支仍要求 `authorize_tool` 通过且 `checked_signals` 全覆盖（fail-closed 性质不变）。

测试 `test_gate.py` 增补：`subscription.list_subscriptions`（READ）直接 `ALLOW`；`subscription.bank.cancel_subscription` 未确认 → `REQUIRE_CONFIRMATION`、已确认未验证 → `REQUIRE_VERIFICATION`（`purpose="basic_identity"`、`scope="session"`、`required_methods=["code"]`）、已确认且同会话已验证 → `ALLOW` 并由执行器成功执行、命中高危 → `BLOCK`。

### 5.5 平台编排（`backend/app/agent_platform/`）

新增 `subscription_runtime.py`（模板：`transfer_runtime.py` 的 `_transfer_factory` / `answer_confirmation` / `bind_verification`）：
1. `SubscriptionRuntime`（或并入 `TransferRuntime` 的模块分发）提供：
   - `ports_factory(trusted, trace)`：构任务级 `SecurityGate`（`confirmation_preparer` 用 6 项展示字段、`verification_preparer` 在 LOW 时 `purpose="basic_identity"`/无摘要、`decision_sink`、`snapshot_writer` 写 `AuthorizationSnapshot`）与执行器参数解析；
   - `answer_confirmation(trusted, answer)`：按任务 `module == "subscription"` 分派，解析该任务待答确认（记录本身带 `operation_id`/`action_revision`），答后沿原任务继续；
   - `bind_verification(trusted, verification_id)`：同分派，绑定验证记录并落审计。
2. `registry` 注册 `SUBSCRIPTION_MANIFEST`（`register_module`）。
3. `model.py` 规划器：新增场景 05 意图识别与槽位（`subscription.list_subscriptions` / `subscription.cancel_subscription`，提取 `subscription_id` / `merchant_hint` / 批量全退标记 / 原始话术），与 transfer、bills 并列且优先级明确（退订动作词优先于盘点词）。
4. `local_demo.py` 的 `risk_facts` 扩展订阅分支：退订动作由服务端 fixture 提供证据（常规退订提供 4 项低风险信号；原始话术命中高危模式时提供 `SCREEN_SHARING`/`CREDENTIAL_REQUEST`/`SECRECY_OR_URGENT_PRESSURE` 等高危信号），并在 `build_runtime` 中接线订阅模块。
5. `harness.py` 不改核心机制，仅按需登记模块。

测试 `test_runtime.py`（或仓库既有 `test_transfer_runtime.py` 同目录新文件）覆盖 SF01–SF06 全状态机。

### 5.6 API 接线（`backend/app/api/`）

1. `app.py`：`/tasks/{task_id}/verifications` 等端点的泛型从 `VerificationResponse[TransferTaskView]` 放宽为兼容 `SubscriptionTaskView`，避免订阅任务完成验证后响应序列化校验失败。
2. `service.py`：
   - 组装并注入 `SubscriptionService`（与 transfer/bills 并列），任务视图 `module="subscription"`；
   - 解除 `isinstance(..., TransferTaskView)` 之类窄化断言，改用模块分发；
   - `input_response` 支持 `module="subscription"` 且 `WAITING_INPUT` 时接收 `selected_option_id`（如 `"sub_001"`）或 `text`（如「优酷视频」）继续进入确认门；
   - 确认/验证恢复路径按任务模块分派到平台对应 hook。
3. 测试 `test_api.py`（或同目录新文件）跑 SF01–SF05 的 HTTP 全链路。

### 5.7 评测集（`evals/subscription/`）

`golden_cases.json`（SF01–SF06 及红线）+ `test_subscription_evals.py`：对工具路由、状态机、银行协议状态、安全门决策、确认/回执文案红线做自动化断言；证据落 `evals/subscription/evidence/<date>/`。

---

## 6. Testing Decisions

1. **契约与模拟银行**：B29 种子与 `days_until_renewal`/`is_upcoming_renewal` 计算；B30 正常解约、幂等重放、`OPERATION_CONFLICT`、`STATE_CONFLICT`、`RECORD_NOT_FOUND`、`ACCESS_DENIED`、缺 `operation_id` 拒绝、B14 还原 `SubscriptionCancelReceipt`。
2. **模块与安全门**：SOP-1 排序/汇总/三种事实等级/`insufficient_data`；SOP-2 单笔命中、多候选、拒绝批量、疑似拦截、已退幂等、话术红线零违规；`demo_policy` 对退订的高低风险裁决与 READ 放行。
3. **平台 / API / 评测**：`F05 /chat`、`F06 /confirmations`、`F07 /verifications`、`F10 /inputs` 端到端走通 SF01–SF06；`evals/subscription/` 回归全绿且不破坏既有 transfer/bills/security/mockbank 测试。

---

## 7. 票据拆分（一票一目录）

| 票 | 标题 | 归属目录 | 依赖 |
|---|---|---|---|
| `v04-subscription/01-contract-models` | 订阅代扣公共契约模型与枚举扩值 | `backend/app/contracts/` | 无 |
| `v04-subscription/02-mockbank-subscriptions` | 模拟银行 B29/B30、自包含表与种子数据 | `backend/app/services/` | 01 |
| `v04-subscription/03-subscription-module` | 订阅代扣业务模块（S01/S02 与 SOP-1/2/3） | `backend/app/modules/subscription/` | 01、02 |
| `v04-subscription/04-security-policy-subscription` | 订阅代扣权限注册与退订风险策略 | `backend/app/security/` | 01、03 |
| `v04-subscription/05-platform-subscription-wiring` | 平台注册、意图路由与退订确认验证编排 | `backend/app/agent_platform/` | 01–04 |
| `v04-subscription/06-api-subscription-wiring` | 路由泛型放宽、F10 消歧输入与订阅模块接线 | `backend/app/api/` | 01–05 |
| `v04-subscription/07-subscription-evals` | 订阅代扣黄金评测集与端到端回归 | `evals/subscription/` | 01–06 |

---

## 8. Out of Scope

1. **不新增签约代扣**：不提供开通自动续费/签约代扣接口（`bank.create_subscription` / `bank.update_subscription` 不做）。
2. **不发起历史扣款退款/拒付**：已扣款项核查归场景 02，本场景不自动退历史已扣款。
3. **v0.4 不修改 `backend/app/modules/bills/` 与 `flow_history.json`，不改动 `frontend/`**：前端订阅插槽属前端交付包，本包只做后端闭环。
4. **不引入中风险刷脸（`mock_face`）**：退订固定为确认按钮 + 会话级基础身份验证码。
5. **不做后台主动推送/弹窗**：提醒只在用户主动查询与清单标注中给出。
6. **不做「查/退他人订阅」**：只允许本人。

---

## 9. Further Notes

### 通用 Skill 检查记录（2026-10-19）
按 [队员开工与通用 Skill](../../docs/agents/delivery-workflow.md) 检查本机 `~/.agents/skills/`：`to-spec`、`to-tickets`、`implement`、`code-review` 就绪（来源 `mattpocock/skills` 提交 `d81f3a183412e71a5b1e84ca21bc1a35eea03a60`）。

### 契约影响评估（2026-10-19，配合 §0 统一决议）
- **性质**：新增文件 `contracts/subscription.py`；`tasks.py` 两处枚举扩值；§5.5 追加 4 个可选字段与 2 个列表级字段；§7A 激活 B29/B30。
- **兼容性**：`ContractModel` 为 `extra="forbid"`，新字段全部带默认值；既有调用方不传即不受影响。枚举扩值不改变既有取值。
- **检索结论**：仓库内没有对 `ModuleError.source` / `TaskView.module` 做穷举匹配的代码；前端插槽按 `module` 取值回退通用插槽；无历史数据迁移需求。
- **未做**：不修改任何既有字段的名称/类型/语义/必填性；如需修改，另行登记并按契约流程评估。
