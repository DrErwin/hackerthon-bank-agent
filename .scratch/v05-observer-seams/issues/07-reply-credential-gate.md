# 07 回复话术门槛：可说明「验证码别给人」，但不得含凭据值

Ticket ID: v05-observer-seams/07
Package: 无独立交付包——v0.5 平台遗留收口（[spec](../spec.md)），来源 [Issue #216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)
Spec: [v05-observer-seams/spec.md](../spec.md)
Core scenarios: S1（写清可疑点与下一步）、S4（输出不得带凭据）
Type: 开发
Owner: Erwin（AI 代行实施与审查，非真人审查）
Directory: `backend/app/agent_platform/`
Status: Todo
Blocked by: [v05-observer-seams/01](01-untrusted-data-seam.md)（同一目录的接缝已合入）
Source issue: Issue #216

## 背景（票 06 实施中发现）

`AgentHarness._check_intent_text` 对**模型回复文本**里出现「验证码 / 短信码 / 密码 / otp…」任意字样就抛 `CREDENTIAL_IN_REQUEST`，于是「这条短信有验证码，别告诉任何人，请通过官方渠道核实」这类**正确且必要**的回复被判失败，消息任务以 `MODEL_UNDERSTANDING_FAILED` 结束、用户拿不到解释。Demo 切片（S1/S2）与真实模型批次因此不可用；这是产品缺陷，不是评测脚本问题。

安全目标没有变：认证秘密（验证码值、密码、口令、otp 值）不得进入模型、不得写进任何输出/日志/消息。需要放开的只是「提到『验证码』这个词并给出防骗建议」。

## 交付物

1. `AgentHarness` 区分两条门：
   - **用户输入**仍用 `_check_intent_text`（请求里出现凭据字样 → 拒绝，保持现状）。
   - **模型回复**改用「凭据值」判定：复用 `backend/app/audit/output_guard.py` 的 `probe_output(text).findings`，只有 `credential` 命中才判失败（保留 `CREDENTIAL_IN_REQUEST` / `MODEL_UNDERSTANDING_FAILED` 的 fail-closed 语义），纯文字提醒（「不要向他人透露验证码」「别把密码给别人」）不再误伤；通过后仍执行既有 `redact(..., free_text=True)` 后才进入结果。
2. 不新增契约字段/事件类型；不改 `backend/app/audit/` 与 `backend/app/security/`；不改变既有「金额非法」「业务提案」等拒绝路径。

## 验收（E2E，真实 Harness + 真实审计/存储 + 替身或真实规划器）

| 编号 | 场景 | 通过条件 |
|---|---|---|
| G01 | 解释型回复 | 替身规划器返回「这条短信里的验证码不要告诉任何人，请通过官方渠道核实」→ 任务照常得到 `ReplyOnly` 并落库发布，不出现 `MODEL_UNDERSTANDING_FAILED` |
| G02 | 带凭据值 | 回复含「验证码是 123456」→ 仍按失败处理（不发布该文本；审计 `model.finished` 失败），数据库中不出现 `123456` |
| G03 | 无标签 6 位码 | 回复含「登录码 135790」→ 仍被判定为 credential 并失败（与票 03 探针口径一致） |
| G04 | 既有路径不回退 | 普通转账提案、金额非法拒绝、等待期回复、会话摘要注入等既有 `backend/app/agent_platform/` 用例全绿；全量 `pytest -q backend` 不降低 |
| G05 | 回复仍脱敏 | 通过门后的回复仍走 `redact(..., free_text=True)`，已知手机号/账号/姓名被掩码 |

## 备注

- 本票是票 06 真实模型批次的前置：不修则「贴可疑短信问真假」永远拿不到解释。
- 安全侧留痕：AI 代行实施与审查、非真人审查；该门收窄只针对「文字提及」，凭据值仍 fail-closed。
