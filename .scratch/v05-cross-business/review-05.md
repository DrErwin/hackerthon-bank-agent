# v05-cross-business/05 执行与交接

执行对话：01a17183-271b-7663-9517-f31a994de51d；日期：2026-10-25。
基线：origin/main `4bba921`；分支 `codex/v05-cross-business-05`；仅实施 cross。
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

待本轮测试、独立审查与 PR 结果回填。真实模型与浏览器 E2E 未运行，真人安全/PM 验收未代签。
