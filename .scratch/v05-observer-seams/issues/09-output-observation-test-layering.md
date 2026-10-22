# 09 输出观察用例分层：回复凭据由 Harness 先拦，出口探针用任务消息验证

Ticket ID: v05-observer-seams/09
Package: 无独立交付包——v0.5 平台遗留收口（[spec](../spec.md)），来源 [Issue #216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)
Spec: [v05-observer-seams/spec.md](../spec.md)
Core scenarios: S4（输出侧观察）
Type: 开发（用例适配）
Owner: Erwin（AI 代行实施与审查，非真人审查）
Directory: `backend/app/api/`
Status: Todo
Blocked by: [v05-observer-seams/04](04-api-output-observation.md)、[v05-observer-seams/07](07-reply-credential-gate.md)
Source issue: Issue #216

## 背景

票 07 把模型回复的凭据门收窄为「探针 credential 命中即 fail-closed」后，票 04 的 `test_d01_credential_reply_is_blocked_whole_and_audited` 前提失效：规划器回复「code 123456」在 Harness 层就被拒（`MODEL_UNDERSTANDING_FAILED`，不产出 assistant 消息），不再走到 API 出口探针，用例失败。这是**分层变化**，不是行为回退：凭据在更早的一层被拦住。

## 交付物（只改 `backend/app/api/test_output_observation.py`）

1. D01 改为**分层无关**断言：规划器返回含凭据值的回复 → 不论由 Harness 失败还是出口拦截，最终用户可见消息 / SSE / 数据库都不出现凭据原文，且请求不被当作已完成业务；不允许依赖某一层的具体错误形态。
2. 新增 D01b：**任务结果消息**携带凭据（模块 `result.message`，不经过规划器回复门）→ API 出口必须整条替换为固定安全文案 `OUTPUT_BLOCKED_REPLY`，写 `chat.message` denied + `OUTPUT_PROBE_BLOCKED` 证据（不含原文）。这是出口探针在凭据类别上的独立证据。
3. 保持 D02—D05 不变；整组用例在 `backend/app/api/` 与全量 `pytest -q backend` 下全绿。

## 验收

| 编号 | 场景 | 通过条件 |
|---|---|---|
| I01 | 分层无关 | 规划器回复含「code 123456」：消息/SSE/库中无原文；是否存在 assistant 消息均可，但不得出现未截断原文 |
| I02 | 出口独立证据 | 任务消息含「验证码是 246813」→ HTTP 读回固定安全文案、审计 `OUTPUT_PROBE_BLOCKED`、证据无原文 |
| I03 | 既有不回退 | D02—D05 与 `test_app.py` 全量通过；不改变生产代码路径（只改用例） |

## 备注

- 冻结点：本票只改测试；若发现生产路径缺陷回到对应实施票。
- 与票 07 的合并顺序：本票可在票 07 之前或之后合入（用例对两层都成立），用于解除 #223 的 CI 阻塞。
