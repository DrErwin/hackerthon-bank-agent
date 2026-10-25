# bank_gateway —— 银行系统接入层

归属：底座（Erwin）。

放什么：统一银行接口、协议与格式隔离、可信身份与操作编号传递、结果查询。接缝五判据见架构 §2.1（同进程部署也必须遵守）。

边界：不做业务决策，不含银行规则，不把模型参数当作身份凭证。读写均经本层，用户身份来自服务端建立的 `TrustedContext`。`submit_transfer` 等待银行结果最多 4 秒；超时返回 `CALL_TIMEOUT`，调用方只能按原 `operation_id` 查询，不能视作交易失败或改号重发。普通业务不能直接导入 `storage.mock_bank` 或 `services.mock_bank`；注册和调用限制由后续统一执行器落实。

v0.3 已实现 B01—B07、B09、B14 与验证码／模拟人脸核验接缝。`submit_transfer` 与 `verify_face` 默认拒绝；组装时分别注入服务端授权判定，前者须核对当前身份、确认、验证和具体动作参数，后者须核对管理员身份及目标挑战的用户、会话、任务与轮次。后续安全执行器和管理入口负责提供判定；不得注入无条件放行函数。模拟码仅由后端专用演示接口从银行验证组件取出，不通过普通 Agent 工具返回。

G2-B 旧尝试退役接缝（v05-birthday-platform-dependencies/06）：`retire_action_challenges(context, *, operation_id, action_revision)` 与只读 `retirement_for(context, operation_id, action_revision)` 只在本层做协议转发——退役事实、同事务判定与原因码都在 `mock_bank`，本层不塞业务判断，也不把内部原因码转成用户文案。
