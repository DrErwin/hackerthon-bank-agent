# 已采用个人预算持久记录

Status: ready-for-agent

Owner / Accepted by: Erwin（中控委派本执行对话）

Accepted at: 2026-10-25

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../v05-cross-linkage/packages/01-platform-bank.md)

## Problem Statement

生日任务需要遵守用户已经采用的个人预算。目前只持久保存预算占用，没有采用记录，无法可靠读取原范围、用途和版本。本次生日上限不能冒充个人预算。

## Solution

在已授权的 storage 目录提供独立、可重开的采用记录。引用[公共契约 §5.4](../../docs/contracts/公共契约-2026-09-23.md#54-联动模块入口与返回06)、[字段详稿 §3.2](../v05-cross-platform/01-contract-detail.md#32-budgetview--budgetref--adoptedbudget--budgetcommitment)，复用 AdoptedBudget / BudgetRef。

## User Stories

1. 用户明确采用后，后续任务可以读取相同用户、相同演示轮次的预算及其原范围、用途和来源任务。
2. 用户重新采用修改后的方案时，保留旧版本和在途占用，只有新版本保持 active。
3. 同一采用交互重放返回原记录，异参重放被拒绝，不能造出第二份采用记录。
4. 并发改版只能有一个获胜；重开数据库后结果不变。
5. 其他用户和新演示轮次看不到原采用记录。

## Implementation Decisions

- 唯一实施目录为 storage；一个工作组、一张实施票、一个分支、一个 PR。仅自己的规格、票据及交接材料例外。
- 数据库兼容升级，按 user/round/budget/version 保存不可变采用快照和独立状态；同 budget 最多一个 active。版本从 1 开始且连续，改版须明确 previous_version 并原子核对当前 active 版本。
- 写入传可信 user/round，核对记录归属、来源任务和 expected_task_revision；禁止直接写 superseded。同源任务的同一 adoption_interaction_id 绑定原预算快照及任务版本，重复写不增记录，异参拒绝。精确重放可在任务前进后读取原结果，不激活旧版。
- 写接口只供受控后端调用。cross 在调用前核对 F10 adopt、原交互、当前方案版本及范围/用途/金额快照。存储不解析业务检查点，也不把存在任务/交互编号当作授权证据。
- 读接口支持准确引用、本人本轮候选列表（默认 active，显式可含历史）。保留原 scope，不在 storage 推断用途、日期/账户适用关系或选择宽松预算。
- 重置沿用既有演示轮次隔离；新轮次不继承采用状态。不新增清库或重置 HTTP 接口。
- 现有预算占用登记/更新/跨版本查询接口保持原样，不引入通用预算框架。

## Testing Decisions

在 ApplicationStore 的真实 SQLite 接缝用临时数据库验证外部行为：

| 场景 | 核验 |
|---|---|
| S01 | 初次采用、准确引用、候选列表及重开恢复 |
| S02 | 新版本原子替换，历史 superseded，跨版本占用不丢 |
| S03 | 同交互同参重放、异参/换预算/换版本冲突，旧请求重放不复活 |
| S04 | 真实用户/轮次/来源任务隔离，任务版本变化后新写拒绝 |
| S05 | 两连接竞争采用/改版只留一个结果，不产生半更新 |
| S06 | v5 升级保留已有任务/占用，初始化幂等，新轮次无旧采用状态 |

先运行本票测试及 storage 回归，再运行 backend 全量一次；不调用真实模型、银行写入或共享数据库。双独立子代理分别核对规范和原票。

## Out of Scope

不改 contracts、API、platform、cross、银行规则、共享进度或 completion。不实现范围用途匹配、L01 取数、额度判定、生日任务预算绑定和冻结前 pending 编排；由后续 cross 票承接。AI 审查不代表真人安全签核或端到端验收。

## Further Notes

2026-10-25 已读取本机 to-spec / to-tickets / implement / code-review。前三者存在但 disable-model-invocation=true，当前会话无显式调用工具，不能宣称自动调用；依据委派中已经明确的一张票与测试接缝按其流程执行。code-review 可用并按双子代理流程执行。团队安装基线为 d81f3a183412e71a5b1e84ca21bc1a35eea03a60，本轮不更新 skill 来源。

核查报告位于中控指定的 runtime-risk 工作区，本轮已完整读取，未改该工作区。新工作组创建前核对最新 origin/main，尚无该组或同号票。基线 9a479ea4414635772fdb723c02b0fc70b76a1a55。
