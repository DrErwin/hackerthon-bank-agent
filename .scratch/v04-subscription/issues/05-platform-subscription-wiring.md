# v04-subscription/05-platform-subscription-wiring: 平台注册、意图路由与退订确认验证编排

Ticket ID: `v04-subscription/05-platform-subscription-wiring`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§5.5）
Core scenarios: SF01–SF06（[spec §4](../spec.md)）
Verification: 本票局部——`pytest backend/app/agent_platform/test_subscription_runtime.py -q`；整条路径由 `07-subscription-evals` 覆盖
Owner: Erwin
Directory: `backend/app/agent_platform/`
Status: in_progress
Blocked by: [`v04-subscription/01-contract-models`](01-contract-models.md)、[`02-mockbank-subscriptions`](02-mockbank-subscriptions.md)、[`03-subscription-module`](03-subscription-module.md)、[`04-security-policy-subscription`](04-security-policy-subscription.md)
Source issue: Issue #123

---

## 1. 目标（Why & What）

把 `subscription` 模块接入主 Agent 平台运行时（`CapabilityRegistry`、`DeepAgentPlanner`、`AgentHarness` + 任务级安全门/执行器），支持自然语言直接路由到 `S01`/`S02`，并打通 `WAITING_INPUT`（消歧）→ 确认门 → 会话级 `basic_identity` 验证（同会话复用）→ 执行 → `SUCCEEDED / CANCELLED / FAILED` 全状态机。

> **目录边界**：只允许修改 `backend/app/agent_platform/` 下的文件。平台侧只做「编排与接线」，业务判定留在模块内。

---

## 2. 改动清单

### 2.1 注册与工厂
- 新增 `subscription_runtime.py`：提供 `ports_factory(trusted, saver, trace)`（实现 `modules/subscription` 的 ports 协议）与 `register_subscription(runtime)`，在 `build_runtime` 中调用（`local_demo.py`）。
- `registry` 走既有 `register_module`（不改核心机制）。

### 2.2 任务级安全门与执行器（模板：`transfer_runtime.py` 的 `_transfer_factory`）
- 构 `SecurityGate`：`confirmation_preparer`（用模块给的 6 项 `DisplayField` 创建确认记录并落 `confirmation.changed` 审计）、`verification_preparer`（`RiskLevel.LOW` → `purpose="basic_identity"`、无摘要、`required_methods=["code"]`、`scope="session"`；其它风险 → `action_step_up`）、`verification_resolver`、`decision_sink`、`snapshot_writer`（写 `AuthorizationSnapshot`，失败即不得提交银行）、`scope_authorizer`（`authorize_tool` + 任务未终止）、`risk_assessor`（`DemoSecurityPolicy.assess_risk`）。
- 参数 `parameters_ref` 解析：订阅退订参数由模块每次 start/resume 依据银行事实确定性重算（`mandate_id`/`amount_fen`/`merchant_name`/`account_id`/`effective_stop_at`），同一动作重放必须得到同一摘要（保证已答确认在恢复后仍有效）；不新增存储表。
- `operation_id`：同一任务同一 `mandate_id` 稳定复用（存在则沿用），换新动作才生成新 UUID4；由执行器写入 `bank_operations`，超时/未知按 B14 回查，**不重提**。

### 2.3 确认/验证恢复分派（API 依赖的 hook）
- `answer_confirmation(trusted, answer)` 与 `bind_verification(trusted, verification_id)` 按任务 `module` 分派：`subscription` 任务走订阅路径（解析该任务待答确认的 `operation_id`/`action_revision` → `ConfirmationService.answer` → 落审计），transfer 任务保持原路径不变。
- `recover_session`：会话恢复后重新过安全门，不复用旧会话的验证结论。

### 2.4 意图路由（`model.py`）
- 识别代扣盘点/续费提醒意图 → `subscription.list_subscriptions`；识别退订意图 → `subscription.cancel_subscription`；提取 `subscription_id`、`merchant_hint`、批量全退标记、原始话术（供安全门检测高危信号）。退订动作词优先于盘点词；与 transfer / bills 的既有分类不冲突。

### 2.5 风险事实解析（`local_demo.py`）
- `risk_facts` 增加订阅分支：退订动作由服务端 fixture 提供证据——常规退订给足 4 项低风险信号（熟商户/熟设备/常规金额/请求明确），原始话术命中屏幕共享、索要验证码、他人操控等模式时给对应 `_HIGH_RISK_SIGNALS`。
- `build_runtime` 中接线订阅模块与 ports。

### 2.6 测试 `test_subscription_runtime.py`
覆盖 SF01–SF06：盘点直接完成；退订 `WAITING_CONFIRMATION → WAITING_VERIFICATION → SUCCEEDED`（验证 purpose/scope 断言、无 `mock_face`）；同会话第二笔复用验证；疑似项直接引导；批量/模糊 → `WAITING_INPUT` → 选择后进入确认门；已退幂等；取消 → `CANCELLED`；3 次错码 → 终止；高危话术 → `BLOCK` 终止且不改协议状态。所有读路径走安全门、写路径经执行器。

---

## 3. 验收与自检命令

```bash
pytest backend/app/agent_platform/test_subscription_runtime.py -q
pytest backend/app/agent_platform -q     # 不破坏既有 harness / transfer runtime 用例
```

---

## Comments

- 2026-10-19 实施（平台线）：新增 `agent_platform/subscription_runtime.py` 与 `test_subscription_runtime.py`；`transfer_runtime` 的 `answer_confirmation`/`bind_verification` 按任务模块分派（transfer 原路径与审计标签不变）；`local_demo.risk_facts` 增订阅分支并注册模块；`model.py` 增订阅意图路由。
- 联调中发现并推动修复票 03 的 4 处缺陷（写相位、参数引用、审计证据键、SF05 词表），并补上平台侧「带 operation_id 的 `tool.started` 必须先落参数快照」的审计职责（与 transfer 的 decision sink 同构）。
- 与票据字面的差异（已接受）：`model.py` 不做槽位提取（契约的入口信封没有订阅槽位，模块按原话确定性解析，加槽位是死代码）；订阅待答确认/验证复用平台既有 `agent_transfer_*` 事实表（表名为历史包袱，语义是平台 task→绑定事实，未新建表）。
- 验证：`test_subscription_runtime.py` 15 passed、`agent_platform` 146 passed（真实 MockBank B29/B30 + 真实门/执行器/审计/存储；替身仅模型入口）。
- 交付：**PR #152**（分支 `feat/subscription/05-platform-subscription-wiring`，待审查与合入）。
