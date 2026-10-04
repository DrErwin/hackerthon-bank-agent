# 01：跨场景代表性评测用例

Type: 评测
Status: resolved
Owner: 周恩宇（Ethan / @zhouey314-cloud）
Ticket ID: v04-ethan-cross-eval/01
Package: [transfer-agent-framework/packages/04-v04-eval-preparation：后续业务评测准备](../../transfer-agent-framework/packages/04-v04-eval-preparation.md)
Spec: [v0.4 跨场景联动评测准备规格](../spec.md)
Directory: `evals/cross/`
Blocked by: None

## 业务目的

把冻结的 06 联动 PRD 转成首批可检查 Eval，验证 Agent 能在 A/B/C 三个场景中自主编排，但无法绕过预算、权限、确认、真实结果和公开能力边界。

## 交付

- 在 `evals/cross/` 新增代表性用例文件。
- 覆盖任务 A 生日礼物、任务 B 用户自设限额、任务 C 收入分配，以及共性编排/失败恢复。
- 每条写清输入/起始状态、预期过程、预期结果与通过标准、公开能力依赖。
- README 链接到本轮代表性用例并标明后续扩充计划。

## 验收

- [x] A/B/C 各至少有正常、缺信息/边界、失败或未知结果用例。
- [x] 覆盖确认失效、预算版本、部分成功、重复执行防护和外部注入边界。
- [x] 只依赖 transfer / bills 等公开能力，不引用私有工具或数据。
- [x] 没有提前实现 cross 业务代码或修改公共契约。
- [x] PASS/FAIL 可由公开状态、模拟银行/订单结果及用户回执客观判断。

## 公开能力依赖

- 02 账单公开能力：真实消费统计。
- 01 转账公开能力：任务 C 多笔资金动作。
- 模拟银行 / 外部服务 Mock：资金冻结/释放、商品查询、下单、订单状态与付款结果。
- 公共安全/验证：确认、身份验证、权限与阻断。

## Comments

- 2026-10-04：周恩宇明确领取交付包 04 并开始本评测准备票。

- 2026-10-04：本轮 AI 规范与规格审查及修正后，[PR #62](https://github.com/DrErwin/hackerthon-bank-agent/pull/62) 已合入；23条代表性用例已交付，链接、编号、内容与差异空白检查通过。仅验收文档准备；全部用例待运行，不代表模块实现、完整评测或真人专业安全验收。
