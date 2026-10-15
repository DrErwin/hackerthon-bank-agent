# 10：规划入口支持第二业务模块（真实 planner 可产账单提案）

Ticket ID: v04-platform/10
Type: 开发
Owner: Erwin
Directory: backend/app/agent_platform/
Status: open
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P01 账单任务在平台上创建（消息入口 → 意图路由 → 账单提案部分）](../spec.md)
Verification: 真实 planner（`DeepAgentPlanner`，非替身）按用户意图产出 `bills.summarize` 提案；含一条端到端用例证明账单任务能从消息入口创建（任务视图 `module=bills`）；转账路径回归（既有 planner / 意图 / #84 上下文摘要用例全绿）。局部验收 = 规划入口可选出第二模块能力；P01 场景通过以 [票 05](05-real-bills-integration.md) 真实接入后的端到端证据为准。命令与输出记入本票 Comments。
Blocked by: None（账单 L01 已在 main〔[PR #131](https://github.com/DrErwin/hackerthon-bank-agent/pull/131)〕；本票不依赖 L02/L03）
Source issue: [Issue #134](https://github.com/DrErwin/hackerthon-bank-agent/issues/134)

## 交付

1. **工具面**：给模型的提案工具参数 schema 补 `capability_name`（或等效机制），模型能按意图在已注册能力中选择——现状 `model.py:123` 的 `args_schema=_TransferFields` 只有转账三字段，`capability_name` 是代码默认值 `transfer.start_transfer`（`model.py:41`），模型没有字段可填。
2. **提示词**：去掉「仅转账」硬编码（`model.py:146`），按 catalog 描述当前能力集合；意图路由纪律与转账一致（只动嘴、缺字段追问、已有业务回原任务、超范围 reply_only）。
3. **catalog 前置**：`select()` 不再要求 `transfer.start_transfer` 必在 catalog（`model.py:119`），改为校验所选能力已注册。
4. **harness 输入构造**：start 侧按 `capability_name` / 模块构造对应输入（`harness.py:471` 现固定 `StartTransferInput`），账单走其模块入口的输入形状；不复制转账运行体系、不新建第二套底座。

## 边界与依赖

- 不改契约语义：`CapabilityCall.capability_name`（`contracts/platform.py:58`）与 `TransferProposal.capability_name`（`model.py:38-48`）已放开，本票只让模型侧能填、harness 侧能按模块用。
- 不在本票：生产装配注册真实 bills 工厂（票 05）；安全侧读账放行口径（[Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137)，Ringo）；L02/L03。
- 回归红线：转账提案路径、`reply_only` 语义、#84 受控上下文摘要注入不回归；替身 planner 的既有用法（评测缝 / API 测试）签名兼容或同步适配并在本票说明。

## Comments

- 2026-10-16：按 [PR #131 审查结论](https://github.com/DrErwin/hackerthon-bank-agent/pull/131#issuecomment-6198615597) 第二节第 1 条建立（[Issue #134](https://github.com/DrErwin/hackerthon-bank-agent/issues/134)）。账单线能否端到端跑通的关键路径，v0.4 硬截止 10-20 前优先。
