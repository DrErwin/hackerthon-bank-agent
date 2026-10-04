# 01：账单代表性评测用例

Type: 评测
Status: resolved
Owner: 周恩宇（Ethan / @zhouey314-cloud）
Ticket ID: v04-ethan-bills-eval/01
Package: [transfer-agent-framework/packages/04-v04-eval-preparation：后续业务评测准备](../../transfer-agent-framework/packages/04-v04-eval-preparation.md)
Spec: [v0.4 账单评测准备规格](../spec.md)
Directory: `evals/bills/`
Blocked by: None

## 业务目的

把冻结的 02 账单 PRD 转成首批可检查 Eval，使 v0.4 账单实现从一开始就有业务验收标准，而不是实现后再补测试。

## 交付

- 在 `evals/bills/` 新增代表性用例文件。
- 覆盖分类统计、异常识别、报告、导出权限四组行为。
- 每条写清输入/起始状态、预期过程、预期结果与通过标准、公开能力依赖。
- README 链接到本轮代表性用例并标明仍需在 v0.4 扩成完整规模。

## 验收

- [x] 正常、边界、异常、权限/导出均有代表性用例。
- [x] 关键冻结规则均至少有一条正向或反向验证。
- [x] 没有真实个人数据。
- [x] 没有提前实现 bills 业务代码或修改公共契约。
- [x] 用例可直接映射到 PRD/契约，PASS/FAIL 可客观判断。

## 公开能力依赖

- 模拟银行 / 银行接入层：本人交易查询。
- 02 本模块未来公开能力：消费分类统计、异常交易识别、账单报告生成。
- 安全/验证公共能力：敏感明细导出前的身份验证。

## Comments

- 2026-10-04：周恩宇明确领取交付包 04 并开始本评测准备票。

- 2026-10-04：本轮 AI 规范与规格审查及修正后，[PR #61](https://github.com/DrErwin/hackerthon-bank-agent/pull/61) 已合入；21条代表性用例已交付，链接、编号、内容与差异空白检查通过。仅验收文档准备；全部用例待运行，不代表模块实现、完整评测或真人专业安全验收。
