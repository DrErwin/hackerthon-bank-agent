# subscription：订阅 / 代扣管理（场景 05）

归属：Erwin（2026-10-19 起）。业务口径见 [05 订阅代扣管理 PRD](../../../../docs/prd/05-订阅代扣管理-PRD-2026-10-19.md)；
公开契约见[公共契约 §5.5](../../../../docs/contracts/公共契约-2026-09-23.md)、[银行接口字段 §7A](../../../../docs/contracts/银行接口字段-2026-09-24.md)；
实施规格与票据见 [`.scratch/v04-subscription/`](../../../../.scratch/v04-subscription/spec.md)。

本模块**不改动 `backend/app/modules/bills/`**：v0.4 期间「查自动扣费 / 退订 / 下月还要扣多少」由主 Agent 直接路由到这里（PRD Q10）。

## 公开能力（注册后进入模型目录）

| 能力 | 入参模型 | 权限 | 等级 | 副作用 | 确认策略 |
|---|---|---|---|---|---|
| `subscription.list_subscriptions` | `SubscriptionListInput` | `subscription.read` | read | 否 | none |
| `subscription.cancel_subscription` | `SubscriptionCancelInput` | `subscription.cancel` | modify | 是 | `per_action` |

## 私有工具（不进模型目录，只经任务级安全门与统一执行器）

| 工具 | 银行能力 | 权限 | 相位 |
|---|---|---|---|
| `subscription.bank.list_accounts` | B01 | `subscription.read` | admission |
| `subscription.bank.list_subscriptions` | B29 | `subscription.read` | admission |
| `subscription.bank.list_transactions` | B08 | `subscription.read` | admission |
| `subscription.bank.cancel_subscription` | B30 | `subscription.cancel` | **execution**（写动作必须用执行相位，否则统一执行器按策略拦截） |

工具声明名带模块前缀，避免与 transfer 的 `bank.*`、bills 的 `bills.bank.*` 在同一策略字典里冲突。

## 三种事实等级（SOP-1）

1. **签约事实**：B29 返回的本行签约协议（`source_type="mandate"`，`active` 才可在线退订）；
2. **扣款事实**：B08 流水按 `merchant_id == counterparty_id` 归集出的 `billed_count` / `billed_total_fen`；
3. **疑似线索**：按公共契约 §5.9 第 4/5 条扫描流水得出的 `source_type="suspected_ledger"`（连续 ≥3 个自然月、同商户同额、锚点 ±3 天、月末对齐），**不能在线退订**，只给外部关闭引导；流水覆盖不足 3 个月时整表标 `insufficient_data`，不报「未发现异常」。

## 状态机（SOP-2）

`WAITING_INPUT`（多候选/拒绝批量全退，单选候选只含可在线退订项）→ 确认门（6 项固定展示字段）→
`WAITING_APPROVAL`(confirmation) → `WAITING_APPROVAL`(verification，`basic_identity` + `scope=session`) →
执行 B30 → `succeeded`；取消 → `cancelled`；验证连续 3 次失败或安全门 `BLOCK` → `failed`（终止，不改银行状态）。
确认单与回执只承诺「从下一期（YYYY-MM-DD）起不再自动扣费，之前已经扣掉的钱不退」。

## 与平台（票 05）的接口

`ports.py` 是模块与平台的唯一接缝，平台实现/提供：

- `context_factory(trusted, operation_id=None, action_revision=None)`：返回带**已答确认**与会话级验证记录的 `ExecutionSecurityContext`（写动作必须带上，否则安全门永远认为未确认）；
- `operation_reserver(trusted, payload)`：按冻结事实幂等返回同一 `operation_id`；
- 可选的 `on_bind(security_context, action_name, parameters_ref, payload)`：把绑定事实交给平台的风险事实解析器（模块的参数存储是内存态、单次调用后清理）；
- `SubscriptionPorts` 的其余读写方法由 `reads.GatewaySubscriptionPorts` 实现，全部过安全门。
