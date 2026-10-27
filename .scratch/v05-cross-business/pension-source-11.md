# 养老金退订选择页来源说明：票 11 最小规格

Status: implemented_pending_review
Owner: Erwin（v0.5）；执行 frontend_acceptance 子代理，顺序切换 Cross 单目录
Accepted by: Erwin，通过 2026-10-27 非比赛资料任务授权及中控明确后继分派
Accepted at: 2026-10-27
Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../v05-cross-linkage/packages/03-cross.md)
Directory: backend/app/modules/cross/

## 问题与结果

根代理真实 HTTP 养老金 P01 在前置退订选择页观察到“账单对比还在查询中”，但本场景读取本月明细 bills_details 已成功，并未创建减支用的月度账单比较。共用选择页无条件读取减支专用 state.bills，把没有该比较误说成查询未结束。

原证据：根工作树 `.mnemon/v05-http-acceptance/20261027/http-live-d7818f4d3f04/observations.jsonl` 第 12 行，父任务前缀 `5be1`；只读保留，不改写为成功。根代理负责用新代码的真实 HTTP 前置页复核。

## 最小方案与验收

- PS01：只有 pension_mode 的签约选择页使用“以下可退订项目来自银行签约盘点。”，来源对应实际签约清单，不再声称账单比较等待。
- PS02：减支选择页继续原账单比较、失败及等待说明；不修改 `_evidence_line`。
- PS03：选项、任务步骤、业务确认、资金规则、路由和生命周期保持原实现；不补新的查询或自造账单结果。

## 验证与边界

复用已有养老金编排和入账/去向检查，另运行既有减支账单失败说明单例。低影响文案不新增逐字镜像测试，不运行完整 Cross 127；真实 HTTP 说明由根代理在原路径复核。实现仅 Cross 与本组过程材料，独立 PR 交根代理两轴；不动前端、公共契约、比赛资料或浏览器，不自合并。

## 实际局部结果（2026-10-27）

在 main `9b54d4e3` 后继分支运行既有 `test_cross_pension.py`、`test_pension_contract_inputs.py` 和 `test_cross_expense.py::test_s02_bills_failure_is_reported_and_the_flow_still_runs`：**17 passed / 15.94s / exit 0**。使用本机已有 Python 环境与隔离临时数据；这些是模块/平台接缝检查，包含测试替身，不是本轮真实 HTTP/模型/页面验收。

`git diff --check` 通过；运行代码仅 `_ask_pick` 的一处说明分支，`_evidence_line` 无差异。未新增测试、未跑完整127，未执行浏览器或比赛资料工作。根代理独立两轴和真实 HTTP 文案复核待进行，原失败记录保留。
