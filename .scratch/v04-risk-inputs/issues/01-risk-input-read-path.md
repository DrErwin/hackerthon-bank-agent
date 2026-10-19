# 01：服务端可信风险输入读取路径与检测器接缝

Ticket ID: v04-risk-inputs/01
Type: 开发
Owner: Erwin
Directory: backend/app/agent_platform/
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../../v04-platform/packages/01-foundation-agent-mockbank.md)
Spec: [v04-risk-inputs 规格](../spec.md)
Core scenarios: 转账风险链路（RS01 / RS02 / RS06 输入侧）；对应 [Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160) 第 1、2、4 项
Status: resolved（[PR #167](https://github.com/DrErwin/hackerthon-bank-agent/pull/167) squash `52d5637` 合入 main，2026-10-19；CI 绿；独立子代理审查〔AI，非真人〕首轮判**不通过**〔1 项 P0：unknown 与 `DemoSecurityPolicy` 全覆盖互斥、验收证据自相矛盾〕→ 按结论返修 → 复审**有条件通过**、唯一必修〔合并前把 P0 登记给 Ringo〕已通过 [Issue #160 回帖](https://github.com/DrErwin/hackerthon-bank-agent/issues/160#issuecomment-6268456610) 满足；变异复验 M2/M4/M5 全部被杀）
Verification: 绑定校验 + 真实 HTTP/harness/安全门/执行器/审计/模拟银行集成测试（仅检测器为注入替身）：真实原文高风险终止且零资金副作用、合法对照完成确认与验证（**流程对照口径**）、未知事实暂停、跨用户/会话/轮次/任务/终态/过期引用拒绝；审计证据无原文与认证秘密。**P0 待决**：`checked_signals` 与 unknown 的映射须由安全侧决定（接缝文档 §4.1、spec §3.1），决定前生产装配（票 02）保持 blocked。
Blocked by: None
Source issue: [Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)（Ringo 代码核查，转给 Erwin）

## 交付

1. 新增 `backend/app/agent_platform/risk_inputs.py`：
   - `RiskInputs`：不可变记录。绑定 `user_id / session_id / demo_round_id / task_id / run_id / action_name / parameters_ref / operation_id / action_revision`，携带原始请求 `request_id` + `request_text`（仅内存，不落证据、`repr` 隐藏）、动作不可变事实 `action_facts`（同上）、三维事实 `facts`、脱敏引用 `evidence_ref`。
   - `RiskFact`：`name / status(known|unknown) / source / scope / value`；known 必须有来源与检查范围；unknown 不得伪造值。
   - `TrustedRiskInputs.resolve(context, action, declaration) -> RiskInputs`：服务端受控读取，绑定校验失败抛 `RiskFactsUnavailable`（`risk-input-task-binding-required` / `risk-input-request-binding-required` / `risk-input-action-binding-required` / `risk-input-action-unsupported`）。
   - `RiskDetector = Callable[[RiskInputs], DemoRiskEvidence]` 接缝；本票只定义与测试，不改生产装配。
2. 事实来源：
   - 原始请求：`ApplicationStore` 任务快照 `intent_text` + `request_id`；任务必须存在、归属当前 user/round、`session_id` 与上下文一致、非终态。
   - 动作事实：`TransferSnapshots.resolve`（user/round/task/action/operation/action_revision 全等才会返回）。
   - 收款人历史：`BankGateway.verify_payee`（B04）+ `list_transactions`（B08，本人账户、180 天窗口、只读出账），输出 `saved` + `prior_outflows`；判定归检测器。
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
- 2026-10-19 实施与合并（[PR #167](https://github.com/DrErwin/hackerthon-bank-agent/pull/167)：`683e314` → 返修 `a12caab` → 复审返修 `454f6cc` → squash `52d5637`）：新增 `risk_inputs.py`（`TrustedRiskInputs.resolve`、`RiskInputs`/`RiskFact`、`RiskDetector` 接缝、十类绑定拒绝、不透明 `evidence_ref`）、`risk-inputs-seam.md`、`test_risk_inputs.py` 12 例。实数（worktree，`app.__file__` 自证）：`pytest app/agent_platform -q` → **158 passed**；返修后全量后端一次运行 **716 passed / 2 failed**，两项为 `app/services` 超时预算用例（单跑 2 passed，[Issue #166](https://github.com/DrErwin/hackerthon-bank-agent/issues/166) 已登记的 Windows 计时抖动），PR CI（Linux）绿；合并后 main 上 `test_risk_inputs.py` 12 passed。
- 2026-10-19 独立审查两轮（子代理，AI、非 Ringo 真人）：
  - 首轮（`683e314`）**不通过**，1 致命 + 2 必修 + 若干建议：P0 = `DemoSecurityPolicy` 要求 `checked_signals` 覆盖全部 14 维（先于信号分类），而接缝要求未检查维度不得写成 checked；如实检测器会让每笔写入暂停，「合法对照完成/高风险 BLOCK」证据只成立于自称已检查设备维度的替身，自相矛盾；P1 = `familiar` 恒真不可表达「不熟悉」、缺无样本/手工收款人/终态任务等回归（变异 M2 未杀，另 M1/M3 杀）。
  - 返修（`a12caab`）：事实改为描述性 `payee_history`（`saved` + `prior_outflows`），补 8 类绑定/unknown 回归与 `fact_backed_detector` 暂停用例，`repr` 隐藏原文与账号、`from None`、provenance 与常量清理；文档把 P0 登记为安全侧待决（接缝 §4.1、spec §3.1）。
  - 复审（`a12caab`）**有条件通过**，M2/M4/M5 全部被杀；唯一必修 = 合并前把 P0 正式交给 Ringo（§4.1 未合入即等于没登记）→ 已发 [Issue #160 回帖](https://github.com/DrErwin/hackerthon-bank-agent/issues/160#issuecomment-6268456610)，并补「仅设备维度未检查即暂停」隔离用例、`saved + prior_outflows=0` 回归、接缝文档摘要口径修正（`454f6cc`）。
- 2026-10-19 结论：本票交付完成（接缝 + 输入路径 + 证据）；**P0（unknown 与 `checked_signals` 映射、设备事实来源）归安全侧/PM 决定**，决定前 [02](02-detector-assembly-and-fixture-removal.md) 保持 blocked，`transfer_fixtures` 只作流程对照。
