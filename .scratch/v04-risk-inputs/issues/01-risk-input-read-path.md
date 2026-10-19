# 01：服务端可信风险输入读取路径与检测器接缝

Ticket ID: v04-risk-inputs/01
Type: 开发
Owner: Erwin
Directory: backend/app/agent_platform/
Status: in_progress（2026-10-19）
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../v04-platform/packages/01-foundation-agent-mockbank.md)
Spec: [v04-risk-inputs 规格](../spec.md)
Core scenarios: 转账风险链路（RS01 / RS02 / RS06 输入侧）；对应 [Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160) 第 1、2、4 项
Verification: 单元级绑定校验 + 真实 HTTP 链路集成测试（真实安全门/执行器/审计/模拟银行，仅检测器为注入的测试实现）：真实原文高风险终止且零资金副作用、合法对照完成确认与验证、未知事实暂停、跨任务/跨会话引用拒绝；审计证据无原文与认证秘密。命令与输出记入本票 Comments。
Blocked by: None
Source issue: [Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)（Ringo 代码核查，转给 Erwin）

## 交付

1. 新增 `backend/app/agent_platform/risk_inputs.py`：
   - `RiskInputs`：不可变记录。绑定 `user_id / session_id / demo_round_id / task_id / run_id / action_name / parameters_ref / operation_id / action_revision`，携带原始请求 `request_id` + `request_text`（仅内存，不落证据）、动作不可变事实 `action_facts`、四维事实 `facts`、脱敏引用 `evidence_ref`。
   - `RiskFact`：`name / status(known|unknown) / source / scope / value`；known 必须有来源与检查范围；unknown 不得伪造值。
   - `TrustedRiskInputs.resolve(context, action, declaration) -> RiskInputs`：服务端受控读取，绑定校验失败抛 `RiskFactsUnavailable`（`risk-input-task-binding-required` / `risk-input-request-binding-required` / `risk-input-action-binding-required` / `risk-input-action-unsupported`）。
   - `RiskDetector = Callable[[RiskInputs], DemoRiskEvidence]` 接缝；本票只定义与测试，不改生产装配。
2. 事实来源：
   - 原始请求：`ApplicationStore` 任务快照 `intent_text` + `request_id`；任务必须存在、归属当前 user/round、`session_id` 与上下文一致、非终态。
   - 动作事实：`TransferSnapshots.resolve`（user/round/task/action/operation/action_revision 全等才会返回）。
   - 收款人熟悉度：`BankGateway.verify_payee`（B04）+ `list_transactions`（B08，本人账户、180 天窗口、只读出账）。
   - 金额历史：同一 B08 窗口内该转出账户「direction=outflow 且 nature=transfer」的金额样本。
   - 环境：无设备指纹可信来源时保持 unknown，不冒充已检查。
3. 接缝说明 `backend/app/agent_platform/risk-inputs-seam.md`：给 Ringo 的接口、约束、事实字段、导入顺序注意事项与后续装配方式。
4. 回归测试 `backend/app/agent_platform/test_risk_inputs.py`。

## 边界

- 只改 `backend/app/agent_platform/`；不改 `security/`、`api/`、`contracts/`、`evals/`。
- 不实现检测算法与风险等级映射；不改变冻结业务规则与既有 `DemoRiskEvidence` 形状。
- 原始请求、账号原文、验证码等不得写入审计证据、日志或事件；`evidence_ref` 只含不透明摘要。

## Comments

- 2026-10-19：按 [Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160) 建立。Issue 第 3 项（生产装配调用检测器、移除 `transfer_fixtures` 依赖）拆到 [02](02-detector-assembly-and-fixture-removal.md)，依赖 Ringo 的 [v04-ringo-security/02](../../v04-ringo-security/issues/02-real-risk-detector.md)。
