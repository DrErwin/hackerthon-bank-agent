# 专用预算 F10 来源接缝（v05-budget-adoption-origin/01）

本接口只供认证后的后端代码调用，未注册为模型工具；不新增HTTP或公共契约字段。来源证明“认证专用输入针对哪份候选提交了哪项”，不证明实体真人，不等于cross已经采用预算，更不是购买/资金授权。实现只用现有任务快照、任务锁及update_task CAS；不需要新storage表。

## 平台接口

| 方法 | 后端输入/输出与边界 |
|---|---|
| `harness.resume_budget_input(trusted, *, input_request_id, interaction_id, selected_option_id)` | 原F10请求ID/交互/选项；身份只能由API当前认证上下文提供。新接受、原请求恢复及历史核实均在原任务锁内。返回不可变`BudgetInputCompletion`，其`.result`是原ModuleResult的副本、`.task_revision`是原完成投影版本、`.input_request_id`保持原请求。 |
| `harness.budget_input_record(trusted, input_request_id)` | API中断恢复分流用；核对当前有效会话及任务归属后返回持久记录副本或None。仅有历史记录不激活来源，不能将它作为cross的采用凭据。不要把该私有记录原样返回前端。 |
| `harness.budget_input_origin(trusted)` | cross在当前专用调用内读取；普通resume/模型choice、查询、历史核实、其他任务/线程和结束后的复制context均没有当前来源。返回frozen `BudgetInputOrigin`或None；`.facts`每次返回从不可变JSON解析的独立副本。 |
| `entry.reconcile_budget_input(trusted, origin, *, thread_id)` | cross06须实现的**只读**接缝：以原origin查自己的稳定attempt和准确预算事实，返回`BudgetInputRecovery(attempt_ref, original_result)`或None。不得新建采用、刷新版本或继续后续步骤。调用时当前来源始终被屏蔽。未实现该方法时平台不会把普通resume当历史核实捷径。 |

持久记录放在task.snapshot的`budget_input_origins`，按原input_request_id保存。固定字段包括origin_id/accepted_at、主体/会话/轮次/任务/run、原请求/交互/选项、accepted_task_revision与dispatch_task_revision、plan_revision、candidate_snapshot及两个digest。candidate_snapshot只含原计划及scope/purpose/personal_limit_fen，candidate_digest不把动态消费/as_of当预算参数；binding_digest绑定原发布ModuleResult（含原文案、原交互和全部选项）。平台不靠label猜哪个选项是adopt。

来源写入一次CAS，dispatch_task_revision=accepted_task_revision+1；写入失败不调用模块。调用前再核对同一原候选与版本。模块正常结果与该来源的completed/completion在同一次原结果CAS保存；外部API receipt丢失时重放冻结结果，不读取当前新计划作为原响应。所有原字段重试不重签。

## API02调用样例

以下仅示意专用预算分支；API02仍须保留原Cookie/同源/链接/交互/receipt参数摘要检查，以及text和option互斥检查。当前本票未修改API。

```python
# trusted来自当前认证会话与已核实任务链接，不接受body自报主体。
record = runtime.harness.budget_input_record(trusted, body.request_id)
if interrupted_receipt and record is None:
    raise ValueError("REQUEST_IN_PROGRESS")  # 没有持久接受事实，不能自动重试成新采用。

# 已有record的精确原请求在current_input_task之前分流，才能恢复
# needs_attention/interaction=None的历史结果。平台内部会再次校验。
completion = runtime.harness.resume_budget_input(
    trusted, input_request_id=body.request_id,
    interaction_id=body.interaction_id, selected_option_id=body.selected_option_id,
)
original_result = completion.result
original_task_revision = completion.task_revision
# 用原已核实链接 + 上述冻结结果/版本构造原TaskView，再完成原receipt；
# 不读取当前task.result冒充旧响应，不返回来源记录或origin_id。
```

已完成API receipt按原协议重放时也必须再次核对当前主体/任务访问规则。键不含session不代表旧会话未消费来源能授权新会话。新会话只允许既有规则下读取已发生的历史事实，不能获得旧来源的新采用权限。

普通非预算F10与模型续答继续`harness.resume(trusted, response)`，不传来源字段；即使知道真实选项或origin_id也没有当前来源。不可为所有F10打开中断重试或在模块中从snapshot自行激活来源。

## cross06调用样例

```python
origin = harness.budget_input_origin(trusted)
if origin is None:
    return require_dedicated_budget_input()
facts = origin.facts
# cross自行核对：当前adopt映射、原interaction/option、plan_revision、
# 完整scope/purpose/limit/旧BudgetRef关系及发布快照binding_digest。
# 校验失败停止，不从模型或来源记录推断adopt。
attempt = checkpoint_original_attempt(
    origin_id=origin.origin_id, expected_task_revision=origin.dispatch_task_revision,
    accepted_at=origin.accepted_at, original_candidate=facts["candidate_snapshot"],
)
# 若attempt已存在，只能使用它首次保存的预算编号/版本/时间/expected_revision。
# cross采用接口归#293/cross06；来源本身不代行该调用。
```

上述require/checkpoint函数代表cross自己的原映射与持久checkpoint逻辑，不是新增平台接口。只读恢复示例：

```python
from app.agent_platform.budget_inputs import BudgetInputRecovery

def reconcile_budget_input(self, trusted, origin, *, thread_id):
    assert self.harness.budget_input_origin(trusted) is None
    attempt = self.load_original_attempt(origin.origin_id, thread_id)
    # 下列查询必须核对origin、原候选/binding、稳定attempt以及准确采用记录；
    # 不存在时返回None，绝不拿最新revision重填采用，也不重新激活superseded版本。
    adopted = self.read_exact_adopted_fact(attempt)
    if adopted is None:
        return None
    return BudgetInputRecovery(attempt.attempt_ref, self.original_result(attempt, adopted))
```

恢复结果必须保留原task_id/run_id和首次业务事实。平台历史分支只保存该原请求的completion，不覆盖当前新计划/取消/终态结果，不设置当前来源，不调用entry.resume。API从completion构造历史响应；对当前任务的新操作仍须重新按当前卡片办理。

若未存attempt/准确采用，平台仅在原会话、原dispatch版本及完整候选仍完全有效时允许原请求继续原写；needs_attention或候选/版本变化时失效，不能刷新revision重试。若旧attempt的准确采用已发生，即使当前interaction=None或已取消，cross只读核实仍可补原请求结果。

## 验证边界

平台测试用真实Harness/ApplicationStore/CAS/任务锁和checkpointer，业务为明确标注的预算stand-in；不等于真实cross06/#293采用或F10 HTTP联调，更不证明资金授权。API02、cross06及原E2E需按本接口另做实际接线验收。本票不改变#160风险政策。
