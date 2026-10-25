# S01/P01 数据入口局部验证 · 2026-10-25

实施票：[v05-cross-e2e/01：减支核心与关键异常 E2E](../../.scratch/v05-cross-e2e/issues/01-expense-reduction-e2e.md)的数据准备增量。分支`codex/v05-cross-e2e-01-fixtures`；基线main `9a479ea4414635772fdb723c02b0fc70b76a1a55`，含前端#286。只改evals/cross与本票过程记录，没有改前后端、共享跟踪、版本completion或#160。

## 已实际验证

- `python -m pytest evals/cross/test_case_runner.py -q`：10 passed（最终一轮9.75秒）。验证真实银行可查询的三签约、唯一5000入账、完整两月消费284/184元；源库/配置不变；空风险维度不补齐；旧批次不重置；真实运行时重启保留已办状态；配置错误不回显凭据。
- 两次实际CLI prepare：`XL-S01/data-20261025-01`、`XL-P01/data-20261025-01`，位于本worktree`.mnemon/v05-cross-e2e/`，各有自己的配置和银行库。
- 真实`build_runtime/create_app`构建后回读：两批各12条案例流水、唯一入账500000分、active签约`cross_keep/sub_001/sub_002`，bank_operations均0，风险配置摘要与源配置相同。
- 未启动HTTP进程、未发送模型请求、未开页面。测试中的网络调用禁止探针未触发；实际准备也只构建客户端，没有调用规划器。以上不是页面或真实模型E2E结果，没有生成通过率。

## 实际发现的跨目录缺口

| 缺口 / 提供目录 | 最小复现 / 观察 | 建议依赖 |
|---|---|---|
| 本人储蓄账户不可选 / `backend/app/modules/cross/` | 本案例真实bank.get_account(U1,A5)存在且余额0；bank.list_payees(U1)没有A5；pension._ask_destination只列payees，cross._dispatch对转账始终造SavedPayee | 交中控关联cross业务微票，提供OwnPayee及本人账户选择后再解锁P01；不把A5伪造成保存联系人 |
| 实际入账识别不兼容 / `backend/app/modules/cross/` | 用本案例真实B08返回的500000分入账，其direction为inflow；直接交给现有PensionFlow._income_transactions返回0行，因为只筛transfer_in；BillDetails直接使用Transaction契约 | 交中控关联cross业务修复，按现有inflow+nature字段识别，并按原5000选定入账验收；不改银行数据为非法direction，不换成按余额分配代替 |
| 养老金动作风险事实 / 安全与平台线 | 复制的本地配置未包含A1→A4、100000分动作匹配项；本人A5也不受现行SavedPayee型配置覆盖；即使补匹配项，联动原文的现行有界文本处理还需核实 | 提供适用且有来源的动作/环境事实或由PM裁定安全语义；保持未知暂停，不自动造低风险/checked维度 |
| 账单入口与平台旧断言 / bills、agent_platform原线 | 本票基线仍是旧账单入口；PR #284仍待合入及对应平台断言修复 | 修复合入后从真实S01入口开始，不用账单失败兜底计完整路径通过 |

入账方向问题的本地只读复现（不是端到端验证）：

```python
from types import SimpleNamespace
from app.modules.cross.pension import PensionFlow
# income是本案例真实bank.list_transactions返回的“养老金到账”Transaction。
state = {"step_state": {"bills_details": {"result": {
    "transactions": [income.model_dump(mode="json")]
}}}}
PensionFlow._income_transactions(SimpleNamespace(state=state))  # 当前实际为[]
```

以上缺口均未越界修复，未创建无明确接收人的GitHub Issue；中控负责关联/分派具体票。前两项是已批准业务的接入错误，不需要重定业务规则；风险未知语义如需变化则必须另行裁定。

## 交付状态

局部数据准备通过，原票完整E2E仍blocked。真实模型、HTTP、页面、200%、键盘、读屏、真机软键盘未运行；PM接受和Ringo本人签核未记录。独立规范/规格审查及PR在本票续派记录中回填。
