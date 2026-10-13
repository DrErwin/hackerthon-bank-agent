# bills —— 账单分析

负责人：周恩宇（Ethan / `zhouey314-cloud`）。v0.4 做账单三类能力及 BF01—BF07；跨场景在 v0.5。

依据：[02 PRD](../../../../docs/prd/02-账单分析-PRD-2026-09-23.md)、[公共契约 §5.3/§5.9/§6.11](../../../../docs/contracts/公共契约-2026-09-23.md)、[实施票 01](../../../../.scratch/v04-ethan-bills-backend/issues/01-statistics-core.md)。

## 当前增量：私有统计计算，不是完整账单服务

- `_statistics.py` 只进行确定性算术：消费/退款/净额、七类、转入转出、对比、月均、明细筛选。
- 七类码直接来自 `app.contracts.common.Category`，不重新定义公共枚举。
- `LedgerRow` 保留退款原单编号与时间。`assemble` 用当前范围及补充的已获准 `original_batches` 解析原消费类别；历史原单只作证据，不重复计入本期金额。无原单、错误账号/时间或矛盾事实时停止，不猜类别；历史取数仍由后续 L01 经 B08 办理，本内核不联网。
- `select_rows` 按已解析的 `category` 过滤；`nature` 只决定消费/转账等金额口径，不覆盖明细标签。
- `share_bps/change_bps` 在最后一步从精确比例四舍五入，占比不强凑 10000（§6.11）。按照书面 §5.3，净消费非正或出现负类别时不输出饼图比例；零净额类别与转账也为 null，兼容公共模型约束。
- `manifest.py` 是票 01 的离线目录清单：无工具、无副作用、无已注册能力。运行导出与能力注册留票 03，不把空清单冒充接口可用。

## 公共依赖现状（2026-10-13 核对）

[Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91) 已关闭：公共 `Transaction`/L01 模型及 `BankGateway.list_transactions` 已合入；`BillReport` 也已提供。**不是继续等待 B08 实现，而是本模块尚未完成公开流程接线。** 报告/导出与平台接入的新增工作由 Erwin 的 `v04-platform` 工作线负责，是否可调用以合入和接口证据为准。

## 验证边界

```sh
# 从仓库根目录（按 backend/README 安装开发依赖）
PYTHONPATH=backend python -m pytest -q backend/app/modules/bills/
```

本增量验证 BF01/BF03 的算术子断言及明细过滤，不关闭 BF01—BF07。97 项模块测试覆盖原单类别不同、跨月来源、原单缺失/冲突、类别与交易性质不同、比例取整等；真实 L01、权限、对话澄清、原任务恢复、L02/L03、HTTP/模型/页面仍需后续票验收。

是否触及公共契约或安全：**只引用，不修改**。不得直读银行私有存储，不新增授权标记，不合并代码 PR。此次审查反馈逐项答复见 [PR #92 评论](https://github.com/DrErwin/hackerthon-bank-agent/pull/92)。
