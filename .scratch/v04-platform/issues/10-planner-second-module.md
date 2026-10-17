# 10：规划入口支持第二业务模块（真实 planner 可产账单提案）

Ticket ID: v04-platform/10
Type: 开发
Owner: Erwin
Directory: backend/app/agent_platform/
Status: resolved（[PR #139](https://github.com/DrErwin/hackerthon-bank-agent/pull/139) squash `15cf0ad` 合入 main，2026-10-17；双轴独立子代理审查〔AI 审查、非真人〕均判可合、变异 2 杀 1 活〔存活=提示词行无自动化覆盖，README 已声明、护栏留票 05/评测〕；[Issue #134](https://github.com/DrErwin/hackerthon-bank-agent/issues/134) 已关闭）
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
- 2026-10-16 实施与验证（[PR #139](https://github.com/DrErwin/hackerthon-bank-agent/pull/139)，rebase 后 `5998d44`，基于 main `221d95c`）：改动收敛在 `model.py`（README 同步）——`propose_transfer` 的 `args_schema` 换成 `TransferProposal`（`capability_name` 成为模型可填字段，默认 `transfer.start_transfer` 保证转账不填时行为不变）；提示词按 `public_catalog()` 动态列举能力；`select()` 前置改 catalog 非空、后置拒绝 catalog 外能力名。**测试命令与输出**（仓库 venv，固定 SHA worktree）：`pytest app/agent_platform -q` → **125 passed**（新增 5 用例）；`pytest -q` → **601 passed**（含 #138 契约测试）。**交付 4 措辞澄清（Spec 轴审查核实）**：harness 无需改动——`capability_name` 分发与 `StartTransferInput` 模块无关信封已在票 03/08 落地（`harness.py:466-475`），真实账单 `entry.start` 正是从 `intent_text` 自解析（`modules/bills/entry.py:150-171`），交付 4 由票 03/08 + 本票工具面共同满足；E2E 用例 `test_bill_task_is_created_from_the_message_entry_by_the_real_planner` 实证账单任务从消息入口创建。HTTP 层 `module=bills` 字面断言留给票 05 真实接入（api 目录）。工具名保留 `propose_transfer`（docstring 通用化）：改名波及 5 处后端断言且使真实模型转账基线漂移。
- 2026-10-17 合并与审查记录：审查版 `5998d44`（合前 rebase 为 `17af9b4`，纯文档增量、内容逐字节相同，结论沿用）。Spec 轴可合（交付 1—3 逐条落地、"不动 harness"声明独立核实、转账断言零放松）；Standards 轴可合（harness/contracts/security 显式零 diff、125+65 passed、变异 3 组〔a 工具面回退 3 红 22 绿——旧转账用例全绿即兼容设计意图；b 删后置拒绝 1 红精确击中；c 删提示词清单行 32 全绿→**无自动化覆盖**，登记 P3〕）。合并 squash `15cf0ad`，[Issue #134](https://github.com/DrErwin/hackerthon-bank-agent/issues/134) 关闭。**遗留**：提示词能力清单行/真实 LLM 路由行为无自动化护栏——票 05 真实接入时以评测集补（含转账真实模型复跑建议）。
