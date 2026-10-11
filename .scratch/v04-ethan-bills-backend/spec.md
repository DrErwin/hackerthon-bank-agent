# v0.4 Ethan 账单实施规格

Status: in_progress
Owner: 周恩宇（Ethan / @zhouey314-cloud）
Source package: [v04-bills/packages/01-bills-backend：账单业务能力与评测](../v04-bills/packages/01-bills-backend.md)
Baseline: 65d1a706941f336e1820d64a4f9b662acdc4584e（2026-10-11）

## Problem Statement

v0.4 已于 10-11 正式启动，周恩宇应从代表性评测准备进入账单后端实施。账单当前只有 README/AGENTS；既有21条核心例不能等同于可运行的三类业务。cross 已移至 v0.5，不在本轮实施。

## Solution

沿 BF01—BF07，先实现与真实银行接缝解耦的确定性统计内核，补覆盖和虚构流水；公共类型与 B08 落地后，接 L01 原任务流程，随后分别做 L02 异常、L03 报告及公共导出接线，路径就绪即联调。不能在账单目录复制公共契约、银行规则或安全系统。

## User Stories

1. 作为本人登录用户，我要按明确账户和期间查询消费，不用额外验证码。
2. 我要分清消费、退款、净消费与转账，不把冻结或利息混成消费。
3. 我要按七类看钱花在哪，无法归类时据银行标签进入其他。
4. 我要跨月退款只影响退款入账月，原消费月不被改写。
5. 我要在净消费为零或负数时看到正确金额，而非伪正常占比图。
6. 我要环比和同比使用正确且完整的对照范围；失败不能当零。
7. 我要只看某类明细，不被强迫先生成报告或做导出验证。
8. 我要用线索定位异常交易，多候选时由我选，而非AI替我猜。
9. 我要四类疑似异常有真实流水依据，不把疑似判成盗刷。
10. 我要报告只有本轮总览/分类/对比；月均按实际统计天数折算30天。
11. 我要报告卡片普通导出、敏感明细再次验证，不能借分享意图越权。
12. 我要查询中断后沿原任务恢复，不丢失范围、不编结果。
13. 作为前端协作者，我要收到可调用的账单形态与真实状态，而非占位接口。
14. 作为审查者，我要区分局部算术、公共能力、真实模型/HTTP/页面和专业安全的证据。

## Implementation Decisions

- 业务目录只修改 bills；评测只修改 evals/bills。一票一目录；同时最多两个未合PR。
- 复用冻结主契约 §5.3/§5.9，公共Pydantic定义由公共目录提供。本模块不再定义一套 BillScope/Transaction/SpendingSummary wire schema。
- [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91) 已交 Erwin：当前 gateway 无 B08，公共 bank/platform 模型尚缺账单类型。登记的是既定能力实现缺口，不是新增业务取舍。
- 内部统计值对象不是接口模型或授权证据；输入必须来自调用方已获准的成功完整B08读取。无访问银行、数据库、Shell、网络、资金写操作。
- 内部精确比率保留 Fraction，公共share_bps/change_bps序列化取整未明确处不自行定成新业务规则。
- 查询失败、缺任一账户或范围矛盾时不返回完整成功；记录数为0与计算结果为0分开。
- 仅私有统计内核就绪时 manifest 不暴露不可运行的公开能力，不虚发前端可联调信号。
- 当前用户明确要求按仓库要求完成并提交；此处记录本人启动，不代表Erwin已批准每张新票或Ringo已审查。

## Testing Decisions

最高现有可用验证点是私有统计内核加手算黄金流水；这只是 BF01/BF03 的算术子断言。后续最高验证点改为注册后的L01/L02/L03及真实平台原任务入口，再接HTTP/真实模型/页面。

局部用例覆盖七类、流入流出、退款、跨月、净额非正、对比、完整空集、缺账户、半开范围、截至时间、严格整数分、精确月均和不重复计数。测试不输出真实个人数据，不以全绿单测冒充业务验收。

核心场景统一引用 [v04-bills BF01—BF07](../v04-bills/spec.md)，不重新编号；覆盖表和细化用例放 evals/bills；原核心21条保留编号及历史。

## Tickets

| 完整票号 | 工作 | 目录 | 开始条件 |
|---|---|---|---|
| [v04-ethan-bills-backend/01](issues/01-statistics-core.md) | L01统计内核与局部测试 | backend/app/modules/bills/ | 可立即执行 |
| [v04-ethan-bills-backend/02](issues/02-coverage-and-fixtures.md) | 覆盖规划、流水fixtures与算术黄金样本 | evals/bills/ | 数据/文档可并行；样本运行需01 |
| [v04-ethan-bills-backend/03](issues/03-public-summary.md) | L01真实取数、注册与原任务恢复 | backend/app/modules/bills/ | 01合入、Issue91公开接缝提供 |
| [v04-ethan-bills-backend/04](issues/04-anomalies.md) | L02定位与四规则 | backend/app/modules/bills/ | 03公开读取路径、对应公共类型 |
| [v04-ethan-bills-backend/05](issues/05-report-export.md) | L03受控报告与导出接线 | backend/app/modules/bills/ | 03、公共资源/验证入口 |
| [v04-ethan-bills-backend/06](issues/06-full-business-eval.md) | 完整业务自动化与运行证据 | evals/bills/ | 02/03/04/05按路径就绪逐步验证 |
| [v04-ethan-bills-backend/07](issues/07-integration-evidence.md) | 前端/HTTP/模型联调证据 | evals/bills/ | 可运行公开路径、前端槽及合法模型配置 |

## Out of Scope

cross/v0.5、完整前端代码、银行共享实现、安全检测器、公共契约修改、代签专业安全结论、擅自合并代码PR。联合收口复用 [v04-bills/02](../v04-bills/packages/02-v04-acceptance.md)，不代Erwin建立新验收层。

## Further Notes

已读取仓库固定来源 d81f3a183412e71a5b1e84ca21bc1a35eea03a60 的 to-spec/to-tickets/implement/code-review 内容作流程参考。本次执行环境为ChatGPT工作容器与GitHub连接器，未安装/调用用户Mac的Codex slash Skill，不能记为本机Skill检查通过；无独立并行审查代理，当前仅执行者自查，独立审查留PR。无法联网clone整个私有仓库，局部代码测试不等于整个仓库回归。

规则未明处：06:00恰好端点及展示比率取整保留待确认，见 evals/bills/gaps.md 后续交付。不用其他常识补成项目既定规则。
