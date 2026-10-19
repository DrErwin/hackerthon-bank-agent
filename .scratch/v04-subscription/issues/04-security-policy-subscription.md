# v04-subscription/04-security-policy-subscription: 订阅代扣权限注册与退订风险策略

Ticket ID: `v04-subscription/04-security-policy-subscription`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§5.4）
Core scenarios: SF02、SF06（风险裁决与 `BLOCK`）
Verification: 本票局部——`pytest backend/app/security/test_gate.py -q`；整条路径由 `07-subscription-evals` 覆盖
Owner: Erwin
Directory: `backend/app/security/`
Status: todo
Blocked by: [`v04-subscription/01-contract-models`](01-contract-models.md)、[`v04-subscription/03-subscription-module`](03-subscription-module.md)
Source issue: Issue #123

---

## 1. 目标（Why & What）

在 `backend/app/security/` 注册场景 05 的模块清单、私有工具与权限，并落地定稿的退订风险策略：**正常本人退订一律低风险**（确认按钮 + `purpose="basic_identity"`、`scope="session"` 验证码，**不拉 `mock_face`**），**命中高危外部操控/非本人信号直接 `HIGH` → `BLOCK` 终止**。

> **目录边界**：只允许修改 `backend/app/security/` 下的文件。`SecurityGate`（`gate.py`）既有机制完备，本票不改其核心逻辑。

---

## 2. 改动清单

### 2.1 `demo_policy.py`（三处白名单 + 一条显式分支）
1. 导入 `SUBSCRIPTION_MANIFEST`、`SUBSCRIPTION_PRIVATE_TOOLS`（来自 `app.modules.subscription`）。
2. `_permissions` 增加 `"subscription.read"`、`"subscription.cancel"`。
3. `_capabilities` 追加 `SUBSCRIPTION_MANIFEST.capabilities`；`_private_tools` 追加 `SUBSCRIPTION_PRIVATE_TOOLS`（保持全字段相等比较，任何字段漂移即等于策略变更）。
4. `assess_risk` 增加显式分支：`declaration.name == "subscription.bank.cancel_subscription"` 时——
   - `evidence.signals & _HIGH_RISK_SIGNALS` → `RiskLevel.HIGH`；
   - 否则 → `RiskLevel.LOW`（**不受转账金额阈值/首次收款人/中风险信号影响**，确保退订永不落到 `action_step_up`/`mock_face`）；
   - 仍保留既有前置校验：`authorize_tool` 不通过或 `checked_signals` 未全覆盖 → `RiskFactsUnavailable`（fail-closed 不变）。

### 2.2 `test_gate.py` 增补
1. `subscription.list_subscriptions`（READ、`confirmation_policy="none"`）→ `ALLOW`；
2. `subscription.bank.cancel_subscription`：未确认 → `REQUIRE_CONFIRMATION`；已确认但本会话无 `basic_identity` 通过记录 → `REQUIRE_VERIFICATION`（`purpose="basic_identity"`、`scope="session"`、`required_methods=["code"]`）；已确认且同 `session_id` 已验证 → `ALLOW` 并由 `DeterministicExecutor` 成功执行（回执经注入的假银行返回）；
3. 同一 `session_id` 第 2 次退订复用已验证记录 → 直接 `ALLOW`（`per_action` 仍要求新的确认记录）；
4. 命中 `_HIGH_RISK_SIGNALS`（如原始话术含「客服让我开启屏幕共享退订」）→ `assess_risk` 返回 `HIGH`，`check_action` 返回 `BLOCK`（`HIGH_RISK_BLOCKED`），不产生执行；
5. `subscription.cancel` 权限缺失 / 私有工具声明漂移 → 拒绝（越权与白名单漂移回归）。

> 注意：`_private_tools` 按名注册，`subscription.bank.*` 前缀用于与 transfer 的 `bank.*`、bills 的 `bills.bank.*` 区分，避免同一策略字典内冲突。

---

## 3. 验收与自检命令

```bash
pytest backend/app/security/test_gate.py -q
pytest backend/app/security -q      # 不破坏既有安全用例
```
