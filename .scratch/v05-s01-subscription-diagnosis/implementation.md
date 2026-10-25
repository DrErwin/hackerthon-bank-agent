# Issue #302 实施证据

2026-10-25；票 [v05-s01-subscription-diagnosis/01：明确单项停止扣费不得静默降级为盘点](issues/01-untyped-action-clarification.md)；[规格](spec.md)。

## 先失败后修复

- 公开注册工厂回归 `test_explicit_stop_reaches_confirmation_without_executing`，输入“请帮我停止优酷的自动扣费”：修复前 expected waiting_approval / actual succeeded，1 failed in 4.18s；正向修复后 1 passed in 2.93s。
- 增加否定回归 `test_negated_cancellation_stays_read_only_even_under_cancel_candidate`：“不要取消优酷，只查询扣费”；在仅正向修复时 expected succeeded / actual waiting_approval，1 failed in 4.96s；补否定/只读边界后两个测试 2 passed in 2.89s。
- 上述为本轮控制台观察，无独立归档的失败日志；旧 `probe-result.json`、`existing-tests.xml`、`reproduce.py` 保留原失败观测，不重跑覆盖。

## 首轮验证

从本实施 worktree 的 `backend/` 运行，共 104 passed in 20.58s：

```powershell
D:/hackerthon-bank-agent/backend/.venv/Scripts/python.exe -m pytest -q app/modules/subscription/ app/agent_platform/test_subscription_runtime.py --tb=short --junitxml=../.scratch/v05-s01-subscription-diagnosis/implementation-tests.xml
```

- 首轮新公开工厂回归 27 项：有代表性的停止/不续费/续订、否定/只读/询问/未明确办理、目标不足/批量逐项选、确认/验证/幂等。使用 FakeBank/FakeGate，不冒充真实银行。
- 新集成回归 6 项：真实 Harness、安全门、执行器及每例隔离 SQLite/MockBank；两种正向表达确认前零写入，验证后一次取消，重复恢复不重复写；三种否定/询问/未明确办理在模型强选 cancel 时仍无写入；既有共享屏幕胁迫信号仍被阻断。
- 新高风险用例初次预期写为 HIGH_RISK，实际既有公共错误为 HIGH_RISK_BLOCKED（source=security，upstream_code=HIGH_RISK）；已按既有契约纠正新测试预期，没有改风险/策略/旧测试。
- 既有订阅与平台订阅接口回归一并通过，含 typed List/Cancel、取消、权限拒绝、银行拒绝和未知原号恢复等。

模型为脚本规划器，风险为既有 server-test fixture；没有新真实模型、React 页面或完整 S01 验收。没有共享数据库、没有真实银行。规范/规格独立审查与 PR / CI 结果待填；不得沿用其他票 CI 例外，不自行合并。

## 独立审查首轮与修复

固定 `f77c07fede5c0b3ca393862c0dce3efd75095918...dced44b8d8d263330b79a71c9af54f899acbec97`，两个独立只读子代理均发现必须项：Standards 两项（否定范围、旧“都关”回归），Spec 三项（前述两类及普通查询/状态）。公开工厂复现均无 fake 写，但错误进入确认仍是意图缺陷，不能以零写入掩盖。

补入实际失败回归：旧“把自动扣费都关”先为 1 failed / 3 passed in 10.65s；审查给出的 7 个否定/查询/状态案例先为 7 failed / 14 passed in 6.30s。然后按语义类别修复：否定作用跨同一分句的对象，目标中的“不需要的”不作为否定指令；读操作与询问保持盘点；旧批量“都关”继续单选。并补状态陈述、不同问法及否定目标描述的正向对照。先前 104 项结果属首轮，最终复验和复审另列。

本分支已 rebase 到最新 main `f77c07fede5c0b3ca393862c0dce3efd75095918`；855497f 至 f77c07f 仅共享文档变化，无产品差异。共享文档由中控提交，本分支不修改。

## 修正后定向复验

同一命令：**120 passed in 37.88s**，JUnit [implementation-tests.xml](implementation-tests.xml) 为最终这轮。新增公开工厂测试现为 43 项，新增真实 Harness/隔离 MockBank 集成仍为 6 项；其余为未修改的订阅与平台订阅回归。新增的查询/否定/旧批量失败样例全部通过。语法解析、本票 Markdown 文件目标、差异空白检查通过。没有运行无关全量、真实模型或页面。
