# transfer —— 智能转账

长期归属：梁爽。v0.3 首条普通转账路径由 Erwin 临时实现。

当前提供 `transfer.start_transfer` 的模块清单和普通转账子图。`TransferWorkflow.start()` 接收公共契约 `StartTransferInput` 与可信任务上下文；`resume()` 沿同一 LangGraph checkpoint 继续等待中的任务。平台负责保存持久 checkpoint、核验任务身份、把当前确认与验证记录装入 `ExecutionSecurityContext`。聊天回复中的“确认”不能代替安全确认记录。

`GatewayTransferTools` 只注册和调用本模块列出的私有银行工具。查询及资金提交都经过统一安全门；资金提交由 `DeterministicExecutor` 先领取唯一执行记录。`TransferSnapshots` 保存不可变的动作参数。平台的 `scope_authorizer` 须先核对权限，并对资金工具调用 `TransferWorkflow.is_current_action()`，确保修改金额或收款人后，旧确认无法用于新动作。图节点执行期间该校验使用节点当前状态，节点外则读取 checkpoint，避免保存稍晚时误拒当前操作。银行接入层的 `authorize_transfer` 回调也须核验该次受控执行。

当银行提交结果未知，子图按原操作编号回查，最多再等 10 秒；主动“查询结果”仍只查原操作。查询权限暂时无法核对或被拒绝时，停止本次查询并保留原任务和操作编号；恢复合法访问后可继续查询，不会重新提交转账。未完成的平台 Harness、HTTP/SSE 和前端接线由集成票负责。

依据：[01-智能转账 PRD](../../../../docs/prd/01-智能转账-PRD-2026-09-23.md) §5.3–5.6。后续普通转账之外的公开能力按各自实施票接入。
