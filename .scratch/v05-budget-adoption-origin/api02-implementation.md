# API02 实施与交接

Ticket: [v05-budget-adoption-origin/02：原 F10 输入身份接入平台来源](issues/02-api-f10-origin.md)。Owner: Erwin委派本执行对话；2026-10-25 收到中控正式开始信号。依赖 [PR #298](https://github.com/DrErwin/hackerthon-bank-agent/pull/298) 已实际合入 `6ce7fb03a3765df00773885953151619c43f52c7`，使用其[真实平台接缝](../../backend/app/agent_platform/budget-inputs-seam.md)。

仅实施 `backend/app/api/`，附本票材料；未改平台、storage、contracts、cross、共享项目跟踪/completion、原#293证据或生日编辑G1/04。本票PR不在此前合入或CI例外批准范围，由中控另行决定。

## 行为与调用边界

- 原F10请求体不变：request_id / interaction_id / selected_option_id 或 text。Cookie/同源、有效会话、任务/对话归属仍核对，来源不是客户端字段。
- F10持有API mutation锁，在普通“当前输入”校验之前查询平台持久来源。只有同一任务、可信user/round内确有原请求记录才开启该次中断重试；receipt参数摘要仍先拒绝异参。普通F10没有来源时不会得到 retry_interrupted。
- 首次专用路径要求 `cross.start_task` 当前input的合法选项，以及完整CrossTaskView预算候选（adopted=false、budget_ref=null）。保留原request/interaction/option调用 `resume_budget_input`，来源由真实平台建立；API不猜哪项是adopt。
- 已有来源时先调用平台原请求恢复，即使当前已needs_attention/interaction=None也不被普通input校验卡住。平台自行核对原来源/attempt、旧会话及失效；API不重签来源、不补最新revision。
- 返回TaskView使用原completion.result/run_id及原completion.task_revision，避免把当前新方案当作原请求结果。前端要查看当前状态仍走原GET任务接口；来源记录/origin_id不回前端。
- 发布的task_updated/interaction_required取当前任务，HTTP历史响应与当前卡片分开。消息/事件/确认验证引用在API原表的同一事务内发布，以稳定task_updated事件为整批标记；已提交后原请求重试整批跳过，避免旧结果夹入新交互，且不重复聊天消息。
- 普通金额、日期、配送引用及非预算输入仍走原input_response/continue_task；消息模型provide_input只走普通resume，不获得平台来源。确认、验证、未知银行操作协议不改。

## 对接示例

客户端仍发送原接口，不增加来源字段：

```http
POST /api/v1/tasks/{task_id}/inputs
Content-Type: application/json

{"request_id":"原客户端请求UUID","interaction_id":"当前服务端交互ID","selected_option_id":"当前服务端选项ID"}
```

后台实际调用为平台已有的 `harness.resume_budget_input(trusted, input_request_id=..., interaction_id=..., selected_option_id=...)`。cross06后续在自身adopt分支读取 `harness.budget_input_origin(trusted)`，核对原映射/计划/完整候选并保存稳定attempt；历史恢复由它实现只读reconcile_budget_input。API02不代行采用或动钱授权。

## 验证框架与实际证据入口

新增测试通过真实本地TCP HTTP请求、真实Harness/ApplicationStore/来源记录/检查点运行；planner与预算业务是明确标注的stand-in。stand-in只把原attempt/测试事实保存在检查点，并验证新增预算用例的银行操作/流水均0；没有调用#293或创建真实AdoptedBudget。受影响回归中的原转账/验证测试会操作各自独立模拟银行，不是现实银行或共享演示库。

| 场景 | 本票观察 |
|---|---|
| O01 | 原F10到真实来源与冻结completion；当前交付不包括cross06真实采用 |
| O02/O06 | 模型知道选项、伪造source/origin字段或普通文本续答均无当前来源；不借历史记录 |
| O03 | 同参返回原响应、异参冲突、同交互换号、两个HTTP请求竞争只接受一份 |
| O04 | 旧交互/非法选项/text混入、其他用户/任务/轮次、过期会话均拒绝；新会话不能沿用旧未消费来源 |
| O05 | 无来源的中断receipt不重试；来源已存/模块前失败可精确恢复；attempt前后失效不刷新revision；已有事实仅补结果；API发布/receipt失败不二次处理 |
| O07 | modify后旧请求不能采用新候选；取消后历史核实不继续执行；冻结响应不覆盖当前新计划 |
| O08 | 原父子输入、普通金额/日期/配送、订阅澄清、确认/验证及原未知操作查询回归 |

首个定向批（修发布问题前）为21 passed，head753da39；随后修正并新增断言的定向批为93 passed / 136.64s，head8a9b6c9。同步主线2a070b9后，最终head355ea4e的同一93项定向批为 **93 passed / 96.15s**，失败/错误/跳过均0；新增预算API23、平台35、相关API35。range-diff证明两条实现提交与审查过的改动等价。原日志、XML、解释器环境、manifest及SHA-256均在[api02-evidence](api02-evidence/summary.json)，不能将早期批次冒充最新源码验证。所有批次均为定向，不是完整后端回归；按中控资源安排未运行全量，后续若需要应先报中控排时。

代码[独立双轴审查](api02-review.md)必须项已清零；原票的真实cross06/#293采用和完整生日E2E仍为下游验收，不能据API接缝通过提前勾选。

## PR与阻塞

[PR #299](https://github.com/DrErwin/hackerthon-bank-agent/pull/299)为本票单目录交付，已附加本对话，保持草稿，不自行合并。已读取ce0c35b上CI的annotation：账号付款/额度导致job未启动，标Blocked；未套用旧PR的CI计费例外。原始捕获日志字节在同目录`.log.gz`，供阅读的JSON/log为LF，摘要分别保存归档、原字节与阅读副本哈希；JUnit保持原文件字节。
