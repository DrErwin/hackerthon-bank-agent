# 01：账单公开工厂接收类型化输入

Ticket ID: v05-bills-cross-input/01
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [账单类型化输入入口](../spec.md)
Type: 开发
Owner: Erwin
Directory: `backend/app/modules/bills/`
Status: review_pending
Blocked by: None（现行公共模型、PR #264 平台派发已合入）
Accepted by: Erwin 授权执行对话
Accepted at: 2026-10-25
Core scenarios: BI01—BI06，见 spec
Verification: 公开工厂精确保留结构化参数；真实 Harness + 安全门 + 隔离种子银行验证实际依据及零写入；覆盖拒绝、重试、恢复及旧聊天回归。

## Acceptance criteria

- [x] 三种输入分别经各自注册工厂运行，summary/details/comparison、异常三模式、报告目的符合既有服务契约。
- [x] 银行事实、读取权限、失败语义、原任务重试/恢复/重放未绕过。
- [x] 普通聊天路径不回归，其他能力输入和裸字典拒绝。
- [x] 独立子代理审查规范与原始规格，修复必须项，代码 PR 交中控排队合并。

## Delivery record

- 代码提交：50c1ed2；完整参数直接交现有服务，未改公共契约或安全门。
- 局部验证：`app/modules/bills/test_typed_entry.py` 18 passed，含 6 条真实 Harness 子任务 + 隔离 SQLite/安全执行器/种子银行路径，各含权限拒绝及银行零写入；规划器与 LOW 风险策略为替身。
- 独立 code-review：Standards PASS（0 必须项），Spec PASS（0 必须项）；规格审查另独立复验 12 passed, 6 deselected。审查基线 e9517b8...50c1ed2。
- 账单目录回归：353 passed。全量后端 1603 passed / 3 failed（891.42s），未通过：平台旧断言仍要求账单入口失败；两项20ms网关重放超时失败，单跑复核均通过但未替代原全量失败。
- [PR #284](https://github.com/DrErwin/hackerthon-bank-agent/pull/284)，CI 未启动：GitHub 注释指出账号付款或 spending limit 阻止 job 启动，并无执行步骤/测试日志；不记为 CI 通过。链接检查本地通过。真实模型/HTTP/页面 E2E/真人接受未执行。
- 跨目录阻塞及最小复现：[集成交接](../research/integration-handoff.md)。平台需按真实账单成功适配旧断言；网关短超时失败由底座线核查。本地链接/差异空白/账单编译通过，mockbank 14 passed。
- 可解锁：减支统计证据、养老金流水依据的联合 E2E；实际 E2E 接受仍由对应联调票验证。
