# 跨场景联动 · 后端能力清单（前端设计输入）

Status: 只读盘点完成（未改业务代码、未提交、未启动服务器、未运行任何测试）

盘点日期：2026-10-25

盘点基线：`git log -1` = `b071408 docs: 登记 v05-cross-frontend/01 执行对话接手`（其父 `232123f`，联动平台/业务代码基线 `1547632`）

盘点方式：读文件 + grep（`backend/app/api`、`backend/app/contracts`、`backend/app/modules/cross`、`backend/app/agent_platform`、`backend/app/modules/bills|transfer|subscription`、`frontend/src`、`docs/contracts`、`.scratch`）。**没有运行 pytest / vitest / uvicorn**，所以下文凡"能/不能走通"的结论都来自静态代码路径推演，标为【码】；涉及"跑起来会怎样"的推断一律写清是推演而非实测。

> **工作区并发说明（如实）**：盘点期间同一工作区有其他对话在写入。开始时 HEAD 为 `232123f`，中途前进到 `b071408`；`git status` 显示未跟踪文件 `.scratch/v05-cross-frontend/page-plan-01.md`、`.scratch/v05-cross-frontend/research/`（含他人写的 `frontend-inventory.md`）、`frontend/联动-交互原型-v0.1.html`。本报告只新增 `research/backend-api-surface.md`，未改 `backend/`、`frontend/`、`docs/` 任何文件。前端侧盘点请与 `research/frontend-inventory.md` 对照阅读（本报告不重复它的组件清单）。

## 证据等级标记

| 标记 | 含义 |
|---|---|
| 【码】 | 读实现代码直接看到（类型定义、路由、分支、装配） |
| 【测读】 | 读了测试源码，能看出被测行为；**未运行**，不代表今天通过 |
| 【票】 | 只在票据 / 文档 / completion 里声称，未在代码中核实到等价实现 |
| 【推】 | 由代码路径推导出的运行期行为（未实机验证），需要一次真跑确认 |
| 【未证】 | 找不到任何证据，不作结论 |

---

## 0. 速读结论（给前端设计者的五句话）

1. **前端没有"联动"专用接口**。三条主线全部复用 §6 的通用任务 / 交互 / 确认 / 验证接口，联动只多出一个 `GET /tasks/{id}/children`。想"新建一个联动任务"没有 REST 入口，只能发一条自然语言消息让模型选中 `cross.start_task`（【码】`backend/app/agent_platform/harness.py:50-54` 的能力白名单不含 cross，`POST /tasks/{id}/actions` 起不了联动任务）。
2. **联动父任务的 `data` 是 `CrossTaskView`，但它目前是"骨架"**：`steps[]` 只有 `step_id / action / child_task_id / status / amount_fen / depends_on`，而 `arrangement`、`budget`、`order_id`、`payment_status`、`operation_id`、`result_ref`、`error` 在运行期恒为 `null`（【码】`backend/app/modules/cross/plan.py:144-171`）。**生日场景的 `steps` 只有 1 条只读账户步骤**，冻结 / 下单 / 付款 / 释放全部不在步骤里，只出现在 `message` 文本中（【码】`backend/app/modules/cross/entry.py:216-227`）。
3. **两处硬阻断会让页面"做到也走不通"**：① 联动父任务的补充输入只接受 `selected_option_id`，任何 `text`（金额、日期、配送引用编号）都返回 `400 USE_CURRENT_INPUT_FIELDS`（【码】`backend/app/api/service.py:1549-1595`）；② 子任务的确认单 / 验证挑战记录没有登记进 `api_records`，`GET /confirmations/{id}`、`POST /confirmations/{id}/answer`、`GET /verifications/{id}`、`POST /verifications/{id}/code` 对子任务大概率 404（【推】，见 G1，须实机复核）。
4. **账单类型化入口仍未通**：`cross` 用 `BillSummarizeInput` 派发 `bills.summarize`，而账单入口只接受 `StartTransferInput`（【码】`backend/app/modules/bills/entry.py:257-260`），所以减支的"账单证据"步骤、养老金的"本月入账"步骤**必然失败**（见 G4）。这直接砍掉 XL-S01 的证据链和 XL-P01 的 `selected_income` 口径。
5. **前端类型层完全缺 cross**：`frontend/src/api.generated.ts` 不是 OpenAPI 生成，而是"Pydantic 模型 → JSON Schema → json2ts"，白名单里没有 `app.contracts.cross`，所以要新增接口类型必须先改生成脚本再重跑 `npm run generate:contracts`（【码】见 §4.2）。

---

## 1. 场景定义与对前端的具体要求

来源：`.scratch/v05-cross-linkage/spec.md`、`.scratch/v05-cross-frontend/spec.md`、`evals/cross/representative-cases.md`（以下逐条摘录并翻译成"界面要做什么"）。

### 1.1 XL-S01 减支（`evals/cross/representative-cases.md:35`）

| 项 | 内容 |
|---|---|
| 用户看到什么 | 提出"最近钱怎么花得快，帮我处理不用的扣费"→ 系统给范围 → 看到消费对比 / 明细 → 看到银行真实签约清单 → 自己勾选两项取消、一项保留 → 逐项确认 + 验证 → 刷新清单 → 总回执 |
| 系统要保证什么 | 原因有账单证据；只取消所选两项，保留项零写入；已扣款不退；不承诺会员立即失效；"预计减少支出"必须注明期间与生效依据 |
| 对前端的具体要求 | ① 一张"证据区"要能同时展示 `consumption_net_fen / comparison.delta_fen / categories[].net_fen`（来自账单子任务，**当前拿不到，见 G4**）；② 签约清单要按"可在线退订 / 疑似（无银行签约）/ 已退订"分组（数据源：订阅子任务的 `SubscriptionListResult.items[].source_type|status|can_cancel_in_bank`）；③ 每个退订项是**独立子任务**，必须能内联展开该子任务的确认卡 + 基础身份验证卡；④ 回执要区分"已退订（银行确认，附 `effective_stop_at`）/ 结果待核实 / 未办理"，且**未知项不得计入"已确定少扣"** |
| 今天能否走通 | **半通**：签约盘点与退订子任务是真的（`subscription.list_subscriptions` / `subscription.cancel_subscription`）；账单证据步骤必失败（G4）；子确认卡大概率打不开（G1） |

### 1.2 XL-P01 养老金月度安排（`evals/cross/representative-cases.md:22`）

| 项 | 内容 |
|---|---|
| 用户看到什么 | "养老金到了，帮我安排本月的钱" → 系统查入账 / 账单 / 代扣 → 用户选不用的服务与留存、去向 → 逐笔确认退订 → 按实际结果刷新计划 → 分别确认两笔转账 → 总回执 |
| 系统要保证什么 | 真实取消指定签约；恰好 2500 / 1000 两笔转账；1500 是"未转出额"而不是第三笔交易；预计节省不等于退款或收入；每项确认、回执、银行事实可对应 |
| 对前端的具体要求 | ① 资金范围二选一（`selected_income` / `available_balance`），并显示"以银行记录为准"；② 留存额是**文本输入**（如 1500 元）；③ "留存是否含已知代扣"是二选一；④ 收款人来自银行已保存收款人列表（`name_masked / account_masked`）；⑤ 每笔金额是文本输入；⑥ 采用（adopt）是一次**独立的方案确认**，不等于批准任何转账；⑦ 每笔转账仍是独立子任务 + 独立确认 + 中风险双因子；⑧ 总回执要能显示"已转出 / 留存 / 未转出留在账户"三个数 |
| 今天能否走通 | **基本不通**：②⑤ 需要文本输入 → 400（G2）；① 需要 `bills_details` 子任务成功 → 必失败（G4），所以只能选"当前可用余额"；⑦ 子确认卡大概率打不开（G1）。**唯一能走完的是"0 笔转账"的空安排**（`backend/app/modules/cross/pension.py:595-602` 对空 `allocations` 直接进入 running → 收尾） |

### 1.3 XL-X02—X05、XL-X08 共性（`evals/cross/representative-cases.md:60-66`）

| 编号 | 用户看到什么 | 系统要保证什么 | 对前端的具体要求 | 今天能否走通 |
|---|---|---|---|---|
| XL-X02 旧确认失效 | 等待确认时改金额 / 账户 / 签约 / 商品 / 日期后，点旧确认按钮或回答旧交互 | 只影响未执行部分；旧版本不批准新动作；成功事实不被重写 | 每个交互带 `interaction_id` + `task_revision`；旧按钮必须只读；选项 id 是**每次询问重新生成**的（`backend/app/modules/cross/entry.py:121-126`），旧 id 提交会 400 `INVALID_OPTION` | 交互层通；确认层受 G1 影响 |
| XL-X03 两任务交错 / 插入只读查询 / D1 | 两个任务分别补充、确认、取消；一个等待时插入只读查询；同一账户两份资金安排；普通转账从另一入口支出 | 输入与确认归属正确；查询不丢原任务；同账户只有一份活动安排，冲突支出暂停但查询 / 限定收尾允许 | ① 必须能"按任务 id 路由"提交，不能把父 id 套给子请求；② 插入查询会新增任务，回到原任务要能恢复；③ D1 冲突时前端只能展示后端给的 `needs_attention` + `error.code=ARRANGEMENT_CONFLICT`，**不要自己推断"哪张账户被占"**（见 G7） | 路由通；D1 提示文案是通用的（G7） |
| XL-X04 断线 / 刷新 / 重复点击 | 原父子任务与操作可找回；成功动作最多写入一次；未知先查原操作 | 重连先连 SSE 再拉 F06/F08/F09；按 `task_revision` 拒绝旧快照；重连不重发 | 需要 `GET /tasks/{id}/children`（**前端目前没接**）+ 每个子任务的 `GET /tasks/{id}`；子任务未注册前 `GET /tasks/{child}` 是 404（懒注册，`backend/app/api/service.py:821-832`） | 通（但前端要自己补 children 调用） |
| XL-X05 会话失效 / 环境重置 | 重登录后旧轮次按钮不可用；旧轮次不影响新银行状态 | 按公共规则重新授权；旧确认 / 验证不继续放行 | 任务视图在会话变化时会**清空 `allowed_actions`** 并给 `recovery_reason=SESSION_RECONFIRMATION_REQUIRED`（`backend/app/api/service.py:360-366`）；写入口返回 409 同码（`service.py:208-210`） | 通 |
| XL-X08 隐私与可追溯 | 验证码 / 完整账号 / 配送原文只走受控路径；父子关系与操作可追溯；部分成功 / 失败 / 未知 / 资金收尾分别展示 | 同左 | ① 只能用 `display_fields` 的掩码值；② 配送原文只能走 `POST /tasks/{id}/details`（**当前对联动不可达，见 G3**）；③ 不得在聊天 / 日志 / 前端存储里回显原文；④ 部分完成只能来自 `status=partially_succeeded`，不能前端拼 | 掩码通；配送入口不通（G3） |

### 1.4 XL-B01—B07 生日（`evals/cross/representative-cases.md:47-53`）

| 编号 | 用户看到什么 | 系统要保证什么 | 对前端的具体要求 | 今天能否走通 |
|---|---|---|---|---|
| XL-B01 完整 | 预算 500 → 补日期 / 地址 / 账户 → 比较并采用候选 → 逐项确认验证 → 冻结 → 下单 → 按订单核销 → 释放 → 总回执 | 冻结 500、付款 199 / 268、消费 467、释放 33；冻结 / 释放不是消费或收入；不宣称已送达 | ① 商品候选**只能从 `interaction.options[].label` 文本里读**（无结构化商品接口，G10）；② 预算 / 日期是文本输入；③ 配送引用是文本输入；④ 冻结确认必须展示 §3.5 限定释放条款（后端已放进 `display_fields`，`backend/app/agent_platform/birthday_runtime.py:55-70`）；⑤ 订单 / 付款 / 冻结 / 释放要分开显示 | **不通**：预算 / 日期 / 配送引用都是文本 → 400（G2）；配送入口 required_fields 不匹配（G3） |
| XL-B02 缺项 / 只要花 | 只追问必要字段；原文走受控输入；缺信息不下单不冻结；计划可省略蛋糕 | 记忆候选不代替本次采用 | 商品选择是"继续加 / 就选这些"的菜单；"蛋糕已买好"走 `就选这些` 跳过（`backend/app/modules/cross/birthday.py:185-204`） | 同上（文本阻断） |
| XL-B03 超预算 / 涨价 / 不可用 | 程序阻止超额；AI 提替代；旧确认不批准新参数；已成功支出继续占预算 | 旧商品确认不得批准新参数 | 需要展示"原价 → 新价"并重新选择（后端有专门分支 `birthday.py:556-583`） | 阻断同上 |
| XL-B04 部分成功 | 花已付款 199、蛋糕下单失败或未付款；核实无在途后释放 301；已付不退 | 不造订单取消；成功订单不重做；总结果不能报两项都完成 | 结果必须逐项列"已付款 / 未付款 / 下单失败 / 未知"，只能来自 `message` 文本（结构化字段恒 null，G5） | 阻断同上 |
| XL-B05 各阶段未知 | 沿原编号回查；冻结未核实不能下单；订单未核实不能付款；在途未核实不能抢先释放 | 回执与银行 / 订单事实一致 | 未知时父任务仍是 `running`（**不是 `needs_attention`**，`backend/app/modules/cross/birthday.py:756-762`），只能靠 `message` + 菜单选项"核实原操作后再试" | 逻辑有；**故障注入接口不存在（G8）**，页面上无法制造未知 |
| XL-B06 取消 / 安全终止 | 停新购买，按限定授权释放；释放未知 / 失败保留待处理 | 释放未知不能宣称已解冻；只有银行确认后才报金额 | 取消用 `POST /tasks/{id}/cancel`；回执里 `已消费 / 已释放 / 仍冻结` 三个数只能读 `message` | 逻辑有；受 G2 阻断 |
| XL-B07 预算版本 / 月限额 | 刷新后最多新增承诺 300（还要扣占用）；旧 400 不能复用；新版本 / 跨月重新采用 | 未采用预算不伪造采用记录；省略引用不能绕过 | 需要 `budget_ref{budget_id,version}`、`used_fen/remaining_fen` —— **运行期 `CrossTaskView.budget` 恒 null，`CrossStartInput.constraints.budget_ref` 不被消费，`budget_version` 恒 1（G6）** | **不通** |

---

## 2. 接口真相（前端真正能调的 HTTP）

所有路径前缀 `/api/v1`。成功 `{data:T}`，失败 `{error:{code,source,field,reason,upstream_code}}`（【码】`backend/app/api/app.py:105-133`）。

**全局前置条件（容易踩）**：

- 所有 POST 必须带受控 `Origin`，否则 403 `ORIGIN_DENIED`（`backend/app/api/app.py:164-171`）。本机前端来源 `http://127.0.0.1:5173` / `http://localhost:5173` 必须写进 `BANK_API_ORIGINS`（`frontend/LOCAL-DEV.md:26`）。
- 会话 Cookie 名 `bank_session`，HttpOnly + SameSite=strict + path=`/api/v1`，固定 2 小时（`app.py:214-221`）。
- 所有会改状态的 POST 必须带 `request_id:UUID`；同号同内容重放返回原响应，同号异内容 409（`app.py:192-212`）。
- 请求体校验失败**不回显原始字段**（`app.py:173-177`）——前端不要指望从 400 里读到用户输入的验证码。

### 2.1 会话与对话

```
POST /api/v1/session/enter
请求: {request_id}
响应: {data: SessionView{session_id,user_display,role:"user"|"admin",demo_round_id,created_at,expires_at}}
定义: backend/app/api/app.py:214-221 ; backend/app/contracts/api.py:26-32
状态: 已接线
```

```
GET /api/v1/session
响应: {data: SessionView}         # 无有效会话 401 AUTH_REQUIRED
定义: backend/app/api/app.py:223-225
状态: 已接线
```

```
POST /api/v1/threads
请求: {request_id}
响应: {data: ThreadView{thread_id,title,created_at,updated_at,demo_round_id}}
定义: backend/app/api/app.py:235-244 ; contracts/api.py:35-40
状态: 已接线
```

```
GET /api/v1/threads?cursor&limit
响应: {data: Page{items:ThreadView[], next_cursor:string|null}}
定义: backend/app/api/app.py:246-249 ; contracts/api.py:60-62
状态: 已接线
```

```
POST /api/v1/threads/{thread_id}/messages     # 202
请求: {request_id, text, untrusted_content?: string(max 8000)}
响应: {data: MessageAccepted{message_id,thread_id,accepted_at,task_id:null}}   # task_id 此刻恒 null
定义: backend/app/api/app.py:251-269 ; contracts/api.py:43-47 ; MessageRequest 见 app.py:59-66
状态: 已接线（**这是创建联动任务的唯一入口**，见 §2.4）
```

```
GET /api/v1/threads/{thread_id}/messages?cursor&limit
响应: {data: Page{items: MessageView{message_id,thread_id,role,text,created_at,task_ids[],report_ids[]}}}
定义: backend/app/api/app.py:271-275
状态: 已接线
```

```
GET /api/v1/threads/{thread_id}/events        # SSE, text/event-stream
事件: StreamEvent{event_id,thread_id,session_id,task_id,run_id,module,event_type,occurred_at,payload}
event_type: message_delta | message_completed | task_updated | interaction_required
          | report_ready | session_expired | stream_error
定义: backend/app/api/app.py:592-615 ; contracts/api.py:216-242
状态: 已接线；`task_updated.payload` 是完整 TaskView（含 module/data）
```

### 2.2 任务（列表 / 详情 / 父子 / 历史）

```
GET /api/v1/tasks?thread_id&recovery_required&cursor&limit
响应: {data: Page{items: TaskView[], next_cursor}}
定义: backend/app/api/app.py:289-300
状态: 已接线（跨模块任务都在这里，含 cross 与子任务）
```

```
GET /api/v1/tasks/{task_id}
响应: {data: TaskView}
定义: backend/app/api/app.py:302-304 ; 组装 backend/app/api/service.py:330-366
TaskView 字段(真实名):
  task_id, run_id, status, data, message, interaction, error, allowed_actions[],
  recovery_required, recovery_reason, module, thread_id, demo_round_id,
  snapshot_at, task_revision, cancel_requested
定义: backend/app/contracts/tasks.py:99-107
状态: 已接线。`data` 对 cross 任务是 CrossTaskView 的原始 JSON（见 §3.3 的"空洞"）
```

```
GET /api/v1/tasks/{task_id}/children
响应: {data: TaskView[]}          # 注意：直接是数组，不是 Page
定义: backend/app/api/app.py:306-310 ; backend/app/api/service.py:804-834
行为: 懒注册——第一次调用才把子任务写进 api_tasks，之后 GET /tasks/{child} 才不 404
      (service.py:821-832)；同时子任务也会出现在 GET /tasks 列表里
状态: 已接线；【码】前端 frontend/src/shell/api/realDataSource.ts 没有调用它（前端要补）
```

```
GET /api/v1/tasks/{task_id}/records
响应: {data: TaskRecordsView{task_id, confirmations:ConfirmationView[], verifications:VerificationView[]}}
定义: backend/app/api/app.py:312-314 ; contracts/api.py:153-158 ; service.py:1312-1337
状态: 已接线。**但只按 api_records 里登记过的记录回放**——子任务同样受 G1 影响（大概率空列表）
```

### 2.3 交互：补充输入 / 资料 / 确认 / 验证 / 恢复 / 取消 / 查询

```
POST /api/v1/tasks/{task_id}/inputs
请求: {request_id, interaction_id, text?: string, selected_option_id?: string}  # 二者至少一项
响应: {data: TaskView}
定义: backend/app/api/app.py:338-344 ; contracts/api.py:79-89 ; service.py:1549-1595
状态: 已接线，但按 module 分支：
  - module=subscription：selected_option_id / required_fields=["merchant_hint"] 的 text 可用
  - 其它（含 **cross**）：selected_option_id 可用（回 {"choice": id}）；
    **text 一律 400 USE_CURRENT_INPUT_FIELDS**（service.py:1595）
  - required_fields 只识别 ["amount_fen"] ["payee_hint"] ["payer_account_id"] 三种文本形态
⇒ 联动父任务的 required_fields 恒为 ["cross_selection"]（entry.py:130），所以只能点选项，不能打字
```

```
POST /api/v1/tasks/{task_id}/details
请求: {request_id, interaction_id, kind:"payee"|"payee_search"|"delivery", fields:{...}}
  delivery.fields = {recipient_name, phone, address}
响应: {data: {detail_ref, display_fields:DisplayField[], candidates:PayeeCandidate[]|null, task:TaskView}}
定义: backend/app/api/app.py:393-441 ; contracts/api.py:102-130
状态: delivery 分支要求**当前交互 required_fields == ["delivery"]**（app.py:398-403）
      ⇒ 联动生日父任务的 required_fields 是 ["cross_selection"]，调不通（G3）
```

```
GET /api/v1/confirmations/{confirmation_id}
响应: {data: ConfirmationView}
定义: backend/app/api/app.py:443-445 ; contracts/security.py:117-124
状态: 已接线；**先按 api_records 找 task_id，找不到就 404 NOT_FOUND**（service.py:853-857）
```

```
POST /api/v1/confirmations/{confirmation_id}/answer
请求: {request_id, confirmation_version:int>0, choice:"approve"|"cancel"}
响应: {data: TaskView}
定义: backend/app/api/app.py:447-457 ; contracts/api.py:133-136
校验: 任务当前 interaction.record_ref 必须等于该 confirmation_id 且 decision=="pending"，
      否则 409 CONFIRMATION_STALE（app.py:450-453）
状态: 已接线（父任务自己的确认卡可用；子任务受 G1 影响）
```

```
GET /api/v1/verifications/{challenge_id}
响应: {data: VerificationView}
定义: backend/app/api/app.py:459-461 ; contracts/security.py:211-223
状态: 已接线（同样依赖 api_records，G1）
```

```
POST /api/v1/verifications/{challenge_id}/code
请求: {request_id, submission_id:UUID, code:string}
响应: {data: {kind:"verified"|"rejected"|"error", verification:VerificationView, task:TaskView, error:ModuleError|null}}
定义: backend/app/api/app.py:507-522 ; contracts/api.py:140-150
状态: 已接线。验证码不进聊天/日志；请求体指纹只存 HMAC（app.py:517-522）
```

```
POST /api/v1/verifications/{challenge_id}/resend-code      # 请求 {request_id} → {data: VerificationView}
POST /api/v1/verifications/{challenge_id}/face/start       # 请求 {request_id} → {data: VerificationView}
定义: backend/app/api/app.py:524-547
状态: 已接线；重发**不延长**中风险 code_expires_at，不清零错误次数
```

```
GET /api/v1/verifications/{challenge_id}/demo-code
响应: {data: {challenge_id, code, expires_at}}
定义: backend/app/api/app.py:463-467 ; contracts/api.py:73-76
状态: 已接线，**演示专用**：这是唯一会把验证码明文交给页面的接口，仅可用于"模拟验证码提示区"，
      不得写入聊天、日志、localStorage 或事件；前端现有实现是 30 秒自动隐藏（frontend-inventory.md §2.5）
```

```
POST /api/v1/tasks/{task_id}/resume        # {request_id} → TaskView
POST /api/v1/tasks/{task_id}/cancel        # {request_id} → TaskView
POST /api/v1/tasks/{task_id}/query-result  # {request_id} → TaskView
定义: backend/app/api/app.py:363-391
状态: 已接线。语义：
  - cancel：要求 "cancel" in allowed_actions，否则 409 ACTION_UNAVAILABLE；登记 cancel_requested 后
    对联动父任务等价于 {"cancel": true} → entry._closeout（app.py:374-380）
  - query-result：要求 "query" in allowed_actions，否则 409；联动父任务**只有终态**才有 "query"
    （entry.py:141），运行中 / 未知态父任务不能调 F13
  - resume：创建新 run_id 沿原 task_id 恢复；减支 / 养老金父任务 resume 只是重新 reconcile 后重发同一菜单；
    **生日父任务在等待确认时不要调 resume**（会被当成提交尝试，见 G14）
```

```
POST /api/v1/tasks/{task_id}/actions
请求: {request_id, source_revision, action:"bill_details"|"bill_check"|"bill_range"|"subscription_cancel"|"refresh_query", category?, subscription_id?, transaction_id?, account_id?, month?}
响应: {data: TaskView}    # 新建的"卡片动作"子任务
定义: backend/app/api/app.py:227-233 ; app.py:88-95 ; service.py:239-328
状态: 已接线。**只服务于已成功的账单 / 订阅清单卡片**；不能用来启动联动任务
```

### 2.4 前端拿不到的东西（这一节是重点，别按文档想象）

| 想要的能力 | 现实 | 证据 |
|---|---|---|
| **直接创建联动任务**（传 `CrossStartInput{goal,scenario,constraints}`） | 没有 HTTP 入口。`cross.start_task` 不在 `_SELECTED_CAPABILITIES`，`POST /tasks/{id}/actions` 起不来；只能 `POST /threads/{id}/messages` 发自然语言，由模型选中能力 | 【码】`backend/app/agent_platform/harness.py:50-54`、`:609-612`；`backend/app/api/service.py:239-328` |
| **`CrossStartInput.constraints` 预填** | 运行期完全不读。`entry.start` 只取 `goal` / `scenario`，`_new_state` 不消费 constraints | 【码】`backend/app/modules/cross/entry.py:181-202`、`:204-255` |
| **商品 / 报价**（`Product{product_id,merchant_id,merchant_name,product_name,unit_price_fen,category,earliest_delivery_at}`） | 无 HTTP 接口。页面只能读 `interaction.options[].label` 的拼接文本（形如 `商户·商品 199.00 元`） | 【码】`backend/app/contracts/bank.py:284-301`（模型存在）；`birthday.py:185-204`（只产 label）；`app.py` 无 products 路由 |
| **订单 / 付款状态**（`OrderView{order_id,...,payment_status,payment_transaction_id}`） | 无 HTTP 接口；`CrossStep.order_id / payment_status` 运行期恒 null | 【码】`backend/app/contracts/bank.py:320-341`；`plan.py:148-155` |
| **冻结 / 释放**（`FreezeView{freeze_id,original_amount_fen,captured_total_fen,released_total_fen,remaining_fen,as_of}`） | 无 HTTP 接口；只能从 `message` 文本读 | 【码】`backend/app/contracts/bank.py:265-278`；`birthday.py:767-789` |
| **预算视图 / 预算版本**（`BudgetView` / `BudgetRef`） | `CrossTaskView.budget` 恒 null；`AdoptedBudget` 从未被写入；`budget_version` 硬编码 1 | 【码】`plan.py:159-171`；`birthday.py:314-317` |
| **资金安排视图**（`ArrangementView`） | 有构造方法 `PensionFlow.view()`，但**从不挂到任务视图**（`build_view` 里 `arrangement=None`） | 【码】`pension.py:118-138`；`plan.py:169` |
| **D1 冲突详情**（哪张账户被谁占） | 普通转账只得到 `needs_attention` + `error.code="ARRANGEMENT_CONFLICT"` + `error.source="security"` + `field=null` + **通用暂停文案**；联动侧冲突只给一段菜单文本 | 【码】`transfer/workflow.py:388-394`、`:33-36`；`transfer_runtime.py:834-845`；`pension.py:587-593`；`birthday.py:349-362` |
| **故障注入 / 演示管理**（F25—F32：故障、快进、重置、会话过期） | `app.py` 里**一条 `/admin/demo*` 路由都没有**；只有 F27 人脸作答与 F33—F35 审计 | 【码】`backend/app/api/app.py` 全量路由（214-615）无 admin/demo；契约 §6.8 要求 F25—F32 |

---

## 3. 状态机与卡片字段

### 3.1 任务状态（8 个，全项目唯一枚举）

`backend/app/contracts/common.py:40-48`

```
running | waiting_input | waiting_approval | succeeded | partially_succeeded
| failed | cancelled | needs_attention
```

**联动父任务实际会出现的**（【码】逐个 return 点核对）：

| 状态 | 出现时机 | allowed_actions | data 里能看什么 |
|---|---|---|---|
| `waiting_input` | 父任务自己的菜单（选目标 / 选签约 / 选资金范围 / 输入留存 / 选商品 / 输入预算…） | `["provide_input","cancel"]`（`entry.py:132`） | **减支 / 养老金**：有 `steps`（`_ask_pick` 额外挂了 view，`entry.py:591`）；**生日**：`data: null`（生日所有菜单都直接走 `entry._ask`，`birthday.py:112-113`，不挂 view）；`message` 是菜单正文；`interaction.options[]` 是候选 |
| `waiting_approval` | **只有生日**的冻结 / 下单 / 付款门（`birthday.py:378-384`、`:430-436`、`:601-608`） | `["confirm","cancel"]` 或 `["verify","cancel"]` | `data: null`（注意：这时 `data` 不是 CrossTaskView！） |
| `running` | 已派发子任务在等用户 / 未知待核实 / 正在推进（`entry.py:164-169`） | `["resume","cancel"]` | `steps[]` + `active_step_id` + `interaction_task_id` |
| `succeeded` | 收尾完成（`entry.py:141`） | `["query"]` | `steps[]` + `stop_reason` |
| `partially_succeeded` | 已成功一部分后停止（`entry.py:708`、`:792`；`birthday.py:795`） | `["query"]` | 同上 |
| `failed` | 无法开始 / 签约盘点失败 / 生日端口未装配（`entry.py:171-177`、`:414`、`:377`） | `[]` | `data: null` |
| `cancelled` | 无实际完成即停止（`entry.py:350`、`:751`、`:762`；`birthday.py:754`） | `["query"]` | `steps[]` |
| `needs_attention` | **父任务从不返回**；只在子任务上出现（父任务用 `running` 表示"未知待核实"，`birthday.py:756-762`） | — | — |

> 前端必须接受的现实：**"未知"在联动父任务上不是 `needs_attention`，而是 `running` + 一段"结果待核实"的 message**。不要在父任务上按 `needs_attention` 分支设计 UI。

`allowed_actions` 服务端还会补一条：`query` 存在而 `cancel` 不存在时追加 `cancel`（`service.py:356-359`）。会话变化时清空全部（`service.py:360-366`）。

### 3.2 子任务状态

子任务就是普通任务：`transfer` / `subscription` / `bills` 的 TaskView。联动父任务把子任务状态原样搬运到 `CrossStep.status`（`plan.py:112-141`），`HOLDING = {waiting_input, waiting_approval, needs_attention, running}`，`TERMINAL = {succeeded, failed, cancelled, partially_succeeded}`（`plan.py:37-42`）。

### 3.3 CrossTaskView / CrossStep 的真实字段与"运行期填充情况"

`backend/app/contracts/cross.py:263-332`

```
CrossStep:
  step_id        string         ✅ 填
  action         string         ✅ 填（"transfer.list_accounts" / "subscription.list_subscriptions" /
                                  "bills.summarize" / "subscription.cancel_subscription" /
                                  "transfer.list_payees" / "transfer.start_transfer"）
  child_task_id  string|null    ✅ 派发后填
  status         TaskStatus|null ✅ 子任务状态；未启动为 null
  amount_fen     number|null    ⚠️ 只有退订（签约金额）与转账（转账额）步骤填
  depends_on     string[]       ✅ 填
  operation_id   UUID|null      ❌ 恒 null
  order_id       string|null    ❌ 恒 null
  payment_status "unpaid"|"paid"|null ❌ 恒 null
  result_ref     string|null    ❌ 恒 null
  error          ModuleError|null ❌ 恒 null（build_steps 里硬编码 None）

CrossTaskView:
  scenario        "expense_reduction"|"monthly_arrangement"|"birthday"|"budget"|"income_distribution"|null ✅
  plan_revision   int>0          ✅（增补步骤时 +1；生日恒 1）
  steps           CrossStep[]    ✅（生日只有 1 条 accounts 只读步骤）
  budget          BudgetView|null ❌ 恒 null
  summary         string         ✅ 等于 message
  plan_step_ids   string[]|null  ✅
  active_step_id  string|null    ✅ 仅在 holding 时有值
  interaction_task_id string|null ✅ 仅在 holding 时有值（**前端靠它路由到子任务**）
  arrangement     ArrangementView|null ❌ 恒 null
  stop_reason     "user_cancelled"|"security_blocked"|"business_failure"|null ✅
定义: backend/app/contracts/cross.py:263-332 ; 填充: backend/app/modules/cross/plan.py:144-171

**重要例外**：生日场景的**所有 `waiting_input` / `waiting_approval` 结果 `data` 都是 `null`**（`birthday.py:112-113` 的 `_ask` 直接返回 `entry._ask`，不挂 view；`_gate` / `_verify_wait` 也是 `data=None`）。只有终态 `_done` 和未知态的 `_view` 才带 `CrossTaskView`。所以生日页在办理过程中**不能靠 `data.steps` 渲染进度**，只能靠 `message` + `interaction.options`。
```

### 3.4 确认卡（`ConfirmationView`）

`backend/app/contracts/security.py:117-124`

```
confirmation_id      string
task_id              string
confirmation_version int>0        # 提交时必须回传；旧版本 409 CONFIRMATION_STALE
display_fields       DisplayField[] (min 1)   # DisplayField{name,label,value_text}
created_at           Timestamp
expires_at           Timestamp     # 契约 §4.1：确认单有效期 1 小时
decision             "pending"|"approved"|"cancelled"|"expired"|"superseded"
```

- **没有** `max_attempts` / `remaining_attempts` 字段；确认单只有 `expires_at` + `decision`。
- 冻结确认的 `display_fields` 会额外带 §3.5 限定释放条款（`backend/app/agent_platform/birthday_runtime.py:55-70` 调用 `with_release_clause`），前端应原样展示、不要截断。
- 生日三次写动作各自一张确认单；连续确认由安全侧放行（#278），前端仍是"一张卡一次点击"。

### 3.5 验证卡（`VerificationView`）

`backend/app/contracts/security.py:211-223`

```
challenge_id              string
task_id                   string
created_at                Timestamp
summary                   VerificationSummary|null   # 基础验证为 null；中风险必有
required_methods          ("code"|"mock_face")[]    # 基础=["code"]；中风险=["code","mock_face"]
code_expires_at           Timestamp
face_started_at           Timestamp|null
face_expires_at           Timestamp|null
code_result               "pending"|"passed"|"failed"|"expired"|"cancelled"
face_result               "pending"|"passed"|"failed"|"expired"|"cancelled"|"not_required"
challenge_status          "pending"|"passed"|"failed"|"expired"|"superseded"|"cancelled"
consecutive_code_failures int >= 0
```

- **剩余尝试次数没有字段**。上限是银行侧硬编码 3 次（`backend/app/services/mock_bank/verification.py:325-326`：`consecutive_code_failures >= 3` 即终止）。前端若要显示"还剩几次"，只能自己用 `3 - consecutive_code_failures` 计算并注明"以服务端为准"；**更稳妥的是只显示"已输错 N 次"**。
- 中风险任一项失败或超时按高风险终止；重发不清零计数、不延长 `code_expires_at`（契约 §4.2）。
- `summary` 里的 `amount_fen` / `payee` / `display_fields` 是"这笔动作"的核对要素，中风险验证页必须展示。

### 3.6 `interaction.required_fields` 的真实取值（前端按它选输入形态）

`backend/app/contracts/tasks.py:18-30`

| 值 | 谁产出 | 前端该怎么答 |
|---|---|---|
| `["cross_selection"]` | **所有联动父任务菜单**（`entry.py:130`） | 只能 `selected_option_id`（`interaction.options[].id`）；打字必 400 |
| `["amount_fen"]` | 转账 / 订阅 / 账单模块 | `text` 为人民币元（"500" / "500 元"），API 转分 |
| `["payee_hint"]` | 转账 | `text` 或候选 `selected_option_id` |
| `["payer_account_id"]` | 转账 | `selected_option_id` 或文本等于选项 id |
| `["merchant_hint"]` | 订阅退订消歧 | `text` |
| `["delivery"]` | **仅**测试构造的任务 | F36 delivery 表单 |

---

## 4. 契约依据（第 6 章及相关章节）

### 4.1 与联动页面直接相关的小节

引用 `docs/contracts/公共契约-2026-09-23.md`。

| 小节 | 规则要点 | 前端必须遵守 |
|---|---|---|
| §3.4（154-167） | 订单创建成功=未付款；只有扣款成功才记已付款；未知先查原操作 | 订单与付款必须两个视觉单元；未知不能显示成"未付款" |
| §3.5（169-179） | 首次冻结确认单展示限定释放条款；结束时只释放未消费余额；释放未知保持待处理 | 冻结确认卡必须完整展示该条款；收尾卡要分"已消费/已释放/仍冻结" |
| §4.1（193-197） | 确认单 1 小时有效；关键内容变化旧确认立即失效；多笔可同屏但逐条确认 | 每张卡带自己的 `confirmation_id + confirmation_version`；不要做"全部批准" |
| §4.2（199-207） | 验证码专用输入；低风险 5 分钟 / 连错 3 次终止；中风险双因子、重发不延时 | 验证码框独立；刷新不延长计时；人脸只能由管理员入口作答 |
| §4.3（209-216） | 低风险记录同会话可复用；中风险只对当前动作 | 不要假设"刚验证过就能直接办下一笔" |
| §5.1（248-271） | `ModuleResult` 外壳、`InteractionRequest`、`allowed_actions` 由状态与权限决定 | 按钮可用性只能来自 `allowed_actions` |
| §5.4（331-353） | `CrossTaskView` / `CrossStep` / `BudgetView` / `BudgetRef` / 占用与版本规则；`ARRANGEMENT_CONFLICT` 口径 | 预算/安排字段按"可能为 null"设计；不要前端算 `remaining_fen` |
| §5.7（386-399） | 各类错误的语义（`waiting_input` 不是失败、`needs_attention` 只查不重发、`SECURITY_BLOCKED` 不绕行） | 错误码→中文文案要集中映射 |
| §6.4（480-500） | 统一信封、HTTP 码、`request_id` 幂等、Cookie/Origin | 见 §2 全局前置条件 |
| §6.5（502-528） | F08—F20、F36、F39；`TaskView` 带 `module`；`ConfirmationView`/`VerificationView`/`VerificationResponse` 字段；"前端不得自行推断放行" | **前端接口清单的正式出处** |
| §6.6（530-544） | SSE 事件类型与断线补齐顺序；按 `task_revision` 拒绝旧快照 | 重连不重发业务动作 |
| §6.7（546-557） | 报告 / 导出（联动页面暂不需要） | — |
| §6.8（559-581） | F25—F35 演示管理（**F25—F32 后端未实现**） | 不要设计"故障开关"页面 |
| §6.11（608-620） | 字段类型一致性补充 | — |

### 4.2 `frontend/src/api.generated.ts` 的生成真相

- **不是 OpenAPI 生成**。生成链是：Pydantic 模型 → JSON Schema → `json-schema-to-typescript`。
  脚本：`frontend/package.json:9`
  `"generate:contracts": "python scripts/generate_contract_schema.py && json2ts --unknownAny --unreachableDefinitions -i .contract-schema.json -o src/api.generated.ts"`
  Python 侧：`frontend/scripts/generate_contract_schema.py`（从 `backend/app/contracts` 直接 import）。
- 白名单是显式的 `PUBLIC_MODELS`（`frontend/scripts/generate_contract_schema.py:46-84`）：只有 transfer / bills / subscription / security / audit / api 的模型，**没有 `app.contracts.cross`**；`TaskView` 还被特化成 `TaskView[TransferTaskView]`（同文件 `:57-58`）。
- 后果（【码】）：`api.generated.ts` 里 `grep Cross|Budget|Arrangement` 只命中 `Module` 枚举与 `ModuleError.source` 里的字符串 `"cross"`；`TaskView.data` 的类型是 `TransferTaskView|null`（`api.generated.ts:786-803`），与联动任务的真实载荷不符。前端 `contracts.ts:37-41` 正是基于这个特化类型导出的（`TransferTaskView`、`TransferReceipt`）。
- **新增接口 / 新类型是否需要重新生成**：需要。任何 `backend/app/contracts/` 的公共模型变化（含新增 `CrossTaskView` 白名单）都必须在装有后端依赖的 Python 环境重跑 `npm run generate:contracts`，否则 `api.generated.ts` 与后端不一致；生成文件禁止手改（`frontend/LOCAL-DEV.md:39-45`）。
- 补 cross 类型的最小改动（前端目录内可做，不需要改后端）：在 `PUBLIC_MODELS` 加 `CrossTaskView / CrossStep / BudgetView / BudgetRef / ArrangementView / CrossScenario / CrossStep[]` 等条目 + 一个 `TaskView[CrossTaskView]`，然后重跑生成；`contracts.ts` 再补导出。

---

## 5. 缺口清单（不要乐观化）

严重度：**P0** = 页面做完也走不通；**P1** = 关键状态无法展示 / 只能退化；**P2** = 体验或一致性缺陷。

### G1【P0】【推】子任务的确认单 / 验证挑战记录无法通过 F14—F17 访问

- 现象：联动父任务派发出的子任务（退订、转账）在等待确认或验证时，页面拿到的是子任务 `GET /tasks/{child}` 里的 `interaction.record_ref`；用这个 id 调 `GET /confirmations/{id}`、`POST /confirmations/{id}/answer`、`GET /verifications/{id}`、`POST /verifications/{id}/code` 会先经过 `record_context()` 查 `api_records` 表，而子任务从未写入该表。
- 证据：
  - `record_context` 只查 `api_records`，无行即 404：`backend/app/api/service.py:853-857`
  - `api_records` 的全部写入点只有 6 处：`app.py:437`（资料）、`app.py:533`（重发验证码）、`service.py:319`（卡片动作）、`service.py:545`（消息作业任务）、`service.py:749`（`publish_task`）、`service.py:794`（配送资料）
  - `child_tasks()` **只写 `api_tasks`**，不写 `api_records`：`backend/app/api/service.py:821-832`
  - 父任务的 `publish_task` 只会登记父任务自己的 `interaction.record_ref`，而联动父任务在子任务等待时 `interaction` 为 `None`：`entry.py:158-169`
- 影响：XL-S01 / XL-P01 的"逐项确认 + 验证"、XL-B01 之外的**所有子任务级敏感动作**在页面上都打不开确认卡（只有 `prompt` 文本，没有 `display_fields` 金额/收款人/生效日），也无法提交确认。
- 票据状态：`v05-cross-platform/04` 的验收项写的是"确认/验证/输入走子任务通用路径"，但该票测试只覆盖了 `inputs`（`backend/app/api/test_parent_child_api.py:179-192`），**没有一条用例走子任务的确认或验证**。⇒ 票据声称【票】与代码路径【码】不一致，需实机复核后回填。
- 建议：这是平台（`backend/app/api/`）缺陷，前端不要绕。修复方向是在 `child_tasks()`（或首次看到子交互处）把子任务的 `interaction.record_ref` 按 kind 登记进 `api_records`。

### G2【P0】【码】联动父任务不接受任何文本回答（金额 / 日期 / 配送引用全部 400）

- 现象：`POST /tasks/{id}/inputs` 带 `text` 打到 cross 任务 → `400 USE_CURRENT_INPUT_FIELDS`。
- 证据：`backend/app/api/service.py:1549-1595`（只识别 subscription、`selected_option_id`、`["amount_fen"]`、`["payee_hint"]`、`["payer_account_id"]`，其余落到 1595 行 400）；联动父任务 `required_fields` 恒为 `["cross_selection"]`（`backend/app/modules/cross/entry.py:130`）。
- 但模块本身是支持文本的：`entry.py:297-309`（`response["text"]` → `PensionFlow.apply_text` / `BirthdayFlow.apply_text`）、`pension.py:512-550`、`birthday.py:301-345`。**模块能收，API 层不给过**。
- 影响：养老金留存额 / 每笔金额（`pension.py:326-331`、`:373-378`）、生日预算 / 日期 / 配送引用（`birthday.py:170-183`）全部无法从页面提交；`apply_text` 里"口述 5000 与银行 4800 不一致"的纠错（`pension.py:530-548`）也无法触发。
- 结论：XL-P01、XL-B01—B06 的页面今天无法真正办理；XL-S01 因全是选项式菜单而**可以**进行（除了 G4 的证据缺失）。
- 建议：平台侧给 `input_response` 增加 cross 分支（把 `text` 原样回 `{"text": ...}`，模块自己会校验）；或后端把金额/日期问题改成带候选的选项。**不要**在前端模拟"输金额"再转成聊天消息——聊天路径最终也走同一个 `input_response`（`service.py:616`），一样 400。

### G3【P0】【码】配送受控入口（F36 delivery）对联动任务不可达

- 现象：`POST /tasks/{id}/details` 的 delivery 分支要求 `pending.interaction.required_fields == ["delivery"]`，而联动生日父任务是 `["cross_selection"]`，直接 `409 DETAILS_NOT_REQUESTED`。
- 证据：`backend/app/api/app.py:398-403`；`backend/app/modules/cross/birthday.py:178-183`（用 `entry._ask` 生成菜单，required_fields 是 `cross_selection`）；`backend/app/api/test_delivery_details.py:20-28` 用的是**手工构造的 `required_fields=["delivery"]` 任务**，不是真实联动任务。
- 影响：XL-B02 / X05 / X08 的"配送原文走专用受控入口"没有可用入口；生日流程连 `delivery_ref` 都拿不到（`birthday.py:330-344` 需要用户回填引用编号，而回填本身又撞 G2）。
- 建议：要么平台给 cross 任务一个真正的 `required_fields=["delivery"]` 输入交互，要么在 F36 放开"任务确实是生日流程且当前阶段=delivery"的判定。前端不要自建明文表单。

### G4【P0】【码】账单类型化入口未通 → 减支无账单证据、养老金无"实际入账"口径

- 现象：`cross` 用 `BillSummarizeInput(scope=..., mode=...)` 派发 `bills.summarize`（`backend/app/modules/cross/entry.py:460-476`），`harness.dispatch_child` 也允许这个类型（`backend/app/agent_platform/harness.py:962-970`），但账单入口只接受 `StartTransferInput`，其它一律 `fail(INVALID_ARGUMENT)`。
- 证据：`backend/app/modules/bills/entry.py:257-260`；`backend/app/modules/bills/service.py:60-68`（`fail` 返回 `status=failed`）；`backend/app/modules/bills/manifest.py:16-24`（声明的是 `BillSummarizeInput`）。
- 影响：
  - 减支：`bills_compare` 步骤必失败 → `state["bills"]={"ok": False,...}` → 页面只能显示"账单对比暂时不可用，本次结论只基于签约盘点"（`entry.py:504-519`、`:605-623`）。XL-S01 的"原因有账单证据"无法满足。
  - 养老金：`bills_details` 必失败 → `_income_transactions()` 返回 `[]` → 资金范围菜单里**永远没有"本月实际入账合计"**，只能选"当前可用余额"（`pension.py:81-87`、`:304-324`）。XL-P01 的 5000 元入账口径无法复现。
- 票据：已登记为遗留（`docs/01-项目跟踪.md:30`、`:32`、`:123`；`docs/versions/v0.5.0/completion.md:14`；`.scratch/v05-cross-platform/issues/05-cross-runtime-wiring.md:47`）。【票】+【码】一致。
- 建议：账单侧补 `BillSummarizeInput` 分支（或 cross 改回用 `intent_text` 派发）。前端在修复前不要设计"账单证据卡"的必现态，要设计"证据不可用"的降级态。

### G5【P1】【码】`CrossTaskView` 结构化字段大面积恒空

- 见 §3.3。`arrangement`、`budget`、`order_id`、`payment_status`、`operation_id`、`result_ref`、`error` 全部不填；生日 `steps` 只有 1 条只读步骤。
- 影响：生日页无法做"订单 / 付款 / 冻结 / 释放"的结构化表格，只能渲染 `message` 文本；养老金页拿不到 `ArrangementView`（`base_fen / living_reserve_fen / protected_fen / distributable_fen / known_debits_fen / facts_as_of / adopted`）。
- 建议：前端按"文本为主 + 步骤状态为辅"设计；把"要结构化"作为对后端的需求写进票据，而不是前端自己从文本里正则解析。

### G6【P0】【码】生日预算引用 / 版本未接线

- 现象：`budget_id` 由前端式拼接 `bud_{user}_{YYYY-MM}`、`budget_version` 恒 1（`backend/app/modules/cross/birthday.py:314-317`）；`CrossStartInput.constraints.budget_ref` 不被读取（`entry.py:181-202`）；没有任何 `AdoptedBudget` 写入（全仓库仅 `contracts/cross.py` 定义与 `storage/application.py:739-782` 的 arrangement 写入，budget 采用记录无写入点）。
- 影响：XL-B07（月限额 3000 / 已用 2600 / 新增 100 → 最多再承诺 300；改版本 / 跨月重新采用）无法演示；页面也没有 `BudgetView` 可显示。
- 票据：`v05-cross-business/issues/03-birthday-orchestration.md:78` 已如实登记（"budget_ref/budget_fen/deliver_by/delivery_ref 尚未接线""budget_version 恒 1"）。【票】+【码】一致。

### G7【P1】【码】D1 冲突的呈现口径不完整

- 现象：普通转账被 D1 挡住时，任务 `status=needs_attention`、`error.code=ARRANGEMENT_CONFLICT`、`error.source="security"`、`error.field=null`、`error.reason` 是**通用暂停文案**（"这笔转账先暂停…安全核对这次没有做完"），而不是 D1 的专用文案（"该付款账户已有正在办理的联动资金安排…"）；`allowed_actions=[]`。
- 证据：`backend/app/modules/transfer/workflow.py:388-394`（`_fail(reason_codes[0], "security", _PAUSE_MESSAGE...)`）、`:33-36`（`_PAUSE_MESSAGE`）、`:571-585`（`allowed_actions` 只有 OPERATION_UNKNOWN/PROCESSING 才给 `query`）；平台侧正确的 D1 文案在 `backend/app/agent_platform/transfer_runtime.py:834-845` 但没被透传。
- 影响：页面只能显示"暂停 + 无按钮"，用户不知道该去结束哪份安排。XL-X03 的"D1 冲突提示"不达标。
- 票据：`.scratch/v05-cross-platform/issues/03-child-task-dispatch.md:75` 已登记为已知偏差（"需转账模块 PAUSE 分支透传 message/source/field"）。【票】+【码】一致。

### G8【P1】【码】故障模拟装配缺失（未知分支无法在页面复现）

- 现象：契约 §6.8 的 F25—F32（`GET /admin/demo`、`POST /admin/demo/faults`、`advance-time`、`reset-preview`、`reset`、`sessions/{id}/expire`、`operations/{id}`）在 `app.py` 里**一条都没有**；`arm_response_loss` 只在单测里用。
- 证据：`backend/app/api/app.py:214-615` 全量路由（只有 `/admin/verifications/{id}/face-result` 与 `/admin/audit/*`）；`.scratch/v05-cross-platform/issues/09-birthday-runtime-wiring.md` 残留段："B28 演示故障配置未装配（`arm_response_loss` 仅单测使用）"。
- 影响：XL-B05（各阶段未知）、XL-S05、XL-P05、XL-X04 的"未知 → 回查"只能靠后端单测证据，页面演示无法制造；`v05-cross-frontend/issues/02-birthday-ui.md:73` 已要求"未知故障尚未装配时记录该层 blocked"。
- 建议：前端把"未知"做成可走查的静态状态（Gallery），并在联调记录里标 blocked，不要用假数据冒充。

### G9【P1】【码】前端契约类型缺 cross（生成链需要改脚本）

- 见 §4.2。`api.generated.ts` 无 `CrossTaskView` / `BudgetView` / `ArrangementView`，且 `TaskView.data` 被定型为 `TransferTaskView`。前端要在 `TaskBlock` 里读 `data.steps` 必须 `as` 断言或先补生成。

### G10【P1】【码】商品 / 报价 / 订单 / 冻结 / 释放没有结构化出口

- 见 §2.4。页面只能从 `interaction.options[].label` 读商品文本（`birthday.py:192-194`），从 `message` 读订单/资金结论（`birthday.py:767-789`）。
- 影响：XL-B01 的"冻结 500 / 消费 467 / 释放 33"三数只能显示为一段文字；无法做"每件商品一行 + 单价 + 合计"的表格。
- 建议：前端设计以"文本回执 + 分组标题"为主；若产品要求表格，需向生日票据提结构化需求（把 `OrderView` / `FreezeView` 摘要放进 `CrossTaskView.steps`）。

### G11【P2】【码】前端数据源未接 `/children`、未接 delivery 表单

- `frontend/src/shell/api/realDataSource.ts:24-106` 有 16 个方法，**没有 `listChildren`**，`submitPayeeDetails` 走的是 F36 的 payee 分支，没有 delivery 形态；`ShellDataSource`（`frontend/src/shell/types.ts:49-84`）也没有对应可选方法。属前端自己的工作量，不是后端缺口。

### G12【P2】【码】文档漂移：`backend/app/api/README.md` 的"前端入口"表未收录 `/tasks/{id}/children`

- `backend/app/api/README.md:39-58` 的表里没有 children（该端点由 #259 新增）。前端若以 README 为准会漏掉唯一的父子接口。以本报告 §2.2 为准。

### G13【P2】【码】`task_view` 的 "query 时补 cancel" 规则对联动无实际作用

- `service.py:356-359` 只在 `query` 存在且 `cancel` 不存在时补 `cancel`；联动父任务终态只有 `["query"]`，于是终态父任务会得到 `["query","cancel"]`，而 `cancel` 在终态会走 `_closeout`（幂等重放终态）。前端不要在终态展示"取消"。

### G14【P2】【推】生日等待确认态若被"恢复/继续"调用，会被当成批准或被当成非法输入

两处独立的状态机缺陷，都在 `backend/app/modules/cross/`：

1. **`resume` 被当成 `approve`**：`entry._respond` 对生日场景把 `choice in {"approve","cancel","resume"}` 一律交给 `BirthdayFlow.answer_gate`（`entry.py:281-296`），而 `answer_gate` 只排除 `cancel`，其余只要 `b["pending"]` 存在就 `_submit`（`birthday.py:394-410`）。也就是说 `POST /tasks/{id}/resume`（F11 发的是 `{"choice":"resume"}`，`app.py:385-387`）会直接尝试提交冻结/下单/付款。真实安全门会因确认未批准而拒绝（`birthday_runtime.py:388-416` 只把 `REQUIRE_VERIFICATION` 映射成 `verify_wait`，其余非 ALLOW 都落到 `state="failed"`），所以**钱不会动**，但任务会被判成失败并进入收尾，用户手里那张待确认卡就废了。
2. **非选项回答会让生日父任务 503**：`_reask` 在无 holding 时直接调 `_ask_pick`（`entry.py:324-335`），而 `_ask_pick` 会遍历 `state["inventory"]`（`entry.py:537-546`）；生日状态的 `inventory` 恒为 `None`（`entry.py:222-227`）→ `TypeError` → `problem()` 兜底成 503 `DEPENDENCY_UNAVAILABLE`（`app.py:105-118`）。

- 可达性（如实）：**当前前端不会触发**。`useConversation.resume()` 只在 `task.recovery_required` 为真时才调 F11（`frontend/src/shell/useConversation.ts:622-629`），生日父任务从不返回 `recovery_required`；等待态的 `allowed_actions` 也没有 `resume`。所以这是"手写请求 / 未来加按钮"才会踩到的坑。
- 建议：前端**不要**在生日 `waiting_approval` 上放"继续/恢复"按钮；后端应让 `answer_gate` 只接受 `approve`，并给 `_reask` 加 birthday 分支。

---

## 6. 安全与隐私约束（真实实现位置）

| 约束 | 实现 | 证据 |
|---|---|---|
| 配送原文只走专用受控入口，绝不进聊天 / SSE / 检查点 | 路由只接受 `kind="delivery"` 且交互匹配；原文写入受控存储，返回一个 `detail_ref` + 掩码字段 | `backend/app/api/app.py:393-403`；`backend/app/api/service.py:778-802`；`backend/app/storage/application.py:917-...`（`store_controlled_detail`，`kind` 只允许 delivery/payee/payee_search，同 ref 内容不一致拒绝） |
| 掩码规则（收件人 / 电话 / 地址） | 收件人保留首字 + `*`；电话 `****` + 后四位；地址前两字 + `****` | `backend/app/api/service.py:764-776`（`_masked_delivery_fields`） |
| 引用绑定用户 + 轮次 + 任务 | `get_controlled_detail(user, round, ref, task_id=...)` 三重校验；生日流程用父任务 id 取 | `backend/app/modules/cross/birthday.py:334-341`；`backend/app/api/test_delivery_details.py:75-79`（跨用户 / 跨轮次解析为 None） |
| 聊天文本里的凭据前置拦截 | `has_chat_secret()` 命中即 400 `USE_VERIFICATION_ENDPOINT`；落库前 `redact()` | `backend/app/api/service.py:71-77` |
| 助手回复里的凭据整条拦截（不是部分打码） | `OUTPUT_BLOCKED_REPLY` 整条替换 | `backend/app/api/service.py:93-97`；`backend/app/audit/output_guard.py` |
| 外部粘贴资料只作数据、不作指令 | `untrusted_material()` 只脱敏；带资料的候选一律拒绝 | `backend/app/api/service.py:80-90`；`backend/app/agent_platform/harness.py:646-649` |
| 验证码不落盘、不回显 | 请求体指纹里存的是 HMAC；`SecretStr` 掩码；校验失败不回显字段 | `backend/app/api/app.py:173-177`、`:517-522`；`backend/app/contracts/api.py:140-143` |
| 验证码 / 人脸明文只给"演示提示区" | `GET /verifications/{id}/demo-code` 单独端点 | `backend/app/api/app.py:463-467` |
| 禁止前端推算余额 / 授权有效性 / 可执行性 | 契约明文；后端 `allowed_actions` 由状态 + 权限生成；会话变化清空 | 契约 §6.5（`docs/contracts/公共契约-2026-09-23.md:522`）；`backend/app/api/service.py:330-366`；前端侧同一口径见 `frontend-inventory.md` §5.3 |
| 确认 / 验证只能走专用入口，聊天说"确认"不算 | 消息路径不创建确认；`ContinueProposal` 只允许 `allowed_actions` 内的动作 | `backend/app/agent_platform/harness.py:326-357`；`backend/app/api/README.md:60-62` |
| 会话失效后旧按钮失效 | 任务视图清空 `allowed_actions` + `SESSION_RECONFIRMATION_REQUIRED`；写入口 409 同码 | `backend/app/api/service.py:201-211`、`:360-366` |
| 未知不重复提交 | 子任务未知 → `needs_attention`，只给 `query`；父任务未知 → `running` + 菜单"核实原操作后再试" | `backend/app/modules/cross/birthday.py:587-612`、`:614-671`；`backend/app/modules/transfer/workflow.py:580-585` |

**前端绝不可做的四件事**（契约 + 代码都指向同一结论）：

1. 不用 `demo-code` 之外的地方显示验证码；不要把 `demo-code` 结果写进 localStorage / 日志 / 聊天。
2. 不把配送原文（姓名 / 电话 / 地址）放进聊天消息、任务 `message`、错误上报或前端持久化。
3. 不用"余额 - 已转出"自己算剩余、不用"确认过 = 已授权"自己推导按钮可用。
4. 不在收到 `needs_attention` / `recovery_required` 时自动重发写动作。

---

## 7. 前端可直接依赖的接口清单（一行一个）

| # | 方法 + 路径 | 用途 | 状态 |
|---|---|---|---|
| 1 | `POST /api/v1/session/enter` | 进入演示会话 | ✅ 已接线 |
| 2 | `GET /api/v1/session` | 读当前会话（401 = 需重进） | ✅ |
| 3 | `POST /api/v1/threads` | 新对话 | ✅ |
| 4 | `GET /api/v1/threads` | 对话列表 | ✅ |
| 5 | `POST /api/v1/threads/{id}/messages` | 发消息（**创建联动任务的唯一入口**，202） | ✅ |
| 6 | `GET /api/v1/threads/{id}/messages` | 消息历史 | ✅ |
| 7 | `GET /api/v1/threads/{id}/events` | SSE（7 类事件） | ✅ |
| 8 | `GET /api/v1/tasks` | 任务 / 待恢复列表 | ✅ |
| 9 | `GET /api/v1/tasks/{id}` | 任务快照（联动父任务的 `data` = CrossTaskView） | ✅ |
| 10 | `GET /api/v1/tasks/{id}/children` | 父任务的真实子任务（`data` 是数组） | ✅ 后端有，前端未接 |
| 11 | `GET /api/v1/tasks/{id}/records` | 该任务的确认 / 验证历史 | ✅（子任务受 G1） |
| 12 | `POST /api/v1/tasks/{id}/inputs` | 答菜单（**仅 selected_option_id 对联动有效**） | ⚠️ 文本 400（G2） |
| 13 | `POST /api/v1/tasks/{id}/details` | 资料表单（payee / payee_search / delivery） | ⚠️ delivery 对联动不可达（G3） |
| 14 | `GET /api/v1/confirmations/{id}` | 确认卡 | ⚠️ 子任务受 G1 |
| 15 | `POST /api/v1/confirmations/{id}/answer` | 提交确认（带 `confirmation_version`） | ⚠️ 同上 |
| 16 | `GET /api/v1/verifications/{id}` | 验证卡 | ⚠️ 同上 |
| 17 | `POST /api/v1/verifications/{id}/code` | 提交验证码 | ⚠️ 同上 |
| 18 | `POST /api/v1/verifications/{id}/resend-code` | 重发 | ✅ |
| 19 | `POST /api/v1/verifications/{id}/face/start` | 开始模拟人脸 | ✅ |
| 20 | `GET /api/v1/verifications/{id}/demo-code` | 演示验证码（仅提示区） | ✅ |
| 21 | `POST /api/v1/tasks/{id}/resume` | 恢复 / 重新核对（**生日等待确认态别用**，G14） | ✅ |
| 22 | `POST /api/v1/tasks/{id}/cancel` | 停止未执行部分 | ✅ |
| 23 | `POST /api/v1/tasks/{id}/query-result` | 只查原操作（父任务仅终态可用） | ✅ |
| 24 | `POST /api/v1/tasks/{id}/actions` | 账单 / 订阅卡片的子任务动作（**不能起联动任务**） | ✅ |
| 25 | `POST /api/v1/admin/verifications/{id}/face-result` | 管理员答人脸（管理端页面） | ✅ |
| 26 | `GET /api/v1/admin/audit/events`、`GET .../{event_id}` | 管理端时间线 | ✅ |

**明确不存在**：`/products`、`/orders`、`/freezes`、`/releases`、`/budgets`、`/arrangements`、`/admin/demo/*`、任何 `cross/*` 路径。

---

## 8. 建议的一次性实机验证（写报告前我没跑，建议前端/联调同学各跑一遍）

按顺序做，每步都能证伪本文的一条推断：

1. **G1**：起 `app.agent_platform.local_demo:create_local_app`，发"帮我处理不用的扣费"，选中一项退订，然后 `GET /tasks/{parent}/children` → `GET /tasks/{child}` → 用 `interaction.record_ref` 调 `GET /confirmations/{id}`。**预期 404**；若返回 200 则 G1 不成立，请回填本报告。
2. **G2**：对联动父任务（资金范围那一步）`POST /tasks/{id}/inputs {"text":"1500元"}`。**预期 400 `USE_CURRENT_INPUT_FIELDS`**。
3. **G3**：对生日父任务在 `delivery` 阶段 `POST /tasks/{id}/details kind=delivery`。**预期 409 `DETAILS_NOT_REQUESTED`**。
4. **G4**：同上第一条流程，看 `GET /tasks/{parent}` 的 `data.steps[]` 里 `bills.summarize` 那条 `status`。**预期 `failed`**，父任务 message 出现"账单对比暂时不可用"。
5. **G7**：让一个联动养老金安排处于 active（`arrangements` 表有记录），再从聊天发起一笔同账户普通转账并走完确认 + 验证。**预期 `needs_attention` + `ARRANGEMENT_CONFLICT` + 通用暂停文案 + `allowed_actions=[]`**。

---

## 附录 A · 字段字典（真实字段名，供前端建模）

### A.1 `CrossTaskView` / `CrossStep`

见 §3.3（`backend/app/contracts/cross.py:263-332`）。

### A.2 `ArrangementView`（运行期不暴露，仅供参考）

`backend/app/contracts/cross.py:196-229`

```
arrangement_id, plan_revision, payer_account_id, funds_basis("available_balance"|"selected_income"),
income_transaction_ids[], base_fen, living_reserve_fen, reserve_includes_known_debits,
upcoming_debit_scope(BillScope), known_debits_fen, protected_fen, distributable_fen,
facts_as_of, adopted
等式: protected_fen = living_reserve_fen + (0 或 known_debits_fen)
      distributable_fen = base_fen - protected_fen
```

### A.3 `BudgetView` / `BudgetRef` / `BudgetCommitment`（运行期不暴露）

`backend/app/contracts/cross.py:43-109`

```
BudgetRef{budget_id, version}
BudgetView{budget_ref|null, purpose, scope, personal_limit_fen, used_fen, remaining_fen,
           facts_as_of, adopted}
  - remaining_fen 必须等于 personal_limit_fen - used_fen（模型校验）
  - adopted=true 必须带 budget_ref；adopted=false 必须不带
BudgetCommitment{budget_ref, task_id, commitment_id, committed_fen, unconsumed_fen,
                 freeze_id|null, operation_ids[], settled_transaction_ids[],
                 state("pending"|"active"|"unknown"|"closed"), updated_at}
```

### A.4 银行侧生日模型（无 HTTP 出口）

`backend/app/contracts/bank.py:215-341`

```
FreezeFundsInput{account_id, amount_fen, reason}
FreezeReceipt{freeze_id, frozen_amount_fen, remaining_fen, balance}
CaptureFrozenInput{freeze_id, amount_fen, merchant_id, merchant_name, purpose, category, order_id|null}
CaptureReceipt{transaction_id, freeze_id, captured_amount_fen, remaining_fen, balance}
ReleaseFrozenInput{freeze_id, amount_fen}
ReleaseReceipt{freeze_id, released_amount_fen, remaining_fen, balance}
FreezeView{freeze_id, account_id, original_amount_fen, captured_total_fen,
           released_total_fen, remaining_fen, as_of}
ListProductsInput{merchant_id|null, purpose|null, deliver_by|null}
Product{product_id, merchant_id, merchant_name, product_name, unit_price_fen, category, earliest_delivery_at}
DeliveryInput{recipient_name, phone, address, deliver_by}     # repr 隐藏原文
CreateOrderInput{product_id, quantity, expected_total_fen, delivery}
OrderView{order_id, product_id, quantity, merchant_id, merchant_name, total_fen, created_at,
          deliver_by, recipient_name_masked, phone_masked, address_masked,
          payment_status("unpaid"|"paid"), payment_transaction_id|null}
```

### A.5 错误码（前端需要映射成中文的）

来源：`backend/app/api/app.py:105-128`、`backend/app/modules/cross/*`、`backend/app/modules/transfer/workflow.py`、`backend/app/modules/bills/service.py`。

| code | HTTP | 触发场景 |
|---|---|---|
| `AUTH_REQUIRED` | 401 | 会话无效 / 过期 |
| `ACCESS_DENIED` | 403 | 越权 / 他人任务 |
| `ORIGIN_DENIED` | 403 | POST 的 Origin 不在白名单 |
| `NOT_FOUND` / `TASK_NOT_FOUND` | 404 | 本人范围内不存在 |
| `INVALID_ARGUMENT` | 400 | 参数或能力输入不合法（含账单子任务失败） |
| `INVALID_OPTION` | 400 | 选项 id 不属于当前交互（旧菜单） |
| `INVALID_AMOUNT` | 400 | 金额文本非法 |
| `USE_CURRENT_INPUT_FIELDS` | 400 | 该交互不接受这种输入形态（**G2 的落点**） |
| `USE_VERIFICATION_ENDPOINT` | 400 | 聊天里出现凭据 |
| `INTERACTION_STALE` | 409 | `interaction_id` 不是当前交互 |
| `CONFIRMATION_STALE` | 409 | 确认版本 / 记录过期 |
| `ACTION_UNAVAILABLE` | 409 | 该动作不在 `allowed_actions` |
| `SESSION_RECONFIRMATION_REQUIRED` | 409 | 会话变化，需重新确认 / 恢复 |
| `REQUEST_CONFLICT` / `TASK_BUSY` / `STALE_ROUND` | 409 | 幂等冲突 / 并发 |
| `ARRANGEMENT_CONFLICT` | （任务内 `error`） | D1 同账户已有活动资金安排（**G7 文案问题**） |
| `DEPENDENCY_UNAVAILABLE` | 503 | 依赖不可用（含验证故障） |
| `STEP_ALREADY_PLANNED` / `PLAN_SUPERSEDED` / `CHILD_STEP_ALREADY_ACTIVE` | 值错误 | 计划版本 / 单活跃子步骤约束（多为内部错误，页面少见） |
| `FREEZE_WITHOUT_CLAUSE` | 任务内 | 冻结未经带条款的确认，安全侧拒绝 |

---

## 附录 B · 与本文相关的票据索引

| 票 | 内容 | 与本文的关系 |
|---|---|---|
| `v05-cross-platform/03` | 受控子任务衔接 + D1 守卫 | G7 偏差来源 |
| `v05-cross-platform/04` | 父子任务 API（#259） | G1 的声称与实测差距 |
| `v05-cross-platform/05` | 联动主入口装配（#276） | 账单类型化缺口登记处 |
| `v05-cross-platform/08` | 配送受控 API（#263） | G3 |
| `v05-cross-platform/09` | 生日真实装配（#279） | G8（B28 未装配） |
| `v05-cross-business/01` | 减支编排（#269） | 减支菜单与回执 |
| `v05-cross-business/02` | 养老金安排（#268） | 资金范围 / 留存 / D1 |
| `v05-cross-business/03` | 生日编排（#274） | G5 / G6 的如实登记 |
| `v05-cross-frontend/01` | 总方案、子确认与结果页 | 本文的主要消费者 |
| `v05-cross-frontend/02` | 商品、配送与资金收尾页 | G3 / G8 / G10 |
| `docs/01-项目跟踪.md:30,32,123` | 遗留总账 | 账单类型化入口等 |
| `docs/versions/v0.5.0/completion.md:14` | 包 03 回填 | 明确列出未做项 |

---

## 附录 C · 本次盘点未覆盖 / 无法确认

- 真实模型是否会稳定地把三类生活目标路由到 `cross.start_task`（`infer_scenario` 只做关键词匹配，`entry.py:57-67`；模型侧没有测过）。
- SSE 在浏览器（EventSource + SameSite=strict Cookie）下的实际可用性；`api.ts:806-852` 用了 `withCredentials:true`，但契约要求 POST 同源，GET SSE 的 Cookie 行为需实机看。
- `api.generated.ts` 重新生成后的具体 diff（未运行 `npm run generate:contracts`）。
- `CrossStep.amount_fen` 在"退订"步骤上取的是签约金额而非"少扣金额"，页面文案要写清"每月/每年扣费额"，不要写成"已省"（`entry.py:482-483` 用 `item["amount_fen"]`）。
- 生日 `steps` 里没有冻结 / 下单 / 付款步骤，因此 `active_step_id` 在生日流程里恒为 `None`；若前端用"步骤高亮"做导航，生日页会永远没有高亮项。
