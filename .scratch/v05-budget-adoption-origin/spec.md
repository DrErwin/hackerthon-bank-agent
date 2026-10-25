# F10 个人预算采用来源：最小前置设计

Status: proposed / research_only — 待中控决定最小实施票；本文不是实施授权。

Owner: Erwin（中控授权本执行对话调查与设计）

Accepted at: 2026-10-25

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../v05-cross-linkage/packages/01-platform-bank.md)

## Problem Statement

预算采用要求用户通过原任务 F10 明确选择。现有专用输入和模型续答都会变成同一 choice，cross 无法区分；选项编号还会出现在模型待办摘要中。若只核对选项、任务版本或传入 source=human，模型就可能代用户采用预算。

本次只追踪事实、运行隔离探针、提出来源记录与目录拆分；PR #293 保持原交付。未实施 API/platform/storage/cross，未改公共字段。

## Solution

保持现行 F10 请求体不变。后台在专用 F10 预算候选选项路径，保存“这个认证会话针对哪份原候选提交了哪个选项”的不可变来源事实。cross 通过仅供后台使用的当前调用读取接口取事实，再核对自己保存的 adopt 选项与候选；聊天/模型续答不获得这个事实。

这证明的是已认证专用入口提交，不声称生物意义上的真人识别、防自动客户端或新增身份等级。预算采用仍只是业务约束，不是购买/动钱授权；规则沿用[公共契约 §5.4](../../docs/contracts/公共契约-2026-09-23.md#54-联动模块入口与返回06)和 F10。

## User Stories

1. 用户在当前预算卡片选采用后，系统能保存对应会话、原交互与原候选，不丢来源。
2. 模型即使知道当前选项编号，也不能生成相同来源事实或借用之前的事实。
3. 重传原请求只处理一次；修改候选、换任务/用户/会话/轮次或换请求参数均不能复用原采用。
4. 中断后沿同一原请求和已保存的采用 attempt 核实；不重新生成时间、版本或授权事实。
5. 新会话可以按既有恢复规则查历史结果，但旧会话的未消费来源不能用于新采用。

## 1. 已核对基线与事实

- 代码 origin/main：`430236645887f3e77d4d211e6dd2c90558479425`。
- cross06 输入设计：origin/codex/v05-cross-budget-design `0c46def89971548e1d1b8eb8eb3d928cd32642ef` 中的 budget-integration-spec / issues/06；使用[固定版本链接](https://github.com/DrErwin/hackerthon-bank-agent/blob/0c46def89971548e1d1b8eb8eb3d928cd32642ef/.scratch/v05-cross-business/budget-integration-spec.md)，避免未合文件的本地断链。
- 本基线未合 PR #293；它只保证预算持久一致性，本任务不改其实现或采用真实性边界。
- 完整路径、可复用能力和探针见[事实报告](research.md)与[探针记录](probe.md)。探针是脚本化 cross 测试能力，不是真实预算采用或安全绕过后的付款。

## 2. 最小输入输出与责任

以下后台方法名/私有字段名仅作建议；没有新增公共模型、工具或 HTTP 参数。

| 位置 | 输入 | 处理 / 输出 |
|---|---|---|
| 原 F10 API | 既有 request_id、interaction_id、selected_option_id；身份来自 Cookie/服务端 | 保留原请求身份，不先降成 choice 再丢信息。会话、同源、任务归属及当前交互仍按原检查；选项和 text 不能混用。预算候选选项转到平台专用后台方法 |
| 平台专用方法（建议 resume_budget_input） | TrustedContext + 原 input_request_id / interaction_id / selected_option_id | 从应用任务结果重新读取并固定候选，持久化来源，再在同一任务锁内执行模块；不接受客户端/模型 supplied source、candidate_digest、plan_revision 或 actor |
| 平台当前调用读取（建议 budget_input_origin） | 只接可信 context；不接来自 choice 的 origin_id | 仅在本次专用 F10/受控原请求恢复的调用范围内，读取并再次核对持久记录，返回不可变来源投影；普通 resume、模型续答、查询和别的任务返回无事实 |
| cross06 | 当前调用来源投影 + 自己保存的原候选/交互/选项映射 | 同时核对真实来源、adopt 选项、计划及范围/用途/限额快照，生成稳定 adoption_attempt，再调用 #293；原 task revision 不能替代这一串核对 |

预算候选识别使用现有 CrossTaskView 的 plan_revision / budget（adopted=false、budget_ref=null），加当前 input 交互及其选项。不能凭 prompt/label 包含“采用”推断。cross06 需按自己的已确认设计把该候选发布到应用任务结果；当前 data=null 或缺候选时不得生成预算采用来源，只能继续普通输入/澄清。平台不判定哪个选项代表 adopt；只有 cross 的原受控映射决定它。

### 2.1 私有来源记录建议

保存在应用任务 snapshot 的一个预算专用映射中，以原 input_request_id 定位不可变记录，不放 response/模型提示/公共 TrustedContext。按任务生命周期保留 completed / invalidated 记录，不能因接受下一个交互就覆盖前一个尚待回执恢复的事实；同交互换请求号不会另存记录。历史业务采用仍由 cross 的 attempt 和 AdoptedBudget 追溯。本期不引入通用授权事件表。

| 字段 | 由谁确定 / 含义 |
|---|---|
| origin_id、accepted_at | 后台首次接受时生成并持久；重试不重签 |
| user_id/session_id/demo_round_id/task_id | 认证上下文 + 应用任务归属，不能从 body/模型复制 |
| input_request_id、endpoint_tag | 原 F10 请求 ID；固定后台入口标识，不是可提交的 source 字段 |
| interaction_id、selected_option_id | 核对原当前 input 与有效选项后固定 |
| accepted_task_revision | 接受前读取的应用任务版本，提供并发检查，不表示采用授权 |
| dispatch_task_revision | 来源写入通过 CAS 后的任务版本；与上项区分，避免写来源后自己把 revision 弄旧 |
| plan_revision、candidate_snapshot | 从应用结果固定的原 scope/purpose/personal_limit_fen；不可由模型补齐 |
| candidate_digest、binding_digest | 确定性规范化 JSON 摘要；前者绑定原预算参数/计划，后者绑定原发布结果（含展示文案、原交互及选项集合）。动态 used/remaining/as_of 不冒充预算参数；发布结果或任务版本变化仍须重核 |
| phase | accepted / completed / invalidated；不是 authorized。accepted 也不代表 cross 已选择 adopt |
| completion | 原模块结果、完成时任务版本、已保存 attempt 的原关联标识；仅供原请求恢复，不把当前任务新结果冒充原响应 |

当前候选 BudgetView 的 budget_ref=null，不能声称平台已经从该字段读到了改版基准。cross06 自己保存 previous BudgetRef 与原选项映射，并按已确认设计在原交互文案明确展示旧预算编号/版本；binding_digest 固定的原发布结果包含该展示。cross 核对原交互、当前内部完整候选及发布结果，计划/旧版关系任一变化都必须重签交互，不能在同一发布快照下偷换旧版关系。若不能证明这种不可变对应，停止采用并回中控；不为此自行新增公共字段。

摘要是关联校验，不能把原本不可信的输入变成可信。可信来自专用后台路径、认证/归属检查、持久记录和模块不可借用的当前调用范围共同保证；不是靠 ID 难猜或一个布尔值。

## 3. 持久化与调用顺序（建议，不实施）

1. API 沿原 mutation 锁/receipt 核对请求；平台仍必须自己重新核对会话、任务、waiting_input、原交互、选项及候选，消除 API 检查后任务已变化的窗口。
2. 在既有 Harness 任务锁内，按 accepted_task_revision 调用 ApplicationStore.update_task 的 CAS 持久保存 accepted 来源，保留原 snapshot 其他字段；同次写入把 dispatch_task_revision 固定为 accepted_task_revision+1（现有 update_task 的递增语义），不能为了记写后版本再写一次造成追版本循环。来源写入失败时不调用模块、不建立 adoption_attempt。
3. 只在该专用方法的当前执行范围设置内部来源句柄，读取时核对持久记录/当前主体/当前任务/版本/候选；调用结束或异常必须清除当前句柄。不可由普通 resume 根据 snapshot 中“有一条来源”自动激活，也不可把 origin_id 放进模型可控 response 再当凭据。
4. cross06 自己比较原采用映射、plan_revision 和完整候选；采用前先保存稳定 adoption_attempt，其中关联 origin_id 和 dispatch_task_revision（也是当时调用 #293 的 expected_task_revision）。同一个 attempt 的时间、预算编号、版本及 expected_task_revision 永不在重试中改写。
5. 模块结果发布时，Harness 在同一次 update_task CAS 中保存 result 和该来源的 completed/completion 投影。不得用旧 snapshot 覆盖刚写的来源；异常路径也保留已写入来源和 checkpoint。预算已落库但结果未发布由 cross attempt 核实，不新建采用。
6. API 完成原 receipt。UI/SSE 失败不撤销已发生的采用，也不能触发新版本。完成 receipt 存在时按原 receipt 返回；缺 receipt 的恢复按下一节处理。completion 的冻结 ModuleResult 含原 run_id，另保存原结果 task_revision；API 用它与原已核对链接构建原 TaskView，而非取当前 snapshot 新计划充当原结果。

存储判定：推荐 **0 张新增 storage 实施票**。现有 update_task 支持完整 JSON 快照、user/round/task/revision CAS，重开可读；任务锁和 checkpoint 也已存在。没有发现必须新增表/方法的缺口。平台不能绕过 CAS 或伪造已完成状态；若实施探针证明该接缝不能保持“来源 + 结果”同一次原子更新，再回中控补具体 storage 票，不先造通用原语。#293 是 cross06 的已有依赖，不是本来源记录的平台实现依赖。

## 4. 幂等、失效与恢复

| 情况 | 必须行为 |
|---|---|
| 同 user/round/endpoint/request_id 同内容，原 receipt 已完成 | 沿原 API receipt 返回；不调用模块、来源或存储采用，不重新激活旧版 |
| 同请求 ID 改 interaction/option/候选或主体关联 | REQUEST_CONFLICT / stale，不能覆盖原来源 |
| 同交互用另一个请求 ID 再答 | 已有 accepted 归属时不得创建第二来源；completed 只认原完成事实，不能当新采用。可以返回原事实或当前卡片，不重写采用 |
| accepted 已持久、尚未保存 attempt | 仅原请求的受控 F10 恢复可重新核对原完整候选；一致且原会话仍有效才继续。没有候选/版本已变则失效、回新交互 |
| attempt 已存、预算未存 | 只在原会话/原来源/原 attempt 和原 dispatch_task_revision 仍有效时尝试原写；版本已变不得取最新 revision 重填重试 |
| 预算已存、结果/receipt 未存 | cross 只核实原 attempt 对应准确记录、补发原结果；不得靠“accepted”重复新建预算。superseded 保留历史，不激活旧版 |
| completed 结果已存、API receipt 丢失 | 平台只返回完成投影、不再调用模块；API 重建首次受理结果并缓存（不存在首次已完成 HTTP 响应时不得借此返回当前新计划作为原结果） |
| 普通 resume / 模型 provide_input / 伪造 source 或 origin_id | 没有本次可信来源，不能采用。旧 accepted 记录不能被这些路径借用；失败后不得刷新来源/版本再写 |
| modify/重新规划/另一输入使候选或交互变化 | 未消费来源 invalidated，新候选必须重新 F10；completed 历史只读 |
| 取消、终态、旧会话过期/切换、轮次重置 | 不能以旧来源进行新采用；已发生的采用事实按原记录查询，旧来源不随会话恢复获得新授权 |

当前 API receipt 的 in-progress 默认会拒绝重放，因此 API 票须为上述 **已有持久来源的原预算请求** 加严格的恢复分支；不能给所有 F10 开 retry_interrupted=True。首次 receipt 已声明但没有来源时，缺乏可复用接受事实，保持受阻/新交互，不自动把未完成请求升格为授权。

复用旧 receipt 的读路径也要再次检查原来源 user/session/round/task 绑定与现有访问规则。API receipt 的键不含 session，不得仅因命中同 user/round/request 就将旧会话未消费的采用当成新会话输入。这里不改变其他 F10、消息、银行未知操作和资金确认协议。

## Testing Decisions

本轮仅运行现有组件的隔离探针，不写测试程序、不运行 CI 或全量回归。未来实施测试观察公开 F10 与脚本化模型续答到真实 cross 的对比，辅以 ApplicationStore/source/attempt 的持久事实；源码全文和猜测字段不替代验证。

| 场景 | 实施后要求 / 负责 |
|---|---|
| O01 | 真实 F10 原选项 → 可信来源 → cross06 adopt；API + platform + cross |
| O02 | 模型知道全部选项/伪造 source/origin/request_id 仍无来源，零采用；API/platform/cross |
| O03 | 同号同参、异参、同交互换请求号、双连接竞争；API/platform |
| O04 | 旧交互/候选/计划版本、跨主体/任务/会话/轮次；platform/cross |
| O05 | 来源落库前后、attempt 前后、采用后/发布前、receipt 前各断点；platform/API/cross，重开恢复 |
| O06 | 普通 resume 不借用 accepted；来源句柄异常后不泄漏；platform |
| O07 | 修改/取消/过期/新会话/新轮次失效；completed 只能补原结果；platform/API/cross |
| O08 | 普通 F10 金额/日期/配送输入及非预算 cross 不受影响；API/platform |

cross 采用验证与生日 E2E 复用[原 cross06 票](https://github.com/DrErwin/hackerthon-bank-agent/blob/0c46def89971548e1d1b8eb8eb3d928cd32642ef/.scratch/v05-cross-business/issues/06-adopted-budget-integration.md)及现有 [v05-cross-e2e/03](../v05-cross-e2e/issues/03-birthday-e2e.md)，不重复建立验收工程。各层证据与真人安全审阅分开。

## Out of Scope

不实施运行代码/公共字段，不改 #293、shared tracking、completion 或包状态；不新增权限等级、通用授权平台、银行确认、自动提额或实体真人检测。只在本工作组写建议票，待中控决定才可变为实施票。

## Further Notes

已读取本机 to-spec/to-tickets；disable-model-invocation 且无显式工具入口，按已授权范围手工执行流程，不声称调用斜杠命令。用户已明确要求调查、规格和票建议，不作实施授权推定。code-review 双子代理用于本次设计双轴审查，不把设计审查写成代码/安全验收。
