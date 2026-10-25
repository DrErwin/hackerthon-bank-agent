# cross —— 跨场景联动

归属：周恩宇。

业务：编排面不是业务场景——任务 A 生日安排、任务 B 用户自设限额、任务 C 收入分配（复用 01 转账公开能力）。

依据：[06-跨场景联动 PRD](../../../../docs/prd/06-跨场景联动-PRD-2026-09-23.md)（§3.2 依赖表是本模块向外的全部索取面）。边界：不直连银行数据库、不复制银行规则、不读其他模块私有数据。

开工前提：契约冻结（09-25/26 定稿会）。

## 生日配送与资金回执（v05-cross-business/05）

配送阶段 `interaction.required_fields == ["delivery"]`：页面将原文仅提交
`POST /api/v1/tasks/{id}/details`（`kind="delivery"`）；收到 `detail_ref` 后，
用同一交互的 `/inputs` 自动发送 `text=detail_ref`。用户无需抄编号，聊天不接收配送原文。
重复请求保留原 `request_id`；旧交互、失效会话与跨用户/轮次/任务仍按既有规则拒绝。
2026-10-25 用户确认不新增配送引用独立有效期。

开始有银行写入事实后，等待输入、确认、验证及最终回执均保留 `CrossTaskView.steps`。
页面按 `action` 区分 `bank.freeze_funds`、`bank.create_order`、`bank.capture_frozen`、
`bank.release_frozen`；`amount_fen` 来自对应银行回执，`operation_id/result_ref` 可追溯。
订单的 `order_id/payment_status` 区分创建和付款，付款未知时不填 `paid`。
只读行 `birthday-remaining`（`bank.get_freeze`）给出银行最后核实的未消费冻结金额；
存在未知写入时金额留空。收尾服务返回消费总额时，`birthday-consumed` 同样直接转呈该事实。
释放未知/被拒时不填释放金额、不关闭占用，恢复仅做原操作核实与限定收尾。
`birthday-*` 行是银行事实的展示投影，不注册新工具、不派发新子任务。

个人预算遗留未在本票扩展：`CrossStartInput.constraints.budget_ref` 尚未接入、
内部 `budget_version` 固定 1，因此 `budget` 保持空；不能将本次生日上限伪装成已采用个人预算。
