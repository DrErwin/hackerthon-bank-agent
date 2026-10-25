# 账单入口修复的跨目录回归交接

日期：2026-10-25。仅记录，不修改提供方目录。

## 平台线：旧缺口断言需适配

提供方目录：`backend/app/agent_platform/`（Erwin 平台执行线）。
最小复现：在本票分支 backend 下运行 `python -m pytest -q app/agent_platform/test_cross_runtime_wiring.py::test_real_composition_mounts_cross_and_traces_children`。
实际：第111行断言账单子任务 status=failed；修复后真实工厂返回 succeeded，断言失败。旧注释明确以账单 typed-input gap 失败为预期。
建议：平台票将本断言改为验证成功及真实 scope、银行来源/对比依据；保留本测试原有任务关系、订阅清单和追踪验证。更新属于平台单目录票，不在本票跨界修复。
基线复核：未含账单修复的 transfer worktree（origin/main a1e8889 + 本轮转账呈现改动）同一用例 1 passed。转账呈现不影响该只读账单流程。
依赖：本账单 PR #284 可供中控审阅；合入前由平台线安排最小断言适配及本用例复验，否则全量不会绿色。真实页面/模型 E2E 仍另验。

## 银行网关线：全量中的短超时失败

提供方目录：`backend/app/services/`（Erwin 底座）。全量保留失败事实，不以单跑替换：
- `app/services/test_bank.py::test_timeout_returns_unknown_then_original_result_becomes_visible` 第141行，20ms 超时配置下同 operation_id 重放得到 QueryFailure，而非已查到的成功结果。
- `app/services/test_subscriptions.py::test_gateway_cancel_timeout_is_unknown_and_b14_finds_the_bank_result` 第182行，同类20ms配置重放返回 QueryFailure。
最小复现：分别运行上述两个精确 pytest node ID，或 `python -m pytest -q` 复现原全量上下文。
独立复核：未含账单修复的 transfer worktree 两项 2 passed in 8.95s；账单 worktree 两项再次单跑 2 passed in 0.92s。说明本次单跑未重现，不能宣布根因已修复；全量并行负载/短时限相关性仅为推断。
建议：底座线保留原超时语义，独立核查测试时限和本机负载，勿在账单或转账目录放宽银行重试/未知规则。

## 验证总账

- 全量后端：3 failed, 1603 passed in 891.42s；未认定通过。
- 账单模块：353 passed；新增 typed 文件18 passed（含6项真实 Harness/安全执行器/隔离 SQLite/种子银行集成）。
- mockbank 评测回归：14 passed。
- 本地链接、差异空白与账单 Python 编译通过。
- CI：GitHub job 因账号付款/spending limit 未启动，没有测试执行证据。
- 模型规划/LOW风险策略为测试替身；未执行真实模型、HTTP、页面 E2E 或真人接受。
