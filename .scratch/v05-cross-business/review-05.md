# v05-cross-business/05 执行与交接

执行对话：01a17183-271b-7663-9517-f31a994de51d；日期：2026-10-25。
创建基线：origin/main `4bba921`；随后 rebase 到 `640fe71`（新增仅前端/docs）；
最终再次 rebase 到 `9a479ea`（仍仅前端/docs，cross 实现差异不变）；
分支 `codex/v05-cross-business-05`；仅实施 cross。
主工作区未改动。前端 01、平台 11 与 PR #281/#282 未接管；共享跟踪与 completion 未更新。

## 决定与能力记录

- 已有 spec/票，直接实施。读取本机 implement/code-review；implement 有
  disable-model-invocation，本会话无斜杠调用接口，按文件执行而不声称调用了命令。
  code-review 的规范/原票两轴使用独立子代理。
- 用户 2026-10-25 回答：配送资料“沿用现有失效规则，不新增有效期”。
- 生日上限与已采用个人预算不同。本票不构造 BudgetView，不扩大个人预算采用/版本语义。

## 对前端的最小输入输出

1. `required_fields=["delivery"]` → 受控 `/details` 提交配送原文。
2. `/details` 返回 `detail_ref/display_fields/task`；前端自动用同一交互 `/inputs`
   提交 `text=detail_ref`，不用用户手抄；原文不进 `/inputs`、聊天或模型。
3. `steps[].action=bank.freeze_funds/create_order/capture_frozen/release_frozen`，
   金额、操作、订单与结果引用均取服务回执。`birthday-remaining` 给银行核实的剩余，
   `birthday-consumed` 给收尾服务的消费总额；未知金额为空，不靠前端减法补齐。
4. 停止后只核实原操作与收尾；释放未知/拒绝保留预算占用和非终态。

## 继承缺口与跨目录发现

- G6 仍存在：输入的 `budget_ref` 等未接入；内部个人预算版本固定 1，生日上限与用户月度预算
  的刷新/采用尚未完整落实。本票的事实投影不依赖伪造 BudgetView，但 XL-B07 不因此完成。
  最小交接：有效 AdoptedBudget + 当前账单事实/已有占用 → 核对当前版本/范围 → 接入 birthday plan。
  需要中控明确范围后另派，不在本票另定规则。
- API 潜在缺陷（未改）：`api/service.py:797` 使用 `DetailsResponse[type(view)]`，
  T 应是业务 data 类型，却传了 TaskView 类。最小输入：当前受控 delivery 交互的任务
  `data=CrossTaskView(...)` 非空；`POST /tasks/{id}/details kind=delivery`。
  实际：资料已写受控存储后，响应构造抛 ValidationError（task.data 缺 task_id/status 等且
  scenario/steps 被当作多余字段），HTTP 503 DEPENDENCY_UNAVAILABLE。预期：200 + 掩码/引用。
  本流程配送发生在首次资金动作前，普通输入维持既有 data=None；资金事实出现后才提供视图，
  因此本票 HTTP 测试可走通。若以后支持付款后改配送，必须先修平台响应泛型；交中控另派 API。

## 验证及审查

- 规范轴：独立子代理 review_standards 对 `640fe71...e4ae5a1` 审查 PASS；必须项 0、建议 0。
  未复跑主对话全量测试，不代替真人安全或 PM 验收。
- 原票轴：review_spec 初轮发现 1 项 P2：原冻结已绑定成功，附加回执查询空时，视图仍永久未知。
  `ca2790b` 修复并增加公开 entry 回归；复审 PASS，子代理独立运行该回归 `1 passed in 9.29s`。
  最终 rebase 后同一修复为 `d67b078`。规范轴亦复审 PASS，必须项 0、建议 0。
- 最终 Cross 回归 `57 passed in 84.10s`；本票测试文件 `13 passed in 34.43s`。
  含真实模拟银行（真实网关/安全门/双因子/限定释放，模型未调用）完整与停止两条资金路径，
  与银行 get_freeze 对账；HTTP TestClient 的受控表单/引用自动提交、幂等、旧交互、失效会话，
  越权/跨轮/跨任务引用拒绝，以及未知/拒绝/停止收尾。模拟银行评测 `14 passed in 1.74s`。
- 链接、语法与差异空白检查通过。后端全量 `1600 passed in 973.72s (0:16:13)`。
  全量进程从首次实现版本启动；其后审查发现的冻结事实修复，以最终 Cross 57 项完整回归
  和新增文件 13 项验证，不将审查前的全量结果冒充最终修复后的第二次全量。
  使用项目已有 backend/.venv Python，PYTHONPATH 显式指本 worktree/backend；全局 Python 缺
  langchain_openai 的早期试跑不计有效验证，未安装或改动依赖。未调用真实模型。
- PR [#288](https://github.com/DrErwin/hackerthon-bank-agent/pull/288) 已创建并 attach。
  GitHub Repository checks（run 40167522614，head ca2790b）未启动，原因为账户近期付款失败或
  支出限额需提高；不是 CI 绿，不视作测试通过。由中控处理 CI 门槛和合并排队。
- 真实模型与浏览器 E2E 未运行，真人安全/PM 验收未代签。

## 2026-10-25 主线同步交接

- 中控已确认首批 #270/#285/#287/#288/#289 的 CI 计费阻塞采用本地验证例外；该例外不适用于
  #297。本对话仅准备 #288，不执行合并，也不将例外写成 CI 绿。
- 已 rebase 至 main `421b344a4ef7d2b5f838689e9d2f338f4c4102a4`（含 #270/#285/#287）。
  验证源码提交 `8c247aa0479b670406c97231cbbf101d783528ff`；整个 Cross 目录 tree
  `7d64f1729eef1a0589c7551cf4cd9d893253901e` 与同步前 `ccf3075` 完全一致。
  没有功能修改，按中控授权沿用既有两轴 PASS；PR 差异仍只有 Cross 与本票四份自有材料。
- 单独 #288 配送及生日编排：`32 passed in 32.14s`（当时 main `36f1d66`）。随后同步新增
  转账/审计修复，再用最新 #289 `0c955f13ee165c9bf723a7124e28c06daee8099b` 组合复验：
  配送/生日编排 32 项、平台装配 5 项、停止恢复探针 4 项，**41 passed in 73.64s**。
  精确组合提交 `30a695267c2828aea152957180fd3cd2a4dac331`，Cross 与本票源码完全相同。
- 配送引用仍沿用既有交互、会话、用户/轮次/任务隔离及幂等规则，不新增独立有效期。
  旧版取消缺陷已覆盖，不另做生产修复。没有重启后端全量、真实模型或页面 E2E。
- #297 全量另有 `1591 passed in 818.10s`，审查回修后 Cross 48 项通过；不把前述 CI 例外
  扩到 #297，也不将审查前全量当成最终代码第二次全量。共享进度及最终排队由中控维护。
- #289 合入后最后 rebase 至 main `31e9f2743028e25503ab5894d6af9f72856b1ea8`。
  最终整个 `backend/` 与已通过 41 项的组合 `30a6952` 完全无差异，Cross tree 亦不变；
  按中控指令不重复同一等价组合。本票最后新增仅交接说明，待中控最终合入与页面走查。
