# v04-subscription/03-subscription-module: 订阅代扣业务模块（S01/S02 与 SOP-1/2/3）

Ticket ID: `v04-subscription/03-subscription-module`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§5.3、§6）
Core scenarios: SF01–SF06（[spec §4](../spec.md)）
Verification: 本票局部——`pytest backend/app/modules/subscription/test_subscription.py -q`；整条路径由 `07-subscription-evals` 覆盖
Owner: Erwin
Directory: `backend/app/modules/subscription/`
Status: resolved
Blocked by: [`v04-subscription/01-contract-models`](01-contract-models.md)、[`v04-subscription/02-mockbank-subscriptions`](02-mockbank-subscriptions.md)
Source issue: Issue #123

---

## 1. 目标（Why & What）

新建 `backend/app/modules/subscription/` 业务模块，实现 PRD 的三大 SOP：SOP-1 代扣与疑似周期扣费盘点（含扣款证据）、SOP-2 单笔本行签约代扣退订（确认门 + 会话级基础身份验证）、SOP-3 未来 30 天被动续费提醒；声明 `SUBSCRIPTION_MANIFEST`（S01/S02）与 `SUBSCRIPTION_PRIVATE_TOOLS`。

> **目录边界**：只在 `backend/app/modules/subscription/` 下新建/修改文件；**不触碰 `backend/app/modules/bills/`**，也不复制 bills 的私有契约。

---

## 2. 改动清单

### 2.1 `manifest.py`
- `SUBSCRIPTION_MANIFEST`（`module_name="subscription"`, `version="0.4.0"`, `owner="Erwin"`, `implementation_kind="workflow"`, `dependencies=["bank_gateway", "security_gate"]`）：
  - `S01 subscription.list_subscriptions`：`SubscriptionListInput` → `ModuleResult[SubscriptionTaskView]`、`["subscription.read"]`、READ、`side_effect=False`、`confirmation_policy="none"`、`retry_policy="read_only"`
  - `S02 subscription.cancel_subscription`：`SubscriptionCancelInput` → `ModuleResult[SubscriptionTaskView]`、`["subscription.cancel"]`、MODIFY、`side_effect=True`、`confirmation_policy="per_action"`、`retry_policy="none"`

### 2.2 `reads.py`（过安全门的读写适配，模板：`modules/bills/reads.py`）
- `SUBSCRIPTION_PRIVATE_TOOLS`：`subscription.bank.list_subscriptions`、`subscription.bank.list_transactions`（READ / `subscription.read` / none / read_only）、`subscription.bank.cancel_subscription`（MODIFY / `subscription.cancel` / `per_action` / `side_effect=True` / retry none）。
- `GatewaySubscriptionReads`：任务级 `SecurityGate` + `DeterministicExecutor`；`mandates(...)`、`transactions(...)` 走 `_read` 路径（decision 必须 `ALLOW`，否则 `SECURITY_REJECTED`）；写路径 `bind_cancel_parameters(...)` + `check_cancel(...)`（只做门判定，不执行）+ `execute_cancel(...)`（执行器执行），并落 `tool.started` / `tool.finished` 审计（写动作必填 `operation_id`）。**绝不直连银行表**。

### 2.3 `service.py`
`SubscriptionService(ports, clock)`：
1. **SOP-1 + SOP-3 `list_subscriptions(context, SubscriptionListInput)`**
   - B29 取签约 → 对每个账户按 `Scope`（近 12 个月，半开区间）取 B08 流水；
   - 扣款事实：按 `merchant_id == counterparty_id` 归集 `billed_count` / `billed_total_fen` / `last_billed_at`；
   - 疑似线索：按契约 §5.9 第 4/5 条扫描同一账户流水（同商户、金额整数分完全相同、连续 ≥3 个自然月、锚点 ±3 天、每笔只匹配一次），排除已归属签约（含 `cancelled`）的商户；命中序列派生 `subscription_id`（`sus_` 前缀）；流水覆盖不足 3 个月时 `suspected_scan_status="insufficient_data"` 并给出原因；
   - 组装 `SubscriptionListResult`（排序：active 按 `next_billing_at` 升序 → suspected → cancelled；`upcoming_renewals` 取 `is_upcoming_renewal` 项，窗口 `reminder_days` 默认 30；`upcoming_total_fen` 为窗口内合计；`active_count`）；
   - 适老化回复：分清「本行签约，可直接帮您退订」与「疑似周期扣费，需去微信/支付宝/商户端关闭」；列 30 天内扣款项、日期、金额与合计；7 天内标「7 天内会扣款」；`insufficient_data` 时如实说明且**不报「未发现异常」**；空结果与取数失败分开表达；末尾追问「需要帮您退订其中某一项吗？」；`SUCCEEDED`。
2. **SOP-2 `prepare_cancel(context, SubscriptionCancelInput)`**
   - 批量全退（`全部`/`所有`/`统统`/`一键全退`等）或未指明目标或多候选 → `WAITING_INPUT`（仅 `status=="active"` 且 `can_cancel_in_bank=True` 的候选，提示每次只能退一项）；
   - 命中 `suspected_ledger` → `SUCCEEDED` + `selected_item` + `external_cancel_guide`（不进确认门、不调 B30）；
   - 命中 `cancelled` → `SUCCEEDED` + 幂等已退订说明（不进确认门）；
   - 唯一命中 `active` 签约 → 生成确认单 6 项 `DisplayField`（商户名、账户尾号、金额与周期、已扣次数与合计、下一期扣款日、退订后果）与待执行参数（`mandate_id`/`amount_fen`/`merchant_name`/`service_name`/`account_id`/`account_masked`/`effective_stop_at`）。
3. **SOP-2 `execute_cancel(context, plan)`**：经执行器调 `subscription.bank.cancel_subscription`；成功组装 `SubscriptionTaskView(action="cancel", selected_item=更新后条目, operation_id, operation=OperationResult[SubscriptionCancelReceipt])` 与回执文案；失败按银行错误码如实说明（`STATE_CONFLICT`/`ACCOUNT_UNAVAILABLE`/`RECORD_NOT_FOUND` 等），未知不得写成成功或失败。
4. **话术红线**：常量 `notice(date) = f"从下一期（{date}）起不再自动扣费，之前已经扣掉的钱不退。"`；确认单与回执禁止出现「会员可用至 / 还能用到 / 先退订再重新订阅」。

### 2.4 `entry.py`
- `SubscriptionEntry(service, saver, trace, clock)` 实现 registry 的 `start` / `resume` / `recover_session` / `checkpoint_context`（checkpoint 用法参照 `modules/bills/entry.py`：只持久化解析后的约束与结果，不落原始用户文本）。
- 服务入口收到平台统一信封 `StartTransferInput`（`request_id` + `intent_text`），转成 `SubscriptionListInput` / `SubscriptionCancelInput`（含 `subscription_id` / `merchant_hint` / 批量标记槽位解析）。
- 状态机：`WAITING_INPUT`（`InteractionRequest(kind="input")`）→ 选择后进入确认门 → `WAITING_APPROVAL`（confirmation）→ 确认后 `WAITING_APPROVAL`（verification）→ 执行 → `SUCCEEDED`；`confirmed=False` → `CANCELLED`；验证连续 3 次失败 → `FAILED`（终止）；门判 `BLOCK` → `FAILED`（终止，高危拦截）；所有中止分支不改银行协议状态。
- `subscription_factory(ports_factory)` 与 `register_subscription(registry, ports_factory)`（供平台注册）。

### 2.5 `__init__.py`
导出 `SUBSCRIPTION_MANIFEST`、`SUBSCRIPTION_PRIVATE_TOOLS`、`SubscriptionService`、`SubscriptionEntry`、`subscription_factory`、`register_subscription`。

### 2.6 `test_subscription.py`
覆盖：SOP-1 三种事实等级/排序/`upcoming_renewals==2`/`upcoming_total_fen==2500+3900`/`billed_count` 证据/7 天标注/30 天提醒/`insufficient_data`/空结果与失败分开；SOP-2 唯一命中生成 6 项确认字段与话术红线零违规、疑似项外部引导不产写操作、已退项幂等、模糊与批量全退 `WAITING_INPUT`、执行成功与银行拒绝分支；高危输入由门 `BLOCK` 终止且不改状态。

---

## 3. 验收与自检命令

```bash
pytest backend/app/modules/subscription/test_subscription.py -q
pytest backend/app/modules -q      # 不破坏 transfer / bills 既有用例
```

---

## Comments

- 2026-10-19 实施：新建 `modules/subscription/`（manifest / ports / _rules / service / entry / reads / README + 单测）：S01 盘点（B29 签约 + B08 扣款证据 + 契约 §5.9 规则 4/5 疑似线索、三种事实等级、7 天标注与 30 天提醒）、S02 单笔退订（拒绝批量、多候选 `WAITING_INPUT`、疑似与已退不进确认门、6 项确认单、话术红线）、写路径只经安全门与统一执行器。
- 2026-10-19 首轮独立审查（`215285d`）：**不通过**——① 写动作用了 `Phase.ADMISSION`，统一执行器必然按策略拦截，B30 永不执行；② `parameters_ref` 每次 uuid4，已批准确认单必然 `CONFIRMATION_STALE`；③ 任意 `BLOCK` 都被渲染成胁迫话术。已修（相位参数化 + 确定性引用 + `security_stop` 按 `reason_code` 分流，并补 4 项真实 SecurityGate/Executor 集成回归）。
- 2026-10-19 复审（`bd7924b`）：3 项必修**验证通过**（含变异 A/B/C 被杀），新发现 1 项 P1——重复执行/恢复重提把银行已成功报成 `SECURITY_REJECTED`；另 2 处测试缺口。已修（`OperationResult` 一律按银行回执上报、非 HIGH_RISK 阻断如实回报、`VERIFICATION_FAILED` 用专门终止说明、候选只含可在线退订项），单测 33 项。
- 平台联调中由票 05 发现并修：确定性参数引用被复用为审计证据键撞 `audit_evidence` 唯一约束（`df61d23`）；spec SF05 原话「把所有自动扣费都关了」缺词（`07a20a5`）。
- 2026-10-19 合入 main：**PR #147**（squash `d3f298c`）。
