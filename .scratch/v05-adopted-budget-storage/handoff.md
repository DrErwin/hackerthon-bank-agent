# 交中控 / cross 的接口说明

实施票：[v05-adopted-budget-storage/01：已采用个人预算持久化与改版](issues/01-adoption-records.md)

## 就绪接口

实现位于 `ApplicationStore`；完整调用示例与参数语义见 [storage README 的采用预算段落](../../backend/app/storage/README.md#已采用个人预算v05-adopted-budget-storage01应用库-v6)。原公共 `AdoptedBudget` / `BudgetRef` 不变。

```python
from app.contracts import BudgetRef

# verified_record 由 cross 完成真实 F10 adopt / 原交互 / 当前计划 / 快照核对后生成。
# task 是核对时读取的同一来源任务，actor 来自可信上下文。
saved = application.adopt_budget(
    actor.user_id, actor.demo_round_id, verified_record,
    expected_task_revision=task.revision,
)
exact = application.get_adopted_budget(
    actor.user_id, actor.demo_round_id,
    BudgetRef(budget_id=saved.budget_id, version=saved.version),
)
candidates = application.list_adopted_budgets(actor.user_id, actor.demo_round_id)

# 改版：同 budget_id、新 adoption_interaction_id、连续 version，重新核对完整快照。
revised = application.adopt_budget(
    actor.user_id, actor.demo_round_id, revised_record,
    expected_task_revision=current_source_task.revision,
    previous_version=saved.version,
)
occupations = application.list_budget_commitments(
    actor.user_id, actor.demo_round_id, revised.budget_id,
)
```

初次 version=1、previous_version=None，改版为旧版+1。返回值是 `AdoptedBudget`；同交互精确重放返回原版本的当前状态，可能已 superseded，调用方不能把重放返回值直接当作当前活动预算。历史准确引用也可能 superseded。候选列表默认只列 active，可传 include_superseded=True 追溯全部版本。

`ValueError` 表示范围/来源任务不符、任务版本改变、交互异参重放、版本跳号或活动版本冲突。cross 需按真实情况回到原任务澄清/刷新，不可捕获后另造 budget_id 或增大额度。存储没有增加公共 ModuleError 枚举或 HTTP。

## cross 后续必须承接

1. 接入真实 adopt / modify / decline，验证原 F10 交互、plan_revision 和 scope/purpose/personal_limit_fen 快照；在同一来源任务版本下调用存储。expected_task_revision 是应用任务版本，不是 plan_revision。
2. 按可信 user/round 取候选，按真实付款账户、消费日期和用途核验；显式引用须核验，省略引用也须查候选，多条重叠不能挑宽松限额。存储返回原 scope，不替业务选择。
3. 保存生日 task_id 与 BudgetRef 的绑定，保留个人总限额和本次 birthday budget_fen 的不同意义。刷新 L01 消费事实、计算剩余、冻结前 pending、未知只回查、交易消费与占用不双算由原业务票落实。
4. 新版采用不会删除同 budget_id 各版本未关闭占用；读取占用仍用原 list_budget_commitments。这里没有修改原占用登记/更新语义。
5. 重置按新 demo_round_id 隔离：旧轮次记录保留追溯，新轮次默认无旧采用状态。同轮次重开数据库保持采用状态。

## 尚待决定与验收

本存储范围内没有新增待裁定业务语义。具体用途匹配/重叠澄清、预算绑定和事实更新应由 cross 按已批准规则实施；若发现规则不足交中控裁定，不能由存储自行编造。生日预算 E2E、HTTP/React、真实模型和真人安全签核均不属于本票已验证结果。

本票只交代码与接口，没有修改共享项目跟踪、completion 或包状态；合并和后续派发由中控执行。
