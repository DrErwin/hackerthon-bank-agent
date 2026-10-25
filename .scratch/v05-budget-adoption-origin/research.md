# F10 预算采用来源：事实与最小缺口

Date: 2026-10-25。代码基线 `430236645887f3e77d4d211e6dd2c90558479425`；设计输入分支 `0c46def89971548e1d1b8eb8eb3d928cd32642ef`。只读调查与临时探针，非修复。

## 已确认的调用链

| 链路 | 现有实现 / 证据位置 | 对采用来源的意义 |
|---|---|---|
| 专用 F10 | [api/app.py](../../backend/app/api/app.py) L338—345：current_input_task → input_response → continue_task | HTTP 路由知道原 request_id/interaction_id，但后两者在进入 Harness 前已丢失 |
| F10 校验 | [api/service.py](../../backend/app/api/service.py) L1523—1530、L1560—1575：认证任务链接、当前 input ID、当前选项有效、禁止 text 混入 | 这些检查有用，但输出只有 choice，不能在模块内区分来源 |
| 模型续答 | [harness.py](../../backend/app/agent_platform/harness.py) L327—357、L462—488；[model.py](../../backend/app/agent_platform/model.py) L60—81 | ContinueProposal 可给 provide_input + selected_option_id；待办摘要包含真实选项 ID/label，因此不能依靠不可猜性 |
| 消息调度 | [api/service.py](../../backend/app/api/service.py) L579—634、L644—708：持久 continuation → 同一 input_response → 同一 continue_task | 身份和任务版本有效的模型选项也会被转换为相同 choice |
| 统一恢复 | [api/service.py](../../backend/app/api/service.py) L1445—1496 → [harness.py](../../backend/app/agent_platform/harness.py) L1118—1245 | 原 resume 接收 dict，并原样交 entry.resume；只知道同一可信 actor/task，没保存这次输入的来源 |
| cross 当前接收 | [cross/entry.py](../../backend/app/modules/cross/entry.py) L272—316 | 接受 choice / selected_option_id；interaction_id 若提供才核对。不能从此字典恢复真实 F10 来源 |

注意本基线的 cross06 尚未实施预算采用。本探针证明的是信息丢失，不能称作已经完成模型越权采用或付款的攻击复现。

## 可以复用与不能冒充的证据

| 现有能力 | 可以复用 | 当前不能证明 |
|---|---|---|
| Cookie、同源检查、Identity、trusted()、link() | 服务端身份、有效会话、原任务/对话归属；不由模型填 actor | 这次 choice 是经哪个入口提交的 |
| api_requests receipt，store.py L117—146 | 同 user/round/endpoint/request_id 参数摘要冲突及已完成结果重放 | 键不含 session；只存摘要及结果，没有可供 cross 读取的原候选/原交互完整事实；声明请求不代表已采用 |
| api_message_jobs.continuation_json | 证明某条模型续答及其调度曾被持久保存 | 它属于聊天来源，不能变成预算 adopt 的专用 F10 事实 |
| ApplicationStore.update_task，application.py L408—422 | 带 user/round/task/revision 的单次 CAS 保存完整 snapshot，重开保留 | revision 一致只证明并发位置，不证明采用意愿 |
| Harness _task_lock，L82—127 | 已有线程及文件任务锁，同任务核对/来源写入/执行可串行，支持重入 | 不证明跨任务预算额度串行；后者仍归 cross06 |
| LangGraph 任务 checkpoint | 保存模块原候选、稳定 adoption_attempt 和中断位置，用户/轮次/任务受控 | 任意 checkpoint 或 model choice 本身不是 F10 来源 |
| RunTrace / 审计 recovery.checked、task.transition | 现有只追加日志与脱敏 evidence 可记 origin_id / digest / 结果，恢复时辅助追溯 | 当前 recovery.checked 只记录原任务/操作恢复结果，没有原 F10 选项及候选绑定；审计不能充当可写授权接口 |
| #293 AdoptedBudget 持久接口 | 原采用版本/重放/范围隔离，可信记录最终保存 | 它有意不核 F10，不能以该存储已落库倒推真实采用 |

因此“已有可直接读取的可信预算采用来源记录”尚不存在；但无需由此推导必须加 storage 表。推荐用现有任务快照的 CAS 保存预算专用来源，再由平台限定当前后台调用可见范围，详见[规格](spec.md)。

## 隔离探针结论

[完整复现与输出](probe.md)：复用现有 API 测试工厂和 scripted cross 测试能力，两个 TemporaryDirectory，各自临时 application/bank 数据库。真实 FastAPI 请求/真实 Harness 与 ApplicationStore；模块是 scripted stand-in，planner 也是脚本替身。

- F10 合法选项：HTTP 200，模块收到 `{"choice":"OPT_APPLY"}`。
- 模型 provide_input 合法选项：真实聊天 HTTP 202，经持久消息 job 到模块，同样只有 choice；脚本 planner 被调用，不调用外部模型。
- 模型待办摘要含该选项 ID（不是猜测）。
- 两条路径重开 ApplicationStore 后 snapshot 的字段一致，均无本轮输入来源；有 trace_id 不代表已经关联原 F10。
- 在 F10 body 加 source=human：实际 HTTP 400（现有 extra=forbid 经 API 错误映射）；原请求字段未扩展。第一次探针对错误码误预期 422 而停止，随后按实际 400/422 拒绝范围重跑并完成，未将中止算作通过。
- 两条路径 bank_operations / ledger_entries 均从 0 保持 0；没有真实预算采用、资金动作或共享数据库写入。

## 最小拆分建议

1. [v05-budget-adoption-origin/01：平台可信来源与恢复](issues/01-platform-origin.md)：单目录 agent_platform，复用任务快照、任务锁和 CAS；提供来源写入与当前调用读取。无需依赖新 storage 表。
2. [v05-budget-adoption-origin/02：专用 F10 接入](issues/02-api-f10-origin.md)：单目录 api，保留原输入身份并使用 01，仅对原预算来源记录的中断请求开放受控恢复，消息续答留普通路径。
3. storage：**无必要新增票**；#293 不变，仍是 cross06 已有采用持久依赖。若后续发现真实 CAS/原子能力缺口，提交具体失败探针再由中控决定补票。
4. cross06 顺序接在 01/02 与其原业务/存储依赖后，核对真实 adopt 映射/候选与 attempt；完整生日 E2E 用原 evals 票。这里只有建议，未激活任何开发票。

## 待中控确认的实现范围（不是新增业务规则）

确认是否采用“平台快照 + 当前后台调用读取，0 新 storage 票”的最小方案，以及建议的 01→02→cross06 顺序。已认证专用 F10 事实是本次来源证明的边界；如果要求实体真人识别或抗自动客户端，那将是新的业务范围，本建议没有替用户增加该要求。
